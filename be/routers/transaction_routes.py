import random
from datetime import datetime, timedelta

from flask import Blueprint, jsonify, request
from flask_cors import cross_origin
from flask_jwt_extended import get_jwt_identity, jwt_required
from models import Account, Transaction, User
from otp import delete_otp_from_db, get_otp_from_db, save_otp_to_db
from service.utils import send_email

transaction_bp = Blueprint("transaction", __name__)
TRANSACTION_LIMIT_PER_TRANSACTION = 10000
TRANSACTION_LIMIT_PER_DAY = 50000
MAX_TRANSACTIONS_PER_DAY = 10

@transaction_bp.route("/api/v1/health-check", methods=["GET"])
def health_check():
    return jsonify({"status": "ok"}), 200


def generate_otp():
    return str(random.randint(100000, 999999))


def send_otp_email(user_id, transaction_type, amount):
    otp = generate_otp()
    expiration_time = datetime.now() + timedelta(minutes=5)

    # Lưu OTP với thông tin giao dịch vào cơ sở dữ liệu
    save_otp_to_db(user_id, otp, expiration_time, transaction_type, amount)

    user = User.get_user_by_id(user_id)
    subject = "Your OTP Code"
    body = f"Dear {user['name']},\n\nYour OTP for the {transaction_type} of {amount} is {otp}. It is valid for 5 minutes."
    send_email(subject, user["email"], body)


@transaction_bp.route("/api/v1/request_otp", methods=["POST"])
@jwt_required()
def request_otp():
    user_id = get_jwt_identity()
    data = request.get_json()
    transaction_type = data.get("transaction_type")
    amount = data.get("amount")
    
    if transaction_type not in ['deposit', 'withdraw', 'transfer'] or not amount or amount <= 0:
        return jsonify({"message": "Invalid transaction type or amount"}), 400

    # Gửi OTP qua email
    send_otp_email(user_id, transaction_type, amount)
    return jsonify({"message": "OTP sent to your email"}), 200


def check_transaction_limits(account_id, amount):
    today_transactions = Transaction.get_today_transactions(account_id)

    # Chỉ tính các giao dịch rút tiền và chuyển tiền
    filtered_transactions = [tx for tx in today_transactions if tx["transaction_type"] in ["withdraw", "transfer"]]
    total_today_amount = sum(tx["amount"] for tx in filtered_transactions)
    transaction_count_today = len(filtered_transactions)

    if amount > TRANSACTION_LIMIT_PER_TRANSACTION:
        return {"message": "Transaction exceeds maximum limit per transaction", "status": "error"}, 400

    if total_today_amount + amount > TRANSACTION_LIMIT_PER_DAY:
        return {"message": "Transaction exceeds maximum limit per day", "status": "error"}, 400

    if transaction_count_today >= MAX_TRANSACTIONS_PER_DAY:
        return {"message": "Transaction limit reached for withdraw/transfer", "status": "error"}, 400

    return None, 200


@transaction_bp.route("/api/v1/deposit", methods=["POST"])
@jwt_required()
@cross_origin()
def deposit():
    user_id = get_jwt_identity()
    data = request.get_json()
    amount = data.get("amount")
    otp = data.get("otp")
    
    otp_record = get_otp_from_db(user_id, "deposit")
    if not otp_record or otp_record['otp'] != otp or datetime.now() > otp_record['expiration_time']:
        return jsonify({"message": "Invalid or expired OTP"}), 400

    account_id = Account.get_account_id_by_user(user_id)
    if not account_id:
        return jsonify({"message": "Account not found"}), 404

    Account.update_balance(account_id, amount, "deposit")
    Transaction.create_transaction(account_id, "deposit", amount)
    
    delete_otp_from_db(user_id, "deposit")

    user = User.get_user_by_id(user_id)
    subject = "Deposit Confirmation"
    body = f"Dear {user['name']},\n\nYou have successfully deposited {amount} into your account."
    send_email(subject, user["email"], body)

    return jsonify({"message": "Deposit successful!"}), 201

@transaction_bp.route("/api/v1/history")
@jwt_required()
@cross_origin()
def transaction_history():
    user_id = get_jwt_identity()
    account_id = Account.get_account_id_by_user(user_id)
    
    if not account_id:
        return jsonify({"message": "Account not found"}), 404

    transactions = Transaction.get_transaction_history(account_id)
    
    if not transactions:
        return jsonify({"message": "No transaction history available"}), 200

    return jsonify({"transactions": transactions}), 200

@transaction_bp.route("/api/v1/withdraw", methods=["POST"])
@jwt_required()
@cross_origin()
def withdraw():
    user_id = get_jwt_identity()
    data = request.get_json()
    amount = data.get("amount")
    otp = data.get("otp")
    
    otp_record = get_otp_from_db(user_id, "withdraw")
    if not otp_record or otp_record['otp'] != otp or datetime.now() > otp_record['expiration_time']:
        return jsonify({"message": "Invalid or expired OTP"}), 400

    if not amount or amount <= 0:
        return jsonify({"message": "Invalid amount!"}), 400

    account_id = Account.get_account_id_by_user(user_id)
    if not account_id:
        return jsonify({"message": "Account not found"}), 404

    error, status_code = check_transaction_limits(account_id, amount)
    if error:
        return jsonify(error), status_code

    balance = Account.get_balance(account_id)
    if balance < amount:
        return jsonify({"message": "Insufficient funds"}), 400

    Account.update_balance(account_id, amount, "withdraw")
    Transaction.create_transaction(account_id, "withdraw", amount)

    delete_otp_from_db(user_id, "withdraw")

    user = User.get_user_by_id(user_id)
    subject = "Withdrawal Confirmation"
    body = f"Dear {user['name']},\n\nYou have successfully withdrawn {amount} from your account."
    send_email(subject, user["email"], body)

    return jsonify({"message": "Withdrawal successful!"}), 201


@transaction_bp.route("/api/v1/transfer", methods=["POST"])
@jwt_required()
@cross_origin()
def transfer():
    user_id = get_jwt_identity()
    data = request.get_json()
    recipient_email = data.get("recipient_email")
    amount = data.get("amount")
    otp = data.get("otp")
    
    otp_record = get_otp_from_db(user_id, "transfer")
    if not otp_record or otp_record['otp'] != otp or datetime.now() > otp_record['expiration_time']:
        return jsonify({"message": "Invalid or expired OTP"}), 400

    sender_account_id = Account.get_account_id_by_user(user_id)
    if not sender_account_id:
        return jsonify({"message": "Sender account not found"}), 404

    error, status_code = check_transaction_limits(sender_account_id, amount)
    if error:
        return jsonify(error), status_code

    recipient = User.verify_user_email(recipient_email)
    if not recipient:
        return jsonify({"message": "Recipient not found"}), 404

    recipient_account_id = Account.get_account_id_by_user(recipient["id"])

    balance = Account.get_balance(sender_account_id)
    if balance < amount:
        return jsonify({"message": "Insufficient funds"}), 400

    Account.update_balance(sender_account_id, amount, "withdraw")
    Account.update_balance(recipient_account_id, amount, "deposit")

    Transaction.create_transaction(sender_account_id, "transfer", -amount)
    Transaction.create_transaction(recipient_account_id, "transfer", amount)

    delete_otp_from_db(user_id, "transfer")

    sender = User.get_user_by_id(user_id)
    subject = "Transfer Confirmation"
    body = f"Dear {sender['name']},\n\nYou have successfully transferred {amount} to {recipient_email}."
    send_email(subject, sender["email"], body)

    body_recipient = f"Dear {recipient['name']},\n\nYou have received {amount} from {sender['email']}."
    send_email(subject, recipient["email"], body_recipient)

    return jsonify({"message": "Transfer successful!"}), 200



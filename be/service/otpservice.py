import random
from datetime import datetime, timedelta
from otp import save_otp_to_db
from utils import send_email


def generate_otp():
    return str(random.randint(100000, 999999))


def send_otp_email(user_id, user_email, transaction_type, amount):
    otp = generate_otp()
    expiration_time = datetime.now() + timedelta(minutes=5)

    save_otp_to_db(user_id, otp, expiration_time, transaction_type, amount)

    subject = "Your OTP Code"
    body = f"Dear User,\n\nYour OTP for {transaction_type} of {amount} is {otp}. It is valid for 5 minutes."
    send_email(subject, user_email, body)

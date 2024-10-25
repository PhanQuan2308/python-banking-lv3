import mysql.connector
from datetime import datetime
from flask import current_app

def save_otp_to_db(user_id, otp, expiration_time, transaction_type, amount):
    connection = mysql.connector.connect(
        host=current_app.config["MYSQL_HOST"],
        user=current_app.config["MYSQL_USER"],
        password=current_app.config["MYSQL_PASSWORD"],
        database=current_app.config["MYSQL_DB"]
    )
    cursor = connection.cursor()
    query = """
    INSERT INTO otp_entries (user_id, otp, expiration_time, transaction_type, amount)
    VALUES (%s, %s, %s, %s, %s)
    """
    cursor.execute(query, (user_id, otp, expiration_time, transaction_type, amount))
    connection.commit()
    cursor.close()
    connection.close()

def get_otp_from_db(user_id, transaction_type):
    connection = mysql.connector.connect(
        host=current_app.config["MYSQL_HOST"],
        user=current_app.config["MYSQL_USER"],
        password=current_app.config["MYSQL_PASSWORD"],
        database=current_app.config["MYSQL_DB"]
    )
    cursor = connection.cursor(dictionary=True)
    query = """
    SELECT * FROM otp_entries 
    WHERE user_id = %s AND transaction_type = %s 
    ORDER BY expiration_time DESC LIMIT 1
    """
    cursor.execute(query, (user_id, transaction_type))
    otp_record = cursor.fetchone()
    cursor.close()
    connection.close()
    return otp_record

def delete_otp_from_db(user_id, transaction_type):
    connection = mysql.connector.connect(
        host=current_app.config["MYSQL_HOST"],
        user=current_app.config["MYSQL_USER"],
        password=current_app.config["MYSQL_PASSWORD"],
        database=current_app.config["MYSQL_DB"]
    )
    cursor = connection.cursor()
    query = "DELETE FROM otp_entries WHERE user_id = %s AND transaction_type = %s"
    cursor.execute(query, (user_id, transaction_type))
    connection.commit()
    cursor.close()
    connection.close()

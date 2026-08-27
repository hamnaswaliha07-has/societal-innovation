import sqlite3
from werkzeug.security import generate_password_hash

connection = sqlite3.connect("database.db")

name = "Admin"
email = "admin@example.com"
password = "Admin@123"
role = "admin"

connection.execute("""
    INSERT INTO users (name, email, password, role)
    VALUES (?, ?, ?, ?)
""", (
    name,
    email,
    generate_password_hash(password),
    role
))

connection.commit()
connection.close()

print("Admin account created successfully!")
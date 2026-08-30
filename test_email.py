import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

# Load .env file with or without python-dotenv
env_dir = os.path.dirname(os.path.abspath(__file__))
env_path = os.path.join(env_dir, ".env")
if not os.path.exists(env_path):
    # Try subfolder
    sub_env = os.path.join(env_dir, "societal-innovation", ".env")
    if os.path.exists(sub_env):
        env_path = sub_env

if os.path.exists(env_path):
    with open(env_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, val = line.split("=", 1)
                key = key.strip()
                val = val.strip().strip('"').strip("'")
                os.environ[key] = val

print("=" * 60)
print("  Societal Innovation Portal - Email & OTP Diagnostics")
print("=" * 60)
print(f"Loaded .env from: {env_path}")

mail_server = os.environ.get("MAIL_SERVER", "smtp.gmail.com")
mail_port_raw = os.environ.get("MAIL_PORT", "587")
mail_username = os.environ.get("MAIL_USERNAME", "")
mail_password = os.environ.get("MAIL_PASSWORD", "")
mail_sender = os.environ.get("MAIL_DEFAULT_SENDER", mail_username)

try:
    mail_port = int(mail_port_raw)
except ValueError:
    mail_port = 587

# Strip any accidental spaces from credentials
mail_username = mail_username.strip()
mail_password = mail_password.strip().replace(" ", "")

print("\nCurrent Configuration in .env:")
print(f"  MAIL_SERVER        : {mail_server}")
print(f"  MAIL_PORT          : {mail_port}")
print(f"  MAIL_USERNAME      : {mail_username if mail_username else '[NOT SET]'}")
print(f"  MAIL_PASSWORD      : {'*' * len(mail_password) if mail_password else '[NOT SET]'}")
print(f"  MAIL_DEFAULT_SENDER: {mail_sender if mail_sender else '[NOT SET]'}")
print("-" * 60)

if not mail_username or not mail_password or "your-email" in mail_username:
    print("\n[!] STATUS: Mail credentials are not configured yet in .env.")
    print("    Please edit .env with your Gmail address and 16-character App Password.")
    exit(0)

test_recipient = mail_username
print(f"\n[1/3] Attempting connection to {mail_server}:{mail_port}...")

try:
    if mail_port == 465:
        server = smtplib.SMTP_SSL(mail_server, mail_port, timeout=15)
    else:
        server = smtplib.SMTP(mail_server, mail_port, timeout=15)
        server.starttls()

    print("[2/3] [OK] Connected to SMTP server and started TLS encryption.")
    print(f"Logging in as {mail_username}...")

    server.login(mail_username, mail_password)
    print("[3/3] [OK] SMTP Authentication successful!")

    # Compose test email
    test_code = "849201"
    msg = MIMEMultipart("alternative")
    msg["Subject"] = f"Your Password Reset Code: {test_code} - Societal Innovation Portal"
    msg["From"] = mail_sender
    msg["To"] = test_recipient

    html = f"""
    <div style="font-family: Arial, sans-serif; max-width: 500px; margin: auto; padding: 25px; border: 1px solid #e2e8f0; border-radius: 12px; background: #ffffff;">
        <h2 style="color: #172554; text-align: center; margin-top: 0;">Societal Innovation Portal</h2>
        <hr style="border: 0; border-top: 1px solid #e2e8f0; margin: 20px 0;">
        <p style="color: #334155; font-size: 15px;">Hello,</p>
        <p style="color: #334155; font-size: 15px;">This is a <strong>test verification email</strong> to confirm your OTP email delivery is working properly.</p>
        <div style="text-align: center; margin: 25px 0;">
            <span style="display: inline-block; font-size: 32px; font-weight: bold; color: #2563eb; letter-spacing: 6px; padding: 12px 28px; background: #eff6ff; border-radius: 8px; border: 2px dashed #2563eb;">{test_code}</span>
        </div>
        <p style="color: #16a34a; font-weight: bold; font-size: 14px; text-align: center;">Email configuration verified successfully!</p>
        <hr style="border: 0; border-top: 1px solid #e2e8f0; margin: 20px 0;">
        <p style="color: #94a3b8; font-size: 12px; text-align: center;">Societal Innovation Portal &copy; All rights reserved.</p>
    </div>
    """
    msg.attach(MIMEText(html, "html"))

    print(f"Sending test email to {test_recipient}...")
    server.sendmail(mail_sender, [test_recipient], msg.as_string())
    server.quit()

    print("\n" + "=" * 60)
    print(" [OK] SUCCESS! Test email was delivered successfully.")
    print(f" Check the inbox of: {test_recipient}")
    print("=" * 60)

except smtplib.SMTPAuthenticationError as e:
    print("\n" + "!" * 60)
    print(" [X] AUTHENTICATION FAILED (Error 535)")
    print(" Common causes & solutions:")
    print(" 1. You entered your normal Gmail password instead of an 'App Password'.")
    print("    Google requires a 16-character App Password.")
    print("    Visit: https://myaccount.google.com/apppasswords")
    print(" 2. 2-Step Verification must be enabled on your Google account first.")
    print(" 3. Check for typos in your email or 16-character App Password.")
    print("!" * 60)
    print(f"Details: {e}\n")

except Exception as e:
    print("\n" + "!" * 60)
    print(f" [X] CONNECTION ERROR: {e}")
    print(" If port 587 timed out, your network or antivirus may be blocking SMTP.")
    print("!" * 60 + "\n")

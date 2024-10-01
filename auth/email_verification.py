import os
import smtplib
from email.mime.text import MIMEText


# Define the SMTP configurations for famous email providers
SMTP_CONFIG = {
    'gmail': {
        'host': 'smtp.gmail.com',
        'port': 587,
        'tls': True,
    },
    'yahoo': {
        'host': 'smtp.mail.yahoo.com',
        'port': 587,
        'tls': True,
    },
    'outlook': {
        'host': 'smtp.office365.com',
        'port': 587,
        'tls': True,
    },
}

def send_verification_email(email: str, verification_link: str, provider: str = 'gmail'):
    """
    Sends a verification email using the specified email provider.

    Args:
        email (str): The recipient's email address.
        verification_link (str): The email verification link.
        provider (str): The email provider to use (e.g., 'gmail', 'yahoo', 'outlook', etc.).
    """
    smtp_host = SMTP_CONFIG.get(provider, {}).get('host')
    smtp_port = SMTP_CONFIG.get(provider, {}).get('port')
    use_tls = SMTP_CONFIG.get(provider, {}).get('tls', True)

    # Get credentials from environment variables
    smtp_user = os.getenv(f'{provider.upper()}_USER')
    smtp_password = os.getenv(f'{provider.upper()}_PASSWORD')

    if not smtp_host or not smtp_user or not smtp_password:
        raise ValueError(f"SMTP configuration or credentials for {provider} are missing")

    try:
        # Set up the email content
        msg = MIMEText(f"Please verify your email by clicking on the link: {verification_link}")
        msg['Subject'] = 'Verify your email'
        msg['From'] = smtp_user
        msg['To'] = email

        # Establish connection to the SMTP server
        with smtplib.SMTP(smtp_host, smtp_port) as server:
            if use_tls:
                server.starttls()  # Secure the connection
            server.login(smtp_user, smtp_password)
            server.sendmail(smtp_user, email, msg.as_string())
            print(f"Verification email sent to {email} using {provider}")
    except Exception as e:
        print(f"Failed to send verification email: {e}")


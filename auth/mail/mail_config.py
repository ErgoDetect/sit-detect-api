from fastapi import HTTPException
from fastapi_mail import ConnectionConfig, FastMail, MessageSchema
from pydantic import BaseModel, EmailStr
from typing import List
import os
from dotenv import load_dotenv
load_dotenv()

# Email schema for sending email requests
class EmailSchema(BaseModel):
    email: List[EmailStr]

# Configuration class for email settings
class EmailConfig:
    MAIL_USERNAME = os.getenv('GMAIL_ADDRESS')  # Use your Gmail email address
    MAIL_PASSWORD = os.getenv('GMAIL_PASSWORD')  # App-specific password
    MAIL_FROM = os.getenv('GMAIL_ADDRESS')  # Same as your Gmail email or desired sender email
    MAIL_PORT = int(os.getenv('MAIL_PORT'))
    MAIL_SERVER = os.getenv('MAIL_SERVER')
    MAIL_STARTTLS = True
    MAIL_SSL_TLS = False
    USE_CREDENTIALS = True
    VALIDATE_CERTS = True


# FastAPI-Mail connection config
CONF = ConnectionConfig(
    MAIL_USERNAME=EmailConfig.MAIL_USERNAME,
    MAIL_PASSWORD=EmailConfig.MAIL_PASSWORD,
    MAIL_FROM=EmailConfig.MAIL_FROM,
    MAIL_PORT=EmailConfig.MAIL_PORT,
    MAIL_SERVER=EmailConfig.MAIL_SERVER,
    MAIL_STARTTLS=EmailConfig.MAIL_STARTTLS,
    MAIL_SSL_TLS=EmailConfig.MAIL_SSL_TLS,   
    USE_CREDENTIALS=EmailConfig.USE_CREDENTIALS,
    VALIDATE_CERTS=EmailConfig.VALIDATE_CERTS
)
    
    
async def send_verification_email(message: MessageSchema):
    """
    Utility function to send the email using FastMail.
    """
    try:
        fm = FastMail(CONF)
        await fm.send_message(message)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to send verification email: {str(e)}")
  

def load_email_template(template_path: str) -> str:
    """
    Loads an HTML template from a file.
    
    Args:
        template_path (str): Path to the HTML file.
    
    Returns:
        str: HTML content of the template.
    """
    with open(template_path, "r", encoding="utf-8") as file:
        return file.read()
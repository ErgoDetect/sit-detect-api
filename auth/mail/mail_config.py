from datetime import timedelta
from fastapi import BackgroundTasks, HTTPException, status
from fastapi_mail import ConnectionConfig, FastMail, MessageSchema
from pydantic import BaseModel, EmailStr
from typing import List
import os
from dotenv import load_dotenv
import logging

from requests import Session

from auth.token import create_verify_token, get_current_time
from database.crud import get_user_by_email
from database.model import VerifyMailToken

load_dotenv()

logger = logging.getLogger(__name__)


# Email schema for sending email requests
class EmailSchema(BaseModel):
    email: List[EmailStr]


# Configuration class for email settings
class EmailConfig:
    MAIL_USERNAME = os.getenv("GMAIL_ADDRESS")  # Use your Gmail email address
    MAIL_PASSWORD = os.getenv("GMAIL_PASSWORD")  # App-specific password
    MAIL_FROM = os.getenv(
        "GMAIL_ADDRESS"
    )  # Same as your Gmail email or desired sender email
    MAIL_PORT = int(os.getenv("MAIL_PORT"))
    MAIL_SERVER = os.getenv("MAIL_SERVER")
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
    VALIDATE_CERTS=EmailConfig.VALIDATE_CERTS,
)


async def send_verification_email(message: MessageSchema):
    """
    Utility function to send the email using FastMail.
    """
    try:
        fm = FastMail(CONF)
        await fm.send_message(message)
    except Exception as e:
        logger.error(f"Failed to send verification email: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to send verification email: {str(e)}",
        )


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


async def verify_mail_send_template(
    db: Session, background_tasks: BackgroundTasks, receiver: str
):
    try:
        user = get_user_by_email(db, email=receiver, sign_up_method="email")
        if not user:
            logging.error(f"No user found with email: {receiver}")
            raise HTTPException(status_code=404, detail="User not found")

        # Create a new token every time
        verify_token = create_verify_token({"sub": receiver})
        current_time = get_current_time()
        token_expiration = current_time + timedelta(hours=24)

        # Check if a token already exists, and update or create accordingly
        verify_mail = (
            db.query(VerifyMailToken)
            .filter(VerifyMailToken.user_id == user.user_id)
            .first()
        )

        if verify_mail:
            # Invalidate the old token
            verify_mail.verification_token = verify_token
            verify_mail.token_expiration = token_expiration
        else:
            # Create a new token
            verify_mail = VerifyMailToken(
                user_id=user.user_id,
                verification_token=verify_token,
                token_expiration=token_expiration,
            )
            db.add(verify_mail)

        db.commit()

    except Exception as e:
        db.rollback()
        logging.error(f"Error generating verification token: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error generating verification token",
        )

    verification_link = f"http://localhost:8000/user/verify/?token={verify_token}"
    template_path = os.path.abspath(
        os.path.join(
            os.path.dirname(__file__), "..", "..", "auth", "mail", "template.html"
        )
    )

    try:
        html_content = load_email_template(template_path)
        html_content = html_content.replace(
            "{{ verification_link }}", verification_link
        )
    except FileNotFoundError as e:
        logger.error(f"Email template not found at {template_path}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Email template not found",
        )

    # Prepare and send the email
    message = MessageSchema(
        subject="Verify your Email",
        recipients=[receiver],
        body=html_content,
        subtype="html",
    )

    background_tasks.add_task(send_verification_email, message)

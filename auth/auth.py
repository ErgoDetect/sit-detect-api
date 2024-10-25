from fastapi import HTTPException, status
from sqlalchemy.orm import Session
from auth.auth_utils import hash_password, verify_password
from database.crud import get_user_by_email
from database.model import User
from database.model import EmailUser
from sqlalchemy.orm import Session
from fastapi import HTTPException, status


def authenticate_user(db: Session, email: str, password: str):
    # Query the user from the user table using the email
    user = (
        db.query(User)
        .filter(User.email == email, User.sign_up_method == "email")
        .first()
    )

    if user is None:
        # Raise a 404 HTTP exception if the email is not found
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Email does not exist."
        )

    # Query the email_users table to check if the user's email is verified
    email_user = db.query(EmailUser).filter(EmailUser.user_id == user.user_id).first()

    if email_user is None or not email_user.verified:
        # Raise a 404 HTTP exception if the email is not verified
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Email not verified."
        )

    # Verify the password
    if not verify_password(password, email_user.password):
        # Raise a 401 exception if the password is incorrect
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Incorrect password."
        )

    return user

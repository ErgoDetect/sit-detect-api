from fastapi import HTTPException, status
from sqlalchemy.orm import Session
from auth.auth_utils import verify_password
from database.model import User


def authenticate_user(db: Session, email: str, password: str) -> User:
    """
    Authenticate a user by their email and password.

    Args:
        db (Session): The database session.
        email (str): The user's email address.
        password (str): The user's password in plaintext.

    Returns:
        User: The authenticated user object.

    Raises:
        HTTPException: If the email does not exist or the password is incorrect.
    """
    # Query the user from the database by email
    user = db.query(User).filter(User.email == email).first()

    if not user:
        # Raise a 404 HTTP exception if the email is not found
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Email does not exist."
        )

    # Verify the password using the auth_utils function
    if not verify_password(password, user.password):
        # Raise a 401 HTTP exception if the password is incorrect
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect password."
        )

    # Return the authenticated user object
    return user

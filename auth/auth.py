from fastapi import HTTPException,status
from sqlalchemy.orm import Session
from auth.auth_utils import verify_password
from database.model import User


def authenticate_user(db: Session, email: str, password: str):
    # Query the user from the database using the email
    user = db.query(User).filter(User.email == email).first()
    
    if user is None:
        # Raise a 404 HTTP exception if the email is not found
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Email does not exist."
        )
    
    if not verify_password(password, user.password):
        # Raise a 401 exception if the password is incorrect
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect password."
        )
    
    return user


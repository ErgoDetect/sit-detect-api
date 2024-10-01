import logging
from fastapi import HTTPException
from pydantic import EmailStr
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError

from database.model import User, UserSession
import random
import string
from auth.auth_utils import hash_password

# Helper function to generate a unique user ID
def generate_unique_user_id(length=21) -> str:
    """
    Generate a unique user ID with the specified length.
    
    Args:
        length (int): Length of the user ID to generate.
    
    Returns:
        str: A unique user ID consisting of digits.
    
    Raises:
        ValueError: If the length is less than 1.
    """
    if length < 1:
        raise ValueError("Length must be at least 1")
    return ''.join(random.choices(string.digits, k=length))

#! Create
def create_user(db: Session, email: EmailStr, password: str, display_name: str) -> dict:
    """
    Create a new user with a unique user ID, email, hashed password, and display name.
    
    Args:
        db (Session): SQLAlchemy database session.
        email (EmailStr): The email address of the user.
        password (str): The user's plaintext password.
        display_name (str): The user's display name.
    
    Returns:
        dict: A success message.
    
    Raises:
        HTTPException: If the email is already registered.
    """
    # Check if email is already registered
    existing_user = db.query(User).filter(User.email == email).first()
    if existing_user:
        raise HTTPException(status_code=400, detail="Email already registered.")
    
    # Generate a unique user_id
    while True:
        user_id = generate_unique_user_id()
        if not db.query(User).filter(User.user_id == user_id).first():
            break

    hashed_password = hash_password(password)

    # Create the user instance
    db_user = User(
        user_id=user_id,
        email=email,
        password=hashed_password,
        display_name=display_name,
        sign_up_method='email',
        verified=False,  # Default user is not verified on creation
    )
    
    try:
        db.add(db_user)
        db.commit()
        db.refresh(db_user)
    except SQLAlchemyError as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Error creating user: {str(e)}")

    return {"message": "User created successfully"}

def create_user_google(db: Session, user_id: str, user_email: EmailStr) -> dict:
    """
    Create a new Google user with a provided user ID and email.
    
    Args:
        db (Session): SQLAlchemy database session.
        user_id (str): The user ID from Google.
        user_email (EmailStr): The email address from Google.
    
    Returns:
        dict: A success message.
    
    Raises:
        HTTPException: If the email is already registered.
    """
    # Check if email is already registered
    if db.query(User).filter(User.email == user_email).first():
        raise HTTPException(status_code=400, detail="Email already registered.")

    db_user = User(
        user_id=user_id,
        email=user_email,
        password=None,  # No password for Google sign-up
        display_name='Google User',  # Can be updated later
        sign_up_method='google',
        verified=True  # Google users are assumed verified
    )
    
    try:
        db.add(db_user)
        db.commit()
        db.refresh(db_user)
    except SQLAlchemyError as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Error creating Google user: {str(e)}")

    return {"message": "Google user created successfully"}

def verify_user_email(db: Session, email: EmailStr) -> User:
    """
    Verify a user's email by setting their verified status to True.
    
    Args:
        db (Session): SQLAlchemy database session.
        email (EmailStr): The email address to verify.
    
    Returns:
        User: The updated User object if the email is found.
    
    Raises:
        HTTPException: If the email is not found.
    """
    user = db.query(User).filter(User.email == email).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found.")
    
    user.verified = True
    db.commit()
    return user

def get_user_by_email(db: Session, email: EmailStr) -> User:
    """
    Get a user by their email.
    
    Args:
        db (Session): SQLAlchemy database session.
        email (EmailStr): The email address of the user.
    
    Returns:
        User: The User object if found, else None.
    """
    return db.query(User).filter(User.email == email).first()

def get_user_by_id(db: Session, user_id: str) -> User:
    """
    Get a user by their user ID.
    
    Args:
        db (Session): SQLAlchemy database session.
        user_id (str): The user's unique ID.
    
    Returns:
        User: The User object if found, else None.
    """
    return db.query(User).filter(User.user_id == user_id).first()

#! Delete
def delete_user(db: Session, email: str) -> None:
    """
    Delete a user by their email.
    
    Args:
        db (Session): SQLAlchemy database session.
        email (str): The email address of the user to delete.
    
    Raises:
        HTTPException: If the user is not found.
    """
    db_user = db.query(User).filter(User.email == email).first()
    
    if not db_user:
        raise HTTPException(status_code=404, detail="User not found")
    
    try:
        db.delete(db_user)
        db.commit()
    except SQLAlchemyError as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Error deleting user: {str(e)}")

# def delete_user_sessions(db: Session, user_id: str):
#     """
#     Deletes all active sessions for the given user.
    
#     Args:
#         db (Session): SQLAlchemy database session.
#         user_id (str): The user ID whose sessions should be deleted.
    
#     Raises:
#         HTTPException: If an error occurs while deleting the sessions.
#     """
#     try:
#         db.query(UserSession).filter(UserSession.user_id == user_id).delete()
#         db.commit()
#     except SQLAlchemyError as e:
#         db.rollback()
#         raise HTTPException(status_code=500, detail=f"Error deleting user sessions: {str(e)}")

def delete_user_sessions(db: Session, user_id: str, device_identifier: str):
    """
    Deletes active sessions for a specific user and device.
    
    Args:
        db (Session): SQLAlchemy database session.
        user_id (str): The user ID whose sessions should be deleted.
        device_identifier (str): The device identifier to target the session.
    
    Raises:
        HTTPException: If an error occurs while deleting the sessions.
    """
    try:
        result = db.query(UserSession).filter_by(user_id=user_id, device_identifier=device_identifier)
        if result == 0:
            logging.warning(f"No sessions found for user_id={user_id} and device_identifier={device_identifier}")
        db.query(UserSession).filter_by(user_id=user_id).delete()
        db.commit()
    except SQLAlchemyError as e:
        logging.error(f"Error deleting user sessions: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error deleting user sessions: {str(e)}")

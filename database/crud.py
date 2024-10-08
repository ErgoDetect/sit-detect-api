import logging
from typing import List, Optional
from fastapi import HTTPException
from pydantic import EmailStr
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError, IntegrityError
import random
import string
from auth.auth_utils import hash_password
from database.model import User, UserSession

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Helper function to generate a unique user ID
def generate_unique_user_id(length=21) -> str:
    """
    Generate a unique user ID with the specified length.
    Args:
        length (int): Length of the user ID to generate.
    Returns:
        str: A unique user ID consisting of digits.
    """
    if length < 1:
        raise ValueError("Length must be at least 1")
    return ''.join(random.choices(string.digits, k=length))

### User creation for email/password sign-up
def create_user(db: Session, email: EmailStr, password: str, display_name: str) -> dict:
    """
    Create a new user with a unique user ID, email, hashed password, and display name.
    
    Args:
        db (Session): SQLAlchemy database session.
        email (EmailStr): The email address of the user.
        password (str): The user's plaintext password.
        display_name (str): The user's display name.
    
    Returns:
        dict: A success message with user ID.
    
    Raises:
        HTTPException: If the email is already registered or an error occurs during creation.
    """
    # Step 1: Check if the email is already registered
    existing_user = db.query(User).filter(User.email == email).first()
    if existing_user and existing_user.sign_up_method == "email":
        raise HTTPException(status_code=400, detail="Email already registered with email sign-up method.")

    # Step 2: Generate a unique user_id
    user_id = generate_unique_user_id()

    # Step 3: Hash the password
    try:
        hashed_password = hash_password(password)
    except Exception as e:
        logger.error(f"Error hashing password: {e}")
        raise HTTPException(status_code=500, detail="Error hashing password")

    # Step 4: Create the user instance
    db_user = User(
        user_id=user_id,
        email=email,
        password=hashed_password,
        display_name=display_name,
        sign_up_method='email',
        verified=False  # Default user is not verified on creation
    )

    # Step 5: Save to database
    try:
        db.add(db_user)
        db.commit()
        db.refresh(db_user)
    except IntegrityError as e:
        db.rollback()
        logger.error(f"Integrity error: {e}")
        raise HTTPException(status_code=400, detail="User ID or email already exists.")
    except SQLAlchemyError as e:
        db.rollback()
        logger.error(f"SQLAlchemy error during user creation: {e}")
        raise HTTPException(status_code=500, detail="Error creating user in database.")

    return {"message": "User created successfully"}

### User creation for Google sign-up
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
        HTTPException: If the email is already registered with Google.
    """
    existing_user = db.query(User).filter(User.email == user_email).first()
    
    # If the user exists with Google sign-up, raise an error
    if existing_user and existing_user.sign_up_method == 'google':
        raise HTTPException(status_code=400, detail="Email already registered with Google sign-up.")

    # Create the Google user if it doesn't exist or is registered with a different method
    db_user = User(
        user_id=user_id,
        email=user_email,
        password=None,  # No password for Google sign-up
        display_name='Google User',  # Default display name, can be changed later
        sign_up_method='google',
        verified=True  # Google users are considered verified
    )

    try:
        db.add(db_user)
        db.commit()
        db.refresh(db_user)
    except SQLAlchemyError as e:
        db.rollback()
        logger.error(f"Error creating Google user: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error creating Google user: {str(e)}")

    return {"message": "Google user created successfully"}

### Verify user email
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

### Retrieve user by email
def get_user_by_email(db: Session, email: EmailStr, sign_up_method: str) -> User:
    """
    Get a user by their email and sign-up method.
    Args:
        db (Session): SQLAlchemy database session.
        email (EmailStr): The email address of the user.
        sign_up_method (str): Sign-up method (e.g., 'email', 'google').
    Returns:
        User: The User object if found, else None.
    """
    return db.query(User).filter(User.email == email, User.sign_up_method == sign_up_method).first()

### Retrieve user by user ID
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

### Delete user by email
def delete_user(db: Session, email: str) -> None:
    """
    Delete a user by their email.
    Args:
        db (Session): SQLAlchemy database session.
        email (str): The email address of the user to delete.
    Raises:
        HTTPException: If the user is not found or there is an error deleting the user.
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

### Retrieve user sessions by user ID
def get_user_sessions(db: Session, user_id: str) -> List[UserSession]:
    """
    Retrieves all active sessions for the given user.
    Args:
        db (Session): SQLAlchemy database session.
        user_id (str): The user ID whose sessions should be retrieved.
    Returns:
        List[UserSession]: A list of UserSession objects representing the user's active sessions.
    """
    return db.query(UserSession).filter(UserSession.user_id == user_id).all()

### Delete user sessions by user ID and device identifier
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
        sessions_to_delete = db.query(UserSession).filter_by(user_id=user_id, device_identifier=device_identifier).all()
        if not sessions_to_delete:
            logger.warning(f"No sessions found for user_id={user_id} and device_identifier={device_identifier}")
        else:
            db.query(UserSession).filter_by(user_id=user_id, device_identifier=device_identifier).delete()
            db.commit()
    except SQLAlchemyError as e:
        db.rollback()
        logger.error(f"Error deleting user sessions: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error deleting user sessions: {str(e)}")

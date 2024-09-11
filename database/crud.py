from fastapi import HTTPException
from sqlalchemy.orm import Session
from .model import User
from .schemas.UserEmail import EmailCreate
import random
import string
from auth.auth_utils import hash_password




def generate_unique_user_id(length=21):
    """Generate a unique user ID with the specified length."""
    if length < 1:
        raise ValueError("Length must be at least 1")
    return ''.join(random.choices(string.digits, k=length))


#! Create
def create_user(db: Session, user: User):
    """Create a new user with a unique user ID."""
    # Generate a unique user_id
    while True:
        user_id = generate_unique_user_id()
        if not db.query(User).filter(User.user_id == user_id).first():
            break
    hashed_password = hash_password(user.password)

    # Create the user instance
    db_user = User(
        user_id=user_id,
        email=user.email,
        password= hashed_password,
        display_name=user.display_name,
        sign_up_method='email',
        
    )
    
    db.add(db_user)
    db.commit()
    db.refresh(db_user)

    return {"message": "User created successfully"}


def create_user_google(db: Session, user_id:str,user_email: EmailCreate) -> User:
    db_user = User(
        user_id=user_id,
        email=user_email,
        password=None,  
        display_name='a',  
        sign_up_method='google',
        verified = True
    )
    db.add(db_user)
    db.commit()
    db.refresh(db_user)  # Refresh the instance to include the new primary key (user_id)
    return {"message": "User created successfully"}

def verify_user_email(db: Session, email: str):
    user = db.query(User).filter(User.email == email).first()
    if user:
        user.verified = True
        db.commit()
        return user
    return None

def get_user_by_email(db: Session, email: str) -> User:
    return db.query(User).filter(User.email == email).first()

# Get a user by ID
def get_user_by_id(db: Session, user_id: str)-> User:
    return db.query(User).filter(User.user_id == user_id).first()

# # Create an OAuth token
# def create_oauth_token(db: Session, token: OAuthTokenCreate) -> OAuthToken:
#     db_token = OAuthToken(
#         user_id=token.user_id,
#         refresh_token=token.refresh_token,
#         expires_in=token.expires_in
#     )
#     db.add(db_token)
#     db.commit()
#     db.refresh(db_token)
#     return db_token

# # Get OAuth tokens by user ID
# def get_oauth_tokens_by_user_id(db: Session, user_id: int) -> list[OAuthToken]:
#     return db.query(OAuthToken).filter(OAuthToken.user_id == user_id).all()

# # Get OAuth token by refresh token
# def get_oauth_token_by_refresh_token(db: Session, refresh_token: str) -> OAuthToken:
#     return db.query(OAuthToken).filter(OAuthToken.refresh_token == refresh_token).first()


#! Delete
def delete_user(db: Session, email: str):
    # Find the user by email
    db_user = db.query(User).filter(User.email == email).first()
    
    # If the user does not exist, raise an exception
    if not db_user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Delete the user
    db.delete(db_user)
    db.commit()
    
    return None
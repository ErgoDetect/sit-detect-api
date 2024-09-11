from sqlalchemy.orm import Session
from auth.auth_utils import verify_password
from database.model import User


def authenticate_user(db: Session, email: str, password: str):
    # Query the user from the database using the email
    user = db.query(User).filter(User.email == email).first()
    if user is None:
        return False
    
    if not verify_password(password, user.password):
        return False
    return user

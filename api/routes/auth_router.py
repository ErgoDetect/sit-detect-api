from datetime import timedelta
from typing import Dict
import uuid
from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Request,
    Response,
    status,
)
from sqlalchemy.orm import Session
from auth.auth_utils import hash_password
from auth.email_verification import generate_verification_token, send_verification_email, verify_verification_token
from auth.token import generate_and_set_tokens, get_current_time, verify_token
from database.crud import delete_user_sessions, get_user_by_email, create_user
from database.database import get_db
from database.model import User, UserSession
from database.schemas.Auth import LoginResponse, SignUpRequest
from database.schemas.Auth import LoginRequest
from auth.auth import authenticate_user
import os

auth_router = APIRouter()
SECURE_COOKIES = os.getenv("HELLO") == "production"



@auth_router.post("/signup/", status_code=status.HTTP_201_CREATED)
def sign_up(signup_data: SignUpRequest, db: Session = Depends(get_db)):
    # Step 1: Check if email is already registered
    if get_user_by_email(db, email=signup_data.email):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Email already registered")
    
    # Step 2: Hash the password and create the user
    hashed_password = hash_password(signup_data.password)
    create_user(db, signup_data.email, hashed_password, signup_data.display_name)
    
    # Step 3: Generate email verification token
    verification_token = generate_verification_token(signup_data.email)
    verification_link = f"http://localhost:8000/auth/verify-email?token={verification_token}"
    
    # Step 4: Send verification email
    send_verification_email(signup_data.email, verification_link,)
    
    return {"message": "User created successfully, please verify your email"}

@auth_router.get("/verify-email/")
def verify_email(token: str, db: Session = Depends(get_db)):
    # Verify the token using itsdangerous
    email = verify_verification_token(token)
    
    if not email:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid or expired token")

    # Mark the user's email as verified
    user = db.query(User).filter(User.email == email).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    user.verified = True
    db.commit()

    return {"message": "Email successfully verified. You can now log in."}

@auth_router.post("/resend-verification/")
def resend_verification(email: str, db: Session = Depends(get_db)):
    # Find the user by email
    user = db.query(User).filter(User.email == email).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    if user.verified:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Email is already verified")

    # Generate a new verification token
    verification_token = generate_verification_token(user.email)
    
    # Send the verification email
    verification_link = f"http://localhost:8000/auth/verify-email?token={verification_token}"
    send_verification_email(user.email, verification_link)
    
    return {"message": "Verification email resent. Please check your inbox."}



@auth_router.post("/login/", response_model=LoginResponse)
def login(request: Request, response: Response, login_data: LoginRequest, db: Session = Depends(get_db)):
    # Step 1: Authenticate the user
    user = authenticate_user(db, login_data.email, login_data.password)
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
    
    # Step 2: Invalidate existing sessions for this user on the current device
    device_identifier = request.headers.get('Device-Identifier')  # You could also pass a custom device ID from client
    if not device_identifier:
        raise HTTPException(status_code=400, detail="Device identifier missing")
    print(f"Device Identifier: {device_identifier}")

    delete_user_sessions(db, user.user_id, device_identifier)  # Deletes old sessions from this specific device

    # Step 3: Create a new session
    session_id = str(uuid.uuid4())
    new_session = UserSession(
        session_id=session_id,
        user_id=user.user_id,
        device_identifier=device_identifier,
        created_at=get_current_time(),
        expires_at=get_current_time() + timedelta(hours=1)
    )

    db.add(new_session)
    db.commit()

    # Step 4: Generate tokens and set them in the response cookies
    tokens = generate_and_set_tokens(response, {"sub": user.user_id, "email": user.email, "session_id": session_id}, secure=False)

    return {
        "access_token": tokens["access_token"],
        "refresh_token": tokens["refresh_token"],
        "token_type": "bearer"
    }



@auth_router.post("/logout/")
def logout(response: Response):
    # Clear application cookies
    response.delete_cookie("access_token", path="/")
    response.delete_cookie("refresh_token", path="/")
    
    # Google Logout URL
    google_logout_url = "https://accounts.google.com/Logout"
    
    # Return a message or redirect the user to the Google logout URL
    return {"message": "Logged out successfully", "google_logout_url": google_logout_url}

@auth_router.post("/refresh-token/", response_model=Dict[str, str])
def refresh_access_token(response: Response, request: Request):
    refresh_token = request.cookies.get("refresh_token")
    if not refresh_token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Refresh token not provided")
    
    try:
        payload = verify_token(refresh_token)
    except HTTPException as e:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh token") from e

    user_id = payload.get("sub")
    email = payload.get("email")
    if not user_id or not email:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh token payload")

    tokens = generate_and_set_tokens(response, {"sub": user_id, "email": email}, SECURE_COOKIES)
    return {
        "access_token": tokens["access_token"],
        "refresh_token": tokens["refresh_token"]
    }

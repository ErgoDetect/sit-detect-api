from datetime import timedelta
from typing import Dict
import uuid
from fastapi import (
    APIRouter, BackgroundTasks, Depends, HTTPException, Request, Response, status
)
from fastapi_mail import MessageSchema, MessageType
from sqlalchemy.orm import Session
from auth.auth_utils import hash_password
from auth.mail.mail_config import load_email_template, send_verification_email
from auth.token import create_verify_token, generate_and_set_tokens, get_current_time, verify_token
from database.crud import delete_user_sessions, get_user_by_email, create_user
from database.database import get_db
from database.model import User, UserSession
from database.schemas.Auth import LoginResponse, SignUpRequest, LoginRequest
from auth.auth import authenticate_user
import os

auth_router = APIRouter()

@auth_router.post("/signup/", status_code=status.HTTP_201_CREATED)
async def sign_up(
    signup_data: SignUpRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    # Step 1: Check if the email is already registered
    if get_user_by_email(db, email=signup_data.email):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Email already registered")
    
    # Step 2: Hash the password and create the user
    # hashed_password = hash_password(signup_data.password)
    
    try:
        create_user(db, signup_data.email,signup_data.password , signup_data.display_name)
    except Exception:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Error during user creation")

    # Step 3: Generate the verification token
    try:
        generated_verify_token = create_verify_token({"sub": signup_data.email})
    except Exception:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Error generating verification token")

    # Step 4: Prepare the verification email
    verification_link = f"http://localhost:8000/user/verify/?token={generated_verify_token}"
    
    # Load email template
    template_path = 'auth/mail/template.html'
    html_content = load_email_template(template_path)

    # Replace the placeholder in the template with the actual verification link
    html_content = html_content.replace("{{ verification_link }}", verification_link)
    
    # Prepare the message
    message = MessageSchema(
        subject="Verify your Email",
        recipients=[signup_data.email],
        body=html_content,
        subtype=MessageType.html
    )

    # Step 5: Send the email in the background
    background_tasks.add_task(send_verification_email, message)

    return {"message": "User created successfully, please verify your email."}

@auth_router.post("/login/", response_model=LoginResponse)
def login(
    request: Request,
    response: Response,
    login_data: LoginRequest,
    db: Session = Depends(get_db)
):
    # Step 1: Authenticate the user
    user = authenticate_user(db, login_data.email, login_data.password)
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
    
    # Step 2: Validate device identifier
    device_identifier = request.headers.get('Device-Identifier')
    if not device_identifier:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Device identifier missing")

    # Step 3: Invalidate old sessions for the device
    delete_user_sessions(db, user.user_id, device_identifier)

    # Step 4: Create a new session and save it to the database
    session_id = str(uuid.uuid4())
    current_time = get_current_time()  # Store to avoid redundant calls
    new_session = UserSession(
        session_id=session_id,
        user_id=user.user_id,
        device_identifier=device_identifier,
        created_at=current_time,
        expires_at=current_time + timedelta(hours=1)
    )
    db.add(new_session)
    db.commit()

    # Step 5: Generate tokens and set them in the response cookies
    tokens = generate_and_set_tokens(
        response,
        {"sub": user.user_id, "email": user.email, "session_id": session_id}
    )

    return {
        "access_token": tokens["access_token"],
        "refresh_token": tokens["refresh_token"],
        "token_type": "bearer"
    }


@auth_router.post("/logout/")
def logout(response: Response):
    # Step 1: Clear cookies
    response.delete_cookie("access_token", path="/")
    response.delete_cookie("refresh_token", path="/")
    
    # Step 2: Return Google Logout URL
    return {"message": "Logged out successfully", "google_logout_url": "https://accounts.google.com/Logout"}


@auth_router.post("/refresh-token/", response_model=Dict[str, str])
def refresh_access_token(response: Response, request: Request):
    refresh_token = request.cookies.get("refresh_token")
    if not refresh_token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Refresh token not provided")
    
    try:
        payload = verify_token(refresh_token)
    except HTTPException:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh token")

    user_id = payload.get("sub")
    email = payload.get("email")
    if not user_id or not email:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh token payload")

    tokens = generate_and_set_tokens(response, {"sub": user_id, "email": email})
    return {
        "access_token": tokens["access_token"],
        "refresh_token": tokens["refresh_token"]
    }

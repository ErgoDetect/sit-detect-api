from datetime import timedelta
import logging
from typing import Dict
import uuid
from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    HTTPException,
    Request,
    Response,
    status,
)
from fastapi_mail import MessageSchema, MessageType
from sqlalchemy.orm import Session
from api.request_user import get_current_user
from auth.mail.mail_config import load_email_template, send_verification_email
from auth.token import (
    check_token,
    create_verify_token,
    generate_and_set_tokens,
    get_current_time,
    verify_token,
)
from database.crud import delete_user_sessions, get_user_by_email, create_user
from database.database import get_db
from database.model import User, UserSession
from database.schemas.Auth import LoginResponse, SignUpRequest, LoginRequest
from auth.auth import authenticate_user


import os

# from dotenv import load_dotenv
# load_dotenv()

logger = logging.getLogger(__name__)
auth_router = APIRouter()


@auth_router.post("/signup", status_code=status.HTTP_201_CREATED)
async def sign_up(
    signup_data: SignUpRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    # Step 1: Check if the email is already registered
    if get_user_by_email(db, email=signup_data.email, sign_up_method="email"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Email already registered"
        )

    # Step 2: Hash the password and create the user
    try:
        # Hash the password (you can assume hash_password is already defined elsewhere)
        create_user(
            db, signup_data.email, signup_data.password, signup_data.display_name
        )
    except Exception as e:
        db.rollback()
        logger.error(f"Error creating user: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error during user creation",
        )

    # Step 3: Generate the verification token
    try:
        generated_verify_token = create_verify_token({"sub": signup_data.email})
    except Exception as e:
        logger.error(f"Error generating verification token: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error generating verification token",
        )

    # Step 4: Prepare the verification email
    verification_link = (
        f"http://localhost:8000/user/verify/?token={generated_verify_token}"
    )

    template_path = os.path.abspath(
        os.path.join(
            os.path.dirname(__file__), "..", "..", "auth", "mail", "template.html"
        )
    )
    logger.info(f"Template path: {template_path}")
    html_content = load_email_template(template_path)

    # Replace the placeholder in the template with the actual verification link
    html_content = html_content.replace("{{ verification_link }}", verification_link)

    try:
        # Load the email template and replace the placeholder with the actual verification link
        html_content = load_email_template(template_path)
        html_content = html_content.replace(
            "{{ verification_link }}", verification_link
        )
    except FileNotFoundError as e:
        logger.error(f"Email template not found: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Email template not found",
        )

    # Prepare the message schema
    message = MessageSchema(
        subject="Verify your Email",
        recipients=[signup_data.email],
        body=html_content,
        subtype=MessageType.html,
    )

    # Step 5: Send the email in the background
    background_tasks.add_task(send_verification_email, message)

    return {"message": "User created successfully, please verify your email."}


@auth_router.post("/login", response_model=LoginResponse)
def login(
    request: Request,
    response: Response,
    login_data: LoginRequest,
    db: Session = Depends(get_db),
):
    # Step 1: Authenticate the user
    user = authenticate_user(db, login_data.email, login_data.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials"
        )

    # Step 2: Validate device identifier
    device_identifier = request.headers.get("Device-Identifier")
    if not device_identifier:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Device identifier missing"
        )

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
        expires_at=current_time + timedelta(hours=1),
    )
    db.add(new_session)
    db.commit()

    # Step 5: Generate tokens and set them in the response cookies
    tokens = generate_and_set_tokens(
        response, {"sub": user.user_id, "email": user.email, "session_id": session_id}
    )

    return {
        "access_token": tokens["access_token"],
        "refresh_token": tokens["refresh_token"],
        "token_type": "bearer",
    }


@auth_router.post("/logout", status_code=status.HTTP_200_OK)
async def logout(
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):

    # Step 1: Retrieve the Device-Identifier header
    device_identifier = request.headers.get("Device-Identifier")
    if not device_identifier:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Device identifier missing"
        )

    # Step 2: Delete user sessions based on the device identifier
    delete_user_sessions(db, current_user["user_id"], device_identifier)

    user_id = current_user["user_id"]

    login_method = db.query(User).filter(User.user_id == user_id).first().sign_up_method

    # if login_method == "google":

    # Step 3: Clear authentication cookies
    response.delete_cookie(
        "access_token", httponly=False, path="/", samesite="none"
    )  # Secure should be True in production
    response.delete_cookie(
        "refresh_token", httponly=False, path="/", samesite="none"
    )  # Secure should be True in production

    return {"Logout Successful"}


@auth_router.get("/status")
async def auth_status(request: Request, db: Session = Depends(get_db)):
    # Retrieve tokens from cookies and headers
    access_token = request.cookies.get("access_token")
    refresh_token = request.cookies.get("refresh_token")
    device_mac = request.headers.get("Device-Identifier")

    if not device_mac:
        return {"status": "LoginRequired", "message": "Device identifier is missing"}

    user_id = None

    # Validate access token
    if access_token:
        access_result = check_token(access_token, "access")
        if access_result.get("status") == "Authenticated":
            user_id = access_result.get("user_id")
            if user_id:
                # Verify session in the database
                user_session = (
                    db.query(UserSession)
                    .filter(
                        UserSession.user_id == user_id,
                        UserSession.device_identifier == device_mac,
                    )
                    .first()
                )

                if user_session:
                    return {
                        "status": "Authenticated",
                        "message": "Session valid",
                        "user_id": user_id,
                    }
                else:
                    return {
                        "status": "LoginRequired",
                        "message": "Device mismatch, login required",
                    }
            else:
                logger.warning("Authenticated access token missing 'user_id' field.")
                return {
                    "status": "LoginRequired",
                    "message": "Invalid access token structure.",
                }

        elif access_result.get("status") == "Expired" and refresh_token:
            refresh_result = check_token(refresh_token, "refresh")
            if refresh_result.get("status") == "Authenticated":
                user_id = refresh_result.get("user_id")
                if user_id:
                    return {
                        "status": "Refresh",
                        "message": "Access token expired, but refresh token is valid",
                        "user_id": user_id,
                    }
                else:
                    logger.warning(
                        "Authenticated refresh token missing 'user_id' field."
                    )
                    return {
                        "status": "LoginRequired",
                        "message": "Invalid refresh token structure.",
                    }

    # If no valid access token, check refresh token
    if refresh_token:
        refresh_result = check_token(refresh_token, "refresh")
        if refresh_result.get("status") == "Authenticated":
            user_id = refresh_result.get("user_id")
            if user_id:
                user_session = (
                    db.query(UserSession)
                    .filter(
                        UserSession.user_id == user_id,
                        UserSession.device_identifier == device_mac,
                    )
                    .first()
                )

                if user_session:
                    return {
                        "status": "Refresh",
                        "message": "No access token, but refresh token is valid",
                        "user_id": user_id,
                    }
                else:
                    return {
                        "status": "LoginRequired",
                        "message": "Device mismatch, login required",
                    }
            else:
                logger.warning("Authenticated refresh token missing 'user_id' field.")
                return {
                    "status": "LoginRequired",
                    "message": "Invalid refresh token structure.",
                }

    # If no valid tokens or device mismatch, prompt login required
    return {
        "status": "LoginRequired",
        "message": "No valid tokens found, or device mismatch. Please log in again.",
    }


@auth_router.post("/refresh-token", response_model=Dict[str, str])
def refresh_access_token(response: Response, request: Request):
    refresh_token = request.cookies.get("refresh_token")
    if not refresh_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token not provided",
        )

    try:
        payload = verify_token(refresh_token)
    except HTTPException:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh token"
        )

    user_id = payload.get("sub")
    email = payload.get("email")
    if not user_id or not email:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid refresh token payload",
        )

    tokens = generate_and_set_tokens(response, {"sub": user_id, "email": email})
    return {
        "access_token": tokens["access_token"],
        "refresh_token": tokens["refresh_token"],
    }

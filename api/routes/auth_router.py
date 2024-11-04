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
from sqlalchemy.orm import Session
from api.request_user import get_current_user
from auth.mail.mail_config import (
    verify_mail_send_template,
)
from auth.token import (
    check_token,
    generate_and_set_tokens,
    get_current_time,
    verify_token,
)
from database.crud import (
    delete_user_sessions,
    get_user_by_email,
    create_user,
)
from database.database import get_db
from database.model import EmailUser, User, UserSession, VerifyMailToken
from database.schemas.Auth import (
    LoginResponse,
    ResendVerificationRequest,
    ResetPassword,
    SignUpRequest,
    LoginRequest,
)
from auth.auth import authenticate_user
from auth.auth_utils import hash_password, verify_password


logger = logging.getLogger(__name__)
auth_router = APIRouter()


def verify_session(db, user_id, device_mac):
    """Helper function to check if a user session is valid."""
    return (
        db.query(UserSession)
        .filter(
            UserSession.user_id == user_id,
            UserSession.device_identifier == device_mac,
        )
        .first()
    )


def handle_token_check(token, token_type, db, device_mac):
    """Helper function to check token validity and return the user session if valid."""
    token_result = check_token(token, token_type)

    if token_result.get("status") == "Authenticated":
        user_id = token_result.get("user_id")
        if not user_id:
            logger.warning(f"Authenticated {token_type} token missing 'user_id' field.")
            return {
                "status": "LoginRequired",
                "message": f"Invalid {token_type} token structure.",
            }

        user_session = verify_session(db, user_id, device_mac)
        if user_session:
            return {
                "status": "Authenticated",
                "message": f"{token_type.capitalize()} token valid, session found",
                "user_id": user_id,
            }
        else:
            return {
                "status": "LoginRequired",
                "message": f"Device mismatch, {token_type} token valid but session invalid",
            }

    elif token_result.get("status") == "Expired":
        return {
            "status": "Expired",
            "message": f"{token_type.capitalize()} token expired",
        }

    return {"status": "LoginRequired", "message": f"Invalid {token_type} token"}


@auth_router.post("/signup", status_code=status.HTTP_201_CREATED)
async def sign_up(
    signup_data: SignUpRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    # Step 1: Check if the email is already registered
    existing_user = get_user_by_email(
        db, email=signup_data.email, sign_up_method="email"
    )
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Email already registered"
        )

    # Step 2: Hash the password and create the user
    try:
        create_user(db, signup_data.email, signup_data.password)
    except Exception as e:
        db.rollback()
        logger.error(f"Error creating user: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error during user creation",
        )

    await verify_mail_send_template(
        db,
        background_tasks=background_tasks,
        receiver=signup_data.email,
        types="mail-verify",
    )

    return {"message": "User created successfully, please verify your email."}


@auth_router.post("/resend-verification", status_code=status.HTTP_200_OK)
async def resend_verification(
    request_data: ResendVerificationRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    user = get_user_by_email(db, email=request_data.email, sign_up_method="email")
    user_verify_token = (
        db.query(VerifyMailToken)
        .filter(VerifyMailToken.user_id == user.user_id)
        .first()
    )

    if not user or not user_verify_token.verification_token:
        raise HTTPException(
            status_code=404, detail="User not found or already verified"
        )

    await verify_mail_send_template(
        db,
        background_tasks=background_tasks,
        receiver=request_data.email,
        types="mail-verify",
    )

    return {"message": "Verification email resent successfully."}


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

    delete_user_sessions(db, user.user_id, device_identifier)

    session_id = str(uuid.uuid4())
    current_time = get_current_time()
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

    # Step 3: Clear authentication cookies
    response.delete_cookie(
        "access_token", httponly=False, path="/", samesite="none"
    )  # Secure should be True in production
    response.delete_cookie(
        "refresh_token", httponly=False, path="/", samesite="none"
    )  # Secure should be True in production

    return {"message": "Logout Successful"}


@auth_router.get("/status")
async def auth_status(request: Request, db: Session = Depends(get_db)):
    # Retrieve tokens from cookies and headers
    access_token = request.cookies.get("access_token")
    refresh_token = request.cookies.get("refresh_token")
    device_mac = request.headers.get("Device-Identifier")

    if not device_mac:
        return {"status": "LoginRequired", "message": "Device identifier is missing"}

    # Helper function to check tokens
    def check_token(token, token_type):
        return handle_token_check(token, token_type, db, device_mac)

    # Check access token first
    if access_token:
        access_check = check_token(access_token, "access")
        if access_check["status"] == "Authenticated":
            return access_check

        # Check refresh token if access token is expired
        if access_check["status"] == "Expired" and refresh_token:
            refresh_check = check_token(refresh_token, "refresh")
            if refresh_check["status"] == "Authenticated":
                return {
                    "status": "Refresh",
                    "message": "Access token expired, but refresh token is valid",
                    "user_id": refresh_check["user_id"],
                }

    # Check refresh token if no valid access token
    if refresh_token:
        refresh_check = check_token(refresh_token, "refresh")
        if refresh_check["status"] == "Authenticated":
            return {
                "status": "Refresh",
                "message": "No access token, but refresh token is valid",
                "user_id": refresh_check["user_id"],
            }

    # Return login required if no valid tokens are found
    return {
        "status": "LoginRequired",
        "message": "No valid tokens found, or device mismatch. Please log in again.",
    }


@auth_router.post("/refresh-token", response_model=Dict[str, str])
def refresh_access_token(
    response: Response, request: Request, db: Session = Depends(get_db)
):
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

    generate_and_set_tokens(response, {"sub": user_id, "email": email})
    user_session = db.query(UserSession).filter_by(user_id=user_id).first()
    if user_session:
        user_session.created_at = get_current_time()
        user_session.expires_at = get_current_time() + timedelta(hours=1)
        db.commit()

    return {"message": "Access token refreshed successfully."}


@auth_router.post("/request/reset-password")
async def reset_password(
    request: ResendVerificationRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):

    await verify_mail_send_template(
        db, background_tasks, receiver=request.email, types="reset-password"
    )


@auth_router.post("/reset-password")
def reset_password(
    request: ResetPassword,
    db: Session = Depends(get_db),
):
    user = get_user_by_email(db, request.email, sign_up_method="email")
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    try:
        user_info = (
            db.query(EmailUser).filter(EmailUser.user_id == user.user_id).first()
        )
        if not user_info:
            raise HTTPException(status_code=404, detail="User record not found")

        if verify_password(request.password, user_info.password):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="New password must be different from the old password",
            )

        else:
            hashed_password = hash_password(request.password)
            user_info.password = hashed_password
            db.commit()

    except Exception as e:
        db.rollback()
        logging.error(f"Error resetting password: {e}")
        if verify_password(request.password, user_info.password):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="New password must be different from the old password",
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Error resetting password",
            )

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
from database.model import User, UserSession
from database.schemas.Auth import (
    LoginResponse,
    ResendVerificationRequest,
    SignUpRequest,
    LoginRequest,
)
from auth.auth import authenticate_user


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

    verify_mail_send_template(db, signup_data.email)
    # try:
    #     new_user_id = get_user_by_email(db, signup_data.email, "email")
    #     generated_verify_token = create_verify_token({"sub": signup_data.email})
    #     verify_mail = db.query(VerifyMailToken).filter(
    #         VerifyMailToken.user_id == new_user_id.user_id
    #     )
    #     verify_mail.verification_token = generated_verify_token
    #     verify_mail.token_expiration = get_current_time() + timedelta(hours=24)
    #     db.commit()
    # except Exception as e:
    #     db.rollback()
    #     logger.error(f"Error generating verification token: {e}")
    #     raise HTTPException(
    #         status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
    #         detail="Error generating verification token",
    #     )

    # # Step 4: Prepare the verification email
    # verification_link = (
    #     f"http://localhost:8000/user/verify/?token={generated_verify_token}"
    # )
    # template_path = os.path.abspath(
    #     os.path.join(
    #         os.path.dirname(__file__), "..", "..", "auth", "mail", "template.html"
    #     )
    # )

    # try:
    #     html_content = load_email_template(template_path)
    #     html_content = html_content.replace(
    #         "{{ verification_link }}", verification_link
    #     )
    # except FileNotFoundError as e:
    #     logger.error(f"Email template not found: {e}")
    #     raise HTTPException(
    #         status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
    #         detail="Email template not found",
    #     )

    # # Prepare the message schema
    # message = MessageSchema(
    #     subject="Verify your Email",
    #     recipients=[signup_data.email],
    #     body=html_content,
    #     subtype=MessageType.html,
    # )

    # # Step 5: Send the email in the background
    # background_tasks.add_task(send_verification_email, message)

    return {"message": "User created successfully, please verify your email."}


@auth_router.post("/resend-verification", status_code=status.HTTP_200_OK)
async def resend_verification(
    request_data: ResendVerificationRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    user = get_user_by_email(db, email=request_data.email)

    if not user or not user.verification_token:
        raise HTTPException(
            status_code=404, detail="User not found or already verified"
        )

    verify_mail_send_template(db, request_data.email)

    # # Invalidate old token and generate a new one
    # new_token = create_verify_token({"sub": request_data.email})
    # verify_mail = db.query(VerifyMailToken).filter(
    #     VerifyMailToken.user_id == user.user_id
    # )
    # verify_mail.verification_token = new_token
    # verify_mail.token_expiration = get_current_time() + timedelta(hours=24)

    # try:
    #     db.commit()
    # except Exception as e:
    #     db.rollback()
    #     logger.error(f"Error updating token: {e}")
    #     raise HTTPException(
    #         status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
    #         detail="Could not update verification token",
    #     )

    # verification_link = f"http://localhost:8000/user/verify/?token={new_token }"
    # template_path = os.path.abspath(
    #     os.path.join(
    #         os.path.dirname(__file__), "..", "..", "auth", "mail", "template.html"
    #     )
    # )

    # try:
    #     html_content = load_email_template(template_path)
    #     html_content = html_content.replace(
    #         "{{ verification_link }}", verification_link
    #     )
    # except FileNotFoundError as e:
    #     logger.error(f"Email template not found: {e}")
    #     raise HTTPException(
    #         status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
    #         detail="Email template not found",
    #     )

    # # Prepare the message schema
    # message = MessageSchema(
    #     subject="Verify your Email",
    #     recipients=[request_data.email],
    #     body=html_content,
    #     subtype=MessageType.html,
    # )

    # # Step 5: Send the email in the background
    # background_tasks.add_task(send_verification_email, message)

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

    user_id = current_user["user_id"]

    login_method = db.query(User).filter(User.user_id == user_id).first().sign_up_method

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

    # First, check the access token
    if access_token:
        access_check = handle_token_check(access_token, "access", db, device_mac)
        if access_check["status"] == "Authenticated":
            return access_check

        # If access token expired but refresh token is present
        if access_check["status"] == "Expired" and refresh_token:
            refresh_check = handle_token_check(refresh_token, "refresh", db, device_mac)
            if refresh_check["status"] == "Authenticated":
                return {
                    "status": "Refresh",
                    "message": "Access token expired, but refresh token is valid",
                    "user_id": refresh_check["user_id"],
                }

    # If no valid access token, check the refresh token
    if refresh_token:
        refresh_check = handle_token_check(refresh_token, "refresh", db, device_mac)
        if refresh_check["status"] == "Authenticated":
            return {
                "status": "Refresh",
                "message": "No access token, but refresh token is valid",
                "user_id": refresh_check["user_id"],
            }

    # If no valid tokens or device mismatch, prompt login required
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
    user_session.created_at = get_current_time()
    user_session.expires_at = get_current_time() + timedelta(hours=1)
    db.commit()

    return {"message": "Access token refreshed successfully."}

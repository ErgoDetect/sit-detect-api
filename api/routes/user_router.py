import logging
import os
from typing import List
from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from sqlalchemy import desc
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError, NoResultFound
from api.request_user import get_current_user
from auth.mail.mail_config import load_email_template
from auth.token import check_token, get_current_time
from database.crud import delete_user, delete_user_sessions
from database.database import get_db
from database.model import SittingSession, User, VerifyMailToken
from database.schemas.Response import SessionSummary
from database.schemas.Response import SittingSessionResponse

user_router = APIRouter()
logger = logging.getLogger(__name__)


# Helper function to load email templates
def load_expiration_template(template_filename: str):
    template_path = os.path.abspath(
        os.path.join(
            os.path.dirname(__file__), "..", "..", "auth", "mail", template_filename
        )
    )
    try:
        html_content = load_email_template(template_path)
        return HTMLResponse(content=html_content, status_code=200)
    except FileNotFoundError:
        logging.error(f"Email template not found at {template_path}")
        raise HTTPException(status_code=500, detail="Email template not found")


@user_router.get("/verify", status_code=302)
@user_router.get("/verify/reset-password", status_code=302)
def verify_user_mail(
    token: str, db: Session = Depends(get_db), request: Request = None
):
    """
    Verify a user's email using the verification token, for either email verification or password reset.
    """

    token_data = check_token(token, "verify")
    user_mail = token_data.get("user_id")
    # Determine if the request is for email verification or password reset based on the endpoint
    is_reset_password = request.url.path.endswith("/reset-password")
    redirect_url = (
        f"ergodetect://reset-password?email={user_mail}"
        if is_reset_password
        else "ergodetect://login"
    )
    template_filename = (
        "reset-password.html" if is_reset_password else "expire_link.html"
    )

    # Validate token and retrieve user email

    if not user_mail:
        raise HTTPException(
            status_code=400, detail="Invalid token: 'user_id' claim missing"
        )

    # Query the user from the database
    user = (
        db.query(User)
        .filter(User.email == user_mail, User.sign_up_method == "email")
        .first()
    )

    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Check if verification token is valid
    verify_link_valid = (
        db.query(VerifyMailToken)
        .filter(
            VerifyMailToken.user_id == user.user_id,
            VerifyMailToken.verification_token == token,
        )
        .first()
    )

    if verify_link_valid:
        user.verified = True
        try:
            db.commit()
            return RedirectResponse(url=redirect_url)
        except Exception as e:
            db.rollback()
            logging.error(f"Error during commit: {e}")
            raise HTTPException(status_code=500, detail="Error committing transaction")
    else:
        # Load the appropriate HTML template based on verification type
        return load_expiration_template(template_filename)


@user_router.get("/summary", response_model=SessionSummary)
def get_user_summary(
    session_id: str,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    # Retrieve the user ID
    user_id = current_user["user_id"]

    # Query the database for the user's session
    user_summary = (
        db.query(SittingSession)
        .filter(
            SittingSession.user_id == user_id,
            SittingSession.sitting_session_id == session_id,
        )
        .first()
    )

    # Raise an HTTPException if the session is not found
    if not user_summary:
        raise HTTPException(status_code=404, detail="Session not found")

    # Return the session data using the Pydantic model
    return SessionSummary(
        session_id=str(user_summary.sitting_session_id),
        date=str(user_summary.date),
        file_name=str(user_summary.file_name),
        blink=user_summary.blink,
        sitting=user_summary.sitting,
        distance=user_summary.distance,
        thoracic=user_summary.thoracic,
        duration=user_summary.duration,
    )


@user_router.get("/history", response_model=List[SittingSessionResponse])
def get_user_history(
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
    date_asc: bool = False,
    stream: bool = False,
    video: bool = False,
):
    user_id = current_user["user_id"]
    query = db.query(SittingSession).filter(SittingSession.user_id == user_id)

    # Order by date based on `date_asc` flag
    if date_asc:
        query = query.order_by(SittingSession.date.asc())
    else:
        query = query.order_by(SittingSession.date.desc())

    # Filter by session type if `stream` or `video` is true
    if stream or video:
        session_types = []
        if stream:
            session_types.append("stream")  # Assuming "stream" is the type value
        if video:
            session_types.append("video")  # Assuming "video" is the type value
        query = query.filter(SittingSession.session_type.in_(session_types))

    all_user_sessions = query.all()

    # Prepare response data
    response_data = [
        {
            "sitting_session_id": str(session.sitting_session_id),
            "file_name": session.file_name,
            "thumbnail": session.thumbnail,
            "date": session.date.isoformat(),  # Use `isoformat()` for standardized formatting
            "session_type": session.session_type,
        }
        for session in all_user_sessions
    ]

    return JSONResponse(content=response_data)


@user_router.get("/history/latest")
def get_latest_user_history(
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    # Query the database to get the user's summary data
    user_id = current_user["user_id"]
    latest_user_history = (
        db.query(SittingSession)
        .filter(SittingSession.user_id == user_id, SittingSession.is_complete == True)
        .order_by(
            SittingSession.date.desc()
        )  # Replace 'timestamp' with the actual date column
        .first()
    )

    if latest_user_history:
        response_data = {
            "session_id": str(latest_user_history.sitting_session_id),
            "date": (str(latest_user_history.date)),
            "file_name": str(latest_user_history.file_name),
            "blink": (
                latest_user_history.blink
                if isinstance(latest_user_history.blink, list)
                else []
            ),
            "sitting": (
                latest_user_history.sitting
                if isinstance(latest_user_history.sitting, list)
                else []
            ),
            "distance": (
                latest_user_history.distance
                if isinstance(latest_user_history.distance, list)
                else []
            ),
            "thoracic": (
                latest_user_history.thoracic
                if isinstance(latest_user_history.thoracic, list)
                else []
            ),
            "duration": latest_user_history.duration,
        }
    else:
        response_data = {"error": "Session not found"}

    return JSONResponse(content=response_data)

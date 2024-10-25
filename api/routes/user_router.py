from datetime import datetime
import logging
import os
from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import HTMLResponse, JSONResponse
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError, NoResultFound
from api.request_user import get_current_user
from auth.mail.mail_config import load_email_template
from auth.token import check_token
from database.crud import delete_user, delete_user_sessions
from database.database import get_db
from database.model import SittingSession, User
from database.schemas.User import SittingSessionResponse

user_router = APIRouter()
logger = logging.getLogger(__name__)


@user_router.get("/verify", status_code=200, response_class=HTMLResponse)
def verify_user_mail(token: str, db: Session = Depends(get_db)):
    """
    Verify a user's email using the verification token.
    """
    try:
        # Decode the token and get the 'sub' (email) claim
        token_data = check_token(token, "verify")
        user_mail = token_data.get("sub")

        if not user_mail:
            raise HTTPException(
                status_code=400, detail="Invalid token: 'sub' claim missing"
            )

        # Query the user from the database
        user = (
            db.query(User)
            .filter(User.email == user_mail, User.sign_up_method == "email")
            .first()
        )

        if not user:
            raise HTTPException(status_code=404, detail="User not found")

        # Mark the user as verified
        user.verified = True

        try:
            db.commit()
        except Exception as e:
            logger.error(f"Error during commit: {e}")
            db.rollback()  # Roll back in case of failure
            raise HTTPException(status_code=500, detail="Error committing transaction")

        # Load the success email template and return it
        template_path = os.path.abspath(
            os.path.join(
                os.path.dirname(__file__),
                "..",
                "..",
                "auth",
                "mail",
                "success_verify.html",
            )
        )

        html_content = load_email_template(template_path)

        return HTMLResponse(content=html_content, status_code=200)

    except SQLAlchemyError as e:
        logger.error(f"Database error during email verification: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")
    except Exception as e:
        logger.error(f"Unexpected error during email verification: {e}")
        raise HTTPException(status_code=500, detail="Unexpected internal error")


@user_router.delete("/delete", status_code=status.HTTP_200_OK)
def delete_user_db(
    db: Session = Depends(get_db), current_user=Depends(get_current_user)
):
    """
    Delete the currently authenticated user from the database.
    """
    try:
        # Delete all user sessions for the current user
        delete_user_sessions(db, current_user.email)

        # Delete the user itself
        delete_user(db, current_user.email)

        return {"message": "User and all sessions deleted successfully"}

    except NoResultFound:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
        )

    except SQLAlchemyError as e:
        logger.error(f"Database error when deleting user: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        )

    # Add other fields from the SittingSession model except for user_id


@user_router.get("/history", response_model=List[SittingSessionResponse])
def get_user_history(
    db: Session = Depends(get_db), current_user=Depends(get_current_user)
):
    user_id = current_user["user_id"]
    all_user_sessions = (
        db.query(SittingSession).filter(SittingSession.user_id == user_id).all()
    )

    # Prepare response data
    response_data = []
    for session in all_user_sessions:
        response_data.append(
            {
                "sitting_session_id": str(
                    session.sitting_session_id
                ),  # Convert UUID to string
                "blink": (
                    session.blink if isinstance(session.blink, list) else []
                ),  # Ensure blink is a list
                "sitting": (
                    session.sitting if isinstance(session.sitting, list) else []
                ),  # Ensure sitting is a list
                "distance": (
                    session.distance if isinstance(session.distance, list) else []
                ),  # Ensure distance is a list
                "thoracic": (
                    session.thoracic if isinstance(session.thoracic, list) else []
                ),  # Ensure thoracic is a list
                "file_name": str(session.file_name),  # Ensure file_name is a list
                "date": (
                    session.date.isoformat()
                    if isinstance(session.date, datetime)
                    else str(session.date)
                ),  # Convert datetime to string
            }
        )

    return JSONResponse(content=response_data)

import logging
from fastapi import APIRouter, Depends
from requests import Session
from api.request_user import get_current_user
from database.crud import delete_user, delete_user_sessions
from database.database import get_db
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError, NoResultFound
from api.request_user import get_current_user
from database.crud import delete_user, delete_user_sessions
from database.database import get_db
from database.model import SittingSession


delete_router = APIRouter()
logger = logging.getLogger(__name__)


@delete_router.delete("/user/account", status_code=status.HTTP_200_OK)
def delete_user_account(
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


@delete_router.delete("/session/history", status_code=status.HTTP_200_OK)
def delete_user_history(
    session_id: str,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    # Attempt to delete the session directly
    result = (
        db.query(SittingSession)
        .filter_by(user_id=current_user["user_id"], sitting_session_id=session_id)
        .delete()
    )

    if result == 0:
        # If no rows were deleted, the session was not found
        db.rollback()  # Rollback is good practice here in case any other DB operations were batched
        raise HTTPException(status_code=404, detail="Session not found")

    # If the deletion was successful, commit the transaction
    db.commit()
    return {"detail": "Session deleted successfully"}

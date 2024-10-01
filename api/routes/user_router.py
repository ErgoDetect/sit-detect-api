import logging
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError, NoResultFound
from api.request_user import get_current_user
from database.crud import delete_user, delete_user_sessions
from database.database import get_db

user_router = APIRouter()
logger = logging.getLogger(__name__)

@user_router.delete("/delete/", status_code=status.HTTP_204_NO_CONTENT)
def delete_user_db(
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user)
):
    """
    Delete the currently authenticated user from the database.

    Args:
        db (Session): The database session.
        current_user: The currently authenticated user obtained from the authentication dependency.

    Raises:
        HTTPException: If the user is not found or a database error occurs.
    """
    try:
        # delete_user_sessions(db, current_user.email)
        delete_user(db, current_user.email)
    except NoResultFound:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    except SQLAlchemyError as e:
        logger.error(f"Database error when deleting user: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Internal server error")

from fastapi import APIRouter, Depends, HTTPException, Response, logger
from pydantic import EmailStr
from requests import Session
from api.request_user import get_current_user
from database.crud import delete_user
from database.database import get_db



user_router = APIRouter()

@user_router.delete("/delete/", status_code=204)
def delete_user_db(email: EmailStr, db: Session = Depends(get_db),user_id: str = Depends(get_current_user)):
    try:
        delete_user(db, email)
        return Response(status_code=204)
    except Exception as e:
        logger.error(f"Error deleting user: {e}")
        raise HTTPException(status_code=500, detail=f"Error deleting user: {e}")
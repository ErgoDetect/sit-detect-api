from fastapi import Depends, HTTPException
from requests import Session
from database.crud import create_user, get_user_by_email,get_user_by_id
from database.schemas.UserEmail import EmailCreate
from main import get_db


def sign_up(user: EmailCreate, db: Session = Depends(get_db)):
    if get_user_by_email(db, email=user.email):
        raise HTTPException(status_code=400, detail="Email already registered")
    return create_user(db, user)

def google_sign_up(id:str, db: Session = Depends(get_db)):
    if get_user_by_id(user_id=id, db=db):
        raise HTTPException(status_code=400, detail="Email already registered")
    return create_user(db, id)
from datetime import datetime, timezone
from typing import Dict
from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import EmailStr
from sqlalchemy.orm import Session
from auth.token import verify_token, create_access_token, create_refresh_token, get_token_expiration_times
from database.crud import get_user_by_email, create_user
from database.database import get_db
from database.schemas.User import LoginRequest
from auth.auth import authenticate_user
from pydantic import BaseModel
import os

auth_router = APIRouter()
SECURE_COOKIES = os.getenv("HELLO") == "production"

class LoginResponse(BaseModel):
    access_token: str
    token_type: str

@auth_router.post("/signup/", status_code=201)
def sign_up(email: EmailStr, password: str, display_name: str, db: Session = Depends(get_db)):
    if get_user_by_email(db, email=email):
        raise HTTPException(status_code=400, detail="Email already registered")
    
    # Hash the password
    hashed_password = hash_password(password)
    create_user(db, email, hashed_password, display_name)
    
    return {"message": "User created successfully"}


@auth_router.post("/login/", response_model=LoginResponse)
def login(response: Response, login_data: LoginRequest, db: Session = Depends(get_db)):
    user = authenticate_user(db, login_data.email, login_data.password)
    if not user:
        raise HTTPException(status_code=400, detail="Invalid credentials")

    access_token = create_access_token({"sub": user.user_id, "email": user.email})
    refresh_token = create_refresh_token({"sub": user.user_id})
    access_token_exp_utc, _ = get_token_expiration_times(access_token)
    refresh_token_exp_utc, _ = get_token_expiration_times(refresh_token)

    response.set_cookie("access_token", access_token, httponly=True, expires=access_token_exp_utc, secure=SECURE_COOKIES)
    response.set_cookie("refresh_token", refresh_token, httponly=True, expires=refresh_token_exp_utc, secure=SECURE_COOKIES)

    return {"access_token": access_token, "token_type": "bearer"}


@auth_router.post("/logout/")
def logout(response: Response):
    response.delete_cookie("access_token", path="/")
    response.delete_cookie("refresh_token", path="/")
    return {"message": "Logged out successfully"}


@auth_router.post("/refresh-token/", response_model=Dict[str, str])
def refresh_access_token(response: Response, request: Request):
    refresh_token = request.cookies.get("refresh_token")
    if not refresh_token:
        raise HTTPException(status_code=401, detail="Refresh token not provided")

    # Verify the refresh token
    payload = verify_token(refresh_token)
    user_id = payload.get("sub")
    email = payload.get("email")
    if not user_id:
        raise HTTPException(status_code=401, detail="Invalid refresh token")

    access_token = create_access_token({"sub": user_id, "email": email})

    # Refresh token rotation logic
    refresh_token_expires_utc, _ = get_token_expiration_times(refresh_token)
    current_time = datetime.now(timezone.utc)
    time_until_expiration = refresh_token_expires_utc - current_time

    # If refresh token is about to expire (within 15 days), create a new one
    if time_until_expiration.days <= 15:
        refresh_token = create_refresh_token({"sub": user_id})
        refresh_token_expires_utc, _ = get_token_expiration_times(refresh_token)

        response.set_cookie(
            key="refresh_token",
            value=refresh_token,
            httponly=True,
            secure=SECURE_COOKIES,
            samesite="lax",
            path="/",
            expires=refresh_token_expires_utc
        )

    # Set the new access token in the cookie
    access_token_expires_utc, _ = get_token_expiration_times(access_token)
    response.set_cookie(
        key="access_token",
        value=access_token,
        httponly=True,
        secure=SECURE_COOKIES,
        samesite="lax",
        path="/",
        expires=access_token_expires_utc
    )

    return {"access_token_is_set": True}


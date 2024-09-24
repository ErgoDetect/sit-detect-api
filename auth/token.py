from fastapi import HTTPException, Response
from datetime import datetime, timedelta, timezone
from typing import Dict, Any, Tuple
import jwt
import os

# JWT Secret key and Algorithm
SECRET_KEY = os.getenv("SECRET_KEY", "your-secret-key")
if not SECRET_KEY:
    raise ValueError("SECRET_KEY environment variable is not set")

ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 1
ACCESS_TOKEN_EXPIRE_HOURS = 1
REFRESH_TOKEN_EXPIRE_DAYS = 365

# Define UTC+7 timezone
UTC_PLUS_7 = timezone(timedelta(hours=7))

# Function to create a token with expiration
def create_token(data: Dict[str, Any], expires_delta: timedelta) -> str:
    to_encode = data.copy()
    expire = datetime.now(UTC_PLUS_7) + expires_delta
    to_encode.update({"exp": expire, "iat": datetime.now(UTC_PLUS_7)})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

# Create access token
def create_access_token(data: Dict[str, Any]) -> str:
    expires_delta = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    return create_token(data, expires_delta)

# Create refresh token
def create_refresh_token(data: Dict[str, Any]) -> str:
    expires_delta = timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)
    return create_token(data, expires_delta)

# Verify and decode token
def verify_token(token: str) -> Dict[str, Any]:
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token has expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")

# Extract expiration times from JWT
def get_token_expiration_times(token: str) -> Tuple[datetime, datetime]:
    decoded_token = verify_token(token)
    exp_timestamp = decoded_token.get("exp")

    if exp_timestamp:
        # Convert expiration timestamp to datetime in UTC
        exp_datetime_utc = datetime.fromtimestamp(exp_timestamp, tz=timezone.utc)
        exp_datetime_local = exp_datetime_utc.astimezone(UTC_PLUS_7)
        return exp_datetime_utc, exp_datetime_local
    else:
        raise ValueError("No expiration claim found in the token")

# Set cookies using expiration from JWT
def set_tokens_as_cookies(response: Response, access_token: str, refresh_token: str):
    access_exp_utc, access_exp_local = get_token_expiration_times(access_token)
    refresh_exp_utc, refresh_exp_local = get_token_expiration_times(refresh_token)

    # Set access token as cookie
    response.set_cookie(
        key="access_token",
        value=access_token,
        expires=access_exp_utc,  # Use the UTC expiration time for the cookie
        httponly=True,
        samesite="Lax"
    )

    # Set refresh token as cookie
    response.set_cookie(
        key="refresh_token",
        value=refresh_token,
        expires=refresh_exp_utc,  # Use the UTC expiration time for the cookie
        httponly=True,
        samesite="Lax"
    )

# Example function to generate tokens and set cookies
def generate_and_set_tokens(response: Response, user_data: Dict[str, Any]):
    # Generate tokens
    access_token = create_access_token(user_data)
    refresh_token = create_refresh_token(user_data)

    # Set tokens as cookies in response
    set_tokens_as_cookies(response, access_token, refresh_token)

    return {"access_token": access_token, "refresh_token": refresh_token}

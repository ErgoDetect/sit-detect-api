from datetime import datetime, timedelta, timezone
from typing import Dict, Any
from fastapi import HTTPException
import jwt
import os

# JWT Secret key and Algorithm
SECRET_KEY = os.getenv("SECRET_KEY", "your-secret-key")
if not SECRET_KEY:
    raise ValueError("SECRET_KEY environment variable is not set")

ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 15
REFRESH_TOKEN_EXPIRE_DAYS = 7

# Define UTC+7 timezone
UTC_PLUS_7 = timezone(timedelta(hours=7))

def create_token(data: Dict[str, Any], expires_delta: timedelta) -> str:
    to_encode = data.copy()
    expire = datetime.now(UTC_PLUS_7) + expires_delta
    to_encode.update({"exp": expire, "iat": datetime.now(UTC_PLUS_7)})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

def create_access_token(data: Dict[str, Any]) -> str:
    expires_delta = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    return create_token(data, expires_delta)

def create_refresh_token(data: Dict[str, Any]) -> str:
    expires_delta = timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)
    return create_token(data, expires_delta)

def verify_token(token: str) -> Dict[str, Any]:
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token has expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")
    
from datetime import datetime, timedelta, timezone
from typing import Tuple

def get_expiration_times(utc_plus_7: timezone, access_token_expire_minutes: int, refresh_token_expire_days: int) -> Tuple[datetime, datetime]:
   
    access_token_expires = datetime.now(utc_plus_7) + timedelta(minutes=access_token_expire_minutes)
    refresh_token_expires = datetime.now(utc_plus_7) + timedelta(days=refresh_token_expire_days)

    # Convert to UTC
    access_token_expires_utc = access_token_expires.astimezone(timezone.utc)
    refresh_token_expires_utc = refresh_token_expires.astimezone(timezone.utc)

    return access_token_expires_utc, refresh_token_expires_utc

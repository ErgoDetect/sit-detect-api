from fastapi import HTTPException, Response
from datetime import datetime, timedelta, timezone
from typing import Dict, Any, Tuple
import jwt
import os
import pytz

# Constants for JWT configuration
SECRET_KEY = os.getenv("SECRET_KEY", "your-secret-key")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60  # Access token expiration time
REFRESH_TOKEN_EXPIRE_DAYS = 365   # Refresh token expiration time

# Timezone setup
LOCAL_TZ = pytz.timezone('Asia/Bangkok')

def get_current_time() -> datetime:
    """
    Get the current time in the specified timezone ('Asia/Bangkok').
    """
    return datetime.now(LOCAL_TZ)

def create_token(data: Dict[str, Any], expires_delta: timedelta) -> str:
    """
    Create a JWT token with an expiration time.

    Args:
        data (Dict[str, Any]): Data to include in the token payload.
        expires_delta (timedelta): Time delta until the token expires.
        
    Returns:
        str: Encoded JWT token.
    """
    to_encode = data.copy()
    expire_time = get_current_time() + expires_delta
    to_encode.update({"exp": expire_time, "iat": get_current_time()})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

def create_access_token(data: Dict[str, str]) -> str:
    """
    Create an access token with a predefined expiration time (60 minutes).

    Args:
        data (Dict[str, str]): Data to include in the token payload.
        
    Returns:
        str: Encoded access token.
    """
    return create_token(data, timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES))

def create_refresh_token(data: Dict[str, str]) -> str:
    """
    Create a refresh token with a predefined expiration time (365 days).

    Args:
        data (Dict[str, str]): Data to include in the token payload.
        
    Returns:
        str: Encoded refresh token.
    """
    return create_token(data, timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS))

def verify_token(token: str) -> Dict[str, Any]:
    """
    Verify and decode a JWT token.

    Args:
        token (str): The JWT token to verify.
        
    Returns:
        Dict[str, Any]: Decoded token payload if valid.
        
    Raises:
        HTTPException: If the token is expired or invalid.
    """
    try:
        return jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token has expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")

def get_token_expiration_times(token: str) -> Tuple[datetime, datetime]:
    """
    Get the expiration times (UTC and local) for a given token.

    Args:
        token (str): The JWT token.
        
    Returns:
        Tuple[datetime, datetime]: Tuple containing UTC and local expiration times.
        
    Raises:
        HTTPException: If the token expiration is not found in the payload.
    """
    decoded_token = verify_token(token)
    exp_timestamp = decoded_token.get("exp")
    
    if exp_timestamp is None:
        raise HTTPException(status_code=401, detail="Token expiration time not found")
    
    exp_datetime_utc = datetime.fromtimestamp(exp_timestamp, tz=timezone.utc)
    exp_datetime_local = exp_datetime_utc.astimezone(LOCAL_TZ)
    
    return exp_datetime_utc, exp_datetime_local

def generate_and_set_tokens(response: Response, data: Dict[str, Any], secure: bool = True) -> Dict[str, str]:
    """
    Generate access and refresh tokens and set them as HTTP-only cookies.

    Args:
        response (Response): FastAPI Response object to set cookies.
        data (Dict[str, Any]): Data to include in the token payload.
        secure (bool): Whether the cookies should be marked as secure (True for HTTPS).
        
    Returns:
        Dict[str, str]: Generated access and refresh tokens.
    """
    access_token = create_access_token(data)
    refresh_token = create_refresh_token(data)
    
    access_token_exp_utc, _ = get_token_expiration_times(access_token)
    refresh_token_exp_utc, _ = get_token_expiration_times(refresh_token)

    # Set access token as a secure HTTP-only cookie
    response.set_cookie(
        key="access_token", 
        value=access_token, 
        httponly=True, 
        secure=secure,
        expires=int(access_token_exp_utc.timestamp()), 
        path="/"
    )
    
    # Set refresh token as a secure HTTP-only cookie
    response.set_cookie(
        key="refresh_token", 
        value=refresh_token, 
        httponly=True, 
        secure=secure,
        expires=int(refresh_token_exp_utc.timestamp()), 
        path="/"
    )
    
    return {"access_token": access_token, "refresh_token": refresh_token}

def get_sub_from_token(token: str) -> str:
    """
    Extract the 'sub' (subject) from a JWT token.

    Args:
        token (str): The JWT token.
        
    Returns:
        str: The 'sub' claim from the token (typically the user ID).
        
    Raises:
        HTTPException: If the 'sub' claim is not found or the token is invalid.
    """
    decoded_token = verify_token(token)
    sub = decoded_token.get("sub")
    
    if not sub:
        raise HTTPException(status_code=401, detail="'sub' claim not found in token")
    
    return sub

def check_token(token: str, token_type: str) -> dict:
    """
    Check the validity of a JWT token and return its status.

    Args:
        token (str): The JWT token to check.
        token_type (str): The type of token being checked ("access" or "refresh").
        
    Returns:
        dict: The token's status and corresponding message.
    """
    try:
        user_id = get_sub_from_token(token)
        return {"status": "Authenticated", "user_id": user_id, "message": f"{token_type.capitalize()} token is valid"}
    except HTTPException as e:
        if e.detail == "Token has expired" and token_type == "access":
            return {"status": "Expired", "message": "Access token expired"}
        return {"status": "Invalid", "message": f"{token_type.capitalize()} token is invalid or expired"}

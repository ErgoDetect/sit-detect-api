import logging
from typing import Dict, Any, Tuple
from fastapi import HTTPException, Response
from fastapi.websockets import WebSocketState
import jwt
import os
from datetime import datetime, timedelta, timezone
import pytz
from dotenv import load_dotenv


load_dotenv()  # Need for windows
logger = logging.getLogger(__name__)
# Constants for JWT configuration
SECRET_KEY = os.getenv("SECRET_KEY")
ALGORITHM = "HS256"
VERIFY_TOKEN_EXPIRE_HOURS = 24  # Verification token expiration time
ACCESS_TOKEN_EXPIRE_MINUTES = 60  # Access token expiration time
REFRESH_TOKEN_EXPIRE_DAYS = 365  # Refresh token expiration time

# Timezone setup
LOCAL_TZ = pytz.timezone("Asia/Bangkok")


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
    current_time = get_current_time()
    expire_time = current_time + expires_delta
    to_encode = data.copy()
    to_encode.update({"exp": expire_time, "iat": current_time})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


def create_verify_token(data: Dict[str, str]) -> str:
    """
    Create a verification token with a predefined expiration time (5 minutes).
    """
    return create_token(data, timedelta(hours=VERIFY_TOKEN_EXPIRE_HOURS))


def create_access_token(data: Dict[str, str]) -> str:
    """
    Create an access token with a predefined expiration time (60 minutes).
    """
    return create_token(data, timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES))


def create_refresh_token(data: Dict[str, str]) -> str:
    """
    Create a refresh token with a predefined expiration time (365 days).
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


def get_token_expiration(token: str) -> Tuple[datetime, datetime]:
    """
    Get the expiration times (UTC and local) for a given token.

    Args:
        token (str): The JWT token to extract expiration information from.

    Returns:
        Tuple[datetime, datetime]: Expiration times in both UTC and local timezones.
    """
    decoded_token = verify_token(token)
    exp_timestamp = decoded_token.get("exp")

    if exp_timestamp is None:
        raise HTTPException(status_code=401, detail="Token expiration time not found")

    exp_datetime_utc = datetime.fromtimestamp(exp_timestamp, tz=timezone.utc)
    exp_datetime_local = exp_datetime_utc.astimezone(LOCAL_TZ)

    return exp_datetime_utc, exp_datetime_local


def set_token_cookies(
    response: Response, access_token: str, refresh_token: str
) -> None:
    """
    Set access and refresh tokens as HTTP-only cookies.

    Args:
        response (Response): FastAPI Response object to set cookies.
        access_token (str): The access token to set in cookies.
        refresh_token (str): The refresh token to set in cookies.
        secure (bool): Whether the cookies should be marked as secure (True for HTTPS).
    """
    access_token_exp_utc, _ = get_token_expiration(access_token)
    refresh_token_exp_utc, _ = get_token_expiration(refresh_token)

    # Set access token cookie
    response.set_cookie(
        key="access_token",
        value=access_token,
        httponly=False,
        secure=True,
        expires=int(access_token_exp_utc.timestamp()),
        path="/",
        samesite="none",
    )

    # Set refresh token cookie
    response.set_cookie(
        key="refresh_token",
        value=refresh_token,
        httponly=False,
        secure=True,
        expires=int(refresh_token_exp_utc.timestamp()),
        path="/",
        samesite="none",
    )


def generate_and_set_tokens(response: Response, data: Dict[str, Any]) -> Dict[str, str]:
    """
    Generate access and refresh tokens and set them as HTTP-only cookies.

    Args:
        response (Response): FastAPI Response object to set cookies.
        data (Dict[str, Any]): Data to include in the token payload.

    Returns:
        Dict[str, str]: Generated access and refresh tokens.
    """
    access_token = create_access_token(data)
    refresh_token = create_refresh_token(data)

    # Set cookies for both tokens
    set_token_cookies(response, access_token, refresh_token)

    return {"access_token": access_token, "refresh_token": refresh_token}


def get_sub_from_token(token: str) -> str:
    """
    Extract the 'sub' (subject) from a JWT token.

    Args:
        token (str): The JWT token.

    Returns:
        str: The 'sub' claim from the token.

    Raises:
        HTTPException: If the 'sub' claim is not found.
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
        user_id = get_sub_from_token(token)  # Implement your JWT decoding logic here
        return {
            "status": "Authenticated",
            "user_id": user_id,
            "message": f"{token_type.capitalize()} token is valid",
        }
    except jwt.ExpiredSignatureError:
        return {
            "status": "Expired",
            "message": f"{token_type.capitalize()} token has expired.",
        }
    except jwt.PyJWTError:
        return {
            "status": "Invalid",
            "message": f"{token_type.capitalize()} token is invalid.",
        }
    except Exception as e:
        logger.error(f"Unexpected error during token validation: {str(e)}")
        return {
            "status": "Error",
            "message": f"An error occurred while validating the {token_type} token.",
        }

import jwt
import os
import datetime
from typing import Dict, Any
from fastapi import HTTPException

# JWT Secret key and Algorithm
SECRET_KEY = os.getenv("SECRET_KEY", "your-secret-key")
ALGORITHM = "HS256"

# Token expiration times
ACCESS_TOKEN_EXPIRE_MINUTES = 15  # 15 minutes for access token
REFRESH_TOKEN_EXPIRE_DAYS = 7  # 7 days for refresh token

def create_token(data: Dict[str, Any], expires_delta: datetime.timedelta) -> str:
    """
    Create a JWT token with the given data and expiration delta.

    Args:
        data (Dict[str, Any]): The payload to include in the token.
        expires_delta (datetime.timedelta): The time duration until the token expires.

    Returns:
        str: The encoded JWT token.
    """
    to_encode = data.copy()
    expire = datetime.datetime.utcnow() + expires_delta
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

def create_access_token(data: Dict[str, Any]) -> str:
    """
    Create a JWT access token.

    Args:
        data (Dict[str, Any]): The payload to include in the token.

    Returns:
        str: The encoded JWT access token.
    """
    return create_token(data, datetime.timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES))

def create_refresh_token(data: Dict[str, Any]) -> str:
    """
    Create a JWT refresh token.

    Args:
        data (Dict[str, Any]): The payload to include in the token.

    Returns:
        str: The encoded JWT refresh token.
    """
    return create_token(data, datetime.timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS))

def verify_token(token: str) -> Dict[str, Any]:
    """
    Verify a JWT token and return its payload.

    Args:
        token (str): The JWT token to verify.

    Returns:
        Dict[str, Any]: The decoded token payload.

    Raises:
        HTTPException: If the token is expired or invalid.
    """
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token has expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")

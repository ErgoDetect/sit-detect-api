import jwt
import os
import datetime
from typing import Dict, Any
from fastapi import HTTPException

# JWT Secret key and Algorithm
SECRET_KEY = os.getenv("SECRET_KEY", "your-secret-key")
if not SECRET_KEY:
    raise ValueError("SECRET_KEY environment variable is not set")

ALGORITHM = "HS256"

# Token expiration times
ACCESS_TOKEN_EXPIRE_MINUTES = 15  # 15 minutes for access token
REFRESH_TOKEN_EXPIRE_DAYS = 7     # 7 days for refresh token

def create_token(data: Dict[str, Any], expires_delta: datetime.timedelta) -> str:
    """
    Create a JWT token with a given expiration time.
    
    Args:
        data (Dict[str, Any]): The payload data to encode in the token.
        expires_delta (datetime.timedelta): The expiration time for the token.
        
    Returns:
        str: The encoded JWT token.
    """
    to_encode = data.copy()
    expire = datetime.datetime.utcnow() + expires_delta
    to_encode.update({"exp": expire, "iat": datetime.datetime.utcnow()})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

def create_access_token(data: Dict[str, Any]) -> str:
    """
    Create an access token that expires in a fixed amount of time.
    
    Args:
        data (Dict[str, Any]): The payload data to encode in the token.
        
    Returns:
        str: The encoded access token.
    """
    expires_delta = datetime.timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    return create_token(data, expires_delta)

def create_refresh_token(data: Dict[str, Any]) -> str:
    """
    Create a refresh token that expires in a fixed amount of time.
    
    Args:
        data (Dict[str, Any]): The payload data to encode in the token.
        
    Returns:
        str: The encoded refresh token.
    """
    expires_delta = datetime.timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)
    return create_token(data, expires_delta)

def verify_token(token: str) -> Dict[str, Any]:
    """
    Verify and decode a JWT token.
    
    Args:
        token (str): The JWT token to verify.
        
    Returns:
        Dict[str, Any]: The decoded token payload.
        
    Raises:
        HTTPException: If the token is invalid or expired.
    """
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token has expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")

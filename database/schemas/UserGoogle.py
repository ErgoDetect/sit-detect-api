from pydantic import BaseModel, EmailStr
from typing import Optional

# Schema for OAuthToken
class OAuthTokenBase(BaseModel):
    refresh_token: Optional[str]
    expires_in: Optional[int]

class OAuthTokenCreate(BaseModel):
    refresh_token: str  # We keep the refresh token from Google
    access_token: str   # Used for fetching user data from Google
    expires_in: Optional[int]  # Token expiration time

class OAuthToken(OAuthTokenBase):
    id: str
    user_id: int

    class Config:
        from_attributes = True

# Google Sign-up Data Response Schema (for internal use)
class GoogleUserData(BaseModel):
    id: str  # Google's unique user ID
    email: EmailStr
    picture: Optional[str] = None  # Profile picture URL from Google
    name: Optional[str] = None  # User's full name (display_name)

# Schema for token response when requesting access tokens
class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str
    expires_in: int

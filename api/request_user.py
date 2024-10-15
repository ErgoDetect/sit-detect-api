from fastapi import HTTPException, Request
from auth.token import verify_token


# Dependency to get the current user from the token
async def get_current_user(request: Request):
    token = request.cookies.get("access_token")
    if not token:
        raise HTTPException(status_code=401, detail="No access token provided")

    try:
        payload = verify_token(token)
        user_id = payload.get("sub")  # 'sub' is typically the user identifier in JWTs
        email = payload.get("email")
        
        # Use 'and' to ensure both user_id and email are present
        if not user_id or not email:
            raise HTTPException(status_code=401, detail="Invalid access token payload")
        
        # Return user info or user_id as needed
        return {"user_id": user_id, "email": email}
    
    except HTTPException:
        raise  # Re-raise the HTTPException if it's already been raised
    except Exception as e:
        # Catch any other exceptions and return an error message
        raise HTTPException(status_code=401, detail=f"Could not validate credentials: {str(e)}")

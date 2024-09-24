from fastapi import HTTPException, Request
from auth.token import verify_token


# Dependency to get the current user from the token
async def get_current_user(request: Request):
    token = request.cookies.get("access_token")
    if not token:
        raise HTTPException(status_code=401, detail="No access token provided")
    try:
        payload = verify_token(token)
        user_id = payload.get("sub")
        email = payload.get("email")
        if not user_id & email:
            raise HTTPException(status_code=401, detail="Invalid access token payload")
        return user_id
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=401, detail=f"Could not validate credentials: {str(e)}")

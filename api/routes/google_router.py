import asyncio
import json
import os
import logging
from fastapi import APIRouter, Request, Depends, Response, HTTPException
from fastapi.responses import JSONResponse, StreamingResponse
from sqlalchemy.orm import Session
from google_auth_oauthlib.flow import Flow
from dotenv import load_dotenv
from api.storage import oauth_results
from auth.token import create_access_token, create_refresh_token, get_token_expiration_times
from database.crud import create_user_google, get_user_by_email
from database.database import get_db

# Load environment variables
load_dotenv()
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Set environment for OAuth flow
os.environ["OAUTHLIB_INSECURE_TRANSPORT"] = "1"  # Allow HTTP for testing

GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID")
GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET")

# Validate Google credentials
if not GOOGLE_CLIENT_ID or not GOOGLE_CLIENT_SECRET:
    raise ValueError("Google OAuth credentials are missing")

REDIRECT_URI = "http://localhost:8000/auth/google/callback/"

# OAuth Flow configuration
flow = Flow.from_client_config(
    {
        "web": {
            "client_id": GOOGLE_CLIENT_ID,
            "client_secret": GOOGLE_CLIENT_SECRET,
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
            "redirect_uris": [REDIRECT_URI],
        }
    },
    scopes=[
        'openid',
        'https://www.googleapis.com/auth/userinfo.profile',
        'https://www.googleapis.com/auth/userinfo.email'
    ],
    redirect_uri=REDIRECT_URI
)

google_router = APIRouter()

# Step 1: Initiate Google OAuth Flow
async def google_login():
    try:
        authorization_url, state = flow.authorization_url(
            access_type="offline",
            include_granted_scopes="true",
            prompt="select_account"
        )
        oauth_results['state'] = state
        return JSONResponse(content={"url": authorization_url})
    except Exception as e:
        logger.error(f"Error during Google login initiation: {e}")
        raise HTTPException(status_code=500, detail="An error occurred during Google login initiation.")

@google_router.get("/login/")
async def login_with_google():
    return await google_login()

# Step 2: Callback Route for Google OAuth
async def google_callback(request: Request, db: Session = Depends(get_db)):
    code = request.query_params.get("code")
    state = request.query_params.get("state")

    if not code:
        raise HTTPException(status_code=401, detail="Missing authorization code from Google.")
    
    if state != oauth_results.get('state'):
        raise HTTPException(status_code=400, detail="Invalid state parameter.")

    try:
        flow.fetch_token(code=code)
        session = flow.authorized_session()
        user_info = session.get("https://www.googleapis.com/oauth2/v1/userinfo").json()

        if not user_info or 'email' not in user_info:
            raise HTTPException(status_code=400, detail="Failed to retrieve user info from Google.")
        
        existing_user = get_user_by_email(db, email=user_info['email'])

        if not existing_user:
            create_user_google(db, user_id=user_info['id'], user_email=user_info['email'])
        
        oauth_results['user'] = {
            'user_id': user_info['id'],
            'user_email': user_info['email'],
            'success': True,
        }

        return {"message": "Callback processed successfully"}

    except Exception as e:
        logger.error(f"Error during Google token exchange: {e}")
        raise HTTPException(status_code=500, detail="An error occurred during token exchange with Google.")

@google_router.get("/callback/")
async def callback_from_google(request: Request, db: Session = Depends(get_db)):
    return await google_callback(request, db)

# Set cookies after authentication
@google_router.get("/set-cookies/")
async def set_cookies(response: Response):
    user = oauth_results.get('user')
    if not user or 'user_email' not in user:
        raise HTTPException(status_code=400, detail="User email not found in results")

    user_email = user['user_email']
    access_token = create_access_token({"sub": user_email})
    refresh_token = create_refresh_token({"sub": user_email})

    access_token_exp_utc, _ = get_token_expiration_times(access_token)
    refresh_token_exp_utc, _ = get_token_expiration_times(refresh_token)



    response.set_cookie(
        key="access_token", 
        value=access_token, 
        httponly=True, 

        samesite="lax", 
        path="/", 
        expires=access_token_exp_utc,
    )
    response.set_cookie(
        key="refresh_token", 
        value=refresh_token, 
        httponly=True, 

        samesite="lax", 
        path="/", 
        expires=refresh_token_exp_utc
    )
    return {"message": "Cookies set successfully"}

# SSE for real-time updates
@google_router.get("/sse/")
async def google_sse():
    async def event_generator():
        while 'user' not in oauth_results:
            await asyncio.sleep(1)
            yield ": keep-alive\n\n"
        
        result = oauth_results.get('user')
        if result:
            yield f"data: {json.dumps(result)}\n\n"
        else:
            logger.error("No 'user' found in OAuth results.")
            yield f"data: {json.dumps({'error': 'User not found'})}\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")

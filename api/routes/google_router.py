import asyncio
from datetime import timedelta
import json
import logging
import uuid
from fastapi import APIRouter, Request, Depends, Response, HTTPException
from fastapi.responses import JSONResponse, StreamingResponse
from sqlalchemy.orm import Session
from google_auth_oauthlib.flow import Flow
from database.crud import create_user_google, delete_user_sessions, get_user_by_email
from database.database import get_db
from auth.token import generate_and_set_tokens, get_current_time
import os

from database.model import UserSession

# Initialize Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Set environment variables for OAuth flow
os.environ["OAUTHLIB_INSECURE_TRANSPORT"] = "1"  # Allow HTTP for testing

# Load Google OAuth credentials
GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID")
GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET")

# Validate Google credentials
if not GOOGLE_CLIENT_ID or not GOOGLE_CLIENT_SECRET:
    raise ValueError("Google OAuth credentials are missing")

REDIRECT_URI = "http://localhost:8000/auth/google/callback/"

# Dictionary to store OAuth flow state and user information securely
oauth_results = {}
oauth_lock = asyncio.Lock()  # Ensures safe concurrent access

# OAuth Flow configuration
def get_google_flow():
    """Helper function to create a new OAuth Flow instance."""
    return Flow.from_client_config(
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

# Helper function to store user info
async def store_oauth_result(key, value):
    async with oauth_lock:
        oauth_results[key] = value

async def get_oauth_result(key):
    async with oauth_lock:
        return oauth_results.get(key)

# Helper function to exchange code for Google user info
async def exchange_google_code_for_user_info(flow, code):
    flow.fetch_token(code=code)
    session = flow.authorized_session()
    user_info = session.get("https://www.googleapis.com/oauth2/v1/userinfo").json()
    if not user_info or 'email' not in user_info:
        raise HTTPException(status_code=400, detail="Failed to retrieve user info from Google.")
    return user_info

# Step 1: Initiate Google OAuth Flow
@google_router.get("/login/")
async def login_with_google(request: Request):
    try:
        device_identifier = request.headers.get("Device-Identifier")
        if not device_identifier:
            raise HTTPException(status_code=400, detail="Device identifier is missing")

        flow = get_google_flow()
        authorization_url, state = flow.authorization_url(
            access_type="offline",
            include_granted_scopes="true",
            prompt="select_account",
        )

        # Store the state and device identifier for the callback
        await store_oauth_result('state', state)
        await store_oauth_result('device_identifier', device_identifier)
        return JSONResponse(content={"url": authorization_url})

    except Exception as e:
        logger.error(f"Error during Google login initiation: {e}")
        raise HTTPException(status_code=500, detail="An error occurred during Google login initiation.")

# Step 2: Callback Route for Google OAuth
@google_router.get("/callback/")
async def callback_from_google(response: Response, request: Request, db: Session = Depends(get_db)):
    try:
        flow = get_google_flow()
        code = request.query_params.get("code")
        state = request.query_params.get("state")

        stored_state = await get_oauth_result('state')
        if not code or state != stored_state:
            raise HTTPException(status_code=400, detail="Invalid state or authorization code.")

        # Exchange the code for user info
        user_info = await exchange_google_code_for_user_info(flow, code)

        # Check if user exists, create if not
        existing_user = get_user_by_email(db, email=user_info['email'])
        if not existing_user:
            create_user_google(db, user_id=user_info['id'], user_email=user_info['email'])

        user_id = user_info['id']  # Google user ID

        # Fetch Device-Identifier from stored results
        device_identifier = await get_oauth_result('device_identifier')
        if not device_identifier:
            raise HTTPException(status_code=400, detail="Device identifier missing")

        # Invalidate existing sessions for this user on the current device
        delete_user_sessions(db, user_id, device_identifier)

        # Create a new session
        session_id = str(uuid.uuid4())
        current_time = get_current_time()
        new_session = UserSession(
            session_id=session_id,
            user_id=user_id,
            device_identifier=device_identifier,
            created_at=current_time,
            expires_at=current_time + timedelta(hours=1)
        )
        db.add(new_session)
        db.commit()

        # Generate and set tokens as HTTP-only cookies
        

        # Store user info for SSE or future use
        await store_oauth_result('user', {
            'user_id': user_info['id'],
            'user_email': user_info['email'],
            'device_identifier': device_identifier,
            'success': True
        })

        return {"message": "Callback processed successfully, tokens set"}

    except Exception as e:
        logger.error(f"Error during Google token exchange: {e}")
        raise HTTPException(status_code=500, detail="Error during token exchange with Google.")

# Set cookies after Google authentication
@google_router.get("/set-cookies/")
async def set_cookies(response: Response):
    user = await get_oauth_result('user')
    if not user or 'user_email' not in user:
        raise HTTPException(status_code=400, detail="User email not found in results")

    generate_and_set_tokens(response, {"sub": user['user_id'], "email": user['user_email']})
    return {"message": "Cookies set successfully"}

# SSE for real-time updates
@google_router.get("/sse/")
async def google_sse():
    async def event_generator():
        # Wait until 'user' is set in oauth_results
        while True:
            user = await get_oauth_result('user')
            if user:
                yield f"data: {json.dumps(user)}\n\n"
                break
            await asyncio.sleep(1)
            yield ": keep-alive\n\n"  # Keep the SSE connection alive

    return StreamingResponse(event_generator(), media_type="text/event-stream")

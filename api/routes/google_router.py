import asyncio
from datetime import timedelta, datetime
import json
import logging
import uuid
from fastapi import APIRouter, Header, Request, Depends, Response, HTTPException
from fastapi.responses import JSONResponse, StreamingResponse
from sqlalchemy.orm import Session
from google_auth_oauthlib.flow import Flow
from database.crud import (
    create_user_google,
    delete_user_sessions,
    get_user_by_email,
)
from database.database import get_db
from auth.token import generate_and_set_tokens
import os
from database.model import OAuthState, User, UserSession

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


# Helper function to get current time
def get_current_time():
    return datetime.utcnow()


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
            "openid",
            "https://www.googleapis.com/auth/userinfo.profile",
            "https://www.googleapis.com/auth/userinfo.email",
        ],
        redirect_uri=REDIRECT_URI,
    )


google_router = APIRouter()


# Helper function to store OAuth state
def store_oauth_state(db: Session, state: str, device_identifier: str):
    """Stores OAuth state with expiration."""
    oauth_state = OAuthState(
        state=state,
        device_identifier=device_identifier,
        expires_at=get_current_time()
        + timedelta(minutes=15),  # State expires in 15 minutes
    )
    db.add(oauth_state)
    db.commit()


# Helper function to exchange code for Google user info
def exchange_google_code_for_user_info(flow, code):
    """Fetches Google user info using OAuth code."""
    flow.fetch_token(code=code)
    session = flow.authorized_session()
    user_info = session.get("https://www.googleapis.com/oauth2/v1/userinfo").json()
    if not user_info or "email" not in user_info:
        raise HTTPException(
            status_code=400, detail="Failed to retrieve user info from Google."
        )
    return user_info


# Step 1: Initiate Google OAuth Flow
@google_router.get("/login")
async def login_with_google(request: Request, db: Session = Depends(get_db)):
    """Initiates the Google OAuth flow."""
    device_identifier = request.headers.get("Device-Identifier")
    if not device_identifier:
        raise HTTPException(status_code=400, detail="Device identifier is missing")

    try:
        flow = get_google_flow()
        authorization_url, state = flow.authorization_url(
            access_type="offline",
            include_granted_scopes="true",
            prompt="select_account",
        )

        # Store OAuth state
        store_oauth_state(db, state, device_identifier)
        return JSONResponse(content={"url": authorization_url})

    except Exception as e:
        logger.error(f"Error during Google login initiation: {e}")
        raise HTTPException(
            status_code=500, detail="An error occurred during Google login initiation."
        )


# Step 2: Callback Route for Google OAuth
@google_router.get("/callback/")
async def callback_from_google(
    response: Response, request: Request, db: Session = Depends(get_db)
):
    """Handles the Google OAuth callback and user session management."""
    code = request.query_params.get("code")
    state = request.query_params.get("state")

    if not code or not state:
        raise HTTPException(
            status_code=400, detail="Missing state or authorization code."
        )

    try:
        # Retrieve OAuth state and verify its existence
        stored_state = db.query(OAuthState).filter(OAuthState.state == state).first()
        if not stored_state:
            raise HTTPException(
                status_code=400, detail="Invalid state or authorization code."
            )

        # Exchange authorization code for user info
        flow = get_google_flow()
        user_info = exchange_google_code_for_user_info(flow, code)

        # Create or update user in the database
        user = get_user_by_email(db, email=user_info["email"], sign_up_method="google")
        if not user:
            user = create_user_google(
                db, user_id=user_info["id"], user_email=user_info["email"]
            )

        # Manage user sessions
        device_identifier = stored_state.device_identifier
        delete_user_sessions(
            db, user_id=user_info["id"], device_identifier=device_identifier
        )

        # Create a new user session
        new_session = UserSession(
            session_id=str(uuid.uuid4()),
            user_id=user_info["id"],
            device_identifier=device_identifier,
            created_at=get_current_time(),
            expires_at=get_current_time()
            + timedelta(hours=1),  # Session valid for 1 hour
        )
        db.add(new_session)

        # Mark OAuth state as successful and remove it
        stored_state.success = True

        # Commit all changes in a single transaction
        db.commit()

        return {"message": "Callback successful"}

    except Exception as e:
        logger.exception("Error during Google token exchange: %s", e)
        raise HTTPException(
            status_code=500, detail="Error during token exchange with Google."
        )


# Set cookies after Google authentication
@google_router.post("/set-cookies")
async def set_cookies(
    request: Request, response: Response, db: Session = Depends(get_db)
):
    """Sets authentication cookies for the user."""

    device_identifier = request.headers.get("Device-Identifier")
    user = (
        db.query(User)
        .join(UserSession)
        .filter(UserSession.device_identifier == device_identifier)
        .first()
    )

    if not user:
        raise HTTPException(status_code=400, detail="User not found")
    if not user.email:
        raise HTTPException(status_code=400, detail="User email not found in results")

    generate_and_set_tokens(response, {"sub": user.user_id, "email": user.email})
    return {"message": "Cookies set successfully"}


# SSE for real-time updates
@google_router.get("/sse")
async def google_sse(device_identifier: str, db: Session = Depends(get_db)):
    """Server-Sent Events for real-time updates."""

    async def event_generator():
        timeout = 60  # Set a shorter timeout for debugging
        start_time = get_current_time()

        while True:
            # Fetch the OAuth state for the given device_identifier
            status = (
                db.query(OAuthState)
                .filter(
                    OAuthState.device_identifier == device_identifier,
                    OAuthState.success == True,
                )
                .first()
            )

            # Log each check
            print(f"Checking OAuth state for device_identifier: {device_identifier}")

            # If success is True, send success event
            if status:
                print(
                    f"OAuth state success found for device_identifier: {device_identifier}"
                )
                yield f"data: {json.dumps({'success': True})}\n\n"

                # Now, delete the status after successfully notifying the client
                db.delete(status)
                logger.info(
                    f"Deleted OAuth state for device_identifier: {device_identifier}"
                )
                db.commit()  # Ensure the deletion is committed
                break  # Stop after success

            await asyncio.sleep(1)

            # Send keep-alive message
            yield ": keep-alive\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")

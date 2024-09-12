from fastapi import FastAPI, HTTPException, Request, Depends
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from google_auth_oauthlib.flow import Flow
import os
import logging
from api.storage import oauth_results
from database.crud import create_user_google, get_user_by_email
from database.database import get_db

app = FastAPI()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Set up environment variables for OAuth 2.0 flow
os.environ["OAUTHLIB_INSECURE_TRANSPORT"] = "1"  # Allow HTTP (for testing purposes)

GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID")
GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET")
REDIRECT_URI = "http://localhost:8000/auth/google/callback/"

# OAuth 2.0 flow configuration
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

#* Google OAuth: Step 1 - Initiate Google OAuth Flow
async def google_login():
    try:
        authorization_url, state = flow.authorization_url(
            access_type="offline",
            include_granted_scopes="true"
        )
        
        # Save state in the oauth_results store for later verification
        oauth_results['state'] = state
        
        return JSONResponse(content={"url": authorization_url})

    except Exception as e:
        logger.error(f"Error during Google login initiation: {e}")
        raise HTTPException(status_code=500, detail="An error occurred during Google login initiation.")

#* Google OAuth: Step 2 - Callback Route for Google OAuth
async def google_callback(request: Request, db: Session = Depends(get_db)):
    code = request.query_params.get("code")
    state = request.query_params.get("state")

    if not code:
        raise HTTPException(status_code=401, detail="Missing authorization code from Google.")
    
    if state != oauth_results.get('state'):
        raise HTTPException(status_code=400, detail="Invalid state parameter.")
    
    try:
        # Fetch token using the authorization code
        flow.fetch_token(code=code)
        credentials = flow.credentials
        
        # Get user info from Google
        session = flow.authorized_session()
        user_info = session.get("https://www.googleapis.com/oauth2/v1/userinfo").json()


        existing_user = get_user_by_email(db, email=user_info['email'])
        
        if not existing_user:
            # Create a new user in the database
            create_user_google(db, user_id=user_info['id'], user_email=user_info['email'])
            
        oauth_results['user'] = {
            'user_id': user_info['id'],
            'user_email': user_info['email'],
            'success': True,
        }

        return {"message": "Callback processed successfully"}
    
    except Exception as e:
        logger.error(f"Error during Google token exchange: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="An error occurred during token exchange with Google.")
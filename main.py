import asyncio
from typing import Dict
from fastapi import FastAPI, Depends, HTTPException, WebSocket, Request,Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from api.request_user import get_current_user
from auth.auth import authenticate_user
from auth.token import create_access_token, create_refresh_token, verify_token
from database.database import engine, SessionLocal
import database.model as model
from database.schemas.UserEmail import EmailCreate
from database.schemas.Login import Login
from database.crud import create_user, get_user_by_email, delete_user
from api.image_processing import upload_images, download_file
from api.websocket_received import process_landmark_results
import logging
import os
import platform
from dotenv_vault import load_dotenv
from api.google_oauth import google_login, google_callback
import json
from api.storage import oauth_results
from database.database import get_db



# Load environment variables
load_dotenv()

# macOS-specific settings
if platform.system() == "Darwin":
    os.environ['KMP_DUPLICATE_LIB_OK'] = 'True'

# Initialize FastAPI app
app = FastAPI()

# CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:1212"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Create all tables
model.Base.metadata.create_all(bind=engine)

# Dependency to get database session
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@app.get("/user/agent")
async def some_endpoint(request: Request):
    user_agent = request.headers.get("User-Agent")
    print(f"User-Agent: {user_agent}")
    # You can then parse the User-Agent string to identify the client
    return {"message": "Request received"}


# SSE to stream OAuth results
@app.get("/auth/google/sse")
async def google_sse():
    async def event_generator():
        while 'user' not in oauth_results:
            await asyncio.sleep(1)  # Poll every second

        latest_results = oauth_results.pop('user', None)
        logger.info(f"Sending OAuth results via SSE: {latest_results}")
        yield f"data: {json.dumps(latest_results)}\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")

# Endpoint to get user info by token
@app.get('/user/info/', response_model=Dict[str, str])
async def get_user_info(request: Request, current_user: str = Depends(get_current_user)):
    return {"user": current_user}

# User sign-up by email
@app.post("/signup/", status_code=201)
def sign_up(user: EmailCreate, db: Session = Depends(get_db)):
    if get_user_by_email(db, email=user.email):
        raise HTTPException(status_code=400, detail="Email already registered")
    return create_user(db, user)

# User login
@app.post("/auth/login", response_model=Dict[str, str])
def login(user_credentials: Login,response: Response, db: Session = Depends(get_db)):
    user = authenticate_user(db, user_credentials.email, user_credentials.password)
    if not user:
        raise HTTPException(status_code=400, detail="Invalid credentials")

    access_token = create_access_token({"sub": user_credentials.email})
    refresh_token = create_refresh_token({"sub": user_credentials.email})

     # Set cookies
    response.set_cookie(key="access_token", value=access_token, httponly=True, secure=False, samesite="Lax",path="/")
    response.set_cookie(key="refresh_token", value=refresh_token, httponly=True, secure=False, samesite="Lax",path="/")
    
    return {"message": "Tokens set in cookies"}

# Refresh access token using refresh token
@app.post("/auth/refresh", response_model=Dict[str, str])
def refresh_token(refresh_token: str):
    payload = verify_token(refresh_token)
    email = payload.get("sub")
    if not email:
        raise HTTPException(status_code=401, detail="Invalid refresh token")

    access_token = create_access_token({"sub": email})
    return {
        "access_token": access_token,
        "token_type": "bearer"
    }

# Google OAuth routes
@app.get("/auth/google")
async def login_with_google():
    return await google_login()

@app.get("/auth/google/callback")
async def callback_from_google(request: Request, db: Session = Depends(get_db)):
    return await google_callback(request, db)

# Delete user by email
@app.delete("/user/{email}", status_code=204)
def delete_user_DB(email: str, db: Session = Depends(get_db)):
    try:
        return delete_user(db, email)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error deleting user: {e}")

# Upload images route
@app.post("/upload-images")
async def handle_upload_images(files: list):
    return await upload_images(files)

# Download file route
@app.get("/download/{filename}")
async def handle_download_file(filename: str):
    return download_file(filename)

# WebSocket route for video landmark processing
@app.websocket("/landmark-results")
async def handle_landmark_results(websocket: WebSocket):
    await process_landmark_results(websocket)

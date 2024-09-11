import asyncio
import logging
import os
import platform
import json
from typing import Dict

from fastapi import FastAPI, Depends, HTTPException, Request, Response, WebSocket
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
from api.google_oauth import google_login, google_callback
from api.storage import oauth_results

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

# Load environment variables and platform-specific settings
def load_config():
    from dotenv_vault import load_dotenv
    load_dotenv()
    if platform.system() == "Darwin":
        os.environ['KMP_DUPLICATE_LIB_OK'] = 'True'

load_config()


#* User Endpoints

@app.get('/user/info/', response_model=Dict[str, str])
async def get_user_info(current_user: str = Depends(get_current_user)):
    return {"user": current_user}

@app.delete("/user/{email}", status_code=204)
def delete_user_DB(email: str, db: Session = Depends(get_db)):
    try:
        return delete_user(db, email)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error deleting user: {e}")


#* Email Endpoints

@app.post("/signup/", status_code=201)
def sign_up(user: EmailCreate, db: Session = Depends(get_db)):
    if get_user_by_email(db, email=user.email):
        raise HTTPException(status_code=400, detail="Email already registered")
    return create_user(db, user)

@app.post("/auth/login", response_model=Dict[str, str])
def login(user_credentials: Login, response: Response, db: Session = Depends(get_db)):
    user = authenticate_user(db, user_credentials.email, user_credentials.password)
    if not user:
        raise HTTPException(status_code=400, detail="Invalid credentials")

    access_token = create_access_token({"sub": user_credentials.email})
    refresh_token = create_refresh_token({"sub": user_credentials.email})

    response.set_cookie(key="access_token", value=access_token, httponly=True, secure=False, samesite="lax", path="/")
    response.set_cookie(key="refresh_token", value=refresh_token, httponly=True, secure=False, samesite="lax", path="/")
    
    return {"message": "Tokens set in cookies"}

#* Token Endpoints

@app.post("/auth/refresh", response_model=Dict[str, str])
def refresh_token(refresh_token: str):
    payload = verify_token(refresh_token)
    email = payload.get("sub")
    if not email:
        raise HTTPException(status_code=401, detail="Invalid refresh token")

    access_token = create_access_token({"sub": email})
    return {"access_token": access_token, "token_type": "bearer"}

#* Google Endpoints

@app.get("/auth/google")
async def login_with_google():
    return await google_login()

@app.get("/auth/google/callback")
async def callback_from_google(request: Request, db: Session = Depends(get_db)):
    return await google_callback(request, db)

@app.get("/auth/google/set-cookies")
async def set_cookies(response: Response):
    user = oauth_results.get('user')
    if not user or 'user_email' not in user:
        return {"error": "User email not found in results"}

    user_email = user['user_email']
    access_token = create_access_token({"sub": user_email})
    refresh_token = create_refresh_token({"sub": user_email})

    response.set_cookie(key="access_token", value=access_token, httponly=True, secure=False, samesite="lax", path="/")
    response.set_cookie(key="refresh_token", value=refresh_token, httponly=True, secure=False, samesite="lax", path="/")
    
    oauth_results.clear()

    logger.debug(f"Cookies set: access_token={access_token}, refresh_token={refresh_token}")
    return {"message": "Cookies set successfully"}

@app.get("/auth/google/sse")
async def google_sse():
    async def event_generator():
        while 'user' not in oauth_results:
            await asyncio.sleep(1)
            yield ": keep-alive\n\n"
        
        result = oauth_results
        if result:
            yield f"data: {json.dumps(result)}\n\n"
        else:
            logger.error("No 'user' found in OAuth results.")

    return StreamingResponse(event_generator(), media_type="text/event-stream")


#* Core Logic Endpoints

@app.post("/upload-images")
async def handle_upload_images(files: list):
    return await upload_images(files)

@app.get("/download/{filename}")
async def handle_download_file(filename: str):
    return download_file(filename)

@app.websocket("/landmark-results")
async def handle_landmark_results(websocket: WebSocket):
    await process_landmark_results(websocket)

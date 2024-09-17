import asyncio
import logging
import os
import platform
import json
from typing import Dict, List

from fastapi import Body, FastAPI, Depends, HTTPException, Request, Response, WebSocket
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from fastapi.openapi.utils import get_openapi
from pydantic import EmailStr
from sqlalchemy.orm import Session

from api.request_user import get_current_user
from auth.auth import authenticate_user
from auth.token import create_access_token, create_refresh_token, verify_token
from database.database import engine, SessionLocal
import database.model as model
from database.crud import create_user, get_user_by_email, delete_user
from api.image_processing import receive_upload_images, download_file
from api.websocket_received import process_landmark_results
from api.google_oauth import google_login, google_callback
from api.storage import oauth_results
from database.schemas.User import LoginRequest
from dotenv_vault import load_dotenv

# load_dotenv()
# Initialize FastAPI app
app = FastAPI()

origins = ["http://localhost:1212"]

# CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
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


# custom api document

def custom_openapi():
    if app.openapi_schema:
        return app.openapi_schema
    openapi_schema = get_openapi(
        title="WebSocket API",
        version="1.0.0",
        description="This is a simple WebSocket API",
        routes=app.routes,
    )
    openapi_schema["paths"]["/landmark/results/"] = {
        "get": {
            "summary": "WebSocket connection",
            "description": "Connect to the WebSocket server. Send a message and receive a response.",
            "responses": {
                "101": {
                    "description": "Switching Protocols - The client is switching protocols as requested by the server.",
                }
            }
        }
    }
    app.openapi_schema = openapi_schema
    return app.openapi_schema

app.openapi = custom_openapi

# User Endpoints
@app.get('/user/info/', response_model=Dict[str, str])
async def get_user_info(current_user: str = Depends(get_current_user)):
    return {"user": current_user}


@app.delete("/user/delete/", status_code=204)
def delete_user_db(email: EmailStr, db: Session = Depends(get_db)):
    try:
        delete_user(db, email)
        return Response(status_code=204)
    except Exception as e:
        logger.error(f"Error deleting user: {e}")
        raise HTTPException(status_code=500, detail=f"Error deleting user: {e}")
    
@app.post("/auth/logout/")
def logout(response: Response):
    response.delete_cookie(key="access_token", path="/")
    response.delete_cookie(key="refresh_token", path="/")
    return {"message": "Logged out successfully"}


# Email Endpoints
@app.post("/auth/signup/", status_code=201)
def sign_up(email:EmailStr,password:str ,display_name:str , db: Session = Depends(get_db)):
    if get_user_by_email(db, email=email):
        raise HTTPException(status_code=400, detail="Email already registered")
    create_user(db, email,password,display_name)
    return {"message": "User created successfully"}

@app.post("/auth/login/", response_model=Dict[str, str])
def login(
    response: Response,
    login_data: LoginRequest,  # Expecting data in the request body
    db: Session = Depends(get_db)
):
    # Use login_data.email and login_data.password here
    user = authenticate_user(db, login_data.email, login_data.password)
    if not user:
        raise HTTPException(status_code=400, detail="Invalid credentials")

    access_token = create_access_token({"sub": user.user_id, "email": user.email})
    refresh_token = create_refresh_token({"sub": user.user_id})

    response.set_cookie(key="access_token", value=access_token, httponly=True, secure=False, samesite="lax", path="/")
    response.set_cookie(key="refresh_token", value=refresh_token, httponly=True, secure=False, samesite="lax", path="/")

    return {"message": "Login Success"}

# Token Endpoints
@app.post("/auth/refresh-token/", response_model=Dict[str, str])
def refresh_token(refresh_token: str):
    payload = verify_token(refresh_token)
    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(status_code=401, detail="Invalid refresh token")

    access_token = create_access_token({"sub": user_id})
    return {"access_token": access_token, "token_type": "bearer"}

# Google Endpoints
@app.get("/auth/google/login/")
async def login_with_google():
    return await google_login()

@app.get("/auth/google/callback/")
async def callback_from_google(request: Request, db: Session = Depends(get_db)):
    return await google_callback(request, db)

@app.get("/auth/google/set-cookies/")
async def set_cookies(response: Response):
    user = oauth_results.get('user')
    if not user or 'user_email' not in user:
        raise HTTPException(status_code=400, detail="User email not found in results")

    user_email = user['user_email']
    access_token = create_access_token({"sub": user_email})
    refresh_token = create_refresh_token({"sub": user_email})

    response.set_cookie(key="access_token", value=access_token, httponly=True, secure=False, samesite="lax", path="/")
    response.set_cookie(key="refresh_token", value=refresh_token, httponly=True, secure=False, samesite="lax", path="/")

    oauth_results.clear()
    logger.debug(f"Cookies set: access_token={access_token}, refresh_token={refresh_token}")

    return {"message": "Cookies set successfully"}

@app.get("/auth/google/sse/")
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


# Core Logic Endpoints
@app.post("/images/upload/")
async def upload_images(files: List,current_user:str=Depends(get_current_user)):
    return await receive_upload_images(files)

@app.get("/files/download/{filename}")
async def download_file(filename: str,current_user:str=Depends(get_current_user)):
    return download_file(filename)

@app.websocket("/landmark/results/")
async def landmark_results(websocket: WebSocket):
    await process_landmark_results(websocket)



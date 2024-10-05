import logging
import os
from typing import List
from dotenv import load_dotenv
from fastapi import (
    Depends,
    FastAPI,
    File,
    Request,
    UploadFile,
    APIRouter,
)
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.utils import get_openapi
from requests import Session

from api.request_user import get_current_user
from api.routes.auth_router import auth_router
from api.routes.google_router import google_router
from api.routes.user_router import user_router
from api.routes.websocket_router import websocket_router
from auth.mail.mail_config import CONF
from auth.token import check_token
from database.database import engine, get_db
import database.model as model
from api.image_processing import receive_upload_images, download_file

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Load environment variables
script_dir = os.path.dirname(os.path.abspath(__file__))
env_path = os.path.join(script_dir, '.env')
load_dotenv(dotenv_path=env_path)
logger.info("Loaded .env file")


# Initialize FastAPI app
app = FastAPI()

# CORS configuration
origins = ["http://localhost:1212","ergodetect://"]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Create all database tables
model.Base.metadata.create_all(bind=engine)

# Custom OpenAPI schema
def custom_openapi():
    if app.openapi_schema:
        return app.openapi_schema
    openapi_schema = get_openapi(
        title="WebSocket API",
        version="1.0.0",
        description="This is a simple WebSocket API",
        routes=app.routes,
    )
    # Add documentation for the WebSocket endpoint
    openapi_schema["paths"]["/landmark/results/"] = {
        "get": {
            "summary": "WebSocket connection",
            "description": "Connect to the WebSocket server. Send a message and receive a response.",
            "responses": {
                "101": {
                    "description": "Switching Protocols - The client is switching protocols as requested by the server.",
                }
            },
        }
    }
    app.openapi_schema = openapi_schema
    return app.openapi_schema

app.openapi = custom_openapi

# Include routers
app.include_router(auth_router, prefix='/auth', tags=["Authentication"])
app.include_router(user_router, prefix='/user', tags=["User"])
app.include_router(google_router, prefix='/auth/google', tags=["Google OAuth"])
app.include_router(websocket_router, prefix='/landmark', tags=["WebSocket"])

# Authentication router
auth_status_router = APIRouter()

@app.get("/")
async def root():
    return {"message": "Hello World"}


@auth_status_router.get("/status/")
async def auth_status(request: Request, db: Session = Depends(get_db)):
    # Retrieve tokens from cookies and headers
    access_token = request.cookies.get("access_token")
    refresh_token = request.cookies.get("refresh_token")
    device_mac = request.headers.get("Device-Identifier")

    if not device_mac:
        return {"status": "LoginRequired", "message": "Device identifier is missing"}

    user_id = None

    # Validate access token
    if access_token:
        access_result = check_token(access_token,"access")
        if access_result["status"] == "Authenticated":
            user_id = access_result["sub"]
            # Verify session in the database
            user_session = db.query(model.UserSession).filter(
                model.UserSession.user_id == user_id,
                model.UserSession.device_identifier == device_mac
            ).first()


            if user_session:
                return {"status": "Authenticated", "message": "Session valid", "user_id": user_id}
            else:
                return {"status": "LoginRequired", "message": "Device mismatch, login required"}
        elif access_result["status"] == "Expired" and refresh_token:
            # Access token expired, check refresh token
            refresh_result = check_token(refresh_token, "refresh")
            if refresh_result["status"] == "Authenticated":
                user_id = refresh_result["user_id"]
                return {
                    "status": "Refresh",
                    "message": "Access token expired, but refresh token is valid",
                    "user_id": user_id
                }

    # If no valid access token, check refresh token
    if refresh_token:
        refresh_result = check_token(refresh_token,"refresh")
        if refresh_result["status"] == "Authenticated":
            user_id = refresh_result["user_id"]
            user_session = db.query(model.UserSession).filter(
                model.UserSession.user_id == user_id,
                model.UserSession.device_identifier == device_mac
            ).first()

            if user_session:
                return {"status": "Refresh", "message": "No access token, but refresh token is valid", "user_id": user_id}
            else:
                return {"status": "LoginRequired", "message": "Device mismatch, login required"}

    # If no valid tokens or device mismatch, prompt login required
    return {"status": "LoginRequired", "message": "No valid tokens found, or device mismatch. Please log in again."}


app.include_router(auth_status_router, prefix='/auth', tags=["Authentication"])

# File operations router
file_router = APIRouter()

@file_router.post("/upload/")
async def upload_images(
    files: List[UploadFile] = File(...),
    user_id: str = Depends(get_current_user)
):
    # Process the uploaded files
    return await receive_upload_images(files)

@file_router.get("/download/{filename}")
async def download_files(
    filename: str,
    user_id: str = Depends(get_current_user)
):
    return await download_file(filename)

app.include_router(file_router, prefix='/files', tags=["Files"])





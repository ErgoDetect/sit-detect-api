import logging
import os
from typing import  List
from dotenv import dotenv_values
from fastapi.openapi.utils import get_openapi
from fastapi import  Depends, FastAPI, File, HTTPException,Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware

from api.request_user import get_current_user
from api.routes.auth_router import auth_router
from api.routes.google_router import google_router
from api.routes.user_router import user_router
from api.routes.websocket_router import websocket_router
from auth.token import  verify_token
from database.database import engine
import database.model as model
from api.image_processing import receive_upload_images, download_file
from dotenv_vault import load_dotenv

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

#load .env
script_dir = os.path.dirname(os.path.abspath(__file__))
logger.info(f"Script directory: {script_dir}")

env_path = os.path.join(script_dir, '.env')
logger.info(f".env file path: {env_path}")

load_dotenv(dotenv_path=env_path)
logger.info("Loaded .env file")

env_variables = dotenv_values(env_path)

for key in env_variables:
    logger.info(f"Loaded key: {key}")

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

# Create all tables
model.Base.metadata.create_all(bind=engine)

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

app.include_router(auth_router, prefix='/auth', tags=["Authentication"])
app.include_router(user_router, prefix='/user', tags=["User"])
app.include_router(google_router, prefix='/auth/google', tags=["Google OAuth"])
app.include_router(websocket_router, prefix='/landmark', tags=["WebSocket"])

@app.get("/auth/status/")
async def auth_status(request: Request):
    access_token = request.cookies.get("access_token")
    
    if not access_token:
        # Raise HTTP 401 Unauthorized if access_token is not found
        raise HTTPException(
            status_code=401,
            detail="No access token"
        )

    try:
        payload = verify_token(access_token)
        return {"is_login": True, "message": "Token is valid"}
    except Exception as e:
        # Raise HTTP 401 Unauthorized if token verification fails
        raise HTTPException(
            status_code=401,
            detail=f"Invalid token: {str(e)}"
        )

@app.post("/images/upload/")
async def upload_images(
    files: List[UploadFile] = File(...), 
    user_id: str = Depends(get_current_user)
):
    # Assuming receive_upload_images is a function that processes the uploaded files
    return await receive_upload_images(files)

@app.get("/files/download/{filename}")
async def download_files(filename: str,user_id: str = Depends(get_current_user)):
    return download_file(filename)




    

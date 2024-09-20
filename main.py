import asyncio
from datetime import  datetime,timedelta,timezone
import logging
import os
import json
from typing import Dict, List

from dotenv import dotenv_values
from fastapi import Body, FastAPI, Depends, HTTPException, Request, Response, WebSocket , WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from fastapi.openapi.utils import get_openapi
from pydantic import EmailStr
from sqlalchemy.orm import Session

from api.request_user import get_current_user
from auth.auth import authenticate_user
from auth.token import ACCESS_TOKEN_EXPIRE_MINUTES, REFRESH_TOKEN_EXPIRE_DAYS, UTC_PLUS_7,create_access_token, create_refresh_token, get_token_expiration_times,  verify_token
from database.database import engine, SessionLocal
import database.model as model
from database.crud import create_user, get_user_by_email, delete_user
from api.image_processing import receive_upload_images, download_file
from api.websocket_received import process_landmark_results
from api.google_oauth import google_login, google_callback
from api.storage import oauth_results
from database.schemas.User import LoginRequest
from dotenv_vault import load_dotenv
from api.procressData import processData
from datetime import datetime

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
    login_data: LoginRequest,
    db: Session = Depends(get_db)
):
    # Authenticate the user
    user = authenticate_user(db, login_data.email, login_data.password)
    if not user:
        raise HTTPException(status_code=400, detail="Invalid credentials")

    # Create tokens
    access_token = create_access_token({"sub": user.user_id, "email": user.email})
    refresh_token = create_refresh_token({"sub": user.user_id})

    # Extract expiration times from the generated JWTs
    access_token_exp_utc, _ = get_token_expiration_times(access_token)
    refresh_token_exp_utc, _ = get_token_expiration_times(refresh_token)

    # Set cookies with the extracted expiration dates
    response.set_cookie(
        key="access_token",
        value=access_token,
        httponly=True,
        secure=False,  # Set to True in production for HTTPS
        samesite="lax",
        path="/",
        expires=access_token_exp_utc,  # Use expiration time from the token
    )
    response.set_cookie(
        key="refresh_token",
        value=refresh_token,
        httponly=True,
        secure=False,  # Set to True in production for HTTPS
        samesite="lax",
        path="/",
        expires=refresh_token_exp_utc,  # Use expiration time from the token
    )

    return {"message": "Login Success"}

# Token Endpoints
from fastapi import Response, Request, Depends, HTTPException
from typing import Dict
from datetime import datetime, timezone

@app.post("/auth/refresh-token/", response_model=Dict[str, str])
def refresh_token(response: Response, request: Request):
    # Extract the refresh token from the cookies
    refresh_token = request.cookies.get("refresh_token")
    if not refresh_token:
        raise HTTPException(status_code=401, detail="Refresh token not provided")

    # Verify the refresh token
    payload = verify_token(refresh_token)
    user_id = payload.get("sub")
    email = payload.get("email")
    if not user_id:
        raise HTTPException(status_code=401, detail="Invalid refresh token")

    # Create a new access token
    access_token = create_access_token({"sub": user_id, "email": email})

    # Get the expiration time for the current refresh token
    refresh_token_expires_utc, _ = get_token_expiration_times(refresh_token)
    current_time = datetime.now(timezone.utc)
    time_until_expiration = refresh_token_expires_utc - current_time

    # If refresh token will expire within 15 days, create a new one
    if time_until_expiration.days <= 15:
        refresh_token = create_refresh_token({"sub": user_id})
        refresh_token_expires_utc, _ = get_token_expiration_times(refresh_token)

        # Set the new refresh token in cookies
        response.set_cookie(
            key="refresh_token",
            value=refresh_token,
            httponly=True,
            secure=False,  # Use secure=True in production with HTTPS
            samesite="lax",
            path="/",
            expires=refresh_token_expires_utc
        )

    # Set the new access token in cookies
    access_token_expires_utc, _ = get_token_expiration_times(access_token)
    response.set_cookie(
        key="access_token",
        value=access_token,
        httponly=True,
        secure=False,  # Use secure=True in production with HTTPS
        samesite="lax",
        path="/",
        expires=access_token_expires_utc
    )

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

    access_token_exp_utc, _ = get_token_expiration_times(access_token)
    refresh_token_exp_utc, _ = get_token_expiration_times(refresh_token)
   
    # Set cookies with expiration dates
    response.set_cookie(
        key="access_token", 
        value=access_token, 
        httponly=True, 
        secure=False, 
        samesite="lax", 
        path="/", 
        expires=access_token_exp_utc,
        
    )
    response.set_cookie(
        key="refresh_token", 
        value=refresh_token, 
        httponly=True, 
        secure=False, 
        samesite="lax", 
        path="/", 
        expires=refresh_token_exp_utc
    )
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
async def upload_images(files: List):
    return await receive_upload_images(files)

@app.get("/files/download/{filename}")
async def download_file(filename: str,):
    return download_file(filename)


class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        self.active_connections.remove(websocket)

    async def send_message(self, message: str, websocket: WebSocket):
        await websocket.send_text(message)

# Instance of the connection manager
manager = ConnectionManager()

@app.websocket("/landmark/results/")
async def landmark_results(websocket: WebSocket):
    await manager.connect(websocket)

    frame_per_second = 1

    response_counter = 0
    saved_values = []
    correct_values = {}
    current_values = {}

    ear_threshoild_low = 0.2
    ear_threshoild_high = 0.4
    ear_below_threshold = False
    blink_detected = False

    lastest_nearest_distance = 0
    lastest_nearest_distance_left = 0
    lastest_nearest_distance_right = 0

    blink_stack = 0
    siting_stack = 0
    distance_stack = 0
    thoracic_stack = 0

    # result = [blink_stack,siting_stack,distance_stack,thoracic_stack]
    # result คือตัวผลลัพธ์ที่จะส่ง
    result = [False,False,False,False]



    # goback = "\033[F" * 2
    try:
        while True:
            # Receive data from the client
            message = await websocket.receive_text()
            object_data = json.loads(message)
            processed_data = processData(object_data['data'])

            # print(object_data['data'],"\n_____________________________________________")
            # Process the first 5 messages
            
            if response_counter < 5:
                # saved_values.append(processed_data)
                correct_values= {"shoulderPosition":processed_data.get_shoulder_position()['y'],
                                 "diameterRight":processed_data.get_diameter_right(),
                                 "diameterLeft":processed_data.get_diameter_left()}
                response_counter += 1
                # print(f"Response {response_counter} saved: {processed_data}", websocket)

            # After 5 messages are saved, continue processing if needed
            if response_counter == 5:
                # print(f"First 5 values saved: {saved_values}", websocket)
                response_counter += 1

            current_values= {"shoulderPosition":processed_data.get_shoulder_position()['y'],
                            "diameterRight":processed_data.get_diameter_right(),
                            "diameterLeft":processed_data.get_diameter_left(),
                            "eyeAspectRatioRight":processed_data.get_blink_right(),
                            "eyeAspectRatioLeft":processed_data.get_blink_left()}
            
            if current_values["shoulderPosition"] == None:
                thoracic_stack = 0
            elif correct_values["shoulderPosition"]*0.90>=current_values["shoulderPosition"]:
                thoracic_stack += 1
            else : thoracic_stack = 0

            if object_data['data']["faceDetect"] == False:
                blink_stack = 0
                siting_stack = 0
                distance_stack = 0
            else :
                siting_stack += 1
                if current_values["diameterRight"] != None or current_values["diameterLeft"] != None:
                    if current_values["diameterRight"] != None:
                        lastest_nearest_distance_right = current_values["diameterRight"]
                    if current_values["diameterLeft"] != None:
                        lastest_nearest_distance_left = current_values["diameterLeft"]
                    if lastest_nearest_distance_right > lastest_nearest_distance_left:
                        lastest_nearest_distance = lastest_nearest_distance_right
                    else : lastest_nearest_distance = lastest_nearest_distance_left
                if correct_values["diameterRight"] > correct_values["diameterLeft"] :
                    if correct_values["diameterRight"] *0.90<= lastest_nearest_distance:
                        distance_stack +=1
                    else : distance_stack = 0
                else :
                    if correct_values["diameterLeft"]*0.90<= lastest_nearest_distance:
                        distance_stack +=1
                    else : distance_stack = 0
                if current_values["eyeAspectRatioLeft"] <= ear_threshoild_low or current_values["eyeAspectRatioRight"] <= ear_threshoild_low:
                    ear_below_threshold = True
                    blink_stack += 1 
                    
                elif ear_below_threshold and (current_values["eyeAspectRatioLeft"]  >= ear_threshoild_high or current_values["eyeAspectRatioRight"] >= ear_threshoild_high):
                    if not blink_detected:
                        blink_stack = 0
                        blink_detected = True
                    ear_below_threshold = False
                else:
                    blink_detected = False
                    blink_stack += 1 
                

            if blink_stack >= 5*frame_per_second:
                result[0] = True
            else : result[0] = False
            if siting_stack >= 2700*frame_per_second:
                result[1] = True
            else : result[1] = False
            if distance_stack >= 30*frame_per_second:
                result[2] = True
            else : result[2] = False
            if thoracic_stack >= 2*frame_per_second:
                result[3] = True 
            else : result[3] = False   
            # print(f"[{blink_stack}], [{siting_stack}], [{distance_stack}], [{thoracic_stack}]")
            # print(result)
            # print(datetime.fromtimestamp(object_data["timestamp"] / 1000))
            # print(current_values["shoulderPosition"])
        
            

    except WebSocketDisconnect:
        manager.disconnect(websocket)
        print(f"Connection closed. Saved values: {saved_values}")


    

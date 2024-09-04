import json
from fastapi import FastAPI, WebSocket, WebSocketDisconnect,      UploadFile, HTTPException
from fastapi.websockets import WebSocketState
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
import numpy as np
import cv2
import logging
import platform
import os
import aiofiles
import shutil
from pathlib import Path
from datetime import datetime
from api.calibration import calibrate_camera
from api.procressData import processData
import database.model as model
from database.config import engine

app = FastAPI()

origins = ["http://localhost:1212","app://."]
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

# Platform-specific settings
if platform.system() == "Darwin":
    os.environ['KMP_DUPLICATE_LIB_OK'] = 'True'
    
model.Base.metadata.create_all(bind=engine)

# Directory to save images and results
IMAGE_SAVE_DIR = Path("images")
RESULT_DIR = Path('calibrate_result')

# Generate a sequential filename
def generate_unique_filename(base_name: str) -> str:
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return f"{base_name}_{timestamp}.png"

async def save_image(file: UploadFile, index: int) -> Path:
    try:
        # Read image data from file
        image_data = await file.read()
        unique_filename = generate_unique_filename(f"calibration_{index}")
        file_path = IMAGE_SAVE_DIR / unique_filename

        # Ensure the directory exists
        IMAGE_SAVE_DIR.mkdir(parents=True, exist_ok=True)

        # Save image asynchronously
        async with aiofiles.open(file_path, 'wb') as out_file:
            await out_file.write(image_data)

        # Process the image with OpenCV
        np_arr = np.frombuffer(image_data, np.uint8)
        img = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)
        if img is None:
            raise ValueError("Unable to decode the image")

        logger.info(f"Received image with shape: {img.shape}")
        return file_path

    except Exception as e:
        logger.error(f"Failed to save and process image: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to process image: {e}")

def calibrate_and_cleanup(image_paths):
    calibration_file = None
    mean_error = None

    try:
        # Perform camera calibration
        calibration_file, mean_error = calibrate_camera(image_paths)

        if calibration_file is not None:
            calibration_file_path = RESULT_DIR / calibration_file

            # Load the existing calibration data
            try:
                with calibration_file_path.open("r") as f:
                    calibration_data = json.load(f)
            except FileNotFoundError:
                logger.error(f"Calibration file {calibration_file_path} not found.")
                return None, None

            # Add the mean error to the calibration data
            calibration_data["mean_error"] = mean_error

            # Save the updated calibration data
            try:
                with calibration_file_path.open("w") as f:
                    json.dump(calibration_data, f)
            except IOError as e:
                logger.error(f"Failed to write to {calibration_file_path}: {e}")
                return None, None

    except Exception as e:
        logger.error(f"Error during calibration: {e}")
    
    finally:
        # Always clean up the directories, even if calibration fails
        directories_to_delete = [IMAGE_SAVE_DIR, RESULT_DIR]
        for directory in directories_to_delete:
            if directory.exists() and directory.is_dir():
                try:
                    shutil.rmtree(directory)
                    logger.info(f"Deleted the directory: {directory}")
                except Exception as e:
                    logger.error(f"Failed to delete directory {directory}: {e}")
            else:
                logger.warning(f"Directory {directory} does not exist or is not a directory, nothing to delete.")

    return calibration_file, mean_error

@app.post("/upload-images")
async def upload_images(files: list[UploadFile]):
    try:
        file_paths = []
        for index, file in enumerate(files):
            file_path = await save_image(file, index)
            file_paths.append(file_path)
        return {"message": "Images saved successfully", "file_paths": [str(path) for path in file_paths]}
    except HTTPException as e:
        raise e
    except Exception as e:
        logger.error(f"Error in upload endpoint: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

@app.get("/download/{filename}")
async def download_file(filename: str):
    file_path = RESULT_DIR / filename
    if file_path.exists() and file_path.is_file():
        return FileResponse(path=file_path, filename=filename)
    else:
        raise HTTPException(status_code=404, detail="File not found")

@app.websocket("/landmark-results")
async def receive_video(websocket: WebSocket):
    await websocket.accept()
    logger.info("WebSocket connection accepted")

    try:
        while websocket.client_state == WebSocketState.CONNECTED:
            try:
                message = await websocket.receive_text()
                object_data = json.loads(message)
                processed_data = processData(object_data['data'])
                result = {
                    "shoulderPosition": processed_data.get_shoulder_position(),
                    "blinkRight": processed_data.get_blink_right(),
                    "blinkLeft": processed_data.get_blink_left(),
                }
                logger.info(f"Shoulder Position: {result['shoulderPosition']}")
                logger.info(f"Blink Right: {result['blinkRight']}")
                logger.info(f"Blink Left: {result['blinkLeft']}")

                await websocket.send_json(result)

            except WebSocketDisconnect:
                logger.info("WebSocket disconnected")
                break

            except Exception as e:
                logger.error(f"Error during WebSocket communication: {e}")
                await websocket.send_json({"error": str(e)})
                await websocket.close()
                break

    except Exception as e:
        logger.error(f"Error in WebSocket connection: {e}")
        if websocket.client_state == WebSocketState.CONNECTED:
            await websocket.close()

import aiofiles
from fastapi import HTTPException, UploadFile
from pathlib import Path
import cv2
from fastapi.responses import FileResponse
import numpy as np
import logging
from datetime import datetime

# Directory paths
IMAGE_SAVE_DIR = Path("images")
RESULT_DIR = Path("calibrate_result")

logger = logging.getLogger(__name__)


# Function to generate unique filenames
def generate_unique_filename(base_name: str) -> str:
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return f"{base_name}_{timestamp}.png"


# Save image asynchronously
async def save_image(file: UploadFile, index: int) -> Path:
    try:
        image_data = await file.read()
        unique_filename = generate_unique_filename(f"calibration_{index}")
        file_path = IMAGE_SAVE_DIR / unique_filename
        IMAGE_SAVE_DIR.mkdir(parents=True, exist_ok=True)
        async with aiofiles.open(file_path, "wb") as out_file:
            await out_file.write(image_data)
        np_arr = np.frombuffer(image_data, np.uint8)
        img = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)
        if img is None:
            raise ValueError("Unable to decode the image")
        logger.info(f"Received image with shape: {img.shape}")
        return file_path
    except Exception as e:
        logger.error(f"Failed to save and process image: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to process image: {e}")


# Upload images
async def receive_upload_images(files: list[UploadFile]):
    try:
        file_paths = [await save_image(file, index) for index, file in enumerate(files)]
        return {
            "message": "Images saved successfully",
            "file_paths": [str(path) for path in file_paths],
        }
    except Exception as e:
        logger.error(f"Error in upload endpoint: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


# Download file
def download_file(filename: str):
    file_path = RESULT_DIR / filename  # Construct the file path
    if (
        file_path.exists() and file_path.is_file()
    ):  # Check if the file exists and is a file
        return FileResponse(
            path=file_path, filename=filename
        )  # Serve the file as a response
    else:
        raise HTTPException(
            status_code=404, detail="File not found"
        )  # Raise 404 error if the file is not found

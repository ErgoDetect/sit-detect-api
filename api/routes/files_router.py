from datetime import datetime
import logging
from typing import List
import uuid
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from requests import Session

from api.image_processing import download_file, receive_upload_images
from api.procressData import processData
from api.request_user import get_current_user
from database.database import get_db

from api.detection import detection

# from api.detection import Detection
from database.model import SittingSession
from sqlalchemy.exc import SQLAlchemyError, IntegrityError

from database.schemas.User import VideoUploadRequest


logger = logging.getLogger(__name__)

files_router = APIRouter()


@files_router.post("/upload/video", status_code=status.HTTP_200_OK)
async def video_process_result_upload(
    request: VideoUploadRequest,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    # Validate file data presence
    object_data = request.files
    if not object_data:
        raise HTTPException(status_code=400, detail="No file data provided")

    # Initialize and extract variables
    detector = detection(frame_per_second=15)
    sitting_session_id = uuid.uuid4()
    user_id = current_user["user_id"]
    date = datetime.now()

    # Process each frame entry in object_data
    for i, entry in enumerate(object_data):
        processed_data = processData(entry)
        current_values = {
            "shoulderPosition": processed_data.get_shoulder_position(),
            "diameterRight": processed_data.get_diameter_right(),
            "diameterLeft": processed_data.get_diameter_left(),
            "eyeAspectRatioRight": processed_data.get_blink_right(),
            "eyeAspectRatioLeft": processed_data.get_blink_left(),
        }

        # Set baseline values if within first 15 frames; otherwise, detect issues
        if i < 15:
            detector.set_correct_value(current_values)
        else:
            detector.detect(current_values, entry.get("faceDetect"))

    # Retrieve detection results
    timeline_result = detector.get_timeline_result()

    # Create SittingSession record
    db_sitting_session = SittingSession(
        sitting_session_id=sitting_session_id,
        user_id=user_id,
        blink=timeline_result["blink"],
        sitting=timeline_result["sitting"],
        distance=timeline_result["distance"],
        thoracic=timeline_result["thoracic"],
        date=date,
        file_name=request.video_name,
        thumbnail=request.thumbnail,
        session_type="video",
    )

    # Database transaction
    try:
        db.add(db_sitting_session)
        db.commit()
        db.refresh(db_sitting_session)
        return {"message": "Process result received successfully."}
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=400, detail="A session with this ID already exists."
        )
    except SQLAlchemyError:
        db.rollback()
        raise HTTPException(
            status_code=500, detail="Database error while creating sitting session."
        )


@files_router.post("/upload/images")
async def upload_images(
    files: List[UploadFile] = File(...), user_id: str = Depends(get_current_user)
):
    # Process the uploaded files
    return await receive_upload_images(files)


@files_router.get("/download/{filename}")
async def download_files(filename: str, user_id: str = Depends(get_current_user)):
    return await download_file(filename)

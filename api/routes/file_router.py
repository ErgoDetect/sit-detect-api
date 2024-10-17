from datetime import datetime
import logging
from typing import Any, Dict, List
import uuid
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from requests import Session

from api.image_processing import download_file, receive_upload_images
from api.procressData import processData
from api.request_user import get_current_user
from database.database import get_db
from api.detection import detection
from database.model import SittingSession
from sqlalchemy.exc import SQLAlchemyError, IntegrityError

logger = logging.getLogger(__name__)

file_router = APIRouter()


@file_router.post("/upload/video/", status_code=status.HTTP_200_OK)
async def video_process_result_upload(
    file: Dict[
        str, List[Dict[str, Any]]
    ],  # Expecting a dict with a "file" key holding the list
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    # Access the file list
    object_data = file[
        "file"
    ]  # 'file' is a dict, so we access the list via file["file"]

    # Instantiate the detector and create other needed variables
    detector = detection()
    sitting_session_id = uuid.uuid4()
    user_id = current_user["user_id"]
    date = datetime.now()

    # Process the incoming data
    for i in range(0, len(object_data)):
        processed_data = processData(
            object_data[i]
        )  # Assuming each dict has the necessary data
        current_values = {
            "shoulderPosition": processed_data.get_shoulder_position(),
            "diameterRight": processed_data.get_diameter_right(),
            "diameterLeft": processed_data.get_diameter_left(),
            "eyeAspectRatioRight": processed_data.get_blink_right(),
            "eyeAspectRatioLeft": processed_data.get_blink_left(),
        }
        if i <= 5:
            detector.set_correct_value(current_values)
        else:
            detector.detect(current_values, object_data[i]["faceDetect"])

    # Create and commit a new SittingSession
    db_sitting_session = SittingSession(
        sitting_session_id=sitting_session_id,
        user_id=user_id,
        sitting_session=detector.get_timeline_result(),
        date=date,
    )

    try:
        db.add(db_sitting_session)
        db.commit()
        db.refresh(db_sitting_session)
        return {"message": "Process result received successfully."}
    except IntegrityError as e:
        db.rollback()
        raise HTTPException(
            status_code=400, detail="Sitting session id already exists."
        )
    except SQLAlchemyError as e:
        db.rollback()
        raise HTTPException(
            status_code=500, detail="Error creating sitting session in database."
        )


@file_router.post("/upload/")
async def upload_images(
    files: List[UploadFile] = File(...), user_id: str = Depends(get_current_user)
):
    # Process the uploaded files
    return await receive_upload_images(files)


@file_router.get("/download/{filename}")
async def download_files(filename: str, user_id: str = Depends(get_current_user)):
    return await download_file(filename)

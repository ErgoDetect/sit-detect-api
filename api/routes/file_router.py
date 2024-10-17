from datetime import datetime
import json
import logging
import uuid
from fastapi import (APIRouter, Depends, HTTPException,status)
from requests import Session

from api.procressData import processData
from api.request_user import get_current_user
from auth.token import get_sub_from_token
from database.database import get_db
from api.detection import detection
from database.model import SittingSession
from sqlalchemy.exc import SQLAlchemyError, IntegrityError

logger = logging.getLogger(__name__)

file_router = APIRouter()
@file_router.post("/upload/video/", status_code=status.HTTP_201_CREATED)
async def file_upload(file,db: Session = Depends(get_db), current_user: dict = Depends(get_current_user)):
    object_data = json.loads(file)
    
    detector = detection()
    sitting_session_id = uuid.uuid4()
    user_id = get_sub_from_token(current_user)
    date = datetime.now()

   
    
    for i in range(0,len(object_data)):
        processed_data = processData(object_data[i]['data'])
        current_values = {
                "shoulderPosition": processed_data.get_shoulder_position(),
                "diameterRight": processed_data.get_diameter_right(),
                "diameterLeft": processed_data.get_diameter_left(),
                "eyeAspectRatioRight": processed_data.get_blink_right(),
                "eyeAspectRatioLeft": processed_data.get_blink_left()
        }
        if i <= 5:
            detector.set_correct_value(current_values)
        else:
            detector.detect(current_values,object_data['data']["faceDetect"])
        
    db_sitting_session = SittingSession(
        sitting_session_id = sitting_session_id,
        user_id = user_id,
        sitting_session = detector.get_timeline_result(),
        date = date
    )
    try:
        db.add(db_sitting_session)
        db.commit()
        db.refresh(db_sitting_session)
    except IntegrityError as e:
        db.rollback()
        logger.error(f"Integrity error: {e}")
        raise HTTPException(status_code=400, detail="Sitting session id already exists.")
    except SQLAlchemyError as e:
        db.rollback()
        logger.error(f"SQLAlchemy error during user creation: {e}")
        raise HTTPException(status_code=500, detail="Error creating sitting session in database.")
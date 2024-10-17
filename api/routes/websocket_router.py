from datetime import datetime
import json
import logging
import uuid 
from fastapi import APIRouter, Depends, HTTPException, Request, WebSocket, WebSocketDisconnect
from fastapi.websockets import WebSocketState
from requests import Session
from api.procressData import processData 
from auth.token import get_sub_from_token
from api.detection import detection
from database.database import get_db
from database.model import SittingSession
from sqlalchemy.exc import SQLAlchemyError, IntegrityError

logger = logging.getLogger(__name__)

websocket_router = APIRouter()

uuid_mudule = uuid

@websocket_router.websocket("/results/")
async def landmark_results(websocket: WebSocket, db: Session = Depends(get_db)):
    await websocket.accept()
    acc_token = websocket.cookies.get("access_token")
    # logger.info(f"WebSocket connection accepted for user: {get_sub_from_token(acc_token)}")
    logger.info("WebSocket connection accepted")

    response_counter = 0

    
    
    try:
        while True:
            # Receive and process data from the client
            message = await websocket.receive_text()
            object_data = json.loads(message)
            processed_data = processData(object_data['data'])
            response_counter += 1
            # Extract current values

            if (response_counter == 1 ):
                detector = detection()
                sitting_session_id = uuid.uuid4()
                user_id = get_sub_from_token(acc_token)
                sitting_session = {}
                date = datetime.now()

                db_sitting_session = SittingSession(
                    sitting_session_id = sitting_session_id,
                    user_id = user_id,
                    sitting_session = sitting_session,
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
                
                sit_session = db.query(SittingSession).filter(SittingSession.sitting_session_id == sitting_session_id).first()

            current_values = {
                "shoulderPosition": processed_data.get_shoulder_position(),
                "diameterRight": processed_data.get_diameter_right(),
                "diameterLeft": processed_data.get_diameter_left(),
                "eyeAspectRatioRight": processed_data.get_blink_right(),
                "eyeAspectRatioLeft": processed_data.get_blink_left()
            }

            # Process the first 5 messages to establish baseline values
            if response_counter <= 5:
                detector.set_correct_value(current_values)
            else:
                detector.detect(current_values,object_data['data']["faceDetect"])
            # Send the result back to the client
            await websocket.send_json(detector.get_alert())

            sit_session.sitting_session = detector.get_timeline_result()
            db.commit()
            # print(detector.get_timeline_result())
            print("blink:",detector.blink_stack)
            print("sitting:",detector.sitting_stack)
            print("distance:",detector.distance_stack)
            print("thoracic:",detector.thoracic_stack)

           

    except WebSocketDisconnect:
        logger.info("WebSocket disconnected")
    except Exception as e:
        logger.error(f"Error in WebSocket connection: {e}")
        if websocket.client_state == WebSocketState.CONNECTED:
            await websocket.close()

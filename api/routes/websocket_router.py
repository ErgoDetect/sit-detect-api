from datetime import datetime
import json
import logging
import uuid
from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect
from requests import Session
from api.procressData import processData
from auth.token import get_sub_from_token
from api.detection import detection

# from api.detection import Detection
from database.database import get_db
from database.model import SittingSession
from sqlalchemy.exc import SQLAlchemyError, IntegrityError

logger = logging.getLogger(__name__)

websocket_router = APIRouter()


@websocket_router.websocket("/results")
async def landmark_results(websocket: WebSocket, db: Session = Depends(get_db)):
    await websocket.accept()
    acc_token = websocket.cookies.get("access_token")
    logger.info("WebSocket connection accepted")

    response_counter = 0
    detector = None
    sitting_session = None

    try:
        while True:
            # Receive and process data from the client
            message = await websocket.receive_text()
            object_data = json.loads(message)
            processed_data = processData(object_data["data"])
            response_counter += 1

            # On first message, initialize session and detector
            if response_counter == 1:
                try:
                    detector, sitting_session = initialize_session(acc_token, db)
                except HTTPException as e:
                    await websocket.close()
                    raise e

            # Extract current values
            current_values = {
                "shoulderPosition": processed_data.get_shoulder_position(),
                "diameterRight": processed_data.get_diameter_right(),
                "diameterLeft": processed_data.get_diameter_left(),
                "eyeAspectRatioRight": processed_data.get_blink_right(),
                "eyeAspectRatioLeft": processed_data.get_blink_left(),
            }

            # Process the first 5 messages to establish baseline values
            if response_counter <= 5:
                detector.set_correct_value(current_values)
            else:
                detector.detect(current_values, object_data["data"]["faceDetect"])

            # Send the result back to the client
            await websocket.send_json(detector.get_alert())

            # Update session in database after processing
            sitting_session.sitting_session = detector.get_timeline_result()
            db.commit()

            # Logging useful details
            logger.info(f"Blink Stack: {detector.blink_stack}")
            logger.info(f"Sitting Stack: {detector.sitting_stack}")
            logger.info(f"Distance Stack: {detector.distance_stack}")
            logger.info(f"Thoracic Stack: {detector.thoracic_stack}")

    except WebSocketDisconnect:
        logger.info("WebSocket disconnected")
    except Exception as e:
        logger.error(f"Error in WebSocket connection: {e}")
        if websocket.client_state == WebSocketState.CONNECTED:
            await websocket.close()


def initialize_session(acc_token, db):
    """Initialize the detection object and create a new sitting session."""
    #  detector = Detection()
    detector = detection()
    sitting_session_id = uuid.uuid4()
    user_id = get_sub_from_token(acc_token)
    date = datetime.now()

    db_sitting_session = SittingSession(
        sitting_session_id=sitting_session_id,
        user_id=user_id,
        sitting_session={},
        date=date,
    )

    try:
        # Add new sitting session to the database
        db.add(db_sitting_session)
        db.commit()
        db.refresh(db_sitting_session)
        return detector, db_sitting_session

    except IntegrityError as e:
        db.rollback()
        logger.error(f"Integrity error: {e}")
        raise HTTPException(
            status_code=400, detail="Sitting session ID already exists."
        )
    except SQLAlchemyError as e:
        db.rollback()
        logger.error(f"SQLAlchemy error during session creation: {e}")
        raise HTTPException(
            status_code=500, detail="Error creating sitting session in database."
        )

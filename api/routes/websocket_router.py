from datetime import datetime
import json
import logging
import uuid
from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect
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


@websocket_router.websocket("/results")
async def landmark_results(
    websocket: WebSocket, db: Session = Depends(get_db), stream: bool = False
):
    await websocket.accept()
    acc_token = websocket.cookies.get("access_token")
    logger.info("WebSocket connection accepted")

    # Initialize variables outside the loop
    detector, sitting_session = None, None
    response_counter = 0

    if stream:
        detector = detection(frame_per_second=15)

    try:
        while True:
            message = await websocket.receive_text()
            object_data = json.loads(message)
            processed_data = processData(object_data["data"])
            current_values = extract_current_values(processed_data)
            response_counter += 1

            # Initialize session and detector if not already done
            if response_counter == 1 and not sitting_session:
                sitting_session = initialize_session(acc_token, db)

            # Set baseline values for the first 5 frames
            (
                detector.set_correct_value(current_values)
                if response_counter <= 5
                else detector.detect(current_values, object_data["data"]["faceDetect"])
            )

            # Prepare and send alert only if necessary
            if send_alert := prepare_alert(detector):
                await websocket.send_json(send_alert)

            # Periodically update session data in the database (e.g., every 5 messages)
            if response_counter % 5 == 0:
                update_sitting_session(detector, sitting_session, db)
                logger.info(f"Session updated at message {response_counter}")

    except WebSocketDisconnect:
        logger.info("WebSocket disconnected")
    except Exception as e:
        logger.error(f"Error in WebSocket connection: {e}")
        if websocket.client_state == WebSocketState.CONNECTED:
            await websocket.close()


def initialize_session(acc_token, db):
    """Initialize the detection object and create a new sitting session."""
    try:
        sitting_session_id = uuid.uuid4()
        user_id = get_sub_from_token(acc_token)
        date = datetime.now()

        db_sitting_session = SittingSession(
            sitting_session_id=sitting_session_id,
            user_id=user_id,
            blink=[],
            sitting=[],
            distance=[],
            thoracic=[],
            date=date,
        )

        db.add(db_sitting_session)
        db.commit()
        db.refresh(db_sitting_session)
        return db_sitting_session

    except (IntegrityError, SQLAlchemyError) as e:
        db.rollback()
        error_type = (
            "Integrity error" if isinstance(e, IntegrityError) else "SQLAlchemy error"
        )
        logger.error(f"{error_type}: {e}")
        raise HTTPException(
            status_code=400 if isinstance(e, IntegrityError) else 500,
            detail=f"Error creating session: {e}",
        )


def extract_current_values(processed_data):
    """Extract the necessary current values from processed data."""
    return {
        "shoulderPosition": processed_data.get_shoulder_position(),
        "diameterRight": processed_data.get_diameter_right(),
        "diameterLeft": processed_data.get_diameter_left(),
        "eyeAspectRatioRight": processed_data.get_blink_right(),
        "eyeAspectRatioLeft": processed_data.get_blink_left(),
    }


def prepare_alert(detector):
    """Prepare the alert dictionary based on the detector's results."""
    alert = detector.get_alert()
    return {key: True for key in alert if alert[key]}


def update_sitting_session(detector, sitting_session, db):
    """Update the sitting session in the database with detector timeline results."""
    try:
        timeline_result = detector.get_timeline_result()
        sitting_session.blink = timeline_result["blink"]
        sitting_session.sitting = timeline_result["sitting"]
        sitting_session.distance = timeline_result["distance"]
        sitting_session.thoracic = timeline_result["thoracic"]
        db.commit()

    except SQLAlchemyError as e:
        db.rollback()
        logger.error(f"Error updating sitting session: {e}")

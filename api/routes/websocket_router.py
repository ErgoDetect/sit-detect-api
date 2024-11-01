from datetime import datetime, timedelta
import time
import json
import logging
import uuid
from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    WebSocket,
    WebSocketDisconnect,
)
from fastapi.websockets import WebSocketState
from requests import Session
from api.procressData import processData
from api.request_user import get_current_user
from auth.token import LOCAL_TZ, get_current_time, get_sub_from_token
from api.detection import detection
from database.database import get_db
from database.model import SittingSession
from sqlalchemy.exc import SQLAlchemyError, IntegrityError

from database.schemas.User import VideoNameRequest

logger = logging.getLogger(__name__)

websocket_router = APIRouter()

# Define alert types and their cooldown and threshold times
ALERT_TYPES = ["blink", "sitting", "distance", "thoracic"]

cooldown_periods = {
    "blink": timedelta(minutes=2),
    "sitting": timedelta(minutes=30),
    "distance": timedelta(minutes=10),
    "thoracic": timedelta(minutes=10),
}

alert_thresholds = {
    "blink": timedelta(seconds=10),
    "sitting": timedelta(minutes=2),
    "distance": timedelta(minutes=1),
    "thoracic": timedelta(minutes=1),
}


# Define a Pydantic model for input validation


@websocket_router.post("/video_name")
async def receive_video_name(
    request: VideoNameRequest,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    try:
        # Get the video name from the request body
        video_name = request.video_name
        thumbnail = request.thumbnail

        # Get the user ID from the current user information
        user_id = current_user["user_id"]

        # Find the most recent sitting session for the user
        sitting_session = (
            db.query(SittingSession)
            .filter(SittingSession.user_id == user_id)
            .order_by(SittingSession.date.desc())
            .first()
        )
        if not sitting_session:
            raise HTTPException(status_code=404, detail="Sitting session not found")

        # Update video session in the database
        update_video_session(video_name, thumbnail, sitting_session, db)
        return {"message": "Video session updated successfully"}

    except Exception as e:
        logger.error(f"Error updating video session: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@websocket_router.websocket("/results")
async def landmark_results(
    websocket: WebSocket,
    db: Session = Depends(get_db),
    stream: bool = False,
    focal_length_enabled: bool = False,
):
    await websocket.accept()
    acc_token = websocket.cookies.get("access_token")
    logger.info("WebSocket connection accepted")

    # Initialize variables outside the loop
    detector = (
        detection(frame_per_second=15, focal_length=focal_length_value)
        if stream
        else None
    )
    sitting_session = None
    sitting_session_id = None
    response_counter = 0
    last_alert_time = {alert_type: None for alert_type in ALERT_TYPES}
    focal_length_values = None
    set_focal_length = False

    if focal_length_enabled and not set_focal_length and focal_length_values is None:
        init_message = await websocket.receive_text()
        init_data = json.loads(init_message)
        focal_length_data = init_data.get("focal_length")
        if focal_length_data:
            set_focal_length = True
            focal_length_values = focal_length_data

    try:
        logger.info(focal_length_values)
        while stream:
            try:
                # Receive and process streaming messages
                message = await websocket.receive_text()
                message_data = json.loads(message)

                # Check if it's a streaming data message
                if "data" in message_data:
                    object_data = message_data["data"]
                    processed_data = processData(object_data)
                    current_values = extract_current_values(processed_data)

                    response_counter += 1

                    # Initialize session and detector if not already done
                    if response_counter == 1 and not sitting_session:
                        sitting_session, sitting_session_id = initialize_session(
                            acc_token, db
                        )

                    # Set baseline values for the first 15 frames
                    if response_counter <= 15:
                        detector.set_correct_value(current_values)
                        if response_counter == 15:
                            await websocket.send_json(
                                {
                                    "type": "initialization_success",
                                    "sitting_session_id": str(sitting_session_id),
                                }
                            )
                            logger.info("Initialization success message sent")
                    else:
                        session_start = time.time()
                        detector.detect(current_values, object_data.get("faceDetect"))

                    # Send the status of all topics in every loop iteration
                    await websocket.send_json(
                        {"type": "all_topic_alerts", "data": prepare_alert(detector)}
                    )

                    # Handle and send alerts based on thresholds and cooldowns
                    triggered_alerts = handle_alerts(
                        detector, last_alert_time, cooldown_periods, alert_thresholds
                    )
                    if triggered_alerts:
                        await websocket.send_json(
                            {"type": "triggered_alerts", "data": triggered_alerts}
                        )

                    # Periodically update the database session
                    if response_counter % 5 == 0:
                        update_sitting_session(
                            detector, response_counter, sitting_session, db
                        )
                else:
                    logger.warning("Unexpected message format, missing 'data' key.")

            except WebSocketDisconnect:
                end_sitting_session(sitting_session, db)
                session_end = time.time()
                session_duration = session_end - session_start
                print(session_duration)
                logger.info("WebSocket disconnected")
                break  # Exit loop to clean up resources on disconnect

            except Exception as e:
                logger.error(f"Error in WebSocket connection: {e}")
                if websocket.client_state == WebSocketState.CONNECTED:
                    await websocket.close()
                break

    except Exception as e:
        logger.error(f"Fatal error in WebSocket connection: {e}")


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
            session_type="stream",
            duration=0,
            is_complete=False,
        )

        db.add(db_sitting_session)
        db.commit()
        return db_sitting_session, sitting_session_id  # Return both session and ID

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
    try:
        return {
            "shoulderPosition": processed_data.get_shoulder_position(),
            "diameterRight": processed_data.get_diameter_right(),
            "diameterLeft": processed_data.get_diameter_left(),
            "eyeAspectRatioRight": processed_data.get_blink_right(),
            "eyeAspectRatioLeft": processed_data.get_blink_left(),
        }
    except KeyError as e:
        logger.error(f"Error extracting current values: missing key {e}")
        return None


def prepare_alert(detector):
    """Prepare a combined alert dictionary based on the detector's results."""
    alert = detector.get_alert()
    return {
        "blink": alert.get("blink_alert"),
        "sitting": alert.get("sitting_alert"),
        "distance": alert.get("distance_alert"),
        "thoracic": alert.get("thoracic_alert"),
    }


def handle_alerts(detector, last_alert_time, cooldown_periods, alert_thresholds):
    """Handle alerts and check if they meet thresholds and cooldowns."""
    triggered_alerts = {}
    current_time = get_current_time()

    for alert_type in ALERT_TYPES:
        if should_send_alert(
            detector=detector,
            alert_type=alert_type,
            last_alert_time=last_alert_time[alert_type],
            cooldown_period=cooldown_periods[alert_type],
            alert_duration_threshold=alert_thresholds[alert_type],
        ):
            triggered_alerts[alert_type] = True
            last_alert_time[alert_type] = current_time
            logger.info(f"Prepared {alert_type} alert at {current_time}")

    return triggered_alerts


def update_sitting_session(detector, duration, sitting_session, db):
    """Update the sitting session in the database with detector timeline results."""
    try:
        timeline_result = detector.get_timeline_result()
        sitting_session.blink = timeline_result["blink"]
        sitting_session.sitting = timeline_result["sitting"]
        sitting_session.distance = timeline_result["distance"]
        sitting_session.thoracic = timeline_result["thoracic"]
        sitting_session.duration = duration
        db.commit()
    except SQLAlchemyError as e:
        db.rollback()
        logger.error(f"Error updating sitting session: {e}")


def end_sitting_session(sitting_session, db):
    try:
        sitting_session.is_complete = True
        db.commit()
    except SQLAlchemyError as e:
        db.rollback()
        logger.error(f"Error updating sitting session: {e}")


def update_video_session(video_name, thumbnail, sitting_session, db):
    """Update the sitting session in the database with video file name."""
    try:
        sitting_session.file_name = video_name
        sitting_session.thumbnail = thumbnail
        db.commit()
    except SQLAlchemyError as e:
        db.rollback()
        logger.error(f"Error updating video session: {e}")


def should_send_alert(
    detector, alert_type, last_alert_time, cooldown_period, alert_duration_threshold
):
    """Determines whether to send an alert based on the posture detection results."""
    current_time = get_current_time()

    # Cooldown check
    if last_alert_time and current_time - last_alert_time < cooldown_period:
        return False

    # Check if the specific alert has persisted long enough
    alert_timeline = detector.timeline_result.get(alert_type, [])
    if detector.result.get(f"{alert_type}_alert") and alert_timeline:
        last_issue_time = datetime.fromtimestamp(alert_timeline[-1][0]).replace(
            tzinfo=LOCAL_TZ
        )
        return current_time - last_issue_time > alert_duration_threshold

    return False

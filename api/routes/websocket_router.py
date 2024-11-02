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
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError, IntegrityError

from api.procressData import processData
from api.request_user import get_current_user
from auth.token import LOCAL_TZ, get_current_time, get_sub_from_token
from api.detection import detection
from database.database import get_db
from database.model import SittingSession
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


@websocket_router.post("/video_name")
async def receive_video_name(
    request: VideoNameRequest,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    try:
        video_name = request.video_name
        thumbnail = request.thumbnail
        user_id = current_user.get("user_id")

        if not user_id:
            raise HTTPException(status_code=400, detail="Invalid user data")

        sitting_session = (
            db.query(SittingSession)
            .filter(SittingSession.user_id == user_id)
            .order_by(SittingSession.date.desc())
            .first()
        )
        if not sitting_session:
            raise HTTPException(status_code=404, detail="Sitting session not found")

        update_video_session(video_name, thumbnail, sitting_session, db)
        return {"message": "Video session updated successfully"}

    except SQLAlchemyError as e:
        logger.error(f"Database error while updating video session: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")
    except Exception as e:
        logger.error(f"Unexpected error updating video session: {e}")
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

    if not acc_token:
        logger.error("Access token missing in WebSocket cookies.")
        await websocket.close(code=4003, reason="Access token missing")
        return

    logger.info("WebSocket connection accepted")

    focal_length_values = None
    set_focal_length = False
    detector = None

    if focal_length_enabled and not set_focal_length:
        try:
            init_message = await websocket.receive_text()
            init_data = json.loads(init_message)
            focal_length_data = init_data.get("focal_length")
            if focal_length_data:
                camera_matrix = focal_length_data.get("cameraMatrix")
                if camera_matrix:
                    fx = round(camera_matrix[0][0], 2)
                    fy = round(camera_matrix[1][1], 2)
                    focal_length_values = (fx + fy) / 2
                    detector = detection(
                        frame_per_second=15, focal_length=focal_length_values
                    )
                    set_focal_length = True
        except json.JSONDecodeError:
            logger.warning("Error decoding initial message JSON")
        except Exception as e:
            logger.warning(f"Error receiving focal length data: {e}")

    if focal_length_enabled:
        detector = (
            detection(frame_per_second=15, focal_length=focal_length_values)
            if stream
            else None
        )
    else:
        detector = detection(frame_per_second=15) if stream else None

    session_start = None
    sitting_session = None
    sitting_session_id = None
    response_counter = 0
    last_alert_time = {alert_type: None for alert_type in ALERT_TYPES}

    try:
        logger.info(f"Focal length values: {focal_length_values}")

        while stream:
            try:
                message = await websocket.receive_text()
                message_data = json.loads(message)

                if "data" in message_data:
                    object_data = message_data["data"]
                    processed_data = processData(object_data)
                    current_values = extract_current_values(processed_data)
                    if current_values is None:
                        continue

                    response_counter += 1

                    if response_counter == 1 and not sitting_session:
                        session_start = time.time()
                        sitting_session, sitting_session_id = initialize_session(
                            acc_token, db
                        )

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
                        detector.detect(current_values, object_data.get("faceDetect"))

                    if response_counter % 3 == 0:
                        await websocket.send_json(
                            {
                                "type": "all_topic_alerts",
                                "data": prepare_alert(detector),
                            }
                        )

                    triggered_alerts = handle_alerts(
                        detector, last_alert_time, cooldown_periods, alert_thresholds
                    )
                    if triggered_alerts:
                        await websocket.send_json(
                            {"type": "triggered_alerts", "data": triggered_alerts}
                        )

                    if response_counter % 5 == 0:
                        update_sitting_session(
                            detector, response_counter, sitting_session, db
                        )
                else:
                    logger.warning("Unexpected message format, missing 'data' key.")

            except WebSocketDisconnect:
                if session_start:
                    # session_end = time.time()
                    # session_duration = session_end - session_start
                    logger.info(f"Session Duration: {response_counter} seconds")
                else:
                    # session_duration = 0
                    response_counter = 0
                end_sitting_session(sitting_session, response_counter, db)
                logger.info("WebSocket disconnected")
                break

            except Exception as e:
                logger.error(f"Error in WebSocket connection: {e}")
                if "401: Token has expired" in str(e):
                    if websocket.client_state == WebSocketState.CONNECTED:
                        await websocket.close(code=4001)
                else:
                    if websocket.client_state == WebSocketState.CONNECTED:
                        await websocket.close(
                            code=1000, reason="Unexpected server error"
                        )
    except Exception as e:
        logger.error(f"Fatal error in WebSocket connection: {e}")


def initialize_session(acc_token, db):
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
        return db_sitting_session, sitting_session_id

    except (IntegrityError, SQLAlchemyError) as e:
        db.rollback()
        logger.error(f"Database error while creating session: {e}")
        raise HTTPException(
            status_code=400 if isinstance(e, IntegrityError) else 500,
            detail=f"Error creating session: {e}",
        )


def extract_current_values(processed_data):
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
        "blink": alert.get("blink_alert", False),
        "sitting": alert.get("sitting_alert", False),
        "distance": alert.get("distance_alert", False),
        "thoracic": alert.get("thoracic_alert", False),
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


def end_sitting_session(sitting_session, duration, db):
    """Mark the sitting session as complete."""
    try:
        if sitting_session:
            sitting_session.is_complete = True
            sitting_session.duration = duration
            db.commit()
    except SQLAlchemyError as e:
        db.rollback()
        logger.error(f"Error ending sitting session: {e}")


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
    """Determines whether to send an alert based on detection results."""
    current_time = get_current_time()

    # Cooldown check
    if last_alert_time and (current_time - last_alert_time) < cooldown_period:
        return False

    # Check if the specific alert has persisted long enough
    alert_timeline = detector.timeline_result.get(alert_type, [])
    if detector.result.get(f"{alert_type}_alert") and alert_timeline:
        last_issue_time = datetime.fromtimestamp(alert_timeline[-1][0]).replace(
            tzinfo=LOCAL_TZ
        )
        return current_time - last_issue_time > alert_duration_threshold

    return False

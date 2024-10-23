from datetime import datetime, timedelta
import json
import logging
import uuid
from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.websockets import WebSocketState
from requests import Session
from api.procressData import processData
from auth.token import LOCAL_TZ, get_current_time, get_sub_from_token
from api.detection import detection
from database.database import get_db
from database.model import SittingSession
from sqlalchemy.exc import SQLAlchemyError, IntegrityError

logger = logging.getLogger(__name__)

websocket_router = APIRouter()

# Define alert types and their cooldown and threshold times
ALERT_TYPES = ["blink", "sitting", "distance", "thoracic"]

cooldown_periods = {
    "blink": timedelta(minutes=2),  # Blink cooldown
    "sitting": timedelta(minutes=30),  # Sitting posture cooldown
    "distance": timedelta(minutes=10),  # Screen distance cooldown
    "thoracic": timedelta(minutes=10),  # Thoracic posture cooldown
}

alert_thresholds = {
    "blink": timedelta(seconds=10),  # Blink threshold
    "sitting": timedelta(minutes=2),  # Sitting posture threshold
    "distance": timedelta(minutes=1),  # Screen distance threshold
    "thoracic": timedelta(minutes=1),  # Thoracic posture threshold
}


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

    # Track last alert times for cooldowns
    last_alert_time = {alert_type: None for alert_type in ALERT_TYPES}

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
            if response_counter <= 15:
                detector.set_correct_value(current_values)
                if response_counter == 15:
                    # Send success message after the baseline is set
                    await websocket.send_json({"type": "initialization_success"})
                    logger.info("Initialization success message sent")
            else:
                detector.detect(current_values, object_data["data"]["faceDetect"])

            current_time = get_current_time()

            # Prepare all topic alert data (status of all topics)
            all_topic_alert_data = prepare_alert(detector)

            # Send the status of all topics in every loop iteration
            await websocket.send_json(
                {"type": "all_topic_alerts", "data": all_topic_alert_data}
            )

            # Prepare triggered alert data (alerts that meet cooldown and threshold)
            triggered_alerts = {}

            # Iterate over each alert type and check if it should be triggered
            for alert_type in ALERT_TYPES:
                if should_send_alert(
                    detector=detector,
                    alert_type=alert_type,
                    last_alert_time=last_alert_time[alert_type],
                    cooldown_period=cooldown_periods[alert_type],
                    alert_duration_threshold=alert_thresholds[alert_type],
                ):
                    triggered_alerts[alert_type] = True  # Only send this alert type
                    last_alert_time[alert_type] = current_time  # Update last alert time
                    logger.info(f"Prepared {alert_type} alert at {current_time}")

            # If there are any triggered alerts, send them separately
            if triggered_alerts:
                await websocket.send_json(
                    {"type": "triggered_alerts", "data": triggered_alerts}
                )

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
    """
    Prepare a combined alert dictionary based on the detector's results.
    This will return alerts for all detection types (blink, sitting, distance, thoracic).
    """
    alert = detector.get_alert()

    # Return the status of all alert types, not just triggered ones
    return {
        "blink": alert["blink_alert"],
        "sitting": alert["sitting_alert"],
        "distance": alert["distance_alert"],
        "thoracic": alert["thoracic_alert"],
    }


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


def should_send_alert(
    detector, alert_type, last_alert_time, cooldown_period, alert_duration_threshold
):
    """
    Determines whether to send an alert based on the posture detection results.

    Args:
    - detector: An instance of the detection class.
    - alert_type: The type of alert (blink, sitting, distance, thoracic).
    - last_alert_time: The last time an alert was sent for this type.
    - cooldown_period: A timedelta object representing the cooldown period between alerts.
    - alert_duration_threshold: A timedelta object representing the minimum time a posture issue should persist before triggering an alert.

    Returns:
    - Boolean indicating whether an alert should be sent.
    """
    current_time = get_current_time()

    # Cooldown check: Don't send another alert if within the cooldown period
    if last_alert_time and current_time - last_alert_time < cooldown_period:
        return False

    # Check if the specific alert has persisted long enough based on timeline results
    if detector.result[f"{alert_type}_alert"]:
        last_issue_time = datetime.fromtimestamp(
            detector.timeline_result[alert_type][-1][0]
        ).replace(tzinfo=LOCAL_TZ)
        if current_time - last_issue_time > alert_duration_threshold:
            return True

    return False

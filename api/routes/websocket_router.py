import asyncio
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
from auth.token import LOCAL_TZ, get_current_time, get_sub_from_token, verify_token
from api.detection import detection
from database.database import get_db
from database.model import SittingSession
from database.schemas.User import VideoNameRequest

logger = logging.getLogger(__name__)

websocket_router = APIRouter()


cooldown_periods = {
    "blink": timedelta(minutes=1),
    "sitting": timedelta(minutes=1),
    "distance": timedelta(minutes=1),
    "thoracic": timedelta(minutes=1),
    "time_limit_exceed": timedelta(minutes=1),
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

    try:
        verify_token(acc_token)
    except HTTPException as e:
        logger.error(f"WebSocket token verification failed: {e.detail}")
        await websocket.close(code=4001, reason=e.detail)
        return

    detector = None
    focal_length_values = None
    if focal_length_enabled:
        try:
            init_message = await websocket.receive_text()
            init_data = json.loads(init_message)
            focal_length_data = init_data.get("focal_length", {})
            camera_matrix = focal_length_data.get("cameraMatrix")
            if camera_matrix:
                fx = round(camera_matrix[0][0], 2)
                fy = round(camera_matrix[1][1], 2)
                focal_length_values = (fx + fy) / 2
                detector = detection(
                    frame_per_second=15, focal_length=focal_length_values
                )
            else:
                logger.error("Focal length data is missing or incomplete.")
                await websocket.close(code=4003, reason="Focal length data missing")
                return
        except json.JSONDecodeError as e:
            logger.error(f"Error decoding initial message JSON: {e}")
            await websocket.close(code=4003, reason="Invalid initial data")
            return
        except Exception as e:
            logger.error(f"Error setting up focal length: {e}")
            await websocket.close(code=1011, reason="Failed to initialize")
            return
    else:
        detector = detection(frame_per_second=15) if stream else None

    session_start = None
    sitting_session = None
    sitting_session_id = None
    response_counter = 0
    is_session_initialized = False  # Flag to check if session is already initialized
    send_alert_time_track = {
        i: {"send": False, "last_time": None} for i in cooldown_periods
    }

    try:
        while stream:
            try:
                message = await websocket.receive_text()
                message_data = json.loads(message)
                data = message_data.get("data")
                if data:
                    processed_data = processData(data)
                    current_values = extract_current_values(processed_data)
                    if current_values is None:
                        continue

                    response_counter += 1

                    if not is_session_initialized:
                        if response_counter == 1 and not sitting_session:
                            session_start = time.time()
                            sitting_session, sitting_session_id = initialize_session(
                                acc_token, db
                            )
                            is_session_initialized = True  # Mark session as initialized

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
                        detector.detect(current_values, data.get("faceDetect"))

                    if response_counter % 3 == 0:
                        await websocket.send_json(
                            {
                                "type": "all_topic_alerts",
                                "data": prepare_alert(detector),
                            }
                        )

                    triggered_alerts = should_send_alert(
                        detector.get_alert(), cooldown_periods, send_alert_time_track
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
                    logger.warning("Received message without 'data' key.")

            except WebSocketDisconnect:
                logger.info(f"Session Duration: {response_counter} seconds")
                end_sitting_session(sitting_session, response_counter, db)
                response_counter = 0
                logger.info("WebSocket disconnected")
                break
            except json.JSONDecodeError as e:
                logger.warning(f"Error decoding message JSON: {e}")

            except Exception as e:
                logger.error(f"Error during message processing: {e}")
                break

    except Exception as e:
        logger.error(f"Fatal error in WebSocket connection: {e}")
        await websocket.close(code=1011, reason="Unexpected error occurred")


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


def should_send_alert(alert, cooldown_periods, send_alert_time_track):
    current_time = get_current_time()
    alert_result = {}
    for i in cooldown_periods:
        if alert[i + "_alert"] and send_alert_time_track[i]["send"] is False:
            send_alert_time_track[i]["send"] = True
            send_alert_time_track[i]["last_time"] = current_time
            alert_result[i] = True
            print(i + ": alert")
        elif alert[i + "_alert"] is False and send_alert_time_track[i]["send"]:
            send_alert_time_track[i]["send"] = False
            send_alert_time_track[i]["last_time"] = None
            print(i + ": stop alert")
        elif (alert[i + "_alert"] and send_alert_time_track[i]["send"]) and (
            (send_alert_time_track[i]["last_time"] + cooldown_periods[i]) < current_time
        ):
            send_alert_time_track[i]["last_time"] = current_time
            alert_result[i] = True
            print(i + ": alert Again?")
    return alert_result

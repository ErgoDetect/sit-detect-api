import json
import logging
from typing import List, Optional
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from fastapi.websockets import WebSocketState
from api.procressData import processData  # Ensure this import is correct

logger = logging.getLogger(__name__)

websocket_router = APIRouter()

@websocket_router.websocket("/results/")
async def landmark_results(websocket: WebSocket):
    await websocket.accept()
    logger.info("WebSocket connection accepted")

    frame_per_second = 1

    response_counter = 0
    saved_values = []
    correct_values = {}
    current_values = {}

    ear_threshold_low = 0.2
    ear_threshold_high = 0.4
    ear_below_threshold = False
    blink_detected = False

    latest_nearest_distance = 0
    latest_nearest_distance_left = 0
    latest_nearest_distance_right = 0

    blink_stack = 0
    sitting_stack = 0
    distance_stack = 0
    thoracic_stack = 0

    result = [False, False, False, False]  # [blink_alert, sitting_alert, distance_alert, thoracic_alert]

    try:
        while True:
            # Receive data from the client
            message = await websocket.receive_text()
            object_data = json.loads(message)
            processed_data = processData(object_data['data'])

            # Extract current values
            current_values = {
                "shoulderPosition": processed_data.get_shoulder_position().get('y'),
                "diameterRight": processed_data.get_diameter_right(),
                "diameterLeft": processed_data.get_diameter_left(),
                "eyeAspectRatioRight": processed_data.get_blink_right(),
                "eyeAspectRatioLeft": processed_data.get_blink_left()
            }

            # Process the first 5 messages to establish baseline values
            if response_counter < 5:
                saved_values.append(current_values)
                response_counter += 1
                if response_counter == 5:
                    # Compute averages for correct_values
                    # Handle cases where values might be None
                    def average(values):
                        valid_values = [v for v in values if v is not None]
                        return sum(valid_values) / len(valid_values) if valid_values else None

                    correct_values = {
                        "shoulderPosition": average([v['shoulderPosition'] for v in saved_values]),
                        "diameterRight": average([v['diameterRight'] for v in saved_values]),
                        "diameterLeft": average([v['diameterLeft'] for v in saved_values])
                    }
                continue  # Skip further processing until baseline is established

            # Now process data using the established correct_values
            # Update thoracic_stack
            shoulder_pos = current_values.get("shoulderPosition")
            baseline_shoulder_pos = correct_values.get("shoulderPosition")
            if shoulder_pos is None or baseline_shoulder_pos is None:
                thoracic_stack = 0
            elif baseline_shoulder_pos * 0.90 >= shoulder_pos:
                thoracic_stack += 1
            else:
                thoracic_stack = 0

            # Check if face is detected
            if not object_data['data'].get("faceDetect", False):
                blink_stack = 0
                sitting_stack = 0
                distance_stack = 0
            else:
                sitting_stack += 1

                # Update distance_stack
                diameter_right = current_values.get("diameterRight")
                diameter_left = current_values.get("diameterLeft")
                baseline_diameter_right = correct_values.get("diameterRight")
                baseline_diameter_left = correct_values.get("diameterLeft")

                if diameter_right is not None:
                    latest_nearest_distance_right = diameter_right
                if diameter_left is not None:
                    latest_nearest_distance_left = diameter_left

                latest_nearest_distance = max(
                    latest_nearest_distance_right, latest_nearest_distance_left
                )

                baseline_distance = max(
                    baseline_diameter_right or 0, baseline_diameter_left or 0
                )

                if baseline_distance and latest_nearest_distance:
                    if baseline_distance * 0.90 <= latest_nearest_distance:
                        distance_stack += 1
                    else:
                        distance_stack = 0

                # Update blink_stack
                ear_left = current_values.get("eyeAspectRatioLeft")
                ear_right = current_values.get("eyeAspectRatioRight")

                if (ear_left is not None and ear_left <= ear_threshold_low) or \
                   (ear_right is not None and ear_right <= ear_threshold_low):
                    ear_below_threshold = True
                    blink_stack += 1
                elif ear_below_threshold and (
                    (ear_left is not None and ear_left >= ear_threshold_high) or
                    (ear_right is not None and ear_right >= ear_threshold_high)
                ):
                    if not blink_detected:
                        blink_stack = 0
                        blink_detected = True
                    ear_below_threshold = False
                else:
                    blink_detected = False
                    blink_stack += 1

            # Update result based on stacks
            result[0] = blink_stack >= 5 * frame_per_second
            result[1] = sitting_stack >= 2700 * frame_per_second
            result[2] = distance_stack >= 30 * frame_per_second
            result[3] = thoracic_stack >= 2 * frame_per_second

            # Send the result back to the client
            await websocket.send_json({
                "blink_alert": result[0],
                "sitting_alert": result[1],
                "distance_alert": result[2],
                "thoracic_alert": result[3]
            })

    except WebSocketDisconnect:
        logger.info("WebSocket disconnected")
    except Exception as e:
        logger.error(f"Error in WebSocket connection: {e}")
        if websocket.client_state == WebSocketState.CONNECTED:
            await websocket.close()

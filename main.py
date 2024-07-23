from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.websockets import WebSocketState
import numpy as np
import cv2
import logging
import platform
import os
import base64
import json
import time
from datetime import datetime

from api.detection import detection

app = FastAPI()

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Platform-specific settings
if platform.system() == "Darwin":
    os.environ['KMP_DUPLICATE_LIB_OK'] = 'True'

async def process_image(data: bytes) -> dict:
    """Process the received image data."""
    try:
        img_data = base64.b64decode(data)
        nparr = np.frombuffer(img_data, np.uint8)
        img_np = cv2.imdecode(nparr, cv2.IMREAD_COLOR)

        detection_result = detection(img_np)
        head_position = detection_result.get_head_position()
        depth_left_iris = detection_result.get_depth_left_iris()
        depth_right_iris = detection_result.get_depth_right_iris()
        shoulder_position = detection_result.get_shoulder_position()


        result = {
            "headPosition": head_position,
            "depthLeftIris":depth_left_iris,
            "depthRightIris":depth_right_iris,
            "shoulderPosition":shoulder_position
        }

        return result
    except Exception as e:
        logger.error(f"Error processing image: {e}")
        return {"error": f"Error processing image: {e}"}

@app.get("/")
def read_root():
    return {"message": "Hello, World"}

@app.websocket("/ws")
async def receive_video(websocket: WebSocket):
    await websocket.accept()
    logger.info("WebSocket connection accepted")

    try:
        while websocket.client_state == WebSocketState.CONNECTED:
            try:
                message = await websocket.receive_text()
                # data = json.loads(message)
                
                # frame_count = data.get('frameCount')
                # image_data = data.get('image')
                logger.info(f"Received message: {message}")
                # if not image_data:
                #     raise ValueError("No image provided")

                # client_timestamp = data.get('timestamp')
                # received_time = time.time() * 1000  # Current time in milliseconds
                # latency = received_time - client_timestamp
                
                # logger.info(f"Received frame {frame_count} at {datetime.utcfromtimestamp(received_time / 1000).isoformat()} with latency {latency:.2f} ms")

                # # Process the image and include landMarkData
                # result = await process_image(image_data)
                # result['frameCount'] = frame_count
                # result['latency'] = latency
                # result['landMarkData'] = land_mark_data  # Include landMarkData in result

                # logger.info(f"Sending frame: {result['frameCount']}")

                # await websocket.send_json(result)

            except WebSocketDisconnect:
                logger.info("WebSocket disconnected")
                break

            except Exception as e:
                logger.error(f"Error during WebSocket communication: {e}")
                await websocket.send_json({"error": str(e)})
                await websocket.close()
                break

    except Exception as e:
        logger.error(f"Error in WebSocket connection: {e}")
        if websocket.client_state == WebSocketState.CONNECTED:
            await websocket.close()

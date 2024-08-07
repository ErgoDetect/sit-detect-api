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

from api.procressData import processData

app = FastAPI()

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Platform-specific settings
if platform.system() == "Darwin":
    os.environ['KMP_DUPLICATE_LIB_OK'] = 'True'



@app.get("/")
def read_root():
    return {"message": "Hello, World"}

@app.websocket("/landmark-results")
async def receive_video(websocket: WebSocket):
    await websocket.accept()
    logger.info("WebSocket connection accepted")

    try:
        while websocket.client_state == WebSocketState.CONNECTED:
            try:
                message = await websocket.receive_text()
                # frame_count = data.get('frameCount')
                # logger.info(f"Received message: {message}")

                objectData = json.loads(message)
                procesData = processData(objectData['data'])
                logger.info(f"Shoulder Position: {procesData.get_shoulder_position()}")
                logger.info(f"Blink Right: {procesData.get_blink_right()}")
                logger.info(f"Blink Left: {procesData.get_blink_left()}")

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

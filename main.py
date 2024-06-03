from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.websockets import WebSocketState
import numpy as np
import cv2
import asyncio
import logging
import platform
import os

# Import optimized detection functions
from api.detection import get_rotation_degree, get_head_position,get_depth,get_shoulder_position

app = FastAPI()

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Check if running on macOS or Windows and adjust settings accordingly
is_macos = platform.system() == "Darwin"
is_windows = platform.system() == "Windows"

if is_macos:
    # macOS specific environment settings (if any)
    os.environ['KMP_DUPLICATE_LIB_OK'] = 'True'

if is_windows:
    # Windows specific environment settings (if any)
    pass

async def process_image(data: bytes) -> dict:
    try:
        nparr = np.frombuffer(data, np.uint8)
        img_np = cv2.imdecode(nparr, cv2.IMREAD_COLOR)

        # Perform image processing asynchronously
        head_position = await asyncio.to_thread(get_head_position, img_np)
        head_rotation_degree = await asyncio.to_thread(get_rotation_degree, img_np)
        depth = await asyncio.to_thread(get_depth, img_np)
        shoulder_position = await asyncio.to_thread(get_shoulder_position, img_np)

        result = {
            "headPosition": head_position,
            "headRotationDegree": head_rotation_degree,
            "depth":depth,
            "shoulderPosition": shoulder_position,
        }
        return result
    except Exception as e:
        logger.error(f"Error processing image: {e}")
        return {"error": f"Error processing image: {e}"}

@app.get("/")
def read_root():
    return {"Hello": "World"}

@app.websocket("/ws")
async def receive_video(websocket: WebSocket):
    await websocket.accept()
    logger.info("WebSocket connection accepted")

    try:
        while websocket.client_state == WebSocketState.CONNECTED:
            try:
                data = await websocket.receive_bytes()

                if isinstance(data, bytes):
                    result = await process_image(data)
                    await websocket.send_json(result)
                else:
                    logger.error("Received data is not of type bytes")
                    await websocket.send_json({"error": "Unexpected data format (not bytes)"})
                    await websocket.close()
                    break

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

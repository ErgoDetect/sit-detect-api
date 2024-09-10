import json
import logging
from fastapi import WebSocket, WebSocketDisconnect
from fastapi.websockets import WebSocketState
from api.procressData import processData

logger = logging.getLogger(__name__)

# Process WebSocket for landmark results
async def process_landmark_results(websocket: WebSocket):
    await websocket.accept()
    logger.info("WebSocket connection accepted")

    try:
        while websocket.client_state == WebSocketState.CONNECTED:
            try:
                message = await websocket.receive_text()
                object_data = json.loads(message)
                processed_data = processData(object_data['data'])
                result = {
                    "shoulderPosition": processed_data.get_shoulder_position(),
                    "blinkRight": processed_data.get_blink_right(),
                    "blinkLeft": processed_data.get_blink_left(),
                }
                await websocket.send_json(result)
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

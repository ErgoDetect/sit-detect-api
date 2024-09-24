import json
import logging
from typing import List
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from fastapi.websockets import WebSocketState
from api.procressData import processData


logger = logging.getLogger(__name__)

class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        self.active_connections.remove(websocket)

    async def send_message(self, message: str, websocket: WebSocket):
        await websocket.send_text(message)

# Instance of the connection manager
manager = ConnectionManager()

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


websocket_router = APIRouter()

@websocket_router.websocket("/results/")
async def landmark_results(websocket: WebSocket):
    await manager.connect(websocket)

    frame_per_second = 1

    response_counter = 0
    saved_values = []
    correct_values = {}
    current_values = {}

    ear_threshoild_low = 0.2
    ear_threshoild_high = 0.4
    ear_below_threshold = False
    blink_detected = False

    lastest_nearest_distance = 0
    lastest_nearest_distance_left = 0
    lastest_nearest_distance_right = 0

    blink_stack = 0
    siting_stack = 0
    distance_stack = 0
    thoracic_stack = 0

    # result = [blink_stack,siting_stack,distance_stack,thoracic_stack]
    # result คือตัวผลลัพธ์ที่จะส่ง
    result = [False,False,False,False]



    # goback = "\033[F" * 2
    try:
        while True:
            # Receive data from the client
            message = await websocket.receive_text()
            object_data = json.loads(message)
            processed_data = processData(object_data['data'])

            # print(object_data['data'],"\n_____________________________________________")
            # Process the first 5 messages
            
            if response_counter < 5:
                # saved_values.append(processed_data)
                if response_counter == 0 :
                    correct_values= {"shoulderPosition":processed_data.get_shoulder_position(),
                                 "diameterRight":processed_data.get_diameter_right(),
                                 "diameterLeft":processed_data.get_diameter_left()}
                else :
                    correct_values_tmp= {"shoulderPosition":processed_data.get_shoulder_position(),
                                 "diameterRight":processed_data.get_diameter_right(),
                                 "diameterLeft":processed_data.get_diameter_left()}
                    if (correct_values_tmp["shoulderPosition"] is not None and
                        correct_values_tmp["diameterRight"] is not None and
                        correct_values_tmp["diameterLeft"] is not None) :
                        correct_values = correct_values_tmp
                response_counter += 1
                # print(f"Response {response_counter} saved: {processed_data}", websocket)

            # After 5 messages are saved, continue processing if needed
            if response_counter == 5:
                # print(f"First 5 values saved: {saved_values}", websocket)
                response_counter += 1

            current_values= {"shoulderPosition":processed_data.get_shoulder_position(),
                            "diameterRight":processed_data.get_diameter_right(),
                            "diameterLeft":processed_data.get_diameter_left(),
                            "eyeAspectRatioRight":processed_data.get_blink_right(),
                            "eyeAspectRatioLeft":processed_data.get_blink_left()}
            
            if current_values["shoulderPosition"] == None:
                thoracic_stack = 0
            elif correct_values["shoulderPosition"]*0.90>=current_values["shoulderPosition"]:
                thoracic_stack += 1
            else : thoracic_stack = 0

            if object_data['data']["faceDetect"] == False:
                blink_stack = 0
                siting_stack = 0
                distance_stack = 0
            else :
                siting_stack += 1
                if current_values["diameterRight"] != None or current_values["diameterLeft"] != None:
                    if current_values["diameterRight"] != None:
                        lastest_nearest_distance_right = current_values["diameterRight"]
                    if current_values["diameterLeft"] != None:
                        lastest_nearest_distance_left = current_values["diameterLeft"]
                    if lastest_nearest_distance_right > lastest_nearest_distance_left:
                        lastest_nearest_distance = lastest_nearest_distance_right
                    else : lastest_nearest_distance = lastest_nearest_distance_left
                if correct_values["diameterRight"] > correct_values["diameterLeft"] :
                    if correct_values["diameterRight"] *0.90<= lastest_nearest_distance:
                        distance_stack +=1
                    else : distance_stack = 0
                else :
                    if correct_values["diameterLeft"]*0.90<= lastest_nearest_distance:
                        distance_stack +=1
                    else : distance_stack = 0
                if current_values["eyeAspectRatioLeft"] <= ear_threshoild_low or current_values["eyeAspectRatioRight"] <= ear_threshoild_low:
                    ear_below_threshold = True
                    blink_stack += 1 
                    
                elif ear_below_threshold and (current_values["eyeAspectRatioLeft"]  >= ear_threshoild_high or current_values["eyeAspectRatioRight"] >= ear_threshoild_high):
                    if not blink_detected:
                        blink_stack = 0
                        blink_detected = True
                    ear_below_threshold = False
                else:
                    blink_detected = False
                    blink_stack += 1 
                

            if blink_stack >= 5*frame_per_second:
                result[0] = True
            else : result[0] = False
            if siting_stack >= 2700*frame_per_second:
                result[1] = True
            else : result[1] = False
            if distance_stack >= 30*frame_per_second:
                result[2] = True
            else : result[2] = False
            if thoracic_stack >= 2*frame_per_second:
                result[3] = True 
            else : result[3] = False   
            # print(f"[{blink_stack}], [{siting_stack}], [{distance_stack}], [{thoracic_stack}]")
            # print(result)
            # print(datetime.fromtimestamp(object_data["timestamp"] / 1000))
            # print(current_values["shoulderPosition"])
        
            

    except WebSocketDisconnect:
        manager.disconnect(websocket)
        print(f"Connection closed. Saved values: {saved_values}")



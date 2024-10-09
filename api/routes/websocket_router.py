import json
import logging
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from fastapi.websockets import WebSocketState
from api.procressData import processData 

logger = logging.getLogger(__name__)

websocket_router = APIRouter()

@websocket_router.websocket("/results/")
async def landmark_results(websocket: WebSocket):
    await websocket.accept()
    logger.info("WebSocket connection accepted")

    # Constants
    frame_per_second = 1
    ear_threshold_low = 0.4
    ear_threshold_high = 0.5

    # Initialization of variables
    response_counter = 0
    saved_values = []
    correct_values = {}
    ear_below_threshold = False
    blink_detected = False

    latest_nearest_distance = 0
    blink_stack = 0
    sitting_stack = 0
    distance_stack = 0
    thoracic_stack = 0

    blink_stack_threshold = 5
    sitting_stack_threshold = 2700
    distance_stack_threshold = 30
    thoracic_stack_threshold = 2
    result = [False, False, False, False]  # [blink_alert, sitting_alert, distance_alert, thoracic_alert]

    timeline_result = {
        "blink":[],
        "sitting":[],
        "distance":[],
        "thoracic":[],
    }
    
    try:
        while True:
            # Receive and process data from the client
            message = await websocket.receive_text()
            object_data = json.loads(message)
            processed_data = processData(object_data['data'])
            # Extract current values
            current_values = {
                "shoulderPosition": processed_data.get_shoulder_position(),
                "diameterRight": processed_data.get_diameter_right(),
                "diameterLeft": processed_data.get_diameter_left(),
                "eyeAspectRatioRight": processed_data.get_blink_right(),
                "eyeAspectRatioLeft": processed_data.get_blink_left()
            }

            # Process the first 5 messages to establish baseline values
            if response_counter <= 5:
                saved_values.append(current_values) 
                # response_counter += 1
                if response_counter == 5:
                    # Compute averages for correct_values
                    def average(values):
                        valid_values = [v for v in values if v is not None]
                        return sum(valid_values) / len(valid_values) if valid_values else None

                    correct_values = {
                        "shoulderPosition": average([v['shoulderPosition'] for v in saved_values]),
                        "diameterRight": average([v['diameterRight'] for v in saved_values]),
                        "diameterLeft": average([v['diameterLeft'] for v in saved_values])
                    }
            else:
                current_values= {"shoulderPosition":processed_data.get_shoulder_position(),
                                "diameterRight":processed_data.get_diameter_right(),
                                "diameterLeft":processed_data.get_diameter_left(),
                                "eyeAspectRatioRight":processed_data.get_blink_right(),
                                "eyeAspectRatioLeft":processed_data.get_blink_left()}

                # Update thoracic_stack if necessary
                if current_values["shoulderPosition"] == None:
                    thoracic_stack = 0
                elif correct_values["shoulderPosition"]+0.05<=current_values["shoulderPosition"]:
                    thoracic_stack += 1
                else : thoracic_stack = 0

                # Reset stacks if no face is detected
                if object_data['data']["faceDetect"] == False:
                    blink_stack = 0
                    sitting_stack = 0
                    distance_stack = 0
                else:
                    sitting_stack += 1

                    # Update distance_stack
                    diameter_right = current_values.get("diameterRight")
                    diameter_left = current_values.get("diameterLeft")
                    correct_diameter_right = correct_values.get("diameterRight")
                    correct_diameter_left = correct_values.get("diameterLeft")

                    latest_nearest_distance = max(
                        diameter_right or latest_nearest_distance,
                        diameter_left or latest_nearest_distance
                    )

                    correct_distance = max(
                        correct_diameter_right or 0, correct_diameter_left or 0
                    )

                    if correct_distance and latest_nearest_distance:
                        if correct_distance * 0.90 <= latest_nearest_distance:
                            distance_stack += 1
                        else:
                            distance_stack = 0

                    # Update blink_stack
                    ear_left = current_values.get("eyeAspectRatioLeft")
                    ear_right = current_values.get("eyeAspectRatioRight")

                    if ((ear_left is not None and ear_left <= ear_threshold_low) or 
                    (ear_right is not None and ear_right <= ear_threshold_low)):
                        ear_below_threshold = True
                        blink_stack += 1
                    elif ear_below_threshold and (
                        (ear_left is not None and ear_left >= ear_threshold_high) or
                        (ear_right is not None and ear_right >= ear_threshold_high)):
                        if not blink_detected:
                            blink_stack = 0
                            blink_detected = True
                        ear_below_threshold = False
                    else:
                        blink_detected = False
                        blink_stack += 1
                
                if(blink_stack >= blink_stack_threshold * frame_per_second ):
                    if(result[0]==False):
                        timeline_result["blink"].append([]) 
                        timeline_result["blink"][len(timeline_result["blink"])-1].append(response_counter-blink_stack_threshold)
                    result[0] = True
                else:
                    if(result[0]==True):
                        timeline_result["blink"][len(timeline_result["blink"])-1].append(response_counter)
                    result[0] = False

                if(sitting_stack >= sitting_stack_threshold * frame_per_second ):
                    if(result[1]==False):
                        timeline_result["sitting"].append([]) 
                        timeline_result["sitting"][len(timeline_result["sitting"])-1].append(response_counter-sitting_stack_threshold)
                    result[1] = True
                else:
                    if(result[1]==True):
                        timeline_result["sitting"][len(timeline_result["sitting"])-1].append(response_counter)
                    result[1] = False

                if(distance_stack >= distance_stack_threshold * frame_per_second ):
                    if(result[2]==False):
                        timeline_result["distance"].append([]) 
                        timeline_result["distance"][len(timeline_result["distance"])-1].append(response_counter-distance_stack_threshold)
                    result[2] = True
                else:
                    if(result[2]==True):
                        timeline_result["distance"][len(timeline_result["distance"])-1].append(response_counter)
                    result[2] = False

                if(thoracic_stack >= thoracic_stack_threshold * frame_per_second ):
                    if(result[3]==False):
                        timeline_result["thoracic"].append([]) 
                        timeline_result["thoracic"][len(timeline_result["thoracic"])-1].append(response_counter-thoracic_stack_threshold)
                    result[3] = True
                else:
                    if(result[3]==True):
                        timeline_result["thoracic"][len(timeline_result["thoracic"])-1].append(response_counter)
                    result[3] = False

                # print(timeline_result)

                # Send the result back to the client
                await websocket.send_json({
                    "blink_alert": result[0],
                    "sitting_alert": result[1],
                    "distance_alert": result[2],
                    "thoracic_alert": result[3]
                })

                # print("correct:",correct_values)
                # print("current:",current_values)
                # print("blink:",blink_stack)
                # print("sitting:",sitting_stack)
                # print("distance:",distance_stack)
                # print("thoracic:",thoracic_stack)
                # print("counter:",response_counter)
            response_counter += 1
           

    except WebSocketDisconnect:
        logger.info("WebSocket disconnected")
    except Exception as e:
        logger.error(f"Error in WebSocket connection: {e}")
        if websocket.client_state == WebSocketState.CONNECTED:
            await websocket.close()

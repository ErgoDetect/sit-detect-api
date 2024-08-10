import cv2
import mediapipe as mp
import numpy as np
import math
import pickle
mp_face_mesh = mp.solutions.face_mesh
mp_face_detection = mp.solutions.face_detection
mp_pose_landmark = mp.solutions.pose
face_mesh = mp_face_mesh.FaceMesh(min_detection_confidence=0.5, min_tracking_confidence=0.5)
refine_face_mesh = mp_face_mesh.FaceMesh(min_detection_confidence=0.5, min_tracking_confidence=0.5,refine_landmarks=True)
face_detection = mp_face_detection.FaceDetection(model_selection=1, min_detection_confidence=0.5)
pose_landmark = mp_pose_landmark.Pose(min_detection_confidence=0.5)

with open("cameraMatrix.pkl", "rb") as f:
    cameraMatrix = pickle.load(f)

class detection:
    def __init__(self, image):
        self.image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)

        self.face_mesh_results = face_mesh.process(image)
        self.face_detection_results = face_detection.process(image)
        self.face_refine_face_mesh_results = refine_face_mesh.process(image)
        self.pose_landmark_result = pose_landmark.process(image)
    
    def get_rotation_degree(self):
        img_h, img_w, _ = self.image.shape
        
        face_3d = []
        face_2d = []
        
        if self.face_mesh_results.multi_face_landmarks:
            for face_landmarks in self.face_mesh_results.multi_face_landmarks:
                for idx, lm in enumerate(face_landmarks.landmark):
                    if idx == 33 or idx == 263 or idx == 1 or idx == 61 or idx == 291 or idx == 199:
                        # if idx == 1:
                            # nose_2d = (lm.x * img_w, lm.y * img_h)
                            # nose_3d = (lm.x * img_w, lm.y * img_h, lm.z * 3000)

                        x, y = int(lm.x * img_w), int(lm.y * img_h)

                        # Get the 2D Coordinates
                        face_2d.append([x, y])

                        # Get the 3D Coordinates
                        face_3d.append([x, y, lm.z])   
                
                # Convert to NumPy arrays
                face_2d = np.array(face_2d, dtype=np.float64)
                face_3d = np.array(face_3d, dtype=np.float64)
                
                # Camera matrix
                focal_length = img_w
                cam_matrix = np.array([[focal_length, 0, img_h / 2],
                                    [0, focal_length, img_w / 2],
                                    [0, 0, 1]])
                
                # Distortion parameters
                dist_matrix = np.zeros((4, 1), dtype=np.float64)
                
                # Solve PnP to get rotation vector
                success, rot_vec, trans_vec = cv2.solvePnP(face_3d, face_2d, cam_matrix, dist_matrix)
                
                # Get rotational matrix
                rmat, _ = cv2.Rodrigues(rot_vec)
                
                # Decompose rotational matrix to get angles
                angles, _, _, _, _, _ = cv2.RQDecomp3x3(rmat)
                
                # Calculate rotation degrees
                x_angle = angles[0] * 360
                y_angle = angles[1] * 360
                z_angle = angles[2] * 360
                return x_angle, y_angle, z_angle
        
        return None, None, None

    # show 
    def get_head_position(self):
        if self.face_detection_results.detections:
            for detection in self.face_detection_results.detections:
                bbox = detection.location_data.relative_bounding_box
                x = (bbox.width/2+bbox.xmin)
                y = (bbox.height/2+bbox.ymin)
                # x = bbox.width
                # y = bbox.height
                # x = bbox.xmin
                # y = bbox.ymin
                return {"x": x, "y":y}
                # return {
                #     "width":bbox.width,
                #     "height":bbox.height,
                #     "xmin" : bbox.xmin,
                #     "ymin": bbox.ymin,
                #     "result_x": (bbox.width/2+bbox.xmin),
                #     "result_y": (bbox.height/2+bbox.ymin)
                # }
                # return detection
        
        return None, None

    def get_depth_left_iris(self):
        img_h, img_w, _ = self.image.shape

        # focal_length = 800
        focal_length = 900
        real_iris_diameter = 1.17  
        #cm
        LEFT_IRIS = [474, 476]

        iris_left = {}
        
        if self.face_refine_face_mesh_results.multi_face_landmarks:
            iris_left[0] = self.face_refine_face_mesh_results.multi_face_landmarks[0].landmark[LEFT_IRIS[0]]
            iris_left[1] = self.face_refine_face_mesh_results.multi_face_landmarks[0].landmark[LEFT_IRIS[1]]
            
            image_iris_diameter_left = math.sqrt(pow(iris_left[0].x - iris_left[1].x,2)+pow(iris_left[0].y-iris_left[1].y,2))*img_w
            return (focal_length * real_iris_diameter) / image_iris_diameter_left   
        return None
    
    def get_depth_right_iris(self):
        img_h, img_w, _ = self.image.shape

        focal_length = cameraMatrix[0][0]
        # focal_length = 500
        real_iris_diameter = 1.17  
        #cm
        RIGHT_IRIS = [469, 471]

        iris_left = {}
        iris_right = {}
        
        if self.face_refine_face_mesh_results.multi_face_landmarks:
            iris_right[0] = self.face_refine_face_mesh_results.multi_face_landmarks[0].landmark[RIGHT_IRIS[0]]
            iris_right[1] = self.face_refine_face_mesh_results.multi_face_landmarks[0].landmark[RIGHT_IRIS[1]]
            
            image_iris_diameter_right = math.sqrt(pow(iris_right[0].x - iris_right[1].x,2)+pow(iris_right[0].y-iris_right[1].y,2))*img_w
            return (focal_length * real_iris_diameter) / image_iris_diameter_right 
        return None

    # show 
    def get_shoulder_position(self):
        # results = pose_landmark.process(image)
        if self.pose_landmark_result.pose_landmarks:
            shoulder_left = self.pose_landmark_result.pose_landmarks.landmark[12]
            shoulder_right = self.pose_landmark_result.pose_landmarks.landmark[11]
            shoulder_position = {"shoulder_left":{"x":shoulder_left.x,"y":shoulder_left.y,"z":shoulder_left.z},
                                 "shoulder_right":{"x":shoulder_right.x,"y":shoulder_right.y,"z":shoulder_right.z}}
            return shoulder_position 
        return None

    def get_chin(self):
        if self.face_refine_face_mesh_results.multi_face_landmarks:
            return self.face_refine_face_mesh_results.multi_face_landmarks[0].landmark[152]
        return None

    def get_blink_right(self):
        results = self.face_refine_face_mesh_results
        if results.multi_face_landmarks:
            dis_p2p6 = math.sqrt(pow(results.multi_face_landmarks[0].landmark[160].x-results.multi_face_landmarks[0].landmark[144].x,2)+pow(results.multi_face_landmarks[0].landmark[160].y-results.multi_face_landmarks[0].landmark[144].y,2))
            dis_p3p5 = math.sqrt(pow(results.multi_face_landmarks[0].landmark[158].x-results.multi_face_landmarks[0].landmark[153].x,2)+pow(results.multi_face_landmarks[0].landmark[158].y-results.multi_face_landmarks[0].landmark[153].y,2))
            dis_p1p4 = math.sqrt(pow(results.multi_face_landmarks[0].landmark[33].x-results.multi_face_landmarks[0].landmark[133].x,2)+pow(results.multi_face_landmarks[0].landmark[33].y-results.multi_face_landmarks[0].landmark[133].y,2))
            eAR = (dis_p2p6+dis_p3p5)/dis_p1p4
            return eAR
        return None

    def get_blink_left(self):
        results = self.face_refine_face_mesh_results
        if results.multi_face_landmarks:
            dis_p2p6 = math.sqrt(pow(results.multi_face_landmarks[0].landmark[385].x-results.multi_face_landmarks[0].landmark[380].x,2)+pow(results.multi_face_landmarks[0].landmark[385].y-results.multi_face_landmarks[0].landmark[380].y,2))
            dis_p3p5 = math.sqrt(pow(results.multi_face_landmarks[0].landmark[387].x-results.multi_face_landmarks[0].landmark[373].x,2)+pow(results.multi_face_landmarks[0].landmark[387].y-results.multi_face_landmarks[0].landmark[373].y,2))
            dis_p1p4 = math.sqrt(pow(results.multi_face_landmarks[0].landmark[362].x-results.multi_face_landmarks[0].landmark[263].x,2)+pow(results.multi_face_landmarks[0].landmark[362].y-results.multi_face_landmarks[0].landmark[263].y,2))
            eAR = (dis_p2p6+dis_p3p5)/dis_p1p4
            return eAR
        return None

    def get_feature(self):
        results = self.pose_landmark_result
        if results.pose_landmarks:
            py = abs(results.pose_landmarks.landmark[8].x - results.pose_landmarks.landmark[7].x )
            hl = (results.pose_landmarks.landmark[12].y+results.pose_landmarks.landmark[11].y)/2
            return {"py":py,
                    "hl":hl}
        return None


# image = cv2.imread("test.jpg")
# height, width, channels = image.shape
# test = detection(image)
# head_position = test.get_head_position()
# print(head_position['x'])
# x_min = np.int32(head_position['xmin']*width)
# x_max = np.int32(head_position['width']*width)
# y_min = np.int32(head_position['ymin']*height)
# y_max = np.int32(head_position['height']*height)
# x_result = np.int32(head_position['result_x']*width)
# y_result = np.int32(head_position['result_y']*height)
# face_react=[np.int32(head_position['xmin']*width),np.int32(head_position['ymin']*height),
#             np.int32(head_position['width']*width),np.int32(head_position['height']*height)]
# draw = cv2.circle(image,(np.int32(head_position['x']*width),np.int32(head_position['y']*height)),1,(0,0,255), -1)
# draw = cv2.rectangle(image, face_react, color=(255, 255, 255), thickness=2)
# draw = cv2.rectangle(image, [x_min,y_min,x_max,y_max], color=(255, 255, 255), thickness=2)
# draw = cv2.circle(image,[x_min,y_min],1,(0,0,255), -1)
# draw = cv2.circle(image,[x_result,y_result],1,(0,0,255), -1)

# tmp_x_min = np.int32(0.4*width)
# tmp_x_max = np.int32(0.6*width)
# tmp_y_min = np.int32(0.4*height)
# tmp_y_max = np.int32(0.6*height)
# draw = cv2.rectangle(image, [tmp_x_min,tmp_y_min,tmp_x_max,tmp_y_max], color=(255, 255, 255), thickness=2)
# draw = cv2.rectangle(image, [tmp_x_min,tmp_y_min],[tmp_x_max,tmp_y_max], color=(255, 255, 255), thickness=2)
# draw = cv2.circle(image,[tmp_x_min,tmp_y_min],1,(0,0,255), -1)
# draw = cv2.circle(image,[tmp_x_max,tmp_y_max],1,(0,0,255), -1)

# cv2.imshow('frame', draw) 
# cv2.waitKey(0) 
# cv2.destroyAllWindows() 

    
# print(" 1 : ",test.get_blink_left())
# print(" 2 : ",test.get_blink_right())
# print(" 3 : ",test.get_chin())
# print(" 4 : ",test.get_depth())
# print(" 5 : ",test.get_feature())
# print(" 6 : ",test.get_head_position())
# print(" 7 : ",test.get_rotation_degree())
# print(" 8 : ",test.get_shoulder_position())

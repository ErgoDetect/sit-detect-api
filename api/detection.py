import cv2
import mediapipe as mp
import numpy as np
import math

class detection:
    def __init__(self, image):
        mp_face_mesh = mp.solutions.face_mesh
        mp_face_detection = mp.solutions.face_detection
        mp_pose_landmark = mp.solutions.pose
        face_mesh = mp_face_mesh.FaceMesh(min_detection_confidence=0.5, min_tracking_confidence=0.5)
        refine_face_mesh = mp_face_mesh.FaceMesh(min_detection_confidence=0.5, min_tracking_confidence=0.5,refine_landmarks=True)
        face_detection = mp_face_detection.FaceDetection(model_selection=1, min_detection_confidence=0.5)
        pose_landmark = mp_pose_landmark.Pose(min_detection_confidence=0.5)
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

    def get_head_position(self):
        if self.face_detection_results.detections:
            for detection in self.face_detection_results.detections:
                bbox = detection.location_data.relative_bounding_box
                return bbox.xmin, bbox.ymin
        
        return None, None

    def get_depth(self):
        img_h, img_w, _ = self.image.shape

        LEFT_IRIS = [474, 476]
        RIGHT_IRIS = [469, 471]

        iris = {}
        i=0
        if self.face_refine_face_mesh_results.multi_face_landmarks:

            iris[0] = self.face_refine_face_mesh_results.multi_face_landmarks[0].landmark[LEFT_IRIS[0]]
            iris[1] = self.face_refine_face_mesh_results.multi_face_landmarks[0].landmark[LEFT_IRIS[1]]
            dx = iris[0].x - iris[1].x
            dX = 11.7
            
            dZ = (1 * (dX / dx))/10.0
            return dZ
        return None

    def get_shoulder_position(self):
        # results = pose_landmark.process(image)
        if self.pose_landmark_result.pose_landmarks:
            shoulder_position = { "shoulder_left": [self.pose_landmark_result.pose_landmarks.landmark[12].x,self.pose_landmark_result.pose_landmarks.landmark[12].y,self.pose_landmark_result.pose_landmarks.landmark[12].z],
                                "shoulder_right": [self.pose_landmark_result.pose_landmarks.landmark[11].x,self.pose_landmark_result.pose_landmarks.landmark[11].y,self.pose_landmark_result.pose_landmarks.landmark[11].z]}
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
            dis_p1p4 = math.sqrt(pow(results.multi_face_landmarks[0].landmark[362].x-results.multi_face_landmarks[0].landmark[263].x,2)+pow(results.multi_face_landmarks[0].landmark[362].y-results.multi_face_landmarks[0].landmark[268].y,2))
            eAR = (dis_p2p6+dis_p3p5)/dis_p1p4
            return eAR
        return None

    def get_feature(self):
        results = self.pose_landmark_result
        if results.pose_landmarks:
            py = abs(results.pose_landmarks.landmark[8].x - results.pose_landmarks.landmark[7].x )
            hl = (results.pose_landmarks.landmark[12].y+results.pose_landmarks.landmark[11].y)/2
            return [py,hl]
        return None

image = cv2.imread("test.jpg")
test = detection(image)


# print(" 1 : ",test.get_blink_left())
# print(" 2 : ",test.get_blink_right())
# print(" 3 : ",test.get_chin())
# print(" 4 : ",test.get_depth())
# print(" 5 : ",test.get_feature())
# print(" 6 : ",test.get_head_position())
# print(" 7 : ",test.get_rotation_degree())
# print(" 8 : ",test.get_shoulder_position())

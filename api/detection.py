import cv2
import mediapipe as mp
import numpy as np
import math

# Initialize Mediapipe solutions only once
mp_face_mesh = mp.solutions.face_mesh
mp_face_detection = mp.solutions.face_detection
mp_pose_landmark = mp.solutions.pose

face_mesh = mp_face_mesh.FaceMesh(min_detection_confidence=0.5, min_tracking_confidence=0.5)
refine_face_mesh = mp_face_mesh.FaceMesh(min_detection_confidence=0.5, min_tracking_confidence=0.5, refine_landmarks=True)
face_detection = mp_face_detection.FaceDetection(model_selection=1, min_detection_confidence=0.5)
pose_landmark = mp_pose_landmark.Pose(min_detection_confidence=0.5)


class detection:
    def __init__(self, image):
        if image is None:
            raise ValueError("No image provided")
        
        self.image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
        self.face_mesh_results = face_mesh.process(self.image)
        self.face_detection_results = face_detection.process(self.image)
        self.face_refine_face_mesh_results = refine_face_mesh.process(self.image)
        self.pose_landmark_result = pose_landmark.process(self.image)

    def get_rotation_degree(self):
        img_h, img_w, _ = self.image.shape

        face_3d = []
        face_2d = []

        if self.face_mesh_results.multi_face_landmarks:
            for face_landmarks in self.face_mesh_results.multi_face_landmarks:
                for idx in [33, 263, 1, 61, 291, 199]:
                    lm = face_landmarks.landmark[idx]
                    x, y = int(lm.x * img_w), int(lm.y * img_h)
                    face_2d.append([x, y])
                    face_3d.append([x, y, lm.z])

                face_2d = np.array(face_2d, dtype=np.float64)
                face_3d = np.array(face_3d, dtype=np.float64)

                focal_length = img_w
                cam_matrix = np.array([[focal_length, 0, img_h / 2],
                                       [0, focal_length, img_w / 2],
                                       [0, 0, 1]])

                dist_matrix = np.zeros((4, 1), dtype=np.float64)

                success, rot_vec, trans_vec = cv2.solvePnP(face_3d, face_2d, cam_matrix, dist_matrix)
                rmat, _ = cv2.Rodrigues(rot_vec)
                angles, _, _, _, _, _ = cv2.RQDecomp3x3(rmat)
                x_angle, y_angle, z_angle = angles * 360

                return x_angle, y_angle, z_angle

        return None, None, None

    def get_head_position(self):
        if self.face_detection_results.detections:
            bbox = self.face_detection_results.detections[0].location_data.relative_bounding_box
            return {"x": bbox.xmin, "y": bbox.ymin}
        return None, None

    def get_depth_iris(self, eye='left'):
        img_h, img_w, _ = self.image.shape
        focal_length = 800
        real_iris_diameter = 1.17
        IRIS_IDX = {'left': [474, 476], 'right': [469, 471]}

        if eye not in IRIS_IDX:
            raise ValueError("Invalid eye specified. Use 'left' or 'right'.")

        iris = {}

        if self.face_refine_face_mesh_results.multi_face_landmarks:
            landmarks = self.face_refine_face_mesh_results.multi_face_landmarks[0].landmark
            iris[0] = landmarks[IRIS_IDX[eye][0]]
            iris[1] = landmarks[IRIS_IDX[eye][1]]

            image_iris_diameter = math.sqrt(pow(iris[0].x - iris[1].x, 2) + pow(iris[0].y - iris[1].y, 2)) * img_w
            return (focal_length * real_iris_diameter) / image_iris_diameter

        return None

    def get_shoulder_position(self):
        if self.pose_landmark_result.pose_landmarks:
            landmarks = self.pose_landmark_result.pose_landmarks.landmark
            shoulder_position = {
                "shoulder_left": [landmarks[12].x, landmarks[12].y, landmarks[12].z],
                "shoulder_right": [landmarks[11].x, landmarks[11].y, landmarks[11].z]
            }
            return shoulder_position
        return None

    def get_chin(self):
        if self.face_refine_face_mesh_results.multi_face_landmarks:
            return self.face_refine_face_mesh_results.multi_face_landmarks[0].landmark[152]
        return None

    def get_blink_ratio(self, eye='left'):
        EYE_IDX = {'left': [33, 133, 362, 263, 385, 380, 387, 373],
                   'right': [33, 133, 362, 263, 160, 144, 158, 153]}

        if eye not in EYE_IDX:
            raise ValueError("Invalid eye specified. Use 'left' or 'right'.")

        if self.face_refine_face_mesh_results.multi_face_landmarks:
            landmarks = self.face_refine_face_mesh_results.multi_face_landmarks[0].landmark
            eye_idx = EYE_IDX[eye]
            dis_p2p6 = math.sqrt(pow(landmarks[eye_idx[4]].x - landmarks[eye_idx[5]].x, 2) +
                                 pow(landmarks[eye_idx[4]].y - landmarks[eye_idx[5]].y, 2))
            dis_p3p5 = math.sqrt(pow(landmarks[eye_idx[6]].x - landmarks[eye_idx[7]].x, 2) +
                                 pow(landmarks[eye_idx[6]].y - landmarks[eye_idx[7]].y, 2))
            dis_p1p4 = math.sqrt(pow(landmarks[eye_idx[0]].x - landmarks[eye_idx[1]].x, 2) +
                                 pow(landmarks[eye_idx[0]].y - landmarks[eye_idx[1]].y, 2))
            eAR = (dis_p2p6 + dis_p3p5) / dis_p1p4
            return eAR
        return None

    def get_feature(self):
        if self.pose_landmark_result.pose_landmarks:
            landmarks = self.pose_landmark_result.pose_landmarks.landmark
            py = abs(landmarks[8].x - landmarks[7].x)
            hl = (landmarks[12].y + landmarks[11].y) / 2
            return [py, hl]
        return None


# Example usage:
# image = cv2.imread("test.jpg")
# test = Detection(image)

# print(" 1 : ", test.get_blink_ratio('left'))
# print(" 2 : ", test.get_blink_ratio('right'))
# print(" 3 : ", test.get_chin())
# print(" 4 : ", test.get_depth_iris('left'))
# print(" 5 : ", test.get_feature())
# print(" 6 : ", test.get_head_position())
# print(" 7 : ", test.get_rotation_degree())
# print(" 8 : ", test.get_shoulder_position())

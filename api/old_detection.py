import cv2
import mediapipe as mp
import numpy as np
import math

class detection:
    def __init__(self):
        # Initialize MediaPipe solutions
        self.mp_face_mesh = mp.solutions.face_mesh
        self.mp_face_detection = mp.solutions.face_detection
        self.mp_pose_landmark = mp.solutions.pose

        # Initialize face mesh, face detection, and pose landmark with specific configurations
        self.face_mesh = self.mp_face_mesh.FaceMesh(min_detection_confidence=0.5, min_tracking_confidence=0.5)
        self.refine_face_mesh = self.mp_face_mesh.FaceMesh(min_detection_confidence=0.5, min_tracking_confidence=0.5, refine_landmarks=True)
        self.face_detection = self.mp_face_detection.FaceDetection(model_selection=1, min_detection_confidence=0.5)
        self.pose_landmark = self.mp_pose_landmark.Pose(min_detection_confidence=0.5)

    def process_image(self, image):
        # Convert image to RGB
        self.image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
        self.img_h, self.img_w, _ = self.image.shape

        # Process with all models
        self.face_mesh_results = self.face_mesh.process(self.image)
        self.refine_face_mesh_results = self.refine_face_mesh.process(self.image)
        self.face_detection_results = self.face_detection.process(self.image)
        self.pose_landmark_results = self.pose_landmark.process(self.image)

    def get_rotation_degree(self):
        face_3d, face_2d = [], []

        if self.face_mesh_results.multi_face_landmarks:
            for face_landmarks in self.face_mesh_results.multi_face_landmarks:
                for idx, lm in enumerate(face_landmarks.landmark):
                    if idx in [33, 263, 1, 61, 291, 199]:
                        x, y = int(lm.x * self.img_w), int(lm.y * self.img_h)
                        face_2d.append([x, y])
                        face_3d.append([x, y, lm.z])

            if face_2d and face_3d:
                face_2d = np.array(face_2d, dtype=np.float64)
                face_3d = np.array(face_3d, dtype=np.float64)

                focal_length = self.img_w
                cam_matrix = np.array([[focal_length, 0, self.img_h / 2],
                                       [0, focal_length, self.img_w / 2],
                                       [0, 0, 1]])
                dist_matrix = np.zeros((4, 1), dtype=np.float64)

                success, rot_vec, trans_vec = cv2.solvePnP(face_3d, face_2d, cam_matrix, dist_matrix)
                rmat, _ = cv2.Rodrigues(rot_vec)
                angles, _, _, _, _, _ = cv2.RQDecomp3x3(rmat)

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
        if self.refine_face_mesh_results.multi_face_landmarks:
            LEFT_IRIS = [474, 476]
            iris = {}
            iris[0] = self.refine_face_mesh_results.multi_face_landmarks[0].landmark[LEFT_IRIS[0]]
            iris[1] = self.refine_face_mesh_results.multi_face_landmarks[0].landmark[LEFT_IRIS[1]]
            dx = iris[0].x - iris[1].x
            dX = 1.17  # cm
            dZ = (1 * (dX / dx)) / 10.0  # depth in decimeters
            return dZ
        return None

    def get_shoulder_position(self):
        if self.pose_landmark_results.pose_landmarks:
            shoulder_position = {"shoulder_left": [self.pose_landmark_results.pose_landmarks.landmark[12].x, self.pose_landmark_results.pose_landmarks.landmark[12].y, self.pose_landmark_results.pose_landmarks.landmark[12].z],
                                 "shoulder_right": [self.pose_landmark_results.pose_landmarks.landmark[11].x, self.pose_landmark_results.pose_landmarks.landmark[11].y, self.pose_landmark_results.pose_landmarks.landmark[11].z]}
            return shoulder_position
        return None

    def get_chin(self):
        if self.refine_face_mesh_results.multi_face_landmarks:
            return self.refine_face_mesh_results.multi_face_landmarks[0].landmark[152]
        return None

    def get_blink_ratio(self, eye_landmarks):
        dis_p2p6 = math.sqrt(pow(eye_landmarks[0].x - eye_landmarks[1].x, 2) + pow(eye_landmarks[0].y - eye_landmarks[1].y, 2))
        dis_p3p5 = math.sqrt(pow(eye_landmarks[2].x - eye_landmarks[3].x, 2) + pow(eye_landmarks[2].y - eye_landmarks[3].y, 2))
        dis_p1p4 = math.sqrt(pow(eye_landmarks[4].x - eye_landmarks[5].x, 2) + pow(eye_landmarks[4].y - eye_landmarks[5].y, 2))
        return (dis_p2p6 + dis_p3p5) / dis_p1p4

    def get_blink_right(self):
        if self.refine_face_mesh_results.multi_face_landmarks:
            eye_landmarks = [self.refine_face_mesh_results.multi_face_landmarks[0].landmark[i] for i in [160, 144, 158, 153, 33, 133]]
            return self.get_blink_ratio(eye_landmarks)
        return None

    def get_blink_left(self):
        if self.refine_face_mesh_results.multi_face_landmarks:
            eye_landmarks = [self.refine_face_mesh_results.multi_face_landmarks[0].landmark[i] for i in [385, 380, 387, 373, 362, 263]]
            return self.get_blink_ratio(eye_landmarks)
        return None

    def get_feature(self):
        if self.pose_landmark_results.pose_landmarks:
            py = abs(self.pose_landmark_results.pose_landmarks.landmark[8].x - self.pose_landmark_results.pose_landmarks.landmark[7].x)
            hl = (self.pose_landmark_results.pose_landmarks.landmark[12].y + self.pose_landmark_results.pose_landmarks.landmark[11].y) / 2
            return [py, hl]
        return None

    def get_test(self):
        if self.refine_face_mesh_results.multi_face_landmarks:
            return [[self.refine_face_mesh_results.multi_face_landmarks[0].landmark[i] for i in [385, 380, 387, 373, 362, 263]]]
        return None

# Example usage
image = cv2.imread("test.jpg")
analyzer = FaceAnalyzer()
analyzer.process_image(image)

# Fetch different analyses
rotation_degrees = analyzer.get_rotation_degree()
head_position = analyzer.get_head_position()
depth = analyzer.get_depth()
shoulder_position = analyzer.get_shoulder_position()
chin = analyzer.get_chin()
blink_left = analyzer.get_blink_left()
blink_right = analyzer.get_blink_right()
feature = analyzer.get_feature()
test = analyzer.get_test()

# Print results
print("Rotation Degrees:", rotation_degrees)
print("Head Position:", head_position)
print("Depth:", depth)
print("Shoulder Position:", shoulder_position)
print("Chin:", chin)
print("Blink Left Ratio:", blink_left)
print("Blink Right Ratio:", blink_right)
print("Feature:", feature)
print("Test:", test)

import cv2
import mediapipe as mp
import numpy as np

# Initialize MediaPipe Face Mesh and Face Detection once and reuse them
mp_face_mesh = mp.solutions.face_mesh
mp_face_detection = mp.solutions.face_detection
mp_drawing = mp.solutions.drawing_utils

# Initialize face mesh and face detection with specific configurations
face_mesh = mp_face_mesh.FaceMesh(min_detection_confidence=0.5, min_tracking_confidence=0.5)
face_detection = mp_face_detection.FaceDetection(model_selection=1, min_detection_confidence=0.5)

# Drawing specifications
drawing_spec = mp_drawing.DrawingSpec(thickness=1, circle_radius=1)

def get_rotation_degree(image):
    # Convert image to RGB and flip horizontally
    image = cv2.cvtColor(cv2.flip(image, 1), cv2.COLOR_BGR2RGB)
    
    # Process the image with face mesh
    results = face_mesh.process(image)
    
    # Get image dimensions
    img_h, img_w, _ = image.shape
    
    # Prepare lists to store 2D and 3D points
    face_3d = []
    face_2d = []
    
    if results.multi_face_landmarks:
        for face_landmarks in results.multi_face_landmarks:
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

def get_head_position(image):
    # Convert image to RGB and flip horizontally
    image = cv2.cvtColor(cv2.flip(image, 1), cv2.COLOR_BGR2RGB)
    
    # Process the image with face detection
    results = face_detection.process(image)
    
    if results.detections:
        for detection in results.detections:
            bbox = detection.location_data.relative_bounding_box
            return bbox.xmin, bbox.ymin
    
    return None, None

# Example usage:
# image = cv2.imread("received_image.jpg")
# rotation_degrees = get_rotation_degree(image)
# head_position = get_head_position(image)
# print("Rotation Degrees:", rotation_degrees)
# print("Head Position:", head_position)

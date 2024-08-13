import numpy as np
import cv2 as cv
import json
import logging
from pathlib import Path
import math

logger = logging.getLogger(__name__)

def calibrate_camera(image_paths, resolution=(1920, 1080)):
    chessboard_size = (9, 6)
    size_of_chessboard_squares_mm = 20

    criteria = (cv.TERM_CRITERIA_EPS + cv.TERM_CRITERIA_MAX_ITER, 50, 0.001)

    # Prepare object points for a standard chessboard pattern
    objp = np.zeros((chessboard_size[0] * chessboard_size[1], 3), np.float32)
    objp[:, :2] = np.mgrid[0:chessboard_size[0], 0:chessboard_size[1]].T.reshape(-1, 2)
    objp *= size_of_chessboard_squares_mm

    objpoints = []  # 3D points in real-world space
    imgpoints = []  # 2D points in image plane

    output_dir = Path('images/calibrate')
    output_dir.mkdir(parents=True, exist_ok=True)

    frame_size = resolution  # Use the provided resolution for resizing images

    for image_path in image_paths:
        img = cv.imread(str(image_path))
        if img is None:
            logger.error(f"Failed to load image: {image_path}")
            continue

        gray = cv.cvtColor(img, cv.COLOR_BGR2GRAY)

        if img.shape[:2] != (frame_size[1], frame_size[0]):
            img = cv.resize(img, frame_size)
            gray = cv.resize(gray, frame_size)

        ret, corners = cv.findChessboardCorners(gray, chessboard_size, None)
        if ret:
            objpoints.append(objp)
            corners2 = cv.cornerSubPix(gray, corners, (11, 11), (-1, -1), criteria)
            imgpoints.append(corners2)

    if objpoints and imgpoints:
        ret, camera_matrix, dist, rvecs, tvecs = cv.calibrateCamera(objpoints, imgpoints, frame_size, None, None)

        # Adjust focal length
        camera_matrix[0, 0] = math.floor(camera_matrix[0, 0] / 2)
        camera_matrix[1, 1] = math.floor(camera_matrix[1, 1] / 2)
        logger.info(f"Adjusted focal length to: fx={camera_matrix[0, 0]}, fy={camera_matrix[1, 1]}")

        mean_error = calculate_reprojection_error(objpoints, imgpoints, rvecs, tvecs, camera_matrix, dist)

        result_dir = Path('calibrate_result')
        result_dir.mkdir(parents=True, exist_ok=True)

        calibration_data = {
            "cameraMatrix": camera_matrix.tolist(),
            "distCoeffs": dist.tolist(),
            "mean_error": mean_error
        }

        calibration_json_file = result_dir / "calibration_data.json"
        try:
            with open(calibration_json_file, 'w') as f:
                json.dump(calibration_data, f)
            logger.info(f"Calibration results saved to {calibration_json_file}")
            return calibration_json_file, mean_error
        except IOError as e:
            logger.error(f"Failed to save calibration data: {e}")
            return None, None
    else:
        logger.error("No valid images found for calibration.")
        return None, None

def calculate_reprojection_error(objpoints, imgpoints, rvecs, tvecs, camera_matrix, dist):
    total_error = 0
    for i in range(len(objpoints)):
        imgpoints2, _ = cv.projectPoints(objpoints[i], rvecs[i], tvecs[i], camera_matrix, dist)
        error = cv.norm(imgpoints[i], imgpoints2, cv.NORM_L2) / len(imgpoints2)
        total_error += error
    return total_error / len(objpoints)

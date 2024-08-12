import numpy as np
import cv2 as cv
import json
import logging
from pathlib import Path
import math

logger = logging.getLogger(__name__)

def calibrate_camera(image_paths, resolution=(1920, 1080)):
    chessboardSize = (9, 6)
    num = 0

    # Criteria for corner refinement
    criteria = (cv.TERM_CRITERIA_EPS + cv.TERM_CRITERIA_MAX_ITER, 50, 0.001)

    # Prepare object points for a standard chessboard pattern
    objp = np.zeros((chessboardSize[0] * chessboardSize[1], 3), np.float32)
    objp[:, :2] = np.mgrid[0:chessboardSize[0], 0:chessboardSize[1]].T.reshape(-1, 2)

    size_of_chessboard_squares_mm = 20
    objp *= size_of_chessboard_squares_mm

    # Arrays to store object points and image points from all images
    objpoints = []
    imgpoints = []

    # Output directories
    output_dir = Path('images/calibrate')
    output_dir.mkdir(parents=True, exist_ok=True)

    frameSize = resolution  # Define frameSize based on input resolution

    for image in image_paths:
        img = cv.imread(str(image))
        if img is None:
            logger.error(f"Failed to load image: {image}")
            continue

        gray = cv.cvtColor(img, cv.COLOR_BGR2GRAY)

        # Rescale image if necessary to match the resolution
        if img.shape[:2] != (frameSize[1], frameSize[0]):
            img = cv.resize(img, frameSize)
            gray = cv.resize(gray, frameSize)

        # Find chessboard corners
        ret, corners = cv.findChessboardCorners(gray, chessboardSize, None)

        if ret:
            objpoints.append(objp)
            corners2 = cv.cornerSubPix(gray, corners, (11, 11), (-1, -1), criteria)
            imgpoints.append(corners2)

    if frameSize is not None and len(objpoints) > 0:
        # Calibrate the camera
        ret, cameraMatrix, dist, rvecs, tvecs = cv.calibrateCamera(objpoints, imgpoints, frameSize, None, None)

        # Adjust focal length by dividing by 2 and flooring the result
        cameraMatrix[0, 0] = math.floor(cameraMatrix[0, 0] / 2)  # Focal length in x direction
        cameraMatrix[1, 1] = math.floor(cameraMatrix[1, 1] / 2)  # Focal length in y direction

        logger.info(f"Adjusted focal length to: fx={cameraMatrix[0, 0]}, fy={cameraMatrix[1, 1]}")

        # Calculate the reprojection error
        mean_error = calculate_reprojection_error(objpoints, imgpoints, rvecs, tvecs, cameraMatrix, dist)
        
        # Save calibration results to JSON
        result_dir = Path('calibrate_result')
        result_dir.mkdir(parents=True, exist_ok=True)

        calibration_data = {
            "cameraMatrix": cameraMatrix.tolist(),
            "distCoeffs": dist.tolist(),
            "mean_error": mean_error
        }

        calibration_json_file = result_dir / "calibration_data.json"
        with open(calibration_json_file, 'w') as f:
            json.dump(calibration_data, f)

        logger.info(f"Calibration results saved to {calibration_json_file}")

        return calibration_json_file, mean_error

    else:
        logger.error("No valid images found for calibration.")
        return None, None

def calculate_reprojection_error(objpoints, imgpoints, rvecs, tvecs, cameraMatrix, dist):
    total_error = 0
    for i in range(len(objpoints)):
        imgpoints2, _ = cv.projectPoints(objpoints[i], rvecs[i], tvecs[i], cameraMatrix, dist)
        error = cv.norm(imgpoints[i], imgpoints2, cv.NORM_L2) / len(imgpoints2)
        total_error += error
    return total_error / len(objpoints)

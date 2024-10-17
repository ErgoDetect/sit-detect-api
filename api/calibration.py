import numpy as np
import cv2 as cv
import json
import logging
from pathlib import Path

logger = logging.getLogger(__name__)


def calibrate_camera(image_paths, resolution=None):
    chessboard_size = (9, 6)
    size_of_chessboard_squares_mm = 20

    criteria = (cv.TERM_CRITERIA_EPS + cv.TERM_CRITERIA_MAX_ITER, 50, 0.001)

    # Prepare object points for a standard chessboard pattern
    objp = np.zeros((chessboard_size[0] * chessboard_size[1], 3), np.float32)
    objp[:, :2] = np.mgrid[0 : chessboard_size[0], 0 : chessboard_size[1]].T.reshape(
        -1, 2
    )
    objp *= size_of_chessboard_squares_mm

    objpoints, imgpoints = (
        [],
        [],
    )  # 3D points in real-world space, 2D points in image plane
    frame_size = None  # Will be set based on the first image

    for image_path in image_paths:
        img = cv.imread(str(image_path))
        if img is None:
            logger.error(f"Failed to load image: {image_path}")
            continue

        gray = cv.cvtColor(img, cv.COLOR_BGR2GRAY)

        if frame_size is None:
            frame_size = gray.shape[::-1]  # (width, height)
        elif gray.shape[::-1] != frame_size:
            logger.warning(f"Image {image_path} has a different size. Skipping.")
            continue

        ret, corners = cv.findChessboardCorners(gray, chessboard_size, None)
        if ret:
            objpoints.append(objp)
            corners2 = cv.cornerSubPix(gray, corners, (11, 11), (-1, -1), criteria)
            imgpoints.append(corners2)
        else:
            logger.warning(f"Chessboard not found in image: {image_path}")

    if not objpoints or not imgpoints:
        logger.error("No valid images found for calibration.")
        return None, None

    # Perform calibration
    ret, camera_matrix, dist_coeffs, rvecs, tvecs = cv.calibrateCamera(
        objpoints, imgpoints, frame_size, None, None
    )

    mean_error = calculate_reprojection_error(
        objpoints, imgpoints, rvecs, tvecs, camera_matrix, dist_coeffs
    )
    logger.info(f"Calibration successful with mean reprojection error: {mean_error}")

    # Save the calibration results
    result_dir = Path("calibrate_result")
    result_dir.mkdir(parents=True, exist_ok=True)
    calibration_data = {
        "cameraMatrix": camera_matrix.tolist(),
        "distCoeffs": dist_coeffs.tolist(),
        "mean_error": mean_error,
    }
    calibration_json_file = result_dir / "calibration_data.json"
    try:
        with open(calibration_json_file, "w") as f:
            json.dump(calibration_data, f)
        logger.info(f"Calibration results saved to {calibration_json_file}")
        return calibration_json_file, mean_error
    except IOError as e:
        logger.error(f"Failed to save calibration data: {e}")
        return None, None


def calculate_reprojection_error(
    objpoints, imgpoints, rvecs, tvecs, camera_matrix, dist_coeffs
):
    total_error, total_points = 0, 0

    for objp, imgp, rvec, tvec in zip(objpoints, imgpoints, rvecs, tvecs):
        imgpoints_proj, _ = cv.projectPoints(
            objp, rvec, tvec, camera_matrix, dist_coeffs
        )
        total_error += cv.norm(imgp, imgpoints_proj, cv.NORM_L2) ** 2
        total_points += len(imgpoints_proj)

    mean_error = np.sqrt(total_error / total_points)
    return mean_error

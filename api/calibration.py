import numpy as np
import cv2 as cv
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

CHESSBOARD_SIZE = (8, 5)
SQUARE_SIZE_MM = 20

# Constant Object Points
OBJP = np.zeros((CHESSBOARD_SIZE[0] * CHESSBOARD_SIZE[1], 3), np.float32)
OBJP[:, :2] = np.mgrid[0 : CHESSBOARD_SIZE[0], 0 : CHESSBOARD_SIZE[1]].T.reshape(-1, 2)
OBJP *= SQUARE_SIZE_MM

# Criteria for cornerSubPix
CRITERIA = (cv.TERM_CRITERIA_EPS + cv.TERM_CRITERIA_MAX_ITER, 50, 0.001)


def calibrate_camera(image_paths):
    objpoints, imgpoints = [], []
    frame_size, valid_images, skipped_images = None, 0, 0

    for image_path in image_paths:
        img = cv.imread(str(image_path))
        if img is None:
            logger.error(f"Failed to load image: {image_path}")
            continue

        gray = cv.cvtColor(img, cv.COLOR_BGR2GRAY)
        if frame_size is None:
            frame_size = gray.shape[::-1]
        elif gray.shape[::-1] != frame_size:
            logger.warning(f"Image {image_path} has a different size. Skipping.")
            skipped_images += 1
            continue

        # Find chessboard corners
        ret, corners = cv.findChessboardCorners(
            gray,
            CHESSBOARD_SIZE,
            flags=cv.CALIB_CB_ADAPTIVE_THRESH | cv.CALIB_CB_NORMALIZE_IMAGE,
        )
        if ret:
            objpoints.append(OBJP)
            corners2 = cv.cornerSubPix(gray, corners, (11, 11), (-1, -1), CRITERIA)
            imgpoints.append(corners2)
            valid_images += 1
        else:
            logger.warning(f"Chessboard not found in image: {image_path}")
            skipped_images += 1

    if not objpoints or not imgpoints:
        logger.error("No valid images found for calibration.")
        return None

    logger.info(
        f"Found chessboard in {valid_images} images; Skipped {skipped_images} images."
    )

    # Perform camera calibration
    ret, camera_matrix, dist_coeffs, rvecs, tvecs = cv.calibrateCamera(
        objpoints, imgpoints, frame_size, None, None
    )

    mean_error = calculate_reprojection_error(
        objpoints, imgpoints, rvecs, tvecs, camera_matrix, dist_coeffs
    )
    logger.info(
        f"Calibration successful with mean reprojection error: {mean_error:.4f}"
    )

    # Return calibration data directly
    calibration_data = {
        "cameraMatrix": camera_matrix.tolist(),
        "distCoeffs": dist_coeffs.tolist(),
        "mean_error": mean_error,
    }
    return calibration_data


def calculate_reprojection_error(
    objpoints, imgpoints, rvecs, tvecs, camera_matrix, dist_coeffs
):
    total_error, total_points = 0, 0

    for objp, imgp, rvec, tvec in zip(objpoints, imgpoints, rvecs, tvecs):
        imgpoints_proj, _ = cv.projectPoints(
            objp, rvec, tvec, camera_matrix, dist_coeffs
        )
        total_error += np.sum((imgp - imgpoints_proj) ** 2)
        total_points += len(imgpoints_proj)

    mean_error = np.sqrt(total_error / total_points)
    return mean_error

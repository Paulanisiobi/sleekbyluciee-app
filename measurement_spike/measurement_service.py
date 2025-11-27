import cv2
import numpy as np
import mediapipe as mp
from mediapipe.framework.formats import landmark_pb2

mp_pose = mp.solutions.pose
LANDMARKS = mp_pose.PoseLandmark


def landmarks_to_coords(landmarks, image_shape):
    h, w = image_shape[:2]
    coords = {}
    for i, lm in enumerate(landmarks.landmark):
        coords[i] = (lm.x * w, lm.y * h, lm.z)
    return coords


def distance(p1, p2):
    return float(np.linalg.norm(np.array(p1[:2]) - np.array(p2[:2])))


def estimate_from_front_landmarks(landmarks, image_shape, height_cm=None):
    coords = landmarks_to_coords(landmarks, image_shape)
    results = {}

    left_shoulder = coords.get(LANDMARKS.LEFT_SHOULDER.value)
    right_shoulder = coords.get(LANDMARKS.RIGHT_SHOULDER.value)
    left_hip = coords.get(LANDMARKS.LEFT_HIP.value)
    right_hip = coords.get(LANDMARKS.RIGHT_HIP.value)

    if left_shoulder and right_shoulder:
        shoulder_px = distance(left_shoulder, right_shoulder)
        results['shoulder_px'] = shoulder_px
    if left_hip and right_hip:
        hip_px = distance(left_hip, right_hip)
        results['hip_px'] = hip_px
    if left_shoulder and right_shoulder and left_hip and right_hip:
        sh_mid = ((left_shoulder[0] + right_shoulder[0]) / 2, (left_shoulder[1] + right_shoulder[1]) / 2)
        hip_mid = ((left_hip[0] + right_hip[0]) / 2, (left_hip[1] + right_hip[1]) / 2)
        torso_px = distance((sh_mid[0], sh_mid[1], 0), (hip_mid[0], hip_mid[1], 0))
        results['torso_px'] = torso_px

    if height_cm and 'torso_px' in results:
        # heuristic: torso ~ 33% of height
        px_per_cm = results['torso_px'] / (height_cm * 0.33)
        if 'shoulder_px' in results:
            results['shoulder_cm'] = round(results['shoulder_px'] / px_per_cm, 1)
        if 'hip_px' in results:
            results['hip_cm'] = round(results['hip_px'] / px_per_cm, 1)
        results['torso_cm'] = round(results['torso_px'] / px_per_cm, 1)

    found = sum(1 for k in [LANDMARKS.LEFT_SHOULDER.value, LANDMARKS.RIGHT_SHOULDER.value, LANDMARKS.LEFT_HIP.value, LANDMARKS.RIGHT_HIP.value] if k in coords)
    results['confidence'] = round(found / 4.0, 2)
    return results


def estimate_from_images(image_paths, height_cm=None):
    """Process one or more images and return combined measurement info.

    For MVP: process the first image with landmarks and return its estimates.
    Future: merge front+side estimates, return more measurements.
    """
    results = {}
    with mp_pose.Pose(static_image_mode=True, model_complexity=1) as pose:
        for p in image_paths:
            img = cv2.imread(p)
            if img is None:
                results[p] = {'error': 'file_not_found'}
                continue
            img_rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
            res = pose.process(img_rgb)
            if not res.pose_landmarks:
                results[p] = {'error': 'no_landmarks_detected'}
                continue
            est = estimate_from_front_landmarks(res.pose_landmarks, img.shape, height_cm)
            results[p] = est

    # Simple aggregation: return first successful estimate and overall confidence
    for p, val in results.items():
        if 'confidence' in val:
            return {'measurements': val, 'source': p}

    # if none succeeded, return aggregated errors
    return {'measurements': None, 'errors': results}

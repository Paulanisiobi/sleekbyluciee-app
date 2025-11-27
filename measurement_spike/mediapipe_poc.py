"""
MediaPipe POC for measurement estimation.

Usage:
  python mediapipe_poc.py --images front.jpg side.jpg --height 165

This script:
- Loads one or more images (front & optional side)
- Runs MediaPipe Pose to extract landmarks
- Computes simple distances (shoulder width, hip width, torso length) in pixel space
- If `--height` (cm) provided, scales normalized distances to centimeters
- Returns a JSON-like dict with measurements and confidence estimates

Note: This is a POC. Real production should use a calibrated pipeline, controlled capture UI, and proper ML model.
"""
import argparse
import json
import cv2
import numpy as np
import mediapipe as mp
from pathlib import Path

mp_pose = mp.solutions.pose

LANDMARKS = mp_pose.PoseLandmark


def load_image(path):
    img = cv2.imread(str(path))
    if img is None:
        raise FileNotFoundError(f"Image not found: {path}")
    return img


def extract_landmarks(image):
    with mp_pose.Pose(static_image_mode=True, model_complexity=1) as pose:
        image_rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
        results = pose.process(image_rgb)
        if not results.pose_landmarks:
            return None
        h, w = image.shape[:2]
        lm = results.pose_landmarks.landmark
+        # Convert to pixel coords
+        coords = {name: (int(l.x * w), int(l.y * h), l.z) for name, l in zip([str(lm_i) for lm_i in range(len(lm))], lm)}
        return results.pose_landmarks


def landmarks_to_coords(landmarks, image_shape):
    h, w = image_shape[:2]
    coords = {}
    for i, lm in enumerate(landmarks.landmark):
        coords[i] = (lm.x * w, lm.y * h, lm.z)
    return coords


def distance(p1, p2):
    return float(np.linalg.norm(np.array(p1[:2]) - np.array(p2[:2])))


def estimate_from_front(landmarks, image_shape, height_cm=None):
    coords = landmarks_to_coords(landmarks, image_shape)
    # key indices from MediaPipe Pose
    left_shoulder = coords.get(LANDMARKS.LEFT_SHOULDER.value)
    right_shoulder = coords.get(LANDMARKS.RIGHT_SHOULDER.value)
    left_hip = coords.get(LANDMARKS.LEFT_HIP.value)
    right_hip = coords.get(LANDMARKS.RIGHT_HIP.value)
    left_ear = coords.get(LANDMARKS.LEFT_EAR.value)
    right_ear = coords.get(LANDMARKS.RIGHT_EAR.value)

    results = {}
    if left_shoulder and right_shoulder:
        shoulder_px = distance(left_shoulder, right_shoulder)
        results['shoulder_px'] = shoulder_px
    if left_hip and right_hip:
        hip_px = distance(left_hip, right_hip)
        results['hip_px'] = hip_px
    # torso length approx shoulder midpoint to hip midpoint
    if left_shoulder and right_shoulder and left_hip and right_hip:
        sh_mid = ((left_shoulder[0] + right_shoulder[0]) / 2, (left_shoulder[1] + right_shoulder[1]) / 2)
        hip_mid = ((left_hip[0] + right_hip[0]) / 2, (left_hip[1] + right_hip[1]) / 2)
        torso_px = distance(sh_mid + (0,), hip_mid + (0,))
        results['torso_px'] = torso_px

    # Rough height in px: use ear/shoulder vs hip positions to approximate; better to ask user real height
    if height_cm and 'torso_px' in results:
        px_per_cm = results['torso_px'] / (height_cm * 0.33)  # assume torso ~33% of height
        # Convert px to cm
        if 'shoulder_px' in results:
            results['shoulder_cm'] = round(results['shoulder_px'] / px_per_cm, 1)
        if 'hip_px' in results:
            results['hip_cm'] = round(results['hip_px'] / px_per_cm, 1)
        results['torso_cm'] = round(results['torso_px'] / px_per_cm, 1)

    # Confidence heuristic: check how many key landmarks found
    found = sum(1 for k in [LANDMARKS.LEFT_SHOULDER.value, LANDMARKS.RIGHT_SHOULDER.value, LANDMARKS.LEFT_HIP.value, LANDMARKS.RIGHT_HIP.value] if k in coords)
    confidence = found / 4.0
    results['confidence'] = round(confidence, 2)
    return results


def main():
    parser = argparse.ArgumentParser(description='MediaPipe measurement POC')
    parser.add_argument('--images', nargs='+', required=True, help='Paths to images (front, optional side)')
    parser.add_argument('--height', type=float, default=None, help='User height in cm (optional)')
    args = parser.parse_args()

    outputs = {}
    for p in args.images:
        path = Path(p)
        img = load_image(path)
        with mp_pose.Pose(static_image_mode=True, model_complexity=1) as pose:
            img_rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
            res = pose.process(img_rgb)
            if not res.pose_landmarks:
                outputs[str(path)] = {'error': 'no_landmarks_detected'}
                continue
            est = estimate_from_front(res.pose_landmarks, img.shape, height_cm=args.height)
            outputs[str(path)] = est

    print(json.dumps({'measurements': outputs}, indent=2))


if __name__ == '__main__':
    main()

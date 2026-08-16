"""
Lightweight head-pose (yaw) estimation from 5-point facial keypoints.

WHY THIS EXISTS: InsightFace's detector reliably returns 5 keypoints
(left eye, right eye, nose, left mouth corner, right mouth corner) for
every model pack, but full 3D pose estimation depends on an optional
landmark_3d_68 sub-model that isn't guaranteed available/enabled in every
InsightFace install. Rather than make the whole CV pipeline depend on that
optional model, we estimate yaw geometrically from the 5 points everyone
gets. This is intentionally an approximation, not a precise Euler-angle
solvePnP result — sufficient for "is the face roughly frontal" (enrollment
quality) and "did the head turn noticeably" (liveness), which is all this
MVP needs. See docs/computer-vision.md for the full disclaimer.

Pitch/roll are not estimated by this heuristic (returned as 0.0) — nothing
in this codebase currently needs them.
"""

from cv.types import FacePose

# Empirical scale factor mapping the normalized nose-offset ratio to degrees.
# Not derived from a calibrated dataset — a reasonable approximation for a
# roughly frontal-facing webcam. Revisit if real-world testing shows the
# yaw estimate is consistently too sensitive or not sensitive enough.
_YAW_SCALE_DEGREES = 50.0


def estimate_yaw(keypoints: list[tuple[float, float]]) -> float:
    """
    keypoints: 5 (x, y) points in image order
        [left_eye, right_eye, nose, left_mouth, right_mouth]
    Returns an approximate yaw in degrees, computed from the RAW
    (unmirrored) camera frame. When the subject turns their head to their
    own right, the camera — facing them — sees their nose shift toward
    smaller x (image-left), which this function reports as NEGATIVE.
    Turning to the subject's own left produces POSITIVE. (This is the
    opposite of what you'd expect looking at the browser's mirrored
    preview — see cv/liveness.py for how this is accounted for.)
    """
    if len(keypoints) < 3:
        return 0.0

    left_eye, right_eye, nose = keypoints[0], keypoints[1], keypoints[2]

    eye_mid_x = (left_eye[0] + right_eye[0]) / 2.0
    eye_distance = abs(right_eye[0] - left_eye[0])
    if eye_distance < 1e-3:
        return 0.0

    offset = nose[0] - eye_mid_x
    ratio = offset / (eye_distance / 2.0)
    ratio = max(-2.0, min(2.0, ratio))  # clamp extreme/noisy geometry

    return ratio * _YAW_SCALE_DEGREES


def estimate_pose(keypoints: list[tuple[float, float]]) -> FacePose:
    return FacePose(yaw=estimate_yaw(keypoints), pitch=0.0, roll=0.0)

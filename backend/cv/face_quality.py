"""
Face quality evaluation.

Runs after detection, before recognition/enrollment ever touches the face.
Returns a QualityResult (cv/types.py) with a composite 0-1 score and a list
of specific issues, so the frontend can show one clear instruction rather
than a vague "quality too low" message.
"""

import cv2
import numpy as np

from cv.thresholds import get_thresholds
from cv.types import DetectedFace, QualityIssue, QualityResult


def _blur_variance(frame: np.ndarray, bbox: tuple[float, float, float, float]) -> float:
    x1, y1, x2, y2 = [int(v) for v in bbox]
    x1, y1 = max(0, x1), max(0, y1)
    x2, y2 = min(frame.shape[1], x2), min(frame.shape[0], y2)
    if x2 <= x1 or y2 <= y1:
        return 0.0
    crop = frame[y1:y2, x1:x2]
    gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
    return float(cv2.Laplacian(gray, cv2.CV_64F).var())


def _brightness(frame: np.ndarray, bbox: tuple[float, float, float, float]) -> float:
    x1, y1, x2, y2 = [int(v) for v in bbox]
    x1, y1 = max(0, x1), max(0, y1)
    x2, y2 = min(frame.shape[1], x2), min(frame.shape[0], y2)
    if x2 <= x1 or y2 <= y1:
        return 0.0
    crop = frame[y1:y2, x1:x2]
    gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
    return float(gray.mean())  # 0-255


def assess_quality(
    frame: np.ndarray,
    faces: list[DetectedFace],
    require_frontal: bool = False,
) -> QualityResult:
    """
    require_frontal: stricter pose check, used for enrollment (we want a
    clean frontal reference embedding). Recognition during attendance is
    more lenient since students won't always look dead-on at the camera.
    """
    thresholds = get_thresholds()
    issues: list[QualityIssue] = []

    if len(faces) == 0:
        return QualityResult(passed=False, score=0.0, issues=[QualityIssue.NO_FACE])
    if len(faces) > 1:
        return QualityResult(passed=False, score=0.0, issues=[QualityIssue.MULTIPLE_FACES])

    face = faces[0]
    frame_width = frame.shape[1]
    x1, y1, x2, y2 = face.bbox
    face_width = x2 - x1
    size_ratio = face_width / frame_width if frame_width else 0.0

    if size_ratio < thresholds.min_face_size_ratio:
        issues.append(QualityIssue.FACE_TOO_SMALL)

    blur_var = _blur_variance(frame, face.bbox)
    if blur_var < thresholds.max_blur_variance_floor:
        issues.append(QualityIssue.TOO_BLURRY)

    brightness = _brightness(frame, face.bbox)
    if brightness < 60:
        issues.append(QualityIssue.TOO_DARK)
    elif brightness > 210:
        issues.append(QualityIssue.TOO_BRIGHT)

    if require_frontal and face.pose is not None:
        if abs(face.pose.yaw) > thresholds.max_yaw_degrees_for_enrollment:
            issues.append(QualityIssue.NOT_FRONTAL)

    # Composite score: start at 1.0, subtract a penalty per issue found.
    # Simple and explainable on purpose (per spec: integrity/quality scores
    # must be explainable, not an opaque black box).
    penalty_per_issue = 0.25
    score = max(0.0, 1.0 - penalty_per_issue * len(issues))

    passed = len(issues) == 0 and score >= thresholds.min_face_quality_score
    return QualityResult(passed=passed, score=score, issues=issues)

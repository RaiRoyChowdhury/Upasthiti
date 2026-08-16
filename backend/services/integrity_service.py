"""
Integrity score service.

Produces an explainable 0-100 score from a fixed set of weighted factors.
This is NOT a scientific probability of anything — it's an internal
decision-support indicator, and the breakdown is returned alongside the
number specifically so nothing about it is opaque. See docs/attendance-engine.md.

Weights (sum to 100, chosen for this MVP — not derived from a calibrated
study, and documented as such):
    recognition confidence  40
    face quality            20
    liveness verified       25
    session validity        10
    not a duplicate          5
"""

from database.models.attendance_model import IntegrityBreakdown

_WEIGHT_RECOGNITION = 40
_WEIGHT_QUALITY = 20
_WEIGHT_LIVENESS = 25
_WEIGHT_SESSION = 10
_WEIGHT_DUPLICATE = 5


def _recognition_component(confidence: float) -> tuple[int, str]:
    if confidence >= 0.80:
        return _WEIGHT_RECOGNITION, "high"
    if confidence >= 0.60:
        return int(_WEIGHT_RECOGNITION * 0.7), "medium"
    return int(_WEIGHT_RECOGNITION * 0.4), "low"


def _quality_component(quality_score: float) -> tuple[int, str]:
    if quality_score >= 0.80:
        return _WEIGHT_QUALITY, "good"
    if quality_score >= 0.55:
        return int(_WEIGHT_QUALITY * 0.6), "fair"
    return int(_WEIGHT_QUALITY * 0.2), "poor"


def compute_integrity_score(
    recognition_confidence: float,
    face_quality_score: float,
    liveness_verified: bool,
    session_valid: bool,
    duplicate: bool,
) -> tuple[int, IntegrityBreakdown]:
    recognition_points, recognition_label = _recognition_component(recognition_confidence)
    quality_points, quality_label = _quality_component(face_quality_score)
    liveness_points = _WEIGHT_LIVENESS if liveness_verified else 0
    session_points = _WEIGHT_SESSION if session_valid else 0
    duplicate_points = 0 if duplicate else _WEIGHT_DUPLICATE

    total = recognition_points + quality_points + liveness_points + session_points + duplicate_points
    total = max(0, min(100, total))

    breakdown = IntegrityBreakdown(
        recognition=recognition_label,
        face_quality=quality_label,
        liveness="verified" if liveness_verified else "failed",
        session_valid=session_valid,
        duplicate=duplicate,
    )
    return total, breakdown

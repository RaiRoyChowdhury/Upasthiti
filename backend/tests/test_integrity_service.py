from services.integrity_service import compute_integrity_score


def test_high_confidence_verified_liveness_scores_high():
    score, breakdown = compute_integrity_score(
        recognition_confidence=0.92,
        face_quality_score=0.88,
        liveness_verified=True,
        session_valid=True,
        duplicate=False,
    )
    assert score >= 85
    assert breakdown.recognition == "high"
    assert breakdown.face_quality == "good"
    assert breakdown.liveness == "verified"
    assert breakdown.session_valid is True
    assert breakdown.duplicate is False


def test_failed_liveness_reduces_score_substantially():
    score_with, _ = compute_integrity_score(0.9, 0.9, True, True, False)
    score_without, breakdown = compute_integrity_score(0.9, 0.9, False, True, False)
    assert score_without < score_with
    assert breakdown.liveness == "failed"


def test_score_is_always_within_bounds():
    score, _ = compute_integrity_score(0.0, 0.0, False, False, True)
    assert 0 <= score <= 100

    score, _ = compute_integrity_score(1.0, 1.0, True, True, False)
    assert 0 <= score <= 100


def test_low_confidence_scores_lower_than_high_confidence():
    high_score, _ = compute_integrity_score(0.85, 0.8, True, True, False)
    low_score, _ = compute_integrity_score(0.62, 0.8, True, True, False)
    assert low_score < high_score

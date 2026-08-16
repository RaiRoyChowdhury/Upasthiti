import pytest

from services.analytics_math import (
    RiskLevel,
    classify_risk,
    forecast_attendance,
    required_classes_to_reach_target,
)


# ---- classify_risk ----

def test_classify_risk_safe_when_at_or_above_required():
    assert classify_risk(80, 75) == RiskLevel.SAFE
    assert classify_risk(75, 75) == RiskLevel.SAFE


def test_classify_risk_at_risk_within_margin():
    assert classify_risk(68, 75) == RiskLevel.AT_RISK  # 7 points below, margin is 10


def test_classify_risk_critical_beyond_margin():
    assert classify_risk(50, 75) == RiskLevel.CRITICAL  # 25 points below


# ---- required_classes_to_reach_target ----

def test_required_classes_zero_when_already_meeting_target():
    assert required_classes_to_reach_target(present_count=30, total_sessions=35, required_percent=75) == 0


def test_required_classes_matches_manual_algebra():
    # 20/40 = 50%, target 75%. Solve x: (20+x)/(40+x) >= 0.75
    # x >= (0.75*40 - 20) / (1 - 0.75) = (30-20)/0.25 = 40
    result = required_classes_to_reach_target(present_count=20, total_sessions=40, required_percent=75)
    assert result == 40
    # Verify it actually satisfies the target when applied
    assert (20 + result) / (40 + result) * 100 >= 75 - 1e-9


def test_required_classes_from_zero_history_needs_one_class():
    assert required_classes_to_reach_target(present_count=0, total_sessions=0, required_percent=75) == 1


def test_required_classes_from_zero_history_and_zero_required_needs_none():
    assert required_classes_to_reach_target(present_count=0, total_sessions=0, required_percent=0) == 0


def test_required_classes_rejects_present_exceeding_total():
    with pytest.raises(ValueError):
        required_classes_to_reach_target(present_count=10, total_sessions=5, required_percent=75)


def test_required_classes_rejects_negative_counts():
    with pytest.raises(ValueError):
        required_classes_to_reach_target(present_count=-1, total_sessions=5, required_percent=75)


# ---- forecast_attendance ----

def test_forecast_matches_manual_calculation():
    # 20/40 present, attend 10 more (out of 10 more classes)
    # (20+10)/(40+10) = 30/50 = 60%
    assert forecast_attendance(present_count=20, total_sessions=40, additional_classes_attended=10) == 60.0


def test_forecast_zero_additional_classes_returns_current_rate():
    assert forecast_attendance(present_count=15, total_sessions=20, additional_classes_attended=0) == 75.0


def test_forecast_with_no_history_and_no_additional_classes_is_zero():
    assert forecast_attendance(present_count=0, total_sessions=0, additional_classes_attended=0) == 0.0


def test_forecast_rejects_negative_additional_classes():
    with pytest.raises(ValueError):
        forecast_attendance(present_count=5, total_sessions=10, additional_classes_attended=-1)

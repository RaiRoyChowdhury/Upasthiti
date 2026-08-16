"""
Pure attendance-analytics math. No database access here on purpose — these
are exactly the functions spec section 33 warns must use "correct
mathematical logic" and "not simply approximate," so they're isolated and
directly unit-tested (tests/test_analytics_math.py) rather than buried
inside a DB-querying service method.
"""

import math
from enum import Enum


class RiskLevel(str, Enum):
    SAFE = "safe"
    AT_RISK = "at_risk"
    CRITICAL = "critical"


# How far below the required percentage counts as "at risk" rather than
# outright "critical". A chosen heuristic, not a derived/calibrated value —
# documented as such rather than presented as authoritative.
AT_RISK_MARGIN_POINTS = 10.0


def classify_risk(attendance_percent: float, required_percent: float) -> RiskLevel:
    if attendance_percent >= required_percent:
        return RiskLevel.SAFE
    if attendance_percent >= required_percent - AT_RISK_MARGIN_POINTS:
        return RiskLevel.AT_RISK
    return RiskLevel.CRITICAL


def required_classes_to_reach_target(
    present_count: int, total_sessions: int, required_percent: float
) -> int:
    """
    How many additional classes (assuming ALL of them are attended) does
    the student need to reach required_percent, starting from their
    current present_count/total_sessions?

    Solves: (present + x) / (total + x) >= required/100  for the smallest
    non-negative integer x. Real algebra, not a bracketed guess:

        present + x >= r*(total + x)          where r = required/100
        present + x >= r*total + r*x
        x - r*x >= r*total - present
        x*(1 - r) >= r*total - present
        x >= (r*total - present) / (1 - r)      [only valid when r < 1]

    If r >= 1 (100% required), it's only reachable if already perfect —
    return 0 if already at/above target, else effectively unreachable
    (returns a large sentinel handled by the caller as "not achievable").
    """
    if total_sessions < 0 or present_count < 0:
        raise ValueError("counts must be non-negative")
    if present_count > total_sessions:
        raise ValueError("present_count cannot exceed total_sessions")

    if total_sessions == 0:
        # No history yet — the ratio (present+x)/(0+x) is 100% for any x>=1
        # attended, so one attended class always reaches any target <=100%.
        # The general formula below divides 0/0 in this case, so it's
        # handled explicitly rather than trusted to fall out "naturally".
        return 1 if required_percent > 0 else 0

    r = required_percent / 100.0
    current = present_count / total_sessions * 100

    if current >= required_percent:
        return 0
    if r >= 1.0:
        return -1  # sentinel: mathematically unreachable once any absence exists

    x = (r * total_sessions - present_count) / (1 - r)
    return max(0, math.ceil(x - 1e-9))  # tiny epsilon guards float rounding at exact boundaries


def forecast_attendance(
    present_count: int, total_sessions: int, additional_classes_attended: int
) -> float:
    """
    "If you attend the next N classes, your attendance becomes X%" —
    assumes all N are attended AND all N count toward the denominator
    (i.e., N future sessions actually happen). A projection, not a
    guarantee — callers must present it as such (see spec section 34).
    """
    if additional_classes_attended < 0:
        raise ValueError("additional_classes_attended must be non-negative")
    new_total = total_sessions + additional_classes_attended
    if new_total == 0:
        return 0.0
    return round((present_count + additional_classes_attended) / new_total * 100, 1)

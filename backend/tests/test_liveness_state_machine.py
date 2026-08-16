import time

from cv.liveness import LivenessManager
from cv.thresholds import get_thresholds
from cv.types import FacePose, LivenessChallengeType, LivenessState


def _fresh_manager():
    # LivenessManager is a singleton by design (see cv/liveness.py docstring
    # on why: reused across requests in the real app). Tests reset its
    # internal session dict directly so each test starts clean.
    manager = LivenessManager()
    manager._sessions.clear()
    return manager


def test_challenge_starts_in_waiting_for_action():
    manager = _fresh_manager()
    session = manager.start_challenge("student_1", FacePose(yaw=0.0, pitch=0.0, roll=0.0))
    assert session.state == LivenessState.WAITING_FOR_ACTION
    assert session.challenge_type in (LivenessChallengeType.TURN_HEAD_LEFT, LivenessChallengeType.TURN_HEAD_RIGHT)


def test_sufficient_head_turn_verifies_liveness():
    manager = _fresh_manager()
    session = manager.start_challenge("student_1", FacePose(yaw=0.0, pitch=0.0, roll=0.0))
    thresholds = get_thresholds()

    # Correct real-world direction per cv/liveness.py's sign convention:
    # turning to the subject's own right produces a NEGATIVE yaw delta in
    # the raw (unmirrored) frame; turning left produces POSITIVE.
    correct_sign = -1 if session.challenge_type == LivenessChallengeType.TURN_HEAD_RIGHT else 1
    turned_yaw = correct_sign * (thresholds.liveness_yaw_delta_degrees + 5)

    updated = manager.process_frame(session.session_id, FacePose(yaw=turned_yaw, pitch=0.0, roll=0.0))
    assert updated.state == LivenessState.VERIFIED


def test_insufficient_head_turn_does_not_verify():
    manager = _fresh_manager()
    session = manager.start_challenge("student_1", FacePose(yaw=0.0, pitch=0.0, roll=0.0))

    # Tiny movement, well under the threshold
    updated = manager.process_frame(session.session_id, FacePose(yaw=1.0, pitch=0.0, roll=0.0))
    assert updated.state == LivenessState.WAITING_FOR_ACTION


def test_wrong_direction_turn_does_not_verify():
    manager = _fresh_manager()
    session = manager.start_challenge("student_1", FacePose(yaw=0.0, pitch=0.0, roll=0.0))
    thresholds = get_thresholds()

    # Turn the WRONG way relative to the challenge (using the correct
    # real-world sign convention — see cv/liveness.py)
    correct_sign = -1 if session.challenge_type == LivenessChallengeType.TURN_HEAD_RIGHT else 1
    wrong_yaw = -correct_sign * (thresholds.liveness_yaw_delta_degrees + 5)

    updated = manager.process_frame(session.session_id, FacePose(yaw=wrong_yaw, pitch=0.0, roll=0.0))
    assert updated.state == LivenessState.WAITING_FOR_ACTION


def test_expired_session_times_out():
    manager = _fresh_manager()
    session = manager.start_challenge("student_1", FacePose(yaw=0.0, pitch=0.0, roll=0.0))
    # Force expiry into the past rather than sleeping in a test.
    session.expires_at = time.time() - 1

    updated = manager.process_frame(session.session_id, FacePose(yaw=50.0, pitch=0.0, roll=0.0))
    assert updated.state == LivenessState.TIMEOUT


def test_unknown_session_id_returns_none():
    manager = _fresh_manager()
    assert manager.process_frame("does-not-exist", FacePose(yaw=0.0, pitch=0.0, roll=0.0)) is None


def test_verified_session_is_terminal():
    manager = _fresh_manager()
    session = manager.start_challenge("student_1", FacePose(yaw=0.0, pitch=0.0, roll=0.0))
    thresholds = get_thresholds()
    correct_sign = -1 if session.challenge_type == LivenessChallengeType.TURN_HEAD_RIGHT else 1
    turned_yaw = correct_sign * (thresholds.liveness_yaw_delta_degrees + 5)

    manager.process_frame(session.session_id, FacePose(yaw=turned_yaw, pitch=0.0, roll=0.0))
    # Further frames, even a face turned back to neutral, must not un-verify.
    updated = manager.process_frame(session.session_id, FacePose(yaw=0.0, pitch=0.0, roll=0.0))
    assert updated.state == LivenessState.VERIFIED

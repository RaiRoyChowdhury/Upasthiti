"""
Liveness verification — practical MVP-level heuristic, NOT certified
anti-spoofing (see docs/computer-vision.md for the full disclaimer, which
must be surfaced to users, not just left in code comments).

Mechanism: the student is asked to turn their head slightly left or right.
We record a baseline yaw from the first frame, then watch subsequent frames
for a sustained yaw change past a configured threshold within a timeout
window. This defeats a static printed photo or a phone held motionless; it
will NOT defeat a video replay or a moved photo, and that limitation is
explicit rather than hidden.

STATE MACHINE (per architectural requirement — not ad-hoc booleans):
    NOT_STARTED -> CHALLENGE_CREATED -> WAITING_FOR_ACTION
        -> ACTION_DETECTED -> VERIFIED
        -> (or) FAILED / TIMEOUT

STORAGE: in-memory, process-local, keyed by a random session id with a TTL.
This is an explicit MVP limitation: it does not survive a server restart
and does not work across multiple worker processes. Acceptable for a
single-instance hackathon/MVP deployment; documented as a scaling
limitation for anything beyond that (docs/computer-vision.md).
"""

import random
import threading
import time
import uuid
from dataclasses import dataclass

from cv.thresholds import get_thresholds
from cv.types import LIVENESS_CHALLENGE_PROMPTS, FacePose, LivenessChallengeType, LivenessState


@dataclass
class LivenessSession:
    session_id: str
    student_id: str
    challenge_type: LivenessChallengeType
    baseline_yaw: float
    state: LivenessState
    created_at: float
    expires_at: float
    verified_at: float | None = None

    @property
    def prompt(self) -> str:
        return LIVENESS_CHALLENGE_PROMPTS[self.challenge_type]


class LivenessManager:
    """Process-wide singleton holding active liveness sessions."""

    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._sessions: dict[str, LivenessSession] = {}
        return cls._instance

    def start_challenge(self, student_id: str, baseline_pose: FacePose) -> LivenessSession:
        thresholds = get_thresholds()
        self._evict_expired()

        challenge_type = random.choice(
            [LivenessChallengeType.TURN_HEAD_LEFT, LivenessChallengeType.TURN_HEAD_RIGHT]
        )
        now = time.time()
        session = LivenessSession(
            session_id=str(uuid.uuid4()),
            student_id=student_id,
            challenge_type=challenge_type,
            baseline_yaw=baseline_pose.yaw,
            state=LivenessState.WAITING_FOR_ACTION,
            created_at=now,
            expires_at=now + thresholds.liveness_timeout_seconds,
        )
        with self._lock:
            self._sessions[session.session_id] = session
        return session

    def get(self, session_id: str) -> LivenessSession | None:
        return self._sessions.get(session_id)

    def process_frame(self, session_id: str, current_pose: FacePose | None) -> LivenessSession | None:
        thresholds = get_thresholds()
        session = self._sessions.get(session_id)
        if session is None:
            return None

        if session.state in (LivenessState.VERIFIED, LivenessState.FAILED, LivenessState.TIMEOUT):
            return session  # terminal state — no further transitions

        now = time.time()
        if now > session.expires_at:
            session.state = LivenessState.TIMEOUT
            return session

        if current_pose is None:
            # No face this frame — stay in WAITING_FOR_ACTION, don't fail
            # outright on a single dropped frame (webcam frames are noisy).
            return session

        delta = current_pose.yaw - session.baseline_yaw
        # Sign convention: the backend works from the RAW, unmirrored camera
        # frame (the browser's mirrored preview is a display-only CSS
        # transform — see js/overlay.js). When a person turns their head to
        # THEIR OWN right, the camera — facing them, like another person
        # would see them — captures their nose shifting toward smaller x
        # (image-left), producing a NEGATIVE yaw delta in pose_estimation.py's
        # convention. So "turn right" must check for a negative delta, and
        # "turn left" a positive one — the reverse of what's intuitive if you
        # think in terms of the mirrored preview instead of the raw frame.
        expected_sign = -1 if session.challenge_type == LivenessChallengeType.TURN_HEAD_RIGHT else 1
        moved_enough = (delta * expected_sign) >= thresholds.liveness_yaw_delta_degrees

        if moved_enough:
            session.state = LivenessState.VERIFIED
            session.verified_at = now

        return session

    def _evict_expired(self) -> None:
        now = time.time()
        with self._lock:
            expired = [sid for sid, s in self._sessions.items() if now > s.expires_at + 30]
            for sid in expired:
                del self._sessions[sid]

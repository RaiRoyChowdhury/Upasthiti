"""
Prevents recognize_face (polled ~every 1.3s while a face is in frame) from
creating a new review event on every single tick for the same lingering
low-confidence/unknown face. Reuses RECOGNITION_COOLDOWN_SECONDS — the
same "don't repeat processing for a face that hasn't left frame" concept
already used for attendance-marking cooldown, applied here to review-event
creation. Process-local, same pattern/limitation as LivenessManager and
ConnectionManager (see docs/computer-vision.md, docs/websocket.md).
"""

import threading
import time

from config.settings import get_settings


class ReviewDedupTracker:
    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._last_seen: dict[str, float] = {}
        return cls._instance

    def should_create(self, key: str) -> bool:
        settings = get_settings()
        now = time.time()
        last = self._last_seen.get(key)
        self._last_seen[key] = now
        return last is None or (now - last) > settings.RECOGNITION_COOLDOWN_SECONDS

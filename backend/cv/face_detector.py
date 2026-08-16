"""
Face detection, wrapping InsightFace's FaceAnalysis app.

MODEL LIFECYCLE (per architectural requirement — do not reload per request):
  The FaceAnalysis app is expensive to construct (loads several ONNX models
  from disk). It is initialized exactly once per process, on first use, and
  reused for every subsequent detection call. See FaceModelSingleton below.

This module returns DetectedFace objects (cv/types.py) — plain data, no
InsightFace types leak past this boundary, so the rest of the app doesn't
need to know InsightFace exists.
"""

import threading

import numpy as np

from config.settings import get_settings
from cv.pose_estimation import estimate_pose
from cv.types import DetectedFace
from utils.logger import get_logger

logger = get_logger(__name__)

_lock = threading.Lock()


class FaceModelSingleton:
    """
    Lazy, thread-safe, process-wide singleton around InsightFace's
    FaceAnalysis app. FastAPI can serve requests from multiple threads
    (sync dependencies) even in a single worker process, hence the lock
    around first-time initialization.
    """

    _instance = None

    def __new__(cls):
        if cls._instance is None:
            with _lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._app = None
        return cls._instance

    def get_app(self):
        if self._app is None:
            with _lock:
                if self._app is None:
                    self._app = self._load_app()
        return self._app

    @staticmethod
    def _load_app():
        # Imported lazily so the rest of the app (and its test suite) can
        # run without insightface/onnxruntime installed if CV endpoints
        # simply aren't exercised.
        from insightface.app import FaceAnalysis

        settings = get_settings()

        # Enforce CPU execution for cloud deployment (prevents CUDA driver lookups)
        providers = ["CPUExecutionProvider"]

        # Override heavy model pack 'buffalo_l' with 'buffalo_sc' to stay under 512MB RAM limit
        configured_pack = getattr(settings, "INSIGHTFACE_MODEL_PACK", "buffalo_sc")
        model_pack = "buffalo_sc" if configured_pack == "buffalo_l" else configured_pack

        logger.info(
            "Loading InsightFace model pack '%s' (providers=%s)... this happens once per process.",
            model_pack,
            providers,
        )
        app = FaceAnalysis(
            name=model_pack,
            providers=providers,
        )

        # ctx_id=-1 explicitly forces CPU execution (ctx_id=0 targets CUDA GPU)
        det_size = getattr(settings, "INSIGHTFACE_DET_SIZE", 640)
        app.prepare(ctx_id=-1, det_size=(det_size, det_size))

        logger.info("InsightFace model pack loaded and ready.")
        return app


def detect_faces(frame: np.ndarray, with_embedding: bool = False) -> list[DetectedFace]:
    """
    Runs detection (+ optionally recognition embedding extraction, which
    InsightFace's FaceAnalysis app computes in the same forward pass) on a
    single BGR frame. Returns detections sorted by detector confidence,
    highest first.
    """
    app = FaceModelSingleton().get_app()
    faces = app.get(frame)

    results: list[DetectedFace] = []
    for face in faces:
        bbox = tuple(float(v) for v in face.bbox)  # x1, y1, x2, y2
        kps = [(float(x), float(y)) for x, y in face.kps] if face.kps is not None else []
        pose = estimate_pose(kps) if kps else None

        embedding = None
        if with_embedding and getattr(face, "normed_embedding", None) is not None:
            embedding = [float(v) for v in face.normed_embedding]

        results.append(
            DetectedFace(
                bbox=bbox,
                det_score=float(face.det_score),
                pose=pose,
                embedding=embedding,
            )
        )

    results.sort(key=lambda f: f.det_score, reverse=True)
    return results
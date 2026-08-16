"""
High-level single-frame extraction pipeline: detect -> quality -> embedding.

Both enrollment and recognition need exactly this sequence, so it lives in
one place rather than being duplicated in two services. Neither caller path
touches InsightFace or OpenCV APIs directly — they work with the
FaceExtraction result below.
"""

from dataclasses import dataclass

import numpy as np

from cv.face_detector import detect_faces
from cv.face_quality import assess_quality
from cv.types import DetectedFace, QualityResult


@dataclass
class FaceExtraction:
    faces_found: int
    quality: QualityResult
    face: DetectedFace | None  # populated only when exactly one face passed quality


def extract_single_face(frame: np.ndarray, require_frontal: bool) -> FaceExtraction:
    """
    Runs detection with embedding extraction enabled, then quality checks.
    `face` is only set when there was exactly one detected face — even if
    quality failed, so callers can still show e.g. a bounding box overlay
    for a too-blurry face if they want to (Phase 2/3 doesn't use this, but
    the data is there for future UI polish).
    """
    faces = detect_faces(frame, with_embedding=True)
    quality = assess_quality(frame, faces, require_frontal=require_frontal)

    face = faces[0] if len(faces) == 1 else None
    return FaceExtraction(faces_found=len(faces), quality=quality, face=face)


@dataclass
class MultiFaceEntry:
    face: DetectedFace
    quality: QualityResult


def extract_all_faces(frame: np.ndarray) -> list[MultiFaceEntry]:
    """
    Phase 9 addition — detects and quality-checks EVERY face in a frame,
    rather than rejecting outright when more than one is present (which is
    still exactly what extract_single_face()/the existing attendance flow
    does, unchanged). Used only by the new multi-face recognition endpoint
    (informational "who's in frame" scanning), never by the attendance-
    marking pipeline — see docs/multi-face.md for why those stay separate.
    """
    faces = detect_faces(frame, with_embedding=True)
    entries = []
    for face in faces:
        quality = assess_quality(frame, [face], require_frontal=False)
        entries.append(MultiFaceEntry(face=face, quality=quality))
    return entries

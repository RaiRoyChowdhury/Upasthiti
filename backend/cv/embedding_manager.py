"""
Embedding comparison utilities.

Deliberately pure functions with no DB access — recognition_service.py
loads enrolled embeddings via the repository layer and passes them in here.
This keeps the CV layer testable with synthetic vectors (per spec: CV
algorithm tests should not require a real model or database).
"""

import numpy as np


def cosine_similarity(a: list[float], b: list[float]) -> float:
    va = np.array(a, dtype=np.float32)
    vb = np.array(b, dtype=np.float32)
    denom = np.linalg.norm(va) * np.linalg.norm(vb)
    if denom == 0:
        return 0.0
    # InsightFace's normed_embedding is already unit-length, but we don't
    # assume that here — callers may pass any embedding source in future.
    return float(np.dot(va, vb) / denom)


def best_match(
    probe_embedding: list[float],
    candidates: list[tuple[str, list[float]]],
) -> tuple[str | None, float]:
    """
    candidates: list of (student_id, embedding) pairs, e.g. loaded from
    every enrolled FaceProfile.

    Returns (best_student_id, best_score). best_student_id is None if
    candidates is empty — caller decides what that means (e.g. UNKNOWN).
    """
    best_id: str | None = None
    best_score = -1.0

    for student_id, embedding in candidates:
        score = cosine_similarity(probe_embedding, embedding)
        if score > best_score:
            best_score = score
            best_id = student_id

    if best_id is None:
        return None, 0.0
    return best_id, best_score

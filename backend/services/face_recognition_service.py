"""
Face recognition service.

Ties together the CV layer (cv/face_recognizer.py, cv/embedding_manager.py)
and the biometric repository to answer: "who, if anyone, is this?" — never
more permissive than the configured thresholds, and never guesses when
unsure (per spec: DO NOT choose the closest student automatically if
confidence is insufficient).
"""

from cv.embedding_manager import best_match, cosine_similarity
from cv.face_recognizer import extract_all_faces, extract_single_face
from cv.preprocessing import decode_base64_image
from cv.thresholds import get_thresholds
from cv.types import RecognitionOutcome, RecognitionResult
from database.repositories.face_profile_repository import FaceProfileRepository
from services.audit_service import AuditService
from utils.logger import get_logger

logger = get_logger(__name__)


class FaceRecognitionService:
    def __init__(self, face_profile_repo: FaceProfileRepository, audit_service: AuditService):
        self._face_profiles = face_profile_repo
        self._audit = audit_service

    async def recognize(self, image_base64: str) -> RecognitionResult:
        frame = decode_base64_image(image_base64)
        extraction = extract_single_face(frame, require_frontal=False)

        if extraction.faces_found == 0:
            return RecognitionResult(outcome=RecognitionOutcome.NO_FACE)
        if extraction.faces_found > 1:
            return RecognitionResult(outcome=RecognitionOutcome.MULTIPLE_FACES)

        if not extraction.quality.passed:
            return RecognitionResult(
                outcome=RecognitionOutcome.POOR_QUALITY,
                quality=extraction.quality,
                bbox=extraction.face.bbox if extraction.face else None,
            )

        face = extraction.face
        if face is None or face.embedding is None:
            return RecognitionResult(outcome=RecognitionOutcome.POOR_QUALITY, quality=extraction.quality)

        candidates = await self._face_profiles.list_all_embeddings()
        if not candidates:
            # No one is enrolled yet — everyone is, correctly, unknown.
            return RecognitionResult(
                outcome=RecognitionOutcome.UNKNOWN,
                quality=extraction.quality,
                pose=face.pose,
                bbox=face.bbox,
            )

        student_id, score = best_match(face.embedding, candidates)
        thresholds = get_thresholds()

        if student_id is None or score < thresholds.low_confidence:
            outcome = RecognitionOutcome.UNKNOWN
        elif score < thresholds.face_recognition:
            outcome = RecognitionOutcome.LOW_CONFIDENCE
        else:
            outcome = RecognitionOutcome.KNOWN

        return RecognitionResult(
            outcome=outcome,
            student_id=student_id if outcome in (RecognitionOutcome.KNOWN, RecognitionOutcome.LOW_CONFIDENCE) else None,
            confidence=round(float(score), 4),
            quality=extraction.quality,
            pose=face.pose,
            bbox=face.bbox,
        )

    async def recognize_all_faces(self, image_base64: str) -> list[RecognitionResult]:
        """
        Phase 9 — recognizes EVERY face in the frame, not just a single
        one. Informational/monitoring use only (e.g. "who's currently in
        the room" scanning) — this method is never called from the
        attendance-marking pipeline, which still requires exactly one
        face + a completed liveness challenge per student (see
        docs/multi-face.md). Faces that fail their own quality check are
        still returned with outcome POOR_QUALITY rather than dropped
        silently, so the UI can show "poor quality" for that one face
        without hiding the others.
        """
        frame = decode_base64_image(image_base64)
        entries = extract_all_faces(frame)
        if not entries:
            return []

        candidates = await self._face_profiles.list_all_embeddings()
        thresholds = get_thresholds()
        results: list[RecognitionResult] = []

        for entry in entries:
            if not entry.quality.passed:
                results.append(
                    RecognitionResult(
                        outcome=RecognitionOutcome.POOR_QUALITY,
                        quality=entry.quality,
                        pose=entry.face.pose,
                        bbox=entry.face.bbox,
                    )
                )
                continue

            if entry.face.embedding is None or not candidates:
                results.append(
                    RecognitionResult(
                        outcome=RecognitionOutcome.UNKNOWN,
                        quality=entry.quality,
                        pose=entry.face.pose,
                        bbox=entry.face.bbox,
                    )
                )
                continue

            student_id, score = best_match(entry.face.embedding, candidates)
            if student_id is None or score < thresholds.low_confidence:
                outcome = RecognitionOutcome.UNKNOWN
            elif score < thresholds.face_recognition:
                outcome = RecognitionOutcome.LOW_CONFIDENCE
            else:
                outcome = RecognitionOutcome.KNOWN

            results.append(
                RecognitionResult(
                    outcome=outcome,
                    student_id=student_id if outcome in (RecognitionOutcome.KNOWN, RecognitionOutcome.LOW_CONFIDENCE) else None,
                    confidence=round(float(score), 4),
                    quality=entry.quality,
                    pose=entry.face.pose,
                    bbox=entry.face.bbox,
                )
            )

        return results

    async def calibration_scores(self, image_base64: str, top_n: int = 5) -> list[dict]:
        """
        Phase 9 calibration tooling — returns the TOP N similarity scores
        against every enrolled student for a single captured frame,
        rather than only the classified KNOWN/UNKNOWN/LOW_CONFIDENCE
        outcome. Lets an admin see the actual score distribution (how far
        apart the genuine match is from the next-closest impostor score)
        instead of tuning FACE_RECOGNITION_THRESHOLD blind — see
        docs/multi-face.md "Calibration tooling".
        """
        frame = decode_base64_image(image_base64)
        extraction = extract_single_face(frame, require_frontal=False)
        if extraction.face is None or extraction.face.embedding is None:
            return []

        candidates = await self._face_profiles.list_all_embeddings()
        scored = [
            {"student_id": sid, "similarity": round(float(cosine_similarity(extraction.face.embedding, emb)), 4)}
            for sid, emb in candidates
        ]
        scored.sort(key=lambda x: x["similarity"], reverse=True)
        return scored[:top_n]

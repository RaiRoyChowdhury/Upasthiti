from cv.face_detector import detect_faces
from cv.liveness import LivenessManager, LivenessSession
from cv.preprocessing import decode_base64_image
from cv.types import LivenessState
from utils.exceptions import ValidationAppError


class LivenessService:
    def __init__(self):
        self._manager = LivenessManager()

    async def start(self, student_id: str, image_base64: str) -> LivenessSession:
        frame = decode_base64_image(image_base64)
        faces = detect_faces(frame, with_embedding=False)
        if len(faces) != 1 or faces[0].pose is None:
            raise ValidationAppError(
                "Need a single, clearly visible face to start a liveness check.",
                code="LIVENESS_START_NO_FACE",
            )
        return self._manager.start_challenge(student_id, faces[0].pose)

    async def check(self, session_id: str, image_base64: str) -> LivenessSession:
        frame = decode_base64_image(image_base64)
        faces = detect_faces(frame, with_embedding=False)
        pose = faces[0].pose if len(faces) == 1 else None

        session = self._manager.process_frame(session_id, pose)
        if session is None:
            raise ValidationAppError("Liveness session not found or expired.", code="LIVENESS_SESSION_NOT_FOUND")
        return session

    def get(self, session_id: str) -> LivenessSession | None:
        return self._manager.get(session_id)

    @staticmethod
    def is_verified(session: LivenessSession) -> bool:
        return session.state == LivenessState.VERIFIED

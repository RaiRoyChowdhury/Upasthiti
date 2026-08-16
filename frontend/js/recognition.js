/**
 * Thin wrapper around the recognition/liveness API endpoints.
 * No decisions live here — just typed calls that attendance.js orchestrates.
 */

const Recognition = {
  /**
   * @param {string} imageBase64
   * @param {string} [sessionId] Attendance session — passed through ONLY so
   *   the backend can route a real-time WebSocket event. Omit it and this
   *   behaves exactly as it did before Phase 4 (no event, same recognition
   *   result). See docs/websocket.md "Fallback behavior".
   */
  recognize(imageBase64, sessionId) {
    return Api.post("/api/face/recognize", { image_base64: imageBase64, session_id: sessionId || null });
  },

  startLiveness(studentId, imageBase64, sessionId) {
    return Api.post("/api/face/liveness/start", {
      student_id: studentId,
      image_base64: imageBase64,
      session_id: sessionId || null,
    });
  },

  checkLiveness(livenessSessionId, imageBase64, attendanceSessionId) {
    return Api.post("/api/face/liveness/check", {
      session_id: livenessSessionId,
      image_base64: imageBase64,
      attendance_session_id: attendanceSessionId || null,
    });
  },

  async findStudentName(studentId) {
    try {
      const data = await Api.get(`/api/students?search=${encodeURIComponent(studentId)}&limit=5`);
      const match = data.items.find((s) => s.student_id === studentId);
      return match ? match.name : studentId;
    } catch (_) {
      return studentId;
    }
  },
};

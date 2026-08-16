/**
 * Enrollment page controller.
 *
 * State machine (per spec section 8):
 *   CAMERA_READY -> CAPTURING -> PROCESSING -> ENROLLMENT_SUCCESSFUL | ENROLLMENT_FAILED
 *
 * All quality/embedding decisions happen server-side (POST .../enrollment).
 * This file's job is just: get a frame, send it, show the server's answer.
 */

const params = new URLSearchParams(window.location.search);
const studentId = params.get("student_id");
const studentName = params.get("name") || studentId;

let capturing = false;

document.addEventListener("DOMContentLoaded", async () => {
  console.log("[CAMERA] enrollment page DOMContentLoaded, studentId =", studentId);

  if (!Api.isAuthenticated()) {
    window.location.href = "login.html";
    return;
  }
  if (!studentId) {
    // Previously this returned silently (no console signal, no visible
    // alert) — camera initialization never ran and there was nothing on
    // screen loud enough to explain why. Now it's an explicit, visible
    // error using the same alert box every other failure on this page uses.
    console.error("[CAMERA] no student_id in URL — camera initialization skipped");
    document.getElementById("enrollment-target").textContent = "No student selected.";
    document.getElementById("capture-btn").disabled = true;
    setStatus(
      "error",
      "No student was selected for enrollment. Go back to Students and click \"Enroll Face\" on a specific student — this page needs a student_id in the URL."
    );
    return;
  }

  document.getElementById("enrollment-target").textContent = studentName;

  try {
    const user = await Api.get("/api/auth/me");
    document.getElementById("user-name").textContent = user.name;
    document.getElementById("user-role").textContent = user.role;
  } catch (_) {}

  document.getElementById("logout-btn").addEventListener("click", async () => {
    try { await Api.post("/api/auth/logout", {}); } catch (_) {}
    Api.clearSession();
    window.location.href = "login.html";
  });

  const videoEl = document.getElementById("camera-video");
  console.log("[CAMERA] about to call Camera.start()", videoEl);
  try {
    await Camera.start(videoEl);
    setStatus("ready", "Camera ready. Position the face in frame and capture.");
  } catch (err) {
    console.error("[CAMERA] Camera.start() rejected", err);
    setStatus("error", err.message);
  }

  document.getElementById("capture-btn").addEventListener("click", onCapture);
});

window.addEventListener("beforeunload", () => Camera.stop());

function setStatus(state, message) {
  const el = document.getElementById("status-message");
  el.textContent = message;
  el.className = `alert alert-${state === "error" ? "danger" : state === "success" ? "success" : "info"}`;
  el.classList.remove("hidden");
}

async function onCapture() {
  if (capturing) return;
  capturing = true;

  const btn = document.getElementById("capture-btn");
  btn.disabled = true;
  btn.innerHTML = '<span class="spinner"></span> Processing...';
  setStatus("info", "Analyzing face quality...");

  const frame = Camera.captureFrameBase64();
  if (!frame) {
    setStatus("error", "Could not capture a frame. Is the camera running?");
    resetButton();
    return;
  }

  try {
    const result = await Api.post(`/api/students/${encodeURIComponent(studentId)}/enrollment`, {
      image_base64: frame,
    });
    setStatus(
      "success",
      `Enrollment successful. Quality score: ${Math.round((result.quality_score || 0) * 100)}%.`
    );
    UI.showToast("Face enrolled successfully.", "success");
  } catch (err) {
    // Server-side quality rejection messages (e.g. "Move closer.") land
    // here directly — this file never invents its own quality feedback.
    setStatus("error", err.message);
  } finally {
    resetButton();
  }
}

function resetButton() {
  capturing = false;
  const btn = document.getElementById("capture-btn");
  btn.disabled = false;
  btn.textContent = "Capture & Enroll";
}

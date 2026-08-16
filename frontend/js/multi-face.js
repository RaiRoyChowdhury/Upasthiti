/**
 * Classroom Scan - Phase 9 multi-face recognition.
 *
 * INFORMATIONAL ONLY: shows who's currently visible in frame, with a box
 * and name per detected face. This page never marks attendance - that
 * still requires Live Attendance's single-face + liveness-verified flow.
 * See docs/multi-face.md for why these are kept deliberately separate.
 */

let scanning = false;
let scanTimer = null;
const SCAN_INTERVAL_MS = 1500;

document.addEventListener("DOMContentLoaded", async () => {
  if (!Api.isAuthenticated()) {
    window.location.href = "login.html";
    return;
  }
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
  try {
    await Camera.start(videoEl);
    scanning = true;
    scanTick();
  } catch (err) {
    document.getElementById("scan-status").textContent = err.message;
  }
});

window.addEventListener("beforeunload", () => {
  Camera.stop();
  if (scanTimer) clearTimeout(scanTimer);
});

async function scanTick() {
  if (!scanning || !Camera.isActive()) return;

  const frame = Camera.captureFrameBase64();
  if (frame) {
    try {
      const result = await Api.post("/api/face/recognize-multi", { image_base64: frame });
      renderFaces(result.faces);
    } catch (err) {
      document.getElementById("scan-status").textContent = err.message;
    }
  }

  scanTimer = setTimeout(scanTick, SCAN_INTERVAL_MS);
}

function renderFaces(faces) {
  const canvas = document.getElementById("overlay-canvas");
  const video = document.getElementById("camera-video");

  const stateMap = { known: "known", low_confidence: "pending", unknown: "unknown", poor_quality: "pending" };
  const drawable = faces
    .filter((f) => f.bbox)
    .map((f) => ({
      bbox: f.bbox,
      state: stateMap[f.outcome] || "pending",
      label:
        f.outcome === "known"
          ? `\u2713 ${(f.student_id || "").toUpperCase()} \u2022 ${Math.round((f.confidence || 0) * 100)}%`
          : f.outcome === "unknown"
            ? "\u26A0 UNKNOWN"
            : f.outcome === "low_confidence"
              ? "\u26A0 LOW CONFIDENCE"
              : "",
    }));

  Overlay.drawFaces(canvas, video, drawable);

  document.getElementById("scan-status").textContent = `${faces.length} face(s) detected`;

  const listEl = document.getElementById("faces-list");
  if (faces.length === 0) {
    listEl.innerHTML = '<div class="text-secondary" style="font-size: var(--fs-sm);">No faces currently in frame.</div>';
    return;
  }
  listEl.innerHTML = faces
    .map((f) => {
      const badgeClass = f.outcome === "known" ? "badge-success" : f.outcome === "unknown" ? "badge-danger" : "badge-warning";
      const label = f.outcome === "known" ? f.student_id : f.outcome.replace("_", " ");
      return `<span class="badge ${badgeClass}" style="margin: 2px;">${UI.escapeHtml(label)}${f.confidence ? ` (${Math.round(f.confidence * 100)}%)` : ""}</span>`;
    })
    .join("");
}

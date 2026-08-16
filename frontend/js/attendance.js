/**
 * Live attendance camera controller.
 *
 * This is the centerpiece demo flow:
 *   scan for a face -> recognize -> (if known) liveness challenge
 *     -> mark attendance -> show result -> cooldown -> scan again
 *
 * Every decision (identity, liveness, duplicate, present/late, integrity
 * score) comes from the server. This file only drives the camera, times
 * the polling loop, and renders whatever the server says.
 */

const RECOGNIZE_INTERVAL_MS = 1300;
const LIVENESS_CHECK_INTERVAL_MS = 700;
const ACTIVITY_DEDUP_WINDOW_MS = 4000; // per spec section 24: no repeated identical events

let activeSession = null;
let mode = "idle"; // idle | scanning | liveness | processing | cooldown
let loopTimer = null;
let liveCounts = { enrolled: null, present: 0, late: 0 };
let recentEventKeys = new Map(); // "eventType:studentId" -> last-seen timestamp, for feed dedup

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

  await loadActiveSessionAndStart();
});

window.addEventListener("beforeunload", () => {
  Camera.stop();
  LiveSocket.close();
  if (loopTimer) clearTimeout(loopTimer);
});

async function loadActiveSessionAndStart() {
  try {
    activeSession = await Api.get("/api/sessions/active");
  } catch (_) {
    activeSession = null;
  }

  if (!activeSession) {
    renderNoSession();
    return;
  }

  document.getElementById("active-session-label").textContent =
    `${activeSession.subject} — ${activeSession.class_name}/${activeSession.section}`;

  const videoEl = document.getElementById("camera-video");
  try {
    setCameraStatus("busy", "Starting camera...");
    await Camera.start(videoEl);
    setCameraStatus("live", "Live");
    startScanning();
  } catch (err) {
    setCameraStatus("error", "Camera error");
    renderResult({ icon: "⚠", title: "Camera Error", subtitle: err.message, variant: "error" });
  }

  connectLiveSocket();
  await loadLiveCounts();
  updatePendingSyncIndicator();
  window.addEventListener("online", () => setTimeout(updatePendingSyncIndicator, 1500));
  setInterval(updatePendingSyncIndicator, 5000);
}

function updatePendingSyncIndicator() {
  const el = document.getElementById("status-pending-sync-value");
  if (el) el.textContent = OfflineQueue.count();
}

// ---- Real-time WebSocket layer (additive — HTTP recognize/mark above is
// unchanged and keeps working exactly as before even if this never connects) ----

function connectLiveSocket() {
  LiveSocket.connect(activeSession._id, {
    onStatusChange: handleWsStatusChange,
    onEvent: handleSocketEvent,
  });
}

function handleWsStatusChange(status) {
  const dot = document.getElementById("ws-status-dot");
  const text = document.getElementById("ws-status-text");
  const panelDot = document.getElementById("status-ws-dot");
  const panelValue = document.getElementById("status-ws-value");

  const labels = {
    connecting: "Connecting...",
    live: "Live",
    reconnecting: "Reconnecting...",
    error: "Unavailable",
    closed: "Disconnected",
  };
  dot.className = `ws-status-dot ${status}`;
  text.textContent = labels[status] || status;

  panelDot.className = `status-dot-sm ${status === "live" ? "on" : status === "error" ? "off" : ""}`;
  panelValue.textContent = labels[status] || status;
}

async function loadLiveCounts() {
  try {
    const students = await Api.get("/api/students?limit=1");
    liveCounts.enrolled = students.total;
  } catch (_) {}

  try {
    const records = await Api.get(`/api/attendance?session_id=${activeSession._id}&limit=500`);
    liveCounts.present = records.items.filter((r) => r.status === "present").length;
    liveCounts.late = records.items.filter((r) => r.status === "late").length;
  } catch (_) {}

  renderLiveCounts();
}

function renderLiveCounts() {
  document.getElementById("status-enrolled-value").textContent = liveCounts.enrolled ?? "—";
  document.getElementById("status-present-value").textContent = liveCounts.present;
  document.getElementById("status-late-value").textContent = liveCounts.late;
}

function shouldSkipDuplicateEvent(key) {
  const now = Date.now();
  const last = recentEventKeys.get(key);
  recentEventKeys.set(key, now);
  return last && now - last < ACTIVITY_DEDUP_WINDOW_MS;
}

function handleSocketEvent(event) {
  console.log("[WS] event", event);

  switch (event.event) {
    case "attendance.marked": {
      const key = `marked:${event.student?.id}`;
      if (event.status === "present") liveCounts.present += 1;
      if (event.status === "late") liveCounts.late += 1;
      renderLiveCounts();
      if (!shouldSkipDuplicateEvent(key)) {
        addActivityItem("success", event.student?.name || event.student?.id, `Attendance marked (${event.status})`);
        UI.showToast(`Attendance marked for ${event.student?.name || "student"}.`, "success");
      }
      return;
    }
    case "attendance.already_marked": {
      const key = `already:${event.student?.id}`;
      if (!shouldSkipDuplicateEvent(key)) {
        addActivityItem("info", event.student?.name || event.student?.id, "Already marked present");
      }
      return;
    }
    case "attendance.rejected": {
      addActivityItem("warning", "Attendance rejected", event.message || "Session not active");
      return;
    }
    case "recognition.unknown": {
      const key = "unknown";
      if (!shouldSkipDuplicateEvent(key)) {
        addActivityItem("danger", "Unknown person", "Review required");
      }
      return;
    }
    case "liveness.failed": {
      const key = `liveness_failed:${event.student_id}`;
      if (!shouldSkipDuplicateEvent(key)) {
        addActivityItem("warning", "Liveness failed", event.student_id || "");
      }
      return;
    }
    case "session.closed": {
      addActivityItem("info", "Session closed", "");
      return;
    }
    default:
      return; // recognition.detected / liveness.started / liveness.progress — status-only, not fed into the log
  }
}

function addActivityItem(variant, name, detail) {
  const feed = document.getElementById("activity-feed");
  if (feed.children.length === 1 && feed.children[0].tagName !== "DIV.activity-item") {
    // remove the initial "No activity yet." placeholder, if still present
    const placeholder = feed.querySelector(":scope > .text-secondary");
    if (placeholder) placeholder.remove();
  }

  const icons = { success: "✓", warning: "⚠", danger: "⚠", info: "◎" };
  const time = new Date().toLocaleTimeString(undefined, { hour: "2-digit", minute: "2-digit", second: "2-digit" });

  const item = document.createElement("div");
  item.className = "activity-item fade-in";
  item.innerHTML = `
    <span class="activity-icon ${variant}">${icons[variant] || "•"}</span>
    <span class="activity-time">${time}</span>
    <div class="activity-body">
      <div class="activity-name">${UI.escapeHtml(name || "")}</div>
      <div class="activity-detail">${UI.escapeHtml(detail || "")}</div>
    </div>
  `;
  feed.prepend(item);

  // Keep the feed from growing unbounded during a long session.
  while (feed.children.length > 30) {
    feed.removeChild(feed.lastChild);
  }
}

function renderNoSession() {
  document.getElementById("active-session-label").textContent = "No active session";
  setCameraStatus("error", "No active session");
  renderResult({
    icon: "◎",
    title: "No Active Session",
    subtitle: "Open a session from the Sessions page before starting live attendance.",
    variant: "info",
  });
}

function setCameraStatus(state, text) {
  const dot = document.getElementById("camera-status-dot");
  const label = document.getElementById("camera-status-text");
  dot.className = `camera-status-dot ${state === "live" ? "live" : state === "error" ? "error" : "busy"}`;
  label.textContent = text;

  const panelCameraDot = document.getElementById("status-camera-dot");
  const panelCameraValue = document.getElementById("status-camera-value");
  panelCameraDot.className = `status-dot-sm ${state === "live" ? "on" : state === "error" ? "off" : ""}`;
  panelCameraValue.textContent = state === "live" ? "Connected" : state === "error" ? "Error" : "Starting";

  const panelRecDot = document.getElementById("status-recognition-dot");
  const panelRecValue = document.getElementById("status-recognition-value");
  panelRecDot.className = `status-dot-sm ${state === "live" ? "on" : ""}`;
  panelRecValue.textContent = state === "live" ? "Active" : "Idle";
}

// ---- Scanning loop (recognize) ----

function startScanning() {
  mode = "scanning";
  scheduleNext(scanTick, 400);
}

function scheduleNext(fn, delay) {
  if (loopTimer) clearTimeout(loopTimer);
  loopTimer = setTimeout(fn, delay);
}

async function scanTick() {
  if (mode !== "scanning" || !Camera.isActive()) return;

  const frame = Camera.captureFrameBase64();
  if (!frame) {
    scheduleNext(scanTick, RECOGNIZE_INTERVAL_MS);
    return;
  }

  try {
    const result = await Recognition.recognize(frame, activeSession._id);
    drawOverlayForResult(result);
    await handleRecognitionResult(result, frame);
  } catch (err) {
    renderResult({ icon: "⚠", title: "Recognition Error", subtitle: err.message, variant: "error" });
  }

  if (mode === "scanning") {
    scheduleNext(scanTick, RECOGNIZE_INTERVAL_MS);
  }
}

function drawOverlayForResult(result) {
  const canvas = document.getElementById("overlay-canvas");
  const video = document.getElementById("camera-video");
  if (!result.bbox) {
    Overlay.clear(canvas);
    return;
  }
  const stateMap = { known: "known", low_confidence: "pending", unknown: "unknown" };
  const label =
    result.outcome === "known"
      ? `✓ ${(result.student_id || "").toUpperCase()} • ${Math.round((result.confidence || 0) * 100)}%`
      : result.outcome === "unknown"
        ? "⚠ UNKNOWN"
        : result.outcome === "low_confidence"
          ? "⚠ LOW CONFIDENCE"
          : "";
  Overlay.drawFace(canvas, video, { bbox: result.bbox, label, state: stateMap[result.outcome] || "pending" });
}

async function handleRecognitionResult(result, frame) {
  switch (result.outcome) {
    case "no_face":
      renderResult({ icon: "◎", title: "No Face Detected", subtitle: "Please face the camera.", variant: "neutral" });
      clearNameOverlay();
      return;
    case "multiple_faces":
      renderResult({
        icon: "⚠",
        title: "Multiple People Detected",
        subtitle: "Please ensure only one person is in frame.",
        variant: "warning",
      });
      clearNameOverlay();
      return;
    case "poor_quality":
      renderResult({ icon: "◎", title: "Adjust Position", subtitle: result.message, variant: "neutral" });
      clearNameOverlay();
      return;
    case "unknown":
      renderResult({
        icon: "⚠",
        title: "Unknown Person",
        subtitle: "Attendance not recorded.",
        variant: "danger",
      });
      clearNameOverlay();
      return;
    case "low_confidence":
      renderResult({
        icon: "⚠",
        title: "Low Confidence",
        subtitle: "Teacher verification required.",
        variant: "warning",
      });
      clearNameOverlay();
      return;
    case "known":
      await beginLivenessFlow(result, frame);
      return;
  }
}

// ---- Liveness flow ----

async function beginLivenessFlow(recognitionResult, frame) {
  mode = "liveness";
  const name = await Recognition.findStudentName(recognitionResult.student_id);
  setNameOverlay(name);

  let livenessSession;
  try {
    livenessSession = await Recognition.startLiveness(recognitionResult.student_id, frame, activeSession._id);
  } catch (err) {
    renderResult({ icon: "⚠", title: "Liveness Error", subtitle: err.message, variant: "error" });
    mode = "scanning";
    scheduleNext(scanTick, RECOGNIZE_INTERVAL_MS);
    return;
  }

  renderVerifying(name, livenessSession.prompt);
  pollLiveness(recognitionResult, livenessSession.session_id);
}

async function pollLiveness(recognitionResult, sessionId) {
  if (mode !== "liveness" || !Camera.isActive()) return;

  const frame = Camera.captureFrameBase64();
  if (!frame) {
    scheduleNext(() => pollLiveness(recognitionResult, sessionId), LIVENESS_CHECK_INTERVAL_MS);
    return;
  }

  let session;
  try {
    session = await Recognition.checkLiveness(sessionId, frame, activeSession._id);
  } catch (err) {
    renderResult({ icon: "⚠", title: "Liveness Error", subtitle: err.message, variant: "error" });
    resumeScanningAfter(2000);
    return;
  }

  if (session.state === "verified") {
    await finalizeAttendance(recognitionResult, sessionId);
    return;
  }
  if (session.state === "timeout") {
    renderResult({
      icon: "⚠",
      title: "Liveness Verification Failed",
      subtitle: "Please try again.",
      variant: "danger",
    });
    resumeScanningAfter(2000);
    return;
  }

  scheduleNext(() => pollLiveness(recognitionResult, sessionId), LIVENESS_CHECK_INTERVAL_MS);
}

// ---- Attendance marking ----

async function finalizeAttendance(recognitionResult, livenessSessionId) {
  mode = "processing";
  renderProcessing();

  const markPayload = {
    student_id: recognitionResult.student_id,
    session_id: activeSession._id,
    liveness_session_id: livenessSessionId,
    recognition_confidence: recognitionResult.confidence ?? 0,
    face_quality_score: recognitionResult.quality_score ?? 0,
  };

  try {
    const decision = await Api.post("/api/attendance/mark", markPayload);
    renderAttendanceDecision(decision);
    resumeScanningAfter((decision.cooldown_seconds || 5) * 1000);
  } catch (err) {
    if (err.code === "NETWORK_ERROR") {
      // The liveness_session_id references an in-memory, process-local
      // server object (see cv/liveness.py) with a short TTL — it will very
      // likely have expired by the time connectivity returns and this gets
      // retried, so queuing an unusable liveness_session_id is worse than
      // just telling the person to try again. Only the mark itself queues
      // when there's a genuine chance of a clean retry (see OfflineQueue
      // docstring for the honest limitation here).
      OfflineQueue.enqueue(markPayload);
      renderResult({
        icon: "◎",
        title: "No Connection",
        subtitle: "Queued — will retry automatically once you're back online.",
        variant: "warning",
      });
    } else {
      renderResult({ icon: "⚠", title: "Attendance Error", subtitle: err.message, variant: "error" });
    }
    resumeScanningAfter(3000);
  }
}

function resumeScanningAfter(delayMs) {
  clearNameOverlay();
  mode = "scanning";
  scheduleNext(scanTick, delayMs);
}

// ---- Rendering ----

function setNameOverlay(name) {
  const el = document.getElementById("name-overlay");
  el.textContent = name;
  el.classList.remove("hidden");
}
function clearNameOverlay() {
  document.getElementById("name-overlay").classList.add("hidden");
  Overlay.clear(document.getElementById("overlay-canvas"));
}

function renderProcessing() {
  const panel = document.getElementById("result-panel");
  panel.innerHTML = `
    <div class="result-state-icon"><span class="spinner" style="width:32px;height:32px;"></span></div>
    <div class="result-title">Processing...</div>
    <div class="result-subtitle">Marking attendance.</div>
  `;
}

function renderVerifying(name, prompt) {
  const panel = document.getElementById("result-panel");
  panel.innerHTML = `
    <div class="result-state-icon">◎</div>
    <div class="result-title">${UI.escapeHtml(name)}</div>
    <div class="verification-checklist">
      <div class="verification-item pass"><span class="check-icon">✓</span> Identity Verified</div>
      <div class="verification-item pending"><span class="check-icon">…</span> Liveness Check</div>
      <div class="verification-item pending"><span class="check-icon">…</span> Session Valid</div>
    </div>
    <div class="result-subtitle" style="margin-top: var(--space-3);">${UI.escapeHtml(prompt || "")}</div>
  `;
}

function renderResult({ icon, title, subtitle, variant }) {
  const panel = document.getElementById("result-panel");
  panel.innerHTML = `
    <div class="result-state-icon">${icon}</div>
    <div class="result-title">${UI.escapeHtml(title)}</div>
    <div class="result-subtitle">${UI.escapeHtml(subtitle || "")}</div>
  `;
}

function renderAttendanceDecision(decision) {
  const panel = document.getElementById("result-panel");

  if (decision.outcome === "already_marked") {
    panel.innerHTML = `
      <div class="result-state-icon">◎</div>
      <div class="result-title">Attendance Already Marked</div>
      <div class="result-subtitle">Marked at ${UI.formatDateTime(decision.attendance?.marked_at)}</div>
    `;
    return;
  }

  if (decision.outcome === "session_not_active") {
    panel.innerHTML = `
      <div class="result-state-icon">⚠</div>
      <div class="result-title">Session Not Active</div>
      <div class="result-subtitle">${UI.escapeHtml(decision.message)}</div>
    `;
    return;
  }

  const a = decision.attendance;
  const statusLabel = a.status === "late" ? "LATE" : "PRESENT";
  panel.innerHTML = `
    <div class="verification-checklist">
      <div class="verification-item pass"><span class="check-icon">✓</span> Identity Verified</div>
      <div class="verification-item pass"><span class="check-icon">✓</span> Liveness Verified</div>
      <div class="verification-item pass"><span class="check-icon">✓</span> Session Valid</div>
    </div>
    <div class="integrity-score-block">
      <div class="integrity-score-value">${a.integrity_score}</div>
      <div class="integrity-score-label">Integrity Score / 100</div>
    </div>
    <div class="result-title" style="color: var(--success);">✓ ATTENDANCE MARKED (${statusLabel})</div>
  `;
}

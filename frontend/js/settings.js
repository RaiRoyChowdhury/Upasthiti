document.addEventListener("DOMContentLoaded", async () => {
  if (!Api.isAuthenticated()) {
    window.location.href = "login.html";
    return;
  }
  let user;
  try {
    user = await Api.get("/api/auth/me");
    document.getElementById("user-name").textContent = user.name;
    document.getElementById("user-role").textContent = user.role;
  } catch (_) {}

  document.getElementById("logout-btn").addEventListener("click", async () => {
    try { await Api.post("/api/auth/logout", {}); } catch (_) {}
    Api.clearSession();
    window.location.href = "login.html";
  });

  if (user && user.role !== "admin") {
    document.getElementById("settings-form-card").innerHTML =
      '<div class="alert alert-danger">Only admins can edit institution policy. You can view current values below.</div>';
    document.getElementById("policy-form-fields").querySelectorAll("input").forEach((el) => (el.disabled = true));
    document.getElementById("policy-submit-btn").classList.add("hidden");
  }

  document.getElementById("policy-form").addEventListener("submit", onSavePolicy);
  document.getElementById("run-retention-btn").addEventListener("click", onRunRetention);
  document.getElementById("calibration-capture-btn").addEventListener("click", onCalibrationCapture);
  await loadPolicy();

  try {
    await Camera.start(document.getElementById("calibration-video"));
  } catch (err) {
    document.getElementById("calibration-results").innerHTML =
      `<div class="alert alert-danger">${UI.escapeHtml(err.message)}</div>`;
  }
});

window.addEventListener("beforeunload", () => Camera.stop());

async function onCalibrationCapture() {
  const frame = Camera.captureFrameBase64();
  const resultsEl = document.getElementById("calibration-results");
  if (!frame) {
    resultsEl.innerHTML = '<div class="alert alert-danger">Camera not ready.</div>';
    return;
  }
  resultsEl.innerHTML = '<div class="skeleton" style="height:60px;"></div>';
  try {
    const data = await Api.post("/api/face/calibration-test", { image_base64: frame });
    if (data.scores.length === 0) {
      resultsEl.innerHTML = '<div class="text-secondary">No face detected, or no students enrolled yet.</div>';
      return;
    }
    resultsEl.innerHTML = `
      <p class="text-secondary" style="font-size: var(--fs-sm); margin-bottom: var(--space-2);">
        Configured KNOWN threshold: <strong>${data.configured_threshold}</strong> —
        LOW_CONFIDENCE floor: <strong>${data.configured_low_confidence_threshold}</strong>
      </p>
      ${data.scores
        .map(
          (s) => `
        <div style="display:flex; justify-content:space-between; padding: 6px 0; border-bottom: 1px solid var(--border); font-size: var(--fs-sm);">
          <span>${UI.escapeHtml(s.student_id)}</span>
          <span style="font-weight:600;">${s.similarity}</span>
        </div>`
        )
        .join("")}
    `;
  } catch (err) {
    resultsEl.innerHTML = `<div class="alert alert-danger">${UI.escapeHtml(err.message)}</div>`;
  }
}

async function loadPolicy() {
  try {
    const policy = await Api.get("/api/policy");
    document.getElementById("required-percent-input").value = policy.required_attendance_percent;
    document.getElementById("late-threshold-input").value = policy.default_late_threshold_minutes;
    document.getElementById("attendance-retention-input").value = policy.attendance_retention_days ?? "";
    document.getElementById("recognition-retention-input").value = policy.recognition_log_retention_days ?? "";
    document.getElementById("retention-enforcement-input").checked = !!policy.retention_enforcement_enabled;
    document.getElementById("policy-updated-note").textContent = policy.updated_by
      ? `Last updated ${UI.formatDateTime(policy.updated_at)}`
      : "Using default values — never edited.";
  } catch (err) {
    UI.showToast(err.message, "error");
  }
}

async function onSavePolicy(event) {
  event.preventDefault();
  const payload = {
    required_attendance_percent: parseFloat(document.getElementById("required-percent-input").value) || null,
    default_late_threshold_minutes: parseInt(document.getElementById("late-threshold-input").value, 10) || null,
    attendance_retention_days: document.getElementById("attendance-retention-input").value
      ? parseInt(document.getElementById("attendance-retention-input").value, 10)
      : null,
    recognition_log_retention_days: document.getElementById("recognition-retention-input").value
      ? parseInt(document.getElementById("recognition-retention-input").value, 10)
      : null,
    retention_enforcement_enabled: document.getElementById("retention-enforcement-input").checked,
  };
  try {
    await Api.put("/api/policy", payload);
    UI.showToast("Policy updated.", "success");
    await loadPolicy();
  } catch (err) {
    UI.showToast(err.message, "error");
  }
}

async function onRunRetention() {
  const resultEl = document.getElementById("retention-result");
  resultEl.innerHTML = '<span class="spinner"></span>';
  try {
    const result = await Api.post("/api/policy/run-retention-now", {});
    if (!result.ran) {
      resultEl.innerHTML = `<div class="alert alert-info">Did not run: ${UI.escapeHtml(result.reason)}</div>`;
      return;
    }
    const deletedText = Object.entries(result.deleted)
      .map(([k, v]) => `${v} ${k}`)
      .join(", ");
    resultEl.innerHTML = `<div class="alert alert-success">Purge ran. Deleted: ${deletedText || "nothing (no records older than the configured retention)."}</div>`;
  } catch (err) {
    resultEl.innerHTML = `<div class="alert alert-danger">${UI.escapeHtml(err.message)}</div>`;
  }
}

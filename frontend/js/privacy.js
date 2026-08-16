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

  document.getElementById("delete-enrollment-form").addEventListener("submit", onDeleteEnrollment);
  await loadRetentionSettings();
});

async function loadRetentionSettings() {
  try {
    const policy = await Api.get("/api/policy");
    document.getElementById("retention-attendance").textContent =
      policy.attendance_retention_days ? `${policy.attendance_retention_days} days` : "Not set (kept indefinitely)";
    document.getElementById("retention-recognition").textContent =
      policy.recognition_log_retention_days ? `${policy.recognition_log_retention_days} days` : "Not set (kept indefinitely)";
  } catch (_) {}
}

async function onDeleteEnrollment(event) {
  event.preventDefault();
  const studentId = document.getElementById("delete-student-id").value.trim();
  const resultEl = document.getElementById("delete-result");
  if (!studentId) return;

  if (!confirm(`Delete the face enrollment for student "${studentId}"? This removes their biometric data. This cannot be undone.`)) {
    return;
  }

  resultEl.innerHTML = '<span class="spinner"></span>';
  try {
    const result = await Api.delete(`/api/students/${encodeURIComponent(studentId)}/enrollment`);
    resultEl.innerHTML = `<div class="alert alert-success">${UI.escapeHtml(result.message)}</div>`;
  } catch (err) {
    resultEl.innerHTML = `<div class="alert alert-danger">${UI.escapeHtml(err.message)}</div>`;
  }
}

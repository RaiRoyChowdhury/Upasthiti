const params = new URLSearchParams(window.location.search);
const studentId = params.get("student_id");

document.addEventListener("DOMContentLoaded", async () => {
  if (!Api.isAuthenticated()) {
    window.location.href = "login.html";
    return;
  }
  if (!studentId) {
    document.getElementById("profile-content").innerHTML =
      '<div class="alert alert-danger">No student selected. Go back to Students and click a student row.</div>';
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

  document.getElementById("forecast-form").addEventListener("submit", onForecast);
  document.getElementById("download-report-btn").addEventListener("click", onDownloadReport);
  document.getElementById("download-report-pdf-btn").addEventListener("click", onDownloadReportPdf);

  await loadProfile();
});

async function loadProfile() {
  document.getElementById("profile-title").textContent = studentId;
  try {
    const data = await Api.get(`/api/analytics/student/${encodeURIComponent(studentId)}`);
    renderProfile(data);
  } catch (err) {
    document.getElementById("profile-content").innerHTML =
      `<div class="alert alert-danger">${UI.escapeHtml(err.message)}</div>`;
  }
}

function renderProfile(data) {
  document.getElementById("metric-percent").textContent = `${data.attendance_percent}%`;
  document.getElementById("metric-present").textContent = data.present;
  document.getElementById("metric-late").textContent = data.late;
  document.getElementById("metric-absent").textContent = data.absent;

  Heatmap.loadAndRender(document.getElementById("heatmap-container"), studentId);

  const riskBadge = document.getElementById("risk-badge");
  riskBadge.textContent = data.risk.replace("_", " ").toUpperCase();
  riskBadge.className = `badge ${UI.badgeClass(data.risk)}`;

  document.getElementById("required-note").textContent =
    data.classes_needed_to_reach_target === 0
      ? `Already meeting the ${data.required_attendance_percent}% requirement.`
      : data.classes_needed_to_reach_target === -1
        ? "Target requires 100% attendance and cannot be reached after any absence."
        : `Needs to attend the next ${data.classes_needed_to_reach_target} class(es) to reach ${data.required_attendance_percent}%.`;

  const historyEl = document.getElementById("history-strip");
  if (data.recent_history.length === 0) {
    historyEl.innerHTML = '<div class="text-secondary">No attendance history yet.</div>';
  } else {
    historyEl.innerHTML = data.recent_history
      .map((h) => {
        const color = h.status === "present" ? "success" : h.status === "late" ? "warning" : "neutral";
        return `<span class="badge badge-${color}" title="${UI.formatDateTime(h.marked_at)} — score ${h.integrity_score}">${h.status}</span>`;
      })
      .join(" ");
  }
}

async function onForecast(event) {
  event.preventDefault();
  const n = parseInt(document.getElementById("forecast-input").value, 10) || 0;
  const resultEl = document.getElementById("forecast-result");
  resultEl.textContent = "Calculating...";
  try {
    const data = await Api.get(`/api/analytics/student/${encodeURIComponent(studentId)}/forecast?additional_classes=${n}`);
    resultEl.innerHTML = `
      If ${data.additional_classes_attended} more classes are attended, projected attendance becomes
      <strong>${data.projected_attendance_percent}%</strong> (currently ${data.current_attendance_percent}%).
      <div class="text-tertiary" style="font-size: var(--fs-xs); margin-top: 4px;">${UI.escapeHtml(data.note)}</div>
    `;
  } catch (err) {
    resultEl.innerHTML = `<span class="text-danger">${UI.escapeHtml(err.message)}</span>`;
  }
}

async function onDownloadReport() {
  try {
    await Api.download(`/api/reports/student/${encodeURIComponent(studentId)}`, `student_${studentId}_report.csv`);
  } catch (err) {
    UI.showToast(err.message, "error");
  }
}

async function onDownloadReportPdf() {
  try {
    await Api.download(
      `/api/reports/student/${encodeURIComponent(studentId)}?format=pdf`,
      `student_${studentId}_report.pdf`
    );
  } catch (err) {
    UI.showToast(err.message, "error");
  }
}

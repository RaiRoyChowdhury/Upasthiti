/**
 * Student dashboard — the student-facing counterpart to dashboard.html.
 *
 * Shows only the logged-in student's OWN data, via the User<->Student link
 * (user.student_id, see database/models/user_model.py). If the account
 * isn't linked to a roster record, that's shown plainly rather than
 * silently failing or showing someone else's data.
 */

document.addEventListener("DOMContentLoaded", async () => {
  if (!Api.isAuthenticated()) {
    window.location.href = "login.html";
    return;
  }

  let user;
  try {
    user = await Api.get("/api/auth/me");
    Api.setSession(Api.getToken(), user);
  } catch (err) {
    console.error(err.message);
    return;
  }

  if (user.role !== "student") {
    // A teacher/admin who navigated here directly — send them to the
    // dashboard that's actually built for their role.
    window.location.href = "dashboard.html";
    return;
  }

  document.getElementById("user-name").textContent = user.name;
  document.getElementById("user-role").textContent = user.role;

  document.getElementById("logout-btn").addEventListener("click", async () => {
    try { await Api.post("/api/auth/logout", {}); } catch (_) {}
    Api.clearSession();
    window.location.href = "login.html";
  });

  if (!user.student_id) {
    document.getElementById("not-linked-message").classList.remove("hidden");
    document.getElementById("linked-content").classList.add("hidden");
    return;
  }

  document.getElementById("forecast-form").addEventListener("submit", onForecast);
  await loadMyStats(user.student_id);
});

async function loadMyStats(studentId) {
  try {
    const data = await Api.get(`/api/analytics/student/${encodeURIComponent(studentId)}`);
    document.getElementById("metric-percent").textContent = `${data.attendance_percent}%`;
    document.getElementById("metric-present").textContent = data.present;
    document.getElementById("metric-late").textContent = data.late;
    document.getElementById("metric-absent").textContent = data.absent;

    const riskBadge = document.getElementById("risk-badge");
    riskBadge.textContent = data.risk.replace("_", " ").toUpperCase();
    riskBadge.className = `badge ${UI.badgeClass(data.risk)}`;

    document.getElementById("required-note").textContent =
      data.classes_needed_to_reach_target === 0
        ? `You're meeting the ${data.required_attendance_percent}% requirement.`
        : data.classes_needed_to_reach_target === -1
          ? "This target requires 100% attendance and can't be reached after any absence."
          : `Attend your next ${data.classes_needed_to_reach_target} class(es) to reach ${data.required_attendance_percent}%.`;

    Heatmap.loadAndRender(document.getElementById("heatmap-container"), studentId);

    const historyEl = document.getElementById("history-strip");
    historyEl.innerHTML =
      data.recent_history.length === 0
        ? '<div class="text-secondary">No attendance history yet.</div>'
        : data.recent_history
            .map((h) => {
              const color = h.status === "present" ? "success" : h.status === "late" ? "warning" : "neutral";
              return `<span class="badge badge-${color}" title="${UI.formatDateTime(h.marked_at)}">${h.status}</span>`;
            })
            .join(" ");
  } catch (err) {
    document.getElementById("linked-content").innerHTML =
      `<div class="alert alert-danger">${UI.escapeHtml(err.message)}</div>`;
  }
}

async function onForecast(event) {
  event.preventDefault();
  const user = Api.getCachedUser();
  const n = parseInt(document.getElementById("forecast-input").value, 10) || 0;
  const resultEl = document.getElementById("forecast-result");
  resultEl.textContent = "Calculating...";
  try {
    const data = await Api.get(
      `/api/analytics/student/${encodeURIComponent(user.student_id)}/forecast?additional_classes=${n}`
    );
    resultEl.innerHTML = `
      If you attend your next ${data.additional_classes_attended} classes, your attendance becomes
      <strong>${data.projected_attendance_percent}%</strong> (currently ${data.current_attendance_percent}%).
      <div class="text-tertiary" style="font-size: var(--fs-xs); margin-top: 4px;">${UI.escapeHtml(data.note)}</div>
    `;
  } catch (err) {
    resultEl.innerHTML = `<span class="text-danger">${UI.escapeHtml(err.message)}</span>`;
  }
}

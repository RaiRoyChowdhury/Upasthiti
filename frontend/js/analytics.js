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

  await loadOverview();
  document.getElementById("class-lookup-form").addEventListener("submit", onClassLookup);
});

async function loadOverview() {
  try {
    const data = await Api.get("/api/analytics/overview");
    document.getElementById("overview-students").textContent = data.total_students;
    document.getElementById("overview-sessions").textContent = data.total_sessions;
    document.getElementById("overview-rate").textContent = `${data.attendance_rate_percent}%`;

    const total = data.present + data.late;
    const presentPct = total > 0 ? (data.present / total) * 100 : 0;
    const latePct = total > 0 ? (data.late / total) * 100 : 0;

    document.getElementById("bar-present").style.width = `${presentPct}%`;
    document.getElementById("bar-late").style.width = `${latePct}%`;
    document.getElementById("bar-present-label").textContent = `Present: ${data.present}`;
    document.getElementById("bar-late-label").textContent = `Late: ${data.late}`;
  } catch (err) {
    UI.showToast(err.message, "error");
  }
}

async function onClassLookup(event) {
  event.preventDefault();
  const form = event.target;
  const className = form.class_name.value.trim();
  const section = form.section.value.trim();
  const resultEl = document.getElementById("class-lookup-result");

  if (!className || !section) return;

  resultEl.innerHTML = '<div class="skeleton" style="height:60px;"></div>';
  try {
    const data = await Api.get(`/api/analytics/class?class_name=${encodeURIComponent(className)}&section=${encodeURIComponent(section)}`);
    resultEl.innerHTML = `
      <div class="metrics-grid" style="margin-top: var(--space-4);">
        <div class="card metric-card"><div class="metric-label">Sessions Counted</div><div class="metric-value">${data.sessions_counted}</div></div>
        <div class="card metric-card"><div class="metric-label">Present</div><div class="metric-value">${data.present}</div></div>
        <div class="card metric-card"><div class="metric-label">Late</div><div class="metric-value">${data.late}</div></div>
        <div class="card metric-card"><div class="metric-label">Attendance Rate</div><div class="metric-value">${data.attendance_rate_percent}%</div></div>
      </div>
      <button class="btn btn-secondary" style="margin-top: var(--space-4);" id="class-csv-btn">Download CSV</button>
    `;
    document.getElementById("class-csv-btn").addEventListener("click", async () => {
      try {
        await Api.download(
          `/api/reports/class?class_name=${encodeURIComponent(className)}&section=${encodeURIComponent(section)}`,
          `class_${className}_${section}_report.csv`
        );
      } catch (err) {
        UI.showToast(err.message, "error");
      }
    });
  } catch (err) {
    resultEl.innerHTML = `<div class="alert alert-danger">${UI.escapeHtml(err.message)}</div>`;
  }
}

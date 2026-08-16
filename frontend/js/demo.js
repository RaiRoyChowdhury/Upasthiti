/**
 * Demo Mode - Phase 10.
 *
 * Every value shown on this page comes from the demo_* collections
 * (see backend/database/repositories/demo_repository.py) - entirely
 * separate from real students/sessions/attendance. Nothing here can
 * appear on the real Dashboard, Students, Sessions, or Analytics pages,
 * and vice versa.
 */

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

  document.getElementById("generate-form").addEventListener("submit", onGenerate);
  document.getElementById("clear-btn").addEventListener("click", onClear);

  await loadSummary();
});

async function loadSummary() {
  try {
    const summary = await Api.get("/api/demo/summary");
    renderSummary(summary);
    if (summary.students > 0) {
      await loadDashboard();
    }
  } catch (err) {
    UI.showToast(err.message, "error");
  }
}

function renderSummary(summary) {
  document.getElementById("summary-students").textContent = summary.students;
  document.getElementById("summary-sessions").textContent = summary.sessions;
  document.getElementById("summary-records").textContent = summary.attendance_records;
  document.getElementById("summary-generated").textContent = summary.generated_at
    ? UI.formatDateTime(summary.generated_at)
    : "Never generated";
}

async function loadDashboard() {
  const container = document.getElementById("demo-dashboard");
  container.innerHTML = '<div class="skeleton" style="height:120px;"></div>';
  try {
    const data = await Api.get("/api/demo/dashboard");
    if (data.students.length === 0) {
      container.innerHTML = '<div class="text-secondary">No demo data yet — generate a dataset above.</div>';
      return;
    }
    container.innerHTML = `
      <table style="width:100%; border-collapse: collapse; font-size: var(--fs-sm);">
        <thead>
          <tr>
            <th style="text-align:left; padding:8px; color:var(--text-tertiary); font-size:var(--fs-xs); text-transform:uppercase;">Name</th>
            <th style="text-align:left; padding:8px; color:var(--text-tertiary); font-size:var(--fs-xs); text-transform:uppercase;">Present</th>
            <th style="text-align:left; padding:8px; color:var(--text-tertiary); font-size:var(--fs-xs); text-transform:uppercase;">Late</th>
            <th style="text-align:left; padding:8px; color:var(--text-tertiary); font-size:var(--fs-xs); text-transform:uppercase;">Absent</th>
            <th style="text-align:left; padding:8px; color:var(--text-tertiary); font-size:var(--fs-xs); text-transform:uppercase;">Attendance %</th>
          </tr>
        </thead>
        <tbody>
          ${data.students
            .map(
              (s) => `
            <tr style="border-top:1px solid var(--border);">
              <td style="padding:8px;">${UI.escapeHtml(s.name)}</td>
              <td style="padding:8px;">${s.present}</td>
              <td style="padding:8px;">${s.late}</td>
              <td style="padding:8px;">${s.absent}</td>
              <td style="padding:8px; font-weight:600;">${s.attendance_percent}%</td>
            </tr>`
            )
            .join("")}
        </tbody>
      </table>
    `;
  } catch (err) {
    container.innerHTML = `<div class="alert alert-danger">${UI.escapeHtml(err.message)}</div>`;
  }
}

async function onGenerate(event) {
  event.preventDefault();
  const form = event.target;
  const studentCount = parseInt(form.student_count.value, 10);
  const sessionCount = parseInt(form.session_count.value, 10);

  const btn = form.querySelector("button[type=submit]");
  btn.disabled = true;
  btn.textContent = "Generating...";
  try {
    const summary = await Api.post("/api/demo/generate", {
      student_count: studentCount,
      session_count: sessionCount,
    });
    renderSummary(summary);
    await loadDashboard();
    UI.showToast("Demo dataset generated.", "success");
  } catch (err) {
    UI.showToast(err.message, "error");
  } finally {
    btn.disabled = false;
    btn.textContent = "Generate Demo Data";
  }
}

async function onClear() {
  if (!confirm("Clear all demo data? This only affects the isolated demo dataset — real data is never touched.")) {
    return;
  }
  try {
    await Api.delete("/api/demo/clear");
    UI.showToast("Demo data cleared.", "success");
    await loadSummary();
    document.getElementById("demo-dashboard").innerHTML =
      '<div class="text-secondary">No demo data — generate a dataset above.</div>';
  } catch (err) {
    UI.showToast(err.message, "error");
  }
}

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

  await populateSessionDropdown();

  document.getElementById("session-report-form").addEventListener("submit", async (e) => {
    e.preventDefault();
    const format = e.submitter?.dataset.format || "csv";
    const sessionId = document.getElementById("session-select").value;
    if (!sessionId) return;
    await download(`/api/reports/session/${sessionId}?format=${format}`, `session_${sessionId}_report.${format}`);
  });

  document.getElementById("student-report-form").addEventListener("submit", async (e) => {
    e.preventDefault();
    const format = e.submitter?.dataset.format || "csv";
    const studentId = document.getElementById("student-id-input").value.trim();
    if (!studentId) return;
    await download(
      `/api/reports/student/${encodeURIComponent(studentId)}?format=${format}`,
      `student_${studentId}_report.${format}`
    );
  });

  document.getElementById("class-report-form").addEventListener("submit", async (e) => {
    e.preventDefault();
    const format = e.submitter?.dataset.format || "csv";
    const className = document.getElementById("class-name-input").value.trim();
    const section = document.getElementById("class-section-input").value.trim();
    if (!className || !section) return;
    await download(
      `/api/reports/class?class_name=${encodeURIComponent(className)}&section=${encodeURIComponent(section)}&format=${format}`,
      `class_${className}_${section}_report.${format}`
    );
  });
});

async function populateSessionDropdown() {
  const select = document.getElementById("session-select");
  try {
    const data = await Api.get("/api/sessions?limit=100");
    select.innerHTML = data.items
      .map((s) => `<option value="${s._id}">${UI.escapeHtml(s.subject)} — ${UI.escapeHtml(s.class_name)}/${UI.escapeHtml(s.section)} (${s.status})</option>`)
      .join("");
  } catch (err) {
    select.innerHTML = `<option>Failed to load sessions</option>`;
  }
}

async function download(path, filename) {
  try {
    await Api.download(path, filename);
    UI.showToast("Report downloaded.", "success");
  } catch (err) {
    UI.showToast(err.message, "error");
  }
}

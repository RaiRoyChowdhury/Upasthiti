document.addEventListener("DOMContentLoaded", async () => {
  if (!Api.isAuthenticated()) {
    window.location.href = "login.html";
    return;
  }

  try {
    const user = await Api.get("/api/auth/me");
    document.getElementById("user-name").textContent = user.name;
    document.getElementById("user-role").textContent = user.role;
    document.getElementById("user-avatar").textContent = initials(user.name);
  } catch (_) {}

  document.getElementById("logout-btn").addEventListener("click", async () => {
    try { await Api.post("/api/auth/logout", {}); } catch (_) {}
    Api.clearSession();
    window.location.href = "login.html";
  });

  document.getElementById("session-create-form").addEventListener("submit", onCreateSession);
  document.getElementById("sessions-tbody").addEventListener("click", onTableClick);
  document.querySelectorAll(".sortable-th").forEach((th) => th.addEventListener("click", onSortClick));

  prefillFromQueryParams();
  await loadSessions();
});

let currentSessions = [];
let sessionSortState = { field: null, direction: "asc" };

function onSortClick(event) {
  const field = event.target.dataset.sort;
  if (sessionSortState.field === field) {
    sessionSortState.direction = sessionSortState.direction === "asc" ? "desc" : "asc";
  } else {
    sessionSortState = { field, direction: "asc" };
  }

  document.querySelectorAll(".sortable-th").forEach((th) => {
    th.classList.remove("sorted-asc", "sorted-desc");
    if (th.dataset.sort === field) {
      th.classList.add(sessionSortState.direction === "asc" ? "sorted-asc" : "sorted-desc");
    }
  });

  renderSessions(sortSessions(currentSessions));
}

function sortSessions(sessions) {
  if (!sessionSortState.field) return sessions;
  return [...sessions].sort((a, b) => {
    const av = (a[sessionSortState.field] ?? "").toString().toLowerCase();
    const bv = (b[sessionSortState.field] ?? "").toString().toLowerCase();
    if (av < bv) return sessionSortState.direction === "asc" ? -1 : 1;
    if (av > bv) return sessionSortState.direction === "asc" ? 1 : -1;
    return 0;
  });
}

/**
 * Supports the "Create Session" convenience link from classes.html's
 * timetable — pre-fills the form fields, does NOT auto-submit. The
 * teacher still reviews and clicks Create Session themselves.
 */
function prefillFromQueryParams() {
  const params = new URLSearchParams(window.location.search);
  const form = document.getElementById("session-create-form");
  ["subject", "class_name", "section"].forEach((field) => {
    const value = params.get(field);
    if (value && form[field]) form[field].value = value;
  });
}

function initials(name) {
  const parts = (name || "").trim().split(/\s+/);
  return ((parts[0]?.[0] || "") + (parts.length > 1 ? parts[parts.length - 1][0] : "")).toUpperCase();
}

async function loadSessions() {
  const tbody = document.getElementById("sessions-tbody");
  tbody.innerHTML = `<tr><td colspan="6"><div class="skeleton" style="height:20px;"></div></td></tr>`;
  try {
    const data = await Api.get("/api/sessions");
    currentSessions = data.items;
    renderSessions(sortSessions(currentSessions));
  } catch (err) {
    tbody.innerHTML = `<tr><td colspan="6">Failed to load sessions: ${UI.escapeHtml(err.message)}</td></tr>`;
  }
}

function renderSessions(sessions) {
  const tbody = document.getElementById("sessions-tbody");
  if (sessions.length === 0) {
    tbody.innerHTML = `<tr><td colspan="6" class="text-secondary">No sessions yet.</td></tr>`;
    return;
  }
  tbody.innerHTML = sessions
    .map((s) => {
      let actions = "";
      if (s.status === "scheduled") {
        actions = `<button class="btn btn-primary" style="padding:6px 12px;font-size:12px;" data-action="open" data-id="${s._id}">Open</button>`;
      } else if (s.status === "active") {
        actions = `<button class="btn btn-danger" style="padding:6px 12px;font-size:12px;" data-action="close" data-id="${s._id}">Close</button>`;
      }
      if (s.status !== "scheduled") {
        actions += ` <button class="btn btn-secondary" style="padding:6px 12px;font-size:12px;" data-action="summary" data-id="${s._id}">Summary</button>`;
      }
      if (s.status === "active") {
        actions += ` <button class="btn btn-secondary" style="padding:6px 12px;font-size:12px;" data-action="occupancy" data-id="${s._id}">Occupancy</button>`;
      }
      return `
      <tr>
        <td>${UI.escapeHtml(s.subject)}</td>
        <td>${UI.escapeHtml(s.class_name)} / ${UI.escapeHtml(s.section)}</td>
        <td><span class="badge ${UI.badgeClass(s.status)}">${s.status}</span></td>
        <td>${UI.formatDateTime(s.start_time)}</td>
        <td>${s.late_threshold_minutes ?? "default"}</td>
        <td>${actions}</td>
      </tr>`;
    })
    .join("");
}

async function onTableClick(event) {
  const btn = event.target.closest("button[data-action]");
  if (!btn) return;
  const { action, id } = btn.dataset;

  if (action === "summary") {
    await showSessionSummary(id);
    return;
  }
  if (action === "occupancy") {
    await showOccupancyPanel(id);
    return;
  }

  btn.disabled = true;
  try {
    await Api.post(`/api/sessions/${id}/${action}`, {});
    UI.showToast(`Session ${action === "open" ? "opened" : "closed"}.`, "success");
    await loadSessions();
  } catch (err) {
    UI.showToast(err.message, "error");
    btn.disabled = false;
  }
}

async function showOccupancyPanel(sessionId) {
  const panel = document.getElementById("occupancy-panel");
  panel.classList.remove("hidden");
  panel.innerHTML = '<div class="skeleton" style="height:60px;"></div>';

  try {
    const [occupancy, records] = await Promise.all([
      Api.get(`/api/sessions/${sessionId}/occupancy`),
      Api.get(`/api/attendance?session_id=${sessionId}&limit=200`),
    ]);

    const presentWithoutExit = records.items.filter(
      (r) => (r.status === "present" || r.status === "late") && !r.exit_time
    );

    panel.innerHTML = `
      <h3 style="margin-bottom: var(--space-3);">
        Live Occupancy: ${occupancy.currently_present} / ${occupancy.total_enrolled}
        (${occupancy.occupancy_percent}%)
      </h3>
      <p class="text-tertiary" style="font-size: var(--fs-xs); margin-bottom: var(--space-3);">
        Exit is marked manually below — this is not automatic camera-based detection
        (see Privacy Center / documentation for why).
      </p>
      ${
        presentWithoutExit.length === 0
          ? '<div class="text-secondary" style="font-size: var(--fs-sm);">No students currently marked present without an exit.</div>'
          : presentWithoutExit
              .map(
                (r) => `
          <div style="display:flex; justify-content:space-between; align-items:center; padding: 6px 0; border-bottom: 1px solid var(--border);">
            <span style="font-size: var(--fs-sm);">${UI.escapeHtml(r.student_id)} (${r.status})</span>
            <button class="btn btn-secondary" style="padding:4px 10px;font-size:12px;" data-exit-id="${r._id}">Mark Exit</button>
          </div>`
              )
              .join("")
      }
    `;

    panel.querySelectorAll("[data-exit-id]").forEach((btn) => {
      btn.addEventListener("click", async () => {
        btn.disabled = true;
        try {
          await Api.post(`/api/attendance/${btn.dataset.exitId}/mark-exit`, {});
          UI.showToast("Exit marked.", "success");
          await showOccupancyPanel(sessionId);
        } catch (err) {
          UI.showToast(err.message, "error");
          btn.disabled = false;
        }
      });
    });
  } catch (err) {
    panel.innerHTML = `<div class="alert alert-danger">${UI.escapeHtml(err.message)}</div>`;
  }
}

async function showSessionSummary(sessionId) {
  try {
    const data = await Api.get(`/api/analytics/session/${sessionId}/summary`);
    alert(data.summary);
  } catch (err) {
    UI.showToast(err.message, "error");
  }
}

async function onCreateSession(event) {
  event.preventDefault();
  const form = event.target;
  const lateThreshold = form.late_threshold_minutes.value;
  const payload = {
    subject: form.subject.value.trim(),
    class_name: form.class_name.value.trim(),
    section: form.section.value.trim(),
    late_threshold_minutes: lateThreshold ? parseInt(lateThreshold, 10) : null,
  };
  try {
    await Api.post("/api/sessions", payload);
    UI.showToast("Session created.", "success");
    form.reset();
    await loadSessions();
  } catch (err) {
    UI.showToast(err.message, "error");
  }
}

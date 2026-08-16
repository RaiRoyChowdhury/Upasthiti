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

  document.getElementById("class-create-form").addEventListener("submit", onCreateClass);
  document.getElementById("timetable-create-form").addEventListener("submit", onCreateTimetableEntry);
  document.getElementById("classes-tbody").addEventListener("click", onClassAction);
  document.getElementById("timetable-tbody").addEventListener("click", onTimetableAction);

  await Promise.all([loadClasses(), loadTimetable()]);
});

let classesCache = [];

async function loadClasses() {
  const tbody = document.getElementById("classes-tbody");
  const select = document.getElementById("timetable-class-select");
  try {
    classesCache = await Api.get("/api/classes");
    if (classesCache.length === 0) {
      tbody.innerHTML = '<tr><td colspan="4" class="text-secondary">No classes yet.</td></tr>';
      select.innerHTML = '<option value="">Create a class first</option>';
      return;
    }
    tbody.innerHTML = classesCache
      .map(
        (c) => `
      <tr>
        <td>${UI.escapeHtml(c.subject)}</td>
        <td>${UI.escapeHtml(c.class_name)}</td>
        <td>${UI.escapeHtml(c.section)}</td>
        <td><button class="btn btn-danger" style="padding:6px 12px;font-size:12px;" data-action="delete-class" data-id="${c._id}">Delete</button></td>
      </tr>`
      )
      .join("");
    select.innerHTML = classesCache
      .map((c) => `<option value="${c._id}">${UI.escapeHtml(c.subject)} — ${UI.escapeHtml(c.class_name)}/${UI.escapeHtml(c.section)}</option>`)
      .join("");
  } catch (err) {
    tbody.innerHTML = `<tr><td colspan="4">Failed to load: ${UI.escapeHtml(err.message)}</td></tr>`;
  }
}

async function loadTimetable() {
  const tbody = document.getElementById("timetable-tbody");
  try {
    const entries = await Api.get("/api/classes/timetable");
    if (entries.length === 0) {
      tbody.innerHTML = '<tr><td colspan="5" class="text-secondary">No timetable entries yet.</td></tr>';
      return;
    }
    tbody.innerHTML = entries
      .map((e) => {
        const cls = classesCache.find((c) => c._id === e.class_id);
        const label = cls ? `${cls.subject} (${cls.class_name}/${cls.section})` : e.class_id;
        return `
        <tr>
          <td>${UI.escapeHtml(label)}</td>
          <td style="text-transform:capitalize;">${UI.escapeHtml(e.day_of_week)}</td>
          <td>${UI.escapeHtml(e.start_time)}</td>
          <td>${UI.escapeHtml(e.end_time)}</td>
          <td>
            <button class="btn btn-secondary" style="padding:6px 12px;font-size:12px;" data-action="use-entry" data-id="${e._id}">Create Session</button>
            <button class="btn btn-danger" style="padding:6px 12px;font-size:12px;" data-action="delete-entry" data-id="${e._id}">Delete</button>
          </td>
        </tr>`;
      })
      .join("");
  } catch (err) {
    tbody.innerHTML = `<tr><td colspan="5">Failed to load: ${UI.escapeHtml(err.message)}</td></tr>`;
  }
}

async function onCreateClass(event) {
  event.preventDefault();
  const form = event.target;
  try {
    await Api.post("/api/classes", {
      subject: form.subject.value.trim(),
      class_name: form.class_name.value.trim(),
      section: form.section.value.trim(),
    });
    form.reset();
    UI.showToast("Class created.", "success");
    await loadClasses();
  } catch (err) {
    UI.showToast(err.message, "error");
  }
}

async function onCreateTimetableEntry(event) {
  event.preventDefault();
  const form = event.target;
  const classId = document.getElementById("timetable-class-select").value;
  if (!classId) {
    UI.showToast("Create a class first.", "error");
    return;
  }
  try {
    await Api.post("/api/classes/timetable", {
      class_id: classId,
      day_of_week: form.day_of_week.value,
      start_time: form.start_time.value,
      end_time: form.end_time.value,
    });
    UI.showToast("Timetable entry added.", "success");
    await loadTimetable();
  } catch (err) {
    UI.showToast(err.message, "error");
  }
}

async function onClassAction(event) {
  const btn = event.target.closest("button[data-action='delete-class']");
  if (!btn) return;
  if (!confirm("Delete this class?")) return;
  try {
    await Api.delete(`/api/classes/${btn.dataset.id}`);
    await loadClasses();
    await loadTimetable();
  } catch (err) {
    UI.showToast(err.message, "error");
  }
}

async function onTimetableAction(event) {
  const deleteBtn = event.target.closest("button[data-action='delete-entry']");
  const useBtn = event.target.closest("button[data-action='use-entry']");

  if (deleteBtn) {
    try {
      await Api.delete(`/api/classes/timetable/${deleteBtn.dataset.id}`);
      await loadTimetable();
    } catch (err) {
      UI.showToast(err.message, "error");
    }
    return;
  }

  if (useBtn) {
    // Pre-fills the existing Sessions creation form via query params —
    // does not create a session itself (see class_routes.py docstring).
    try {
      const defaults = await Api.get(`/api/classes/timetable/${useBtn.dataset.id}/session-defaults`);
      const params = new URLSearchParams(defaults);
      window.location.href = `sessions.html?${params.toString()}`;
    } catch (err) {
      UI.showToast(err.message, "error");
    }
  }
}

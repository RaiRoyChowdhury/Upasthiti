/**
 * Students page controller.
 */

let currentUserRole = null;

document.addEventListener("DOMContentLoaded", async () => {
  if (!Api.isAuthenticated()) {
    window.location.href = "login.html";
    return;
  }

  try {
    const user = await Api.get("/api/auth/me");
    currentUserRole = user.role;
    document.getElementById("user-name").textContent = user.name;
    document.getElementById("user-role").textContent = user.role;
    document.getElementById("user-avatar").textContent = initials(user.name);

    if (!["admin", "teacher"].includes(user.role)) {
      document.getElementById("add-student-btn").classList.add("hidden");
    }
  } catch (err) {
    console.error(err.message);
  }

  document.getElementById("logout-btn").addEventListener("click", async () => {
    try {
      await Api.post("/api/auth/logout", {});
    } catch (_) {}
    Api.clearSession();
    window.location.href = "login.html";
  });

  document.getElementById("add-student-btn").addEventListener("click", () => {
    document.getElementById("add-student-form").classList.toggle("hidden");
  });

  document.getElementById("student-create-form").addEventListener("submit", onCreateStudent);
  document.getElementById("search-input").addEventListener("input", debounce(loadStudents, 350));
  document.querySelectorAll(".sortable-th").forEach((th) => th.addEventListener("click", onSortClick));

  await loadStudents();
});

let currentStudents = [];
let sortState = { field: null, direction: "asc" };

function onSortClick(event) {
  const field = event.target.dataset.sort;
  if (sortState.field === field) {
    sortState.direction = sortState.direction === "asc" ? "desc" : "asc";
  } else {
    sortState = { field, direction: "asc" };
  }

  document.querySelectorAll(".sortable-th").forEach((th) => {
    th.classList.remove("sorted-asc", "sorted-desc");
    if (th.dataset.sort === field) {
      th.classList.add(sortState.direction === "asc" ? "sorted-asc" : "sorted-desc");
    }
  });

  renderStudents(sortStudents(currentStudents));
}

function sortStudents(students) {
  if (!sortState.field) return students;
  const sorted = [...students].sort((a, b) => {
    const av = (a[sortState.field] ?? "").toString().toLowerCase();
    const bv = (b[sortState.field] ?? "").toString().toLowerCase();
    if (av < bv) return sortState.direction === "asc" ? -1 : 1;
    if (av > bv) return sortState.direction === "asc" ? 1 : -1;
    return 0;
  });
  return sorted;
}

function initials(name) {
  const parts = (name || "").trim().split(/\s+/);
  return ((parts[0]?.[0] || "") + (parts.length > 1 ? parts[parts.length - 1][0] : "")).toUpperCase();
}

function debounce(fn, delay) {
  let t;
  return (...args) => {
    clearTimeout(t);
    t = setTimeout(() => fn(...args), delay);
  };
}

async function loadStudents() {
  const tbody = document.getElementById("students-tbody");
  const search = document.getElementById("search-input").value.trim();
  tbody.innerHTML = `<tr><td colspan="7"><div class="skeleton" style="height:20px;"></div></td></tr>`;

  try {
    const query = search ? `?search=${encodeURIComponent(search)}` : "";
    const data = await Api.get(`/api/students${query}`);
    currentStudents = data.items;
    renderStudents(sortStudents(currentStudents));
  } catch (err) {
    tbody.innerHTML = `<tr><td colspan="7">Failed to load students: ${UI.escapeHtml(err.message)}</td></tr>`;
  }
}

function renderStudents(students) {
  const tbody = document.getElementById("students-tbody");
  if (students.length === 0) {
    tbody.innerHTML = `<tr><td colspan="7" class="text-secondary">No students found.</td></tr>`;
    return;
  }

  tbody.innerHTML = students
    .map(
      (s) => `
    <tr>
      <td>${UI.escapeHtml(s.name)}</td>
      <td>${UI.escapeHtml(s.student_id)}</td>
      <td>${UI.escapeHtml(s.roll_number)}</td>
      <td>${UI.escapeHtml(s.department)} / ${UI.escapeHtml(s.section)}</td>
      <td><span class="badge ${s.face_enrolled ? "badge-success" : "badge-neutral"}">${
        s.face_enrolled ? "Enrolled" : "Not enrolled"
      }</span></td>
      <td><span class="badge ${UI.badgeClass(s.status)}">${UI.escapeHtml(s.status)}</span></td>
      <td>
        <a class="btn btn-secondary" style="padding:6px 12px;font-size:12px;"
           href="enrollment.html?student_id=${encodeURIComponent(s.student_id)}&name=${encodeURIComponent(s.name)}">
           ${s.face_enrolled ? "Re-enroll" : "Enroll Face"}
        </a>
        <a class="btn btn-secondary" style="padding:6px 12px;font-size:12px;"
           href="student-profile.html?student_id=${encodeURIComponent(s.student_id)}">
           Profile
        </a>
      </td>
    </tr>`
    )
    .join("");
}

async function onCreateStudent(event) {
  event.preventDefault();
  const form = event.target;
  const payload = {
    name: form.name.value.trim(),
    student_id: form.student_id.value.trim(),
    roll_number: form.roll_number.value.trim(),
    department: form.department.value.trim(),
    section: form.section.value.trim(),
    email: form.email.value.trim() || null,
  };

  try {
    await Api.post("/api/students", payload);
    UI.showToast("Student created.", "success");
    form.reset();
    document.getElementById("add-student-form").classList.add("hidden");
    await loadStudents();
  } catch (err) {
    UI.showToast(err.message, "error");
  }
}

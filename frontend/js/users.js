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
    document.getElementById("main-content").innerHTML =
      '<div class="alert alert-danger">Only admins can manage users.</div>';
    return;
  }

  document.getElementById("user-create-form").addEventListener("submit", onCreateUser);
  document.getElementById("role-filter").addEventListener("change", loadUsers);
  document.addEventListener("click", onTableClick);
  document.addEventListener("change", onTableChange);

  await loadUsers();
});

let currentAdminId = null;

async function loadUsers() {
  const tbody = document.getElementById("users-tbody");
  tbody.innerHTML = '<tr><td colspan="6"><div class="skeleton" style="height:20px;"></div></td></tr>';
  try {
    const me = await Api.get("/api/auth/me");
    currentAdminId = me._id;

    const data = await Api.get("/api/auth/users?limit=200");
    const roleFilter = document.getElementById("role-filter").value;
    const items = roleFilter ? data.items.filter((u) => u.role === roleFilter) : data.items;
    renderUsers(items);
  } catch (err) {
    tbody.innerHTML = `<tr><td colspan="6">Failed to load users: ${UI.escapeHtml(err.message)}</td></tr>`;
  }
}

function renderUsers(users) {
  const tbody = document.getElementById("users-tbody");
  if (users.length === 0) {
    tbody.innerHTML = '<tr><td colspan="6" class="text-secondary">No users found.</td></tr>';
    return;
  }
  tbody.innerHTML = users
    .map((u) => {
      const isSelf = u._id === currentAdminId;
      return `
      <tr>
        <td>${UI.escapeHtml(u.name)}</td>
        <td>${UI.escapeHtml(u.email)}</td>
        <td>
          <select class="input" style="padding:4px 8px; font-size:12px;" data-action="change-role" data-id="${u._id}" ${isSelf ? "disabled" : ""}>
            <option value="admin" ${u.role === "admin" ? "selected" : ""}>admin</option>
            <option value="teacher" ${u.role === "teacher" ? "selected" : ""}>teacher</option>
            <option value="student" ${u.role === "student" ? "selected" : ""}>student</option>
          </select>
        </td>
        <td>${u.student_id ? UI.escapeHtml(u.student_id) : '<span class="text-tertiary">Not linked</span>'}</td>
        <td><span class="badge ${u.is_active ? "badge-success" : "badge-neutral"}">${u.is_active ? "Active" : "Inactive"}</span></td>
        <td>
          ${
            isSelf
              ? '<span class="text-tertiary" style="font-size:12px;">(you)</span>'
              : `<button class="btn ${u.is_active ? "btn-danger" : "btn-secondary"}" style="padding:6px 12px;font-size:12px;"
                   data-action="toggle-active" data-id="${u._id}" data-active="${u.is_active}">
                   ${u.is_active ? "Deactivate" : "Reactivate"}
                 </button>`
          }
        </td>
      </tr>`;
    })
    .join("");
}

async function onCreateUser(event) {
  event.preventDefault();
  const form = event.target;
  const studentId = form.student_id.value.trim();
  const payload = {
    name: form.name.value.trim(),
    email: form.email.value.trim(),
    role: form.role.value,
    password: form.password.value,
    student_id: studentId || null,
  };
  try {
    await Api.post("/api/auth/register", payload);
    UI.showToast("User created.", "success");
    form.reset();
    await loadUsers();
  } catch (err) {
    UI.showToast(err.message, "error");
  }
}

async function onTableClick(event) {
  const toggleBtn = event.target.closest("button[data-action='toggle-active']");
  if (!toggleBtn) return;
  const isActive = toggleBtn.dataset.active === "true";
  try {
    await Api.request(`/api/auth/users/${toggleBtn.dataset.id}`, {
      method: "PATCH",
      body: { is_active: !isActive },
    });
    UI.showToast(isActive ? "User deactivated." : "User reactivated.", "success");
    await loadUsers();
  } catch (err) {
    UI.showToast(err.message, "error");
  }
}

async function onTableChange(event) {
  const roleSelect = event.target.closest("select[data-action='change-role']");
  if (!roleSelect) return;
  try {
    await Api.request(`/api/auth/users/${roleSelect.dataset.id}`, {
      method: "PATCH",
      body: { role: roleSelect.value },
    });
    UI.showToast("Role updated.", "success");
  } catch (err) {
    UI.showToast(err.message, "error");
    await loadUsers();
  }
}

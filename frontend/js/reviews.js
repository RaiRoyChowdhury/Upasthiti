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

  document.getElementById("reviews-tbody").addEventListener("click", onResolveClick);
  await loadReviews();
});

async function loadReviews() {
  const tbody = document.getElementById("reviews-tbody");
  tbody.innerHTML = `<tr><td colspan="5"><div class="skeleton" style="height:20px;"></div></td></tr>`;
  try {
    const data = await Api.get("/api/reviews?status=pending");
    renderReviews(data.items);
  } catch (err) {
    tbody.innerHTML = `<tr><td colspan="5">Failed to load: ${UI.escapeHtml(err.message)}</td></tr>`;
  }
}

function renderReviews(items) {
  const tbody = document.getElementById("reviews-tbody");
  if (items.length === 0) {
    tbody.innerHTML = `<tr><td colspan="5" class="text-secondary">No pending reviews.</td></tr>`;
    return;
  }
  tbody.innerHTML = items
    .map(
      (r) => `
    <tr>
      <td><span class="badge ${UI.badgeClass(r.event_type)}">${UI.escapeHtml(r.event_type)}</span></td>
      <td>${UI.escapeHtml(r.candidate_student_id || "—")}</td>
      <td>${r.confidence !== null ? UI.formatPercent(r.confidence) : "—"}</td>
      <td>${UI.formatDateTime(r.created_at)}</td>
      <td>
        <button class="btn btn-primary" style="padding:6px 12px;font-size:12px;" data-action="approved" data-id="${r._id}">Approve</button>
        <button class="btn btn-danger" style="padding:6px 12px;font-size:12px;" data-action="rejected" data-id="${r._id}">Reject</button>
      </td>
    </tr>`
    )
    .join("");
}

async function onResolveClick(event) {
  const btn = event.target.closest("button[data-action]");
  if (!btn) return;
  const { action, id } = btn.dataset;
  btn.disabled = true;
  try {
    await Api.post(`/api/reviews/${id}/resolve`, { status: action });
    UI.showToast("Review resolved.", "success");
    await loadReviews();
  } catch (err) {
    UI.showToast(err.message, "error");
    btn.disabled = false;
  }
}

/**
 * Dashboard shell controller.
 *
 * Now backed by real data: /api/analytics/overview for metric cards,
 * /api/notifications for the bell — no fabricated numbers.
 */

document.addEventListener("DOMContentLoaded", async () => {
  if (!Api.isAuthenticated()) {
    window.location.href = "login.html";
    return;
  }

  // Show cached user immediately for a fast paint, then confirm with the server.
  renderUser(Api.getCachedUser());

  try {
    const user = await Api.get("/api/auth/me");
    Api.setSession(Api.getToken(), user);
    renderUser(user);
    applyRoleVisibility(user.role);

    if (user.role === "student") {
      window.location.href = "student-dashboard.html";
      return;
    }
  } catch (err) {
    // Api.request already redirects to login on 401; anything else, show inline.
    console.error("Failed to load current user:", err.message);
  }

  const logoutBtn = document.getElementById("logout-btn");
  if (logoutBtn) {
    logoutBtn.addEventListener("click", async () => {
      try {
        await Api.post("/api/auth/logout", {});
      } catch (_) {
        // Even if the server call fails, still clear the local session.
      }
      Api.clearSession();
      window.location.href = "login.html";
    });
  }

  await loadOverviewMetrics();
  await setupNotificationBell();
});

async function loadOverviewMetrics() {
  try {
    const overview = await Api.get("/api/analytics/overview");
    setMetric("metric-total-students", overview.total_students);
    setMetric("metric-present", overview.present);
    setMetric("metric-late", overview.late);
    setMetric("metric-attendance-rate", `${overview.attendance_rate_percent}%`);
  } catch (err) {
    console.error("Failed to load overview metrics:", err.message);
  }
}

function setMetric(id, value) {
  const el = document.getElementById(id);
  if (el) {
    el.textContent = value;
    el.classList.remove("metric-placeholder");
    el.classList.add("metric-value");
  }
}

async function setupNotificationBell() {
  const bell = document.getElementById("notification-bell");
  const badge = document.getElementById("notification-badge");
  const dropdown = document.getElementById("notification-dropdown");
  if (!bell) return;

  async function refreshBadge() {
    try {
      const data = await Api.get("/api/notifications/unread-count");
      if (data.unread_count > 0) {
        badge.textContent = data.unread_count > 9 ? "9+" : data.unread_count;
        badge.classList.remove("hidden");
      } else {
        badge.classList.add("hidden");
      }
    } catch (_) {}
  }

  async function loadDropdown() {
    dropdown.innerHTML = '<div class="notification-item">Loading...</div>';
    try {
      const notifications = await Api.get("/api/notifications");
      if (notifications.length === 0) {
        dropdown.innerHTML = '<div class="notification-item text-secondary">No notifications yet.</div>';
        return;
      }
      dropdown.innerHTML = notifications
        .map(
          (n) => `
        <div class="notification-item ${n.read ? "" : "unread"}">
          <div>${UI.escapeHtml(n.message)}</div>
          <div class="notification-item-time">${UI.formatDateTime(n.created_at)}</div>
        </div>`
        )
        .join("");
    } catch (err) {
      dropdown.innerHTML = `<div class="notification-item">Failed to load: ${UI.escapeHtml(err.message)}</div>`;
    }
  }

  bell.addEventListener("click", async (e) => {
    e.stopPropagation();
    const isHidden = dropdown.classList.contains("hidden");
    dropdown.classList.toggle("hidden");
    if (isHidden) {
      await loadDropdown();
      try {
        await Api.post("/api/notifications/read-all", {});
        await refreshBadge();
      } catch (_) {}
    }
  });

  document.addEventListener("click", (e) => {
    if (!dropdown.contains(e.target) && e.target !== bell) {
      dropdown.classList.add("hidden");
    }
  });

  await refreshBadge();
}

function renderUser(user) {
  if (!user) return;
  const nameEl = document.getElementById("user-name");
  const roleEl = document.getElementById("user-role");
  const avatarEl = document.getElementById("user-avatar");

  if (nameEl) nameEl.textContent = user.name;
  if (roleEl) roleEl.textContent = user.role;
  if (avatarEl) avatarEl.textContent = initials(user.name);
}

function initials(name) {
  if (!name) return "?";
  const parts = name.trim().split(/\s+/);
  const first = parts[0]?.[0] || "";
  const last = parts.length > 1 ? parts[parts.length - 1][0] : "";
  return (first + last).toUpperCase();
}

/**
 * Nav items are visually gated by role for UX clarity only.
 * This is NOT a security boundary — the server enforces RBAC on every
 * protected route regardless of what the sidebar shows or hides.
 */
function applyRoleVisibility(role) {
  document.querySelectorAll("[data-role-only]").forEach((el) => {
    const allowedRoles = el.getAttribute("data-role-only").split(",").map((r) => r.trim());
    if (!allowedRoles.includes(role)) {
      el.classList.add("hidden");
    }
  });
}

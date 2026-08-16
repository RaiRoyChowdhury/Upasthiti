/**
 * Small shared UI helpers used across pages.
 */

const UI = {
  badgeClass(status) {
    const map = {
      active: "badge-success",
      present: "badge-success",
      verified: "badge-success",
      scheduled: "badge-info",
      pending: "badge-warning",
      pending_review: "badge-warning",
      low_confidence: "badge-warning",
      late: "badge-warning",
      closed: "badge-neutral",
      failed: "badge-danger",
      rejected: "badge-danger",
      unknown: "badge-danger",
      inactive: "badge-neutral",
    };
    return map[status] || "badge-neutral";
  },

  formatDateTime(isoString) {
    if (!isoString) return "—";
    const d = new Date(isoString);
    return d.toLocaleString(undefined, {
      month: "short",
      day: "numeric",
      hour: "2-digit",
      minute: "2-digit",
    });
  },

  formatPercent(value) {
    if (value === null || value === undefined) return "—";
    return `${Math.round(value * 100)}%`;
  },

  escapeHtml(str) {
    const div = document.createElement("div");
    div.textContent = str ?? "";
    return div.innerHTML;
  },

  showToast(message, variant = "info") {
    let container = document.getElementById("toast-container");
    if (!container) {
      container = document.createElement("div");
      container.id = "toast-container";
      container.style.cssText =
        "position:fixed;top:20px;right:20px;z-index:1000;display:flex;flex-direction:column;gap:8px;";
      document.body.appendChild(container);
    }
    const toast = document.createElement("div");
    toast.className = `alert alert-${variant === "error" ? "danger" : variant} fade-in`;
    toast.style.cssText = "min-width:260px; box-shadow: var(--shadow-md);";
    toast.textContent = message;
    container.appendChild(toast);
    setTimeout(() => toast.remove(), 4000);
  },
};

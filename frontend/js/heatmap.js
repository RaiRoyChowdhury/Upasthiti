/**
 * Renders a simple day-by-day attendance heatmap (present=green,
 * late=yellow, absent=red, no_class=gray) into a container element.
 * Data comes from GET /api/analytics/student/{id}/heatmap — real
 * per-calendar-day status, not a mockup grid.
 */

const Heatmap = {
  colors: {
    present: "var(--success)",
    late: "var(--warning)",
    absent: "var(--danger)",
    no_class: "var(--surface-elevated)",
  },

  render(containerEl, days) {
    if (!days || days.length === 0) {
      containerEl.innerHTML = '<div class="text-secondary" style="font-size: var(--fs-sm);">No data yet.</div>';
      return;
    }

    const cells = days
      .map((d) => {
        const color = this.colors[d.status] || this.colors.no_class;
        return `<div class="heatmap-cell" style="background:${color};" title="${d.date}: ${d.status.replace("_", " ")}"></div>`;
      })
      .join("");

    containerEl.innerHTML = `
      <div class="heatmap-grid">${cells}</div>
      <div class="heatmap-legend">
        <span><span class="heatmap-legend-dot" style="background:${this.colors.present}"></span> Present</span>
        <span><span class="heatmap-legend-dot" style="background:${this.colors.late}"></span> Late</span>
        <span><span class="heatmap-legend-dot" style="background:${this.colors.absent}"></span> Absent</span>
        <span><span class="heatmap-legend-dot" style="background:${this.colors.no_class}"></span> No class</span>
      </div>
    `;
  },

  async loadAndRender(containerEl, studentId, days = 90) {
    containerEl.innerHTML = '<div class="skeleton" style="height:80px;"></div>';
    try {
      const data = await Api.get(`/api/analytics/student/${encodeURIComponent(studentId)}/heatmap?days=${days}`);
      this.render(containerEl, data);
    } catch (err) {
      containerEl.innerHTML = `<div class="alert alert-danger">${UI.escapeHtml(err.message)}</div>`;
    }
  },
};

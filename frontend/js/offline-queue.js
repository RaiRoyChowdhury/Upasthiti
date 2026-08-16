/**
 * Offline queue for attendance-mark requests that fail due to a genuine
 * network error (not a business-logic rejection — those aren't queued,
 * see attendance.js's NETWORK_ERROR check).
 *
 * HONEST LIMITATION: a queued mark payload includes a liveness_session_id
 * referencing an in-memory, short-TTL object on the server (see
 * cv/liveness.py). If connectivity is down long enough for that TTL to
 * expire, the retried request will come back with LIVENESS_SESSION_NOT_FOUND
 * — a real, expected failure, not a bug — and that item is dropped from
 * the queue rather than retried forever. This queue smooths over brief
 * connectivity blips (the actual common case on a spotty campus network),
 * not extended outages; a fundamentally offline-first redesign of the
 * liveness step would be a much larger change than this phase's scope.
 *
 * Server-side idempotency (attendance_repository.py's unique index) means
 * a retried mark is always safe to resend even if it partially succeeded
 * before the connection dropped.
 */

const OfflineQueue = {
  STORAGE_KEY: "smartattend_offline_queue",

  _read() {
    try {
      const raw = localStorage.getItem(this.STORAGE_KEY);
      return raw ? JSON.parse(raw) : [];
    } catch (_) {
      return [];
    }
  },

  _write(items) {
    try {
      localStorage.setItem(this.STORAGE_KEY, JSON.stringify(items));
    } catch (_) {
      // Storage full/unavailable — queuing is a best-effort convenience,
      // not a guarantee, so fail silently rather than break the page.
    }
  },

  enqueue(payload) {
    const items = this._read();
    items.push({ ...payload, queued_at: new Date().toISOString() });
    this._write(items);
    console.log("[OFFLINE-QUEUE] queued", payload);
  },

  count() {
    return this._read().length;
  },

  /**
   * Attempts to resend every queued item. Removes items that either
   * succeed OR fail with a non-network error (nothing left to retry for
   * those — see module docstring). Items that fail again with a network
   * error stay queued for the next flush attempt.
   */
  async flush(onProgress) {
    const items = this._read();
    if (items.length === 0) return;

    const stillQueued = [];
    for (const item of items) {
      const { queued_at, ...payload } = item;
      try {
        await Api.post("/api/attendance/mark", payload);
        console.log("[OFFLINE-QUEUE] synced", payload);
      } catch (err) {
        if (err.code === "NETWORK_ERROR") {
          stillQueued.push(item); // retry next time
        } else {
          console.warn("[OFFLINE-QUEUE] dropping item — no longer retryable:", err.message, payload);
        }
      }
    }
    this._write(stillQueued);
    if (onProgress) onProgress(stillQueued.length);
  },
};

// Flush automatically when the browser regains connectivity, and on load
// in case items were queued in a previous session.
window.addEventListener("online", () => OfflineQueue.flush());
document.addEventListener("DOMContentLoaded", () => {
  if (navigator.onLine) OfflineQueue.flush();
});

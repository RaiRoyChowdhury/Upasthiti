/**
 * WebSocket client for /ws/attendance/{session_id}.
 *
 * Responsible ONLY for: opening the connection, reconnecting with backoff,
 * and forwarding parsed events to a callback. It never makes an
 * attendance/recognition decision — it just delivers whatever the server
 * publishes. If this fails entirely, the existing HTTP recognize/mark
 * polling flow in attendance.js keeps working unchanged (this is additive,
 * not a replacement — see docs/websocket.md "Fallback behavior").
 */

const LiveSocket = {
  ws: null,
  sessionId: null,
  onEvent: null,
  onStatusChange: null,
  reconnectAttempts: 0,
  maxReconnectDelayMs: 15000,
  manualClose: false,

  connect(sessionId, { onEvent, onStatusChange } = {}) {
    this.sessionId = sessionId;
    this.onEvent = onEvent || (() => {});
    this.onStatusChange = onStatusChange || (() => {});
    this.manualClose = false;
    this._open();
  },

  _open() {
    const token = Api.getToken();
    if (!token) {
      console.error("[WS] no auth token available, cannot connect");
      this.onStatusChange("error");
      return;
    }

    // Derives the WS host from API_BASE_URL (api.js) rather than
    // window.location.host directly — in a split deployment (frontend on
    // Vercel, backend on Render), the WebSocket must connect to the
    // backend's host, not the page's own host. Same-origin local dev is
    // unaffected since API_BASE_URL defaults to window.location.origin.
    const apiUrl = new URL(API_BASE_URL);
    const protocol = apiUrl.protocol === "https:" ? "wss:" : "ws:";
    const url = `${protocol}//${apiUrl.host}/ws/attendance/${encodeURIComponent(this.sessionId)}?token=${encodeURIComponent(token)}`;

    console.log("[WS] connecting", url.replace(/token=[^&]+/, "token=***"));
    this.onStatusChange(this.reconnectAttempts > 0 ? "reconnecting" : "connecting");

    this.ws = new WebSocket(url);

    this.ws.onopen = () => {
      console.log("[WS] connected");
      this.reconnectAttempts = 0;
      this.onStatusChange("live");
    };

    this.ws.onmessage = (msg) => {
      try {
        const event = JSON.parse(msg.data);
        this.onEvent(event);
      } catch (err) {
        console.error("[WS] failed to parse event", err, msg.data);
      }
    };

    this.ws.onerror = (err) => {
      console.error("[WS] error", err);
    };

    this.ws.onclose = (event) => {
      console.log("[WS] closed", event.code, event.reason);
      if (this.manualClose) {
        this.onStatusChange("closed");
        return;
      }
      if (event.code === 4401 || event.code === 4403 || event.code === 4404) {
        // Auth/authorization/session errors — reconnecting won't help.
        console.error("[WS] connection rejected, not retrying (code " + event.code + ")");
        this.onStatusChange("error");
        return;
      }
      this._scheduleReconnect();
    };
  },

  _scheduleReconnect() {
    this.reconnectAttempts += 1;
    const delay = Math.min(1000 * 2 ** this.reconnectAttempts, this.maxReconnectDelayMs);
    console.log(`[WS] reconnecting in ${delay}ms (attempt ${this.reconnectAttempts})`);
    this.onStatusChange("reconnecting");
    setTimeout(() => {
      if (!this.manualClose) this._open();
    }, delay);
  },

  close() {
    this.manualClose = true;
    if (this.ws) {
      this.ws.close();
    }
  },
};

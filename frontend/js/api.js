/**
 * Thin fetch wrapper shared by every page.
 *
 * Important: this file only ever *displays* what the server decides. It does
 * not make any authorization or attendance decision itself — the frontend
 * is never the source of truth for "is this user allowed to do X", it just
 * reflects the server's answer.
 */

/**
 * API_BASE_URL resolution — supports two deployment topologies without
 * code changes (see docs/deployment.md):
 *   1. Same-origin (default, local dev, or single-service Render deploy):
 *      frontend and backend served from the same origin — window.location.origin.
 *   2. Split deployment (frontend on Vercel, backend on Render):
 *      set window.SMARTATTEND_API_BASE_URL BEFORE this script loads
 *      (see frontend/config.js, generated per-environment) to point at
 *      the Render backend's URL instead.
 */
const API_BASE_URL = window.SMARTATTEND_API_BASE_URL || window.location.origin;
const TOKEN_KEY = "smartattend_token";
const USER_KEY = "smartattend_user";

const Api = {
  getToken() {
    return localStorage.getItem(TOKEN_KEY);
  },

  setSession(token, user) {
    localStorage.setItem(TOKEN_KEY, token);
    localStorage.setItem(USER_KEY, JSON.stringify(user));
  },

  getCachedUser() {
    const raw = localStorage.getItem(USER_KEY);
    return raw ? JSON.parse(raw) : null;
  },

  clearSession() {
    localStorage.removeItem(TOKEN_KEY);
    localStorage.removeItem(USER_KEY);
  },

  isAuthenticated() {
    return Boolean(this.getToken());
  },

  /**
   * @param {string} path e.g. "/api/auth/login"
   * @param {object} options { method, body, auth }
   */
  async request(path, options = {}) {
    const { method = "GET", body, auth = true } = options;

    const headers = { "Content-Type": "application/json" };
    if (auth) {
      const token = this.getToken();
      if (token) headers["Authorization"] = `Bearer ${token}`;
    }

    let response;
    try {
      response = await fetch(`${API_BASE_URL}${path}`, {
        method,
        headers,
        body: body ? JSON.stringify(body) : undefined,
      });
    } catch (networkErr) {
      throw new ApiError("Could not reach the server. Check your connection and try again.", 0, "NETWORK_ERROR");
    }

    let data = null;
    try {
      data = await response.json();
    } catch (_) {
      // No JSON body (e.g. 204) — fine.
    }

    if (!response.ok) {
      const code = data?.error?.code || "UNKNOWN_ERROR";
      const message = data?.error?.message || "Something went wrong. Please try again.";

      if (response.status === 401 && auth) {
        this.clearSession();
        if (!window.location.pathname.includes("login.html")) {
          window.location.href = "/app/pages/login.html";
        }
      }
      throw new ApiError(message, response.status, code);
    }

    return data;
  },

  get(path, options = {}) {
    return this.request(path, { ...options, method: "GET" });
  },
  post(path, body, options = {}) {
    return this.request(path, { ...options, method: "POST", body });
  },
  put(path, body, options = {}) {
    return this.request(path, { ...options, method: "PUT", body });
  },
  delete(path, options = {}) {
    return this.request(path, { ...options, method: "DELETE" });
  },

  /**
   * Downloads a file from an authenticated endpoint (e.g. CSV reports).
   * A plain <a href="/api/..."> would not carry the Authorization header
   * our API requires, so this fetches with the header and triggers the
   * browser's save dialog via a temporary object URL instead.
   */
  async download(path, filename) {
    const token = this.getToken();
    const response = await fetch(`${API_BASE_URL}${path}`, {
      headers: token ? { Authorization: `Bearer ${token}` } : {},
    });
    if (!response.ok) {
      let message = "Download failed.";
      try {
        const data = await response.json();
        message = data?.error?.message || message;
      } catch (_) {}
      throw new ApiError(message, response.status, "DOWNLOAD_FAILED");
    }
    const blob = await response.blob();
    const url = window.URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    a.remove();
    window.URL.revokeObjectURL(url);
  },
};

class ApiError extends Error {
  constructor(message, status, code) {
    super(message);
    this.status = status;
    this.code = code;
  }
}

/**
 * Deployment configuration - ONLY relevant for split deployment (frontend
 * on Vercel, backend on Render). Local dev and single-service Render
 * deployment (the recommended default - see docs/deployment.md) don't
 * need this file loaded at all; api.js falls back to same-origin.
 *
 * To use split deployment: uncomment the <script src="../config.js">
 * line in every page's <head> (see docs/deployment.md "Path B"), and set
 * the real backend URL here before deploying the frontend.
 */
window.SMARTATTEND_API_BASE_URL = "https://your-backend.onrender.com";

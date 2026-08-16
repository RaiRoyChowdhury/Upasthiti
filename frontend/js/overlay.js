/**
 * Bounding-box overlay renderer.
 *
 * Draws on a <canvas> absolutely positioned over the <video> element. The
 * canvas shares the video's CSS mirror transform (scaleX(-1)) so we can
 * draw in plain, unmirrored coordinates and let the shared transform
 * handle the mirroring identically for both — no manual x-axis flip math,
 * no risk of getting that flip backwards.
 *
 * Coordinate mapping handles what the video element itself does via
 * object-fit: cover: the native frame (video.videoWidth x videoHeight) is
 * scaled up to fill the container and cropped, not stretched. We replicate
 * that same scale+offset math here so a box drawn from backend pixel
 * coordinates lands on the actual face rather than a stretched/offset
 * position. See docs/websocket.md "Coordinate mapping" for the full math.
 */

const Overlay = {
  smoothingFactor: 0.35, // 0 = no movement, 1 = no smoothing (snap instantly)
  _lastBox: null, // { x1, y1, x2, y2 } in displayed canvas pixel coords, post-smoothing

  /**
   * Call whenever the container/video size might have changed (resize,
   * orientation change, initial load) — keeps canvas resolution matching
   * its displayed CSS size so drawing isn't blurry or misaligned.
   */
  syncCanvasSize(canvasEl, videoEl) {
    const rect = videoEl.getBoundingClientRect();
    const dpr = window.devicePixelRatio || 1;
    canvasEl.width = Math.round(rect.width * dpr);
    canvasEl.height = Math.round(rect.height * dpr);
    canvasEl.style.width = `${rect.width}px`;
    canvasEl.style.height = `${rect.height}px`;
    return { width: rect.width, height: rect.height, dpr };
  },

  /**
   * Maps a native-video-pixel bbox to displayed canvas coordinates,
   * replicating object-fit: cover's scale+crop behavior.
   */
  _mapBoxToDisplay(bbox, videoEl, containerWidth, containerHeight, dpr) {
    const nativeW = videoEl.videoWidth;
    const nativeH = videoEl.videoHeight;
    if (!nativeW || !nativeH) return null;

    const scale = Math.max(containerWidth / nativeW, containerHeight / nativeH);
    const renderedW = nativeW * scale;
    const renderedH = nativeH * scale;
    const offsetX = (containerWidth - renderedW) / 2;
    const offsetY = (containerHeight - renderedH) / 2;

    const [x1, y1, x2, y2] = bbox;
    return {
      x1: (x1 * scale + offsetX) * dpr,
      y1: (y1 * scale + offsetY) * dpr,
      x2: (x2 * scale + offsetX) * dpr,
      y2: (y2 * scale + offsetY) * dpr,
    };
  },

  _smooth(newBox) {
    if (!this._lastBox) {
      this._lastBox = newBox;
      return newBox;
    }
    const f = this.smoothingFactor;
    const lerp = (a, b) => a + (b - a) * f;
    this._lastBox = {
      x1: lerp(this._lastBox.x1, newBox.x1),
      y1: lerp(this._lastBox.y1, newBox.y1),
      x2: lerp(this._lastBox.x2, newBox.x2),
      y2: lerp(this._lastBox.y2, newBox.y2),
    };
    return this._lastBox;
  },

  /**
   * Draws a rounded rectangle path without relying on ctx.roundRect(),
   * which isn't available in all browsers/versions — this avoids a
   * silent draw failure on anything slightly older than very recent
   * Chrome/Edge/Firefox.
   */
  _roundedRectPath(ctx, x, y, w, h, r) {
    const radius = Math.min(r, w / 2, h / 2);
    ctx.beginPath();
    ctx.moveTo(x + radius, y);
    ctx.lineTo(x + w - radius, y);
    ctx.arcTo(x + w, y, x + w, y + radius, radius);
    ctx.lineTo(x + w, y + h - radius);
    ctx.arcTo(x + w, y + h, x + w - radius, y + h, radius);
    ctx.lineTo(x + radius, y + h);
    ctx.arcTo(x, y + h, x, y + h - radius, radius);
    ctx.lineTo(x, y + radius);
    ctx.arcTo(x, y, x + radius, y, radius);
    ctx.closePath();
  },

  clear(canvasEl) {
    const ctx = canvasEl.getContext("2d");
    ctx.clearRect(0, 0, canvasEl.width, canvasEl.height);
    this._lastBox = null;
  },

  /**
   * @param {HTMLCanvasElement} canvasEl
   * @param {HTMLVideoElement} videoEl
   * @param {{bbox: number[], label: string, state: "known"|"unknown"|"pending"|"liveness"}} face
   *   Single-face rendering only in this phase — the backend's recognition
   *   pipeline returns at most one bbox per frame (see docs/websocket.md
   *   "Known limitations"); the API shape here accepts one face object,
   *   not an array, for that reason, documented rather than faked.
   */
  drawFace(canvasEl, videoEl, face) {
    const { width, height, dpr } = this.syncCanvasSize(canvasEl, videoEl);
    const ctx = canvasEl.getContext("2d");
    ctx.clearRect(0, 0, canvasEl.width, canvasEl.height);

    if (!face || !face.bbox) {
      this._lastBox = null;
      return;
    }

    const mapped = this._mapBoxToDisplay(face.bbox, videoEl, width, height, dpr);
    if (!mapped) return;
    const box = this._smooth(mapped);

    const colors = {
      known: "#22c55e",
      unknown: "#ef4444",
      pending: "#eab308",
      liveness: "#8b5cf6",
    };
    const color = colors[face.state] || colors.pending;

    ctx.lineWidth = 3 * dpr;
    ctx.strokeStyle = color;
    ctx.shadowColor = color;
    ctx.shadowBlur = 8 * dpr;
    const radius = 10 * dpr;
    const w = box.x2 - box.x1;
    const h = box.y2 - box.y1;
    this._roundedRectPath(ctx, box.x1, box.y1, w, h, radius);
    ctx.stroke();
    ctx.shadowBlur = 0;

    if (face.label) {
      ctx.font = `${13 * dpr}px Inter, sans-serif`;
      const textWidth = ctx.measureText(face.label).width;
      const padX = 8 * dpr;
      const labelH = 22 * dpr;
      const labelY = box.y2 + 6 * dpr;

      ctx.fillStyle = "rgba(19, 20, 23, 0.9)";
      this._roundedRectPath(ctx, box.x1, labelY, textWidth + padX * 2, labelH, 6 * dpr);
      ctx.fill();

      ctx.fillStyle = color;
      ctx.textBaseline = "middle";
      ctx.fillText(face.label, box.x1 + padX, labelY + labelH / 2);
    }
  },

  /**
   * Phase 9 — draws MULTIPLE faces in one pass (Classroom Scan mode).
   * No cross-frame smoothing here (each face is independent and faces
   * can appear/disappear between frames, unlike the single-tracked-box
   * case) — a documented simplification, not an oversight.
   */
  drawFaces(canvasEl, videoEl, faces) {
    const { width, height, dpr } = this.syncCanvasSize(canvasEl, videoEl);
    const ctx = canvasEl.getContext("2d");
    ctx.clearRect(0, 0, canvasEl.width, canvasEl.height);

    const colors = { known: "#22c55e", unknown: "#ef4444", pending: "#eab308", liveness: "#8b5cf6" };

    for (const face of faces || []) {
      if (!face.bbox) continue;
      const box = this._mapBoxToDisplay(face.bbox, videoEl, width, height, dpr);
      if (!box) continue;
      const color = colors[face.state] || colors.pending;

      ctx.lineWidth = 2.5 * dpr;
      ctx.strokeStyle = color;
      const w = box.x2 - box.x1;
      const h = box.y2 - box.y1;
      this._roundedRectPath(ctx, box.x1, box.y1, w, h, 8 * dpr);
      ctx.stroke();

      if (face.label) {
        ctx.font = `${11 * dpr}px Inter, sans-serif`;
        const textWidth = ctx.measureText(face.label).width;
        const padX = 6 * dpr;
        const labelH = 18 * dpr;
        const labelY = box.y2 + 4 * dpr;

        ctx.fillStyle = "rgba(19, 20, 23, 0.9)";
        this._roundedRectPath(ctx, box.x1, labelY, textWidth + padX * 2, labelH, 4 * dpr);
        ctx.fill();

        ctx.fillStyle = color;
        ctx.textBaseline = "middle";
        ctx.fillText(face.label, box.x1 + padX, labelY + labelH / 2);
      }
    }
  },
};

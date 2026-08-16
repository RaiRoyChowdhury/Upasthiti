/**
 * Shared webcam helper.
 *
 * Responsible ONLY for: camera permission, video preview, and frame
 * capture. It never makes a recognition/liveness/attendance decision —
 * those all come back from the server. This file just gets pixels off
 * the webcam and into a base64 JPEG string the API can consume.
 */

const Camera = {
  stream: null,
  videoEl: null,
  canvasEl: null,

  /**
   * @param {HTMLVideoElement} videoEl
   * @returns {Promise<void>}
   */
  async start(videoEl) {
    console.log("[CAMERA] initialization started");
    this.videoEl = videoEl;

    if (!videoEl) {
      console.error("[CAMERA] video element not found (camera-video)");
      throw new Error("camera-video element not found");
    }
    console.log("[CAMERA] video element", videoEl);

    if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
      console.error("[CAMERA] getUserMedia not supported in this browser");
      throw new Error("Camera access is not supported in this browser.");
    }

    console.log("[CAMERA] requesting getUserMedia");
    try {
      this.stream = await navigator.mediaDevices.getUserMedia({
        video: { width: { ideal: 960 }, height: { ideal: 720 }, facingMode: "user" },
        audio: false,
      });
    } catch (err) {
      console.error("[CAMERA] getUserMedia failed — name:", err.name, "| message:", err.message);
      console.error("[CAMERA] full error object:", err);
      if (err.name === "NotAllowedError" || err.name === "PermissionDeniedError") {
        throw new Error("Camera access is required for attendance. Please allow camera permission.");
      }
      throw new Error(`Could not access the camera (${err.name}: ${err.message}).`);
    }
    console.log("[CAMERA] getUserMedia succeeded", this.stream);

    const videoTracks = this.stream.getVideoTracks();
    console.log("[CAMERA] video track", videoTracks);
    if (videoTracks.length === 0) {
      console.error("[CAMERA] stream has no video tracks");
      throw new Error("Camera stream has no video track. Try a different camera.");
    }

    console.log("[CAMERA] assigning stream to video");
    videoEl.srcObject = this.stream;
    console.log("[CAMERA] srcObject after assignment", videoEl.srcObject);

    try {
      await videoEl.play();
      console.log("[CAMERA] video.play() succeeded", {
        readyState: videoEl.readyState,
        videoWidth: videoEl.videoWidth,
        videoHeight: videoEl.videoHeight,
        paused: videoEl.paused,
      });
    } catch (playErr) {
      // srcObject IS already attached at this point even if play() itself
      // rejects (e.g. AbortError from a rapid double-init) — log it clearly
      // rather than letting it surface as a generic "camera failed".
      console.error("[CAMERA] video.play() failed", playErr);
      throw new Error("Camera stream attached but could not start playback: " + playErr.message);
    }

    this.canvasEl = document.createElement("canvas");
    console.log("[CAMERA] initialization complete");
  },

  stop() {
    if (this.stream) {
      this.stream.getTracks().forEach((track) => track.stop());
      this.stream = null;
    }
    if (this.videoEl) {
      this.videoEl.srcObject = null;
    }
  },

  isActive() {
    return Boolean(this.stream);
  },

  /**
   * Captures the current video frame as a base64 JPEG (no data URL prefix).
   * @returns {string|null}
   */
  captureFrameBase64() {
    if (!this.videoEl || !this.canvasEl || this.videoEl.videoWidth === 0) {
      return null;
    }
    this.canvasEl.width = this.videoEl.videoWidth;
    this.canvasEl.height = this.videoEl.videoHeight;
    const ctx = this.canvasEl.getContext("2d");
    ctx.drawImage(this.videoEl, 0, 0, this.canvasEl.width, this.canvasEl.height);
    const dataUrl = this.canvasEl.toDataURL("image/jpeg", 0.85);
    return dataUrl.split(",")[1]; // strip "data:image/jpeg;base64," prefix
  },
};

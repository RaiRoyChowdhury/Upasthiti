# Computer Vision — Phase 2/3

## Pipeline overview

```
base64 frame (from browser canvas)
   -> cv/preprocessing.py       decode to BGR numpy array (OpenCV)
   -> cv/face_detector.py       InsightFace detection (+ optional embedding)
   -> cv/pose_estimation.py     approximate yaw from 5-point keypoints
   -> cv/face_quality.py        size / blur / brightness / frontal checks
   -> cv/embedding_manager.py   cosine similarity against enrolled embeddings
   -> cv/liveness.py            head-turn challenge state machine
```

Every step above is a plain function/class with no FastAPI or MongoDB
dependency — they're unit-testable with synthetic data (see
`tests/test_embedding_manager.py`, `tests/test_liveness_state_machine.py`).
Routes never call into `cv/` directly; they go through `services/`.

## Model lifecycle

`cv/face_detector.py`'s `FaceModelSingleton` loads InsightFace's
`FaceAnalysis` app exactly once per process, on first use, and reuses it for
every subsequent request. Loading it is expensive (multiple ONNX models
read from disk); reloading per-request would make recognition unusably
slow and is explicitly the wrong pattern here.

**Import-time dependency note**: `opencv-python-headless` and `numpy` are
imported at module load time (`cv/preprocessing.py`, `cv/face_quality.py`)
because decoding an image is a core, always-needed operation. `insightface`
and `onnxruntime` are imported **lazily**, only inside
`FaceModelSingleton._load_app()`, the first time a detection is actually
requested. Practically: if `opencv-python-headless` fails to install, the
whole app fails to start. If `insightface`/`onnxruntime` fail to install,
the app starts fine and every non-CV endpoint (auth, students list,
sessions, etc.) works — only the first recognition/enrollment call will
fail, with a clear error rather than a silent crash at boot.

## Thresholds — all configuration-driven

Every threshold below lives in `.env` / `config/settings.py`, read through
the single choke point `cv/thresholds.py`. Nothing in the CV or attendance
code has a hardcoded number.

| Setting | Meaning |
|---|---|
| `FACE_RECOGNITION_THRESHOLD` | Minimum cosine similarity to call a match KNOWN |
| `LOW_CONFIDENCE_THRESHOLD` | Below `FACE_RECOGNITION_THRESHOLD` but above this: LOW_CONFIDENCE (teacher review). Below this: UNKNOWN |
| `MIN_FACE_QUALITY_SCORE` | Composite 0-1 quality score required to proceed |
| `MIN_FACE_SIZE_RATIO` | Face bounding-box width ÷ frame width, minimum |
| `MAX_BLUR_VARIANCE_FLOOR` | Laplacian variance below this = rejected as too blurry |
| `MAX_YAW_DEGREES_FOR_ENROLLMENT` | Frontal-ness requirement, enrollment only |
| `LIVENESS_YAW_DELTA_DEGREES` | Minimum head-turn to count as a completed liveness challenge |
| `LIVENESS_TIMEOUT_SECONDS` | How long a liveness challenge stays open |
| `RECOGNITION_COOLDOWN_SECONDS` | How long the frontend pauses polling after a mark decision |

**None of these defaults are calibrated.** They are reasonable starting
points for a webcam at a normal indoor distance, chosen by inspection, not
by testing against real enrollment data. Before using this system with a
real cohort of students, run enrollment + recognition against your actual
camera/lighting setup and tune these values — see "Calibration" below.

## Pose estimation — an explicit approximation

`cv/pose_estimation.py` estimates head yaw from the 5 keypoints InsightFace
always returns (eyes, nose, mouth corners), rather than requiring the
optional `landmark_3d_68` sub-model. This is a **geometric heuristic**
(nose horizontal offset relative to eye midpoint, scaled by an empirical
constant), not a calibrated Euler-angle solvePnP result. It's sufficient
for "is this roughly frontal" and "did the head turn noticeably" — the only
two things this MVP needs — but it is not a precise pose measurement.
Pitch and roll are not estimated at all (returned as 0.0); nothing in this
codebase currently uses them.

## Liveness — heuristic, NOT certified anti-spoofing

**This must be stated plainly anywhere liveness is described to an end
user** — the Privacy Center (a later phase) and this doc, not buried in a
code comment.

The liveness check asks the student to turn their head slightly left or
right, then verifies the yaw actually moved past a threshold within a
timeout window. This defeats:
- A static printed photo held up to the camera
- A phone displaying a still image, held motionless

It does **not** defeat:
- A video replay of the real student turning their head
- A photo that someone physically tilts/rotates in front of the camera
- Any coordinated attempt using footage of the actual enrolled student

It is a practical, MVP-appropriate deterrent against the most casual
spoofing attempt, not a security boundary. Do not describe it to users as
"anti-spoofing" or "impossible to fool."

**Storage limitation**: liveness sessions live in an in-memory,
process-local dict (`cv/liveness.py`'s `LivenessManager`) with a TTL. This
does not survive a server restart and does not work if the app ever runs
as multiple worker processes/instances. Fine for a single-instance
MVP/hackathon deployment (matches the Render single-instance deployment
target); a real scaling requirement would need this moved to Redis or
similar — documented here as a known limitation, not silently ignored.

## Biometric privacy boundary

- `database/models/face_profile_model.py` has **no** "Public" API variant.
  It must never be returned from a route.
- Only `enrollment_service.py` and `face_recognition_service.py` are
  allowed to import `FaceProfileRepository`.
- `cv/embedding_manager.list_all_embeddings()` (via the repository) is only
  ever called from `face_recognition_service.py`, and its result is used
  purely for in-memory comparison — never serialized into a response,
  never logged.
- Enrollment/recognition failures return human-readable messages
  ("Move closer.", "Improve lighting.") — never raw vectors or model
  internals.

## Calibration

To tune thresholds for a real deployment:
1. Enroll a representative sample of students under your actual camera/lighting.
2. Run recognition attempts (both genuine matches and impostor attempts)
   and record the confidence scores returned by `/api/face/recognize`.
3. Pick `FACE_RECOGNITION_THRESHOLD` and `LOW_CONFIDENCE_THRESHOLD` to
   separate genuine-match scores from impostor scores with an acceptable
   false-accept / false-reject tradeoff for your context.
4. Re-test after any change to `INSIGHTFACE_MODEL_PACK` or camera hardware
   — thresholds are specific to the model + hardware combination.

## Known limitations (Phase 2/3)

- Single active session assumption (`session_repository.get_active_session()`)
  — one classroom camera at a time, institution-wide. Multi-classroom
  concurrent sessions are a scalability item, not implemented here.
- Liveness sessions are in-memory/single-process (see above).
- Recognition cooldown is a frontend polling pause, not a backend
  short-circuit of the CV pipeline — see `services/attendance_service.py`
  docstring for why the database's unique index remains the actual
  duplicate-prevention guarantee.
- No frame-level bounding-box overlay is drawn on the video feed in this
  phase (the name overlay is shown as text below the camera, not
  positioned over the detected face) — a nice-to-have UI polish item, not
  a functional gap.

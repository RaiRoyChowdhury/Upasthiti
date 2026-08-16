# Multi-Face Recognition & Calibration - Phase 9

## Why "Classroom Scan" is separate from Live Attendance

The single-face constraint in `cv/face_recognizer.py::extract_single_face`
(unchanged since Phase 2) exists because the attendance-marking pipeline
needs an unambiguous mapping from one detected face to one liveness
challenge to one attendance record. Running N simultaneous liveness
challenges for N people in frame is a materially different, harder
problem (each person needs their own baseline pose, their own timeout,
their own pass/fail state, and the UI needs to show N progress
indicators at once) - genuinely a separate feature, not a small
extension.

So Phase 9 adds multi-face **recognition** (`extract_all_faces()`,
`FaceRecognitionService.recognize_all_faces()`,
`POST /api/face/recognize-multi`) as a new, informational-only capability
- "who is currently in the room" - completely separate from the
attendance-marking pipeline, which is untouched. `multi-face.html`
("Classroom Scan") explicitly says on the page that it does not mark
attendance.

## What changed and what didn't

**New, additive:**
- `cv/face_recognizer.py::extract_all_faces()` - detects and quality-checks
  every face, doesn't reject at >1 face
- `FaceRecognitionService.recognize_all_faces()` - runs the same
  KNOWN/LOW_CONFIDENCE/UNKNOWN classification per face independently
- `POST /api/face/recognize-multi` - new endpoint, new response shape
  (a list, not a single result)
- `Overlay.drawFaces()` - renders N boxes in one pass (no cross-frame
  smoothing per box, since faces can appear/disappear between polls -
  a documented simplification vs. the single-tracked-box smoothing used
  on Live Attendance)

**Completely unchanged:**
- `extract_single_face()`, `FaceRecognitionService.recognize()`,
  `POST /api/face/recognize` (the one Live Attendance actually uses)
- The entire liveness state machine
- The entire attendance-marking pipeline and its idempotency guarantees

## Calibration tooling

`POST /api/face/calibration-test` (admin-only) returns the top-5 raw
cosine-similarity scores against every enrolled student for one captured
frame, plus the currently-configured thresholds - not just the single
classified outcome the normal recognize endpoint returns. This lets an
admin actually see the gap between a genuine match's score and the
next-closest impostor score before deciding whether
`FACE_RECOGNITION_THRESHOLD` needs adjusting, instead of the "edit .env
blind" workflow from Phases 2-8.

**Still does not auto-tune anything.** This is a diagnostic tool, not an
automatic calibration algorithm - the admin still edits `.env` themselves
based on what they observe here, and the new threshold still needs a
server restart to take effect (unchanged from every prior phase's
threshold-handling behavior).

## Known limitations

- Multi-face recognition has no liveness component at all - it's pure
  identification, informational only, by design (see above).
- No temporal identity smoothing across frames in Classroom Scan (a face
  recognized as "Unknown" one poll and "Known" the next isn't
  deduplicated/stabilized) - acceptable for a monitoring view, would
  matter more for a decision-making view.
- Calibration tooling captures one frame at a time manually; no batch/
  historical calibration report across many past enrollment attempts.

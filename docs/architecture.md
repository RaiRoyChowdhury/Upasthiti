# Architecture — Phase 1

## Layering

```
HTTP request
   → api/routes/*        (HTTP concerns only: request/response shape, status codes)
   → services/*           (business logic, decisions, validation)
   → database/repositories/* (the ONLY layer that talks to MongoDB)
   → database/models/*    (schemas: what's stored vs. what's exposed)
```

Routes never import Motor or issue queries directly. Services never import
`fastapi`. This boundary is what lets Phase 2's face-embedding storage plug
into the same pattern (`embedding_repository.py`) without recognition logic
knowing whether it's backed by plain MongoDB documents or, later, a
vector-search index.

## Why auth/RBAC is fully built before any CV work

Every attendance-relevant decision in later phases (who counts as a
"teacher" allowed to close a session, who can see the review center, who can
issue a manual attendance correction) depends on roles existing and being
enforced server-side. Building that scaffolding first means Phase 3+ CV
work plugs into a real permission system instead of retrofitting one later.

## Configuration-first thresholds

`FACE_RECOGNITION_THRESHOLD`, `LIVENESS_THRESHOLD`, and
`RECOGNITION_COOLDOWN_SECONDS` are declared in `config/settings.py` and
`.env.example` starting in Phase 1, even though nothing reads them yet.
This is deliberate: it forces every future phase to pull these values from
configuration instead of hardcoding a number inline the first time recognition
code gets written. The default values are **placeholders**, not calibrated
results — they must be tuned against the actual recognition model and real
enrollment data once Phase 2/3 land.

## Incremental CV rollout (Phases 2–4)

1. **Phase 2 — single-face only.** Enrollment and recognition are validated
   against one face at a time end-to-end (webcam → embedding → match) before
   any multi-face complexity is introduced. This isolates bugs to either
   "the pipeline" or "the multi-face logic" instead of debugging both at once.
2. **Phase 3 — multi-face + real-time.** Once single-face recognition is
   provably correct, the same pipeline is extended to handle multiple
   simultaneous faces and streamed over WebSocket.
3. **Phase 4 — liveness + policy + idempotency.** Liveness checks, attendance
   windows, and duplicate-prevention/cooldown logic are layered on top of a
   recognition pipeline that's already proven reliable on its own.

## Idempotent attendance marking (design, implemented in Phase 4)

Two mechanisms combine, both server-side:
- **Duplicate check**: before creating an attendance record, the service
  checks whether one already exists for `(student_id, session_id)`.
- **Recognition cooldown**: `RECOGNITION_COOLDOWN_SECONDS` prevents the
  recognition pipeline from even attempting repeated attendance-marking
  logic for the same recognized face within a short window, reducing
  redundant DB round-trips while a student is still in frame.

Neither mechanism lives in the frontend. The camera UI reflects the
server's decision; it never decides "this is a duplicate" on its own.

## Liveness — heuristic, not certified anti-spoofing

Documented explicitly here so it's never implied otherwise in UI copy,
marketing language, or code comments in later phases: the liveness checks
planned for Phase 4 (blink detection, head-turn detection via MediaPipe
landmarks) are practical, heuristic signals suitable for a classroom MVP.
They are **not** a certified biometric anti-spoofing system and will not
withstand a sophisticated presentation attack. This limitation must be
stated plainly in the Privacy Center (Phase 8) and README, not buried.

## Embedding privacy boundary

Planned for Phase 2, but the boundary is decided now: face embeddings will
sit behind their own repository (`embedding_repository.py`), accessed only
by `face_recognition_service.py`. No route will ever return an embedding in
a response body, and logging code will never serialize one. This mirrors
the `UserInDB` / `UserPublic` split already in place for passwords in
Phase 1 — the same "storage schema ≠ API schema" principle applied to
biometric data.

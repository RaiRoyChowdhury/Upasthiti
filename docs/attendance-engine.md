# Attendance Engine — Phase 3

## Pipeline (implemented in `services/attendance_service.py`)

```
1-2. Identity + liveness established upstream (face_routes.py, then the
     frontend's liveness poll loop) before mark_attendance() is ever called.
3.   Load session, confirm status == ACTIVE.
4.   (policy = "is this session currently accepting attendance")
5.   Duplicate check: existing (student_id, session_id) record?
6.   Determine PRESENT vs LATE from session.start_time + late threshold.
7.   Compute integrity score (services/integrity_service.py).
8.   Insert attendance record — idempotent, see below.
9.   Write an audit log entry.
10.  Return an AttendanceDecision (outcome + message + record + cooldown).
```

## Idempotency — two layers, one authoritative

**Layer 1 (fast path, not authoritative):** `AttendanceService` checks
`attendance_repository.get_existing(student_id, session_id)` before
attempting an insert. This handles the overwhelmingly common case cheaply
and returns a friendly `ALREADY_MARKED` decision.

**Layer 2 (authoritative):** `attendance_records` has a unique compound
index on `(student_id, session_id)` (`attendance_repository.ensure_indexes()`,
also created at app startup in `database/connection.py`). If two requests
for the same student+session race each other and both pass the Layer-1
check, only one `insert_one` succeeds — the second raises
`DuplicateKeyError`, which `AttendanceRepository.create()` translates into
`AttendanceAlreadyExistsError`, which the service catches and turns into
the same `ALREADY_MARKED` decision. The database guarantees correctness;
the pre-check is purely an optimization.

This is proven in
`tests/test_sessions_and_attendance.py::test_mark_attendance_success_then_duplicate_is_blocked`
end-to-end through the real API and service, not just asserted in a docstring.

## Present vs. Late

`AttendanceService._determine_status()` compares "now" against
`session.start_time + late_threshold_minutes`. `late_threshold_minutes`
comes from the session itself if set, otherwise falls back to
`DEFAULT_LATE_THRESHOLD_MINUTES` from configuration — never hardcoded in
the comparison logic.

## Session states and what they permit

| Status | Attendance can be marked? |
|---|---|
| `SCHEDULED` | No — `mark_attendance` returns `SESSION_NOT_ACTIVE` |
| `ACTIVE` | Yes |
| `CLOSED` | No — same `SESSION_NOT_ACTIVE` outcome, and a closed session cannot be reopened |

Only one session may be `ACTIVE` institution-wide at a time
(`SessionService.open_session` raises `ANOTHER_SESSION_ACTIVE` if one
already is) — see docs/computer-vision.md "Known limitations" for why this
is a deliberate MVP simplification, not an oversight.

## Integrity score

See `services/integrity_service.py` for the full weighted breakdown
(recognition confidence, face quality, liveness, session validity,
duplicate status — weights sum to 100). The score and its breakdown are
explicitly **not** a scientific probability of anything; they're an
internal decision-support number, returned alongside its breakdown
(`IntegrityBreakdown`) so nothing about it is opaque to a teacher looking
at a result.

## What the client never controls

The attendance-mark endpoint (`POST /api/attendance/mark`) takes a
`liveness_session_id`, not a `liveness_verified` boolean. The route looks
up that session server-side via `LivenessService`/`LivenessManager` and
checks its actual state before ever calling into `AttendanceService`. A
client cannot simply assert "liveness passed" — see
`api/routes/attendance_routes.py` docstring and
`tests/test_sessions_and_attendance.py::test_mark_attendance_rejected_without_verified_liveness`.

Likewise, `RecognitionOutcome` (KNOWN/UNKNOWN/LOW_CONFIDENCE/etc.) is
always computed server-side in `FaceRecognitionService` against
configured thresholds — the frontend only renders whichever outcome the
server returns.

## Manual override / verification

`POST /api/attendance/{id}/verify` (teacher/admin only) lets a teacher
correct a record's status, requiring a reason string, and writes a
`MANUAL_ATTENDANCE_VERIFICATION` audit event with the reason and new
status.

## Known limitations

- Review events (`ReviewService.create_event`) are not yet auto-created by
  the recognition/attendance flow — the service and API
  (`GET/POST /api/reviews/...`) are fully implemented and tested at the
  data layer, but nothing currently calls `create_event()` automatically
  when a `LOW_CONFIDENCE` or `UNKNOWN` outcome occurs during live
  recognition. Wiring that trigger is a small, contained follow-up rather
  than a design gap — the review data model and resolution workflow are
  real and tested, just not yet auto-populated from the live camera flow.

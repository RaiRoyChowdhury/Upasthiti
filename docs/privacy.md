# Privacy, Policy Engine & Data Retention - Phase 6

## Why policy is DB-backed but CV thresholds stay in .env

`database/models/policy_model.py` deliberately covers only business rules
(required attendance %, late threshold, retention day counts) - never
`FACE_RECOGNITION_THRESHOLD`, `LIVENESS_THRESHOLD`, or any other CV
threshold. Those stay in `.env`/`config/settings.py` on purpose: changing
them without recalibrating against real enrollment data (see
docs/computer-vision.md "Calibration") can silently degrade recognition
accuracy with no warning to whoever changed it. An admin casually editing
"required attendance %" from 75 to 80 has no such risk - it's a pure
business rule. That's the actual reasoning behind the split, not an
arbitrary line.

## Policy storage: singleton document

`PolicyRepository` uses a fixed `_key` value so there is always exactly
one policy document - `get_or_create()` seeds sensible defaults
(75% required attendance, 10-minute late threshold) on first read against
a fresh database, so there's no separate migration/seed script needed.

## Data retention: settings only, no automatic deletion

`PolicyUpdate.attendance_retention_days` and
`recognition_log_retention_days` are **recorded configuration values
only**. Nothing in this codebase reads them to actually delete anything.
This is a direct, deliberate choice, not an oversight - the original
project spec explicitly warns: "Do not implement automatic deletion
without clear configuration and authorization." Implementing a real purge
job is a meaningfully separate piece of work (a scheduled task, careful
handling of what "deleting" an attendance record means for audit-trail
integrity, explicit admin confirmation flow) that deserves its own
deliberate design rather than being bolted on as a side effect of a
settings page. The Settings and Privacy Center pages both say this
plainly to the admin viewing them - the UI doesn't imply an active purge
job exists when it doesn't.

## Review event auto-creation (resolves a Phase 3 limitation)

Phase 3's docs (`docs/attendance-engine.md`) documented that nothing
automatically created review events for LOW_CONFIDENCE/UNKNOWN recognition
outcomes - the review data layer existed and was tested, but wasn't wired
to the live camera flow. Phase 6 resolves this: `face_routes.py`'s
`recognize_face` now calls `review_service.create_event()` for
LOW_CONFIDENCE and UNKNOWN outcomes, and sends a notification
(`NotificationService.notify`) to the acting teacher for LOW_CONFIDENCE
specifically (the case that actually needs a human judgment call on a
candidate identity).

**Deduplication**: `/api/face/recognize` is polled roughly every 1.3
seconds while a face stays in frame, so without protection a single
lingering low-confidence face would create dozens of review events and
notifications per minute. `services/review_dedup.py`'s `ReviewDedupTracker`
is a process-local, in-memory cooldown (reusing `RECOGNITION_COOLDOWN_SECONDS`
- the same "don't reprocess a face that hasn't left frame" concept already
used elsewhere) keyed by `(session_id, outcome, candidate)`, so only the
first occurrence within that window actually creates a record. Same
architectural pattern and same documented single-process limitation as
`LivenessManager` and `ConnectionManager`.

## Notifications

In-app only - no email/SMS, matching the original scope note ("do not add
unnecessary external notification APIs unless needed"). Stored per-user in
the `notifications` collection, fetched via `GET /api/notifications`, with
an unread-count badge on the dashboard bell that clears on open
(`POST /api/notifications/read-all`).

## Enrollment deletion - already existed, now has a UI

`DELETE /api/students/{id}/enrollment` was built in Phase 2 but had no
frontend entry point. The Privacy Center page (`privacy.html`) now
surfaces it directly, with a confirmation prompt before calling it -
closing the loop between "the capability exists" and "a person can
actually use it."

## Known limitations / explicitly deferred

- **No automatic retention enforcement** (see above - intentional).
- **Demo Mode**: not implemented in this phase. The original spec listed
  it as a lower-priority, presentation-oriented feature; building a
  correctly-isolated demo dataset that can never be confused with real
  attendance records deserves dedicated attention rather than being
  squeezed in alongside six other features. Deferred, not faked.
- **Entry/exit tracking & live occupancy**: also deferred for the same
  reason - a real implementation needs its own session-state design
  (tracking a student's exit without a second camera event is genuinely
  ambiguous) rather than a token field bolted onto the existing attendance
  record.
- **No per-class student roster** - see docs/analytics.md.

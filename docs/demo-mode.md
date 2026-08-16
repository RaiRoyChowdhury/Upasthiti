# Demo Mode & Entry/Exit Tracking - Phase 10

## Demo Mode - isolation by construction, not by convention

The isolation guarantee for Demo Mode isn't "we remember to filter out
demo records" - it's structural: `demo_students`, `demo_sessions`, and
`demo_attendance` are entirely separate MongoDB collections from
`students`, `attendance_sessions`, and `attendance_records`
(`database/repositories/demo_repository.py`). No route that serves real
data (`student_routes.py`, `session_routes.py`, `attendance_routes.py`,
`analytics_routes.py`) ever queries a `demo_*` collection, and
`demo_routes.py` never queries a real one. There is no shared code path
by which a bug could leak demo data into a real view or vice versa -
they're simply different tables, read by different repositories, served
by different routes.

**Generated data is unmistakably fake**: names are literally "Demo
Student 1", "Demo Student 2", etc. - never anything that could be
confused with a real enrolled student's name. The frontend page
(`demo.html`) has a permanent diagonal-striped purple banner reading
"DEMO MODE - SYNTHETIC DATA, NOT REAL ATTENDANCE RECORDS" that cannot be
dismissed.

**Randomization**: each demo student gets a randomized base
present-probability (`random.uniform(0.55, 0.97)`), so a generated
dataset has realistic variety - some consistently-present students, some
borderline, a few clearly at-risk - useful for actually demonstrating the
risk/analytics features rather than showing uniform, boring data.

Regenerating always clears and replaces the previous demo dataset
(`DemoService.generate()` calls `clear_all()` first) - there's no
accumulation of stale demo runs.

## Entry/exit tracking - manual, not camera-automatic

`AttendanceInDB.exit_time` (optional, defaults unset) and
`POST /api/attendance/{id}/mark-exit` implement exit tracking as an
**explicit manual action** a teacher/admin takes (via the Sessions page's
"Occupancy" panel), not something the camera detects on its own.

This was a deliberate choice stated back in Phase 6/8's deferral notes:
distinguishing "a student left the room" from "a student is briefly out
of camera frame" (leaned back, turned away, someone walked in front of
them) is genuinely ambiguous without a second explicit signal, and a
wrong automatic exit determination would silently corrupt duration data
with no way for anyone to notice. Manual marking has none of that
ambiguity - a teacher clicking "Mark Exit" is an unambiguous, auditable
action (`ATTENDANCE_EXIT_MARKED` in the audit log).

## Occupancy

`GET /api/sessions/{id}/occupancy` counts attendance records with status
`present`/`late` and no `exit_time` set yet - a real query
(`AttendanceRepository.count_present_without_exit()`), not an estimate.
Divided by total enrolled students (from the existing student roster
count) for a percentage. Surfaced on the Sessions page's "Occupancy"
panel, refreshed after every exit is marked.

## Known limitations

- No automatic exit detection (see above - intentional).
- Occupancy assumes every active student is "eligible" for the session,
  same simplification noted in docs/analytics.md (no per-class roster).
- No duration analytics built on top of `exit_time` yet (e.g. "average
  time in class") - the raw data exists (`marked_at` to `exit_time`), but
  no report currently computes or displays it.

# Retention Enforcement - Phase 10

## Two independent gates, both required

The original master spec is explicit: "Do not implement automatic
deletion without clear configuration and authorization." This is
implemented as two genuinely separate conditions, checked in
`RetentionService.run_purge_cycle()`:

1. **Configuration** - `attendance_retention_days` /
   `recognition_log_retention_days` must be explicitly set to a number.
2. **Authorization** - `policy.retention_enforcement_enabled` must be
   explicitly `True` - a separate checkbox in Settings an admin must
   deliberately check. Setting a retention day-count alone does nothing;
   the enforcement checkbox does nothing without a day-count either.

Neither gate implies the other. Both were added in the same Phase 10
change specifically so it's impossible to accidentally end up with live
deletion from a setting that looked like a harmless number field.

## What actually gets deleted

- `attendance_retention_days` -> deletes `attendance_records` older than
  the cutoff (by `marked_at`).
- `recognition_log_retention_days` -> deletes `review_events` older than
  the cutoff (by `created_at`). Review events are this schema's closest
  analog to "recognition logs" - there is no separate raw per-frame
  recognition-attempt log in this codebase (Phase 3 deliberately avoided
  creating a database record for every polled frame - see
  docs/attendance-engine.md).

**Audit logs are never purged by this job.** Deleting the record of "a
purge happened" via the purge itself would undermine the ability to
verify what was deleted and when - `RETENTION_PURGE_EXECUTED` audit
entries are the accountability trail for this feature and are
intentionally exempt from the mechanism they describe.

## How it runs

A background `asyncio` task (`main.py::_retention_background_loop`)
started in the app's lifespan, sleeping `RETENTION_CHECK_INTERVAL_HOURS`
(default 24) between cycles. A failed cycle is logged and does not crash
the loop or the app - see the `except Exception` in that loop.

**For testing without waiting 24 hours**: `POST /api/policy/run-retention-now`
(admin-only, also exposed as a button in Settings) runs one cycle
immediately, subject to the exact same two gates - it does not bypass
`retention_enforcement_enabled`.

## Known limitations

- Single-process, in-memory scheduling (`asyncio.sleep` loop) - like
  `LivenessManager`/`ConnectionManager` in earlier phases, this doesn't
  coordinate across multiple server instances. Running this app as more
  than one process would run the purge cycle redundantly in each (harmless
  - deleting already-deleted records is a no-op - but wasteful).
- No dry-run mode - "Run Retention Now" actually deletes if both gates
  are satisfied. There's no preview-only mode that shows what *would* be
  deleted without deleting it.
- No per-student or per-session retention override - the cutoff applies
  uniformly to the whole `attendance_records`/`review_events` collections.

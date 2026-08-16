# Analytics & Reporting - Phase 5

## What "total sessions" means for a percentage

A student's attendance percentage is computed as
`(present + late) / countable_sessions * 100`, where `countable_sessions`
is every session that reached `ACTIVE` at least once (i.e. `ACTIVE` or
`CLOSED` status) - a `SCHEDULED` session that was created but never opened
never had a chance for anyone to attend, so it's excluded from the
denominator. See `AnalyticsService._countable_session_count()`.

**Known simplification, stated plainly**: this codebase has no formal
per-class student roster. Every active student is treated as eligible for
every countable session, regardless of `class_name`/`section`. A precise
implementation would only count a student against sessions for classes
they're actually enrolled in - that's a real gap, not hidden behind vague
language, and would be the natural next step if a roster/enrollment
concept gets added in a later phase.

## The math (and why it's real, not approximated)

All three of the trickier calculations live in `services/analytics_math.py`
as pure functions, deliberately separate from any database access, and are
directly unit-tested in `tests/test_analytics_math.py` - **and were also
executed directly in this development environment** (not just
statically reviewed) to confirm the algebra is actually correct, since
this module has zero external dependencies and could run standalone even
without pytest installed.

- **`classify_risk`**: SAFE if at/above the required %; AT_RISK if within
  10 percentage points below it; CRITICAL beyond that. The 10-point margin
  is a stated heuristic, not a derived constant.
- **`required_classes_to_reach_target`**: solves
  `(present + x) / (total + x) >= required/100` for the smallest
  non-negative integer `x`, via real algebra (shown in the function's
  docstring), not a bracketed guess. Handles the zero-history edge case
  explicitly (an empty record divides 0/0 in the general formula, so it's
  special-cased to "attend 1 class" rather than silently returning a wrong
  answer).
- **`forecast_attendance`**: `(present + N) / (total + N) * 100`, presented
  to the user with an explicit "this is a projection, not a guarantee"
  note (see `AnalyticsService.forecast_for_student`'s returned `note`
  field) - never as a certainty.

## Reports

CSV only in this phase - PDF was explicitly "if practical" in the original
scope, and CSV covers the baseline requirement without adding a new
dependency. Three report types (`services/report_service.py`), all reading
the exact same `attendance_records`/`attendance_sessions` collections the
rest of the app uses - no separate reporting datastore, no denormalized
copy that could drift from the source of truth.

Downloads go through `Api.download()` (`js/api.js`), not a plain
`<a href="/api/...">` link - a bare anchor tag can't attach the
`Authorization` header these endpoints require, so it would 401. The
helper fetches with the header and triggers the browser's save dialog via
a temporary object URL instead.

## Attendance heatmap

`AnalyticsService.student_heatmap()` (Phase 8) computes real per-calendar-day
status over a configurable window (default 90 days): `present`/`late` (had
a record that day), `absent` (a countable session existed that day but no
record for this student), or `no_class` (no countable session at all that
day). "Present wins over late" if a student somehow has records with both
statuses on the same calendar day (multiple sessions in one day) - present
is the more informative signal. Rendered client-side as a GitHub-style
contribution grid (`js/heatmap.js`), not a full interactive month-by-month
calendar with click-through - a deliberate simplification of the original
spec's "click a date to see details" to avoid building a substantial
calendar-UI component for what's fundamentally a summary visualization.

## Smart summary

`AnalyticsService.session_summary()` generates a plain-language recap of
one session - e.g. "Data Structures (CS101/A): attendance was 81%. 34 of
42 students were present, 4 arrived late, and 2 have not been marked." -
via string formatting over real counts, **not** an LLM call or any kind of
free-text generation. Every number in the sentence is one that was already
computed elsewhere in this file; the "smart" part is presentation, not the
data source. Displayed via a plain `alert()` from the Sessions page for
now - functional, not polished; a proper modal/panel would be the natural
next UI improvement.

## PDF export (Phase 8)

`fpdf2` (pure-Python, no system dependencies, low install risk) generates
simple tabular PDFs mirroring the exact same data as the CSV export -
same query methods, just a different renderer
(`services/report_service.py`'s `_build_pdf_table()`). Every
CSV-producing route now accepts `?format=csv` (default) or `?format=pdf`.
No layout/branding beyond a title and a bordered grid - this is a data
export, not a designed document.

## Known limitations

- No per-class student roster (see above) - percentage calculations treat
  every active student as eligible for every countable session.
- Class-level stats (`AnalyticsService.class_stats`) iterate every matching
  session's attendance records in a loop rather than a single aggregation
  query - fine at the row counts a single-classroom MVP produces, would
  want a proper aggregation pipeline before scaling to many concurrent
  classes with years of history.
- Heatmap is a summary grid, not an interactive calendar with per-day
  click-through (see above).
- Session summary is displayed via a plain `alert()`, not a styled panel.

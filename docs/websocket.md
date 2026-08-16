# Real-Time WebSocket Architecture — Phase 4

## Architecture diagram

```
Browser (attendance.html)
   |
   |-- HTTP polling loop (unchanged from Phase 3)
   |     captures frame -> POST /api/face/recognize
   |     -> POST /api/face/liveness/start|check
   |     -> POST /api/attendance/mark
   |     -> renders result-panel + bounding box directly from each response
   |     This is still the ONLY thing that makes attendance decisions.
   |
   `-- WebSocket connection (NEW, additive)
        js/websocket.js  ->  wss://.../ws/attendance/{session_id}?token=JWT
                                    |
                             FastAPI WS route (api/routes/websocket_routes.py)
                                    |  auth + RBAC + session-exists checks
                                    v
                        websocket/connection_manager.py (ConnectionManager)
                                    ^
                                    |  broadcast_to_session(session_id, event)
                                    |
        REST routes (face_routes.py, attendance_routes.py, session_routes.py)
        call manager.broadcast_to_session(...) AFTER their existing
        service call has already completed -- never before, never instead of.
```

## Business logic rule (the one that matters most)

```
ROUTE -> SERVICE -> BUSINESS LOGIC -> DATABASE -> EVENT PUBLISHING
```

**Not** `WEBSOCKET -> DATABASE -> ATTENDANCE`. The WebSocket layer cannot
mark attendance, decide an identity, or pass a liveness check — it only
reports decisions the existing Phase 2/3 services already made and
persisted. Every event-publishing call site in this codebase sits
immediately after a service call whose result is already final
(`attendance_service.mark_attendance()`, `session_service.open_session()`,
etc.) — grep any of the three modified route files (`face_routes.py`,
`attendance_routes.py`, `session_routes.py`) and `manager.broadcast_to_session(...)`
only ever appears after the service call it's reporting on, never before.

## Authentication

Browsers cannot set custom headers (like `Authorization: Bearer ...`) on a
native WebSocket handshake — there's no API for it. The standard,
documented workaround is to pass the JWT as a query parameter instead:

```
wss://host/ws/attendance/{session_id}?token=<jwt>
```

`get_current_user_ws()` (added to `api/dependencies/auth_dependency.py`,
alongside the existing HTTP `get_current_user`) decodes and validates this
token using the exact same `decode_access_token()` and `UserRepository`
that HTTP auth uses — no separate auth mechanism, no duplicated validation
logic.

**Role check**: only `admin`/`teacher` may connect — matches every other
live-attendance-adjacent endpoint's RBAC. A student token is rejected with
close code `4403` before the connection is ever accepted. A missing/invalid
token gets `4401`. A `session_id` that doesn't exist gets `4404`. All three
checks happen before `websocket.accept()` is called, so a rejected client
never gets a "connected" event.

## Session scoping

`ConnectionManager` tracks sockets in a `dict[session_id, set[WebSocket]]`.
`broadcast_to_session(session_id, event)` only iterates the sockets under
that exact key — there is no "broadcast to everyone" method, and no
mechanism by which session A's events could reach session B's listeners.
This is directly tested in
`tests/test_connection_manager.py::test_broadcast_is_scoped_to_session_id`.

## Event types

| Event | Published from | When |
|---|---|---|
| `recognition.detected` | `face_routes.py` recognize | outcome == KNOWN |
| `recognition.low_confidence` | `face_routes.py` recognize | outcome == LOW_CONFIDENCE |
| `recognition.unknown` | `face_routes.py` recognize | outcome == UNKNOWN |
| `liveness.started` | `face_routes.py` liveness/start | always (if `session_id` provided) |
| `liveness.progress` | `face_routes.py` liveness/check | state == WAITING_FOR_ACTION |
| `liveness.passed` | `face_routes.py` liveness/check | state == VERIFIED |
| `liveness.failed` | `face_routes.py` liveness/check | state == TIMEOUT |
| `attendance.marked` | `attendance_routes.py` mark | outcome == MARKED |
| `attendance.already_marked` | `attendance_routes.py` mark | outcome == ALREADY_MARKED |
| `attendance.rejected` | `attendance_routes.py` mark | outcome == SESSION_NOT_ACTIVE |
| `session.opened` / `session.closed` | `session_routes.py` | after the session service call succeeds |

Deliberately **not** published: `NO_FACE`, `MULTIPLE_FACES`, `POOR_QUALITY`
recognition outcomes — these happen on essentially every polling tick while
someone adjusts position, and publishing them would spam every connected
listener every ~1.3 seconds for no informational gain (spec section 24,
"no event spam"). `review.created` is not published because nothing in
this codebase automatically creates review events yet — see
`docs/attendance-engine.md` "Known limitations", unchanged from Phase 3.

Every event has this shape (`websocket/events.py::build_event`):
```json
{ "event": "attendance.marked", "timestamp": "2026-...", "session_id": "...", "...type-specific fields": "..." }
```
Never an embedding, never a raw frame — enforced by convention (every call
site passes plain IDs/strings/numbers) and spot-checked in
`tests/test_websocket_events.py`.

## Bounding box: dual-source by design

The face bounding box shown on the live camera comes from **the HTTP
`/api/face/recognize` response's new optional `bbox` field**, drawn locally
on every poll tick — **not** from a WebSocket event. This is deliberate:
per spec section 26 ("WebSockets must not be a single point of failure for
attendance business logic/UI"), the box that matters most — the one on
your own camera — must keep working even if the WebSocket never connects.
The same `recognition.detected`/`recognition.unknown` events are also
broadcast over the socket, primarily useful for a second connected client
(e.g. someone else watching that session), not for the primary camera view.

## Coordinate mapping (`js/overlay.js`)

The bbox from the backend is in the **original captured frame's native
pixel coordinates** (`video.videoWidth` x `video.videoHeight`), but the
`<video>` element is displayed via CSS `object-fit: cover`, which scales
and crops rather than stretches. `Overlay._mapBoxToDisplay()` replicates
that exact scale+crop math (`scale = max(containerW/nativeW,
containerH/nativeH)`, then centers and crops) so a box computed from
backend pixel coordinates lands on the actual displayed face position, not
a stretched/offset one.

**Mirroring**: rather than manually flip the x-axis (error-prone — easy to
get backwards), the overlay `<canvas>` shares the exact same CSS
`transform: scaleX(-1)` as the `<video>` element (see `camera.css`
`.overlay-canvas`). Both get mirrored identically by the shared transform,
so all drawing code works in plain, unmirrored coordinates.

**Smoothing**: `Overlay._smooth()` does simple exponential interpolation
between the previous displayed box and the new one (`smoothingFactor:
0.35`) — enough to remove visible jitter between polling ticks without a
full object-tracking framework (spec section 17: "do not add a huge
tracking framework unless necessary").

## Known limitations

- **Single face only.** The backend's recognition pipeline
  (`cv/face_recognizer.py::extract_single_face`) is single-face by design
  since Phase 2 — this phase does not change that. `Overlay.drawFace()`
  accepts one face object, not an array; true multi-face bounding-box
  rendering would need the CV pipeline itself extended first, which is out
  of scope here (spec section 37, "no new face recognition model/algorithm
  in Phase 4").
- **In-memory connection manager.** Like `LivenessManager` (Phase 3),
  `ConnectionManager` is process-local. Fine for a single-instance
  deployment; would need a pub/sub backend (Redis, etc.) to work across
  multiple server processes/instances.
- **No message-level backpressure.** A very high-frequency broadcast
  scenario isn't specifically load-tested here — acceptable for a
  single-classroom MVP's actual event rate (at most a few events per
  second per session).
- **Reconnect backoff caps at 15s**, exponential from 1s
  (`js/websocket.js`). No maximum retry count — matches spec section 25
  ("do not create infinite *aggressive* reconnect loops"; this backs off
  rather than hammering, but does keep trying indefinitely, which is the
  right default for a page a teacher leaves open all class period).

## Troubleshooting

- **WS status pill stuck on "Connecting..."**: check the browser console
  for `[WS]` logs — they log the exact URL (token redacted), every state
  transition, and the close code/reason if the server rejects the
  connection. Close codes `4401`/`4403`/`4404` map to auth/role/session
  errors respectively (see table above) and are deliberately **not**
  retried — reconnecting won't fix a bad token or wrong role.
- **Bounding box misaligned**: almost always a stale `Overlay._lastBox` from
  a previous face size — should self-correct within a couple of frames
  due to smoothing; if it's consistently wrong, check that the video
  element's `object-fit` in `camera.css` is still `cover` (the coordinate
  math assumes that specific mode).

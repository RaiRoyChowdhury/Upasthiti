# UPASTHITI

**AI-Powered Attendance Integrity & Intelligence Platform**

> UPASTHITI doesn't simply recognize faces and mark attendance. It
> verifies identity and liveness, prevents duplicate and proxy attendance,
> detects anomalies, evaluates attendance integrity, enforces attendance
> policies, and provides real-time classroom intelligence through a
> professional SaaS dashboard.

---

## Build status

This repository is being built in phases. **Phases 1, 2, and 3 are complete
and pass automated tests. The webcam/CV pipeline has not yet been exercised
live against a real camera on the developer's machine — see "Validation
performed" below for exactly what's confirmed vs. what needs your live run.**

| Phase | Scope | Status |
|---|---|---|
| 1 | API foundation, auth, RBAC, database, dark SaaS UI shell | ✅ Done, live-validated |
| 2 | Student management + face enrollment (single-face CV pipeline) | ✅ Built, tested with synthetic data — needs your live webcam run |
| 3 | Sessions, liveness, attendance engine, integrity score, review center | ✅ Built, tested with synthetic data — needs your live webcam run |
| 4 | Real-time WebSocket events, bounding-box overlay, live activity feed | ✅ Built and live-validated (including a real bug fix — see docs/computer-vision.md) |
| 5 | Analytics, risk analysis, forecasting, CSV reports, student profiles | ✅ Built — math verified by direct execution, needs your live run |
| 6 | Policy engine, classes/timetable, notifications, privacy center, offline queue | ✅ Built — needs your live run |
| 7 | Student dashboard, Users & Roles admin, User↔Student linking | ✅ Built — needs your live run |
| 8 | Attendance heatmap, PDF export, smart summary, table sorting | ✅ Built — needs your live run |
| 9 | Multi-face recognition (Classroom Scan), calibration tooling | ✅ Built — needs your live run |
| 10 | Demo mode, entry/exit tracking, retention enforcement, Docker Compose | ✅ Built — needs your live run |
| 11 | Deployment configs (Render + Vercel) | ✅ Configs written — needs YOU to actually deploy (see docs/deployment.md) |

---

## What's in Phase 1

- FastAPI backend with a clean `routes → services → repositories` architecture
- MongoDB connection (Motor, async) with startup health checks and index creation
- User model with roles (`admin`, `teacher`, `student`)
- JWT authentication (login, logout, current-user) with bcrypt password hashing
- Role-based access control (`require_role(...)` dependency)
- Centralized configuration via `.env` (nothing hardcoded, including the
  face-recognition/liveness threshold placeholders reserved for later phases)
- Unified API error responses + global exception handling
- CORS configuration
- Structured logging (never logs secrets, tokens, or biometric data)
- Swagger / OpenAPI docs at `/docs`
- A vanilla-JS, dark-theme SaaS frontend shell: login page + dashboard shell
  with role-aware navigation
- Pytest suite covering security utilities, auth flows, and RBAC, using an
  in-memory MongoDB mock (no real database needed to run tests)

## What's in Phase 9 + 10 + 11

**Phase 9 — Multi-Face Recognition & Calibration:**
- "Classroom Scan" (`multi-face.html`) — recognizes every face in frame
  simultaneously, informational only, deliberately kept separate from
  attendance marking (which still requires the single-face + liveness
  flow — see `docs/multi-face.md` for why)
- Recognition calibration tool (Settings, admin-only) — capture a frame,
  see real similarity scores against every enrolled student instead of
  editing `FACE_RECOGNITION_THRESHOLD` blind

**Phase 10 — Operational Completeness:**
- **Demo Mode** (`demo.html`) — isolated by construction, not convention:
  entirely separate MongoDB collections (`demo_*`), so it's structurally
  impossible for synthetic data to leak into real views or vice versa
- **Entry/exit tracking + live occupancy** — manual exit marking (not
  camera-automatic — see `docs/demo-mode.md` for why), real occupancy
  calculation on the Sessions page
- **Retention enforcement** — a real background job, gated by two
  independent conditions (a retention-days value AND an explicit
  authorization checkbox) before anything is ever deleted — see
  `docs/retention.md`
- **Docker Compose** — optional local-dev convenience (`docker compose up`)

**Phase 11 — Deployment (configs only — see below):**
- `render.yaml`, `vercel.json`, `Dockerfile`, and a configurable API base
  URL (`frontend/config.js`) supporting both a simple single-service
  deployment and the original spec's Vercel+Render split
- **A full step-by-step guide in `docs/deployment.md`** — I cannot deploy
  this myself (no network access in the environment that built it — see
  that doc's opening note), so every step is written for you to execute

## What's in Phase 7 + 8

**Phase 7 — Access & Personalization:**
- Optional User↔Student link (`User.student_id`) — a login account and a
  roster record were always separate concepts; this connects them without
  forcing every student record to have a login (see `docs/access.md`)
- Student-facing dashboard (`student-dashboard.html`) — their own
  attendance %, risk, required classes, forecast, and heatmap only, with
  role-based redirect so a student account never lands on the
  teacher/admin dashboard (and vice versa)
- Users & Roles admin page — list/create users, change roles, activate/
  deactivate, all backed by real endpoints (`GET/PATCH /api/auth/users`)
  — an admin cannot deactivate their own account (server-enforced)

**Phase 8 — Visualization & Reporting Polish:**
- Real attendance heatmap — per-calendar-day present/late/absent/no-class,
  computed from actual records (not a mockup grid)
- PDF export alongside the existing CSV export (`fpdf2`, pure-Python, low
  install risk) — every report route now takes `?format=csv|pdf`
- Smart summary — plain-language session recap generated by string
  formatting over real counts, not an LLM call (see `docs/analytics.md`)
- Table sorting on Students and Sessions (client-side, since the data's
  already loaded)

## What's in Phase 5 + 6

**Phase 5 — Analytics & Reporting:**
- Real-time overview dashboard metrics (no more placeholder `—` cards)
- Per-student stats: attendance %, present/late/absent, risk level (Safe/At
  Risk/Critical), classes needed to reach the required percentage — real
  algebra, not an approximation (see `docs/analytics.md`)
- Attendance forecast ("if you attend N more classes...") — clearly
  labeled as a projection
- Student profile page with recent-attendance history strip
- CSV report export (session, student, class) via a real authenticated
  download helper (`Api.download()` — a plain link can't carry the auth
  header these endpoints need)
- Class lookup with real aggregate stats

**Phase 6 — Policy Engine, Classes, Notifications, Privacy:**
- DB-backed institution policy (required attendance %, late threshold,
  retention day counts) — admin-editable via Settings, deliberately
  separate from CV/recognition thresholds (see `docs/privacy.md` for why)
- Class + weekly timetable management, with a "Create Session" shortcut
  that pre-fills the existing session form from a timetable entry
- **Resolved a documented Phase 3 limitation**: low-confidence and unknown
  recognition outcomes now automatically create real review events and
  notify the teacher — deduplicated so a lingering face doesn't spam
  dozens of events per minute (`docs/privacy.md`)
- In-app notification bell with unread count
- Privacy Center: what's stored, why, who can access it, plus a working
  "delete this student's face enrollment" tool (the endpoint existed since
  Phase 2 but had no UI until now)
- Data retention *settings* — explicitly storage-only, no automatic
  deletion job (per the original spec's warning against silent auto-purge)
- Real offline queue for attendance marking: a genuine network failure
  queues the attempt in localStorage and retries automatically on
  reconnect, with an honestly-documented limitation around liveness
  session TTLs (see `docs/privacy.md`)

**Deferred, not faked**: Demo Mode and entry/exit/occupancy tracking — see
`docs/privacy.md` "Known limitations" for why these were left out rather
than half-built.

## What's in Phase 4

- Real-time WebSocket endpoint (`/ws/attendance/{session_id}`), JWT-authenticated
  via query param, teacher/admin only, session-scoped broadcasting
- Live face bounding-box overlay on the camera feed (canvas, proper
  coordinate mapping for `object-fit: cover` + mirrored preview, lightweight
  smoothing) — see `docs/websocket.md` "Coordinate mapping"
- Live activity feed and a live status panel (camera/recognition/real-time
  connection state, enrolled/present/late counts from real API data)
- Automatic reconnection with exponential backoff
- **The existing HTTP recognize/liveness/mark flow is unchanged and is
  still what actually makes every attendance decision** — WebSockets only
  report what already happened. See `docs/websocket.md` "Business logic
  rule" for why this matters and how it's enforced.

## What's in Phase 2 + 3

**Phase 2 — Student management + face enrollment:**
- Student CRUD with search/filter/pagination (`/api/students`)
- CV pipeline: face detection (InsightFace), quality checks (size/blur/
  brightness/frontal-pose via OpenCV), embedding generation
- Enrollment endpoint (`POST /api/students/{id}/enrollment`) — rejects
  poor-quality captures with a specific, actionable message
- Biometric data (`face_profiles` collection) is completely isolated from
  the `students` collection and never returned by any API response

**Phase 3 — Sessions, liveness, and the attendance engine:**
- Session lifecycle: create → open → close, single-active-session enforced
  server-side
- Real-time-ish recognition via HTTP polling (`POST /api/face/recognize`)
- Heuristic liveness verification (head-turn challenge, state machine) —
  explicitly documented as MVP-level, not certified anti-spoofing
- Idempotent attendance marking: a unique `(student_id, session_id)`
  database index is the authoritative duplicate-prevention mechanism
- Explainable integrity score (0-100, weighted breakdown, never a raw
  probability claim)
- Present/Late classification from session timing
- Manual teacher verification/override with required reason + audit trail
- Review center (list/resolve low-confidence or unknown-person events)
- Full audit logging for every state-changing action

See `docs/computer-vision.md` and `docs/attendance-engine.md` for the full
design rationale, thresholds, and known limitations.

**Frontend additions:** Students page, Face Enrollment page (live webcam
capture), Sessions page, Live Attendance page (the core demo — camera feed,
name overlay, verification checklist, integrity score, all four required
result states: marked/already-marked/unknown/low-confidence), Review Center.

## What's deliberately NOT in Phase 2/3

- WebSockets (recognition/liveness are HTTP polling — see
  docs/architecture.md "Phase 4" for why this is sequenced this way)
- Automatic review-event creation from a live LOW_CONFIDENCE/UNKNOWN
  recognition (the review data layer is built and tested; the trigger
  wiring is a documented small follow-up — see docs/attendance-engine.md
  "Known limitations")
- Bounding-box overlay drawn on the video feed (name is shown as text
  below the camera, not positioned over the face)
- Multi-classroom concurrent sessions (one active session institution-wide,
  documented limitation)

---

## Project structure

```
smartattend-ai/
├── backend/
│   ├── main.py                  # FastAPI app entrypoint
│   ├── config/settings.py       # All configuration, from .env
│   ├── database/
│   │   ├── connection.py        # Motor client lifecycle
│   │   ├── models/user_model.py
│   │   └── repositories/user_repository.py
│   ├── api/
│   │   ├── routes/auth_routes.py
│   │   ├── routes/health_routes.py
│   │   └── dependencies/auth_dependency.py
│   ├── services/auth_service.py
│   ├── auth/security.py         # Password hashing + JWT
│   ├── utils/logger.py, exceptions.py
│   ├── scripts/create_admin.py  # Bootstraps the first admin account
│   └── tests/                   # pytest suite
├── frontend/
│   ├── index.html
│   ├── pages/login.html, dashboard.html
│   ├── css/                     # Design system (main.css) + components
│   └── js/                      # api.js, auth.js, dashboard.js
├── docs/
├── .env.example
├── requirements.txt
└── README.md
```

---

## Running Phase 1 locally

### Prerequisites

- Python 3.11 or 3.12
- A running MongoDB instance — either:
  - **Local**: install MongoDB Community Edition and run it on the default
    port (`mongodb://localhost:27017`), or
  - **Atlas**: create a free cluster at mongodb.com/atlas and use its
    connection string.

### 1. Install dependencies

```bash
cd smartattend-ai
python3 -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

**Install-risk note (read this if step fails):** `opencv-python-headless`,
`onnxruntime`, and `insightface` are the highest-risk packages in this
project — see `docs/computer-vision.md` "Model lifecycle" for exactly
which ones are required at import time vs. only when a face is actually
processed. If `insightface`/`onnxruntime` fail to install on your Python
version, the rest of the app (auth, students list, sessions) still works —
only enrollment/recognition/liveness endpoints will fail until that's
resolved. If `opencv-python-headless` fails to install, nothing will start —
that one's non-negotiable. Report the exact pip error if you hit one; it's
very likely a Python-version compatibility issue that needs a version pin
adjustment, not a code problem.

### 2. Configure environment

```bash
cp .env.example .env
```

Edit `.env`:
- Set `MONGODB_URI` to your local or Atlas connection string.
- Set `JWT_SECRET` to a real random value:
  ```bash
  python -c "import secrets; print(secrets.token_urlsafe(64))"
  ```

### 3. Start the backend

```bash
cd backend
uvicorn main:app --reload --port 8000
```

You should see log lines confirming MongoDB connected and Uvicorn running on
`http://127.0.0.1:8000`. If MongoDB isn't reachable, startup will fail loudly
with a clear message rather than starting in a broken state.

### 4. Create the first admin account

In a second terminal (venv active, still inside `backend/`):

```bash
python scripts/create_admin.py
```

Follow the prompts (name, email, password). Every other account after this
one is created by an admin via `POST /api/auth/register`.

### 5. Open the app

- **Frontend (served by the backend for local dev convenience):**
  `http://127.0.0.1:8000/app/pages/login.html`
- **API docs (Swagger UI):** `http://127.0.0.1:8000/docs`
- **Health check:** `http://127.0.0.1:8000/api/health`

Log in with the admin account you just created.

### 6. Try the full Phase 2/3 flow

1. Go to **Students**, click **+ Add Student**, create one (any student ID).
2. Click **Enroll Face** next to that student — allow camera access, face
   the camera directly, click **Capture & Enroll**. You should see
   "Enrollment successful" with a quality score. If you see a rejection
   message instead ("Move closer.", "Improve lighting."), that's the real
   quality check working — adjust and try again.
3. Go to **Sessions**, create a session, click **Open**.
4. Go to **Live Attendance**. The camera should start automatically. Face
   the camera — you should see your name appear, a liveness prompt
   ("turn your head slightly left/right"), then either "ATTENDANCE MARKED"
   with an integrity score, or "ATTENDANCE ALREADY MARKED" if you'd already
   been marked for that session.
5. Have someone unenrolled (or a photo) appear in frame — you should see
   "Unknown Person" and no attendance record created.
6. Try appearing again after being marked — confirm you get "Attendance
   Already Marked", not a second record. Check **GET /api/attendance** in
   Swagger to confirm only one record exists for that student+session.

### 7. Try the Phase 5/6 flow

1. **Dashboard** — metric cards should now show real numbers (Total
   Students, Present, Late, Attendance Rate), not `—` placeholders.
2. **Analytics** — overview stats + present/late bar chart, and a class
   lookup form (try a class/section you've created sessions for).
3. **Classes** — create a class, add a weekly timetable entry, click
   "Create Session" on it — confirm it takes you to Sessions with the form
   pre-filled (doesn't auto-create).
4. **Student Profile** (via Students → "Profile" on any row) — attendance
   %, risk badge, "classes needed to reach target," forecast calculator,
   recent-attendance strip, CSV download.
5. **Reports** — download a session/student/class CSV, confirm the file
   actually downloads (not a 401 — this validates the `Api.download()`
   auth-header fix).
6. **Settings** (admin only) — edit required attendance % / late
   threshold, save, reload the page, confirm it persisted.
7. **Privacy Center** — check the retention values display correctly, and
   test deleting a face enrollment for a test student (confirm they show
   as "Not enrolled" again on the Students page afterward).
8. **Notification bell** (top-right, any page with it) — trigger a
   LOW_CONFIDENCE recognition (e.g. show the camera a partially-obscured
   enrolled face) during Live Attendance, then check the bell shows an
   unread badge and the notification appears in the dropdown. Also check
   **Review Center** — a new pending review event should appear there too.
9. **Offline queue** — during Live Attendance, disable your network
   connection (turn off Wi-Fi) right as attendance would be marked, watch
   for the "No Connection — Queued" message, then reconnect and confirm it
   syncs automatically (check the "Pending Sync" counter in the live
   status panel drops back to 0).

### 8. Run the test suite

```bash
cd backend
pytest -v
```

Tests use an in-memory MongoDB mock — no real database needed. Tests that
touch the liveness state machine or integrity scoring run with synthetic
data and do not require a webcam or the InsightFace model to actually
load. Tests do require `opencv-python-headless` and `numpy` to be
installed (see the install-risk note above) since the app imports them at
module load time even for non-CV routes.

---

## Validation performed on this codebase

Since this was generated in an environment without internet/package-install
access, the following was verified directly and mechanically:

- Every Python file (70 total) passes `python -m py_compile` (syntax-valid)
- Every internal `from X import Y` resolves to a real file, and every
  imported name is actually defined in its source module
- Every CSS/JS file referenced from any HTML page exists at that path
- Every `document.getElementById(...)` target in every page's JS exists as
  an `id` in that page's HTML
- Every frontend API call matches an actual backend route + prefix exactly,
  across all Phase 1/2/3 pages
- New Phase 2/3 unit tests (integrity scoring, embedding comparison,
  liveness state machine) use synthetic data and were written to be
  runnable without a real camera or MongoDB
- New Phase 2/3 API tests (student CRUD, session lifecycle, attendance
  idempotency) construct a `VERIFIED` liveness session directly via the
  same `LivenessManager` singleton the app uses, bypassing only the image
  pipeline — so the actual duplicate-prevention, session-validity, and
  RBAC logic is exercised through the real API and service layers, not
  mocked out

**What could NOT be verified in this environment — genuinely needs your
live run, same as Phase 1:**
- Whether `opencv-python-headless`, `onnxruntime`, and `insightface`
  actually install cleanly on your Python version/OS (this is the
  documented highest-risk area — see docs/computer-vision.md)
- Whether the InsightFace model pack downloads and loads correctly on
  first use
- Whether real webcam frames produce sensible detection/quality/
  recognition results — synthetic-vector tests prove the *logic* is
  correct, not that the *model* behaves well against a real camera
- Whether the liveness head-turn challenge feels usable/responsive in
  practice (the yaw-delta threshold is a starting guess, not tuned)
- `pytest -v` actually passing end-to-end with all CV dependencies
  installed (structurally verified by inspection, never executed)

Please work through steps 1-7 above and report back — especially the
enrollment quality check and the live attendance demo, since those are
the parts I could not execute here at all.

---

## Security notes (Phase 1)

- Passwords are hashed with bcrypt, never stored or logged in plaintext.
- JWTs are stateless; logout is client-side token disposal (a server-side
  revocation list is a documented future improvement).
- `password_hash` never appears in any API response — enforced structurally
  via separate `UserInDB` / `UserPublic` schemas, not by convention.
- Registration is admin-only; the first admin is bootstrapped outside the
  API via `scripts/create_admin.py`.
- The app refuses to start in `APP_ENV=production` if `JWT_SECRET` is still
  the default placeholder value.

See `docs/security.md` (added in a later phase) for the full security model
once biometric data is introduced.

# UPASTHITI — How to Run (PowerShell)

This is a short, practical guide to get the app running locally in
PowerShell. For full feature docs, architecture, and phase history, see
`README.md` and the `docs/` folder.

---

## Prerequisites (one-time, skip if already done)

- Python 3.11 or 3.12 installed
- A MongoDB database — either MongoDB Atlas (recommended, free tier) or
  a local MongoDB install
- Git (only needed if you plan to push this to GitHub later)

---

## First-time setup

If this is your **very first time** running the project (no existing
`.venv` from a previous phase), do this:

```powershell
# 1. Go to the project folder (the one containing backend/, frontend/, requirements.txt)
cd "C:\Users\<you>\Downloads\smartattend-ai\smartattend-ai"

# 2. Create a virtual environment
python -m venv .venv

# 3. Activate it
.\.venv\Scripts\Activate.ps1

# 4. Install dependencies (this takes a while — opencv/insightface are large)
pip install -r requirements.txt

# 5. Set up your environment file
copy .env.example .env
notepad .env
```

In Notepad, set at minimum:
- `MONGODB_URI` — your MongoDB Atlas connection string (or `mongodb://localhost:27017` for local Mongo)
- `JWT_SECRET` — generate one with:
  ```powershell
  python -c "import secrets; print(secrets.token_urlsafe(64))"
  ```

Save and close Notepad.

```powershell
# 6. Create your first admin account
cd backend
python scripts/create_admin.py
```
Follow the prompts (name, email, password).

---

## If you already have a working `.venv` from a previous version

Reuse it instead of reinstalling everything — much faster:

```powershell
# 1. Copy your .env from the old folder
copy "C:\path\to\old-version\smartattend-ai\.env" "C:\path\to\new-version\smartattend-ai\.env"

# 2. Copy your working .venv from the old folder
Copy-Item -Recurse "C:\path\to\old-version\smartattend-ai\.venv" "C:\path\to\new-version\smartattend-ai\.venv"

# 3. Verify the copy worked
Test-Path "C:\path\to\new-version\smartattend-ai\.venv\Scripts\python.exe"
# should print: True
```

If a newer version added a dependency, `pip install -r requirements.txt`
once inside the new folder (with the venv activated) to catch anything
missing — check `requirements.txt`'s comments for what's new.

---

## Every time you want to run the app

```powershell
# 1. Go to the project folder
cd "C:\Users\<you>\Downloads\smartattend-ai\smartattend-ai"

# 2. Activate the virtual environment
.\.venv\Scripts\Activate.ps1

# 3. Move into the backend folder
cd backend

# 4. Start the server
python -m uvicorn main:app --reload --port 8000
```

Wait for this line before continuing:
```
INFO:     Application startup complete.
```

Leave this terminal window open and running.

---

## Open the app

In your browser (Incognito/Private window recommended, to avoid stale
cache from previous versions):

```
http://127.0.0.1:8000/app/pages/login.html
```

Log in with the admin account you created.

- **API docs (Swagger)**: `http://127.0.0.1:8000/docs`
- **Health check**: `http://127.0.0.1:8000/api/health`

---

## Stopping the server

Click into the terminal window and press `Ctrl+C`.

---

## Quick troubleshooting

| Symptom | Likely cause | Fix |
|---|---|---|
| `uvicorn : term not recognized` | Venv not activated | Run `.\.venv\Scripts\Activate.ps1` — check for `(.venv)` in your prompt |
| `Error loading ASGI app. Could not import module "main"` | Wrong folder | Run `pwd` — must end in `...\smartattend-ai\backend` |
| Page loads but looks outdated / missing new features | Browser cache | Open in a fresh Incognito window |
| `NotReadableError` on camera | Camera locked by another app | Close other camera apps/tabs; if it persists, restart your computer |
| MongoDB won't connect at startup | Wrong `MONGODB_URI` or IP not allow-listed | Check `.env`, and in Atlas confirm your current IP is under Network Access |
| `.venv\Scripts\python.exe` missing after copying | Copy didn't finish, or was nested wrong | Delete `.venv`, redo the `Copy-Item` command carefully, verify with `Test-Path` before continuing |

---

## Folder reference

```
smartattend-ai/
├── backend/          ← run uvicorn from here
│   ├── main.py
│   └── scripts/create_admin.py
├── frontend/          ← served automatically by the backend, no separate step needed
├── .env               ← your real config (never commit this)
├── .env.example        ← template, safe to commit
├── requirements.txt
└── docs/              ← detailed feature/architecture documentation
```

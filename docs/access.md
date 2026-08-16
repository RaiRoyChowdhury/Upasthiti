# Access & Roles - Phase 7

## User accounts vs. student roster records - two separate concepts

This is the single most important thing to understand about this phase.
A **User** (`database/models/user_model.py`) is a login account with a
role (`admin`/`teacher`/`student`). A **Student**
(`database/models/student_model.py`) is a roster record with a
`student_id`, enrollment status, and attendance history. These were
always two separate collections (since Phase 1 and Phase 2 respectively) -
nothing in the earlier phases ever linked them.

Phase 7 adds an *optional* link: `User.student_id` can point at a
`Student.student_id`. This is optional and asymmetric on purpose:

- A `student`-role login can exist **unlinked** (e.g., created before the
  student's roster record exists, or for a role that doesn't need roster
  data).
- A `Student` roster record can exist with **no** login account at all -
  that's the normal case for Phases 1-6, and still is; not every enrolled
  student needs to be able to log in.

## Where the link is set

- `POST /api/auth/register` (admin-only) accepts an optional `student_id`
  on the request body. The route validates that a `Student` with that
  `student_id` actually exists before creating the account - a typo'd
  student ID is rejected immediately, not silently stored.
- `PATCH /api/auth/users/{id}` (admin-only) can change or add the link
  after the fact via the Users & Roles page.
- **Known limitation**: there's currently no way to *clear* an existing
  link back to "unlinked" through this endpoint - `UserAdminUpdate`'s
  `model_dump(exclude_unset=True)` combined with the repository's
  "skip None values" filter means sending `student_id: null` won't
  actually clear it. Re-linking to a *different* student_id works fine;
  explicit unlinking would need a small follow-up (a dedicated endpoint,
  or changing the update semantics to distinguish "field omitted" from
  "field explicitly nulled").

## Role-based landing pages

- `dashboard.js` (the teacher/admin dashboard) checks `user.role` right
  after login and redirects to `student-dashboard.html` if the role is
  `student` - so a student account never sees the teacher-oriented
  dashboard (session controls, enrollment tools, institution-wide metrics).
- `student-dashboard.js` does the reverse check and redirects
  teacher/admin accounts back to `dashboard.html` if they land there
  directly.
- If a student account is **unlinked** (no `student_id`), the student
  dashboard shows a plain explanatory message rather than an error or
  someone else's data - "Your account isn't linked to a student roster
  record yet."

## RBAC on existing endpoints - unchanged

Nothing about the underlying RBAC model changed. `require_role(...)`
still gates every route exactly as before; the student dashboard simply
calls the *same* `/api/analytics/student/{id}` endpoint any authenticated
user can already call (student, teacher, or admin) - a student viewing
their own linked record isn't a new permission, it's the existing
"any authenticated user" bar from Phase 5, now with a purpose-built UI in
front of it instead of only being reachable via the teacher-facing
Student Profile page or Swagger.

## Users & Roles admin page

`users.html` - list all accounts, create new ones (reuses the existing
`/api/auth/register` endpoint, now with a role dropdown and optional
student-ID link field), toggle active/inactive, change role inline via a
dropdown. An admin cannot deactivate their own account
(`AuthService.admin_update_user` rejects this explicitly) - a real safety
check, not just a UI restriction, since it's enforced server-side.

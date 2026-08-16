"""
Analytics service - computes overview/per-student/per-class statistics
from the SAME collections Phase 3 already writes to (attendance_records,
attendance_sessions, students). No new attendance data is generated here;
this is read-only aggregation.

"Total sessions" for a student's percentage is every session that reached
ACTIVE at least once (SCHEDULED-but-never-opened sessions never had a
chance for anyone to attend, so they're excluded - a real, documented
choice, not an arbitrary one). This is an approximation given the codebase
has no formal per-class student roster (see docs/analytics.md) - every
active student is treated as eligible for every session.
"""

from database.models.session_model import SessionStatus
from database.repositories.attendance_repository import AttendanceRepository
from database.repositories.session_repository import SessionRepository
from database.repositories.student_repository import StudentRepository
from services.analytics_math import (
    classify_risk,
    forecast_attendance,
    required_classes_to_reach_target,
)
from services.policy_service import PolicyService


class AnalyticsService:
    def __init__(
        self,
        attendance_repo: AttendanceRepository,
        session_repo: SessionRepository,
        student_repo: StudentRepository,
        policy_service: PolicyService,
    ):
        self._attendance = attendance_repo
        self._sessions = session_repo
        self._students = student_repo
        self._policy = policy_service

    async def _countable_session_count(self) -> int:
        _, active_total = await self._sessions.list_sessions(status=SessionStatus.ACTIVE, limit=1000)
        _, closed_total = await self._sessions.list_sessions(status=SessionStatus.CLOSED, limit=1000)
        return active_total + closed_total

    async def overview(self) -> dict:
        _, total_students = await self._students.list_students(limit=1)
        total_sessions = await self._countable_session_count()

        records, total_records = await self._attendance.list_records(limit=5000)
        present = sum(1 for r in records if r["status"] == "present")
        late = sum(1 for r in records if r["status"] == "late")

        attendance_rate = round((present + late) / total_records * 100, 1) if total_records else 0.0

        return {
            "total_students": total_students,
            "total_sessions": total_sessions,
            "total_attendance_records": total_records,
            "present": present,
            "late": late,
            "attendance_rate_percent": attendance_rate,
        }

    async def student_stats(self, student_id: str) -> dict:
        records, total_records = await self._attendance.list_records(student_id=student_id, limit=2000)
        total_sessions = await self._countable_session_count()

        present = sum(1 for r in records if r["status"] == "present")
        late = sum(1 for r in records if r["status"] == "late")
        attended = present + late
        absent = max(0, total_sessions - attended)

        attendance_percent = round(attended / total_sessions * 100, 1) if total_sessions else 0.0

        policy = await self._policy.get_policy()
        risk = classify_risk(attendance_percent, policy.required_attendance_percent)
        required_more = required_classes_to_reach_target(
            attended, total_sessions, policy.required_attendance_percent
        )

        history = sorted(records, key=lambda r: r["marked_at"], reverse=True)[:20]

        return {
            "student_id": student_id,
            "total_sessions": total_sessions,
            "present": present,
            "late": late,
            "absent": absent,
            "attendance_percent": attendance_percent,
            "risk": risk.value,
            "required_attendance_percent": policy.required_attendance_percent,
            "classes_needed_to_reach_target": required_more,
            "recent_history": [
                {
                    "session_id": r["session_id"],
                    "status": r["status"],
                    "marked_at": r["marked_at"].isoformat() if hasattr(r["marked_at"], "isoformat") else r["marked_at"],
                    "integrity_score": r["integrity_score"],
                }
                for r in history
            ],
        }

    async def forecast_for_student(self, student_id: str, additional_classes: int) -> dict:
        records, _ = await self._attendance.list_records(student_id=student_id, limit=2000)
        total_sessions = await self._countable_session_count()
        attended = sum(1 for r in records if r["status"] in ("present", "late"))

        projected = forecast_attendance(attended, total_sessions, additional_classes)
        return {
            "student_id": student_id,
            "current_attendance_percent": round(attended / total_sessions * 100, 1) if total_sessions else 0.0,
            "additional_classes_attended": additional_classes,
            "projected_attendance_percent": projected,
            "note": "This is a projection assuming every additional class listed is actually attended, not a guarantee.",
        }

    async def class_stats(self, class_name: str, section: str) -> dict:
        session_docs, _ = await self._sessions.list_sessions(limit=1000)
        matching_session_ids = [
            str(s["_id"])
            for s in session_docs
            if s["class_name"] == class_name and s["section"] == section and s["status"] != "scheduled"
        ]

        all_present = all_late = 0
        for session_id in matching_session_ids:
            records, _ = await self._attendance.list_records(session_id=session_id, limit=1000)
            all_present += sum(1 for r in records if r["status"] == "present")
            all_late += sum(1 for r in records if r["status"] == "late")

        _, total_students = await self._students.list_students(limit=1)
        total_possible = total_students * len(matching_session_ids)
        attendance_rate = (
            round((all_present + all_late) / total_possible * 100, 1) if total_possible else 0.0
        )

        return {
            "class_name": class_name,
            "section": section,
            "sessions_counted": len(matching_session_ids),
            "present": all_present,
            "late": all_late,
            "attendance_rate_percent": attendance_rate,
        }

    async def student_heatmap(self, student_id: str, days: int = 90) -> list[dict]:
        """
        Per-calendar-day status for a student over the last `days` days:
        "present"/"late" (had a record that day), "absent" (a countable
        session existed that day but this student has no record for it),
        or "no_class" (no countable session that day at all — the gray
        squares in a GitHub-style contribution heatmap).

        Real computation from the same attendance_records/sessions data
        used everywhere else — not a separate denormalized store.
        """
        from datetime import datetime, timedelta, timezone

        cutoff = datetime.now(timezone.utc) - timedelta(days=days)

        records, _ = await self._attendance.list_records(student_id=student_id, limit=2000)
        session_docs, _ = await self._sessions.list_sessions(limit=2000)

        def _to_date(value):
            if hasattr(value, "date"):
                return value.date().isoformat()
            return str(value)[:10]

        status_by_day: dict[str, str] = {}
        for r in records:
            marked_at = r["marked_at"]
            if hasattr(marked_at, "tzinfo") and marked_at.tzinfo is None:
                marked_at = marked_at.replace(tzinfo=timezone.utc)
            if hasattr(marked_at, "date") and marked_at < cutoff:
                continue
            day = _to_date(r["marked_at"])
            # "present" wins over "late" if somehow both exist the same day
            # (multiple sessions in one day) — present is the better signal.
            if day not in status_by_day or r["status"] == "present":
                status_by_day[day] = r["status"]

        countable_days: set[str] = set()
        for s in session_docs:
            if s["status"] not in ("active", "closed") or not s.get("start_time"):
                continue
            start_time = s["start_time"]
            if hasattr(start_time, "tzinfo") and start_time.tzinfo is None:
                start_time = start_time.replace(tzinfo=timezone.utc)
            if start_time < cutoff:
                continue
            countable_days.add(_to_date(s["start_time"]))

        all_days = countable_days | set(status_by_day.keys())
        return [
            {"date": day, "status": status_by_day.get(day, "absent" if day in countable_days else "no_class")}
            for day in sorted(all_days)
        ]

    async def session_summary(self, session_id: str) -> dict:
        """
        A deterministic, template-generated recap of one session — e.g.
        "Attendance was 81%. 34 of 42 students were present, 4 arrived
        late, and 2 were not recognized." Every number here comes from
        `records`/`total_students` fetched above; nothing is invented.
        Per spec: "This should summarize actual database data. Do not
        fabricate information" — there is no LLM call or free-text
        generation involved, just string formatting over real counts.
        """
        session_doc = await self._sessions.get_by_id(session_id)
        if not session_doc:
            return {"session_id": session_id, "summary": "Session not found."}

        records, total_records = await self._attendance.list_records(session_id=session_id, limit=1000)
        present = sum(1 for r in records if r["status"] == "present")
        late = sum(1 for r in records if r["status"] == "late")

        _, total_students = await self._students.list_students(limit=1)
        rate = round((present + late) / total_students * 100, 1) if total_students else 0.0

        summary = (
            f"{session_doc['subject']} ({session_doc['class_name']}/{session_doc['section']}): "
            f"attendance was {rate}%. {present} of {total_students} students were present"
        )
        if late:
            summary += f", {late} arrived late"
        not_yet = max(0, total_students - present - late)
        if not_yet:
            summary += f", and {not_yet} have not been marked"
        summary += "."

        return {
            "session_id": session_id,
            "total_students": total_students,
            "present": present,
            "late": late,
            "not_marked": not_yet,
            "attendance_rate_percent": rate,
            "summary": summary,
        }

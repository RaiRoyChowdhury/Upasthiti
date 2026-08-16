"""
Demo Mode service - Phase 10.

Generates a synthetic-but-realistic dataset (students with clearly-labeled
demo names, sessions, and attendance patterns with a randomized
present/late/absent mix per student) for presentation purposes.

Every generated name is explicitly "Demo Student N" - never a name that
could be mistaken for a real enrolled student - and every generated
record lives in the demo_* collections (see demo_repository.py), never
the real ones. See docs/demo-mode.md for the full isolation guarantee.
"""

import random
from datetime import datetime, timedelta, timezone

from database.models.demo_model import DemoDatasetSummary
from database.repositories.demo_repository import DemoRepository

_SUBJECTS = ["Data Structures", "Database Systems", "Operating Systems", "Computer Networks"]


class DemoService:
    def __init__(self, repo: DemoRepository):
        self._repo = repo

    async def generate(self, student_count: int, session_count: int) -> DemoDatasetSummary:
        await self._repo.clear_all()

        now = datetime.now(timezone.utc)

        student_docs = [
            {"demo_student_id": f"DEMO-{i:03d}", "name": f"Demo Student {i}", "created_at": now}
            for i in range(1, student_count + 1)
        ]
        await self._repo.insert_students(student_docs)

        session_docs = []
        for i in range(1, session_count + 1):
            start = now - timedelta(days=session_count - i)
            session_docs.append(
                {
                    "demo_session_id": f"DEMO-SESSION-{i:03d}",
                    "subject": random.choice(_SUBJECTS),
                    "start_time": start,
                    "created_at": now,
                }
            )
        await self._repo.insert_sessions(session_docs)

        attendance_docs = []
        for student in student_docs:
            base_present_chance = random.uniform(0.55, 0.97)
            for session in session_docs:
                roll = random.random()
                if roll < base_present_chance * 0.85:
                    status = "present"
                elif roll < base_present_chance:
                    status = "late"
                else:
                    status = "absent"

                if status == "absent":
                    continue

                attendance_docs.append(
                    {
                        "demo_student_id": student["demo_student_id"],
                        "demo_session_id": session["demo_session_id"],
                        "status": status,
                        "marked_at": session["start_time"] + timedelta(minutes=random.randint(0, 15)),
                        "integrity_score": random.randint(78, 99),
                    }
                )
        await self._repo.insert_attendance(attendance_docs)
        await self._repo.set_generated_at(now)

        return DemoDatasetSummary(
            students=len(student_docs),
            sessions=len(session_docs),
            attendance_records=len(attendance_docs),
            generated_at=now,
        )

    async def clear(self) -> None:
        await self._repo.clear_all()

    async def get_summary(self) -> DemoDatasetSummary:
        data = await self._repo.summary()
        return DemoDatasetSummary(**data)

    async def get_dashboard_data(self) -> dict:
        students = await self._repo.list_students()
        sessions = await self._repo.list_sessions()
        attendance = await self._repo.list_attendance()

        by_student = {}
        for s in students:
            sid = s["demo_student_id"]
            records = [a for a in attendance if a["demo_student_id"] == sid]
            present = sum(1 for r in records if r["status"] == "present")
            late = sum(1 for r in records if r["status"] == "late")
            total = len(sessions)
            pct = round((present + late) / total * 100, 1) if total else 0.0
            by_student[sid] = {
                "name": s["name"],
                "present": present,
                "late": late,
                "absent": max(0, total - present - late),
                "attendance_percent": pct,
            }

        return {
            "students": list(by_student.values()),
            "sessions": [{"subject": s["subject"], "start_time": s["start_time"].isoformat()} for s in sessions],
            "total_students": len(students),
            "total_sessions": len(sessions),
        }

"""
Report service - CSV and PDF export built from the exact same attendance/
session/student data the rest of the app reads.
"""

import csv
import io

from fpdf import FPDF

from database.repositories.attendance_repository import AttendanceRepository
from database.repositories.session_repository import SessionRepository
from database.repositories.student_repository import StudentRepository


def _build_pdf_table(title: str, headers: list[str], rows: list[list[str]]) -> bytes:
    """
    Minimal, real tabular PDF — no styling library, just fpdf2's basic
    cell grid. Deliberately simple: this is a data export, not a
    branded document.
    """
    pdf = FPDF(orientation="L", unit="mm", format="A4")
    pdf.add_page()
    pdf.set_font("Helvetica", "B", 14)
    pdf.cell(0, 10, title, ln=True)
    pdf.ln(2)

    col_width = (pdf.w - 20) / max(len(headers), 1)
    pdf.set_font("Helvetica", "B", 9)
    for h in headers:
        pdf.cell(col_width, 8, str(h), border=1)
    pdf.ln()

    pdf.set_font("Helvetica", "", 8)
    for row in rows:
        for cell in row:
            pdf.cell(col_width, 7, str(cell) if cell is not None else "", border=1)
        pdf.ln()

    output = pdf.output(dest="S")
    return bytes(output)


class ReportService:
    def __init__(
        self,
        attendance_repo: AttendanceRepository,
        session_repo: SessionRepository,
        student_repo: StudentRepository,
    ):
        self._attendance = attendance_repo
        self._sessions = session_repo
        self._students = student_repo

    async def session_report_csv(self, session_id: str) -> str:
        records, _ = await self._attendance.list_records(session_id=session_id, limit=1000)
        buffer = io.StringIO()
        writer = csv.writer(buffer)
        writer.writerow(["student_id", "status", "marked_at", "recognition_confidence", "integrity_score"])
        for r in records:
            writer.writerow(
                [
                    r["student_id"],
                    r["status"],
                    r["marked_at"].isoformat() if hasattr(r["marked_at"], "isoformat") else r["marked_at"],
                    r.get("recognition_confidence"),
                    r["integrity_score"],
                ]
            )
        return buffer.getvalue()

    async def student_report_csv(self, student_id: str) -> str:
        records, _ = await self._attendance.list_records(student_id=student_id, limit=2000)
        buffer = io.StringIO()
        writer = csv.writer(buffer)
        writer.writerow(["session_id", "status", "marked_at", "integrity_score", "verification_method"])
        for r in records:
            writer.writerow(
                [
                    r["session_id"],
                    r["status"],
                    r["marked_at"].isoformat() if hasattr(r["marked_at"], "isoformat") else r["marked_at"],
                    r["integrity_score"],
                    r["verification_method"],
                ]
            )
        return buffer.getvalue()

    async def class_report_csv(self, class_name: str, section: str) -> str:
        session_docs, _ = await self._sessions.list_sessions(limit=1000)
        matching = [s for s in session_docs if s["class_name"] == class_name and s["section"] == section]

        buffer = io.StringIO()
        writer = csv.writer(buffer)
        writer.writerow(["session_id", "subject", "status", "student_id", "attendance_status", "marked_at"])
        for session in matching:
            session_id = str(session["_id"])
            records, _ = await self._attendance.list_records(session_id=session_id, limit=1000)
            for r in records:
                writer.writerow(
                    [
                        session_id,
                        session["subject"],
                        session["status"],
                        r["student_id"],
                        r["status"],
                        r["marked_at"].isoformat() if hasattr(r["marked_at"], "isoformat") else r["marked_at"],
                    ]
                )
        return buffer.getvalue()

    @staticmethod
    def _fmt(value):
        return value.isoformat() if hasattr(value, "isoformat") else value

    async def session_report_pdf(self, session_id: str) -> bytes:
        records, _ = await self._attendance.list_records(session_id=session_id, limit=1000)
        rows = [
            [r["student_id"], r["status"], self._fmt(r["marked_at"]), r.get("recognition_confidence"), r["integrity_score"]]
            for r in records
        ]
        return _build_pdf_table(
            f"Session Report - {session_id}",
            ["Student ID", "Status", "Marked At", "Confidence", "Integrity"],
            rows,
        )

    async def student_report_pdf(self, student_id: str) -> bytes:
        records, _ = await self._attendance.list_records(student_id=student_id, limit=2000)
        rows = [
            [r["session_id"], r["status"], self._fmt(r["marked_at"]), r["integrity_score"], r["verification_method"]]
            for r in records
        ]
        return _build_pdf_table(
            f"Student Report - {student_id}",
            ["Session ID", "Status", "Marked At", "Integrity", "Method"],
            rows,
        )

    async def class_report_pdf(self, class_name: str, section: str) -> bytes:
        session_docs, _ = await self._sessions.list_sessions(limit=1000)
        matching = [s for s in session_docs if s["class_name"] == class_name and s["section"] == section]

        rows = []
        for session in matching:
            session_id = str(session["_id"])
            records, _ = await self._attendance.list_records(session_id=session_id, limit=1000)
            for r in records:
                rows.append(
                    [session_id, session["subject"], r["student_id"], r["status"], self._fmt(r["marked_at"])]
                )
        return _build_pdf_table(
            f"Class Report - {class_name}/{section}",
            ["Session ID", "Subject", "Student ID", "Status", "Marked At"],
            rows,
        )

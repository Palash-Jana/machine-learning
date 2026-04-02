from __future__ import annotations

import csv
import io
from datetime import datetime, timedelta
from pathlib import Path

import jwt
from fastapi import Depends, FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from fastapi.staticfiles import StaticFiles

from .auth import create_access_token, decode_access_token, hash_password, verify_password
from .database import get_connection, init_db
from .schemas import (
    AdminCredentialsUpdate,
    AttendanceWindowUpdate,
    LoginRequest,
    RecognitionResponse,
    StudentUpdate,
    TokenResponse,
)
from .services.face_service import face_service


APP_DIR = Path(__file__).resolve().parents[2]
FRONTEND_DIST = APP_DIR / "frontend" / "dist"
DEFAULT_ADMIN_ID = "AdminID"
DEFAULT_ADMIN_PASSWORD = "admin@123"

app = FastAPI(title="Face Attendance System", version="1.0.0")
security = HTTPBearer()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def now_local() -> datetime:
    return datetime.now().astimezone()


def parse_time(value: str) -> datetime.time:
    try:
        return datetime.strptime(value, "%H:%M").time()
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Time must use HH:MM format") from exc


def seed_admin() -> None:
    connection = get_connection()
    cursor = connection.cursor()
    row = cursor.execute("SELECT id FROM admin_settings WHERE id = 1").fetchone()
    if row is None:
        cursor.execute(
            """
            INSERT INTO admin_settings (id, admin_id, password_hash, attendance_start, attendance_end, late_grace_minutes)
            VALUES (1, ?, ?, '08:00', '09:00', 10)
            """,
            (DEFAULT_ADMIN_ID, hash_password(DEFAULT_ADMIN_PASSWORD)),
        )
        connection.commit()
    connection.close()


@app.on_event("startup")
def startup_event() -> None:
    init_db()
    seed_admin()


def get_admin(credentials: HTTPAuthorizationCredentials = Depends(security)) -> str:
    try:
        return decode_access_token(credentials.credentials)
    except jwt.PyJWTError as exc:
        raise HTTPException(status_code=401, detail="Invalid or expired token") from exc


def get_settings_row() -> dict:
    connection = get_connection()
    row = connection.execute("SELECT * FROM admin_settings WHERE id = 1").fetchone()
    connection.close()
    return dict(row)


def attendance_window_state() -> dict:
    settings = get_settings_row()
    current_time = now_local().time()
    start = parse_time(settings["attendance_start"])
    end = parse_time(settings["attendance_end"])
    active = start <= current_time <= end
    return {
        "attendance_start": settings["attendance_start"],
        "attendance_end": settings["attendance_end"],
        "late_grace_minutes": settings["late_grace_minutes"],
        "window_active": active,
    }


@app.get("/api/health")
def health() -> dict:
    return {"ok": True}


@app.post("/api/auth/login", response_model=TokenResponse)
def login(payload: LoginRequest) -> TokenResponse:
    connection = get_connection()
    row = connection.execute("SELECT admin_id, password_hash FROM admin_settings WHERE id = 1").fetchone()
    connection.close()

    if row is None or row["admin_id"] != payload.admin_id or not verify_password(
        payload.password, row["password_hash"]
    ):
        raise HTTPException(status_code=401, detail="Invalid admin credentials")
    return TokenResponse(access_token=create_access_token(payload.admin_id))


@app.get("/api/settings")
def get_settings() -> dict:
    settings = get_settings_row()
    window = attendance_window_state()
    return {
        "admin_id": settings["admin_id"],
        "attendance_start": window["attendance_start"],
        "attendance_end": window["attendance_end"],
        "late_grace_minutes": window["late_grace_minutes"],
        "window_active": window["window_active"],
    }


@app.put("/api/settings/attendance-window")
def update_attendance_window(
    payload: AttendanceWindowUpdate, _: str = Depends(get_admin)
) -> dict:
    start = parse_time(payload.attendance_start)
    end = parse_time(payload.attendance_end)
    if start >= end:
        raise HTTPException(status_code=400, detail="Attendance start must be before end time")

    connection = get_connection()
    connection.execute(
        """
        UPDATE admin_settings
        SET attendance_start = ?, attendance_end = ?, late_grace_minutes = ?
        WHERE id = 1
        """,
        (payload.attendance_start, payload.attendance_end, payload.late_grace_minutes),
    )
    connection.commit()
    connection.close()
    return {"message": "Attendance window updated successfully"}


@app.post("/api/settings/change-credentials")
def update_admin_credentials(
    payload: AdminCredentialsUpdate, _: str = Depends(get_admin)
) -> dict:
    connection = get_connection()
    row = connection.execute("SELECT password_hash FROM admin_settings WHERE id = 1").fetchone()
    if row is None or not verify_password(payload.current_password, row["password_hash"]):
        connection.close()
        raise HTTPException(status_code=400, detail="Current password is incorrect")

    connection.execute(
        "UPDATE admin_settings SET admin_id = ?, password_hash = ? WHERE id = 1",
        (payload.new_admin_id, hash_password(payload.new_password)),
    )
    connection.commit()
    connection.close()
    return {"message": "Admin credentials updated successfully"}


@app.get("/api/students")
def list_students(_: str = Depends(get_admin)) -> list[dict]:
    connection = get_connection()
    rows = connection.execute(
        "SELECT id, roll_no, name, father_name, address, created_at FROM students ORDER BY roll_no"
    ).fetchall()
    connection.close()
    return [dict(row) for row in rows]


@app.post("/api/students/enroll")
async def enroll_student(
    roll_no: str = Form(...),
    name: str = Form(...),
    father_name: str = Form(...),
    address: str = Form(...),
    images: list[UploadFile] = File(...),
    _: str = Depends(get_admin),
) -> dict:
    if len(images) < 3:
        raise HTTPException(status_code=400, detail="Capture at least 3 photos from different angles")

    encodings: list[list[float]] = []
    for image in images:
        content = await image.read()
        encodings.append(face_service.encoding_from_image_bytes(content))

    averaged_encoding = face_service.average_encodings(encodings)
    connection = get_connection()
    try:
        connection.execute(
            """
            INSERT INTO students (roll_no, name, father_name, address, face_encoding, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                roll_no.strip(),
                name.strip(),
                father_name.strip(),
                address.strip(),
                face_service.encoding_to_json(averaged_encoding),
                now_local().isoformat(),
            ),
        )
        connection.commit()
    except Exception as exc:
        connection.close()
        raise HTTPException(status_code=400, detail=f"Could not enroll student: {exc}") from exc
    connection.close()
    return {"message": "Student enrolled successfully"}


@app.put("/api/students/{student_id}")
def update_student(student_id: int, payload: StudentUpdate, _: str = Depends(get_admin)) -> dict:
    connection = get_connection()
    result = connection.execute(
        """
        UPDATE students SET name = ?, father_name = ?, address = ?
        WHERE id = ?
        """,
        (payload.name.strip(), payload.father_name.strip(), payload.address.strip(), student_id),
    )
    connection.commit()
    connection.close()
    if result.rowcount == 0:
        raise HTTPException(status_code=404, detail="Student not found")
    return {"message": "Student updated successfully"}


@app.delete("/api/students/{student_id}")
def delete_student(student_id: int, _: str = Depends(get_admin)) -> dict:
    connection = get_connection()
    connection.execute("DELETE FROM attendance_logs WHERE student_id = ?", (student_id,))
    result = connection.execute("DELETE FROM students WHERE id = ?", (student_id,))
    connection.commit()
    connection.close()
    if result.rowcount == 0:
        raise HTTPException(status_code=404, detail="Student not found")
    return {"message": "Student deleted successfully"}


@app.get("/api/attendance/today")
def attendance_today(_: str = Depends(get_admin)) -> dict:
    today = now_local().date().isoformat()
    connection = get_connection()
    rows = connection.execute(
        """
        SELECT s.roll_no, s.name, s.father_name, a.attendance_date, a.attendance_time, a.status, a.confidence
        FROM attendance_logs a
        JOIN students s ON s.id = a.student_id
        WHERE a.attendance_date = ?
        ORDER BY a.attendance_time
        """,
        (today,),
    ).fetchall()
    total_students = connection.execute("SELECT COUNT(*) AS count FROM students").fetchone()["count"]
    connection.close()
    return {
        "date": today,
        "total_students": total_students,
        "present_count": len(rows),
        "records": [dict(row) for row in rows],
    }


@app.post("/api/attendance/recognize", response_model=RecognitionResponse)
async def recognize_attendance(image: UploadFile = File(...)) -> RecognitionResponse:
    window = attendance_window_state()
    if not window["window_active"]:
        return RecognitionResponse(
            recognized=False,
            message="Attendance is currently closed",
            status="outside_window",
        )

    probe_bytes = await image.read()
    try:
        probe_encoding = face_service.encoding_from_image_bytes(probe_bytes)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    connection = get_connection()
    students = connection.execute("SELECT * FROM students").fetchall()
    if not students:
        connection.close()
        raise HTTPException(status_code=400, detail="No students enrolled yet")

    best_student = None
    best_confidence = 0.0
    for student in students:
        is_match, confidence = face_service.compare(
            probe_encoding, face_service.encoding_from_json(student["face_encoding"])
        )
        if is_match and confidence > best_confidence:
            best_student = student
            best_confidence = confidence

    if best_student is None:
        connection.close()
        return RecognitionResponse(
            recognized=False,
            message="Face not recognized. Please contact admin.",
            confidence=0.0,
            status="unknown",
        )

    today = now_local().date().isoformat()
    current_dt = now_local()
    existing = connection.execute(
        "SELECT id FROM attendance_logs WHERE student_id = ? AND attendance_date = ?",
        (best_student["id"], today),
    ).fetchone()
    if existing is not None:
        connection.close()
        return RecognitionResponse(
            recognized=True,
            message="Attendance already marked for today",
            confidence=round(best_confidence, 3),
            student={
                "roll_no": best_student["roll_no"],
                "name": best_student["name"],
            },
            status="duplicate",
        )

    start = parse_time(window["attendance_start"])
    late_cutoff = datetime.combine(current_dt.date(), start, tzinfo=current_dt.tzinfo) + timedelta(
        minutes=window["late_grace_minutes"]
    )
    attendance_status = "late" if current_dt > late_cutoff else "present"

    connection.execute(
        """
        INSERT INTO attendance_logs (student_id, attendance_date, attendance_time, status, confidence)
        VALUES (?, ?, ?, ?, ?)
        """,
        (
            best_student["id"],
            today,
            current_dt.strftime("%H:%M:%S"),
            attendance_status,
            round(best_confidence, 4),
        ),
    )
    connection.commit()
    connection.close()

    return RecognitionResponse(
        recognized=True,
        message=f"Attendance marked as {attendance_status}",
        confidence=round(best_confidence, 3),
        student={
            "roll_no": best_student["roll_no"],
            "name": best_student["name"],
        },
        status=attendance_status,
    )


@app.get("/api/attendance/export")
def export_attendance_csv(date: str, _: str = Depends(get_admin)) -> StreamingResponse:
    try:
        datetime.strptime(date, "%Y-%m-%d")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Date must be in YYYY-MM-DD format") from exc

    connection = get_connection()
    rows = connection.execute(
        """
        SELECT s.roll_no, s.name, s.father_name, s.address, a.attendance_date, a.attendance_time, a.status, a.confidence
        FROM attendance_logs a
        JOIN students s ON s.id = a.student_id
        WHERE a.attendance_date = ?
        ORDER BY s.roll_no
        """,
        (date,),
    ).fetchall()
    connection.close()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(
        ["Roll No", "Name", "Father Name", "Address", "Attendance Date", "Attendance Time", "Status", "Confidence"]
    )
    for row in rows:
        writer.writerow(
            [
                row["roll_no"],
                row["name"],
                row["father_name"],
                row["address"],
                row["attendance_date"],
                row["attendance_time"],
                row["status"],
                row["confidence"],
            ]
        )
    output.seek(0)
    headers = {"Content-Disposition": f'attachment; filename="attendance-{date}.csv"'}
    return StreamingResponse(iter([output.getvalue()]), media_type="text/csv", headers=headers)


@app.get("/api/dashboard")
def dashboard(_: str = Depends(get_admin)) -> dict:
    today = now_local().date().isoformat()
    connection = get_connection()
    total_students = connection.execute("SELECT COUNT(*) AS count FROM students").fetchone()["count"]
    present_today = connection.execute(
        "SELECT COUNT(*) AS count FROM attendance_logs WHERE attendance_date = ?",
        (today,),
    ).fetchone()["count"]
    late_today = connection.execute(
        "SELECT COUNT(*) AS count FROM attendance_logs WHERE attendance_date = ? AND status = 'late'",
        (today,),
    ).fetchone()["count"]
    connection.close()
    return {
        "total_students": total_students,
        "present_today": present_today,
        "late_today": late_today,
        "absent_today": max(0, total_students - present_today),
    }


if FRONTEND_DIST.exists():
    app.mount("/", StaticFiles(directory=FRONTEND_DIST, html=True), name="frontend")

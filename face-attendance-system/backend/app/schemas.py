from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class LoginRequest(BaseModel):
    admin_id: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class AdminCredentialsUpdate(BaseModel):
    current_password: str
    new_admin_id: str = Field(min_length=4)
    new_password: str = Field(min_length=6)


class AttendanceWindowUpdate(BaseModel):
    attendance_start: str
    attendance_end: str
    late_grace_minutes: int = Field(default=10, ge=0, le=180)


class StudentUpdate(BaseModel):
    name: str
    father_name: str
    address: str


class RecognitionResponse(BaseModel):
    recognized: bool
    message: str
    student: dict | None = None
    confidence: float | None = None
    status: Literal["present", "late", "outside_window", "duplicate", "unknown"]

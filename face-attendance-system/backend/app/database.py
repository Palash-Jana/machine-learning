from __future__ import annotations

import sqlite3
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parents[2]
DATA_DIR = BASE_DIR / "backend" / "data"
DB_PATH = DATA_DIR / "attendance.db"


def get_connection() -> sqlite3.Connection:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(DB_PATH, check_same_thread=False)
    connection.row_factory = sqlite3.Row
    return connection


def init_db() -> None:
    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS admin_settings (
            id INTEGER PRIMARY KEY CHECK (id = 1),
            admin_id TEXT NOT NULL,
            password_hash TEXT NOT NULL,
            attendance_start TEXT NOT NULL DEFAULT '08:00',
            attendance_end TEXT NOT NULL DEFAULT '09:00',
            late_grace_minutes INTEGER NOT NULL DEFAULT 10
        )
        """
    )

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS students (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            roll_no TEXT UNIQUE NOT NULL,
            name TEXT NOT NULL,
            father_name TEXT NOT NULL,
            address TEXT NOT NULL,
            face_encoding TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
        """
    )

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS attendance_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id INTEGER NOT NULL,
            attendance_date TEXT NOT NULL,
            attendance_time TEXT NOT NULL,
            status TEXT NOT NULL,
            confidence REAL NOT NULL,
            UNIQUE(student_id, attendance_date),
            FOREIGN KEY (student_id) REFERENCES students(id)
        )
        """
    )

    connection.commit()
    connection.close()

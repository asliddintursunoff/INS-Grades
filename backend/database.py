import sqlite3
import os
import json
from pathlib import Path
from typing import Any, List, Dict, Optional
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

DATABASE_PATH = os.getenv("DATABASE_PATH")
if not DATABASE_PATH:
    # Look for data/timetable.db in current directory or parent
    base_dir = Path(__file__).resolve().parent
    data_dir = base_dir / "data"
    data_dir.mkdir(parents=True, exist_ok=True)
    DATABASE_PATH = str(data_dir / "timetable.db")

def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(DATABASE_PATH, timeout=10.0, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode = WAL;")
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn

def query(sql: str, params: tuple = ()) -> List[Dict[str, Any]]:
    """Execute a query and return results as a list of dicts."""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(sql, params)
        if cursor.description is None:
            conn.commit()
            return []
        columns = [col[0] for col in cursor.description]
        rows = cursor.fetchall()
        return [dict(zip(columns, row)) for row in rows]

def execute(sql: str, params: tuple = ()) -> int:
    """Execute an INSERT/UPDATE/DELETE and return affected row count or lastrowid."""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(sql, params)
        conn.commit()
        return cursor.lastrowid or cursor.rowcount

def init_db():
    """Create tables if they do not exist and seed default university data."""
    with get_connection() as conn:
        conn.executescript("""
        CREATE TABLE IF NOT EXISTS professors (
            professor_id INTEGER PRIMARY KEY AUTOINCREMENT,
            full_name TEXT NOT NULL,
            email TEXT UNIQUE
        );

        CREATE TABLE IF NOT EXISTS groups (
            group_id INTEGER PRIMARY KEY AUTOINCREMENT,
            group_name TEXT NOT NULL UNIQUE,
            timetable_image_url TEXT
        );

        CREATE TABLE IF NOT EXISTS students (
            student_id TEXT PRIMARY KEY,
            full_name TEXT NOT NULL,
            group_id INTEGER NOT NULL REFERENCES groups(group_id),
            year_of_study INTEGER NOT NULL DEFAULT 2,
            telegram_id INTEGER UNIQUE,
            telegram_username TEXT
        );

        CREATE TABLE IF NOT EXISTS subjects (
            subject_id INTEGER PRIMARY KEY AUTOINCREMENT,
            short_name TEXT NOT NULL,
            full_name TEXT NOT NULL,
            year_level INTEGER NOT NULL DEFAULT 1
        );

        CREATE TABLE IF NOT EXISTS classes (
            class_id INTEGER PRIMARY KEY AUTOINCREMENT,
            subject_id INTEGER NOT NULL REFERENCES subjects(subject_id),
            professor_id INTEGER NOT NULL REFERENCES professors(professor_id),
            group_id INTEGER NOT NULL REFERENCES groups(group_id),
            room TEXT
        );

        CREATE TABLE IF NOT EXISTS group_timetable (
            slot_id INTEGER PRIMARY KEY AUTOINCREMENT,
            group_id INTEGER NOT NULL REFERENCES groups(group_id),
            day_of_week INTEGER NOT NULL CHECK (day_of_week BETWEEN 1 AND 7),
            start_time TEXT NOT NULL,
            end_time TEXT NOT NULL,
            class_id INTEGER NOT NULL REFERENCES classes(class_id)
        );

        CREATE TABLE IF NOT EXISTS student_schedule_overrides (
            override_id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id TEXT NOT NULL REFERENCES students(student_id),
            day_of_week INTEGER NOT NULL CHECK (day_of_week BETWEEN 1 AND 7),
            start_time TEXT NOT NULL,
            end_time TEXT NOT NULL,
            class_id INTEGER NOT NULL REFERENCES classes(class_id),
            valid_from TEXT,
            valid_to TEXT
        );

        CREATE TABLE IF NOT EXISTS student_class_enrollment (
            enrollment_id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id TEXT NOT NULL REFERENCES students(student_id),
            class_id INTEGER NOT NULL REFERENCES classes(class_id),
            status TEXT NOT NULL DEFAULT 'active',
            enrolled_at TEXT DEFAULT CURRENT_TIMESTAMP,
            dropped_at TEXT NULL,
            UNIQUE (student_id, class_id)
        );

        CREATE TABLE IF NOT EXISTS homeworks (
            homework_id INTEGER PRIMARY KEY AUTOINCREMENT,
            class_id INTEGER NOT NULL REFERENCES classes(class_id),
            title TEXT NOT NULL,
            description TEXT,
            deadline TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS homework_submissions (
            submission_id INTEGER PRIMARY KEY AUTOINCREMENT,
            homework_id INTEGER NOT NULL REFERENCES homeworks(homework_id),
            student_id TEXT NOT NULL REFERENCES students(student_id),
            is_done INTEGER DEFAULT 0,
            is_active INTEGER DEFAULT 1,
            submitted_at TEXT NULL,
            grade REAL NULL,
            UNIQUE (homework_id, student_id)
        );

        CREATE TABLE IF NOT EXISTS lecture_sessions (
            session_id INTEGER PRIMARY KEY AUTOINCREMENT,
            class_id INTEGER NOT NULL REFERENCES classes(class_id),
            session_date TEXT NOT NULL,
            start_time TEXT NOT NULL,
            end_time TEXT NOT NULL,
            UNIQUE (class_id, session_date)
        );

        CREATE TABLE IF NOT EXISTS attendance (
            attendance_id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id TEXT NOT NULL REFERENCES students(student_id),
            session_id INTEGER NOT NULL REFERENCES lecture_sessions(session_id),
            status TEXT NOT NULL DEFAULT 'absent',
            makeup_session_id INTEGER NULL REFERENCES lecture_sessions(session_id),
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            UNIQUE (student_id, session_id)
        );

        CREATE TABLE IF NOT EXISTS notification_settings (
            student_id TEXT PRIMARY KEY REFERENCES students(student_id),
            enabled INTEGER DEFAULT 1,
            minutes_before INTEGER DEFAULT 30
        );

        CREATE TABLE IF NOT EXISTS sent_notifications (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id TEXT NOT NULL,
            session_id INTEGER NOT NULL,
            sent_at TEXT DEFAULT CURRENT_TIMESTAMP,
            UNIQUE (student_id, session_id)
        );
        """)
        conn.commit()

        # Seed if empty
        row = conn.execute("SELECT COUNT(*) as c FROM students;").fetchone()
        if row and row["c"] == 0:
            seed_data(conn)

def seed_data(conn: sqlite3.Connection):
    professors = [
        (1, 'Prof. F. Atamurotov', 'atamurotov@university.uz'),
        (2, 'Prof. N. Karimov', 'karimov@university.uz'),
        (3, 'Prof. M. Siddiqov', 'siddiqov@university.uz'),
        (4, 'Prof. D. Umarova', 'umarova@university.uz'),
        (5, 'Prof. A. Rakhimov', 'rakhimov@university.uz'),
        (6, 'Prof. Z. Khusanov', 'khusanov@university.uz'),
        (7, 'Prof. S. Makhmudov', 'makhmudov@university.uz'),
        (8, 'Prof. G. Karimova', 'karimova@university.uz'),
        (9, 'Prof. T. Usmonov', 'usmonov@university.uz'),
        (10, 'Prof. L. Azizova', 'azizova@university.uz'),
    ]
    conn.executemany("INSERT OR IGNORE INTO professors VALUES (?, ?, ?);", professors)

    groups = [
        (1, 'CIE26-3', 'https://images.unsplash.com/photo-1509062522246-3755977927d7?auto=format&fit=crop&w=1200&q=80'),
        (2, 'CIE26-5', 'https://images.unsplash.com/photo-1523240795612-9a054b0db644?auto=format&fit=crop&w=1200&q=80'),
        (3, 'CIE26-2', 'https://images.unsplash.com/photo-1516321318423-f06f85e504b3?auto=format&fit=crop&w=1200&q=80'),
        (4, 'CIE26-1', 'https://images.unsplash.com/photo-1434030216411-0b793f4b4173?auto=format&fit=crop&w=1200&q=80'),
        (5, 'CIE26-4', 'https://images.unsplash.com/photo-1524178232363-1fb2b075b655?auto=format&fit=crop&w=1200&q=80'),
        (6, 'CSE25-1', 'https://images.unsplash.com/photo-1519452635265-7b1fbfd1e4e0?auto=format&fit=crop&w=1200&q=80'),
        (7, 'CSE25-2', 'https://images.unsplash.com/photo-1497633762265-9d179a990aa6?auto=format&fit=crop&w=1200&q=80'),
        (8, 'ECE25-1', 'https://images.unsplash.com/photo-1532094349884-543bc11b234d?auto=format&fit=crop&w=1200&q=80'),
    ]
    conn.executemany("INSERT OR IGNORE INTO groups VALUES (?, ?, ?);", groups)

    students = [
        ('U2410252', 'Asliddin Xolmatov', 1, 2, 987654321, 'asliddin_dev'),
        ('U2410253', 'Javohir Toshmatov', 1, 2, None, 'javohir_t'),
        ('U2410254', 'Madina Alimova', 2, 2, None, 'madina_a'),
        ('U2510101', 'Bekzod Rahimov', 4, 1, None, 'bekzod_r'),
    ]
    conn.executemany("INSERT OR IGNORE INTO students VALUES (?, ?, ?, ?, ?, ?);", students)

    subjects = [
        (1, 'P1', 'Physics 1', 1),
        (2, 'AE1', 'Academic English 1', 1),
        (3, 'CS101', 'Computer Science 1', 1),
        (4, 'M1', 'Calculus 1', 1),
        (5, 'MATH102', 'Linear Algebra', 1),
        (6, 'DM101', 'Discrete Mathematics', 1),
        (7, 'CHEM101', 'General Chemistry', 1),
        (8, 'CS201', 'Data Structures & Algorithms', 2),
        (9, 'CS202', 'Object-Oriented Programming', 2),
        (10, 'ECE201', 'Computer Architecture', 2),
        (11, 'STAT201', 'Probability & Statistics', 2),
        (12, 'CS203', 'Database Systems', 2),
        (13, 'MATH201', 'Differential Equations', 2),
        (14, 'CS301', 'Web Development & Cloud Systems', 3),
        (15, 'CS302', 'Operating Systems', 3),
    ]
    conn.executemany("INSERT OR IGNORE INTO subjects VALUES (?, ?, ?, ?);", subjects)
    conn.commit()

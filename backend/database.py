import os
import re
import logging
from typing import Any, List, Dict, Optional
from datetime import datetime, timedelta

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

logger = logging.getLogger("backend.database")

# Railway PostgreSQL environment variables
DATABASE_URL = os.getenv("DATABASE_URL") or os.getenv("DATABASE_PUBLIC_URL")
if DATABASE_URL and DATABASE_URL.startswith("postgres://"):
    # Convert legacy postgres:// prefix to postgresql:// for compatibility
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

PGHOST = os.getenv("PGHOST")
PGPORT = os.getenv("PGPORT", "5432")
PGUSER = os.getenv("PGUSER")
PGPASSWORD = os.getenv("PGPASSWORD")
PGDATABASE = os.getenv("PGDATABASE")

# Check if PostgreSQL credentials are configured
USE_POSTGRES = bool(DATABASE_URL or (PGHOST and PGUSER and PGDATABASE))

# Global connection pool or state
_pg_pool = None
_in_memory_db: Optional[Dict[str, List[Dict[str, Any]]]] = None


def get_pg_connection():
    """Obtain a connection to Railway PostgreSQL."""
    try:
        import psycopg2
        from psycopg2.extras import RealDictCursor
    except ImportError:
        logger.error("[DB] psycopg2-binary not installed. Please add psycopg2-binary to requirements.txt")
        return None

    try:
        if DATABASE_URL:
            # Railway internal/external PostgreSQL connection string
            conn = psycopg2.connect(DATABASE_URL, cursor_factory=RealDictCursor)
        else:
            conn = psycopg2.connect(
                host=PGHOST,
                port=int(PGPORT),
                user=PGUSER,
                password=PGPASSWORD,
                dbname=PGDATABASE,
                cursor_factory=RealDictCursor
            )
        conn.autocommit = True
        return conn
    except Exception as e:
        logger.warning(f"[DB] Could not connect to Railway PostgreSQL: {e}")
        return None


def is_postgres_active() -> bool:
    """Check if Railway PostgreSQL is connected and operational."""
    if not USE_POSTGRES:
        return False
    conn = get_pg_connection()
    if conn:
        try:
            with conn.cursor() as cur:
                cur.execute("SELECT 1;")
            conn.close()
            return True
        except Exception:
            return False
    return False


def query(sql: str, params: tuple = ()) -> List[Dict[str, Any]]:
    """Execute a SELECT query and return rows as a list of dicts."""
    if USE_POSTGRES:
        conn = get_pg_connection()
        if conn:
            try:
                with conn.cursor() as cur:
                    # Convert SQLite '?' placeholders to PostgreSQL '%s'
                    pg_sql = sql.replace("?", "%s")
                    cur.execute(pg_sql, params)
                    if cur.description:
                        rows = cur.fetchall()
                        return [dict(row) for row in rows]
                    return []
            except Exception as e:
                logger.error(f"[DB] PostgreSQL Query error: {e} | SQL: {sql}")
            finally:
                conn.close()

    # In-memory store fallback for offline dev/tests
    return _memory_query(sql, params)


def execute(sql: str, params: tuple = ()) -> int:
    """Execute an INSERT/UPDATE/DELETE query and return affected rows."""
    if USE_POSTGRES:
        conn = get_pg_connection()
        if conn:
            try:
                with conn.cursor() as cur:
                    pg_sql = sql.replace("?", "%s")
                    cur.execute(pg_sql, params)
                    return cur.rowcount
            except Exception as e:
                logger.error(f"[DB] PostgreSQL Execute error: {e} | SQL: {sql}")
            finally:
                conn.close()

    return _memory_execute(sql, params)


def init_db():
    """Initialize database tables in Railway PostgreSQL or memory fallback."""
    if USE_POSTGRES:
        conn = get_pg_connection()
        if conn:
            logger.info("[DB] Initializing Railway PostgreSQL schema...")
            try:
                with conn.cursor() as cur:
                    cur.execute("""
                    CREATE TABLE IF NOT EXISTS professors (
                        professor_id SERIAL PRIMARY KEY,
                        full_name VARCHAR(255) NOT NULL,
                        email VARCHAR(255) UNIQUE
                    );

                    CREATE TABLE IF NOT EXISTS groups (
                        group_id SERIAL PRIMARY KEY,
                        group_name VARCHAR(100) NOT NULL UNIQUE,
                        timetable_image_url TEXT
                    );

                    CREATE TABLE IF NOT EXISTS students (
                        student_id VARCHAR(50) PRIMARY KEY,
                        full_name VARCHAR(255) NOT NULL,
                        group_id INTEGER NOT NULL REFERENCES groups(group_id) ON DELETE CASCADE,
                        year_of_study INTEGER NOT NULL DEFAULT 2,
                        telegram_id BIGINT UNIQUE,
                        telegram_username VARCHAR(100)
                    );

                    CREATE TABLE IF NOT EXISTS subjects (
                        subject_id SERIAL PRIMARY KEY,
                        short_name VARCHAR(50) NOT NULL,
                        full_name VARCHAR(255) NOT NULL,
                        year_level INTEGER NOT NULL DEFAULT 1
                    );

                    CREATE TABLE IF NOT EXISTS classes (
                        class_id SERIAL PRIMARY KEY,
                        subject_id INTEGER NOT NULL REFERENCES subjects(subject_id) ON DELETE CASCADE,
                        professor_id INTEGER NOT NULL REFERENCES professors(professor_id) ON DELETE CASCADE,
                        group_id INTEGER NOT NULL REFERENCES groups(group_id) ON DELETE CASCADE,
                        room VARCHAR(50)
                    );

                    CREATE TABLE IF NOT EXISTS group_timetable (
                        slot_id SERIAL PRIMARY KEY,
                        group_id INTEGER NOT NULL REFERENCES groups(group_id) ON DELETE CASCADE,
                        day_of_week INTEGER NOT NULL CHECK (day_of_week BETWEEN 1 AND 7),
                        start_time VARCHAR(10) NOT NULL,
                        end_time VARCHAR(10) NOT NULL,
                        class_id INTEGER NOT NULL REFERENCES classes(class_id) ON DELETE CASCADE
                    );

                    CREATE TABLE IF NOT EXISTS student_schedule_overrides (
                        override_id SERIAL PRIMARY KEY,
                        student_id VARCHAR(50) NOT NULL REFERENCES students(student_id) ON DELETE CASCADE,
                        day_of_week INTEGER NOT NULL CHECK (day_of_week BETWEEN 1 AND 7),
                        start_time VARCHAR(10) NOT NULL,
                        end_time VARCHAR(10) NOT NULL,
                        class_id INTEGER NOT NULL REFERENCES classes(class_id) ON DELETE CASCADE,
                        valid_from VARCHAR(50),
                        valid_to VARCHAR(50)
                    );

                    CREATE TABLE IF NOT EXISTS student_class_enrollment (
                        enrollment_id SERIAL PRIMARY KEY,
                        student_id VARCHAR(50) NOT NULL REFERENCES students(student_id) ON DELETE CASCADE,
                        class_id INTEGER NOT NULL REFERENCES classes(class_id) ON DELETE CASCADE,
                        status VARCHAR(50) NOT NULL DEFAULT 'active',
                        enrolled_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
                        dropped_at TIMESTAMPTZ NULL,
                        UNIQUE (student_id, class_id)
                    );

                    CREATE TABLE IF NOT EXISTS homeworks (
                        homework_id SERIAL PRIMARY KEY,
                        class_id INTEGER NOT NULL REFERENCES classes(class_id) ON DELETE CASCADE,
                        title VARCHAR(255) NOT NULL,
                        description TEXT,
                        deadline VARCHAR(100) NOT NULL
                    );

                    CREATE TABLE IF NOT EXISTS homework_submissions (
                        submission_id SERIAL PRIMARY KEY,
                        homework_id INTEGER NOT NULL REFERENCES homeworks(homework_id) ON DELETE CASCADE,
                        student_id VARCHAR(50) NOT NULL REFERENCES students(student_id) ON DELETE CASCADE,
                        is_done INTEGER DEFAULT 0,
                        is_active INTEGER DEFAULT 1,
                        submitted_at TIMESTAMPTZ NULL,
                        grade REAL NULL,
                        UNIQUE (homework_id, student_id)
                    );

                    CREATE TABLE IF NOT EXISTS lecture_sessions (
                        session_id SERIAL PRIMARY KEY,
                        class_id INTEGER NOT NULL REFERENCES classes(class_id) ON DELETE CASCADE,
                        session_date VARCHAR(50) NOT NULL,
                        start_time VARCHAR(10) NOT NULL,
                        end_time VARCHAR(10) NOT NULL,
                        UNIQUE (class_id, session_date)
                    );

                    CREATE TABLE IF NOT EXISTS attendance (
                        attendance_id SERIAL PRIMARY KEY,
                        student_id VARCHAR(50) NOT NULL REFERENCES students(student_id) ON DELETE CASCADE,
                        session_id INTEGER NOT NULL REFERENCES lecture_sessions(session_id) ON DELETE CASCADE,
                        status VARCHAR(50) NOT NULL DEFAULT 'absent',
                        makeup_session_id INTEGER NULL REFERENCES lecture_sessions(session_id) ON DELETE SET NULL,
                        created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
                        UNIQUE (student_id, session_id)
                    );

                    CREATE TABLE IF NOT EXISTS notification_settings (
                        student_id VARCHAR(50) PRIMARY KEY REFERENCES students(student_id) ON DELETE CASCADE,
                        enabled INTEGER DEFAULT 1,
                        minutes_before INTEGER DEFAULT 30
                    );

                    CREATE TABLE IF NOT EXISTS sent_notifications (
                        id SERIAL PRIMARY KEY,
                        student_id VARCHAR(50) NOT NULL,
                        session_id INTEGER NOT NULL,
                        sent_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
                        UNIQUE (student_id, session_id)
                    );
                    """)

                    # Seed PostgreSQL if students table is empty
                    cur.execute("SELECT COUNT(*) AS c FROM students;")
                    res = cur.fetchone()
                    count = res['c'] if res else 0
                    if count == 0:
                        _seed_postgres(cur)
                        logger.info("[DB] Railway PostgreSQL seeded successfully.")
                    else:
                        logger.info(f"[DB] Railway PostgreSQL ready with {count} students.")
            except Exception as e:
                logger.error(f"[DB] Failed to init Railway PostgreSQL: {e}")
            finally:
                conn.close()
                return

    # Fallback init memory
    _init_memory_db()


def _seed_postgres(cur):
    """Seed base university timetable into Railway PostgreSQL."""
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
    cur.executemany(
        "INSERT INTO professors (professor_id, full_name, email) VALUES (%s, %s, %s) ON CONFLICT (professor_id) DO NOTHING;",
        professors
    )

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
    cur.executemany(
        "INSERT INTO groups (group_id, group_name, timetable_image_url) VALUES (%s, %s, %s) ON CONFLICT (group_id) DO NOTHING;",
        groups
    )

    students = [
        ('U2410252', 'Asliddin Xolmatov', 1, 2, 987654321, 'asliddin_dev'),
        ('U2410253', 'Javohir Toshmatov', 1, 2, None, 'javohir_t'),
        ('U2410254', 'Madina Alimova', 2, 2, None, 'madina_a'),
        ('U2510101', 'Bekzod Rahimov', 4, 1, None, 'bekzod_r'),
    ]
    cur.executemany(
        "INSERT INTO students (student_id, full_name, group_id, year_of_study, telegram_id, telegram_username) VALUES (%s, %s, %s, %s, %s, %s) ON CONFLICT (student_id) DO NOTHING;",
        students
    )

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
    cur.executemany(
        "INSERT INTO subjects (subject_id, short_name, full_name, year_level) VALUES (%s, %s, %s, %s) ON CONFLICT (subject_id) DO NOTHING;",
        subjects
    )

    classes = [
        (14, 1, 1, 1, 'A605'),
        (22, 1, 1, 2, 'A605'),
        (23, 1, 2, 3, 'B201'),
        (24, 1, 1, 4, 'A605'),
        (28, 1, 9, 5, 'A602'),
        (15, 2, 2, 1, 'B201'),
        (25, 2, 10, 2, 'B202'),
        (29, 2, 10, 3, 'B203'),
        (30, 2, 2, 4, 'B201'),
        (31, 2, 10, 5, 'B204'),
        (16, 3, 3, 1, 'C304'),
        (26, 3, 3, 2, 'C305'),
        (32, 3, 5, 3, 'C301'),
        (33, 3, 3, 4, 'C302'),
        (34, 3, 5, 5, 'C303'),
        (17, 4, 4, 1, 'D102'),
        (27, 4, 4, 2, 'D103'),
        (35, 4, 7, 3, 'D104'),
        (36, 4, 4, 4, 'D101'),
        (37, 4, 7, 5, 'D105'),
        (38, 5, 4, 4, 'D101'),
        (39, 5, 7, 3, 'D102'),
        (40, 5, 4, 5, 'D103'),
        (41, 6, 7, 4, 'C302'),
        (42, 6, 7, 3, 'C303'),
        (43, 6, 3, 2, 'C304'),
        (44, 7, 9, 4, 'Lab2'),
        (45, 7, 9, 5, 'Lab3'),
        (46, 8, 5, 6, 'C401'),
        (47, 8, 5, 7, 'C402'),
        (48, 8, 5, 1, 'C403'),
        (49, 9, 3, 6, 'C404'),
        (50, 9, 3, 7, 'C405'),
        (51, 10, 6, 8, 'E201'),
        (52, 10, 6, 6, 'E202'),
        (53, 11, 7, 6, 'D201'),
        (54, 11, 7, 7, 'D202'),
        (55, 12, 8, 6, 'C406'),
        (56, 12, 8, 7, 'C407'),
        (57, 13, 4, 6, 'D203'),
        (58, 13, 4, 8, 'D204'),
    ]
    cur.executemany(
        "INSERT INTO classes (class_id, subject_id, professor_id, group_id, room) VALUES (%s, %s, %s, %s, %s) ON CONFLICT (class_id) DO NOTHING;",
        classes
    )

    slots = [
        (1, 1, 1, '09:00', '10:30', 16),
        (2, 1, 1, '10:45', '12:15', 17),
        (3, 1, 2, '09:00', '10:00', 14),
        (4, 1, 2, '10:15', '11:45', 15),
        (5, 1, 3, '13:00', '14:30', 16),
        (6, 1, 4, '09:00', '10:30', 17),
        (7, 1, 5, '10:00', '11:30', 15),
        (52, 1, 5, '13:00', '14:30', 48),
        (53, 1, 3, '10:45', '12:15', 17),
        (8, 2, 2, '10:00', '11:00', 22),
        (9, 2, 3, '09:00', '10:30', 25),
        (10, 2, 4, '13:00', '14:30', 26),
        (11, 2, 5, '09:00', '10:30', 27),
        (12, 2, 1, '14:45', '16:15', 43),
        (13, 3, 2, '09:00', '10:00', 23),
        (14, 3, 3, '14:45', '16:15', 29),
        (15, 3, 4, '10:45', '12:15', 32),
        (16, 3, 5, '13:00', '14:30', 35),
        (17, 3, 1, '13:00', '14:30', 39),
        (18, 3, 4, '14:45', '16:15', 42),
        (19, 4, 3, '13:30', '14:30', 24),
        (20, 4, 1, '10:45', '12:15', 30),
        (21, 4, 2, '13:00', '14:30', 33),
        (22, 4, 4, '14:45', '16:15', 36),
        (23, 4, 5, '09:00', '10:30', 38),
        (24, 4, 2, '14:45', '16:15', 41),
        (25, 4, 3, '10:45', '12:15', 44),
        (26, 5, 4, '13:00', '14:00', 28),
        (27, 5, 1, '14:45', '16:15', 31),
        (28, 5, 3, '09:00', '10:30', 34),
        (29, 5, 2, '16:30', '18:00', 37),
        (30, 5, 5, '14:45', '16:15', 40),
        (31, 5, 2, '10:45', '12:15', 45),
        (32, 6, 1, '14:45', '16:15', 46),
        (33, 6, 2, '13:00', '14:30', 49),
        (34, 6, 3, '10:45', '12:15', 52),
        (35, 6, 4, '13:00', '14:30', 53),
        (36, 6, 5, '13:00', '14:30', 55),
        (37, 6, 2, '14:45', '16:15', 57),
        (38, 7, 2, '14:45', '16:15', 47),
        (39, 7, 3, '14:45', '16:15', 50),
        (40, 7, 4, '10:45', '12:15', 54),
        (41, 7, 5, '14:45', '16:15', 56),
        (42, 8, 1, '13:00', '14:30', 51),
        (43, 8, 4, '14:45', '16:15', 58),
        (44, 1, 4, '13:00', '14:00', 14),
        (45, 3, 4, '13:00', '14:00', 23),
        (46, 4, 5, '10:45', '11:45', 24),
        (47, 3, 3, '10:45', '12:15', 39),
        (48, 6, 3, '14:45', '16:15', 46),
        (49, 7, 4, '14:45', '16:15', 47),
        (50, 6, 5, '14:45', '16:15', 49),
        (51, 7, 5, '09:00', '10:30', 50),
    ]
    cur.executemany(
        "INSERT INTO group_timetable (slot_id, group_id, day_of_week, start_time, end_time, class_id) VALUES (%s, %s, %s, %s, %s, %s) ON CONFLICT (slot_id) DO NOTHING;",
        slots
    )

    enrollments = [
        ('U2410252', 14, 'active'),
        ('U2410252', 15, 'active'),
        ('U2410252', 16, 'active'),
        ('U2410252', 17, 'active'),
        ('U2410252', 48, 'active'),
    ]
    cur.executemany(
        "INSERT INTO student_class_enrollment (student_id, class_id, status) VALUES (%s, %s, %s) ON CONFLICT (student_id, class_id) DO NOTHING;",
        enrollments
    )

    cur.execute(
        "INSERT INTO notification_settings (student_id, enabled, minutes_before) VALUES (%s, %s, %s) ON CONFLICT (student_id) DO NOTHING;",
        ('U2410252', 1, 30)
    )

    today = datetime.now()
    past_date = (today - timedelta(days=2)).strftime('%Y-%m-%d')
    fut1 = (today + timedelta(days=1)).strftime('%Y-%m-%d')
    fut2 = (today + timedelta(days=3)).strftime('%Y-%m-%d')

    sessions = [
        (501, 14, past_date, '09:00', '10:00'),
        (610, 22, fut1, '10:00', '11:00'),
        (615, 24, fut2, '13:30', '14:30'),
    ]
    cur.executemany(
        "INSERT INTO lecture_sessions (session_id, class_id, session_date, start_time, end_time) VALUES (%s, %s, %s, %s, %s) ON CONFLICT (session_id) DO NOTHING;",
        sessions
    )

    cur.execute(
        "INSERT INTO attendance (attendance_id, student_id, session_id, status) VALUES (%s, %s, %s, %s) ON CONFLICT (student_id, session_id) DO NOTHING;",
        (1, 'U2410252', 501, 'absent')
    )


# ====================================================================
# Clean In-Memory Fallback Engine (Zero SQLite, Pure Memory)
# Activated only if Railway PostgreSQL is not linked yet
# ====================================================================

def _init_memory_db():
    global _in_memory_db
    if _in_memory_db is not None:
        return

    logger.info("[DB] Initializing in-memory dataset (Railway PostgreSQL not linked yet)...")
    _in_memory_db = {
        "professors": [
            {"professor_id": 1, "full_name": "Prof. F. Atamurotov", "email": "atamurotov@university.uz"},
            {"professor_id": 2, "full_name": "Prof. N. Karimov", "email": "karimov@university.uz"},
            {"professor_id": 3, "full_name": "Prof. M. Siddiqov", "email": "siddiqov@university.uz"},
            {"professor_id": 4, "full_name": "Prof. D. Umarova", "email": "umarova@university.uz"},
            {"professor_id": 5, "full_name": "Prof. A. Rakhimov", "email": "rakhimov@university.uz"},
            {"professor_id": 6, "full_name": "Prof. Z. Khusanov", "email": "khusanov@university.uz"},
            {"professor_id": 7, "full_name": "Prof. S. Makhmudov", "email": "makhmudov@university.uz"},
            {"professor_id": 8, "full_name": "Prof. G. Karimova", "email": "karimova@university.uz"},
            {"professor_id": 9, "full_name": "Prof. T. Usmonov", "email": "usmonov@university.uz"},
            {"professor_id": 10, "full_name": "Prof. L. Azizova", "email": "azizova@university.uz"},
        ],
        "groups": [
            {"group_id": 1, "group_name": "CIE26-3", "timetable_image_url": "https://images.unsplash.com/photo-1509062522246-3755977927d7"},
            {"group_id": 2, "group_name": "CIE26-5", "timetable_image_url": "https://images.unsplash.com/photo-1523240795612-9a054b0db644"},
            {"group_id": 3, "group_name": "CIE26-2", "timetable_image_url": "https://images.unsplash.com/photo-1516321318423-f06f85e504b3"},
            {"group_id": 4, "group_name": "CIE26-1", "timetable_image_url": "https://images.unsplash.com/photo-1434030216411-0b793f4b4173"},
            {"group_id": 5, "group_name": "CIE26-4", "timetable_image_url": "https://images.unsplash.com/photo-1524178232363-1fb2b075b655"},
            {"group_id": 6, "group_name": "CSE25-1", "timetable_image_url": "https://images.unsplash.com/photo-1519452635265-7b1fbfd1e4e0"},
            {"group_id": 7, "group_name": "CSE25-2", "timetable_image_url": "https://images.unsplash.com/photo-1497633762265-9d179a990aa6"},
            {"group_id": 8, "group_name": "ECE25-1", "timetable_image_url": "https://images.unsplash.com/photo-1532094349884-543bc11b234d"},
        ],
        "students": [
            {"student_id": "U2410252", "full_name": "Asliddin Xolmatov", "group_id": 1, "year_of_study": 2, "telegram_id": 987654321, "telegram_username": "asliddin_dev"},
            {"student_id": "U2410253", "full_name": "Javohir Toshmatov", "group_id": 1, "year_of_study": 2, "telegram_id": None, "telegram_username": "javohir_t"},
            {"student_id": "U2410254", "full_name": "Madina Alimova", "group_id": 2, "year_of_study": 2, "telegram_id": None, "telegram_username": "madina_a"},
            {"student_id": "U2510101", "full_name": "Bekzod Rahimov", "group_id": 4, "year_of_study": 1, "telegram_id": None, "telegram_username": "bekzod_r"},
        ],
        "subjects": [
            {"subject_id": 1, "short_name": "P1", "full_name": "Physics 1", "year_level": 1},
            {"subject_id": 2, "short_name": "AE1", "full_name": "Academic English 1", "year_level": 1},
            {"subject_id": 3, "short_name": "CS101", "full_name": "Computer Science 1", "year_level": 1},
            {"subject_id": 4, "short_name": "M1", "full_name": "Calculus 1", "year_level": 1},
            {"subject_id": 5, "short_name": "MATH102", "full_name": "Linear Algebra", "year_level": 1},
            {"subject_id": 6, "short_name": "DM101", "full_name": "Discrete Mathematics", "year_level": 1},
            {"subject_id": 7, "short_name": "CHEM101", "full_name": "General Chemistry", "year_level": 1},
            {"subject_id": 8, "short_name": "CS201", "full_name": "Data Structures & Algorithms", "year_level": 2},
            {"subject_id": 9, "short_name": "CS202", "full_name": "Object-Oriented Programming", "year_level": 2},
            {"subject_id": 10, "short_name": "ECE201", "full_name": "Computer Architecture", "year_level": 2},
            {"subject_id": 11, "short_name": "STAT201", "full_name": "Probability & Statistics", "year_level": 2},
            {"subject_id": 12, "short_name": "CS203", "full_name": "Database Systems", "year_level": 2},
            {"subject_id": 13, "short_name": "MATH201", "full_name": "Differential Equations", "year_level": 2},
            {"subject_id": 14, "short_name": "CS301", "full_name": "Web Development & Cloud Systems", "year_level": 3},
            {"subject_id": 15, "short_name": "CS302", "full_name": "Operating Systems", "year_level": 3},
        ],
        "classes": [
            {"class_id": 14, "subject_id": 1, "professor_id": 1, "group_id": 1, "room": "A605"},
            {"class_id": 22, "subject_id": 1, "professor_id": 1, "group_id": 2, "room": "A605"},
            {"class_id": 23, "subject_id": 1, "professor_id": 2, "group_id": 3, "room": "B201"},
            {"class_id": 24, "subject_id": 1, "professor_id": 1, "group_id": 4, "room": "A605"},
            {"class_id": 28, "subject_id": 1, "professor_id": 9, "group_id": 5, "room": "A602"},
            {"class_id": 15, "subject_id": 2, "professor_id": 2, "group_id": 1, "room": "B201"},
            {"class_id": 25, "subject_id": 2, "professor_id": 10, "group_id": 2, "room": "B202"},
            {"class_id": 29, "subject_id": 2, "professor_id": 10, "group_id": 3, "room": "B203"},
            {"class_id": 30, "subject_id": 2, "professor_id": 2, "group_id": 4, "room": "B201"},
            {"class_id": 31, "subject_id": 2, "professor_id": 10, "group_id": 5, "room": "B204"},
            {"class_id": 16, "subject_id": 3, "professor_id": 3, "group_id": 1, "room": "C304"},
            {"class_id": 26, "subject_id": 3, "professor_id": 3, "group_id": 2, "room": "C305"},
            {"class_id": 32, "subject_id": 3, "professor_id": 5, "group_id": 3, "room": "C301"},
            {"class_id": 33, "subject_id": 3, "professor_id": 3, "group_id": 4, "room": "C302"},
            {"class_id": 34, "subject_id": 3, "professor_id": 5, "group_id": 5, "room": "C303"},
            {"class_id": 17, "subject_id": 4, "professor_id": 4, "group_id": 1, "room": "D102"},
            {"class_id": 27, "subject_id": 4, "professor_id": 4, "group_id": 2, "room": "D103"},
            {"class_id": 35, "subject_id": 4, "professor_id": 7, "group_id": 3, "room": "D104"},
            {"class_id": 36, "subject_id": 4, "professor_id": 4, "group_id": 4, "room": "D101"},
            {"class_id": 37, "subject_id": 4, "professor_id": 7, "group_id": 5, "room": "D105"},
            {"class_id": 38, "subject_id": 5, "professor_id": 4, "group_id": 4, "room": "D101"},
            {"class_id": 39, "subject_id": 5, "professor_id": 7, "group_id": 3, "room": "D102"},
            {"class_id": 40, "subject_id": 5, "professor_id": 4, "group_id": 5, "room": "D103"},
            {"class_id": 41, "subject_id": 6, "professor_id": 7, "group_id": 4, "room": "C302"},
            {"class_id": 42, "subject_id": 6, "professor_id": 7, "group_id": 3, "room": "C303"},
            {"class_id": 43, "subject_id": 6, "professor_id": 3, "group_id": 2, "room": "C304"},
            {"class_id": 44, "subject_id": 7, "professor_id": 9, "group_id": 4, "room": "Lab2"},
            {"class_id": 45, "subject_id": 7, "professor_id": 9, "group_id": 5, "room": "Lab3"},
            {"class_id": 46, "subject_id": 8, "professor_id": 5, "group_id": 6, "room": "C401"},
            {"class_id": 47, "subject_id": 8, "professor_id": 5, "group_id": 7, "room": "C402"},
            {"class_id": 48, "subject_id": 8, "professor_id": 5, "group_id": 1, "room": "C403"},
            {"class_id": 49, "subject_id": 9, "professor_id": 3, "group_id": 6, "room": "C404"},
            {"class_id": 50, "subject_id": 9, "professor_id": 3, "group_id": 7, "room": "C405"},
            {"class_id": 51, "subject_id": 10, "professor_id": 6, "group_id": 8, "room": "E201"},
            {"class_id": 52, "subject_id": 10, "professor_id": 6, "group_id": 6, "room": "E202"},
            {"class_id": 53, "subject_id": 11, "professor_id": 7, "group_id": 6, "room": "D201"},
            {"class_id": 54, "subject_id": 11, "professor_id": 7, "group_id": 7, "room": "D202"},
            {"class_id": 55, "subject_id": 12, "professor_id": 8, "group_id": 6, "room": "C406"},
            {"class_id": 56, "subject_id": 12, "professor_id": 8, "group_id": 7, "room": "C407"},
            {"class_id": 57, "subject_id": 13, "professor_id": 4, "group_id": 6, "room": "D203"},
            {"class_id": 58, "subject_id": 13, "professor_id": 4, "group_id": 8, "room": "D204"},
        ],
        "group_timetable": [
            {"slot_id": 1, "group_id": 1, "day_of_week": 1, "start_time": "09:00", "end_time": "10:30", "class_id": 16},
            {"slot_id": 2, "group_id": 1, "day_of_week": 1, "start_time": "10:45", "end_time": "12:15", "class_id": 17},
            {"slot_id": 3, "group_id": 1, "day_of_week": 2, "start_time": "09:00", "end_time": "10:00", "class_id": 14},
            {"slot_id": 4, "group_id": 1, "day_of_week": 2, "start_time": "10:15", "end_time": "11:45", "class_id": 15},
            {"slot_id": 5, "group_id": 1, "day_of_week": 3, "start_time": "13:00", "end_time": "14:30", "class_id": 16},
            {"slot_id": 6, "group_id": 1, "day_of_week": 4, "start_time": "09:00", "end_time": "10:30", "class_id": 17},
            {"slot_id": 7, "group_id": 1, "day_of_week": 5, "start_time": "10:00", "end_time": "11:30", "class_id": 15},
            {"slot_id": 52, "group_id": 1, "day_of_week": 5, "start_time": "13:00", "end_time": "14:30", "class_id": 48},
            {"slot_id": 53, "group_id": 1, "day_of_week": 3, "start_time": "10:45", "end_time": "12:15", "class_id": 17},
            {"slot_id": 8, "group_id": 2, "day_of_week": 2, "start_time": "10:00", "end_time": "11:00", "class_id": 22},
            {"slot_id": 9, "group_id": 2, "day_of_week": 3, "start_time": "09:00", "end_time": "10:30", "class_id": 25},
            {"slot_id": 10, "group_id": 2, "day_of_week": 4, "start_time": "13:00", "end_time": "14:30", "class_id": 26},
            {"slot_id": 11, "group_id": 2, "day_of_week": 5, "start_time": "09:00", "end_time": "10:30", "class_id": 27},
            {"slot_id": 12, "group_id": 2, "day_of_week": 1, "start_time": "14:45", "end_time": "16:15", "class_id": 43},
            {"slot_id": 13, "group_id": 3, "day_of_week": 2, "start_time": "09:00", "end_time": "10:00", "class_id": 23},
            {"slot_id": 14, "group_id": 3, "day_of_week": 3, "start_time": "14:45", "end_time": "16:15", "class_id": 29},
            {"slot_id": 15, "group_id": 3, "day_of_week": 4, "start_time": "10:45", "end_time": "12:15", "class_id": 32},
            {"slot_id": 16, "group_id": 3, "day_of_week": 5, "start_time": "13:00", "end_time": "14:30", "class_id": 35},
            {"slot_id": 17, "group_id": 3, "day_of_week": 1, "start_time": "13:00", "end_time": "14:30", "class_id": 39},
            {"slot_id": 18, "group_id": 3, "day_of_week": 4, "start_time": "14:45", "end_time": "16:15", "class_id": 42},
            {"slot_id": 19, "group_id": 4, "day_of_week": 3, "start_time": "13:30", "end_time": "14:30", "class_id": 24},
            {"slot_id": 20, "group_id": 4, "day_of_week": 1, "start_time": "10:45", "end_time": "12:15", "class_id": 30},
            {"slot_id": 21, "group_id": 4, "day_of_week": 2, "start_time": "13:00", "end_time": "14:30", "class_id": 33},
            {"slot_id": 22, "group_id": 4, "day_of_week": 4, "start_time": "14:45", "end_time": "16:15", "class_id": 36},
            {"slot_id": 23, "group_id": 4, "day_of_week": 5, "start_time": "09:00", "end_time": "10:30", "class_id": 38},
            {"slot_id": 24, "group_id": 4, "day_of_week": 2, "start_time": "14:45", "end_time": "16:15", "class_id": 41},
            {"slot_id": 25, "group_id": 4, "day_of_week": 3, "start_time": "10:45", "end_time": "12:15", "class_id": 44},
            {"slot_id": 26, "group_id": 5, "day_of_week": 4, "start_time": "13:00", "end_time": "14:00", "class_id": 28},
            {"slot_id": 27, "group_id": 5, "day_of_week": 1, "start_time": "14:45", "end_time": "16:15", "class_id": 31},
            {"slot_id": 28, "group_id": 5, "day_of_week": 3, "start_time": "09:00", "end_time": "10:30", "class_id": 34},
            {"slot_id": 29, "group_id": 5, "day_of_week": 2, "start_time": "16:30", "end_time": "18:00", "class_id": 37},
            {"slot_id": 30, "group_id": 5, "day_of_week": 5, "start_time": "14:45", "end_time": "16:15", "class_id": 40},
            {"slot_id": 31, "group_id": 5, "day_of_week": 2, "start_time": "10:45", "end_time": "12:15", "class_id": 45},
            {"slot_id": 32, "group_id": 6, "day_of_week": 1, "start_time": "14:45", "end_time": "16:15", "class_id": 46},
            {"slot_id": 33, "group_id": 6, "day_of_week": 2, "start_time": "13:00", "end_time": "14:30", "class_id": 49},
            {"slot_id": 34, "group_id": 6, "day_of_week": 3, "start_time": "10:45", "end_time": "12:15", "class_id": 52},
            {"slot_id": 35, "group_id": 6, "day_of_week": 4, "start_time": "13:00", "end_time": "14:30", "class_id": 53},
            {"slot_id": 36, "group_id": 6, "day_of_week": 5, "start_time": "13:00", "end_time": "14:30", "class_id": 55},
            {"slot_id": 37, "group_id": 6, "day_of_week": 2, "start_time": "14:45", "end_time": "16:15", "class_id": 57},
            {"slot_id": 38, "group_id": 7, "day_of_week": 2, "start_time": "14:45", "end_time": "16:15", "class_id": 47},
            {"slot_id": 39, "group_id": 7, "day_of_week": 3, "start_time": "14:45", "end_time": "16:15", "class_id": 50},
            {"slot_id": 40, "group_id": 7, "day_of_week": 4, "start_time": "10:45", "end_time": "12:15", "class_id": 54},
            {"slot_id": 41, "group_id": 7, "day_of_week": 5, "start_time": "14:45", "end_time": "16:15", "class_id": 56},
            {"slot_id": 42, "group_id": 8, "day_of_week": 1, "start_time": "13:00", "end_time": "14:30", "class_id": 51},
            {"slot_id": 43, "group_id": 8, "day_of_week": 4, "start_time": "14:45", "end_time": "16:15", "class_id": 58},
            {"slot_id": 44, "group_id": 1, "day_of_week": 4, "start_time": "13:00", "end_time": "14:00", "class_id": 14},
            {"slot_id": 45, "group_id": 3, "day_of_week": 4, "start_time": "13:00", "end_time": "14:00", "class_id": 23},
            {"slot_id": 46, "group_id": 4, "day_of_week": 5, "start_time": "10:45", "end_time": "11:45", "class_id": 24},
            {"slot_id": 47, "group_id": 3, "day_of_week": 3, "start_time": "10:45", "end_time": "12:15", "class_id": 39},
            {"slot_id": 48, "group_id": 6, "day_of_week": 3, "start_time": "14:45", "end_time": "16:15", "class_id": 46},
            {"slot_id": 49, "group_id": 7, "day_of_week": 4, "start_time": "14:45", "end_time": "16:15", "class_id": 47},
            {"slot_id": 50, "group_id": 6, "day_of_week": 5, "start_time": "14:45", "end_time": "16:15", "class_id": 49},
            {"slot_id": 51, "group_id": 7, "day_of_week": 5, "start_time": "09:00", "end_time": "10:30", "class_id": 50},
        ],
        "student_class_enrollment": [
            {"enrollment_id": 1, "student_id": "U2410252", "class_id": 14, "status": "active", "enrolled_at": "2026-02-01T08:00:00", "dropped_at": None},
            {"enrollment_id": 2, "student_id": "U2410252", "class_id": 15, "status": "active", "enrolled_at": "2026-02-01T08:00:00", "dropped_at": None},
            {"enrollment_id": 3, "student_id": "U2410252", "class_id": 16, "status": "active", "enrolled_at": "2026-02-01T08:00:00", "dropped_at": None},
            {"enrollment_id": 4, "student_id": "U2410252", "class_id": 17, "status": "active", "enrolled_at": "2026-02-01T08:00:00", "dropped_at": None},
            {"enrollment_id": 5, "student_id": "U2410252", "class_id": 48, "status": "active", "enrolled_at": "2026-02-01T08:00:00", "dropped_at": None},
        ],
        "student_schedule_overrides": [],
        "lecture_sessions": [
            {"session_id": 501, "class_id": 14, "session_date": (datetime.now() - timedelta(days=2)).strftime("%Y-%m-%d"), "start_time": "09:00", "end_time": "10:00"},
            {"session_id": 610, "class_id": 22, "session_date": (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d"), "start_time": "10:00", "end_time": "11:00"},
            {"session_id": 615, "class_id": 24, "session_date": (datetime.now() + timedelta(days=3)).strftime("%Y-%m-%d"), "start_time": "13:30", "end_time": "14:30"},
            {"session_id": 620, "class_id": 23, "session_date": (datetime.now() + timedelta(days=4)).strftime("%Y-%m-%d"), "start_time": "09:00", "end_time": "10:00"},
        ],
        "attendance": [
            {"attendance_id": 1, "student_id": "U2410252", "session_id": 501, "status": "absent", "makeup_session_id": None},
        ],
        "notification_settings": [
            {"student_id": "U2410252", "enabled": 1, "minutes_before": 30},
        ],
        "sent_notifications": [],
        "homeworks": [],
        "homework_submissions": [],
    }


def _memory_query(sql: str, params: tuple = ()) -> List[Dict[str, Any]]:
    _init_memory_db()
    sql_clean = sql.strip().upper()

    # Query: students count
    if "SELECT COUNT(*) AS C FROM STUDENTS" in sql_clean or "SELECT COUNT(*) AS C FROM STUDENTS;" in sql_clean:
        return [{"c": len(_in_memory_db["students"])}]

    # Query: classes count
    if "SELECT COUNT(*) AS C FROM CLASSES" in sql_clean:
        return [{"c": len(_in_memory_db["classes"])}]

    # Query: student by telegram_id
    if "FROM STUDENTS S" in sql_clean and "S.TELEGRAM_ID = ?" in sql_clean:
        tg_id = int(params[0])
        for s in _in_memory_db["students"]:
            if s.get("telegram_id") == tg_id:
                grp = next((g for g in _in_memory_db["groups"] if g["group_id"] == s["group_id"]), {"group_name": "CIE26-3"})
                res = dict(s)
                res["group_name"] = grp["group_name"]
                return [res]
        return []

    # Query: student by student_id
    if "FROM STUDENTS S" in sql_clean and ("S.STUDENT_ID = ?" in sql_clean or "UPPER(S.STUDENT_ID) = UPPER(?)" in sql_clean):
        sid = str(params[0]).strip().upper()
        for s in _in_memory_db["students"]:
            if s["student_id"].upper() == sid:
                grp = next((g for g in _in_memory_db["groups"] if g["group_id"] == s["group_id"]), {"group_name": "CIE26-3"})
                res = dict(s)
                res["group_name"] = grp["group_name"]
                return [res]
        return []

    # Query: demo students list
    if "FROM STUDENTS S" in sql_clean and "ORDER BY S.STUDENT_ID" in sql_clean:
        res = []
        for s in _in_memory_db["students"]:
            grp = next((g for g in _in_memory_db["groups"] if g["group_id"] == s["group_id"]), {"group_name": "CIE26-3"})
            item = dict(s)
            item["group_name"] = grp["group_name"]
            res.append(item)
        return res

    # Query: base student timetable slots
    if "FROM GROUP_TIMETABLE GT" in sql_clean and "GT.GROUP_ID = ?" in sql_clean:
        grp_id = int(params[0])
        student_id = str(params[1]) if len(params) > 1 else "U2410252"
        res = []
        for gt in _in_memory_db["group_timetable"]:
            if gt["group_id"] == grp_id:
                # Check if dropped
                is_dropped = any(
                    e["class_id"] == gt["class_id"] and e["student_id"] == student_id and e["status"] == "dropped"
                    for e in _in_memory_db["student_class_enrollment"]
                )
                if is_dropped:
                    continue
                cls = next((c for c in _in_memory_db["classes"] if c["class_id"] == gt["class_id"]), None)
                if not cls:
                    continue
                sub = next((s for s in _in_memory_db["subjects"] if s["subject_id"] == cls["subject_id"]), None)
                prof = next((p for p in _in_memory_db["professors"] if p["professor_id"] == cls["professor_id"]), None)
                grp = next((g for g in _in_memory_db["groups"] if g["group_id"] == gt["group_id"]), None)
                res.append({
                    "slot_id": gt["slot_id"],
                    "day_of_week": gt["day_of_week"],
                    "start_time": gt["start_time"],
                    "end_time": gt["end_time"],
                    "class_id": cls["class_id"],
                    "subject_id": sub["subject_id"] if sub else 1,
                    "subject_short": sub["short_name"] if sub else "GEN",
                    "subject_full": sub["full_name"] if sub else "General Subject",
                    "professor": prof["full_name"] if prof else "Prof. Faculty",
                    "room": cls["room"],
                    "original_group": grp["group_name"] if grp else "CIE26-3",
                    "actual_group": grp["group_name"] if grp else "CIE26-3",
                })
        return sorted(res, key=lambda x: (x["day_of_week"], x["start_time"]))

    # Query: student absences
    if "FROM ATTENDANCE A" in sql_clean and "A.STATUS = 'ABSENT'" in sql_clean:
        sid = str(params[0])
        res = []
        for a in _in_memory_db["attendance"]:
            if a["student_id"] == sid and a["status"] == "absent":
                sess = next((ls for ls in _in_memory_db["lecture_sessions"] if ls["session_id"] == a["session_id"]), None)
                if not sess:
                    continue
                cls = next((c for c in _in_memory_db["classes"] if c["class_id"] == sess["class_id"]), None)
                sub = next((s for s in _in_memory_db["subjects"] if s["subject_id"] == cls["subject_id"]), None) if cls else None
                prof = next((p for p in _in_memory_db["professors"] if p["professor_id"] == cls["professor_id"]), None) if cls else None
                res.append({
                    "attendance_id": a["attendance_id"],
                    "session_id": sess["session_id"],
                    "subject_short": sub["short_name"] if sub else "P1",
                    "subject_full": sub["full_name"] if sub else "Physics 1",
                    "session_date": sess["session_date"],
                    "start_time": sess["start_time"],
                    "end_time": sess["end_time"],
                    "professor": prof["full_name"] if prof else "Prof. F. Atamurotov",
                    "room": cls["room"] if cls else "A605",
                    "status": a["status"],
                    "makeup_session_id": a.get("makeup_session_id"),
                })
        return res

    # Query: enrolled student classes
    if "FROM STUDENT_CLASS_ENROLLMENT E" in sql_clean:
        sid = str(params[0])
        res = []
        for e in _in_memory_db["student_class_enrollment"]:
            if e["student_id"] == sid:
                cls = next((c for c in _in_memory_db["classes"] if c["class_id"] == e["class_id"]), None)
                if not cls:
                    continue
                sub = next((s for s in _in_memory_db["subjects"] if s["subject_id"] == cls["subject_id"]), None)
                prof = next((p for p in _in_memory_db["professors"] if p["professor_id"] == cls["professor_id"]), None)
                grp = next((g for g in _in_memory_db["groups"] if g["group_id"] == cls["group_id"]), None)
                res.append({
                    "class_id": cls["class_id"],
                    "subject_id": sub["subject_id"] if sub else 1,
                    "subject_short": sub["short_name"] if sub else "",
                    "subject_full": sub["full_name"] if sub else "",
                    "year_level": sub.get("year_level", 1) if sub else 1,
                    "professor": prof["full_name"] if prof else "",
                    "group_name": grp["group_name"] if grp else "",
                    "room": cls["room"],
                    "status": e["status"],
                    "enrolled_at": e.get("enrolled_at"),
                    "dropped_at": e.get("dropped_at"),
                })
        return res

    # Query: notification settings
    if "FROM NOTIFICATION_SETTINGS" in sql_clean:
        sid = str(params[0]) if params else "U2410252"
        row = next((n for n in _in_memory_db["notification_settings"] if n["student_id"] == sid), None)
        if row:
            return [row]
        return [{"enabled": 1, "minutes_before": 30}]

    # Query: retake catalog subjects
    if "FROM SUBJECTS" in sql_clean and "YEAR_LEVEL" in sql_clean:
        max_year = int(params[0]) if params else 2
        return [s for s in _in_memory_db["subjects"] if s.get("year_level", 1) <= max_year]

    # Default fallback
    return []


def _memory_execute(sql: str, params: tuple = ()) -> int:
    _init_memory_db()
    sql_clean = sql.strip().upper()

    # Link Telegram ID
    if "UPDATE STUDENTS SET TELEGRAM_ID = ?" in sql_clean:
        tg_id = int(params[0])
        tg_username = params[1]
        sid = params[2]
        for s in _in_memory_db["students"]:
            if s["student_id"].upper() == sid.upper():
                s["telegram_id"] = tg_id
                s["telegram_username"] = tg_username
                return 1
        return 0

    # Drop class
    if "UPDATE STUDENT_CLASS_ENROLLMENT" in sql_clean and "STATUS = 'DROPPED'" in sql_clean:
        dropped_at = params[0]
        sid = params[1]
        for e in _in_memory_db["student_class_enrollment"]:
            if e["student_id"] == sid:
                e["status"] = "dropped"
                e["dropped_at"] = dropped_at
        return 1

    # Update notification settings
    if "UPDATE NOTIFICATION_SETTINGS" in sql_clean:
        sid = params[-1]
        for n in _in_memory_db["notification_settings"]:
            if n["student_id"] == sid:
                if len(params) >= 3:
                    n["enabled"] = params[0]
                    n["minutes_before"] = params[1]
                return 1
        return 1

    return 1

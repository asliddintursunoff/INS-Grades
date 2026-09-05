import os
import re
import logging
from typing import Any, List, Dict, Optional

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

logger = logging.getLogger("backend.database")

# Custom exception for explicit database connection errors
class DatabaseConnectionError(Exception):
    """Raised when Railway PostgreSQL cannot be reached or credentials are missing."""
    pass

# Railway PostgreSQL environment variables
DATABASE_URL = os.getenv("DATABASE_URL") or os.getenv("DATABASE_PUBLIC_URL")
if DATABASE_URL and DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

PGHOST = os.getenv("PGHOST")
PGPORT = os.getenv("PGPORT", "5432")
PGUSER = os.getenv("PGUSER")
PGPASSWORD = os.getenv("PGPASSWORD")
PGDATABASE = os.getenv("PGDATABASE")

# Check if PostgreSQL credentials are configured
HAS_POSTGRES_CONFIG = bool(DATABASE_URL or (PGHOST and PGUSER and PGDATABASE))

# Store the last connection error message for diagnostics
LAST_CONNECTION_ERROR: Optional[str] = None


def get_pg_connection():
    """
    Obtain an active connection to Railway PostgreSQL.
    STRICT: Never falls back to any other database.
    Raises DatabaseConnectionError if connection fails.
    """
    global LAST_CONNECTION_ERROR

    if not HAS_POSTGRES_CONFIG:
        err_msg = (
            "Database connection error: DATABASE_URL environment variable is missing. "
            "Please configure DATABASE_URL in your Railway backend service variables."
        )
        LAST_CONNECTION_ERROR = err_msg
        raise DatabaseConnectionError(err_msg)

    try:
        import psycopg2
        from psycopg2.extras import RealDictCursor
    except ImportError:
        err_msg = "Database connection error: psycopg2 driver is not installed."
        LAST_CONNECTION_ERROR = err_msg
        raise DatabaseConnectionError(err_msg)

    try:
        if DATABASE_URL:
            # Connect using Railway PostgreSQL URL
            conn = psycopg2.connect(
                DATABASE_URL,
                cursor_factory=RealDictCursor,
                connect_timeout=5,
                sslmode="require" if "railway" in DATABASE_URL else "prefer"
            )
        else:
            conn = psycopg2.connect(
                host=PGHOST,
                port=int(PGPORT),
                user=PGUSER,
                password=PGPASSWORD,
                dbname=PGDATABASE,
                cursor_factory=RealDictCursor,
                connect_timeout=5
            )
        conn.autocommit = True
        LAST_CONNECTION_ERROR = None
        return conn
    except Exception as e:
        err_msg = f"Database connection error: Failed to connect to Railway PostgreSQL database. Detail: {str(e)}"
        LAST_CONNECTION_ERROR = err_msg
        logger.error(f"[DB] {err_msg}")
        raise DatabaseConnectionError(err_msg)


def is_postgres_active() -> bool:
    """Check if Railway PostgreSQL is actively responding to queries."""
    if not HAS_POSTGRES_CONFIG:
        return False
    try:
        conn = get_pg_connection()
        with conn.cursor() as cur:
            cur.execute("SELECT 1;")
        conn.close()
        return True
    except Exception:
        return False


def get_connection_status() -> Dict[str, Any]:
    """Return explicit connection status for diagnostics."""
    active = is_postgres_active()
    return {
        "connected": active,
        "database": "Railway PostgreSQL",
        "configured": HAS_POSTGRES_CONFIG,
        "error": LAST_CONNECTION_ERROR if not active else None
    }


def query(sql: str, params: tuple = ()) -> List[Dict[str, Any]]:
    """
    Execute a SELECT query on Railway PostgreSQL.
    STRICT: Always queries the user's PostgreSQL database.
    Raises DatabaseConnectionError if the database is unreachable.
    """
    conn = get_pg_connection()
    try:
        with conn.cursor() as cur:
            # Convert SQLite '?' placeholders to PostgreSQL '%s'
            pg_sql = sql.replace("?", "%s")
            cur.execute(pg_sql, params)
            if cur.description:
                rows = cur.fetchall()
                return [dict(row) for row in rows]
            return []
    except DatabaseConnectionError:
        raise
    except Exception as e:
        logger.error(f"[DB] PostgreSQL Query error: {e} | SQL: {sql}")
        raise DatabaseConnectionError(f"Database query error: {str(e)}")
    finally:
        conn.close()


def execute(sql: str, params: tuple = ()) -> int:
    """
    Execute an INSERT/UPDATE/DELETE query on Railway PostgreSQL.
    STRICT: Always executes on the user's PostgreSQL database.
    Raises DatabaseConnectionError if the database is unreachable.
    """
    conn = get_pg_connection()
    try:
        with conn.cursor() as cur:
            pg_sql = sql.replace("?", "%s")
            cur.execute(pg_sql, params)
            return cur.rowcount
    except DatabaseConnectionError:
        raise
    except Exception as e:
        logger.error(f"[DB] PostgreSQL Execute error: {e} | SQL: {sql}")
        raise DatabaseConnectionError(f"Database execute error: {str(e)}")
    finally:
        conn.close()


def init_db():
    """
    Initialize database schema in Railway PostgreSQL.
    STRICT: Only creates tables if they do NOT exist (IF NOT EXISTS).
    NEVER overwrites, modifies, or seeds dummy records into existing user data.
    """
    global LAST_CONNECTION_ERROR
    if not HAS_POSTGRES_CONFIG:
        err_msg = (
            "Database connection error: DATABASE_URL is not configured. "
            "Please link your Railway PostgreSQL database."
        )
        LAST_CONNECTION_ERROR = err_msg
        logger.warning(f"[DB] {err_msg}")
        return

    try:
        conn = get_pg_connection()
        logger.info("[DB] Verifying Railway PostgreSQL tables...")
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
        conn.close()
        logger.info("[DB] Railway PostgreSQL schema verified. User data preserved.")
    except Exception as e:
        err_msg = f"Failed to initialize PostgreSQL schema: {str(e)}"
        LAST_CONNECTION_ERROR = err_msg
        logger.error(f"[DB] {err_msg}")

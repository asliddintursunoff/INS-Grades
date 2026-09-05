import os
import re
import logging
import urllib.parse
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

# Store the last connection error message for diagnostics
LAST_CONNECTION_ERROR: Optional[str] = None

# Backward compatibility flag
HAS_POSTGRES_CONFIG: bool = bool(
    os.getenv("DATABASE_URL")
    or os.getenv("DATABASE_PUBLIC_URL")
    or os.getenv("DB_HOST")
    or os.getenv("PGHOST")
    or os.getenv("DB_PASSWORD")
    or os.getenv("PGPASSWORD")
)


def _mask_secret(s: Optional[str]) -> str:
    """Safely mask secrets for logging diagnostics."""
    if not s:
        return "<none>"
    if len(s) <= 4:
        return "***"
    return f"{s[:2]}...{s[-2:]} (len {len(s)})"


def _get_connection_candidates() -> List[Dict[str, Any]]:
    """
    Build connection candidates dynamically in priority order.
    Top Priority: Explicit individual environment variables entered by hand:
      - DB_HOST (or PGHOST, POSTGRES_HOST)
      - DB_PORT (or PGPORT, POSTGRES_PORT)
      - DB_USER (or PGUSER, POSTGRES_USER)
      - DB_PASSWORD (or PGPASSWORD, POSTGRES_PASSWORD)
      - DB_NAME (or PGDATABASE, POSTGRES_DB)
      - DB_SSLMODE (optional: disable, require, prefer)
    Fallback: DATABASE_URL and DATABASE_PUBLIC_URL
    """
    candidates = []

    # Manual individual environment variables (Highest priority)
    db_host = (os.getenv("DB_HOST") or os.getenv("PGHOST") or os.getenv("POSTGRES_HOST") or "").strip()
    db_port_raw = (os.getenv("DB_PORT") or os.getenv("PGPORT") or os.getenv("POSTGRES_PORT") or "5432").strip()
    db_port = int(db_port_raw) if db_port_raw.isdigit() else 5432
    db_user = (os.getenv("DB_USER") or os.getenv("PGUSER") or os.getenv("POSTGRES_USER") or "postgres").strip()
    db_pass = (os.getenv("DB_PASSWORD") or os.getenv("PGPASSWORD") or os.getenv("POSTGRES_PASSWORD") or "").strip()
    db_name = (os.getenv("DB_NAME") or os.getenv("PGDATABASE") or os.getenv("POSTGRES_DB") or "railway").strip()
    db_sslmode = (os.getenv("DB_SSLMODE") or "").strip().lower()

    if db_host and db_pass:
        is_internal = "railway.internal" in db_host or "localhost" in db_host or "127.0.0.1" in db_host
        is_external_proxy = "proxy.rlwy.net" in db_host

        ssl_modes_to_try = []
        if db_sslmode:
            ssl_modes_to_try.append(db_sslmode)
        elif is_external_proxy:
            ssl_modes_to_try = ["require", "prefer"]
        elif is_internal:
            ssl_modes_to_try = ["prefer", "disable", "require"]
        else:
            ssl_modes_to_try = ["prefer", "require", "disable"]

        for mode in ssl_modes_to_try:
            candidates.append({
                "desc": f"Individual Env Vars (host={db_host}:{db_port}, user={db_user}, db={db_name}, pass={_mask_secret(db_pass)}, ssl={mode})",
                "kwargs": {
                    "host": db_host,
                    "port": db_port,
                    "user": db_user,
                    "password": db_pass,
                    "dbname": db_name,
                    "sslmode": mode,
                    "connect_timeout": 5,
                }
            })

    # Fallback: Parse DATABASE_URL and DATABASE_PUBLIC_URL
    urls_to_try = []
    db_url = os.getenv("DATABASE_URL")
    pub_url = os.getenv("DATABASE_PUBLIC_URL")
    if db_url:
        urls_to_try.append(("DATABASE_URL", db_url))
    if pub_url and pub_url != db_url:
        urls_to_try.append(("DATABASE_PUBLIC_URL", pub_url))

    for url_label, raw_url in urls_to_try:
        norm_url = raw_url.strip()
        if norm_url.startswith("postgres://"):
            norm_url = norm_url.replace("postgres://", "postgresql://", 1)

        try:
            parsed = urllib.parse.urlparse(norm_url)
            user = urllib.parse.unquote(parsed.username or "postgres")
            raw_password = parsed.password or ""
            unquoted_password = urllib.parse.unquote(raw_password)
            host = parsed.hostname or "localhost"
            port = parsed.port or 5432
            dbname = parsed.path.lstrip("/") if parsed.path else "railway"
            is_internal = "railway.internal" in host or "localhost" in host

            # Use keyword args with unquoted password
            # For internal Railway connections, disable or prefer SSL
            sslmode = "disable" if is_internal else "require"

            candidates.append({
                "desc": f"{url_label} parsed with unquoted password (host={host}:{port}, user={user}, pass={_mask_secret(unquoted_password)}, ssl={sslmode})",
                "kwargs": {
                    "host": host,
                    "port": port,
                    "user": user,
                    "password": unquoted_password,
                    "dbname": dbname,
                    "sslmode": sslmode,
                    "connect_timeout": 5,
                }
            })

            # Also try with sslmode=prefer
            candidates.append({
                "desc": f"{url_label} parsed (host={host}:{port}, user={user}, ssl=prefer)",
                "kwargs": {
                    "host": host,
                    "port": port,
                    "user": user,
                    "password": unquoted_password,
                    "dbname": dbname,
                    "sslmode": "prefer",
                    "connect_timeout": 5,
                }
            })

            # If unquoted differs from raw password, try raw password
            if unquoted_password != raw_password:
                candidates.append({
                    "desc": f"{url_label} parsed with raw password (host={host}:{port}, user={user})",
                    "kwargs": {
                        "host": host,
                        "port": port,
                        "user": user,
                        "password": raw_password,
                        "dbname": dbname,
                        "sslmode": sslmode,
                        "connect_timeout": 5,
                    }
                })

            # Fallback to direct DSN string
            candidates.append({
                "desc": f"{url_label} direct DSN string (sslmode={'disable' if is_internal else 'prefer'})",
                "dsn": norm_url,
                "kwargs": {
                    "sslmode": "disable" if is_internal else "prefer",
                    "connect_timeout": 5,
                }
            })
        except Exception as pe:
            logger.warning(f"[DB] Error parsing {url_label}: {pe}")
            candidates.append({
                "desc": f"{url_label} raw DSN fallback",
                "dsn": norm_url,
                "kwargs": {"connect_timeout": 5}
            })

    return candidates


def get_pg_connection():
    """
    Obtain an active connection to Railway PostgreSQL.
    STRICT: Never falls back to SQLite or mock data.
    Raises DatabaseConnectionError if connection fails.
    """
    global LAST_CONNECTION_ERROR

    try:
        import psycopg2
        from psycopg2.extras import RealDictCursor
    except ImportError:
        err_msg = "Database connection error: psycopg2 driver is not installed."
        LAST_CONNECTION_ERROR = err_msg
        raise DatabaseConnectionError(err_msg)

    candidates = _get_connection_candidates()
    if not candidates:
        err_msg = (
            "Database connection error: Neither DATABASE_URL nor PGHOST/PGPASSWORD environment variables are set. "
            "Please configure DATABASE_URL in your Railway backend service variables."
        )
        LAST_CONNECTION_ERROR = err_msg
        raise DatabaseConnectionError(err_msg)

    attempt_errors = []
    for cand in candidates:
        try:
            if "dsn" in cand:
                conn = psycopg2.connect(
                    cand["dsn"],
                    cursor_factory=RealDictCursor,
                    **cand.get("kwargs", {})
                )
            else:
                conn = psycopg2.connect(
                    cursor_factory=RealDictCursor,
                    **cand["kwargs"]
                )
            conn.autocommit = True
            LAST_CONNECTION_ERROR = None
            logger.info(f"[DB] Connected successfully via {cand['desc']}")
            return conn
        except Exception as e:
            err_str = str(e).strip()
            attempt_errors.append(f"{cand['desc']} -> {err_str}")
            logger.debug(f"[DB] Candidate failed: {cand['desc']} - {err_str}")

    # All candidates failed
    last_err = attempt_errors[-1] if attempt_errors else "Unknown connection error"
    err_msg = (
        f"Database connection error: Failed to connect to Railway PostgreSQL database across {len(candidates)} connection methods. "
        f"Detail: {last_err}"
    )
    LAST_CONNECTION_ERROR = err_msg
    logger.error(f"[DB] {err_msg}")
    raise DatabaseConnectionError(err_msg)


def is_postgres_active() -> bool:
    """Check if Railway PostgreSQL is actively responding to queries."""
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
    candidates = _get_connection_candidates()
    return {
        "connected": active,
        "database": "Railway PostgreSQL",
        "configured": len(candidates) > 0,
        "candidates_available": len(candidates),
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
    candidates = _get_connection_candidates()
    if not candidates:
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

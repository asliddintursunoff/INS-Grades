import os
import hmac
import hashlib
import time
import json
import logging
from contextlib import asynccontextmanager
from typing import Optional, Dict, Any, List
from urllib.parse import parse_qsl

from fastapi import FastAPI, Request, Response, HTTPException, status, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

from database import (
    init_db,
    query,
    execute,
    is_postgres_active,
    get_connection_status,
    DatabaseConnectionError,
    HAS_POSTGRES_CONFIG,
)
from services.timetable_service import (
    get_effective_schedule,
    get_available_groups_for_subject,
    change_student_group,
    revert_student_override,
)
from services.enrollment_service import (
    get_student_classes,
    drop_class,
    retake_class,
    get_retake_catalog,
    enroll_retake_class,
)
from services.attendance_service import (
    get_student_absences,
    suggest_makeup_sessions,
    record_makeup,
)
from services.notification_service import (
    get_notification_settings,
    update_notification_settings,
    get_upcoming_sessions_for_scheduler,
    mark_notification_sent,
)
from telegram_bot import bot_instance

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("backend")

# ==================== Security & Configuration ====================

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "7963381665:AAFljS3q8j5GvFp-7u2vK5Dq5f5mBqW9X5A")

# Secure API Key for protected endpoints (Never expose to frontend!)
API_KEY = os.getenv("API_KEY") or os.getenv("INTERNAL_KEY") or os.getenv("INTERNAL_API_KEY") or "ins_secure_api_key_2026_default"

# Rate limiting configuration (requests per minute per IP)
RATE_LIMIT_PER_MINUTE = int(os.getenv("RATE_LIMIT_PER_MINUTE", "60"))
_rate_limit_store: Dict[str, List[float]] = {}

# Ephemeral session secret for browser frontend (avoids exposing master API_KEY)
SESSION_SECRET = hashlib.sha256(API_KEY.encode()).hexdigest()

# ==================== Lifespan ====================

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    logger.info("[INS-Grades] Initializing Railway PostgreSQL connection...")
    init_db()
    if is_postgres_active():
        logger.info("[INS-Grades] Connected to Railway PostgreSQL successfully.")
    else:
        logger.warning("[INS-Grades] Railway PostgreSQL is currently NOT connected. Check DATABASE_URL.")

    await bot_instance.start()
    yield
    # Shutdown
    logger.info("[INS-Grades] Shutting down...")
    await bot_instance.stop()

app = FastAPI(
    title="INS Grades University Timetable API",
    description="Secure Backend API in Python & FastAPI for INS Grades with Railway PostgreSQL",
    version="2.1.0",
    lifespan=lifespan,
)

# ==================== Rate Limiting Middleware ====================

@app.middleware("http")
async def rate_limiting_middleware(request: Request, call_next):
    # Allow CORS preflight requests without rate limiting
    if request.method == "OPTIONS":
        return await call_next(request)

    client_ip = request.client.host if request.client else "unknown"
    now = time.time()
    minute_ago = now - 60.0

    # Prune old timestamps
    timestamps = _rate_limit_store.get(client_ip, [])
    timestamps = [t for t in timestamps if t > minute_ago]

    if len(timestamps) >= RATE_LIMIT_PER_MINUTE:
        reset_time = int(timestamps[0] + 60.0 - now) if timestamps else 60
        return JSONResponse(
            status_code=429,
            content={
                "error": "Too Many Requests",
                "message": f"Rate limit of {RATE_LIMIT_PER_MINUTE} requests per minute exceeded. Please slow down.",
                "retry_after_seconds": max(1, reset_time),
            },
            headers={
                "Retry-After": str(max(1, reset_time)),
                "X-RateLimit-Limit": str(RATE_LIMIT_PER_MINUTE),
                "X-RateLimit-Remaining": "0",
            },
        )

    timestamps.append(now)
    _rate_limit_store[client_ip] = timestamps

    response = await call_next(request)
    remaining = max(0, RATE_LIMIT_PER_MINUTE - len(timestamps))
    response.headers["X-RateLimit-Limit"] = str(RATE_LIMIT_PER_MINUTE)
    response.headers["X-RateLimit-Remaining"] = str(remaining)
    return response

# ==================== Database Exception Handler ====================

@app.exception_handler(DatabaseConnectionError)
async def db_connection_exception_handler(request: Request, exc: DatabaseConnectionError):
    return JSONResponse(
        status_code=503,
        content={
            "error": "Database connection error",
            "message": str(exc),
            "hint": "Please verify that DATABASE_URL is set in your Railway project variables and the PostgreSQL service is active.",
        },
    )

# ==================== Proper CORS Configuration ====================

allowed_origins_env = os.getenv(
    "ALLOWED_ORIGINS",
    "https://ins-grades.vercel.app,http://localhost:3000,http://localhost:5173"
)
allowed_origins_list = [origin.strip() for origin in allowed_origins_env.split(",") if origin.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins_list,
    allow_origin_regex=r"https://(ins-grades.*\.vercel\.app|web\.telegram\.org)",
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=[
        "Content-Type",
        "Authorization",
        "X-API-Key",
        "X-Session-Token",
        "X-Internal-Key",
        "X-Requested-With",
        "Accept",
    ],
)

# ==================== Authentication & Verification ====================

def verify_telegram_init_data(init_data: str) -> Optional[Dict[str, Any]]:
    """
    Cryptographically verify Telegram WebApp initData with BOT_TOKEN using HMAC-SHA256.
    Allows authentication without registration or password login.
    """
    if not init_data or not BOT_TOKEN:
        return None
    try:
        parsed_data = dict(parse_qsl(init_data))
        if "hash" not in parsed_data:
            return None

        received_hash = parsed_data.pop("hash")
        data_check_string = "\n".join(f"{k}={v}" for k, v in sorted(parsed_data.items()))

        secret_key = hmac.new(b"WebAppData", BOT_TOKEN.encode(), hashlib.sha256).digest()
        calculated_hash = hmac.new(secret_key, data_check_string.encode(), hashlib.sha256).hexdigest()

        if hmac.compare_digest(calculated_hash, received_hash):
            user_data = parsed_data.get("user")
            return json.loads(user_data) if user_data else parsed_data
        return None
    except Exception as e:
        logger.warning(f"Telegram initData verification failed: {e}")
        return None

def verify_session_token(token: str) -> bool:
    """Verify signed ephemeral session token for browser clients."""
    if not token or ":" not in token:
        return False
    try:
        parts = token.split(":")
        if len(parts) != 3:
            return False
        ip, timestamp_str, signature = parts
        timestamp = float(timestamp_str)
        # Session token expires after 4 hours
        if time.time() - timestamp > 14400:
            return False

        message = f"{ip}:{timestamp_str}"
        expected_sig = hmac.new(SESSION_SECRET.encode(), message.encode(), hashlib.sha256).hexdigest()
        return hmac.compare_digest(expected_sig, signature)
    except Exception:
        return False

def require_api_auth(request: Request) -> Dict[str, Any]:
    """
    Authentication dependency for protected endpoints.
    Allows:
      1. Master API Key in 'X-API-Key' or 'Authorization: Bearer <key>'
      2. Authenticated Telegram WebApp in 'Authorization: TelegramWebApp <initData>'
      3. Ephemeral Frontend Session Token in 'X-Session-Token'
      4. Internal bot calls with 'X-Internal-Key'
    """
    # 1. Check API Key Header
    api_key_header = request.headers.get("x-api-key")
    if api_key_header and hmac.compare_digest(api_key_header, API_KEY):
        return {"auth_type": "api_key"}

    # 2. Check Authorization Bearer or TelegramWebApp
    auth_header = request.headers.get("authorization", "")
    if auth_header.startswith("Bearer "):
        token = auth_header[7:].strip()
        if hmac.compare_digest(token, API_KEY):
            return {"auth_type": "api_key"}
        if verify_session_token(token):
            return {"auth_type": "session_token"}

    if auth_header.startswith("TelegramWebApp "):
        init_data = auth_header[15:].strip()
        tg_user = verify_telegram_init_data(init_data)
        if tg_user:
            return {"auth_type": "telegram_webapp", "user": tg_user}

    # 3. Check Session Token Header
    session_token = request.headers.get("x-session-token")
    if session_token and verify_session_token(session_token):
        return {"auth_type": "session_token"}

    # 4. Check Internal Key
    internal_key = request.headers.get("x-internal-key")
    if internal_key and hmac.compare_digest(internal_key, API_KEY):
        return {"auth_type": "internal_key"}

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Unauthorized: Protected endpoint requires valid API key (X-API-Key / Bearer) or Telegram authentication.",
    )

def resolve_student(tg_or_id: Any) -> Optional[Dict[str, Any]]:
    """Resolve student from PostgreSQL by telegram_id or student_id."""
    if not tg_or_id:
        return None

    # Check numeric telegram_id
    if str(tg_or_id).isdigit():
        found = query(
            "SELECT s.*, g.group_name FROM students s JOIN groups g ON s.group_id = g.group_id WHERE s.telegram_id = ?",
            (int(tg_or_id),)
        )
        if found:
            return found[0]

    # Check student_id
    found_sid = query(
        "SELECT s.*, g.group_name FROM students s JOIN groups g ON s.group_id = g.group_id WHERE UPPER(s.student_id) = UPPER(?)",
        (str(tg_or_id),)
    )
    if found_sid:
        return found_sid[0]

    return None

# ==================== Pydantic Models ====================

class LinkStudentRequest(BaseModel):
    student_id: str
    telegram_id: int
    telegram_username: Optional[str] = None

class ClassActionRequest(BaseModel):
    class_id: int

class ChangeGroupRequest(BaseModel):
    old_class_id: int
    new_class_id: int
    change_type: Optional[str] = "one_time"

class RevertOverrideRequest(BaseModel):
    subject_id: int

class MakeupRequest(BaseModel):
    student_telegram_id: Optional[str] = None
    makeup_session_id: int

class NotificationSettingsRequest(BaseModel):
    enabled: Optional[bool] = None
    minutes_before: Optional[int] = None

class MarkSentRequest(BaseModel):
    telegram_id: int
    session_id: int

# ==================== Public Endpoints ====================

@app.get("/")
@app.get("/api/health")
@app.get("/api/health/")
def health_check():
    """Public health check endpoint testing PostgreSQL connection."""
    db_status = get_connection_status()
    is_healthy = db_status["connected"]

    response_payload = {
        "status": "healthy" if is_healthy else "database_connection_error",
        "service": "INS Grades University Timetable API",
        "framework": "FastAPI (Python 3.11)",
        "security": "API-Key & Telegram HMAC Enabled",
        "database": db_status["database"],
        "database_connected": is_healthy,
        "database_error": db_status["error"],
    }

    if not is_healthy:
        return JSONResponse(status_code=503, content=response_payload)
    return response_payload

@app.post("/api/auth/session")
@app.post("/api/auth/session/")
def create_client_session(request: Request):
    """
    Public handshake endpoint for frontend clients.
    Issues a short-lived ephemeral session token without requiring registration or exposing API_KEY.
    """
    client_ip = request.client.host if request.client else "web_client"
    timestamp_str = str(time.time())
    message = f"{client_ip}:{timestamp_str}"
    signature = hmac.new(SESSION_SECRET.encode(), message.encode(), hashlib.sha256).hexdigest()
    session_token = f"{client_ip}:{timestamp_str}:{signature}"

    return {
        "session_token": session_token,
        "expires_in_seconds": 14400,
        "auth_type": "ephemeral_client_session"
    }

# ==================== Protected Endpoints ====================

@app.get("/api/system/status", dependencies=[Depends(require_api_auth)])
@app.get("/api/system/status/", dependencies=[Depends(require_api_auth)])
def system_status():
    db_status = get_connection_status()
    is_active = db_status["connected"]
    student_count = 0
    class_count = 0

    if is_active:
        try:
            student_res = query("SELECT COUNT(*) as c FROM students;")
            student_count = student_res[0]["c"] if student_res else 0
            class_res = query("SELECT COUNT(*) as c FROM classes;")
            class_count = class_res[0]["c"] if class_res else 0
        except Exception:
            pass

    return {
        "status": "ok" if is_active else "database_connection_error",
        "database": "Railway PostgreSQL",
        "postgres_connected": is_active,
        "database_connected": is_active,
        "database_error": db_status.get("error"),
        "framework": "FastAPI (Python)",
        "bot_active": True,
        "bot_username": "INS_gradesbot",
        "student_count": student_count,
        "class_count": class_count,
    }

@app.get("/api/demo/students", dependencies=[Depends(require_api_auth)])
@app.get("/api/demo/students/", dependencies=[Depends(require_api_auth)])
def get_demo_students():
    db_status = get_connection_status()
    if not db_status["connected"]:
        return JSONResponse(
            status_code=503,
            content={
                "error": "Database connection error",
                "message": db_status.get("error") or "Railway PostgreSQL is not connected.",
                "database_connected": False,
                "students": [],
            }
        )
    try:
        students = query(
            """SELECT s.student_id, s.full_name, s.telegram_id, s.telegram_username, g.group_name
               FROM students s
               JOIN groups g ON s.group_id = g.group_id
               ORDER BY s.student_id"""
        )
        return {"students": students, "database_connected": True}
    except DatabaseConnectionError as dbe:
        return JSONResponse(
            status_code=503,
            content={
                "error": "Database connection error",
                "message": str(dbe),
                "database_connected": False,
                "students": [],
            }
        )

@app.get("/api/auth/me/{telegram_id}", dependencies=[Depends(require_api_auth)])
@app.get("/api/auth/me/{telegram_id}/", dependencies=[Depends(require_api_auth)])
def get_current_user(telegram_id: str):
    if not telegram_id or not telegram_id.isdigit():
        return {"found": False}

    student_rows = query(
        """SELECT s.student_id, s.full_name, s.group_id, s.year_of_study, s.telegram_id, s.telegram_username, g.group_name 
           FROM students s 
           JOIN groups g ON s.group_id = g.group_id 
           WHERE s.telegram_id = ?""",
        (int(telegram_id),)
    )
    if not student_rows:
        return {"found": False}

    s = student_rows[0]
    return {
        "found": True,
        "student": {
            "student_id": s["student_id"],
            "full_name": s["full_name"],
            "group_name": s["group_name"],
            "year_of_study": s.get("year_of_study") or 2,
            "telegram_id": s["telegram_id"],
            "telegram_username": s["telegram_username"],
        }
    }

@app.post("/api/auth/link", dependencies=[Depends(require_api_auth)])
@app.post("/api/auth/link/", dependencies=[Depends(require_api_auth)])
def link_student(data: LinkStudentRequest):
    clean_id = data.student_id.strip()
    student_rows = query(
        """SELECT s.student_id, s.full_name, s.year_of_study, g.group_name 
           FROM students s 
           JOIN groups g ON s.group_id = g.group_id 
           WHERE UPPER(s.student_id) = UPPER(?)""",
        (clean_id,)
    )
    if not student_rows:
        raise HTTPException(
            status_code=404,
            detail=f"Student ID '{clean_id}' was not found in university database."
        )

    student = student_rows[0]
    execute(
        "UPDATE students SET telegram_id = ?, telegram_username = ? WHERE student_id = ?",
        (data.telegram_id, data.telegram_username, student["student_id"])
    )

    return {
        "success": True,
        "student_id": student["student_id"],
        "full_name": student["full_name"],
        "group_name": student["group_name"],
        "year_of_study": student.get("year_of_study") or 2,
    }

# ==================== Timetable ====================

@app.get("/api/students/{telegram_id}/timetable", dependencies=[Depends(require_api_auth)])
@app.get("/api/students/{telegram_id}/timetable/", dependencies=[Depends(require_api_auth)])
def get_student_timetable(telegram_id: str):
    student = resolve_student(telegram_id)
    if not student:
        raise HTTPException(status_code=404, detail="Student record not found in PostgreSQL database.")
    try:
        schedule_data = get_effective_schedule(student["student_id"])
        return schedule_data
    except DatabaseConnectionError as dbe:
        raise HTTPException(status_code=503, detail=str(dbe))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# ==================== Courses, Retakes, Drops ====================

@app.get("/api/students/{telegram_id}/classes", dependencies=[Depends(require_api_auth)])
@app.get("/api/students/{telegram_id}/classes/", dependencies=[Depends(require_api_auth)])
def get_classes(telegram_id: str):
    student = resolve_student(telegram_id)
    if not student:
        raise HTTPException(status_code=404, detail="Student record not found.")
    classes = get_student_classes(student["student_id"])
    return {"classes": classes}

@app.get("/api/students/{telegram_id}/retake-catalog", dependencies=[Depends(require_api_auth)])
@app.get("/api/students/{telegram_id}/retake-catalog/", dependencies=[Depends(require_api_auth)])
def get_catalog(telegram_id: str):
    student = resolve_student(telegram_id)
    if not student:
        raise HTTPException(status_code=404, detail="Student record not found.")
    return get_retake_catalog(student["student_id"])

@app.post("/api/students/{telegram_id}/enroll-retake", dependencies=[Depends(require_api_auth)])
@app.post("/api/students/{telegram_id}/enroll-retake/", dependencies=[Depends(require_api_auth)])
def enroll_retake(telegram_id: str, data: ClassActionRequest):
    student = resolve_student(telegram_id)
    if not student:
        raise HTTPException(status_code=404, detail="Student record not found.")
    return enroll_retake_class(student["student_id"], data.class_id)

@app.post("/api/students/{telegram_id}/drop", dependencies=[Depends(require_api_auth)])
@app.post("/api/students/{telegram_id}/drop/", dependencies=[Depends(require_api_auth)])
def drop_course(telegram_id: str, data: ClassActionRequest):
    student = resolve_student(telegram_id)
    if not student:
        raise HTTPException(status_code=404, detail="Student record not found.")
    return drop_class(student["student_id"], data.class_id)

@app.post("/api/students/{telegram_id}/retake", dependencies=[Depends(require_api_auth)])
@app.post("/api/students/{telegram_id}/retake/", dependencies=[Depends(require_api_auth)])
def retake_course(telegram_id: str, data: ClassActionRequest):
    student = resolve_student(telegram_id)
    if not student:
        raise HTTPException(status_code=404, detail="Student record not found.")
    return retake_class(student["student_id"], data.class_id)

# ==================== Group Switching ====================

@app.get("/api/subjects/{subject_id}/available-groups", dependencies=[Depends(require_api_auth)])
@app.get("/api/subjects/{subject_id}/available-groups/", dependencies=[Depends(require_api_auth)])
def get_available_groups(subject_id: int, student_telegram_id: Optional[str] = None):
    student = resolve_student(student_telegram_id)
    if not student:
        raise HTTPException(status_code=404, detail="Student record not found.")
    options = get_available_groups_for_subject(subject_id, student["student_id"])
    return {"options": options}

@app.post("/api/students/{telegram_id}/change-group", dependencies=[Depends(require_api_auth)])
@app.post("/api/students/{telegram_id}/change-group/", dependencies=[Depends(require_api_auth)])
def change_group(telegram_id: str, data: ChangeGroupRequest):
    student = resolve_student(telegram_id)
    if not student:
        raise HTTPException(status_code=404, detail="Student record not found.")
    return change_student_group(
        student["student_id"],
        data.old_class_id,
        data.new_class_id,
        data.change_type or "one_time"
    )

@app.post("/api/students/{telegram_id}/revert-override", dependencies=[Depends(require_api_auth)])
@app.post("/api/students/{telegram_id}/revert-override/", dependencies=[Depends(require_api_auth)])
def revert_override(telegram_id: str, data: RevertOverrideRequest):
    student = resolve_student(telegram_id)
    if not student:
        raise HTTPException(status_code=404, detail="Student record not found.")
    return revert_student_override(student["student_id"], data.subject_id)

# ==================== Absences & Makeup ====================

@app.get("/api/students/{telegram_id}/absences", dependencies=[Depends(require_api_auth)])
@app.get("/api/students/{telegram_id}/absences/", dependencies=[Depends(require_api_auth)])
def get_absences(telegram_id: str):
    student = resolve_student(telegram_id)
    if not student:
        raise HTTPException(status_code=404, detail="Student record not found.")
    return {"absences": get_student_absences(student["student_id"])}

@app.get("/api/attendance/{session_id}/makeup-options", dependencies=[Depends(require_api_auth)])
@app.get("/api/attendance/{session_id}/makeup-options/", dependencies=[Depends(require_api_auth)])
def get_makeup_options(session_id: int, student_telegram_id: Optional[str] = None):
    student = resolve_student(student_telegram_id)
    if not student:
        raise HTTPException(status_code=404, detail="Student record not found.")
    options = suggest_makeup_sessions(student["student_id"], session_id)
    return {"options": options}

@app.post("/api/attendance/{session_id}/makeup", dependencies=[Depends(require_api_auth)])
@app.post("/api/attendance/{session_id}/makeup/", dependencies=[Depends(require_api_auth)])
def schedule_makeup(session_id: int, data: MakeupRequest):
    student = resolve_student(data.student_telegram_id)
    if not student:
        raise HTTPException(status_code=404, detail="Student record not found.")
    return record_makeup(student["student_id"], session_id, data.makeup_session_id)

# ==================== Notifications ====================

@app.get("/api/students/{telegram_id}/notification-settings", dependencies=[Depends(require_api_auth)])
@app.get("/api/students/{telegram_id}/notification-settings/", dependencies=[Depends(require_api_auth)])
def get_settings(telegram_id: str):
    student = resolve_student(telegram_id)
    if not student:
        raise HTTPException(status_code=404, detail="Student record not found.")
    return get_notification_settings(student["student_id"])

@app.patch("/api/students/{telegram_id}/notification-settings", dependencies=[Depends(require_api_auth)])
@app.patch("/api/students/{telegram_id}/notification-settings/", dependencies=[Depends(require_api_auth)])
def update_settings(telegram_id: str, data: NotificationSettingsRequest):
    student = resolve_student(telegram_id)
    if not student:
        raise HTTPException(status_code=404, detail="Student record not found.")
    res = update_notification_settings(student["student_id"], data.enabled, data.minutes_before)
    return {"success": True, **res}

# ==================== Internal Bot Endpoints ====================

@app.get("/api/internal/upcoming-sessions", dependencies=[Depends(require_api_auth)])
@app.get("/api/internal/upcoming-sessions/", dependencies=[Depends(require_api_auth)])
def get_internal_upcoming():
    notifications = get_upcoming_sessions_for_scheduler()
    return {"notifications": notifications}

@app.post("/api/internal/upcoming-sessions/mark-sent", dependencies=[Depends(require_api_auth)])
@app.post("/api/internal/upcoming-sessions/mark-sent/", dependencies=[Depends(require_api_auth)])
def mark_internal_sent(data: MarkSentRequest):
    return mark_notification_sent(data.telegram_id, data.session_id)

import os
import hmac
import hashlib
import json
import logging
from contextlib import asynccontextmanager
from typing import Optional, Dict, Any
from urllib.parse import parse_qsl

from fastapi import FastAPI, Request, Response, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

from database import init_db, query, execute
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

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "7963381665:AAFljS3q8j5GvFp-7u2vK5Dq5f5mBqW9X5A")
INTERNAL_KEY = os.getenv("INTERNAL_KEY", "ins_secret_internal_key_2025")

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    logger.info("[INS-Grades] Initializing database and services...")
    init_db()
    await bot_instance.start()
    yield
    # Shutdown
    logger.info("[INS-Grades] Shutting down...")
    await bot_instance.stop()

app = FastAPI(
    title="INS Grades University Timetable API",
    description="Backend API in Python & FastAPI for INS Grades with Telegram Bot integration",
    version="2.0.0",
    lifespan=lifespan,
)

# CORS middleware for Vercel and local dev
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

def resolve_student(tg_or_id: Any) -> Optional[Dict[str, Any]]:
    """Resolve student by telegram_id, student_id, or return fallback for preview."""
    if not tg_or_id:
        fallback = query("SELECT s.*, g.group_name FROM students s JOIN groups g ON s.group_id = g.group_id LIMIT 1")
        return fallback[0] if fallback else None

    # Check if numeric telegram_id
    if str(tg_or_id).isdigit():
        found = query("SELECT s.*, g.group_name FROM students s JOIN groups g ON s.group_id = g.group_id WHERE s.telegram_id = ?", (int(tg_or_id),))
        if found:
            return found[0]

    # Check student_id
    found_sid = query("SELECT s.*, g.group_name FROM students s JOIN groups g ON s.group_id = g.group_id WHERE UPPER(s.student_id) = UPPER(?)", (str(tg_or_id),))
    if found_sid:
        return found_sid[0]

    # Fallback to demo student for preview mode
    fallback = query("SELECT s.*, g.group_name FROM students s JOIN groups g ON s.group_id = g.group_id LIMIT 1")
    return fallback[0] if fallback else None

# Pydantic models for request bodies
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

# ==================== Health & Status ====================

@app.get("/")
@app.get("/api/health")
def health_check():
    return {
        "status": "healthy",
        "framework": "FastAPI (Python)",
        "service": "INS Grades Backend",
        "developer": "@asliddin_tursunoff"
    }

@app.get("/api/system/status")
def system_status():
    student_count = query("SELECT COUNT(*) as c FROM students")[0]["c"]
    class_count = query("SELECT COUNT(*) as c FROM classes")[0]["c"]
    return {
        "status": "ok",
        "database": "SQLite / Railway persistent storage",
        "framework": "FastAPI (Python)",
        "bot_active": True,
        "bot_username": "INS_gradesbot",
        "student_count": student_count,
        "class_count": class_count,
    }

@app.get("/api/demo/students")
def get_demo_students():
    students = query(
        """SELECT s.student_id, s.full_name, s.telegram_id, s.telegram_username, g.group_name
           FROM students s
           JOIN groups g ON s.group_id = g.group_id
           ORDER BY s.student_id"""
    )
    return {"students": students}

# ==================== Auth Endpoints ====================

@app.get("/api/auth/me/{telegram_id}")
@app.get("/api/auth/me/{telegram_id}/")
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

@app.post("/api/auth/link")
@app.post("/api/auth/link/")
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
            detail="Student ID was not found in university database. Please contact admin: @asliddin_tursunoff"
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

@app.get("/api/students/{telegram_id}/timetable")
@app.get("/api/students/{telegram_id}/timetable/")
def get_student_timetable(telegram_id: str):
    student = resolve_student(telegram_id)
    if not student:
        raise HTTPException(status_code=404, detail="Student not found")
    try:
        schedule_data = get_effective_schedule(student["student_id"])
        return schedule_data
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# ==================== Courses, Retakes, Drops ====================

@app.get("/api/students/{telegram_id}/classes")
@app.get("/api/students/{telegram_id}/classes/")
def get_classes(telegram_id: str):
    student = resolve_student(telegram_id)
    if not student:
        raise HTTPException(status_code=404, detail="Student not found")
    classes = get_student_classes(student["student_id"])
    return {"classes": classes}

@app.get("/api/students/{telegram_id}/retake-catalog")
@app.get("/api/students/{telegram_id}/retake-catalog/")
def get_catalog(telegram_id: str):
    student = resolve_student(telegram_id)
    if not student:
        raise HTTPException(status_code=404, detail="Student not found")
    return get_retake_catalog(student["student_id"])

@app.post("/api/students/{telegram_id}/enroll-retake")
@app.post("/api/students/{telegram_id}/enroll-retake/")
def enroll_retake(telegram_id: str, data: ClassActionRequest):
    student = resolve_student(telegram_id)
    if not student:
        raise HTTPException(status_code=404, detail="Student not found")
    return enroll_retake_class(student["student_id"], data.class_id)

@app.post("/api/students/{telegram_id}/drop")
@app.post("/api/students/{telegram_id}/drop/")
def drop_course(telegram_id: str, data: ClassActionRequest):
    student = resolve_student(telegram_id)
    if not student:
        raise HTTPException(status_code=404, detail="Student not found")
    return drop_class(student["student_id"], data.class_id)

@app.post("/api/students/{telegram_id}/retake")
@app.post("/api/students/{telegram_id}/retake/")
def retake_course(telegram_id: str, data: ClassActionRequest):
    student = resolve_student(telegram_id)
    if not student:
        raise HTTPException(status_code=404, detail="Student not found")
    return retake_class(student["student_id"], data.class_id)

# ==================== Group Switching ====================

@app.get("/api/subjects/{subject_id}/available-groups")
@app.get("/api/subjects/{subject_id}/available-groups/")
def get_available_groups(subject_id: int, student_telegram_id: Optional[str] = None):
    student = resolve_student(student_telegram_id)
    if not student:
        raise HTTPException(status_code=404, detail="Student not found")
    options = get_available_groups_for_subject(subject_id, student["student_id"])
    return {"options": options}

@app.post("/api/students/{telegram_id}/change-group")
@app.post("/api/students/{telegram_id}/change-group/")
def change_group(telegram_id: str, data: ChangeGroupRequest):
    student = resolve_student(telegram_id)
    if not student:
        raise HTTPException(status_code=404, detail="Student not found")
    return change_student_group(
        student["student_id"],
        data.old_class_id,
        data.new_class_id,
        data.change_type or "one_time"
    )

@app.post("/api/students/{telegram_id}/revert-override")
@app.post("/api/students/{telegram_id}/revert-override/")
def revert_override(telegram_id: str, data: RevertOverrideRequest):
    student = resolve_student(telegram_id)
    if not student:
        raise HTTPException(status_code=404, detail="Student not found")
    return revert_student_override(student["student_id"], data.subject_id)

# ==================== Absences & Makeup ====================

@app.get("/api/students/{telegram_id}/absences")
@app.get("/api/students/{telegram_id}/absences/")
def get_absences(telegram_id: str):
    student = resolve_student(telegram_id)
    if not student:
        raise HTTPException(status_code=404, detail="Student not found")
    return {"absences": get_student_absences(student["student_id"])}

@app.get("/api/attendance/{session_id}/makeup-options")
@app.get("/api/attendance/{session_id}/makeup-options/")
def get_makeup_options(session_id: int, student_telegram_id: Optional[str] = None):
    student = resolve_student(student_telegram_id)
    if not student:
        raise HTTPException(status_code=404, detail="Student not found")
    options = suggest_makeup_sessions(student["student_id"], session_id)
    return {"options": options}

@app.post("/api/attendance/{session_id}/makeup")
@app.post("/api/attendance/{session_id}/makeup/")
def schedule_makeup(session_id: int, data: MakeupRequest):
    student = resolve_student(data.student_telegram_id)
    if not student:
        raise HTTPException(status_code=404, detail="Student not found")
    return record_makeup(student["student_id"], session_id, data.makeup_session_id)

# ==================== Notifications ====================

@app.get("/api/students/{telegram_id}/notification-settings")
@app.get("/api/students/{telegram_id}/notification-settings/")
def get_settings(telegram_id: str):
    student = resolve_student(telegram_id)
    if not student:
        raise HTTPException(status_code=404, detail="Student not found")
    return get_notification_settings(student["student_id"])

@app.patch("/api/students/{telegram_id}/notification-settings")
@app.patch("/api/students/{telegram_id}/notification-settings/")
def update_settings(telegram_id: str, data: NotificationSettingsRequest):
    student = resolve_student(telegram_id)
    if not student:
        raise HTTPException(status_code=404, detail="Student not found")
    res = update_notification_settings(student["student_id"], data.enabled, data.minutes_before)
    return {"success": True, **res}

# ==================== Internal Bot Endpoints ====================

@app.get("/api/internal/upcoming-sessions")
@app.get("/api/internal/upcoming-sessions/")
def get_internal_upcoming(request: Request):
    key = request.headers.get("x-internal-key")
    if key != INTERNAL_KEY and request.client.host not in ["127.0.0.1", "localhost", "::1"]:
        raise HTTPException(status_code=403, detail="Unauthorized")
    notifications = get_upcoming_sessions_for_scheduler()
    return {"notifications": notifications}

@app.post("/api/internal/upcoming-sessions/mark-sent")
@app.post("/api/internal/upcoming-sessions/mark-sent/")
def mark_internal_sent(data: MarkSentRequest, request: Request):
    key = request.headers.get("x-internal-key")
    if key != INTERNAL_KEY and request.client.host not in ["127.0.0.1", "localhost", "::1"]:
        raise HTTPException(status_code=403, detail="Unauthorized")
    return mark_notification_sent(data.telegram_id, data.session_id)

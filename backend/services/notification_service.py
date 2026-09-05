from typing import List, Dict, Any, Optional
from datetime import datetime
from database import query, execute

def get_notification_settings(student_id: str) -> Dict[str, Any]:
    rows = query("SELECT enabled, minutes_before FROM notification_settings WHERE student_id = ?", (student_id,))
    if not rows:
        return {"enabled": True, "minutes_before": 30}
    return {
        "enabled": bool(rows[0]["enabled"]),
        "minutes_before": rows[0]["minutes_before"] or 30,
    }

def update_notification_settings(
    student_id: str,
    enabled: Optional[bool] = None,
    minutes_before: Optional[int] = None
) -> Dict[str, Any]:
    existing = query("SELECT student_id FROM notification_settings WHERE student_id = ?", (student_id,))

    if existing:
        if enabled is not None and minutes_before is not None:
            execute(
                "UPDATE notification_settings SET enabled = ?, minutes_before = ? WHERE student_id = ?",
                (1 if enabled else 0, minutes_before, student_id)
            )
        elif enabled is not None:
            execute(
                "UPDATE notification_settings SET enabled = ? WHERE student_id = ?",
                (1 if enabled else 0, student_id)
            )
        elif minutes_before is not None:
            execute(
                "UPDATE notification_settings SET minutes_before = ? WHERE student_id = ?",
                (minutes_before, student_id)
            )
    else:
        execute(
            "INSERT INTO notification_settings (student_id, enabled, minutes_before) VALUES (?, ?, ?)",
            (student_id, 1 if (enabled if enabled is not None else True) else 0, minutes_before or 30)
        )

    return get_notification_settings(student_id)

def get_upcoming_sessions_for_scheduler() -> List[Dict[str, Any]]:
    today_str = datetime.now().strftime("%Y-%m-%d")
    now = datetime.now()
    current_minutes = now.hour * 60 + now.minute

    students = query(
        """SELECT s.student_id, s.telegram_id, ns.minutes_before
           FROM students s
           JOIN notification_settings ns ON s.student_id = ns.student_id
           WHERE ns.enabled = 1 AND s.telegram_id IS NOT NULL"""
    )

    results = []
    for student in students:
        sessions = query(
            """SELECT 
                   ls.session_id,
                   ls.session_date,
                   ls.start_time,
                   ls.end_time,
                   s.short_name AS subject_short,
                   s.full_name AS subject_full,
                   p.full_name AS professor,
                   c.room
               FROM lecture_sessions ls
               JOIN classes c ON ls.class_id = c.class_id
               JOIN subjects s ON c.subject_id = s.subject_id
               JOIN professors p ON c.professor_id = p.professor_id
               JOIN student_class_enrollment sce ON sce.class_id = c.class_id AND sce.student_id = ? AND sce.status = 'active'
               WHERE ls.session_date = ?""",
            (student["student_id"], today_str)
        )

        for session in sessions:
            try:
                sh, sm = map(int, session["start_time"].split(":"))
                session_minutes = sh * 60 + sm
                diff = session_minutes - current_minutes

                # Within notification window
                if 0 <= diff <= int(student["minutes_before"]):
                    already_sent = query(
                        "SELECT id FROM sent_notifications WHERE student_id = ? AND session_id = ?",
                        (student["student_id"], session["session_id"])
                    )
                    if not already_sent:
                        results.append({
                            "telegram_id": student["telegram_id"],
                            "session_id": session["session_id"],
                            "subject_full": session["subject_full"],
                            "subject_short": session["subject_short"],
                            "professor": session["professor"],
                            "room": session["room"],
                            "start_time": session["start_time"],
                            "minutes_left": diff,
                        })
            except Exception:
                continue

    return results

def mark_notification_sent(telegram_id: int, session_id: int) -> Dict[str, Any]:
    student_rows = query("SELECT student_id FROM students WHERE telegram_id = ?", (telegram_id,))
    if not student_rows:
        return {"success": False, "error": "Student not found"}

    student_id = student_rows[0]["student_id"]
    execute(
        "INSERT OR IGNORE INTO sent_notifications (student_id, session_id) VALUES (?, ?)",
        (student_id, session_id)
    )
    return {"success": True}

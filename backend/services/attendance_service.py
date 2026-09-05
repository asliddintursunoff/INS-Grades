from typing import List, Dict, Any
from datetime import datetime
from database import query, execute
from services.timetable_service import get_effective_schedule, has_time_conflict

def get_student_absences(student_id: str) -> List[Dict[str, Any]]:
    return query(
        """SELECT 
               a.attendance_id,
               ls.session_id,
               s.short_name AS subject_short,
               s.full_name AS subject_full,
               ls.session_date,
               ls.start_time,
               ls.end_time,
               p.full_name AS professor,
               c.room,
               a.status,
               a.makeup_session_id
           FROM attendance a
           JOIN lecture_sessions ls ON a.session_id = ls.session_id
           JOIN classes c ON ls.class_id = c.class_id
           JOIN subjects s ON c.subject_id = s.subject_id
           JOIN professors p ON c.professor_id = p.professor_id
           WHERE a.student_id = ? AND a.status = 'absent'
           ORDER BY ls.session_date DESC""",
        (student_id,)
    )

def suggest_makeup_sessions(student_id: str, missed_session_id: int) -> List[Dict[str, Any]]:
    missed_rows = query(
        """SELECT 
               ls.session_id,
               ls.session_date,
               ls.start_time,
               ls.end_time,
               c.class_id,
               c.subject_id,
               c.professor_id,
               c.group_id
           FROM lecture_sessions ls
           JOIN classes c ON ls.class_id = c.class_id
           WHERE ls.session_id = ?""",
        (missed_session_id,)
    )
    if not missed_rows:
        raise ValueError("Sessiya topilmadi")
    missed = missed_rows[0]

    student_rows = query("SELECT student_id, group_id FROM students WHERE student_id = ?", (student_id,))
    if not student_rows:
        raise ValueError("Talaba topilmadi")
    student = student_rows[0]

    today_str = datetime.now().strftime("%Y-%m-%d")
    candidates = query(
        """SELECT 
               ls.session_id,
               ls.session_date,
               ls.start_time,
               ls.end_time,
               c.class_id,
               c.subject_id,
               c.professor_id,
               p.full_name AS professor,
               g.group_name,
               c.room
           FROM lecture_sessions ls
           JOIN classes c ON ls.class_id = c.class_id
           JOIN professors p ON c.professor_id = p.professor_id
           JOIN groups g ON c.group_id = g.group_id
           WHERE c.subject_id = ? 
             AND c.group_id != ?
             AND ls.session_date >= ?
           ORDER BY ls.session_date ASC""",
        (missed["subject_id"], student["group_id"], today_str)
    )

    effective_schedule = get_effective_schedule(student_id)["schedule"]
    valid = []
    for cand in candidates:
        try:
            cand_dt = datetime.strptime(cand["session_date"], "%Y-%m-%d")
            # weekday: Mon=0 -> 1..7
            day_of_week = cand_dt.weekday() + 1
        except Exception:
            day_of_week = 1

        chk = has_time_conflict(effective_schedule, day_of_week, cand["start_time"], cand["end_time"])
        if not chk.get("conflict"):
            valid.append(cand)

    valid.sort(key=lambda c: (
        c["professor_id"] != missed["professor_id"],
        c["session_date"],
        c["start_time"]
    ))

    return valid

def record_makeup(student_id: str, session_id: int, makeup_session_id: int) -> Dict[str, Any]:
    execute(
        """UPDATE attendance 
           SET status = 'makeup_scheduled', makeup_session_id = ? 
           WHERE student_id = ? AND session_id = ?""",
        (makeup_session_id, student_id, session_id)
    )
    return {
        "success": True,
        "message": "Make-up slot scheduled successfully",
        "student_id": student_id,
        "session_id": session_id,
        "makeup_session_id": makeup_session_id,
    }

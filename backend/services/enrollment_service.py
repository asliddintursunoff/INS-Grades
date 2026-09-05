from typing import List, Dict, Any
from datetime import datetime
from database import query, execute

def get_student_classes(student_id: str) -> List[Dict[str, Any]]:
    all_rows = query(
        """SELECT 
               c.class_id,
               s.subject_id,
               s.short_name AS subject_short,
               s.full_name AS subject_full,
               COALESCE(s.year_level, 1) AS year_level,
               p.full_name AS professor,
               g.group_name,
               c.room,
               e.status,
               e.enrolled_at,
               e.dropped_at
           FROM student_class_enrollment e
           JOIN classes c ON e.class_id = c.class_id
           JOIN subjects s ON c.subject_id = s.subject_id
           JOIN professors p ON c.professor_id = p.professor_id
           JOIN groups g ON c.group_id = g.group_id
           WHERE e.student_id = ?
           ORDER BY 
               CASE WHEN e.status = 'active' THEN 0 ELSE 1 END,
               e.enrolled_at DESC""",
        (student_id,)
    )

    subject_map: Dict[int, Dict[str, Any]] = {}
    for row in all_rows:
        sid = row["subject_id"]
        if sid not in subject_map:
            subject_map[sid] = row

    result = list(subject_map.values())
    result.sort(key=lambda x: x["subject_full"])
    return result

def drop_class(student_id: str, class_id: int) -> Dict[str, Any]:
    cls_rows = query("SELECT subject_id FROM classes WHERE class_id = ?", (class_id,))
    now_iso = datetime.now().isoformat()

    if cls_rows:
        subject_id = cls_rows[0]["subject_id"]
        execute(
            """UPDATE student_class_enrollment 
               SET status = 'dropped', dropped_at = ? 
               WHERE student_id = ? AND class_id IN (SELECT class_id FROM classes WHERE subject_id = ?)""",
            (now_iso, student_id, subject_id)
        )
        execute(
            """DELETE FROM student_schedule_overrides 
               WHERE student_id = ? AND class_id IN (SELECT class_id FROM classes WHERE subject_id = ?)""",
            (student_id, subject_id)
        )
    else:
        execute(
            """UPDATE student_class_enrollment 
               SET status = 'dropped', dropped_at = ? 
               WHERE student_id = ? AND class_id = ?""",
            (now_iso, student_id, class_id)
        )

    # Homeworks cascade
    homeworks = query(
        """SELECT h.homework_id 
           FROM homeworks h
           JOIN homework_submissions hs ON h.homework_id = hs.homework_id
           WHERE h.class_id = ? AND hs.student_id = ? AND h.deadline > ?""",
        (class_id, student_id, now_iso)
    )
    if homeworks:
        hw_ids = [h["homework_id"] for h in homeworks]
        placeholders = ",".join("?" for _ in hw_ids)
        execute(
            f"UPDATE homework_submissions SET is_active = 0 WHERE student_id = ? AND homework_id IN ({placeholders})",
            tuple([student_id] + hw_ids)
        )

    return {
        "success": True,
        "message": "Course successfully dropped",
        "removed_homeworks_count": len(homeworks),
    }

def retake_class(student_id: str, class_id: int) -> Dict[str, Any]:
    execute(
        """UPDATE student_class_enrollment 
           SET status = 'active', dropped_at = NULL 
           WHERE student_id = ? AND class_id = ?""",
        (student_id, class_id)
    )

    student_rows = query("SELECT group_id FROM students WHERE student_id = ?", (student_id,))
    cls_rows = query("SELECT class_id, group_id, subject_id FROM classes WHERE class_id = ?", (class_id,))

    if student_rows and cls_rows and student_rows[0]["group_id"] != cls_rows[0]["group_id"]:
        slots = query("SELECT day_of_week, start_time, end_time FROM group_timetable WHERE class_id = ?", (class_id,))
        for slot in slots:
            execute(
                """INSERT INTO student_schedule_overrides (student_id, day_of_week, start_time, end_time, class_id)
                   VALUES (?, ?, ?, ?, ?)""",
                (student_id, slot["day_of_week"], slot["start_time"], slot["end_time"], class_id)
            )

    now_iso = datetime.now().isoformat()
    open_homeworks = query(
        "SELECT homework_id FROM homeworks WHERE class_id = ? AND deadline > ?",
        (class_id, now_iso)
    )

    restored = 0
    for hw in open_homeworks:
        existing = query(
            "SELECT submission_id FROM homework_submissions WHERE homework_id = ? AND student_id = ?",
            (hw["homework_id"], student_id)
        )
        if existing:
            execute("UPDATE homework_submissions SET is_active = 1 WHERE submission_id = ?", (existing[0]["submission_id"],))
        else:
            execute(
                "INSERT INTO homework_submissions (homework_id, student_id, is_done, is_active) VALUES (?, ?, 0, 1)",
                (hw["homework_id"], student_id)
            )
        restored += 1

    return {
        "success": True,
        "message": "Course successfully re-enrolled",
        "restored_homeworks_count": restored,
    }

def get_retake_catalog(student_id: str) -> Dict[str, Any]:
    student_rows = query(
        "SELECT student_id, full_name, group_id, COALESCE(year_of_study, 2) AS year_of_study FROM students WHERE student_id = ?",
        (student_id,)
    )
    if not student_rows:
        raise ValueError(f"Student {student_id} not found")
    student = student_rows[0]

    user_year = int(student.get("year_of_study") or 2)
    available_years = list(range(1, user_year + 1))
    placeholders = ",".join("?" for _ in available_years)

    subjects = query(
        f"""SELECT 
               s.subject_id,
               s.short_name,
               s.full_name,
               COALESCE(s.year_level, 1) AS year_level
           FROM subjects s
           WHERE COALESCE(s.year_level, 1) IN ({placeholders})
           ORDER BY s.year_level ASC, s.full_name ASC""",
        tuple(available_years)
    )

    active_enrollments = query(
        """SELECT c.subject_id, e.status, e.class_id 
           FROM student_class_enrollment e
           JOIN classes c ON e.class_id = c.class_id
           WHERE e.student_id = ?""",
        (student_id,)
    )

    subject_enr_map = {}
    for row in active_enrollments:
        sid = row["subject_id"]
        if sid not in subject_enr_map or row["status"] == "active":
            subject_enr_map[sid] = row

    enriched = []
    for sub in subjects:
        sid = sub["subject_id"]
        enr = subject_enr_map.get(sid)
        is_enr = enr["status"] == "active" if enr else False
        enriched.append({
            "subject_id": sid,
            "short_name": sub["short_name"],
            "full_name": sub["full_name"],
            "year_level": sub["year_level"],
            "enrollment_status": enr["status"] if enr else "none",
            "is_enrolled": is_enr,
            "current_class_id": enr["class_id"] if enr else None,
        })

    return {
        "student_id": student["student_id"],
        "student_name": student["full_name"],
        "student_year": user_year,
        "available_years": available_years,
        "subjects": enriched,
    }

def enroll_retake_class(student_id: str, class_id: int) -> Dict[str, Any]:
    cls_rows = query(
        """SELECT c.class_id, c.subject_id, c.group_id, s.full_name AS subject_name, s.short_name
           FROM classes c
           JOIN subjects s ON c.subject_id = s.subject_id
           WHERE c.class_id = ?""",
        (class_id,)
    )
    if not cls_rows:
        raise ValueError(f"Class {class_id} not found")
    cls = cls_rows[0]

    existing = query(
        "SELECT enrollment_id, status FROM student_class_enrollment WHERE student_id = ? AND class_id = ?",
        (student_id, class_id)
    )
    if existing:
        execute(
            "UPDATE student_class_enrollment SET status = 'active', dropped_at = NULL WHERE student_id = ? AND class_id = ?",
            (student_id, class_id)
        )
    else:
        execute(
            "INSERT INTO student_class_enrollment (student_id, class_id, status) VALUES (?, ?, 'active')",
            (student_id, class_id)
        )

    # If section belongs to another group, add schedule slots
    student_rows = query("SELECT group_id FROM students WHERE student_id = ?", (student_id,))
    if student_rows and student_rows[0]["group_id"] != cls["group_id"]:
        slots = query("SELECT day_of_week, start_time, end_time FROM group_timetable WHERE class_id = ?", (class_id,))
        for slot in slots:
            execute(
                """INSERT INTO student_schedule_overrides (student_id, day_of_week, start_time, end_time, class_id)
                   VALUES (?, ?, ?, ?, ?)""",
                (student_id, slot["day_of_week"], slot["start_time"], slot["end_time"], class_id)
            )

    return {
        "success": True,
        "message": f"Successfully enrolled into {cls['subject_name']}!",
        "subject_name": cls["subject_name"],
        "class_id": class_id,
    }

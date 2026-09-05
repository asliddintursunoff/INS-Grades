from typing import List, Dict, Any, Optional
from datetime import datetime
from database import query, execute

DAY_NAMES = {
    1: 'Monday',
    2: 'Tuesday',
    3: 'Wednesday',
    4: 'Thursday',
    5: 'Friday',
    6: 'Saturday',
    7: 'Sunday',
}

DAY_SHORT = {
    1: 'Mon',
    2: 'Tue',
    3: 'Wed',
    4: 'Thu',
    5: 'Fri',
    6: 'Sat',
    7: 'Sun',
}

def to_minutes(t_str: str) -> int:
    try:
        parts = t_str.split(':')
        return int(parts[0]) * 60 + int(parts[1])
    except Exception:
        return 0

def has_time_conflict(
    schedule: List[Dict[str, Any]],
    day_of_week: int,
    start_time: str,
    end_time: str,
    ignore_subject_short: Optional[str] = None
) -> Dict[str, Any]:
    cand_start = to_minutes(start_time)
    cand_end = to_minutes(end_time)

    for item in schedule:
        if item.get("day_of_week") == day_of_week:
            if ignore_subject_short and item.get("subject_short") == ignore_subject_short:
                continue
            item_start = to_minutes(item.get("start_time", "00:00"))
            item_end = to_minutes(item.get("end_time", "00:00"))

            # Overlap: start1 < end2 && start2 < end1
            if cand_start < item_end and item_start < cand_end:
                return {"conflict": True, "conflict_subject": item.get("subject_short")}

    return {"conflict": False}

def get_effective_schedule(student_id: str) -> Dict[str, Any]:
    # 1. Student info
    student_rows = query(
        """SELECT s.student_id, s.full_name, s.group_id, g.group_name, g.timetable_image_url
           FROM students s
           JOIN groups g ON s.group_id = g.group_id
           WHERE s.student_id = ?""",
        (student_id,)
    )
    if not student_rows:
        raise ValueError(f"Student not found: {student_id}")
    student = student_rows[0]

    # 2. Base group timetable slots
    base_slots = query(
        """SELECT 
               gt.slot_id,
               gt.day_of_week,
               gt.start_time,
               gt.end_time,
               c.class_id,
               s.subject_id,
               s.short_name AS subject_short,
               s.full_name AS subject_full,
               p.full_name AS professor,
               c.room,
               g.group_name AS original_group,
               g.group_name AS actual_group
           FROM group_timetable gt
           JOIN classes c ON gt.class_id = c.class_id
           JOIN subjects s ON c.subject_id = s.subject_id
           JOIN professors p ON c.professor_id = p.professor_id
           JOIN groups g ON gt.group_id = g.group_id
           WHERE gt.group_id = ?
             AND NOT EXISTS (
                 SELECT 1 FROM student_class_enrollment sce 
                 WHERE sce.student_id = ? AND sce.class_id = c.class_id AND sce.status = 'dropped'
             )
           ORDER BY gt.day_of_week, gt.start_time""",
        (student["group_id"], student_id)
    )

    # 3. Extra enrolled classes (e.g. permanently changed sections or retakes)
    extra_slots = query(
        """SELECT 
               gt.slot_id,
               gt.day_of_week,
               gt.start_time,
               gt.end_time,
               c.class_id,
               s.subject_id,
               s.short_name AS subject_short,
               s.full_name AS subject_full,
               p.full_name AS professor,
               c.room,
               g.group_name AS original_group,
               g.group_name AS actual_group
           FROM student_class_enrollment sce
           JOIN classes c ON sce.class_id = c.class_id
           JOIN group_timetable gt ON gt.class_id = c.class_id
           JOIN subjects s ON c.subject_id = s.subject_id
           JOIN professors p ON c.professor_id = p.professor_id
           JOIN groups g ON c.group_id = g.group_id
           WHERE sce.student_id = ? AND sce.status = 'active' AND c.group_id != ?
           ORDER BY gt.day_of_week, gt.start_time""",
        (student_id, student["group_id"])
    )

    # 4. One-time make-up overrides
    overrides = query(
        """SELECT 
               sso.override_id,
               sso.day_of_week,
               sso.start_time,
               sso.end_time,
               c.class_id,
               s.subject_id,
               s.short_name AS subject_short,
               s.full_name AS subject_full,
               p.full_name AS professor,
               c.room,
               g.group_name AS actual_group
           FROM student_schedule_overrides sso
           JOIN classes c ON sso.class_id = c.class_id
           JOIN subjects s ON c.subject_id = s.subject_id
           JOIN professors p ON c.professor_id = p.professor_id
           JOIN groups g ON c.group_id = g.group_id
           WHERE sso.student_id = ?
           ORDER BY sso.day_of_week, sso.start_time""",
        (student_id,)
    )

    overridden_subject_ids = {o["subject_id"] for o in overrides}
    extra_subject_ids = {s["subject_id"] for s in extra_slots}
    schedule: List[Dict[str, Any]] = []

    # Add base slots (if not overridden by one-time makeup AND not replaced by extra section)
    for slot in base_slots:
        if slot["subject_id"] not in overridden_subject_ids and slot["subject_id"] not in extra_subject_ids:
            schedule.append({
                "day_of_week": slot["day_of_week"],
                "day_name": DAY_NAMES.get(slot["day_of_week"], f"Day {slot['day_of_week']}"),
                "start_time": slot["start_time"],
                "end_time": slot["end_time"],
                "subject_id": slot["subject_id"],
                "subject_short": slot["subject_short"],
                "subject_full": slot["subject_full"],
                "professor": slot["professor"],
                "room": slot["room"],
                "class_id": slot["class_id"],
                "is_changed": False,
                "is_one_time": False,
                "original_group": student["group_name"],
                "actual_group": slot["actual_group"],
            })

    # Add extra slots
    for slot in extra_slots:
        if slot["subject_id"] not in overridden_subject_ids:
            is_perm = slot["actual_group"] != student["group_name"]
            schedule.append({
                "day_of_week": slot["day_of_week"],
                "day_name": DAY_NAMES.get(slot["day_of_week"], f"Day {slot['day_of_week']}"),
                "start_time": slot["start_time"],
                "end_time": slot["end_time"],
                "subject_id": slot["subject_id"],
                "subject_short": slot["subject_short"],
                "subject_full": slot["subject_full"],
                "professor": slot["professor"],
                "room": slot["room"],
                "class_id": slot["class_id"],
                "is_changed": is_perm,
                "is_one_time": False,
                "reverts_next_week": False,
                "make_up_note": f"Permanent section ({slot['actual_group']})" if is_perm else None,
                "original_group": student["group_name"],
                "actual_group": slot["actual_group"],
            })

    # Add one-time overrides
    for o in overrides:
        schedule.append({
            "day_of_week": o["day_of_week"],
            "day_name": DAY_NAMES.get(o["day_of_week"], f"Day {o['day_of_week']}"),
            "start_time": o["start_time"],
            "end_time": o["end_time"],
            "subject_id": o["subject_id"],
            "subject_short": o["subject_short"],
            "subject_full": o["subject_full"],
            "professor": o["professor"],
            "room": o["room"],
            "class_id": o["class_id"],
            "is_changed": True,
            "is_one_time": True,
            "reverts_next_week": True,
            "make_up_note": "One-time make-up (this week only)",
            "original_group": student["group_name"],
            "actual_group": o["actual_group"],
        })

    # Sort by day and start_time
    schedule.sort(key=lambda item: (item["day_of_week"], item["start_time"]))

    # Add session numbers (e.g. Session 1 of 2)
    subject_counts: Dict[int, int] = {}
    for item in schedule:
        s_id = item["subject_id"]
        subject_counts[s_id] = subject_counts.get(s_id, 0) + 1

    subject_curr: Dict[int, int] = {}
    for item in schedule:
        s_id = item["subject_id"]
        subject_curr[s_id] = subject_curr.get(s_id, 0) + 1
        item["session_number"] = subject_curr[s_id]
        item["total_sessions"] = subject_counts[s_id]

    return {
        "student_id": student["student_id"],
        "student_name": student["full_name"],
        "group_name": student["group_name"],
        "timetable_image_url": student["timetable_image_url"],
        "schedule": schedule,
    }

def get_available_groups_for_subject(subject_id: int, student_id: str) -> List[Dict[str, Any]]:
    subject_rows = query("SELECT short_name, full_name FROM subjects WHERE subject_id = ?", (subject_id,))
    subject_short = subject_rows[0]["short_name"] if subject_rows else ""

    current_schedule = get_effective_schedule(student_id)["schedule"]
    student_rows = query("SELECT group_id FROM students WHERE student_id = ?", (student_id,))
    student_group_id = student_rows[0]["group_id"] if student_rows else 0

    rows = query(
        """SELECT 
               c.class_id,
               g.group_id,
               g.group_name,
               p.full_name AS professor,
               c.room,
               gt.day_of_week,
               gt.start_time,
               gt.end_time
           FROM classes c
           JOIN groups g ON c.group_id = g.group_id
           JOIN professors p ON c.professor_id = p.professor_id
           JOIN group_timetable gt ON c.class_id = gt.class_id
           WHERE c.subject_id = ?
           ORDER BY g.group_name, gt.day_of_week, gt.start_time""",
        (subject_id,)
    )

    class_map: Dict[int, Dict[str, Any]] = {}
    now = datetime.now()
    # Python weekday(): Mon=0 ... Sun=6 -> 1..7
    current_day = now.weekday() + 1
    current_time = now.strftime("%H:%M")

    for row in rows:
        cid = row["class_id"]
        if cid not in class_map:
            class_map[cid] = {
                "class_id": row["class_id"],
                "group_id": row["group_id"],
                "group_name": row["group_name"],
                "professor": row["professor"],
                "room": row["room"],
                "slots": [],
            }

        is_upcoming = (
            row["day_of_week"] > current_day or
            (row["day_of_week"] == current_day and row["start_time"] >= current_time)
        )

        class_map[cid]["slots"].append({
            "day_of_week": row["day_of_week"],
            "day_name": DAY_NAMES.get(row["day_of_week"], f"Day {row['day_of_week']}"),
            "day_short": DAY_SHORT.get(row["day_of_week"], f"D{row['day_of_week']}"),
            "start_time": row["start_time"],
            "end_time": row["end_time"],
            "room": row["room"],
            "is_upcoming": is_upcoming,
        })

    options = []
    for cls in class_map.values():
        is_own_group = (cls["group_id"] == student_group_id)
        sessions_per_week = len(cls["slots"])
        has_upcoming = any(s["is_upcoming"] for s in cls["slots"])

        has_conflict = False
        conflict_reason = None

        for slot in cls["slots"]:
            chk = has_time_conflict(
                current_schedule,
                slot["day_of_week"],
                slot["start_time"],
                slot["end_time"],
                subject_short
            )
            if chk.get("conflict"):
                has_conflict = True
                conflict_reason = f"Clashes on {slot['day_name']} ({slot['start_time']}-{slot['end_time']}) with {chk.get('conflict_subject')}"
                break

        is_available = not has_conflict
        is_recommended = is_available and (not is_own_group) and has_upcoming

        time_summary = " • ".join(f"{s['day_short']} {s['start_time']}-{s['end_time']}" for s in cls["slots"])
        days_summary = " & ".join(s["day_short"] for s in cls["slots"])

        first_slot = cls["slots"][0] if cls["slots"] else {
            "day_of_week": 1,
            "day_name": "Monday",
            "start_time": "09:00",
            "end_time": "10:00"
        }

        options.append({
            "class_id": cls["class_id"],
            "group_name": cls["group_name"],
            "professor": cls["professor"],
            "room": cls["room"],
            "sessions_per_week": sessions_per_week,
            "slots": cls["slots"],
            "day_of_week": first_slot["day_of_week"],
            "day_name": days_summary if sessions_per_week > 1 else first_slot["day_name"],
            "start_time": first_slot["start_time"],
            "end_time": first_slot["end_time"],
            "time_summary": time_summary,
            "is_own_group": is_own_group,
            "is_available": is_available,
            "is_upcoming": has_upcoming,
            "upcoming_text": "Upcoming lesson this week" if has_upcoming else "Past slot this week",
            "recommended": is_recommended,
            "conflict_reason": conflict_reason,
        })

    # Sort options: available first, upcoming first, other groups first
    options.sort(key=lambda o: (
        not o["is_available"],
        not o["is_upcoming"],
        o["is_own_group"],
        o["day_of_week"]
    ))

    return options

def change_student_group(
    student_id: str,
    old_class_id: int,
    new_class_id: int,
    change_type: str = "one_time"
) -> Dict[str, Any]:
    new_class_rows = query(
        """SELECT c.class_id, c.subject_id, c.group_id, g.group_name 
           FROM classes c 
           JOIN groups g ON c.group_id = g.group_id
           WHERE c.class_id = ?""",
        (new_class_id,)
    )
    if not new_class_rows:
        raise ValueError("Selected class section was not found")
    new_class = new_class_rows[0]

    slots = query(
        "SELECT day_of_week, start_time, end_time FROM group_timetable WHERE class_id = ?",
        (new_class_id,)
    )
    if not slots:
        raise ValueError("Selected class section has no scheduled timetable slots")

    student_rows = query("SELECT group_id FROM students WHERE student_id = ?", (student_id,))
    student = student_rows[0] if student_rows else None

    # Clear previous overrides for this subject
    execute(
        """DELETE FROM student_schedule_overrides 
           WHERE student_id = ? AND class_id IN (SELECT class_id FROM classes WHERE subject_id = ?)""",
        (student_id, new_class["subject_id"])
    )

    # If returning to primary group
    if student and new_class["group_id"] == student["group_id"]:
        execute(
            """DELETE FROM student_class_enrollment 
               WHERE student_id = ? AND class_id IN (SELECT class_id FROM classes WHERE subject_id = ?) AND class_id != ?""",
            (student_id, new_class["subject_id"], new_class_id)
        )
        existing = query(
            "SELECT enrollment_id FROM student_class_enrollment WHERE student_id = ? AND class_id = ?",
            (student_id, new_class_id)
        )
        if existing:
            execute(
                "UPDATE student_class_enrollment SET status = 'active', dropped_at = NULL WHERE student_id = ? AND class_id = ?",
                (student_id, new_class_id)
            )
        else:
            execute(
                "INSERT INTO student_class_enrollment (student_id, class_id, status) VALUES (?, ?, 'active')",
                (student_id, new_class_id)
            )
        return {
            "success": True,
            "is_permanent": True,
            "is_one_time": False,
            "message": f"Returned to primary group schedule ({new_class['group_name']}) permanently."
        }

    # Permanent Change
    if change_type == "permanent":
        execute(
            """DELETE FROM student_class_enrollment 
               WHERE student_id = ? AND class_id IN (SELECT class_id FROM classes WHERE subject_id = ?)""",
            (student_id, new_class["subject_id"])
        )
        execute(
            "INSERT INTO student_class_enrollment (student_id, class_id, status) VALUES (?, ?, 'active')",
            (student_id, new_class_id)
        )
        return {
            "success": True,
            "is_permanent": True,
            "is_one_time": False,
            "message": f"Permanently changed to section {new_class['group_name']} ({len(slots)} sessions/week) for the semester! Your timetable is permanently updated."
        }

    # One-Time Make-Up
    for slot in slots:
        execute(
            """INSERT INTO student_schedule_overrides (student_id, day_of_week, start_time, end_time, class_id)
               VALUES (?, ?, ?, ?, ?)""",
            (student_id, slot["day_of_week"], slot["start_time"], slot["end_time"], new_class_id)
        )

    return {
        "success": True,
        "is_one_time": True,
        "is_permanent": False,
        "message": f"One-time make-up lesson scheduled for this week ({len(slots)} sessions)! Your timetable will automatically revert to your primary group next week."
    }

def revert_student_override(student_id: str, subject_id: int) -> Dict[str, Any]:
    student_rows = query("SELECT group_id FROM students WHERE student_id = ?", (student_id,))
    if student_rows:
        primary_class = query(
            "SELECT class_id FROM classes WHERE subject_id = ? AND group_id = ?",
            (subject_id, student_rows[0]["group_id"])
        )
        if primary_class:
            execute(
                """UPDATE student_class_enrollment SET class_id = ?, status = 'active', dropped_at = NULL 
                   WHERE student_id = ? AND class_id IN (SELECT class_id FROM classes WHERE subject_id = ?)""",
                (primary_class[0]["class_id"], student_id, subject_id)
            )

    execute(
        """DELETE FROM student_schedule_overrides 
           WHERE student_id = ? AND class_id IN (SELECT class_id FROM classes WHERE subject_id = ?)""",
        (student_id, subject_id)
    )

    return {
        "success": True,
        "message": "Reverted to primary group schedule successfully."
    }

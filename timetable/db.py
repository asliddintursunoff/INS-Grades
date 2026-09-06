#!/usr/bin/env python3
"""
Database Manager for Timetable Service.
Supports direct connection to PostgreSQL (via DATABASE_URL or DB_* vars)
and SQLite (local fallback).

Handles:
  - In-place upsert of Professors, Groups, Subjects
  - In-place upsert of CourseClass by (group_id, subject_id) preserving class_id
  - In-place update of GroupTimetableSlot timings
  - Student enrollment matching:
      * Respects 'dropped' status (never re-adds dropped courses)
      * Preserves extra/retake courses from other groups (never deletes them)
      * Automatically enrolls students into active group courses
  - Updates Group timetable_image_url
"""

import datetime
import os
import re
import urllib.parse
from typing import Any, Dict, List, Optional, Set, Tuple


class DatabaseManager:
    def __init__(self, database_url: Optional[str] = None):
        self.raw_url = database_url or os.getenv("DATABASE_URL") or os.getenv("DATABASE_PUBLIC_URL") or ""
        self.conn = None
        self.is_postgres = False

    def connect(self):
        """Establishes database connection to PostgreSQL or SQLite."""
        url = self.raw_url.strip()

        if url.startswith("postgres://") or url.startswith("postgresql://"):
            import psycopg2
            # Handle special characters or convert postgres:// to postgresql://
            parsed = urllib.parse.urlparse(url)
            self.conn = psycopg2.connect(
                dbname=parsed.path.lstrip("/"),
                user=parsed.username,
                password=parsed.password,
                host=parsed.hostname,
                port=parsed.port or 5432,
                sslmode=os.getenv("DB_SSLMODE", "prefer"),
                connect_timeout=10,
            )
            self.conn.autocommit = False
            self.is_postgres = True
            print(f"[{datetime.datetime.now().strftime('%H:%M:%S')}] Connected to PostgreSQL at {parsed.hostname}:{parsed.port or 5432}/{parsed.path.lstrip('/')}")
        elif os.getenv("DB_HOST") and os.getenv("DB_PASSWORD"):
            import psycopg2
            self.conn = psycopg2.connect(
                host=os.getenv("DB_HOST"),
                port=int(os.getenv("DB_PORT", "5432")),
                user=os.getenv("DB_USER", "postgres"),
                password=os.getenv("DB_PASSWORD"),
                dbname=os.getenv("DB_NAME", "railway"),
                sslmode=os.getenv("DB_SSLMODE", "prefer"),
                connect_timeout=10,
            )
            self.conn.autocommit = False
            self.is_postgres = True
            print(f"[{datetime.datetime.now().strftime('%H:%M:%S')}] Connected to PostgreSQL at {os.getenv('DB_HOST')}:{os.getenv('DB_PORT', '5432')}")
        else:
            # SQLite fallback
            import sqlite3
            repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            db_path = os.path.join(repo_root, "backend", "db.sqlite3")
            if not os.path.exists(db_path):
                db_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "db.sqlite3")

            self.conn = sqlite3.connect(db_path)
            self.conn.isolation_level = None  # manual transactions
            self.is_postgres = False
            print(f"[{datetime.datetime.now().strftime('%H:%M:%S')}] Connected to local SQLite database at {db_path}")

        return self

    def _execute(self, cursor, query: str, params: Optional[Tuple] = None):
        """Translates placeholder syntax (%s for Postgres vs ? for SQLite)."""
        if not self.is_postgres:
            query = query.replace("%s", "?")
        return cursor.execute(query, params or ())

    def commit(self):
        if self.conn:
            self.conn.commit()

    def rollback(self):
        if self.conn:
            self.conn.rollback()

    def close(self):
        if self.conn:
            self.conn.close()
            self.conn = None

    # --------------------------------------------------------------------------
    # 1. Professors
    # --------------------------------------------------------------------------
    def sync_professors(self, teachers_dict: Dict[str, Dict[str, Any]]) -> Dict[str, int]:
        """
        Upserts professors into `professors` table.
        Returns dict: {full_name: professor_id}
        """
        cur = self.conn.cursor()
        prof_map: Dict[str, int] = {}

        # 1. Ensure fallback 'TBA' professor exists
        self._execute(cur, "SELECT professor_id FROM professors WHERE full_name = %s", ("TBA",))
        row = cur.fetchone()
        if row:
            prof_map["TBA"] = row[0]
        else:
            if self.is_postgres:
                self._execute(cur, "INSERT INTO professors (full_name, email) VALUES (%s, %s) RETURNING professor_id", ("TBA", "tba@inha.uz"))
                prof_map["TBA"] = cur.fetchone()[0]
            else:
                self._execute(cur, "INSERT INTO professors (full_name, email) VALUES (%s, %s)", ("TBA", "tba@inha.uz"))
                prof_map["TBA"] = cur.lastrowid

        # 2. Upsert each scraped teacher
        for t in teachers_dict.values():
            full_name = t.get("full_name", "").strip()
            if not full_name:
                continue

            email = t.get("email")
            if not email and t.get("short_name"):
                sanitized = t["short_name"].lower().replace(" ", ".").replace("..", ".")
                email = f"{sanitized}@inha.uz"

            self._execute(cur, "SELECT professor_id, email FROM professors WHERE full_name = %s", (full_name,))
            existing = cur.fetchone()
            if existing:
                prof_id, existing_email = existing[0], existing[1]
                if not existing_email and email:
                    self._execute(cur, "UPDATE professors SET email = %s WHERE professor_id = %s", (email, prof_id))
                prof_map[full_name] = prof_id
            else:
                if self.is_postgres:
                    self._execute(cur, "INSERT INTO professors (full_name, email) VALUES (%s, %s) RETURNING professor_id", (full_name, email))
                    prof_map[full_name] = cur.fetchone()[0]
                else:
                    self._execute(cur, "INSERT INTO professors (full_name, email) VALUES (%s, %s)", (full_name, email))
                    prof_map[full_name] = cur.lastrowid

        return prof_map

    # --------------------------------------------------------------------------
    # 2. Groups
    # --------------------------------------------------------------------------
    def sync_groups(self, group_names: List[str]) -> Dict[str, int]:
        """
        Upserts groups into `groups` table.
        Returns dict: {group_name: group_id}
        """
        cur = self.conn.cursor()
        group_map: Dict[str, int] = {}

        for grp_name in group_names:
            grp_name = grp_name.strip()
            if not grp_name:
                continue

            self._execute(cur, "SELECT group_id FROM groups WHERE group_name = %s", (grp_name,))
            row = cur.fetchone()
            if row:
                group_map[grp_name] = row[0]
            else:
                if self.is_postgres:
                    self._execute(cur, "INSERT INTO groups (group_name) VALUES (%s) RETURNING group_id", (grp_name,))
                    group_map[grp_name] = cur.fetchone()[0]
                else:
                    self._execute(cur, "INSERT INTO groups (group_name) VALUES (%s)", (grp_name,))
                    group_map[grp_name] = cur.lastrowid

        return group_map

    # --------------------------------------------------------------------------
    # 3. Subjects
    # --------------------------------------------------------------------------
    def sync_subjects(self, subjects_dict: Dict[str, Dict[str, Any]]) -> Dict[str, int]:
        """
        Upserts subjects into `subjects` table.
        Returns dict: {full_name: subject_id}
        """
        cur = self.conn.cursor()
        subj_map: Dict[str, int] = {}

        for s in subjects_dict.values():
            full_name = s.get("name", "").strip()
            short_name = s.get("short", "").strip() or full_name[:20]
            if not full_name:
                continue

            year_level = 1
            m = re.search(r"\b([1-4])\b", full_name)
            if m:
                year_level = int(m.group(1))

            self._execute(cur, "SELECT subject_id, short_name FROM subjects WHERE full_name = %s", (full_name,))
            row = cur.fetchone()
            if row:
                subj_id, cur_short = row[0], row[1]
                if short_name and cur_short != short_name:
                    self._execute(cur, "UPDATE subjects SET short_name = %s WHERE subject_id = %s", (short_name, subj_id))
                subj_map[full_name] = subj_id
            else:
                if self.is_postgres:
                    self._execute(cur, "INSERT INTO subjects (full_name, short_name, year_level) VALUES (%s, %s, %s) RETURNING subject_id", (full_name, short_name, year_level))
                    subj_map[full_name] = cur.fetchone()[0]
                else:
                    self._execute(cur, "INSERT INTO subjects (full_name, short_name, year_level) VALUES (%s, %s, %s)", (full_name, short_name, year_level))
                    subj_map[full_name] = cur.lastrowid

        return subj_map

    # --------------------------------------------------------------------------
    # 4. CourseClass & GroupTimetableSlots
    # --------------------------------------------------------------------------
    def sync_classes_and_slots(
        self,
        group_name: str,
        group_id: int,
        slots: List[Any],
        prof_map: Dict[str, int],
        subj_map: Dict[str, int],
    ) -> Tuple[int, int, int]:
        """
        In-place sync for CourseClass and GroupTimetableSlot.
        CRITICAL: Matches CourseClass by (group_id, subject_id) so existing class_ids
        remain stable, keeping student enrollments intact.
        Returns (classes_synced, slots_created, slots_updated)
        """
        cur = self.conn.cursor()
        classes_synced = 0
        slots_created = 0
        slots_updated = 0

        # Group slots by subject
        from collections import defaultdict
        slots_by_subj = defaultdict(list)
        for s in slots:
            slots_by_subj[s.subject].append(s)

        for subj_name, subj_slots in slots_by_subj.items():
            subj_id = subj_map.get(subj_name)
            if not subj_id:
                continue

            primary_slot = subj_slots[0]
            prof_id = prof_map.get(primary_slot.professor) or prof_map.get("TBA")
            room = primary_slot.classroom

            # 1. Look up existing CourseClass by (group_id, subject_id)
            self._execute(
                cur,
                "SELECT class_id, professor_id, room FROM classes WHERE group_id = %s AND subject_id = %s",
                (group_id, subj_id),
            )
            existing_class = cur.fetchone()

            if existing_class:
                class_id, cur_prof_id, cur_room = existing_class[0], existing_class[1], existing_class[2]
                if cur_prof_id != prof_id or cur_room != room:
                    self._execute(
                        cur,
                        "UPDATE classes SET professor_id = %s, room = %s WHERE class_id = %s",
                        (prof_id, room, class_id),
                    )
            else:
                if self.is_postgres:
                    self._execute(
                        cur,
                        "INSERT INTO classes (group_id, subject_id, professor_id, room) VALUES (%s, %s, %s, %s) RETURNING class_id",
                        (group_id, subj_id, prof_id, room),
                    )
                    class_id = cur.fetchone()[0]
                else:
                    self._execute(
                        cur,
                        "INSERT INTO classes (group_id, subject_id, professor_id, room) VALUES (%s, %s, %s, %s)",
                        (group_id, subj_id, prof_id, room),
                    )
                    class_id = cur.lastrowid

            classes_synced += 1

            # 2. In-place update of timetable slots for this CourseClass
            self._execute(
                cur,
                "SELECT slot_id, day_of_week, start_time, end_time FROM group_timetable WHERE group_id = %s AND class_id = %s ORDER BY day_of_week, start_time",
                (group_id, class_id),
            )
            existing_slots = cur.fetchall()

            new_slots = sorted(subj_slots, key=lambda x: (x.day_of_week, x.start_time))

            # Update matching existing slots
            for i in range(min(len(existing_slots), len(new_slots))):
                e_id, e_day, e_start, e_end = existing_slots[i]
                n_slot = new_slots[i]
                if e_day != n_slot.day_of_week or e_start != n_slot.start_time or e_end != n_slot.end_time:
                    self._execute(
                        cur,
                        "UPDATE group_timetable SET day_of_week = %s, start_time = %s, end_time = %s WHERE slot_id = %s",
                        (n_slot.day_of_week, n_slot.start_time, n_slot.end_time, e_id),
                    )
                    slots_updated += 1

            # If more new slots than existing, create the extra ones
            if len(new_slots) > len(existing_slots):
                for extra in new_slots[len(existing_slots):]:
                    self._execute(
                        cur,
                        "INSERT INTO group_timetable (group_id, class_id, day_of_week, start_time, end_time) VALUES (%s, %s, %s, %s, %s)",
                        (group_id, class_id, extra.day_of_week, extra.start_time, extra.end_time),
                    )
                    slots_created += 1

            # If fewer new slots, remove the excess ones
            elif len(existing_slots) > len(new_slots):
                for extra in existing_slots[len(new_slots):]:
                    self._execute(cur, "DELETE FROM group_timetable WHERE slot_id = %s", (extra[0],))

        return classes_synced, slots_created, slots_updated

    # --------------------------------------------------------------------------
    # 5. Student Enrollment Management
    # --------------------------------------------------------------------------
    def sync_student_enrollments(self, target_group_id: Optional[int] = None) -> Tuple[int, int, int]:
        """
        Manages StudentClassEnrollment:
          - CRITICAL: Never re-adds dropped courses (status='dropped') or dropped subjects.
          - CRITICAL: Never drops or deletes existing extra / retake courses from other groups.
          - Automatically matches new active group courses to students who haven't dropped them.
          - Updates existing enrollments in-place to new timings without recreation.
        Returns (enrollments_created, enrollments_preserved, dropped_courses_respected)
        """
        cur = self.conn.cursor()
        created_count = 0
        preserved_count = 0
        dropped_respected_count = 0

        # Query students
        if target_group_id:
            self._execute(cur, "SELECT student_id, group_id FROM students WHERE group_id = %s", (target_group_id,))
        else:
            self._execute(cur, "SELECT student_id, group_id FROM students")
        students = cur.fetchall()

        now_str = datetime.datetime.now(datetime.timezone.utc).isoformat()

        for student_id, student_group_id in students:
            # 1. Fetch all existing enrollments for this student with their subject_id and class's group_id
            query = """
                SELECT e.enrollment_id, e.class_id, e.status, c.subject_id, c.group_id
                FROM student_class_enrollment e
                JOIN classes c ON e.class_id = c.class_id
                WHERE e.student_id = %s
            """
            self._execute(cur, query, (student_id,))
            existing_enrollments = cur.fetchall()

            enrolled_class_ids: Set[int] = {row[1] for row in existing_enrollments}
            # Track subjects explicitly dropped by student
            dropped_subject_ids: Set[int] = {
                row[3] for row in existing_enrollments if (row[2] or "").lower() == "dropped"
            }

            # 2. Get active classes for the student's group
            self._execute(cur, "SELECT class_id, subject_id FROM classes WHERE group_id = %s", (student_group_id,))
            group_classes = cur.fetchall()

            for class_id, subject_id in group_classes:
                if class_id in enrolled_class_ids:
                    # Already enrolled
                    enrollment_status = next(row[2] for row in existing_enrollments if row[1] == class_id)
                    if (enrollment_status or "").lower() == "dropped":
                        # Respected: Do NOT reactivate dropped courses!
                        dropped_respected_count += 1
                    else:
                        preserved_count += 1
                else:
                    # Student not enrolled in this class
                    if subject_id in dropped_subject_ids:
                        # Respected: Student previously dropped this subject! Do NOT re-add!
                        dropped_respected_count += 1
                        continue

                    # Create enrollment for this active group class
                    self._execute(
                        cur,
                        "INSERT INTO student_class_enrollment (student_id, class_id, status, enrolled_at) VALUES (%s, %s, %s, %s)",
                        (student_id, class_id, "active", now_str),
                    )
                    created_count += 1

            # 3. Existing enrollments from other groups (extra / retake courses) are kept intact
            for row in existing_enrollments:
                course_group_id = row[4]
                if course_group_id != student_group_id:
                    preserved_count += 1

        return created_count, preserved_count, dropped_respected_count

    # --------------------------------------------------------------------------
    # 6. Group Screenshot Linking
    # --------------------------------------------------------------------------
    def get_group_screenshot(self, group_name: str) -> Optional[str]:
        """Retrieves existing timetable_image_url for a group."""
        cur = self.conn.cursor()
        self._execute(
            cur,
            "SELECT timetable_image_url FROM groups WHERE group_name = %s",
            (group_name,),
        )
        row = cur.fetchone()
        return row[0] if row and row[0] else None

    def update_group_screenshot(self, group_name: str, image_url: str) -> bool:
        """Updates `timetable_image_url` on the `groups` table."""
        cur = self.conn.cursor()
        self._execute(
            cur,
            "UPDATE groups SET timetable_image_url = %s WHERE group_name = %s",
            (image_url, group_name),
        )
        return cur.rowcount > 0

#!/usr/bin/env python3
"""
EduPage Timetable Scraper & Text Parser for IUT (Inha University in Tashkent)
Source: https://iut.edupage.org/timetable/

Features:
  - Discovers active semester/timetable dynamically or accepts custom tt_num
  - Extracts professors, subjects, classrooms, student groups
  - Accurately computes exact start_time & end_time (30-min block arithmetic)
  - Decodes day bitmasks to standard 1..7 (Monday..Sunday)
  - Properly links shared / multi-group lectures (e.g. Calculus 1 shared by CIE26-1..4)
  - Generates group schedules, professor schedules, and room schedules
  - Exports to JSON, CSV, and Django backend payload
  - Zero external dependencies required (runs on standard Python 3.7+)
"""

import argparse
import csv
import json
import os
import re
import sys
import urllib.error
import urllib.request
from collections import defaultdict
from dataclasses import asdict, dataclass
from typing import Any, Dict, List, Optional


DEFAULT_BASE_URL = "https://iut.edupage.org"
DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36"
)

DAY_NAMES = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
DAY_SHORTS = ["Mo", "Tu", "We", "Th", "Fr", "Sa", "Su"]


@dataclass
class GroupSlot:
    """A timetable slot viewed from the perspective of a student group."""
    day: str
    day_of_week: int  # 1 = Monday ... 7 = Sunday
    start_time: str   # HH:MM
    end_time: str     # HH:MM
    period_start: int
    period_end: int
    duration_periods: int
    subject: str
    subject_short: str
    professors: List[str]
    professor: str
    classrooms: List[str]
    classroom: str
    group: str
    all_groups: List[str]
    lesson_id: str
    card_id: str

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class SessionSlot:
    """A scheduled session (deduplicated by card/time) viewed by professor or room."""
    day: str
    day_of_week: int
    start_time: str
    end_time: str
    period_start: int
    period_end: int
    duration_periods: int
    subject: str
    subject_short: str
    professors: List[str]
    professor: str
    classrooms: List[str]
    classroom: str
    groups: List[str]
    groups_str: str
    lesson_id: str
    card_id: str

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class EduPageParser:
    def __init__(self, base_url: str = DEFAULT_BASE_URL, tt_num: Optional[str] = None):
        self.base_url = base_url.rstrip("/")
        self.tt_num = tt_num
        self.active_timetable_info: Dict[str, Any] = {}

        # Raw relational lookups from EduPage
        self.classes: Dict[str, Dict[str, Any]] = {}
        self.teachers: Dict[str, Dict[str, Any]] = {}
        self.subjects: Dict[str, Dict[str, Any]] = {}
        self.classrooms: Dict[str, Dict[str, Any]] = {}
        self.periods: Dict[str, Dict[str, Any]] = {}
        self.days: Dict[str, Dict[str, Any]] = {}
        self.lessons: Dict[str, Dict[str, Any]] = {}
        self.cards: List[Dict[str, Any]] = []

        # Processed schedules
        self.schedule_by_group: Dict[str, List[GroupSlot]] = defaultdict(list)
        self.schedule_by_professor: Dict[str, List[SessionSlot]] = defaultdict(list)
        self.schedule_by_room: Dict[str, List[SessionSlot]] = defaultdict(list)
        self.all_group_slots: List[GroupSlot] = []

    def _post_rpc(self, endpoint: str, args: List[Any], gsh: str = "00000000") -> Dict[str, Any]:
        url = f"{self.base_url}{endpoint}"
        payload = json.dumps({"__args": args, "__gsh": gsh}).encode("utf-8")
        headers = {
            "Content-Type": "application/json; charset=utf-8",
            "User-Agent": DEFAULT_USER_AGENT,
            "Accept": "application/json, text/javascript, */*",
        }
        req = urllib.request.Request(url, data=payload, headers=headers, method="POST")
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                data = resp.read().decode("utf-8")
                return json.loads(data)
        except urllib.error.URLError as e:
            raise RuntimeError(f"Network error querying {url}: {e}")
        except json.JSONDecodeError as e:
            raise RuntimeError(f"Failed to decode response from {url}: {e}")

    def fetch_active_tt_info(self) -> Dict[str, Any]:
        """Queries TTViewer to obtain current active semester information."""
        res = self._post_rpc("/timetable/server/ttviewer.js?__func=getTTViewerData", [None, 2026])
        regular = res.get("r", {}).get("regular", {})
        default_num = regular.get("default_num")
        timetables = regular.get("timetables", [])

        info = {
            "default_num": default_num,
            "timetables": timetables,
            "current_title": "",
            "year": None,
            "date_from": None,
        }

        for tt in timetables:
            if str(tt.get("tt_num")) == str(default_num):
                info["current_title"] = tt.get("text", "")
                info["year"] = tt.get("year")
                info["date_from"] = tt.get("datefrom")
                break

        self.active_timetable_info = info
        return info

    def fetch_raw_data(self, tt_num: Optional[str] = None) -> Dict[str, Any]:
        """Fetches raw relational timetable database tables from EduPage."""
        target_num = tt_num or self.tt_num
        if not target_num:
            info = self.fetch_active_tt_info()
            target_num = info.get("default_num")
            if not target_num:
                raise RuntimeError("Could not automatically discover active timetable number.")
            self.tt_num = str(target_num)

        res = self._post_rpc(
            "/timetable/server/regulartt.js?__func=regularttGetData",
            [None, str(self.tt_num)],
        )

        r = res.get("r", {})
        if "error" in r and not r.get("dbiAccessorRes"):
            raise RuntimeError(f"EduPage returned error: {r.get('error')}")

        dbi = r.get("dbiAccessorRes")
        if not dbi or "tables" not in dbi:
            raise RuntimeError("Malformed response: missing 'dbiAccessorRes.tables'")

        return dbi

    def parse(self, tt_num: Optional[str] = None) -> "EduPageParser":
        """Fetches and builds all relational entities and structured timetables."""
        dbi = self.fetch_raw_data(tt_num=tt_num)
        tables = {t["id"]: t["data_rows"] for t in dbi["tables"]}

        # 1. Periods (Exact start time & end time per block)
        self.periods = {}
        for p in tables.get("periods", []):
            self.periods[str(p["period"])] = {
                "id": p["id"],
                "period": int(p["period"]),
                "name": p.get("name", f"{p['period']}."),
                "short": p.get("short", ""),
                "starttime": p.get("starttime", "00:00"),
                "endtime": p.get("endtime", "00:00"),
            }

        # 2. Days
        self.days = {}
        for d in tables.get("days", []):
            day_id = int(d["id"])
            self.days[str(day_id)] = {
                "id": str(day_id),
                "name": d.get("name", DAY_NAMES[day_id] if day_id < len(DAY_NAMES) else f"Day {day_id + 1}"),
                "short": d.get("short", DAY_SHORTS[day_id] if day_id < len(DAY_SHORTS) else f"D{day_id + 1}"),
                "day_of_week": day_id + 1,
            }

        # 3. Student Groups / Classes
        self.classes = {}
        for c in tables.get("classes", []):
            name = c.get("name", "").strip()
            if name:
                self.classes[c["id"]] = {
                    "id": c["id"],
                    "name": name,
                    "short": c.get("short", "").strip(),
                    "color": c.get("color", ""),
                }

        # 4. Teachers / Professors
        self.teachers = {}
        for t in tables.get("teachers", []):
            full_name = t.get("name", "").strip()
            if full_name:
                self.teachers[t["id"]] = {
                    "id": t["id"],
                    "full_name": full_name,
                    "short_name": t.get("short", "").strip(),
                    "name": full_name,
                    "email": t.get("email", ""),
                }

        # 5. Subjects
        self.subjects = {}
        for s in tables.get("subjects", []):
            name = s.get("name", "").strip()
            if name:
                self.subjects[s["id"]] = {
                    "id": s["id"],
                    "name": name,
                    "short": s.get("short", "").strip(),
                    "color": s.get("color", ""),
                }

        # 6. Classrooms
        self.classrooms = {}
        for r in tables.get("classrooms", []):
            name = r.get("name", "").strip()
            if name:
                self.classrooms[r["id"]] = {
                    "id": r["id"],
                    "name": name,
                    "short": r.get("short", "").strip(),
                }

        # 7. Lessons
        self.lessons = {les["id"]: les for les in tables.get("lessons", [])}

        # 8. Cards
        self.cards = tables.get("cards", [])

        # Process timetable slots
        self._build_schedule_slots()
        return self

    def _build_schedule_slots(self) -> None:
        self.schedule_by_group.clear()
        self.schedule_by_professor.clear()
        self.schedule_by_room.clear()
        self.all_group_slots.clear()

        for card in self.cards:
            period_val = card.get("period")
            days_bits = card.get("days")
            if not period_val or not days_bits:
                continue

            lesson_id = card.get("lessonid")
            lesson = self.lessons.get(lesson_id, {})
            if not lesson:
                continue

            # Exact period calculation: start period + duration
            p_start = int(period_val)
            duration = int(lesson.get("durationperiods", 1))
            p_end = p_start + duration - 1

            start_period_info = self.periods.get(str(p_start))
            end_period_info = self.periods.get(str(p_end))

            start_time = start_period_info["starttime"] if start_period_info else f"Period {p_start}"
            end_time = end_period_info["endtime"] if end_period_info else f"Period {p_end}"

            # Subject
            subject_info = self.subjects.get(lesson.get("subjectid"), {})
            subject_name = subject_info.get("name", "Unknown Subject")
            subject_short = subject_info.get("short", subject_name)

            # Professors
            prof_names = [
                self.teachers[tid]["full_name"]
                for tid in lesson.get("teacherids", [])
                if tid in self.teachers and self.teachers[tid]["full_name"]
            ]
            primary_prof = prof_names[0] if prof_names else "TBA"

            # Classrooms
            room_ids = card.get("classroomids") or lesson.get("classroomids") or []
            room_names = [
                self.classrooms[rid]["name"]
                for rid in room_ids
                if rid in self.classrooms and self.classrooms[rid]["name"]
            ]
            primary_room = room_names[0] if room_names else "TBA"

            # Groups / Classes
            group_names = [
                self.classes[cid]["name"]
                for cid in lesson.get("classids", [])
                if cid in self.classes and self.classes[cid]["name"]
            ]
            if not group_names:
                continue

            groups_str = ", ".join(group_names)

            # Decode Day bitmask (e.g. '00010' -> Thursday, index 3)
            day_indices = [i for i, b in enumerate(days_bits) if b == "1"]
            for d_idx in day_indices:
                day_info = self.days.get(str(d_idx))
                day_name = day_info["name"] if day_info else DAY_NAMES[d_idx % 7]
                day_of_week = d_idx + 1

                # 1. Populate individual group slots
                for grp_name in group_names:
                    g_slot = GroupSlot(
                        day=day_name,
                        day_of_week=day_of_week,
                        start_time=start_time,
                        end_time=end_time,
                        period_start=p_start,
                        period_end=p_end,
                        duration_periods=duration,
                        subject=subject_name,
                        subject_short=subject_short,
                        professors=prof_names,
                        professor=primary_prof,
                        classrooms=room_names,
                        classroom=primary_room,
                        group=grp_name,
                        all_groups=group_names,
                        lesson_id=str(lesson_id),
                        card_id=str(card.get("id")),
                    )
                    self.schedule_by_group[grp_name].append(g_slot)
                    self.all_group_slots.append(g_slot)

                # 2. Populate session slot for professors and rooms (one row per actual session)
                session = SessionSlot(
                    day=day_name,
                    day_of_week=day_of_week,
                    start_time=start_time,
                    end_time=end_time,
                    period_start=p_start,
                    period_end=p_end,
                    duration_periods=duration,
                    subject=subject_name,
                    subject_short=subject_short,
                    professors=prof_names,
                    professor=primary_prof,
                    classrooms=room_names,
                    classroom=primary_room,
                    groups=group_names,
                    groups_str=groups_str,
                    lesson_id=str(lesson_id),
                    card_id=str(card.get("id")),
                )

                for prof in prof_names:
                    self.schedule_by_professor[prof].append(session)

                for rm in room_names:
                    self.schedule_by_room[rm].append(session)

        # Sort chronologically by (day_of_week, start_time)
        for grp in self.schedule_by_group:
            self.schedule_by_group[grp].sort(key=lambda s: (s.day_of_week, s.start_time))
        for prof in self.schedule_by_professor:
            self.schedule_by_professor[prof].sort(key=lambda s: (s.day_of_week, s.start_time))
        for rm in self.schedule_by_room:
            self.schedule_by_room[rm].sort(key=lambda s: (s.day_of_week, s.start_time))

    def get_all_groups(self) -> List[str]:
        return sorted(list(self.schedule_by_group.keys()))

    def get_all_professors(self) -> List[str]:
        return sorted([p["full_name"] for p in self.teachers.values() if p["full_name"]])

    def get_all_subjects(self) -> List[Dict[str, str]]:
        return sorted(
            [{"name": s["name"], "short": s["short"]} for s in self.subjects.values() if s["name"]],
            key=lambda x: x["name"],
        )

    def get_all_classrooms(self) -> List[str]:
        return sorted([r["name"] for r in self.classrooms.values() if r["name"]])

    def get_group_schedule(self, group_name: str) -> List[GroupSlot]:
        exact = self.schedule_by_group.get(group_name)
        if exact is not None:
            return exact
        lower_map = {k.lower(): v for k, v in self.schedule_by_group.items()}
        return lower_map.get(group_name.lower(), [])

    def get_professor_schedule(self, prof_name: str) -> List[SessionSlot]:
        exact = self.schedule_by_professor.get(prof_name)
        if exact is not None:
            return exact
        target = prof_name.lower()
        results = []
        for name, slots in self.schedule_by_professor.items():
            if target in name.lower():
                results.extend(slots)
        results.sort(key=lambda s: (s.day_of_week, s.start_time))
        return results

    def get_room_schedule(self, room_name: str) -> List[SessionSlot]:
        exact = self.schedule_by_room.get(room_name)
        if exact is not None:
            return exact
        target = room_name.lower()
        results = []
        for name, slots in self.schedule_by_room.items():
            if target in name.lower():
                results.extend(slots)
        results.sort(key=lambda s: (s.day_of_week, s.start_time))
        return results

    def to_django_backend_payload(self) -> Dict[str, Any]:
        """
        Maps scraped data directly into backend/api/models.py schema:
          - Professor (full_name, email)
          - Group (group_name)
          - Subject (short_name, full_name, year_level)
          - CourseClass (subject, professor, group, room)
          - GroupTimetableSlot (group, day_of_week, start_time, end_time, course_class)
        """
        prof_list = [
            {
                "full_name": p["full_name"],
                "email": p.get("email") or f"{p['short_name'].lower().replace(' ', '.').replace('..', '.')}@inha.uz",
            }
            for p in self.teachers.values()
            if p["full_name"]
        ]

        group_list = [{"group_name": grp} for grp in self.get_all_groups()]

        subject_list = []
        for s in self.subjects.values():
            if not s["name"]:
                continue
            year_match = re.search(r"\b([1-4])\b", s["name"])
            year_level = int(year_match.group(1)) if year_match else 1
            subject_list.append({
                "short_name": s["short"] or s["name"][:10],
                "full_name": s["name"],
                "year_level": year_level,
            })

        classes_map = {}
        slots_list = []

        for slot in self.all_group_slots:
            class_key = f"{slot.subject}|{slot.professor}|{slot.group}|{slot.classroom}"
            if class_key not in classes_map:
                classes_map[class_key] = {
                    "subject_name": slot.subject,
                    "professor_name": slot.professor,
                    "group_name": slot.group,
                    "room": slot.classroom,
                }

            slots_list.append({
                "group_name": slot.group,
                "day_of_week": slot.day_of_week,
                "start_time": slot.start_time,
                "end_time": slot.end_time,
                "subject_name": slot.subject,
                "professor_name": slot.professor,
                "room": slot.classroom,
            })

        return {
            "metadata": {
                "source": self.base_url,
                "timetable_num": self.tt_num,
                "timetable_info": self.active_timetable_info,
            },
            "professors": prof_list,
            "groups": group_list,
            "subjects": subject_list,
            "classes": list(classes_map.values()),
            "timetable_slots": slots_list,
        }

    def export_json(self, output_dir: str = "data") -> Dict[str, str]:
        """Saves all extracted datasets to structured JSON files."""
        os.makedirs(output_dir, exist_ok=True)
        files = {}

        # Group schedules
        grp_dict = {
            grp: [slot.to_dict() for slot in slots]
            for grp, slots in self.schedule_by_group.items()
        }
        p_grp = os.path.join(output_dir, "timetables_by_group.json")
        with open(p_grp, "w", encoding="utf-8") as f:
            json.dump(grp_dict, f, indent=2, ensure_ascii=False)
        files["timetables_by_group"] = p_grp

        # Professor schedules
        prof_dict = {
            prof: [slot.to_dict() for slot in slots]
            for prof, slots in self.schedule_by_professor.items()
        }
        p_prof = os.path.join(output_dir, "timetables_by_professor.json")
        with open(p_prof, "w", encoding="utf-8") as f:
            json.dump(prof_dict, f, indent=2, ensure_ascii=False)
        files["timetables_by_professor"] = p_prof

        # Classroom schedules
        room_dict = {
            rm: [slot.to_dict() for slot in slots]
            for rm, slots in self.schedule_by_room.items()
        }
        p_room = os.path.join(output_dir, "timetables_by_room.json")
        with open(p_room, "w", encoding="utf-8") as f:
            json.dump(room_dict, f, indent=2, ensure_ascii=False)
        files["timetables_by_room"] = p_room

        # Entities
        for entity_name, data in [
            ("groups", self.get_all_groups()),
            ("professors", self.get_all_professors()),
            ("subjects", self.get_all_subjects()),
            ("classrooms", self.get_all_classrooms()),
        ]:
            p_ent = os.path.join(output_dir, f"{entity_name}.json")
            with open(p_ent, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            files[entity_name] = p_ent

        # Django payload
        p_backend = os.path.join(output_dir, "django_backend_payload.json")
        with open(p_backend, "w", encoding="utf-8") as f:
            json.dump(self.to_django_backend_payload(), f, indent=2, ensure_ascii=False)
        files["django_backend_payload"] = p_backend

        # Master dataset
        p_master = os.path.join(output_dir, "all_data.json")
        master = {
            "metadata": {
                "source": self.base_url,
                "timetable_num": self.tt_num,
                "timetable_info": self.active_timetable_info,
                "total_groups": len(self.schedule_by_group),
                "total_professors": len(self.teachers),
                "total_subjects": len(self.subjects),
                "total_classrooms": len(self.classrooms),
                "total_group_slots": len(self.all_group_slots),
            },
            "timetables_by_group": grp_dict,
        }
        with open(p_master, "w", encoding="utf-8") as f:
            json.dump(master, f, indent=2, ensure_ascii=False)
        files["all_data"] = p_master

        return files

    def export_csv(self, output_dir: str = "data") -> str:
        """Exports all group schedule slots into a single CSV table."""
        os.makedirs(output_dir, exist_ok=True)
        csv_path = os.path.join(output_dir, "all_timetable_slots.csv")
        fieldnames = [
            "group",
            "day",
            "day_of_week",
            "start_time",
            "end_time",
            "duration_periods",
            "subject",
            "subject_short",
            "professor",
            "professors",
            "classroom",
            "all_groups",
            "period_start",
            "period_end",
        ]

        with open(csv_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            for slot in sorted(self.all_group_slots, key=lambda s: (s.group, s.day_of_week, s.start_time)):
                writer.writerow({
                    "group": slot.group,
                    "day": slot.day,
                    "day_of_week": slot.day_of_week,
                    "start_time": slot.start_time,
                    "end_time": slot.end_time,
                    "duration_periods": slot.duration_periods,
                    "subject": slot.subject,
                    "subject_short": slot.subject_short,
                    "professor": slot.professor,
                    "professors": ", ".join(slot.professors),
                    "classroom": slot.classroom,
                    "all_groups": ", ".join(slot.all_groups),
                    "period_start": slot.period_start,
                    "period_end": slot.period_end,
                })

        return csv_path


def format_group_table(slots: List[GroupSlot], title: str = "") -> str:
    lines = []
    if title:
        lines.append("=" * 96)
        lines.append(f"  {title}")
        lines.append("=" * 96)

    if not slots:
        lines.append("  (No schedule slots found)")
        return "\n".join(lines)

    header = f"| {'Day':<9} | {'Time':<11} | {'Subject':<32} | {'Professor':<22} | {'Room':<12} |"
    sep = "+" + "-" * 11 + "+" + "-" * 13 + "+" + "-" * 34 + "+" + "-" * 24 + "+" + "-" * 14 + "+"

    lines.append(sep)
    lines.append(header)
    lines.append(sep)

    current_day = None
    for s in slots:
        if current_day is not None and s.day != current_day:
            lines.append(sep)
        current_day = s.day
        subj = s.subject[:32]
        prof = s.professor[:22]
        room = s.classroom[:12]
        time_str = f"{s.start_time}-{s.end_time}"
        lines.append(f"| {s.day:<9} | {time_str:<11} | {subj:<32} | {prof:<22} | {room:<12} |")

    lines.append(sep)
    return "\n".join(lines)


def format_session_table(slots: List[SessionSlot], title: str = "", is_professor: bool = True) -> str:
    lines = []
    if title:
        lines.append("=" * 112)
        lines.append(f"  {title}")
        lines.append("=" * 112)

    if not slots:
        lines.append("  (No schedule slots found)")
        return "\n".join(lines)

    col4_name = "Groups" if is_professor else "Professor"
    col5_name = "Room" if is_professor else "Groups"
    header = f"| {'Day':<9} | {'Time':<11} | {'Subject':<28} | {col4_name:<28} | {col5_name:<26} |"
    sep = "+" + "-" * 11 + "+" + "-" * 13 + "+" + "-" * 30 + "+" + "-" * 30 + "+" + "-" * 28 + "+"

    lines.append(sep)
    lines.append(header)
    lines.append(sep)

    current_day = None
    for s in slots:
        if current_day is not None and s.day != current_day:
            lines.append(sep)
        current_day = s.day
        subj = s.subject[:28]
        time_str = f"{s.start_time}-{s.end_time}"
        if is_professor:
            col4_val = s.groups_str[:28]
            col5_val = s.classroom[:26]
        else:
            col4_val = s.professor[:28]
            col5_val = s.groups_str[:26]

        lines.append(f"| {s.day:<9} | {time_str:<11} | {subj:<28} | {col4_val:<28} | {col5_val:<26} |")

    lines.append(sep)
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(
        description="EduPage University Timetable Scraper & Text Parser",
        formatter_class=argparse.RawTextHelpFormatter,
    )
    parser.add_argument("--url", default=DEFAULT_BASE_URL, help="Base URL of EduPage timetable (default: %(default)s)")
    parser.add_argument("--tt-num", default=None, help="Specific timetable number (default: auto-detect active)")
    parser.add_argument("--output-dir", "-o", default="data", help="Directory to save JSON/CSV exports (default: %(default)s)")
    parser.add_argument("--group", "-g", help="Display timetable for a specific student group (e.g. CIE26-1)")
    parser.add_argument("--groups", action="store_true", help="List all available group names")
    parser.add_argument("--professor", "-p", help="Display timetable for a specific professor")
    parser.add_argument("--professors", action="store_true", help="List all professors")
    parser.add_argument("--room", "-r", help="Display timetable for a specific classroom")
    parser.add_argument("--classrooms", action="store_true", help="List all classrooms")
    parser.add_argument("--subjects", action="store_true", help="List all subjects")
    parser.add_argument("--export-csv", action="store_true", help="Export slots to CSV in addition to JSON")
    parser.add_argument("--quiet", "-q", action="store_true", help="Run without printing summaries")

    args = parser.parse_args()

    script_dir = os.path.dirname(os.path.abspath(__file__))
    output_dir = args.output_dir if os.path.isabs(args.output_dir) else os.path.join(script_dir, args.output_dir)

    if not args.quiet:
        print(f"Connecting to EduPage at {args.url}...")

    edupage = EduPageParser(base_url=args.url, tt_num=args.tt_num)

    try:
        edupage.parse()
    except Exception as exc:
        print(f"Error parsing timetable: {exc}", file=sys.stderr)
        sys.exit(1)

    info = edupage.active_timetable_info
    tt_title = info.get("current_title", f"TT #{edupage.tt_num}")

    if not args.quiet:
        print(f"Successfully loaded timetable: {tt_title} (Number: {edupage.tt_num})")
        print(f"  • Groups:     {len(edupage.schedule_by_group)}")
        print(f"  • Professors: {len(edupage.teachers)}")
        print(f"  • Subjects:   {len(edupage.subjects)}")
        print(f"  • Classrooms: {len(edupage.classrooms)}")
        print(f"  • Total group slots: {len(edupage.all_group_slots)}")

    # Specific queries
    if args.groups:
        print("\nAll Available Groups:")
        for g in edupage.get_all_groups():
            print(f"  {g}")
        return

    if args.professors:
        print("\nAll Available Professors:")
        for p in edupage.get_all_professors():
            print(f"  {p}")
        return

    if args.subjects:
        print("\nAll Available Subjects:")
        for s in edupage.get_all_subjects():
            print(f"  {s['short']:<10} - {s['name']}")
        return

    if args.classrooms:
        print("\nAll Available Classrooms:")
        for r in edupage.get_all_classrooms():
            print(f"  {r}")
        return

    if args.group:
        slots = edupage.get_group_schedule(args.group)
        print("\n" + format_group_table(slots, title=f"Timetable for Group: {args.group} ({tt_title})"))
        return

    if args.professor:
        slots = edupage.get_professor_schedule(args.professor)
        print("\n" + format_session_table(slots, title=f"Timetable for Professor: {args.professor} ({tt_title})", is_professor=True))
        return

    if args.room:
        slots = edupage.get_room_schedule(args.room)
        print("\n" + format_session_table(slots, title=f"Timetable for Classroom: {args.room} ({tt_title})", is_professor=False))
        return

    # Export datasets
    exported_json = edupage.export_json(output_dir=output_dir)
    if not args.quiet:
        print(f"\nSaved JSON datasets to {output_dir}:")
        for key, path in exported_json.items():
            print(f"  ✓ {key:<24} -> {os.path.basename(path)}")

    if args.export_csv:
        csv_path = edupage.export_csv(output_dir=output_dir)
        if not args.quiet:
            print(f"  ✓ CSV Export               -> {os.path.basename(csv_path)}")

    # Show a sample group schedule preview
    if not args.quiet and edupage.schedule_by_group:
        sample_group = "CIE26-1" if "CIE26-1" in edupage.schedule_by_group else list(edupage.schedule_by_group.keys())[0]
        sample_slots = edupage.get_group_schedule(sample_group)
        print("\n" + format_group_table(sample_slots, title=f"Sample Schedule Preview: {sample_group} ({tt_title})"))


if __name__ == "__main__":
    main()

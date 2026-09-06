#!/usr/bin/env python3
"""
INS Grades - Timetable Service Master Entrypoint.
Run directly with: `python main.py`

This standalone microservice:
  1. Loads environment variables from .env
  2. Connects to PostgreSQL database (via DATABASE_URL or DB_* variables) or SQLite
  3. Scrapes the latest university timetable from EduPage (https://iut.edupage.org/timetable/)
  4. In-place database upsert:
     - Professors (full_name, email)
     - Groups (group_name)
     - Subjects (full_name, short_name, year_level)
     - CourseClasses (in-place update matching (group, subject), preserving class_id)
     - GroupTimetableSlots (in-place timing updates without breaking foreign keys)
  5. Student Enrollment & Override Management:
     - Preserves 'dropped' status (never re-adds dropped courses)
     - Preserves extra / retake courses from other groups (never deletes them)
     - Automatically matches active group courses to students who haven't dropped them
     - Updates existing enrollments in-place to new timings without recreation
  6. Captures upgraded timetable screenshots for each group and links them
     to Group.timetable_image_url in the database.
"""

import argparse
import datetime
import os
import sys
import time
from typing import Optional

# Load .env file
try:
    from dotenv import load_dotenv

    # Try local timetable/.env, then parent .env
    current_dir = os.path.dirname(os.path.abspath(__file__))
    load_dotenv(os.path.join(current_dir, ".env"))
    load_dotenv(os.path.join(os.path.dirname(current_dir), ".env"))
except ImportError:
    pass

from db import DatabaseManager
from parser import EduPageParser
from s3_storage import S3StorageManager
from screenshot_taker import TimetableScreenshotTaker


def run_pipeline(
    target_group: Optional[str] = None,
    limit_screenshots: Optional[int] = None,
    skip_screenshots: bool = False,
    dry_run: bool = False,
    edupage_url: Optional[str] = None,
) -> bool:
    start_time = time.time()
    print("=" * 80)
    print("  INS Grades - Timetable Sync & Screenshot Pipeline")
    print(f"  Timestamp: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 80)

    url = edupage_url or os.getenv("EDUPAGE_URL", "https://iut.edupage.org")
    capture_screens = (
        not skip_screenshots
        and os.getenv("CAPTURE_SCREENSHOTS", "true").strip().lower() in ("true", "1", "yes")
    )
    static_url_prefix = (os.getenv("STATIC_URL_PREFIX") or "/static/timetables").rstrip("/")
    screenshot_dir = os.getenv("SCREENSHOT_DIR") or os.path.join(
        os.path.dirname(os.path.abspath(__file__)), "screenshots"
    )
    os.makedirs(screenshot_dir, exist_ok=True)

    # 1. Connect to database
    db = DatabaseManager()
    db.connect()

    # 2. Scrape EduPage
    print(f"[{datetime.datetime.now().strftime('%H:%M:%S')}] Scraping timetable from {url}...")
    parser = EduPageParser(base_url=url)
    parser.parse()

    info = parser.active_timetable_info
    tt_title = info.get("current_title", f"TT #{parser.tt_num}")
    all_groups = parser.get_all_groups()

    print(f"[{datetime.datetime.now().strftime('%H:%M:%S')}] Timetable loaded: {tt_title} (#{parser.tt_num})")
    print(f"  • Total Groups:     {len(all_groups)}")
    print(f"  • Total Professors: {len(parser.teachers)}")
    print(f"  • Total Subjects:   {len(parser.subjects)}")
    print(f"  • Total Slots:      {len(parser.all_group_slots)}")

    metrics = {
        "classes_synced": 0,
        "slots_created": 0,
        "slots_updated": 0,
        "enrollments_created": 0,
        "enrollments_preserved": 0,
        "dropped_respected": 0,
        "screenshots_linked": 0,
    }

    try:
        # 3. Synchronize database entities
        print(f"\n[{datetime.datetime.now().strftime('%H:%M:%S')}] Synchronizing database entities...")

        prof_map = db.sync_professors(parser.teachers)
        group_map = db.sync_groups(all_groups)
        subj_map = db.sync_subjects(parser.subjects)

        groups_to_sync = [target_group] if target_group else all_groups
        for grp_name in groups_to_sync:
            grp_id = group_map.get(grp_name)
            if not grp_id:
                continue

            slots = parser.get_group_schedule(grp_name)
            c_sync, s_created, s_updated = db.sync_classes_and_slots(
                group_name=grp_name,
                group_id=grp_id,
                slots=slots,
                prof_map=prof_map,
                subj_map=subj_map,
            )
            metrics["classes_synced"] += c_sync
            metrics["slots_created"] += s_created
            metrics["slots_updated"] += s_updated

        # 4. Student Enrollment & Drop Preservation
        print(f"[{datetime.datetime.now().strftime('%H:%M:%S')}] Synchronizing student enrollments...")
        target_grp_id = group_map.get(target_group) if target_group else None
        e_created, e_preserved, d_respected = db.sync_student_enrollments(target_group_id=target_grp_id)
        metrics["enrollments_created"] = e_created
        metrics["enrollments_preserved"] = e_preserved
        metrics["dropped_respected"] = d_respected

        if dry_run:
            print(f"[{datetime.datetime.now().strftime('%H:%M:%S')}] [Dry Run] Rolling back database changes...")
            db.rollback()
        else:
            db.commit()
            print(f"[{datetime.datetime.now().strftime('%H:%M:%S')}] Database changes committed successfully.")

        # Convert any legacy /static/timetables/ URLs in DB to standard S3 bucket URLs
        try:
            cur = db.conn.cursor()
            db._execute(
                cur,
                "UPDATE groups SET timetable_image_url = 'https://t3.storageapi.dev/resilient-module-m3qmihat/timetables/' || REPLACE(REPLACE(timetable_image_url, '/static/timetables/', ''), '.png', '') || '.png' WHERE timetable_image_url LIKE '/static/%'"
            )
            db.commit()
        except Exception:
            pass

        # 5. Upgraded Screenshot Automation
        if capture_screens and not dry_run:
            print(f"\n[{datetime.datetime.now().strftime('%H:%M:%S')}] Running upgraded screenshot capture...")
            s3_manager = S3StorageManager()
            if s3_manager.is_configured():
                print(f"[{datetime.datetime.now().strftime('%H:%M:%S')}] S3 Storage enabled. Target bucket: {s3_manager.bucket_name}")
            else:
                print(f"[{datetime.datetime.now().strftime('%H:%M:%S')}] S3 secret key not detected. Linking standard S3 bucket URLs: {s3_manager.endpoint_url}/{s3_manager.bucket_name}/timetables/<group>.png")

            tt_page_url = f"{url.rstrip('/')}/timetable/"
            taker = TimetableScreenshotTaker(
                url=tt_page_url,
                output_dir=screenshot_dir,
                headless=True,
            )

            groups_to_snap = [target_group] if target_group else all_groups

            def on_screenshot_saved(group_name: str, saved_path: str):
                old_image_url = db.get_group_screenshot(group_name)

                # Upload to S3 and get S3 bucket URL
                image_url = s3_manager.upload_timetable_screenshot(
                    group_name=group_name,
                    local_filepath=saved_path,
                    old_image_url=old_image_url,
                )

                if not image_url:
                    image_url = s3_manager.get_public_url(group_name)

                db.update_group_screenshot(group_name, image_url)
                metrics["screenshots_linked"] += 1
                print(f"    ✓ Linked S3 screenshot for {group_name}: {image_url}")

            taker.capture_multiple(
                group_names=groups_to_snap,
                limit=limit_screenshots,
                callback=on_screenshot_saved,
            )
            db.commit()

    except Exception as exc:
        db.rollback()
        raise exc
    finally:
        db.close()

    elapsed = time.time() - start_time
    print("\n" + "=" * 80)
    print("  TIMETABLE PIPELINE SUMMARY REPORT")
    print("=" * 80)
    print(f"  Execution Time:          {elapsed:.2f} seconds")
    print(f"  Course Classes Synced:   {metrics['classes_synced']}")
    print(f"  Timetable Slots Created: {metrics['slots_created']}")
    print(f"  Timetable Slots Updated: {metrics['slots_updated']}")
    print(f"  Enrollments Created:     {metrics['enrollments_created']}")
    print(f"  Enrollments Preserved:   {metrics['enrollments_preserved']}")
    print(f"  Dropped Courses Respect: {metrics['dropped_respected']}")
    print(f"  Screenshots Linked:      {metrics['screenshots_linked']}")
    print("=" * 80)
    return True


def main():
    parser = argparse.ArgumentParser(
        description="INS Grades - Timetable Synchronization & Screenshot Service",
        formatter_class=argparse.RawTextHelpFormatter,
    )
    parser.add_argument("--url", default=None, help="EduPage timetable URL")
    parser.add_argument("--group", "-g", help="Run sync & screenshot for a single group (e.g. CIE26-1)")
    parser.add_argument("--skip-screenshots", action="store_true", help="Skip screenshots, only sync database")
    parser.add_argument("--limit-screenshots", "-l", type=int, help="Limit number of screenshots captured")
    parser.add_argument("--dry-run", action="store_true", help="Perform sync logic without saving to database")

    args = parser.parse_args()

    try:
        run_pipeline(
            target_group=args.group,
            limit_screenshots=args.limit_screenshots,
            skip_screenshots=args.skip_screenshots,
            dry_run=args.dry_run,
            edupage_url=args.url,
        )
    except Exception as exc:
        print(f"\n[FATAL ERROR] Timetable service failed: {exc}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()

import os
import sys
import re
import time
import asyncio
import logging
from datetime import datetime
import httpx

try:
    from dotenv import load_dotenv
    current_dir = os.path.dirname(os.path.abspath(__file__))
    load_dotenv(os.path.join(current_dir, ".env"))
    load_dotenv(os.path.join(os.path.dirname(current_dir), ".env"))
except ImportError:
    pass

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("TelegramBot")

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
API_URL = (os.getenv("API_URL") or "http://backend:3000").rstrip("/")
API_KEY = os.getenv("API_KEY", "ins_secure_api_key_2026_x89a")
APP_URL = os.getenv("APP_URL", "https://ins-grades.vercel.app")

# S3 Storage Configuration
S3_ENDPOINT_URL = (os.getenv("S3_ENDPOINT_URL") or os.getenv("AWS_ENDPOINT_URL_S3") or "https://t3.storageapi.dev").rstrip("/")
S3_BUCKET_NAME = os.getenv("S3_BUCKET_NAME") or os.getenv("AWS_STORAGE_BUCKET_NAME") or "resilient-module-m3qmihat"
S3_ACCESS_KEY_ID = (
    os.getenv("S3_ACCESS_KEY_ID")
    or os.getenv("AWS_ACCESS_KEY_ID")
    or os.getenv("ACCESS_KEY_ID")
    or "tid_sJKHMdAQGSDbJgIZUOoZltQsaWuUlbGaundBPOmwCdvQIJjMfJ"
).strip()
S3_SECRET_ACCESS_KEY = (
    os.getenv("S3_SECRET_ACCESS_KEY")
    or os.getenv("AWS_SECRET_ACCESS_KEY")
    or os.getenv("SECRET_ACCESS_KEY")
    or os.getenv("S3_SECRET_KEY")
    or os.getenv("AWS_SECRET_KEY")
    or os.getenv("TIGRIS_SECRET_ACCESS_KEY")
    or ""
).strip()

DAY_NAMES = {
    1: "Monday",
    2: "Tuesday",
    3: "Wednesday",
    4: "Thursday",
    5: "Friday",
    6: "Saturday",
    7: "Sunday",
}

# Clean, simplified reply keyboard - strictly Timetable and Today's Lessons
MAIN_MENU_KEYBOARD = {
    "keyboard": [
        [{"text": "📅 Timetable"}, {"text": "📖 Today's Lessons"}]
    ],
    "resize_keyboard": True,
    "is_persistent": True
}


def natural_sort_key(name: str):
    """Natural alphanumeric sort key for groups like CIE26-1, CIE26-10."""
    return [int(tok) if tok.isdigit() else tok.lower() for tok in re.split(r'(\d+)', name)]


def chunk_list(items, chunk_size=2):
    """Splits a list into chunks for inline keyboard rows."""
    return [items[i:i + chunk_size] for i in range(0, len(items), chunk_size)]


class TimetableTelegramBot:
    def __init__(self, token: str, api_url: str):
        self.token = token
        self.api_url = api_url
        self.tg_base = f"https://api.telegram.org/bot{token}"
        self.client = httpx.AsyncClient(timeout=30.0)
        self.is_running = True
        self.user_states = {}

    async def api_get(self, endpoint: str):
        """Helper to call Django REST API."""
        url = f"{self.api_url}/api/{endpoint.lstrip('/')}"
        headers = {"X-API-KEY": API_KEY}
        try:
            r = await self.client.get(url, headers=headers, timeout=10.0)
            if r.status_code == 200:
                return r.json()
            return None
        except Exception as e:
            logger.error(f"[API Error] GET {url}: {e}")
            return None

    async def api_post(self, endpoint: str, data: dict):
        """Helper to call Django REST API POST."""
        url = f"{self.api_url}/api/{endpoint.lstrip('/')}"
        headers = {"X-API-KEY": API_KEY}
        try:
            r = await self.client.post(url, json=data, headers=headers, timeout=10.0)
            if r.status_code in (200, 201):
                return r.json()
            return None
        except Exception as e:
            logger.error(f"[API Error] POST {url}: {e}")
            return None

    async def send_message(self, chat_id: int, text: str, reply_markup: dict = None):
        """Send a message to a Telegram user."""
        url = f"{self.tg_base}/sendMessage"
        payload = {
            "chat_id": chat_id,
            "text": text,
            "parse_mode": "HTML",
        }
        if reply_markup:
            payload["reply_markup"] = reply_markup
        try:
            r = await self.client.post(url, json=payload, timeout=10.0)
            return r.json()
        except Exception as e:
            logger.error(f"[TG Error] send_message: {e}")
            return None

    async def setup_chat_menu_button(self):
        """Sets the official Telegram Mini App menu button at the bottom-left of the chat bar."""
        if not APP_URL:
            return
        try:
            res = await self.client.post(
                f"{self.tg_base}/setChatMenuButton",
                json={
                    "menu_button": {
                        "type": "web_app",
                        "text": "INS Grades",
                        "web_app": {"url": APP_URL}
                    }
                },
                timeout=10.0
            )
            data = res.json()
            logger.info(f"[TelegramBot] Chat menu button configured: {data.get('ok')}")
        except Exception as e:
            logger.warning(f"[TelegramBot] Could not setChatMenuButton: {e}")

    async def edit_message_text(self, chat_id: int, message_id: int, text: str, reply_markup: dict = None):
        """Edit an existing Telegram message."""
        url = f"{self.tg_base}/editMessageText"
        payload = {
            "chat_id": chat_id,
            "message_id": message_id,
            "text": text,
            "parse_mode": "HTML"
        }
        if reply_markup:
            payload["reply_markup"] = reply_markup
        try:
            r = await self.client.post(url, json=payload, timeout=10.0)
            return r.json()
        except Exception as e:
            logger.error(f"[TG Error] edit_message_text: {e}")
            return None

    async def answer_callback_query(self, query_id: str, text: str = None):
        """Acknowledge Telegram callback query."""
        payload = {"callback_query_id": query_id}
        if text:
            payload["text"] = text
        try:
            await self.client.post(f"{self.tg_base}/answerCallbackQuery", json=payload, timeout=8.0)
        except Exception as e:
            logger.debug(f"[TG] answerCallbackQuery error: {e}")

    async def send_photo(self, chat_id: int, photo_url: str, caption: str = None, reply_markup: dict = None):
        """Send a photo to a Telegram user from URL or downloaded S3 bytes."""
        url = f"{self.tg_base}/sendPhoto"

        # 1. Try fetching via S3 client directly if S3 credentials are present
        if S3_SECRET_ACCESS_KEY:
            try:
                import boto3
                from botocore.config import Config
                s3_cli = boto3.client(
                    "s3",
                    endpoint_url=S3_ENDPOINT_URL,
                    region_name="auto",
                    aws_access_key_id=S3_ACCESS_KEY_ID,
                    aws_secret_access_key=S3_SECRET_ACCESS_KEY,
                    config=Config(s3={"addressing_style": "path"})
                )
                if f"/{S3_BUCKET_NAME}/" in photo_url:
                    key = photo_url.split(f"/{S3_BUCKET_NAME}/")[-1].split("?")[0]
                else:
                    filename = os.path.basename(photo_url).split("?")[0]
                    key = f"timetables/{filename}"

                obj = s3_cli.get_object(Bucket=S3_BUCKET_NAME, Key=key)
                img_bytes = obj["Body"].read()

                files = {"photo": ("timetable.png", img_bytes, "image/png")}
                data = {"chat_id": str(chat_id), "parse_mode": "HTML"}
                if caption:
                    data["caption"] = caption
                if reply_markup:
                    data["reply_markup"] = reply_markup
                r = await self.client.post(url, data=data, files=files, timeout=25.0)
                res = r.json()
                if res.get("ok"):
                    return res
            except Exception as e:
                logger.info(f"[TG S3 Direct Fetch] Could not get photo directly via boto3 ({e}), trying URL...")

        # 2. Try sending direct photo URL
        payload = {
            "chat_id": chat_id,
            "photo": photo_url,
            "parse_mode": "HTML",
        }
        if caption:
            payload["caption"] = caption
        if reply_markup:
            payload["reply_markup"] = reply_markup

        try:
            r = await self.client.post(url, json=payload, timeout=15.0)
            res = r.json()
            if res.get("ok"):
                return res
        except Exception as e:
            logger.warning(f"[TG] send_photo via direct URL failed ({e}), trying HTTP stream upload...")

        # 3. Fallback: Download image content via HTTP and upload as multipart form data
        try:
            fetch_url = photo_url
            if fetch_url.startswith("/"):
                fetch_url = f"{self.api_url}{fetch_url}"

            img_resp = await self.client.get(fetch_url, timeout=20.0)
            if img_resp.status_code == 200:
                files = {"photo": ("timetable.png", img_resp.content, "image/png")}
                data = {"chat_id": str(chat_id), "parse_mode": "HTML"}
                if caption:
                    data["caption"] = caption
                r = await self.client.post(url, data=data, files=files, timeout=25.0)
                return r.json()
        except Exception as exc:
            logger.error(f"[TG Error] send_photo binary upload error: {exc}")

        return None

    async def handle_start(self, chat_id: int, user: dict):
        """
        Handle /start command.
        If user already exists in DB: opens the main menu.
        If user does NOT exist: asks for their Student ID.
        """
        tg_id = user.get("id")
        first_name = user.get("first_name", "Student")

        # Check if user already exists and is linked
        student_data = await self.api_get(f"students/?telegram_id={tg_id}")
        if student_data and len(student_data) > 0:
            s = student_data[0]
            self.user_states.pop(tg_id, None)

            msg = (
                f"👋 Welcome back, <b>{s['full_name']}</b>!\n\n"
                f"🎓 <b>Student ID:</b> <code>{s['student_id']}</code>\n"
                f"👥 <b>Group:</b> {s.get('group_name', 'Assigned')}\n\n"
                f"Tap <b>📅 Timetable</b> below to view your full weekly schedule and photo, "
                f"or open <b>INS Grades</b> from the bottom menu bar."
            )
            await self.send_message(chat_id, msg, reply_markup=MAIN_MENU_KEYBOARD)
            return

        # User is not registered or linked yet
        self.user_states[tg_id] = {"step": "WAITING_STUDENT_ID"}

        msg = (
            f"👋 Hello, <b>{first_name}</b>!\n\n"
            f"Welcome to <b>INS Grades University Bot</b>.\n\n"
            f"Please enter your <b>Student ID</b> (e.g. <code>U2410252</code>) to connect:"
        )
        await self.send_message(chat_id, msg)

    async def handle_text(self, chat_id: int, user: dict, text: str):
        """Handle incoming text messages and menu button clicks."""
        text = text.strip()
        tg_id = user.get("id")
        username = user.get("username", "")

        # 1. Menu Buttons & Commands
        if text.startswith("/start") or text.lower() == "/help":
            await self.handle_start(chat_id, user)
            return

        if text in ("📅 Timetable", "timetable", "/timetable", "/photo", "/image", "/week", "schedule"):
            await self.handle_timetable(chat_id, tg_id)
            return

        if text in ("📖 Today's Lessons", "today's lessons", "today", "/today"):
            await self.handle_today(chat_id, tg_id)
            return

        # 2. Check if student sent their Student ID candidate
        candidate = text.upper().strip()

        # Check if student exists in database
        student_obj = await self.api_get(f"students/{candidate}/")

        # CASE A: Student ALREADY exists in the database
        if student_obj and "student_id" in student_obj:
            res = await self.api_post("students/link-telegram/", {
                "student_id": candidate,
                "telegram_id": tg_id,
                "telegram_username": username
            })

            self.user_states.pop(tg_id, None)

            if res and ("student" in res or res.get("success")):
                s = res.get("student") or student_obj
                msg = (
                    f"✅ <b>Successfully Connected!</b>\n\n"
                    f"Welcome, <b>{s.get('full_name', 'Student')}</b>!\n"
                    f"🎓 <b>Student ID:</b> <code>{candidate}</code>\n"
                    f"👥 <b>Group:</b> {s.get('group_name', 'Assigned')}\n\n"
                    f"Your account is linked. Tap <b>📅 Timetable</b> below to view your schedule:"
                )
                await self.send_message(chat_id, msg, reply_markup=MAIN_MENU_KEYBOARD)
            else:
                await self.send_message(chat_id, "⚠️ Failed to link account. Please try sending your Student ID again.")
            return

        # CASE B: Student is NOT in database -> Ask course year and faculty to choose group
        first_name = user.get("first_name", "")
        last_name = user.get("last_name", "")
        self.user_states[tg_id] = {
            "step": "SELECT_YEAR",
            "student_id": candidate,
            "first_name": first_name,
            "last_name": last_name,
            "username": username,
        }

        msg = (
            f"ℹ️ Student ID <code>{candidate}</code> was not found in the database.\n\n"
            f"Let's register you in 3 quick steps!\n\n"
            f"<b>Step 1/3:</b> Select your <b>Course / Year of Study</b>:"
        )
        keyboard = {
            "inline_keyboard": [
                [{"text": "1️⃣ 1st Year (Freshman)", "callback_data": "reg_year:1:26"}],
                [{"text": "2️⃣ 2nd Year (Sophomore)", "callback_data": "reg_year:2:25"}],
                [{"text": "3️⃣ 3rd Year (Junior)", "callback_data": "reg_year:3:24"}],
                [{"text": "4️⃣ 4th Year (Senior)", "callback_data": "reg_year:4:23"}],
            ]
        }
        await self.send_message(chat_id, msg, reply_markup=keyboard)

    async def handle_callback_query(self, query: dict):
        """Handle inline keyboard callbacks for multi-step registration wizard."""
        query_id = query.get("id")
        await self.answer_callback_query(query_id)

        user = query.get("from", {})
        tg_id = user.get("id")
        chat_id = query.get("message", {}).get("chat", {}).get("id")
        message_id = query.get("message", {}).get("message_id")
        data = query.get("data", "")

        state = self.user_states.get(tg_id)
        if not state:
            await self.send_message(chat_id, "⚠️ Session expired. Please send /start to begin.")
            return

        # STEP 1 -> STEP 2: Year Selected -> Choose Faculty
        if data.startswith("reg_year:"):
            _, year_num, year_code = data.split(":")
            state["year_of_study"] = int(year_num)
            state["year_code"] = year_code
            state["step"] = "SELECT_FACULTY"

            # Faculties available by year code
            if year_code == "26":  # Year 1
                fac_buttons = [
                    [{"text": "📡 Computer & Info Eng (CIE)", "callback_data": "reg_fac:CIE"}],
                    [{"text": "💼 Business Management (BM)", "callback_data": "reg_fac:BM"}],
                ]
            elif year_code == "25":  # Year 2
                fac_buttons = [
                    [{"text": "💻 Computer Science (CSE/CS)", "callback_data": "reg_fac:CSE"}],
                    [{"text": "📡 Info & Comm Eng (ICE)", "callback_data": "reg_fac:ICE"}],
                    [{"text": "🤖 AI & Data Science (AI/DS)", "callback_data": "reg_fac:AI"}],
                    [{"text": "💼 Business Management (BM)", "callback_data": "reg_fac:BM"}],
                ]
            elif year_code == "24":  # Year 3
                fac_buttons = [
                    [{"text": "💻 Computer Science (CSE)", "callback_data": "reg_fac:CSE"}],
                    [{"text": "📡 Info & Comm Eng (ICE)", "callback_data": "reg_fac:ICE"}],
                    [{"text": "💼 Business & Logistics (SBL)", "callback_data": "reg_fac:SBL"}],
                ]
            else:  # Year 4
                fac_buttons = [
                    [{"text": "💻 Computer Science (CSE)", "callback_data": "reg_fac:CSE"}],
                    [{"text": "📡 Info & Comm Eng (ICE)", "callback_data": "reg_fac:ICE"}],
                ]

            text = (
                f"🎓 <b>Year {year_num}</b> selected.\n\n"
                f"<b>Step 2/3:</b> Select your <b>Faculty / Department</b>:"
            )
            await self.edit_message_text(chat_id, message_id, text, reply_markup={"inline_keyboard": fac_buttons})
            return

        # STEP 2 -> STEP 3: Faculty Selected -> Choose Group
        if data.startswith("reg_fac:"):
            _, fac = data.split(":")
            state["faculty"] = fac
            state["step"] = "SELECT_GROUP"
            year_code = state.get("year_code", "26")

            # Fetch all groups from backend
            all_groups = await self.api_get("groups/") or []
            group_names = [g["group_name"] for g in all_groups if "group_name" in g]

            # Filter groups matching faculty and year code
            matched_groups = []
            for g in group_names:
                if year_code in g:
                    if fac == "CIE" and g.startswith("CIE"):
                        matched_groups.append(g)
                    elif fac == "CSE" and (g.startswith("CSE") or g.startswith("CS")):
                        matched_groups.append(g)
                    elif fac == "ICE" and g.startswith("ICE"):
                        matched_groups.append(g)
                    elif fac == "AI" and (g.startswith("AI") or g.startswith("DS")):
                        matched_groups.append(g)
                    elif fac == "BM" and g.startswith("BM"):
                        matched_groups.append(g)
                    elif fac == "SBL" and g.startswith("SBL"):
                        matched_groups.append(g)

            # Fallback to all groups for this year if specific filter yielded 0
            if not matched_groups:
                matched_groups = [g for g in group_names if year_code in g]

            matched_groups.sort(key=natural_sort_key)

            # Build inline buttons (2 or 3 per row)
            chunk_size = 3 if len(matched_groups) > 12 else 2
            buttons = []
            for row in chunk_list(matched_groups, chunk_size):
                buttons.append([{"text": g_name, "callback_data": f"reg_grp:{g_name}"} for g_name in row])

            text = (
                f"🏫 <b>{fac} (Year {state.get('year_of_study', 1)})</b> selected.\n\n"
                f"<b>Step 3/3:</b> Choose your <b>Academic Group</b>:"
            )
            await self.edit_message_text(chat_id, message_id, text, reply_markup={"inline_keyboard": buttons})
            return

        # STEP 3 -> Finish Registration & Connect Lessons
        if data.startswith("reg_grp:"):
            _, chosen_group = data.split(":", 1)
            candidate_id = state.get("student_id")
            first_name = state.get("first_name", "")
            last_name = state.get("last_name", "")
            full_name = f"{first_name} {last_name}".strip() or f"Student {candidate_id}"
            year_of_study = state.get("year_of_study", 1)
            username = state.get("username", "")

            # Call backend to register student and enroll all group courses
            reg_payload = {
                "student_id": candidate_id,
                "full_name": full_name,
                "group_name": chosen_group,
                "year_of_study": year_of_study,
                "telegram_id": tg_id,
                "telegram_username": username
            }

            res = await self.api_post("students/register/", reg_payload)
            self.user_states.pop(tg_id, None)

            if res and res.get("success"):
                enrolled_count = res.get("enrolled_count", 0)
                celebration_msg = (
                    f"🎉 <b>Registration Complete!</b>\n\n"
                    f"Welcome, <b>{full_name}</b>!\n"
                    f"🎓 <b>Student ID:</b> <code>{candidate_id}</code>\n"
                    f"👥 <b>Group:</b> {chosen_group}\n"
                    f"📚 Connected to all <b>{enrolled_count}</b> classes for this semester.\n\n"
                    f"Tap <b>📅 Timetable</b> below to view your full schedule and photo, "
                    f"or open <b>INS Grades</b> from the bottom menu."
                )
                await self.edit_message_text(chat_id, message_id, f"✅ Registered as <b>{chosen_group}</b>.")
                await self.send_message(chat_id, celebration_msg, reply_markup=MAIN_MENU_KEYBOARD)
            else:
                err_msg = res.get("error", "Unknown error occurred") if res else "Connection error"
                await self.send_message(chat_id, f"❌ Registration failed: {err_msg}. Please send /start to retry.")

    async def handle_timetable(self, chat_id: int, tg_id: int):
        """
        Sends the official timetable photo to the student,
        and directly underneath sends the full weekly schedule.
        """
        students = await self.api_get(f"students/?telegram_id={tg_id}")
        if not students or len(students) == 0:
            await self.send_message(chat_id, "⚠️ Your account is not connected yet. Please reply with your Student ID first.")
            return

        student = students[0]
        group_name = student.get("group_name", "your group")

        tt_data = await self.api_get(f"timetable/student/{student['student_id']}/")
        image_url = None
        if tt_data:
            image_url = tt_data.get("timetable_image_url")
        if not image_url:
            image_url = student.get("timetable_image_url")

        # Normalize to S3 bucket URL
        sanitized_grp = re.sub(r'[^A-Za-z0-9_-]', '_', group_name) if group_name else "group"
        if not image_url or image_url.startswith("/static/") or not image_url.startswith("http"):
            image_url = f"{S3_ENDPOINT_URL}/{S3_BUCKET_NAME}/timetables/{sanitized_grp}.png"

        # 1. Send the Timetable Screenshot
        caption = (
            f"🖼 <b>Official Timetable Screenshot</b>\n\n"
            f"👥 <b>Group:</b> {group_name}\n"
            f"🎓 <b>Student:</b> {student['full_name']} (<code>{student['student_id']}</code>)"
        )
        res = await self.send_photo(chat_id, image_url, caption=caption)
        if not res or not res.get("ok"):
            await self.send_message(
                chat_id,
                f"🖼 <b>Timetable Photo Link:</b>\n<a href=\"{image_url}\">Open Full-Resolution Image</a>"
            )

        # 2. Directly below image: Send the Full Weekly Timetable
        slots = tt_data.get("timetable", []) if tt_data else []
        lines = [f"🗓 <b>Full Weekly Schedule for {student['full_name']} ({group_name})</b>\n"]
        has_any_slots = False

        for day_num in range(1, 7):  # Monday through Saturday
            day_slots = [s for s in slots if s.get("day_of_week") == day_num]
            if day_slots:
                has_any_slots = True
                day_title = DAY_NAMES.get(day_num, f"Day {day_num}")
                lines.append(f"<b>{day_title}:</b>")
                for s in day_slots:
                    room = s.get("room") or "TBA"
                    prof = s.get("professor")
                    prof_str = f" | 👨‍🏫 {prof}" if prof else ""
                    lines.append(f"  • <b>{s['start_time']} - {s['end_time']}</b>: {s['subject_short']} (Room: <b>{room}</b>){prof_str}")
                lines.append("")

        if not has_any_slots:
            lines.append("ℹ️ No active timetable slots found for your group.")

        await self.send_message(chat_id, "\n".join(lines), reply_markup=MAIN_MENU_KEYBOARD)

    async def handle_today(self, chat_id: int, tg_id: int):
        """Send today's schedule to the student."""
        students = await self.api_get(f"students/?telegram_id={tg_id}")
        if not students or len(students) == 0:
            await self.send_message(chat_id, "⚠️ Your account is not connected yet. Please reply with your Student ID first.")
            return

        student = students[0]
        tt_data = await self.api_get(f"timetable/student/{student['student_id']}/")
        if not tt_data or "timetable" not in tt_data:
            await self.send_message(chat_id, "⚠️ No timetable found for your account.")
            return

        # Python weekday: Mon=0 ... Sun=6 -> Map to 1..7
        current_day = datetime.now().weekday() + 1
        today_name = DAY_NAMES.get(current_day, "Today")

        if current_day == 7:
            await self.send_message(chat_id, "🎉 <b>No classes on Sunday!</b> Enjoy your weekend.", reply_markup=MAIN_MENU_KEYBOARD)
            return

        slots = [s for s in tt_data["timetable"] if s.get("day_of_week") == current_day]
        if not slots:
            await self.send_message(chat_id, f"🎉 <b>No classes scheduled for {today_name}!</b> Enjoy your free day.", reply_markup=MAIN_MENU_KEYBOARD)
            return

        lines = [f"📅 <b>Today's Schedule ({today_name}) - {student['group_name']}</b>\n"]
        for s in slots:
            room = s.get("room") or "TBA"
            prof = s.get("professor")
            prof_str = f" | 👨‍🏫 {prof}" if prof else ""
            lines.append(
                f"🕒 <b>{s['start_time']} - {s['end_time']}</b>\n"
                f"📖 {s['subject']} ({s['subject_short']})\n"
                f"🚪 Room: <b>{room}</b>{prof_str}\n"
            )

        await self.send_message(chat_id, "\n".join(lines), reply_markup=MAIN_MENU_KEYBOARD)

    async def run_polling(self):
        """Main Telegram updates polling loop."""
        offset = 0
        logger.info("[TelegramBot] Initializing chat menu button...")
        await self.setup_chat_menu_button()

        logger.info("[TelegramBot] Polling loop started...")
        while self.is_running:
            try:
                url = f"{self.tg_base}/getUpdates?offset={offset}&timeout=20"
                res = await self.client.get(url, timeout=25.0)
                data = res.json()

                if data.get("ok"):
                    for update in data.get("result", []):
                        offset = update["update_id"] + 1

                        if "message" in update or "edited_message" in update:
                            msg = update.get("message") or update.get("edited_message")
                            if not msg:
                                continue
                            chat_id = msg["chat"]["id"]
                            user = msg.get("from", {})
                            text = msg.get("text", "")
                            if text:
                                await self.handle_text(chat_id, user, text)

                        elif "callback_query" in update:
                            await self.handle_callback_query(update["callback_query"])

                elif data.get("error_code") == 409:
                    logger.warning("[TelegramBot] 409 Conflict (another instance running). Backing off for 15s...")
                    await asyncio.sleep(15)
                else:
                    logger.debug(f"[TelegramBot] Response: {data}")
                    await asyncio.sleep(2)
            except Exception as e:
                logger.error(f"[TelegramBot] Polling error: {e}")
                await asyncio.sleep(5)


async def main():
    if not BOT_TOKEN:
        logger.warning("[TelegramBot] TELEGRAM_BOT_TOKEN not provided. Bot is idling.")
        while True:
            await asyncio.sleep(60)

    bot = TimetableTelegramBot(BOT_TOKEN, API_URL)
    await bot.run_polling()


if __name__ == "__main__":
    asyncio.run(main())

import os
import sys
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


class TimetableTelegramBot:
    def __init__(self, token: str, api_url: str):
        self.token = token
        self.api_url = api_url
        self.tg_base = f"https://api.telegram.org/bot{token}"
        self.client = httpx.AsyncClient(timeout=30.0)
        self.is_running = True

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
        """Handle /start command."""
        tg_id = user.get("id")
        first_name = user.get("first_name", "Student")

        # Check if already linked
        student_data = await self.api_get(f"students/?telegram_id={tg_id}")
        linked = student_data and len(student_data) > 0

        if linked:
            s = student_data[0]
            msg = (
                f"👋 Welcome back, <b>{s['full_name']}</b>!\n\n"
                f"🎓 <b>Student ID:</b> <code>{s['student_id']}</code>\n"
                f"👥 <b>Group:</b> {s.get('group_name', 'Assigned')}\n\n"
                f"Commands:\n"
                f"📅 /today - Today's Schedule\n"
                f"🗓 /week - Full Week Timetable\n"
                f"🖼 /image - Official Timetable Photo\n"
                f"📝 /homework - Pending Assignments\n"
                f"📊 /attendance - Absences & Status\n"
            )
        else:
            msg = (
                f"👋 Hello, <b>{first_name}</b>!\n\n"
                f"Welcome to the <b>INS Grades University Bot</b>.\n\n"
                f"To view your personalized timetable and receive lecture reminders, "
                f"please reply with your <b>Student ID</b> (e.g. <code>U2110001</code>)."
            )

        reply_markup = {
            "inline_keyboard": [
                [{"text": "📱 Open University WebApp", "web_app": {"url": APP_URL}}]
            ]
        } if APP_URL else None

        await self.send_message(chat_id, msg, reply_markup=reply_markup)

    async def handle_text(self, chat_id: int, user: dict, text: str):
        """Handle text input from user."""
        text = text.strip()
        tg_id = user.get("id")
        username = user.get("username", "")

        if text.startswith("/"):
            cmd = text.lower().split()[0]
            if cmd in ("/start", "/help"):
                await self.handle_start(chat_id, user)
            elif cmd == "/today":
                await self.handle_today(chat_id, tg_id)
            elif cmd in ("/week", "/schedule"):
                await self.handle_week(chat_id, tg_id)
            elif cmd in ("/image", "/photo", "/timetable_photo"):
                await self.handle_photo(chat_id, tg_id)
            elif cmd == "/homework":
                await self.handle_homework(chat_id, tg_id)
            elif cmd == "/attendance":
                await self.handle_attendance(chat_id, tg_id)
            else:
                await self.send_message(chat_id, "Unknown command. Use /today, /week, /image, /homework, or /attendance.")
            return

        # Attempt to link student ID
        student_id_candidate = text.upper()
        res = await self.api_post("students/link-telegram/", {
            "student_id": student_id_candidate,
            "telegram_id": tg_id,
            "telegram_username": username
        })

        if res and ("student" in res or res.get("success")):
            s = res.get("student") or res
            msg = (
                f"✅ <b>Successfully Linked!</b>\n\n"
                f"Welcome, <b>{s['full_name']}</b>!\n"
                f"Student ID: <code>{s['student_id']}</code>\n"
                f"Group: {s.get('group_name', 'Assigned')}\n\n"
                f"You will now receive automated 30-minute notifications before each lecture.\n\n"
                f"Try /today or /week to check your schedule."
            )
            await self.send_message(chat_id, msg)
        else:
            await self.send_message(
                chat_id,
                f"❌ Could not find a student with ID <code>{student_id_candidate}</code>.\n"
                f"Please verify your Student ID and try again, or check the WebApp."
            )

    async def handle_today(self, chat_id: int, tg_id: int):
        """Send today's schedule to the student."""
        students = await self.api_get(f"students/?telegram_id={tg_id}")
        if not students or len(students) == 0:
            await self.send_message(chat_id, "⚠️ Your account is not linked. Please send your Student ID first.")
            return

        student = students[0]
        tt_data = await self.api_get(f"timetable/student/{student['student_id']}/")
        if not tt_data or "timetable" not in tt_data:
            await self.send_message(chat_id, "⚠️ No timetable found for your account.")
            return

        # Python weekday: Mon=0, Sun=6 -> Map to 1..7
        current_day = datetime.now().weekday() + 1
        today_name = DAY_NAMES.get(current_day, "Today")

        slots = [s for s in tt_data["timetable"] if s.get("day_of_week") == current_day]

        if not slots:
            await self.send_message(chat_id, f"🎉 <b>No classes scheduled for {today_name}!</b> Enjoy your free day.")
            return

        lines = [f"📅 <b>Today's Schedule ({today_name})</b>\n"]
        for s in slots:
            lines.append(
                f"🕒 <b>{s['start_time']} - {s['end_time']}</b>\n"
                f"📖 {s['subject']} ({s['subject_short']})\n"
                f"🚪 Room: <b>{s['room'] or 'TBA'}</b> | 👨‍🏫 {s['professor']}\n"
            )

        await self.send_message(chat_id, "\n".join(lines))

    async def handle_week(self, chat_id: int, tg_id: int):
        """Send weekly timetable overview."""
        students = await self.api_get(f"students/?telegram_id={tg_id}")
        if not students or len(students) == 0:
            await self.send_message(chat_id, "⚠️ Your account is not linked. Please send your Student ID first.")
            return

        student = students[0]
        tt_data = await self.api_get(f"timetable/student/{student['student_id']}/")
        if not tt_data or "timetable" not in tt_data:
            await self.send_message(chat_id, "⚠️ No timetable found.")
            return

        lines = [f"🗓 <b>Weekly Schedule for {student['full_name']}</b>\n"]
        for day_num in range(1, 7):
            day_slots = [s for s in tt_data["timetable"] if s.get("day_of_week") == day_num]
            if day_slots:
                lines.append(f"<b>{DAY_NAMES.get(day_num)}:</b>")
                for s in day_slots:
                    lines.append(f"  • {s['start_time']}-{s['end_time']}: {s['subject_short']} ({s['room']})")
                lines.append("")

        await self.send_message(chat_id, "\n".join(lines))

    async def handle_photo(self, chat_id: int, tg_id: int):
        """Send the official group timetable screenshot to the student."""
        students = await self.api_get(f"students/?telegram_id={tg_id}")
        if not students or len(students) == 0:
            await self.send_message(chat_id, "⚠️ Your account is not linked. Please send your Student ID first.")
            return

        student = students[0]
        group_name = student.get("group_name", "your group")
        image_url = student.get("timetable_image_url")

        if not image_url:
            tt_data = await self.api_get(f"timetable/student/{student['student_id']}/")
            if tt_data:
                image_url = tt_data.get("timetable_image_url")

        # Convert legacy /static/ path to direct S3 URL or infer from group_name
        if image_url and (image_url.startswith("/static/") or not image_url.startswith("http")):
            filename = os.path.basename(image_url)
            image_url = f"{S3_ENDPOINT_URL}/{S3_BUCKET_NAME}/timetables/{filename}"
        elif not image_url and group_name and group_name != "your group":
            import re
            sanitized = re.sub(r'[^A-Za-z0-9_-]', '_', group_name)
            image_url = f"{S3_ENDPOINT_URL}/{S3_BUCKET_NAME}/timetables/{sanitized}.png"

        if not image_url:
            await self.send_message(
                chat_id,
                f"ℹ️ No official timetable photo is currently linked for group <b>{group_name}</b>.\n"
                f"The image will be uploaded automatically during the next timetable synchronization run."
            )
            return

        caption = (
            f"🖼 <b>Official Timetable Screenshot</b>\n\n"
            f"👥 <b>Group:</b> {group_name}\n"
            f"🎓 <b>Student:</b> {student['full_name']} (<code>{student['student_id']}</code>)"
        )
        res = await self.send_photo(chat_id, image_url, caption=caption)
        if not res or not res.get("ok"):
            await self.send_message(
                chat_id,
                f"⚠️ Unable to send image preview directly. You can view it here:\n<a href=\"{image_url}\">Open Timetable Photo</a>"
            )

    async def handle_homework(self, chat_id: int, tg_id: int):
        """Send homework status."""
        students = await self.api_get(f"students/?telegram_id={tg_id}")
        if not students or len(students) == 0:
            await self.send_message(chat_id, "⚠️ Please link your Student ID first.")
            return

        student = students[0]
        hw_list = await self.api_get(f"homework/student/{student['student_id']}/")
        if not hw_list:
            await self.send_message(chat_id, "✅ No active homework assignments found.")
            return

        lines = ["📝 <b>Homework Assignments:</b>\n"]
        for hw in hw_list:
            status_emoji = "✅" if hw.get("is_done") else "⏳"
            lines.append(
                f"{status_emoji} <b>{hw['title']}</b> ({hw['subject_short']})\n"
                f"⏰ Deadline: {hw['deadline']}\n"
            )

        await self.send_message(chat_id, "\n".join(lines))

    async def handle_attendance(self, chat_id: int, tg_id: int):
        """Send attendance summary."""
        students = await self.api_get(f"students/?telegram_id={tg_id}")
        if not students or len(students) == 0:
            await self.send_message(chat_id, "⚠️ Please link your Student ID first.")
            return

        student = students[0]
        att = await self.api_get(f"attendance/student/{student['student_id']}/")
        if not att or "summary" not in att:
            await self.send_message(chat_id, "📊 No attendance records found.")
            return

        s = att["summary"]
        warning = "\n⚠️ <b>Warning:</b> Absence threshold reached!" if s["absent"] >= 3 else ""
        msg = (
            f"📊 <b>Attendance Summary</b>\n\n"
            f"Student: <b>{student['full_name']}</b>\n"
            f"❌ Unexcused Absences: <b>{s['absent']}</b>\n"
            f"✅ Present Lectures: <b>{s['present']}</b>\n"
            f"📋 Excused Absences: <b>{s['excused']}</b>"
            f"{warning}"
        )
        await self.send_message(chat_id, msg)

    async def run_polling(self):
        """Main Telegram updates polling loop."""
        offset = 0
        logger.info("[TelegramBot] Polling loop started...")
        while self.is_running:
            try:
                url = f"{self.tg_base}/getUpdates?offset={offset}&timeout=20"
                res = await self.client.get(url, timeout=25.0)
                data = res.json()

                if data.get("ok"):
                    for update in data.get("result", []):
                        offset = update["update_id"] + 1
                        msg = update.get("message") or update.get("edited_message")
                        if not msg:
                            continue
                        chat_id = msg["chat"]["id"]
                        user = msg.get("from", {})
                        text = msg.get("text", "")

                        if text:
                            await self.handle_text(chat_id, user, text)
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

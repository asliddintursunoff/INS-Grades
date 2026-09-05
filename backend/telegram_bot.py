import os
import asyncio
import logging
import httpx
from datetime import datetime
from typing import Optional, Dict, Any
from database import query, execute
from services.timetable_service import get_effective_schedule, DAY_NAMES
from services.enrollment_service import get_student_classes
from services.attendance_service import get_student_absences
from services.notification_service import get_upcoming_sessions_for_scheduler, mark_notification_sent

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("telegram_bot")

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "7963381665:AAFljS3q8j5GvFp-7u2vK5Dq5f5mBqW9X5A")
APP_URL = os.getenv("APP_URL", "https://ins-grades.vercel.app")

class TelegramBot:
    def __init__(self, token: str, app_url: str):
        self.token = token
        self.app_url = app_url.rstrip("/")
        self.api_url = f"https://api.telegram.org/bot{self.token}"
        self.offset = 0
        self.is_running = False
        self.client: Optional[httpx.AsyncClient] = None

    async def call_api(self, method: str, json_data: Dict[str, Any] = None) -> Dict[str, Any]:
        if not self.client:
            self.client = httpx.AsyncClient(timeout=35.0)
        try:
            resp = await self.client.post(f"{self.api_url}/{method}", json=json_data or {})
            return resp.json()
        except Exception as e:
            logger.warning(f"Telegram API call error {method}: {e}")
            return {"ok": False, "error": str(e)}

    def get_keyboard(self):
        return {
            "keyboard": [
                [
                    {"text": "📱 Open INS grades", "web_app": {"url": self.app_url}},
                    {"text": "📅 Today"},
                ],
                [
                    {"text": "📆 Full Week"},
                    {"text": "🔄 Make-up Slot"},
                ],
                [
                    {"text": "👤 My Profile"},
                    {"text": "🔔 Reminders"},
                ]
            ],
            "resize_keyboard": True,
            "persistent": True
        }

    async def send_message(self, chat_id: int, text: str, reply_markup: Any = None):
        payload = {
            "chat_id": chat_id,
            "text": text,
            "parse_mode": "HTML",
        }
        if reply_markup:
            payload["reply_markup"] = reply_markup
        await self.call_api("sendMessage", payload)

    async def set_menu_button(self):
        if self.app_url:
            await self.call_api("setChatMenuButton", {
                "menu_button": {
                    "type": "web_app",
                    "text": "📱 INS grades App",
                    "web_app": {"url": self.app_url}
                }
            })

    async def handle_start(self, chat_id: int, user: Dict[str, Any]):
        tg_id = user.get("id")
        username = user.get("username", "")
        first_name = user.get("first_name", "Student")

        students = query("SELECT s.*, g.group_name FROM students s JOIN groups g ON s.group_id = g.group_id WHERE s.telegram_id = ?", (tg_id,))
        if students:
            student = students[0]
            msg = (
                f"👋 <b>Welcome back, {student['full_name']}!</b>\n\n"
                f"🎓 <b>Student ID:</b> <code>{student['student_id']}</code>\n"
                f"👥 <b>Group:</b> {student['group_name']}\n\n"
                f"Tap below to launch your <b>INS grades Mini App</b> to check timetable, attendances, and drop/retake courses."
            )
            inline_kb = {
                "inline_keyboard": [
                    [{"text": "📱 Launch INS grades App", "web_app": {"url": self.app_url}}]
                ]
            }
            await self.send_message(chat_id, msg, reply_markup=inline_kb)
        else:
            msg = (
                f"👋 <b>Hello, {first_name}! Welcome to INS grades!</b>\n\n"
                f"Your Telegram account is not yet connected to a Student ID.\n\n"
                f"📝 <b>Please enter your Student ID</b> (e.g. <code>U2410252</code>) directly in this chat, "
                f"or open the Web App below to login."
            )
            inline_kb = {
                "inline_keyboard": [
                    [{"text": "📱 Open INS grades Web App", "web_app": {"url": self.app_url}}]
                ]
            }
            await self.send_message(chat_id, msg, reply_markup=inline_kb)

        # Also send keyboard
        await self.send_message(chat_id, "Choose an option from the menu:", reply_markup=self.get_keyboard())

    async def handle_text(self, chat_id: int, user: Dict[str, Any], text: str):
        tg_id = user.get("id")
        username = user.get("username", "")
        clean_text = text.strip()

        # Check for Student ID link attempt (e.g. U2410252)
        if clean_text.upper().startswith("U2") and len(clean_text) >= 8:
            matched = query("SELECT s.*, g.group_name FROM students s JOIN groups g ON s.group_id = g.group_id WHERE UPPER(s.student_id) = UPPER(?)", (clean_text,))
            if matched:
                student = matched[0]
                execute(
                    "UPDATE students SET telegram_id = ?, telegram_username = ? WHERE student_id = ?",
                    (tg_id, username, student["student_id"])
                )
                msg = (
                    f"✅ <b>Successfully connected!</b>\n\n"
                    f"👤 <b>Name:</b> {student['full_name']}\n"
                    f"🎓 <b>ID:</b> {student['student_id']}\n"
                    f"👥 <b>Group:</b> {student['group_name']}\n\n"
                    f"You will now receive automatic class reminders and can manage your classes seamlessly."
                )
                inline_kb = {
                    "inline_keyboard": [
                        [{"text": "📱 Open INS grades", "web_app": {"url": self.app_url}}]
                    ]
                }
                await self.send_message(chat_id, msg, reply_markup=inline_kb)
                return
            else:
                await self.send_message(
                    chat_id,
                    f"❌ Student ID <code>{clean_text}</code> was not found in university records.\n"
                    f"Please contact admin: @asliddin_tursunoff"
                )
                return

        # Resolve student
        students = query("SELECT s.*, g.group_name FROM students s JOIN groups g ON s.group_id = g.group_id WHERE s.telegram_id = ?", (tg_id,))
        if not students:
            # Fallback for demo
            students = query("SELECT s.*, g.group_name FROM students s JOIN groups g ON s.group_id = g.group_id LIMIT 1")

        if not students:
            await self.send_message(chat_id, "Please link your Student ID first (e.g. <code>U2410252</code>).")
            return

        student = students[0]

        if clean_text in ["📅 Today", "/today"]:
            now = datetime.now()
            today_day = now.weekday() + 1
            sched = get_effective_schedule(student["student_id"])["schedule"]
            today_classes = [s for s in sched if s["day_of_week"] == today_day]

            if not today_classes:
                await self.send_message(chat_id, f"🎉 <b>No classes scheduled for today ({DAY_NAMES.get(today_day)})!</b> Enjoy your free day.")
                return

            lines = [f"📅 <b>Today's Schedule ({DAY_NAMES.get(today_day)}):</b>\n"]
            for idx, c in enumerate(today_classes, 1):
                note = f" <i>({c['make_up_note']})</i>" if c.get("make_up_note") else ""
                lines.append(
                    f"<b>{idx}. {c['start_time']} - {c['end_time']}</b> | {c['subject_short']}\n"
                    f"   📚 {c['subject_full']}\n"
                    f"   👨‍🏫 {c['professor']} • 🚪 Room: <b>{c['room']}</b>{note}\n"
                )
            await self.send_message(chat_id, "\n".join(lines))

        elif clean_text in ["📆 Full Week", "/schedule", "/timetable"]:
            sched = get_effective_schedule(student["student_id"])["schedule"]
            if not sched:
                await self.send_message(chat_id, "No scheduled classes found.")
                return

            lines = [f"📆 <b>Full Weekly Schedule for {student['full_name']} ({student['group_name']}):</b>\n"]
            current_day = None
            for c in sched:
                if c["day_of_week"] != current_day:
                    current_day = c["day_of_week"]
                    lines.append(f"\n📌 <b>{c['day_name'].upper()}</b>")
                lines.append(f"  • <b>{c['start_time']} - {c['end_time']}</b>: {c['subject_short']} ({c['room']}) - {c['professor']}")

            await self.send_message(chat_id, "\n".join(lines))

        elif clean_text in ["🔄 Make-up Slot", "/absences", "/makeup"]:
            absences = get_student_absences(student["student_id"])
            if not absences:
                await self.send_message(chat_id, "✅ <b>You have 0 unexcused absences!</b> Excellent attendance.")
                return

            lines = ["⚠️ <b>Your Absences eligible for Make-up:</b>\n"]
            for a in absences[:5]:
                lines.append(f"• <b>{a['subject_short']}</b>: {a['session_date']} ({a['start_time']}) - Room {a['room']}")
            lines.append("\nOpen the Mini App to view free parallel slots and select your make-up time!")
            inline_kb = {
                "inline_keyboard": [
                    [{"text": "🔄 Schedule Make-up in App", "web_app": {"url": self.app_url}}]
                ]
            }
            await self.send_message(chat_id, "\n".join(lines), reply_markup=inline_kb)

        elif clean_text in ["👤 My Profile", "/profile"]:
            classes = get_student_classes(student["student_id"])
            active_courses = [c for c in classes if c.get("status") == "active"]
            msg = (
                f"👤 <b>Student Profile:</b>\n\n"
                f"<b>Name:</b> {student['full_name']}\n"
                f"<b>ID:</b> <code>{student['student_id']}</code>\n"
                f"<b>Group:</b> {student['group_name']}\n"
                f"<b>Year:</b> Year {student.get('year_of_study', 2)}\n"
                f"<b>Active Courses:</b> {len(active_courses)} enrolled\n\n"
                f"👨‍💻 <b>Developer:</b> @asliddin_tursunoff"
            )
            await self.send_message(chat_id, msg)

        elif clean_text in ["🔔 Reminders", "/reminders"]:
            sett = query("SELECT enabled, minutes_before FROM notification_settings WHERE student_id = ?", (student["student_id"],))
            status = "ON 🟢" if (sett and sett[0]["enabled"]) else "OFF 🔴"
            mins = sett[0]["minutes_before"] if sett else 30
            msg = (
                f"🔔 <b>Notification Settings:</b>\n\n"
                f"Status: <b>{status}</b>\n"
                f"Notice window: <b>{mins} minutes</b> before class begins.\n\n"
                f"You can customize timing in the Web App settings."
            )
            await self.send_message(chat_id, msg)

        elif clean_text in ["/help", "help", "Help"]:
            msg = (
                "ℹ️ <b>INS grades Bot Help:</b>\n\n"
                "• /start - Welcome & Open Web App\n"
                "• /today - View today's classes\n"
                "• /schedule - View full weekly timetable\n"
                "• /absences - View missed lessons & make-ups\n"
                "• /profile - Student info and group\n"
                "• /reminders - Check notification status\n\n"
                "💡 <i>Tip: Tap the button below to open the interactive INS grades interface!</i>"
            )
            inline_kb = {
                "inline_keyboard": [
                    [{"text": "📱 Open INS grades", "web_app": {"url": self.app_url}}]
                ]
            }
            await self.send_message(chat_id, msg, reply_markup=inline_kb)

        else:
            await self.send_message(
                chat_id,
                f"Received: <i>{clean_text}</i>\nUse the buttons below or launch the Mini App:",
                reply_markup=self.get_keyboard()
            )

    async def poll_updates(self):
        logger.info("[TelegramBot] Polling loop started...")
        while self.is_running:
            try:
                res = await self.call_api("getUpdates", {
                    "offset": self.offset,
                    "timeout": 20,
                    "allowed_updates": ["message", "callback_query"]
                })
                if res.get("ok") and "result" in res:
                    for update in res["result"]:
                        self.offset = update["update_id"] + 1
                        msg = update.get("message")
                        if not msg:
                            continue
                        chat_id = msg["chat"]["id"]
                        user = msg.get("from", {})
                        text = msg.get("text", "").strip()

                        if text == "/start" or text.startswith("/start "):
                            await self.handle_start(chat_id, user)
                        elif text:
                            await self.handle_text(chat_id, user, text)
            except Exception as e:
                logger.error(f"[TelegramBot] Error in polling loop: {e}")
                await asyncio.sleep(3)

            await asyncio.sleep(0.5)

    async def check_upcoming_notifications(self):
        """Scheduler task to notify students before class starts."""
        while self.is_running:
            try:
                upcoming = get_upcoming_sessions_for_scheduler()
                for item in upcoming:
                    tg_id = item["telegram_id"]
                    msg = (
                        f"⏰ <b>Lesson Reminder!</b>\n\n"
                        f"📖 <b>{item['subject_full']}</b> ({item['subject_short']})\n"
                        f"🕒 Starts at: <b>{item['start_time']}</b> (in {item['minutes_left']} mins)\n"
                        f"🚪 Room: <b>{item['room']}</b>\n"
                        f"👨‍🏫 Professor: {item['professor']}\n\n"
                        f"Have a productive lecture!"
                    )
                    await self.send_message(tg_id, msg)
                    mark_notification_sent(tg_id, item["session_id"])
            except Exception as e:
                logger.error(f"[TelegramBot] Reminder check error: {e}")

            await asyncio.sleep(30)

    async def start(self):
        if not self.token or "MY_BOT_TOKEN" in self.token:
            logger.warning("[TelegramBot] TELEGRAM_BOT_TOKEN not configured. Bot paused.")
            return

        self.is_running = True
        logger.info(f"[TelegramBot] Bot starting with App URL: {self.app_url}")
        await self.set_menu_button()

        asyncio.create_task(self.poll_updates())
        asyncio.create_task(self.check_upcoming_notifications())

    async def stop(self):
        self.is_running = False
        if self.client:
            await self.client.aclose()

bot_instance = TelegramBot(BOT_TOKEN, APP_URL)

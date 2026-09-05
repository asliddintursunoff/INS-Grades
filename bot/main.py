import os
import asyncio
import logging
import httpx
from datetime import datetime
from typing import Optional, Dict, Any
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("ins_grades_bot")

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "7963381665:AAFljS3q8j5GvFp-7u2vK5Dq5f5mBqW9X5A")
API_URL = os.getenv("API_URL", "http://localhost:3000").rstrip("/")
INTERNAL_KEY = os.getenv("INTERNAL_KEY", "ins_secret_internal_key_2025")
APP_URL = os.getenv("APP_URL", "https://ins-grades.vercel.app").rstrip("/")

class StandaloneTelegramBot:
    def __init__(self, token: str, api_url: str, app_url: str, internal_key: str):
        self.token = token
        self.api_url = api_url
        self.app_url = app_url
        self.internal_key = internal_key
        self.tg_url = f"https://api.telegram.org/bot{self.token}"
        self.offset = 0
        self.is_running = False
        self.client: Optional[httpx.AsyncClient] = None

    async def call_tg(self, method: str, data: Dict[str, Any] = None) -> Dict[str, Any]:
        if not self.client:
            self.client = httpx.AsyncClient(timeout=35.0)
        try:
            resp = await self.client.post(f"{self.tg_url}/{method}", json=data or {})
            return resp.json()
        except Exception as e:
            logger.warning(f"Telegram API call error {method}: {e}")
            return {"ok": False, "error": str(e)}

    async def api_get(self, endpoint: str) -> Optional[Dict[str, Any]]:
        headers = {"X-Internal-Key": self.internal_key}
        try:
            async with httpx.AsyncClient(timeout=15.0) as http:
                resp = await http.get(f"{self.api_url}{endpoint}", headers=headers)
                if resp.status_code == 200:
                    return resp.json()
        except Exception as e:
            logger.error(f"Backend API GET error {endpoint}: {e}")
        return None

    async def api_post(self, endpoint: str, body: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        headers = {"X-Internal-Key": self.internal_key}
        try:
            async with httpx.AsyncClient(timeout=15.0) as http:
                resp = await http.post(f"{self.api_url}{endpoint}", json=body, headers=headers)
                if resp.status_code == 200:
                    return resp.json()
        except Exception as e:
            logger.error(f"Backend API POST error {endpoint}: {e}")
        return None

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
        await self.call_tg("sendMessage", payload)

    async def set_menu_button(self):
        if self.app_url:
            await self.call_tg("setChatMenuButton", {
                "menu_button": {
                    "type": "web_app",
                    "text": "📱 INS grades App",
                    "web_app": {"url": self.app_url}
                }
            })

    async def handle_start(self, chat_id: int, user: Dict[str, Any]):
        tg_id = user.get("id")
        first_name = user.get("first_name", "Student")

        me_data = await self.api_get(f"/api/auth/me/{tg_id}")
        if me_data and me_data.get("found"):
            st = me_data["student"]
            msg = (
                f"👋 <b>Welcome back, {st['full_name']}!</b>\n\n"
                f"🎓 <b>Student ID:</b> <code>{st['student_id']}</code>\n"
                f"👥 <b>Group:</b> {st['group_name']}\n\n"
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

        await self.send_message(chat_id, "Choose an option from the menu:", reply_markup=self.get_keyboard())

    async def handle_text(self, chat_id: int, user: Dict[str, Any], text: str):
        tg_id = user.get("id")
        username = user.get("username", "")
        clean_text = text.strip()

        # Link account
        if clean_text.upper().startswith("U2") and len(clean_text) >= 8:
            link_res = await self.api_post("/api/auth/link", {
                "student_id": clean_text,
                "telegram_id": tg_id,
                "telegram_username": username
            })
            if link_res and link_res.get("success"):
                msg = (
                    f"✅ <b>Successfully connected!</b>\n\n"
                    f"👤 <b>Name:</b> {link_res['full_name']}\n"
                    f"🎓 <b>ID:</b> {link_res['student_id']}\n"
                    f"👥 <b>Group:</b> {link_res['group_name']}\n\n"
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

        if clean_text in ["📅 Today", "/today"]:
            data = await self.api_get(f"/api/students/{tg_id}/timetable/")
            if not data or "schedule" not in data:
                await self.send_message(chat_id, "Could not fetch schedule. Please verify your Student ID link.")
                return

            now = datetime.now()
            today_day = now.weekday() + 1
            today_classes = [s for s in data["schedule"] if s.get("day_of_week") == today_day]
            if not today_classes:
                await self.send_message(chat_id, "🎉 <b>No classes scheduled for today!</b> Enjoy your free day.")
                return

            lines = [f"📅 <b>Today's Schedule:</b>\n"]
            for idx, c in enumerate(today_classes, 1):
                note = f" <i>({c['make_up_note']})</i>" if c.get("make_up_note") else ""
                lines.append(
                    f"<b>{idx}. {c['start_time']} - {c['end_time']}</b> | {c['subject_short']}\n"
                    f"   📚 {c['subject_full']}\n"
                    f"   👨‍🏫 {c['professor']} • 🚪 Room: <b>{c['room']}</b>{note}\n"
                )
            await self.send_message(chat_id, "\n".join(lines))

        elif clean_text in ["📆 Full Week", "/schedule", "/timetable"]:
            data = await self.api_get(f"/api/students/{tg_id}/timetable/")
            if not data or "schedule" not in data:
                await self.send_message(chat_id, "Could not fetch timetable.")
                return

            sched = data["schedule"]
            lines = [f"📆 <b>Full Weekly Schedule for {data.get('student_name', '')} ({data.get('group_name', '')}):</b>\n"]
            current_day = None
            for c in sched:
                if c["day_of_week"] != current_day:
                    current_day = c["day_of_week"]
                    lines.append(f"\n📌 <b>{c['day_name'].upper()}</b>")
                lines.append(f"  • <b>{c['start_time']} - {c['end_time']}</b>: {c['subject_short']} ({c['room']}) - {c['professor']}")

            await self.send_message(chat_id, "\n".join(lines))

        elif clean_text in ["🔄 Make-up Slot", "/absences", "/makeup"]:
            data = await self.api_get(f"/api/students/{tg_id}/absences/")
            absences = data.get("absences", []) if data else []
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
            me_data = await self.api_get(f"/api/auth/me/{tg_id}")
            if me_data and me_data.get("found"):
                st = me_data["student"]
                msg = (
                    f"👤 <b>Student Profile:</b>\n\n"
                    f"<b>Name:</b> {st['full_name']}\n"
                    f"<b>ID:</b> <code>{st['student_id']}</code>\n"
                    f"<b>Group:</b> {st['group_name']}\n"
                    f"<b>Year:</b> Year {st.get('year_of_study', 2)}\n\n"
                    f"👨‍💻 <b>Developer:</b> @asliddin_tursunoff"
                )
                await self.send_message(chat_id, msg)
            else:
                await self.send_message(chat_id, "Please link your Student ID first (e.g. <code>U2410252</code>).")

        elif clean_text in ["🔔 Reminders", "/reminders"]:
            data = await self.api_get(f"/api/students/{tg_id}/notification-settings/")
            if data:
                status = "ON 🟢" if data.get("enabled") else "OFF 🔴"
                mins = data.get("minutes_before", 30)
                msg = (
                    f"🔔 <b>Notification Settings:</b>\n\n"
                    f"Status: <b>{status}</b>\n"
                    f"Notice window: <b>{mins} minutes</b> before class begins.\n\n"
                    f"You can customize timing in the Web App settings."
                )
                await self.send_message(chat_id, msg)
            else:
                await self.send_message(chat_id, "Could not fetch reminder settings.")

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
        logger.info("[TelegramBot Worker] Starting update polling loop...")
        while self.is_running:
            try:
                res = await self.call_tg("getUpdates", {
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
                logger.error(f"Error in poll_updates: {e}")
                await asyncio.sleep(3)

            await asyncio.sleep(0.5)

    async def run(self):
        if not self.token or "MY_BOT_TOKEN" in self.token:
            logger.warning("TELEGRAM_BOT_TOKEN not provided. Worker paused.")
            return

        self.is_running = True
        logger.info(f"Bot worker started. Backend API: {self.api_url}, App: {self.app_url}")
        await self.set_menu_button()
        await self.poll_updates()

async def main():
    bot = StandaloneTelegramBot(BOT_TOKEN, API_URL, APP_URL, INTERNAL_KEY)
    await bot.run()

if __name__ == "__main__":
    asyncio.run(main())

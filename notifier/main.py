import os
import sys
import time
import signal
import asyncio
import logging
from datetime import datetime, timezone, timedelta

try:
    from zoneinfo import ZoneInfo
except ImportError:
    ZoneInfo = None

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
    format="%(asctime)s [%(levelname)s] [Notifier]: %(message)s"
)
logger = logging.getLogger("ClassNotifier")

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
API_URL = (os.getenv("API_URL") or "http://backend:3000").rstrip("/")
API_KEY = os.getenv("API_KEY", "ins_secure_api_key_2026_x89a")


def get_tashkent_now():
    """Returns current datetime in Asia/Tashkent timezone."""
    if ZoneInfo:
        try:
            return datetime.now(ZoneInfo("Asia/Tashkent"))
        except Exception:
            pass
    return datetime.now(timezone(timedelta(hours=5)))


class ClassReminderNotifier:
    def __init__(self, bot_token: str, api_url: str, api_key: str):
        self.bot_token = bot_token
        self.api_url = api_url
        self.api_key = api_key
        self.client = httpx.AsyncClient(timeout=20.0)
        self.is_running = True

    async def api_get(self, endpoint: str):
        """Calls Django backend API with auth key."""
        url = f"{self.api_url}/api/{endpoint.lstrip('/')}"
        headers = {"X-API-KEY": self.api_key}
        try:
            r = await self.client.get(url, headers=headers, timeout=10.0)
            if r.status_code == 200:
                return r.json()
            logger.warning(f"Backend GET {url} returned HTTP {r.status_code}: {r.text[:150]}")
            return None
        except Exception as e:
            logger.error(f"Failed to reach backend at {url}: {e}")
            return None

    async def api_post(self, endpoint: str, data: dict):
        """Calls Django backend API POST with auth key."""
        url = f"{self.api_url}/api/{endpoint.lstrip('/')}"
        headers = {"X-API-KEY": self.api_key}
        try:
            r = await self.client.post(url, json=data, headers=headers, timeout=10.0)
            return r.status_code == 200
        except Exception as e:
            logger.error(f"Failed to post backend at {url}: {e}")
            return False

    async def send_telegram_message(self, chat_id: int, text: str):
        """Sends an HTML formatted message to Telegram user."""
        if not self.bot_token:
            logger.error("TELEGRAM_BOT_TOKEN is not configured.")
            return False

        url = f"https://api.telegram.org/bot{self.bot_token}/sendMessage"
        payload = {
            "chat_id": chat_id,
            "text": text,
            "parse_mode": "HTML",
            "disable_web_page_preview": True,
        }
        try:
            r = await self.client.post(url, json=payload, timeout=10.0)
            res = r.json()
            if res.get("ok"):
                return True
            logger.warning(f"Telegram sendMessage failed for chat_id={chat_id}: {res.get('description')}")
            return False
        except Exception as e:
            logger.error(f"Error sending Telegram message to {chat_id}: {e}")
            return False

    def format_reminder_message(self, alert: dict) -> str:
        """Constructs an aesthetic, crystal-clear notification message."""
        minutes_left = alert.get("minutes_left", 15)
        if minutes_left <= 0:
            time_phrase = "starting now"
        elif minutes_left == 1:
            time_phrase = "starts in 1 minute"
        else:
            time_phrase = f"starts in {minutes_left} minutes"

        is_makeup = alert.get("is_one_time", False)
        makeup_badge = "⚡ <b>One-Time Make-Up Lecture (This week only)</b>\n" if is_makeup else ""

        subject_full = alert.get("subject_full") or "Lecture"
        subject_short = alert.get("subject_short") or ""
        professor = alert.get("professor") or "TBA"
        start_time = alert.get("start_time") or ""
        end_time = alert.get("end_time") or ""
        room = alert.get("room") or "TBA"
        group = alert.get("actual_group") or ""

        return (
            f"🔔 <b>Class Starting Soon!</b>\n\n"
            f"{makeup_badge}"
            f"📚 <b>{subject_full}</b> (<code>{subject_short}</code>)\n"
            f"👨‍🏫 <b>Professor:</b> {professor}\n"
            f"⏰ <b>Time:</b> {start_time} - {end_time} (<b>{time_phrase}</b>)\n"
            f"📍 <b>Room:</b> <code>{room}</code>\n"
            f"👥 <b>Section:</b> {group}\n\n"
            f"<i>Have a great lecture! 🎓</i>"
        )

    async def process_pending_alerts(self):
        """Polls backend for alerts due right now and dispatches them."""
        data = await self.api_get("notifications/pending-alerts/")
        if not data or not isinstance(data.get("alerts"), list):
            return

        alerts = data["alerts"]
        if not alerts:
            return

        logger.info(f"Discovered {len(alerts)} pending class reminder(s) to dispatch.")

        for alert in alerts:
            tg_id = alert.get("telegram_id")
            if not tg_id:
                continue

            text = self.format_reminder_message(alert)
            success = await self.send_telegram_message(tg_id, text)

            if success:
                logger.info(
                    f"✓ Reminder delivered to student {alert.get('student_id')} "
                    f"({alert.get('subject_short')} at {alert.get('start_time')})"
                )
                await self.api_post("notifications/mark-sent/", {
                    "student_id": alert.get("student_id"),
                    "slot_key": alert.get("slot_key"),
                    "notification_date": alert.get("notification_date")
                })
            else:
                logger.warning(f"✗ Failed to deliver reminder to student {alert.get('student_id')}")

            # Telegram flood control safety
            await asyncio.sleep(0.05)

    async def run(self):
        """
        High-precision daemon loop with adaptive sleep:
          - During active lecture hours (07:30 to 20:30, Mon-Sat):
            Sleeps until exact top of the next minute (:00) for exact timing.
          - During nights (20:30 to 07:30) and Sundays:
            Sleeps in 10-minute blocks to minimize CPU and power usage.
        """
        logger.info("Class Reminder Notifier service started successfully.")
        logger.info(f"Target backend: {self.api_url}")

        while self.is_running:
            try:
                now = get_tashkent_now()
                current_day = now.isoweekday()  # 1=Mon ... 7=Sun
                current_hour = now.hour
                current_minute = now.minute

                # Adaptive Sleep Condition: Outside class hours
                is_sunday = (current_day == 7)
                is_night = (current_hour < 7 or (current_hour == 7 and current_minute < 30) or current_hour >= 21)

                if is_sunday or is_night:
                    sleep_duration = 600  # 10 minutes
                    reason = "Sunday off" if is_sunday else "Night hours (no classes)"
                    logger.debug(f"{reason}. Sleeping for {sleep_duration}s...")
                    await asyncio.sleep(sleep_duration)
                    continue

                # Active Lecture Hours: Check for pending alerts
                await self.process_pending_alerts()

                # High Precision Sleep: Sync with top of the next minute (:00)
                now_after = get_tashkent_now()
                sleep_seconds = 60.0 - now_after.second - (now_after.microsecond / 1_000_000.0)
                if sleep_seconds <= 0.05:
                    sleep_seconds = 60.0

                await asyncio.sleep(sleep_seconds)

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Unexpected error in notifier loop: {e}", exc_info=True)
                await asyncio.sleep(10)

        await self.client.aclose()
        logger.info("Class Reminder Notifier service stopped.")

    def stop(self):
        self.is_running = False


def main():
    notifier = ClassReminderNotifier(BOT_TOKEN, API_URL, API_KEY)

    def handle_signal(sig, frame):
        logger.info(f"Received termination signal {sig}. Shutting down gracefully...")
        notifier.stop()

    signal.signal(signal.SIGINT, handle_signal)
    signal.signal(signal.SIGTERM, handle_signal)

    try:
        asyncio.run(notifier.run())
    except (KeyboardInterrupt, SystemExit):
        pass


if __name__ == "__main__":
    main()

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
API_KEY = os.getenv("API_KEY", "")


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
        self.client = httpx.AsyncClient(timeout=30.0)
        self.is_running = True

    async def api_get(self, endpoint: str):
        """Calls Django backend API with auth key."""
        url = f"{self.api_url}/api/{endpoint.lstrip('/')}"
        headers = {"X-API-KEY": self.api_key}
        try:
            r = await self.client.get(url, headers=headers, timeout=25.0)
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
        minutes_left = alert.get("minutes_left")
        minutes_before = alert.get("minutes_before")

        # Prefer user-selected minutes_before if actual time is within the tight 2-min latency window
        if minutes_before is not None and minutes_left is not None and abs(minutes_left - minutes_before) <= 2:
            display_minutes = minutes_before
        elif minutes_left is not None:
            display_minutes = minutes_left
        else:
            display_minutes = 15

        if display_minutes <= 0:
            time_phrase = "starting now"
        elif display_minutes == 1:
            time_phrase = "starts in 1 minute"
        else:
            time_phrase = f"starts in {display_minutes} minutes"

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
        High-precision daemon loop with ultra-low latency:
          - Active lecture hours (06:00 to 22:30, Mon-Sat):
            Polls every 20 seconds (:00, :20, :40) to guarantee latency < 20s (well below 2 min limit).
          - Night hours (22:30 to 06:00) and Sundays:
            Polls every 60 seconds (1 minute) to ensure no morning lecture reminders are missed.
        """
        logger.info("Class Reminder Notifier service started successfully.")
        logger.info(f"Target backend: {self.api_url}")

        health_server = await self.start_health_server()

        POLL_INTERVAL = 20.0  # seconds between checks during active hours

        while self.is_running:
            try:
                now = get_tashkent_now()
                current_day = now.isoweekday()  # 1=Mon ... 7=Sun
                current_hour = now.hour

                # Outside class hours: check every 60s (zero chance of sleeping through morning lectures)
                is_sunday = (current_day == 7)
                is_night = (current_hour < 6 or current_hour >= 23)

                if is_sunday or is_night:
                    await asyncio.sleep(60)
                    continue

                # Active lecture hours: Check for pending alerts
                await self.process_pending_alerts()

                # High-precision sleep: Sync with 20-second boundaries (:00, :20, :40)
                now_after = get_tashkent_now()
                remainder = (now_after.second % POLL_INTERVAL) + (now_after.microsecond / 1_000_000.0)
                sleep_seconds = POLL_INTERVAL - remainder
                if sleep_seconds <= 0.1:
                    sleep_seconds = POLL_INTERVAL

                await asyncio.sleep(sleep_seconds)

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Unexpected error in notifier loop: {e}", exc_info=True)
                await asyncio.sleep(5)

        if health_server:
            health_server.close()
            await health_server.wait_closed()

        await self.client.aclose()
        logger.info("Class Reminder Notifier service stopped.")

    async def start_health_server(self):
        """Starts a zero-overhead health check socket if PORT is assigned by host (e.g. Railway)."""
        port_str = os.getenv("PORT")
        if not port_str:
            return None
        try:
            port = int(port_str)
        except ValueError:
            return None

        async def handle_ping(reader, writer):
            try:
                await reader.read(256)
                body = b'{"status":"ok","service":"class-reminder-notifier"}\n'
                resp = (
                    b"HTTP/1.1 200 OK\r\n"
                    b"Content-Type: application/json\r\n"
                    b"Content-Length: " + str(len(body)).encode() + b"\r\n"
                    b"Connection: close\r\n\r\n" + body
                )
                writer.write(resp)
                await writer.drain()
            except Exception:
                pass
            finally:
                try:
                    writer.close()
                    await writer.wait_closed()
                except Exception:
                    pass

        try:
            server = await asyncio.start_server(handle_ping, "0.0.0.0", port)
            logger.info(f"Health check endpoint listening on port {port}")
            return server
        except Exception as e:
            logger.warning(f"Could not bind health server to port {port}: {e}")
            return None

    def stop(self):
        self.is_running = False


def main():
    notifier = ClassReminderNotifier(BOT_TOKEN, API_URL, API_KEY)

    def handle_signal(sig, frame):
        sig_name = "SIGTERM" if sig == signal.SIGTERM else ("SIGINT" if sig == signal.SIGINT else str(sig))
        logger.info(f"Received termination signal {sig} ({sig_name}). Shutting down gracefully...")
        notifier.stop()

    signal.signal(signal.SIGINT, handle_signal)
    signal.signal(signal.SIGTERM, handle_signal)

    try:
        asyncio.run(notifier.run())
    except (KeyboardInterrupt, SystemExit):
        pass


if __name__ == "__main__":
    main()

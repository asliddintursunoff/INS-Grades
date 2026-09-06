import os
import sys
import signal
import asyncio
import logging
import httpx
from dotenv import load_dotenv
from telethon import TelegramClient, events
from telethon.sessions import StringSession

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    format="%(asctime)s [%(levelname)s] [PaymentWorker]: %(message)s",
    level=logging.INFO,
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger("PaymentWorker")

# Configurations
API_ID = os.getenv("TELEGRAM_API_ID")
API_HASH = os.getenv("TELEGRAM_API_HASH")
SESSION_STRING = os.getenv("TELETHON_SESSION_STRING")
BACKEND_API_URL = os.getenv("BACKEND_API_URL", "http://localhost:3000").rstrip("/")
PAYMENT_SECRET_KEY = os.getenv("PAYMENT_SECRET_KEY", "ins_pay_internal_secret_2026_x77")
ALLOWED_SMS_SENDERS = [
    s.strip().lstrip("@").lower()
    for s in os.getenv("ALLOWED_SMS_SENDERS", "humocardbot").split(",")
    if s.strip()
]
ADMIN_TELEGRAM_ID = os.getenv("ADMIN_TELEGRAM_ID")
BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

shutdown_event = asyncio.Event()

def handle_exit_signal(sig, frame):
    logger.info(f"Received termination signal {sig}. Shutting down worker gracefully...")
    shutdown_event.set()

signal.signal(signal.SIGINT, handle_exit_signal)
signal.signal(signal.SIGTERM, handle_exit_signal)


async def send_admin_alert(text: str):
    """Sends a notification to the administrator via the Telegram Bot API."""
    if not BOT_TOKEN or not ADMIN_TELEGRAM_ID:
        return
    try:
        url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
        async with httpx.AsyncClient(timeout=5.0) as client:
            await client.post(url, json={
                "chat_id": ADMIN_TELEGRAM_ID,
                "text": text,
                "parse_mode": "HTML"
            })
    except Exception as e:
        logger.error(f"Failed to send admin notification: {e}")


async def process_sms_event(event, client: TelegramClient):
    """
    Processes incoming messages strictly from authorized bank bots (e.g. @HUMOcardbot).
    Completely ignores expenses/debits and only forwards valid top-up notifications.
    """
    try:
        # Ignore outgoing messages sent by the user account itself
        if event.out:
            return

        chat = await event.get_chat()
        sender = await event.get_sender()

        sender_id = str(getattr(sender, 'id', ''))
        sender_username = (getattr(sender, 'username', '') or '').lstrip('@').lower()
        sender_phone = (getattr(sender, 'phone', '') or '').lower()
        sender_name = f"{getattr(sender, 'first_name', '')} {getattr(sender, 'last_name', '')}".strip()

        chat_id = str(getattr(chat, 'id', ''))
        chat_username = (getattr(chat, 'username', '') or '').lstrip('@').lower()

        # Strict sender filtering: default only humocardbot
        if "*" not in ALLOWED_SMS_SENDERS:
            matched_sender = False
            for allowed in ALLOWED_SMS_SENDERS:
                if allowed in (sender_id, sender_username, chat_id, chat_username, sender_phone):
                    matched_sender = True
                    break
            if not matched_sender:
                # Silently ignore messages from any other bot, group, or user
                return

        raw_text = event.raw_text or ""
        if not raw_text.strip():
            return

        # Pre-filter for HUMOcardbot / Bank notifications:
        # 1. Type 1: Expense/Debit (💸 To'lov ➖ 10.075,00 UZS) -> MUST IGNORE COMPLETELY!
        lower_text = raw_text.lower()
        if "➖" in raw_text or (
            ("to'lov" in lower_text or "oplata" in lower_text or "spisanie" in lower_text)
            and not ("to'ldirish" in lower_text or "popolnenie" in lower_text or "пополнение" in lower_text)
        ):
            return

        # 2. Type 2: Top-up/Deposit (🎉 To'ldirish ➕ 10.216,00 UZS) -> ONLY PROCESS THIS!
        if not ("➕" in raw_text or "+" in raw_text or "to'ldirish" in lower_text or "popolnenie" in lower_text or "пополнение" in lower_text):
            return

        logger.info(f"Incoming top-up notification from '{chat_username or sender_username}' (msg_id: {event.id}): {raw_text[:80]}...")

        # Forward message to Django Backend for atomic matching and verification
        target_endpoint = f"{BACKEND_API_URL}/api/payments/process-incoming-sms/"
        headers = {
            "X-Payment-Secret": PAYMENT_SECRET_KEY,
            "Content-Type": "application/json"
        }
        payload = {
            "raw_message": raw_text,
            "sender": chat_username or sender_username or sender_name or sender_id,
            "telegram_message_id": f"{chat_id or sender_id}_{event.id}"
        }

        async with httpx.AsyncClient(timeout=10.0) as http_client:
            resp = await http_client.post(target_endpoint, json=payload, headers=headers)

        if resp.status_code != 200:
            logger.error(f"Backend rejected SMS processing with status {resp.status_code}: {resp.text}")
            return

        data = resp.json()

        if data.get("duplicate"):
            logger.info(f"Duplicate notification ignored (msg_id: {event.id}).")
        elif data.get("matched"):
            amount = data.get("amount")
            student_id = data.get("student_id")
            student_name = data.get("student_name")
            tx_id = data.get("transaction_id")
            logger.info(f"✅ [MATCHED] Payment of {amount:,} UZS verified for {student_name} ({student_id})! Transaction: {tx_id}")
            
            # Send notification to admin ONLY on successful payment match
            await send_admin_alert(
                f"✅ <b>Yangi to'lov qabul qilindi!</b>\n\n"
                f"👤 <b>Talaba:</b> {student_name} (<code>{student_id}</code>)\n"
                f"💰 <b>Summa:</b> {amount:,} so'm\n"
                f"🆔 <b>Tranzaksiya:</b> <code>{tx_id}</code>\n"
                f"⭐ <b>Premium muddat:</b> 30 kunga faollashtirildi."
            )
        else:
            extracted = data.get("extracted_amount")
            reason = data.get("reason", "Unknown")
            logger.warning(f"⚠️ [UNMATCHED] Deposit ({extracted} UZS): {reason}. Logged to audit trail (no alert sent).")
            # NOTE: Intentionally do NOT send admin alert for unmatched payments to prevent notification spam or feedback loops.

    except Exception as e:
        logger.error(f"Error handling incoming message event: {e}", exc_info=True)


async def main():
    logger.info("Starting INS Grades Automated Payment Telethon Worker...")
    logger.info(f"Backend target URL: {BACKEND_API_URL}")

    if not API_ID or not API_HASH:
        logger.error("TELEGRAM_API_ID and TELEGRAM_API_HASH environment variables are required.")
        logger.error("Please get them from https://my.telegram.org and configure them.")
        sys.exit(1)

    if not SESSION_STRING:
        logger.error("TELETHON_SESSION_STRING environment variable is missing.")
        logger.error("Please generate one using 'python generate_session.py' and set TELETHON_SESSION_STRING.")
        sys.exit(1)

    try:
        api_id_int = int(API_ID)
    except ValueError:
        logger.error("TELEGRAM_API_ID must be a valid integer.")
        sys.exit(1)

    client = TelegramClient(StringSession(SESSION_STRING), api_id_int, API_HASH)

    @client.on(events.NewMessage)
    async def incoming_message_handler(event):
        await process_sms_event(event, client)

    logger.info("Connecting to Telegram...")
    await client.start()
    me = await client.get_me()
    logger.info(f"Connected successfully as Telegram account: {me.first_name} (@{me.username or 'no_username'}, ID: {me.id})")
    logger.info("Listening for incoming bank SMS / transfer notifications in PASSIVE listener mode...")

    # Keep running until SIGINT/SIGTERM is received
    await shutdown_event.wait()

    logger.info("Disconnecting Telethon client...")
    await client.disconnect()
    logger.info("Payment Worker terminated successfully.")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logger.info("Process exited.")

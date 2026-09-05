import dotenv from 'dotenv';
import { TelegramBotService } from './telegram_bot';

dotenv.config();

const BOT_TOKEN = process.env.TELEGRAM_BOT_TOKEN || '8234622386:AAGRh0DIzbn4BrG-gGBWiuTzMHu6l0chciE';
const BACKEND_URL = process.env.BACKEND_API_URL || 'http://localhost:3000';
const INTERNAL_KEY = process.env.INTERNAL_API_KEY || 'uni-system-internal-secret-key-2026';
const APP_URL = process.env.APP_URL || 'https://ins-grades.vercel.app';

console.log('[Bot Worker] Starting standalone INS Telegram Bot Worker...');
console.log(`[Bot Worker] Backend URL: ${BACKEND_URL}`);
console.log(`[Bot Worker] Mini App URL: ${APP_URL}`);

const bot = new TelegramBotService(
  BOT_TOKEN,
  BACKEND_URL,
  INTERNAL_KEY,
  APP_URL
);

bot.start()
  .then(() => {
    console.log('[Bot Worker] Telegram bot polling & reminder loop is active!');
  })
  .catch((err) => {
    console.error('[Bot Worker] Failed to start Telegram bot:', err);
    process.exit(1);
  });

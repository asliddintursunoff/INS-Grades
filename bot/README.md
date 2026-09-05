# INS Grades - Dedicated Telegram Bot Worker (Railway)

This folder contains a standalone worker service for **INS_gradesbot** if you prefer running the Telegram Bot in its own dedicated Railway worker container rather than bundled inside `backend/`.

> **Note:** The `backend/` service already includes this bot automatically by default. You only need this `bot/` folder if you want to scale or deploy the bot independently as a background worker!

## 🚀 Deployment on Railway as a Background Worker

1. In your Railway project, click **"New"** -> **"GitHub Repo"** (or add a new service from the existing repo).
2. Set **Root Directory** in Service Settings to: `bot`
3. Under **Variables**, add:
   - `TELEGRAM_BOT_TOKEN`: `8234622386:AAGRh0DIzbn4BrG-gGBWiuTzMHu6l0chciE`
   - `BACKEND_API_URL`: Your Railway backend domain (e.g. `https://ins-grades-backend.up.railway.app`)
   - `INTERNAL_API_KEY`: `uni-system-internal-secret-key-2026`
   - `APP_URL`: Your Vercel frontend URL (e.g. `https://ins-grades.vercel.app`)
4. Railway will build and run the worker continuously with automatic restart on failure.

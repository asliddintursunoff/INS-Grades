# 🚀 INS Grades - Full Deployment Guide (Vercel + Railway)

This repository is organized into distinct, production-ready modules:

- **`frontend/`** ➔ **Vercel** (React 19 + Vite + Tailwind Mini App)
- **`backend/`** ➔ **Railway** (Express REST API + Database + Telegram Bot + Schedulers)
- **`bot/`** ➔ **Railway** (Optional: Dedicated standalone Telegram Bot worker service)

---

## 📦 Architecture Overview

```
├── frontend/             # Deploy this folder to VERCEL
│   ├── package.json
│   ├── vercel.json
│   ├── vite.config.ts
│   ├── .env.example
│   ├── src/
│   └── public/
│
├── backend/              # Deploy this folder to RAILWAY
│   ├── package.json
│   ├── Procfile
│   ├── railway.json
│   ├── .env.example
│   ├── server.ts
│   ├── db.ts
│   ├── services/
│   └── telegram_bot.ts
│
├── bot/                  # (Optional) Standalone Bot worker on Railway
│   ├── package.json
│   ├── bot_worker.ts
│   └── railway.json
│
└── DEPLOYMENT.md         # This deployment guide
```

---

## Part 1: Push Code to GitHub

You can push this project to your GitHub repository using either of these two methods:

### Method A: Export directly via Google AI Studio
1. Open the **Settings / Export** menu in Google AI Studio.
2. Select **Export to GitHub** or **Download ZIP**.
3. If downloading ZIP, extract and push to your GitHub repo.

### Method B: Using Git in Terminal
Run the following commands in the project directory:

```bash
# 1. Add your GitHub repository as origin
git remote add origin https://github.com/YOUR_USERNAME/YOUR_REPO_NAME.git

# 2. Rename branch to main (if not already)
git branch -M main

# 3. Stage and commit all changes
git add -A
git commit -m "feat: complete INS grades system with Vercel frontend and Railway backend"

# 4. Push to your repository
git push -u origin main
```

---

## Part 2: Deploy Backend to Railway

1. Go to [railway.com](https://railway.com) and click **New Project** ➔ **Deploy from GitHub repo**.
2. Select your repository.
3. In Railway, click on your service and go to **Settings**:
   - **Root Directory**: Set to `backend`
4. Under **Variables**, add these environment variables:

| Variable | Value Example | Notes |
|---|---|---|
| `PORT` | `3000` | Railway automatically assigns a port |
| `TELEGRAM_BOT_TOKEN` | `8234622386:AAGRh0DIzbn4BrG-gGBWiuTzMHu6l0chciE` | From @BotFather |
| `APP_URL` | `https://your-frontend.vercel.app` | Your Vercel frontend URL (set after Part 3) |
| `INTERNAL_API_KEY` | `uni-system-internal-secret-key-2026` | Keep secret |
| `DATABASE_URL` | *(Optional)* | Link a PostgreSQL database plugin in Railway or leave empty for embedded SQLite |

5. Under **Settings ➔ Networking**, click **Generate Domain**.
   - Copy this domain (e.g., `https://ins-grades-backend.up.railway.app`).

---

## Part 3: Deploy Frontend to Vercel

1. Go to [vercel.com](https://vercel.com) and click **Add New Project** ➔ **Import Git Repository**.
2. Select your repository.
3. In project configuration:
   - **Framework Preset**: `Vite`
   - **Root Directory**: Click *Edit* and select `frontend`
4. Under **Environment Variables**, add:

| Variable | Value Example | Notes |
|---|---|---|
| `VITE_API_URL` | `https://ins-grades-backend.up.railway.app` | Your public Railway backend URL (no trailing slash) |
| `VITE_BOT_USERNAME` | `INS_gradesbot` | Your Telegram bot handle |

5. Click **Deploy**. Vercel will build and give you a live production URL (e.g., `https://ins-grades.vercel.app`).

---

## Part 4: Connect Telegram Bot with your Vercel WebApp

Now connect your live Vercel URL to the Telegram Bot:

1. In Railway:
   - Update `APP_URL` in Railway Variables to: `https://ins-grades.vercel.app` (your actual Vercel URL).
2. In Telegram [@BotFather](https://t.me/botfather):
   - Send `/mybots`
   - Choose `@INS_gradesbot`
   - Click **Bot Settings** ➔ **Menu Button** ➔ **Configure menu button**
   - Enter your Vercel URL: `https://ins-grades.vercel.app`
   - Enter button title: `Open INS Grades`
3. In BotFather, also set the WebApp domain:
   - `/setmenubutton` ➔ select bot ➔ set URL.

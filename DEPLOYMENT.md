# INS Grades — Deployment Guide (FastAPI + React + Telegram Bot)

This repository is split into three clean services for effortless deployment:

```
├── frontend/      # React + Vite + Tailwind (Deploy to Vercel)
├── backend/       # Python + FastAPI + SQLite (Deploy to Railway)
└── bot/           # Python Standalone Telegram Bot worker (Optional Railway worker)
```

---

## 1. 🌐 Deploy Frontend to Vercel

1. Go to [vercel.com](https://vercel.com) and click **"Add New Project"**.
2. Select your repository: `asliddintursunoff/INS-Grades`.
3. Set the **Root Directory** to `frontend`.
4. Add the following **Environment Variable**:
   - `VITE_API_URL`: The URL of your Railway backend (e.g. `https://ins-grades-backend.up.railway.app`).
5. Click **Deploy**. Vercel will build and assign you a domain (e.g. `https://ins-grades.vercel.app`).

---

## 2. 🚂 Deploy Backend (Python / FastAPI) to Railway with PostgreSQL

1. Go to [railway.com](https://railway.com) and click **"New Project"**.
2. **Add PostgreSQL Database**:
   - Click **"+ New"** -> **"Database"** -> **"Add PostgreSQL"**.
   - Railway will provision a high-performance PostgreSQL database immediately.
3. **Deploy Backend Service**:
   - In the same project, click **"+ New"** -> **"GitHub Repo"**.
   - Select `asliddintursunoff/INS-Grades`.
   - In settings, set **Root Directory** to `backend`.
4. **Link PostgreSQL to Backend**:
   - Go to your backend service -> **Variables** tab.
   - Click **"Add Reference"** or select `DATABASE_URL` from the PostgreSQL service.
   - Railway will inject `DATABASE_URL` into your backend automatically.
5. In **Variables**, also add:
   - `PORT`: `3000` (or leave default `$PORT`)
   - `TELEGRAM_BOT_TOKEN`: `7963381665:AAFljS3q8j5GvFp-7u2vK5Dq5f5mBqW9X5A`
   - `APP_URL`: Your Vercel frontend URL (e.g. `https://ins-grades.vercel.app`)
   - `INTERNAL_KEY`: `ins_secret_internal_key_2025`
6. Railway will automatically build and start the server with:
   ```bash
   uvicorn main:app --host 0.0.0.0 --port $PORT
   ```
   On startup, the backend connects to your Railway PostgreSQL database, initializes all tables, and auto-seeds the full university schedule and professor directory!
7. In Railway **Settings** -> **Networking**, click **"Generate Domain"** to get your public backend URL.

---

## 3. 🤖 (Optional) Standalone Bot Worker on Railway

If you want the bot running in an isolated worker process instead of inside the backend:
1. In the same Railway project, click **"+ New"** -> **"GitHub Repo"**.
2. Select `asliddintursunoff/INS-Grades`.
3. Set **Root Directory** to `bot`.
4. Add environment variables:
   - `TELEGRAM_BOT_TOKEN`: `7963381665:AAFljS3q8j5GvFp-7u2vK5Dq5f5mBqW9X5A`
   - `API_URL`: Your deployed backend URL from step 2
   - `APP_URL`: Your Vercel URL
   - `INTERNAL_KEY`: `ins_secret_internal_key_2025`
5. Railway will launch `python main.py` using the included Procfile.

---

## 4. 🔑 Summary of Environment Variables

### Frontend (`frontend/.env`)
```env
VITE_API_URL=https://your-backend-name.up.railway.app
```

### Backend (`backend/.env`)
```env
PORT=3000
TELEGRAM_BOT_TOKEN=7963381665:AAFljS3q8j5GvFp-7u2vK5Dq5f5mBqW9X5A
APP_URL=https://ins-grades.vercel.app
INTERNAL_KEY=ins_secret_internal_key_2025
DATABASE_URL=postgresql://postgres:password@host:port/railway
```

### Bot Worker (`bot/.env`)
```env
TELEGRAM_BOT_TOKEN=7963381665:AAFljS3q8j5GvFp-7u2vK5Dq5f5mBqW9X5A
API_URL=https://your-backend-name.up.railway.app
APP_URL=https://ins-grades.vercel.app
INTERNAL_KEY=ins_secret_internal_key_2025
```

# INS Grades - Python FastAPI Backend & Telegram Bot

Powered by **FastAPI** + **Python 3.11** + **Railway PostgreSQL**.
Authored & Configured by `@asliddin_tursunoff`.

## 🚀 Key Highlights
- **Framework:** FastAPI (high-performance asynchronous Python REST API)
- **Database:** Railway PostgreSQL (managed, persistent, zero SQLite files)
- **Automatic Docs:** Swagger UI at `/docs` and ReDoc at `/redoc`
- **Telegram Bot:** Asynchronous polling & reminder scheduler embedded (`telegram_bot.py`)
- **Compatibility:** 100% compatible with the React frontend on Vercel
- **Zero-Config Railway Deployment:** Natively runs on Railway via Nixpacks or Dockerfile

## 🛠 Local Setup
```bash
cd backend
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt

# Start development server
uvicorn main:app --reload --port 3000
```

## 🌐 Deploy to Railway with PostgreSQL
1. Push this folder to your GitHub repo (`asliddintursunoff/INS-Grades`).
2. In [Railway.com](https://railway.com), create a new project.
3. Click **"+ New"** -> **"Database"** -> **"Add PostgreSQL"**.
4. In the same project, click **"+ New"** -> **"GitHub Repo"** and select `asliddintursunoff/INS-Grades`.
5. Set the **Root Directory** to `backend`.
6. Under backend service **Variables**, link `DATABASE_URL` from the PostgreSQL service.
7. Add remaining environment variables:
   - `PORT`: `3000` (or Railway's default `$PORT`)
   - `TELEGRAM_BOT_TOKEN`: `7963381665:AAFljS3q8j5GvFp-7u2vK5Dq5f5mBqW9X5A`
   - `APP_URL`: `https://ins-grades.vercel.app` (your Vercel frontend URL)
   - `INTERNAL_KEY`: `ins_secret_internal_key_2025`
8. Railway will automatically build and start the server with:
   `uvicorn main:app --host 0.0.0.0 --port $PORT`

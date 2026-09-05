# INS Grades - Python FastAPI Backend & Telegram Bot

Powered by **FastAPI** + **Python 3.11** + **SQLite / Railway**.
Authored & Configured by `@asliddin_tursunoff`.

## 🚀 Key Highlights
- **Framework:** FastAPI (high-performance asynchronous Python REST API)
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

## 🌐 Deploy to Railway
1. Push this folder to your GitHub repo (`asliddintursunoff/INS-Grades`).
2. In [Railway.com](https://railway.com), create a new project from your repo.
3. Set the **Root Directory** to `backend`.
4. Add environment variables in Railway:
   - `PORT`: `3000` (or Railway's default `$PORT`)
   - `TELEGRAM_BOT_TOKEN`: `7963381665:AAFljS3q8j5GvFp-7u2vK5Dq5f5mBqW9X5A`
   - `APP_URL`: `https://ins-grades.vercel.app` (your Vercel frontend URL)
   - `INTERNAL_KEY`: `ins_secret_internal_key_2025`
5. Railway will automatically build and start the server with:
   `uvicorn main:app --host 0.0.0.0 --port $PORT`

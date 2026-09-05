# INS Grades - Python Telegram Bot Worker

Standalone Python Telegram Bot worker for INS Grades.
Configured by `@asliddin_tursunoff`.

## 📌 Description
This worker handles Telegram Bot commands and delivers upcoming class notifications by interacting with the FastAPI backend REST API.

## 🛠 Local Run
```bash
cd bot
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python main.py
```

## 🌐 Deploy to Railway
1. Create a new service in your Railway project.
2. Connect to GitHub repo and set **Root Directory** to `bot`.
3. Set environment variables:
   - `TELEGRAM_BOT_TOKEN`: Your Telegram Bot Token
   - `API_URL`: URL of your deployed `backend` service
   - `APP_URL`: Your Vercel frontend URL
   - `INTERNAL_KEY`: Secret internal communication key
4. Railway will automatically build via Nixpacks/Dockerfile and start `python main.py`.

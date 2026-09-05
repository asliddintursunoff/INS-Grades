# INS Grades - Backend & Telegram Bot (Railway Deployment)

This is the Express REST API and automated Telegram Bot service for **INS Grades**.

## 🚀 Quick Railway Deployment

### Step 1: Create a Project on Railway
1. Go to [railway.com](https://railway.com) and log in.
2. Click **"New Project"** -> **"Deploy from GitHub repo"**.
3. Select your repository.

### Step 2: Configure Service Root Directory
1. In your Railway service settings (**Settings** tab), find **Root Directory**.
2. Set **Root Directory** to: `backend`
3. Railway automatically detects Nixpacks and runs:
   - Build: `npm run build`
   - Start: `npm run start:dev` (or `npm start`)

### Step 3: Add Variables in Railway
Under the **Variables** tab in Railway, add:

| Variable | Recommended Value | Description |
|----------|-------------------|-------------|
| `PORT` | `3000` | (Railway assigns its own port automatically, but good to have fallback) |
| `TELEGRAM_BOT_TOKEN` | `8234622386:AAGRh0DIzbn4BrG-gGBWiuTzMHu6l0chciE` | Your Telegram Bot token from @BotFather |
| `APP_URL` | `https://your-frontend.vercel.app` | Your frontend WebApp URL deployed on Vercel |
| `INTERNAL_API_KEY` | `uni-system-internal-secret-key-2026` | Security secret for internal bot calls |
| `DATABASE_URL` | *(Optional)* | Link a Railway PostgreSQL database here. If left empty, SQLite with full schema runs automatically! |

### Step 4: Generate a Public Domain
1. In Railway under **Settings** -> **Networking**, click **"Generate Domain"**.
2. You will get a domain like: `https://ins-grades-production.up.railway.app`.
3. Copy this URL and set it as `VITE_API_URL` in your Vercel frontend!

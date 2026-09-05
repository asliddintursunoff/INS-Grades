# INS Grades - Frontend (Vercel Deployment)

This is the React 19 + Vite + Tailwind CSS Telegram WebApp frontend for **INS Grades**.

## 🚀 Quick Vercel Deployment

### Step 1: Connect your GitHub Repo to Vercel
1. Go to [vercel.com](https://vercel.com) and click **"Add New Project"**.
2. Select your imported GitHub repository.
3. In the project setup screen, configure the **Root Directory**:
   - Click **Edit** next to Root Directory and set it to: `frontend` (or leave as `./` if using monorepo root).
4. Framework Preset will auto-detect as **Vite**.

### Step 2: Configure Environment Variables
In Vercel's **Environment Variables** section, add:

| Name | Value Example | Description |
|------|---------------|-------------|
| `VITE_API_URL` | `https://your-backend.up.railway.app` | The public Railway URL of your backend server (no trailing slash) |
| `VITE_BOT_USERNAME` | `INS_gradesbot` | Your Telegram Bot username (without @) |

### Step 3: Deploy
Click **Deploy**. Vercel will build and assign you a production URL (e.g. `https://ins-grades.vercel.app`).

### Step 4: Link with Telegram Bot
Once you have your Vercel URL, go to your Railway backend settings or Telegram BotFather:
1. In Railway backend, set `APP_URL=https://ins-grades.vercel.app`.
2. In Telegram [@BotFather](https://t.me/botfather):
   - Send `/mybots` -> Select `@INS_gradesbot` -> **Bot Settings** -> **Menu Button** -> **Configure menu button**.
   - Enter your Vercel URL: `https://ins-grades.vercel.app`.

# INS Grades - University Timetable System

A modern university schedule and attendance tracking platform built with a modular 3-tier microservice architecture:

```
├── backend/                  # Django REST Framework API & PostgreSQL
├── frontend/                 # React + Vite + Tailwind Web Application
├── bot/                      # Telegram Bot for Schedule & Notifications
└── docker-compose.yml        # Multi-container orchestration
```

---

## Architecture Overview

### 1. `backend/` (Django REST Framework)
- **Framework**: Django 5.x & Django REST Framework
- **Database**: PostgreSQL (Railway integration with support for explicit host/port/credentials)
- **Deployment**: `backend/Dockerfile` using Gunicorn
- **Environment config**: See `backend/.env.example`

### 2. `frontend/` (React + Vite SPA)
- **Framework**: React 18, TypeScript, Tailwind CSS, Lucide icons
- **Deployment**: Vercel or `frontend/Dockerfile` (Nginx)
- **Environment config**: See `frontend/.env.example`

### 3. `bot/` (Telegram Bot)
- **Runtime**: Python Async (`httpx`)
- **Features**: Personalized schedule, week view, homework tracking, attendance alerts
- **Deployment**: `bot/Dockerfile` or Railway Worker
- **Environment config**: See `bot/.env.example`

---

## Local Development with Docker

Run all three services together:

```bash
docker compose up --build
```

- **Frontend**: http://localhost:3000
- **Django REST API**: http://localhost:8000/api/
- **API Health**: http://localhost:8000/api/health/
- **Telegram Bot**: Runs in background polling Telegram updates

# Timetable Microservice

Automated university timetable synchronization and screenshot service for **Inha University in Tashkent (IUT)** (`https://iut.edupage.org/timetable/`).

Designed to run as an independent microservice or scheduled cron job on **Railway** or **Docker**.

---

## What It Does

1. **Scrapes Text Timetable Data**:
   - Discovers active semester timetable dynamically from EduPage.
   - Accurately parses all groups, professors, subjects, classrooms, and timing slots.
2. **In-Place Database Synchronization**:
   - Updates `professors`, `groups`, `subjects`, `classes` (preserving `class_id`), and `group_timetable` slots.
3. **Student Enrollment & Drop Protection**:
   - **Dropped Courses Respected**: If a student dropped a course (`status='dropped'`) or dropped that subject, the script **never re-enrolls or re-activates it**.
   - **Extra / Retake Courses Preserved**: If a student is enrolled in a class from another group, the script **never deletes or drops it**.
   - **Automatic Group Enrollment**: Matches active group courses to students who haven't dropped them.
   - **Existing Enrollments Updated**: Student enrollments remain connected to the updated class timings.
4. **Upgraded Timetable Screenshots & Railway S3 Storage**:
   - Uses Headless Chrome/Chromium to capture element-cropped timetable PNGs for each group.
   - Automatically uploads screenshots to **Railway S3 / Tigris** bucket (`resilient-module-m3qmihat`).
   - **Old Photo Cleanup**: When updating a group's timetable photo, the previous photo is automatically removed from S3 storage before setting the new one.
   - Updates `Group.timetable_image_url` in the database with the new public S3 URL.
   - Falls back gracefully to local static files if S3 credentials are not set.

---

## Directory Structure

```
timetable/
├── main.py              # Master entrypoint (`python main.py`)
├── parser.py            # EduPage text scraper & parser
├── screenshot_taker.py  # Upgraded headless Chrome screenshot taker
├── s3_storage.py        # S3-compatible Tigris/Railway object storage manager
├── db.py                # Database connection & in-place upsert logic
├── requirements.txt     # Service dependencies
├── Dockerfile           # Multi-stage container with Chromium for Railway / Docker
├── railway.json         # Railway worker / cron deployment configuration
├── .env                 # Local environment variables (DATABASE_URL, S3 credentials)
└── .env.example         # Template configuration without secrets
```

---

## Configuration (`.env`)

Set `DATABASE_URL` and S3 credentials in `.env`:

```env
# Database Connection
DATABASE_URL=postgresql://postgres:your_password@your_railway_host:5432/railway

# Railway S3-Compatible Object Storage Credentials
S3_ENDPOINT_URL=https://t3.storageapi.dev
S3_REGION=auto
S3_BUCKET_NAME=your_bucket_name_here
S3_ACCESS_KEY_ID=your_access_key_id_here
S3_SECRET_ACCESS_KEY=your_secret_access_key_here
```

*(If `DATABASE_URL` is empty, it automatically falls back to local SQLite at `backend/db.sqlite3`)*.

---

## Running the Service

### 1. Direct Execution
```bash
python main.py
```

### 2. Fast DB Sync Only (Skip Screenshots)
```bash
python main.py --skip-screenshots
```

### 3. Sync Single Group
```bash
python main.py --group CIE26-1
```

### 4. Dry Run (Test without committing to DB)
```bash
python main.py --dry-run
```

---

## Docker & Railway Deployment

### Railway Cron Job:
1. Connect this repository to Railway.
2. Create a new service with Root Directory: `timetable`.
3. In Railway **Settings**:
   - Set **Cron Schedule** (e.g. `0 3 * * *` for daily at 3:00 AM).
   - Set Environment Variable: `DATABASE_URL` = `${{Postgres.DATABASE_URL}}`.
4. Railway will trigger the container on schedule and run `python main.py`.

### Local Docker Build & Run:
```bash
docker build -t ins-timetable ./timetable
docker run --env-file ./timetable/.env ins-timetable
```

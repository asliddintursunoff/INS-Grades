import express from 'express';
import path from 'path';
import crypto from 'crypto';
import dotenv from 'dotenv';
import { createServer as createViteServer } from 'vite';

import { db } from './server/db';
import { getStudentClasses, dropClass, retakeClass, getRetakeCatalog, enrollRetakeClass } from './server/services/enrollment_service';
import { getEffectiveSchedule, getAvailableGroupsForSubject, changeStudentGroup, revertStudentOverride } from './server/services/timetable_service';
import { getStudentAbsences, suggestMakeupSessions, recordMakeup } from './server/services/attendance_service';
import { getNotificationSettings, updateNotificationSettings, getUpcomingSessionsForScheduler, markNotificationSent } from './server/services/notification_service';
import { TelegramBotService } from './server/telegram_bot';

dotenv.config();

const app = express();
const PORT = Number(process.env.PORT) || 3000;
const INTERNAL_KEY = process.env.INTERNAL_API_KEY || 'uni-system-internal-secret-key-2026';
const BOT_TOKEN = process.env.TELEGRAM_BOT_TOKEN || '8234622386:AAGRh0DIzbn4BrG-gGBWiuTzMHu6l0chciE';
const APP_URL = process.env.APP_URL || '';

// Enable CORS for Vercel and external clients
app.use((req, res, next) => {
  res.header('Access-Control-Allow-Origin', '*');
  res.header('Access-Control-Allow-Methods', 'GET, POST, PUT, DELETE, OPTIONS');
  res.header('Access-Control-Allow-Headers', 'Origin, X-Requested-With, Content-Type, Accept, Authorization');
  if (req.method === 'OPTIONS') {
    return res.sendStatus(200);
  }
  next();
});

app.use(express.json());

// Helper: Resolve student from either numeric telegram_id or student_id
function resolveStudent(idParam: string | number) {
  const isNumeric = /^\d+$/.test(String(idParam));
  let student: any;

  if (isNumeric) {
    student = db.query(
      `SELECT s.*, g.group_name 
       FROM students s 
       JOIN groups g ON s.group_id = g.group_id 
       WHERE s.telegram_id = ?`,
      [Number(idParam)]
    ).rows[0];
  } else {
    student = db.query(
      `SELECT s.*, g.group_name 
       FROM students s 
       JOIN groups g ON s.group_id = g.group_id 
       WHERE s.student_id = ?`,
      [String(idParam)]
    ).rows[0];
  }

  // Fallback to first student if not found in demo mode
  if (!student) {
    const fallback = db.query(
      `SELECT s.*, g.group_name 
       FROM students s 
       JOIN groups g ON s.group_id = g.group_id 
       LIMIT 1`
    ).rows[0];
    return fallback;
  }
  return student;
}

// Telegram WebApp initData HMAC-SHA256 validator
function validateTelegramInitData(initData: string): { valid: boolean; user?: any } {
  if (!initData) return { valid: false };
  try {
    const params = new URLSearchParams(initData);
    const hash = params.get('hash');
    if (!hash) return { valid: false };

    params.delete('hash');
    const sorted = Array.from(params.entries())
      .map(([k, v]) => `${k}=${v}`)
      .sort()
      .join('\n');

    const secret = crypto.createHmac('sha256', 'WebAppData').update(BOT_TOKEN).digest();
    const calculatedHash = crypto.createHmac('sha256', secret).update(sorted).digest('hex');

    if (calculatedHash === hash) {
      const userStr = params.get('user');
      const user = userStr ? JSON.parse(userStr) : undefined;
      return { valid: true, user };
    }
    return { valid: false };
  } catch (err) {
    return { valid: false };
  }
}

// Auth middleware for internal bot calls
function requireInternalKey(req: express.Request, res: express.Response, next: express.NextFunction) {
  const key = req.headers['x-internal-key'];
  if (key === INTERNAL_KEY) {
    return next();
  }
  // Also permit local loopback for convenience
  const ip = req.ip || req.socket.remoteAddress || '';
  if (ip.includes('127.0.0.1') || ip.includes('::1')) {
    return next();
  }
  res.status(403).json({ error: "Ruxsat berilmadi: X-Internal-Key noto'g'ri" });
}

// ==========================================
// 6. REST API ENDPOINTS
// ==========================================

// 6.1 Auth
// GET /api/auth/me/:telegram_id
app.get('/api/auth/me/:telegram_id', (req, res) => {
  const tgId = Number(req.params.telegram_id);
  if (!tgId || isNaN(tgId)) {
    return res.json({ found: false });
  }

  const student = db.query(
    `SELECT s.student_id, s.full_name, s.group_id, s.year_of_study, s.telegram_id, s.telegram_username, g.group_name 
     FROM students s 
     JOIN groups g ON s.group_id = g.group_id 
     WHERE s.telegram_id = ?`,
    [tgId]
  ).rows[0];

  if (!student) {
    return res.json({ found: false });
  }

  return res.json({
    found: true,
    student: {
      student_id: student.student_id,
      full_name: student.full_name,
      group_name: student.group_name,
      year_of_study: student.year_of_study,
      telegram_id: student.telegram_id,
      telegram_username: student.telegram_username,
    },
  });
});

// POST /api/auth/link/
app.post('/api/auth/link/', (req, res) => {
  const { student_id, telegram_id, telegram_username } = req.body;
  if (!student_id || !telegram_id) {
    return res.status(400).json({ success: false, error: 'Student ID and Telegram ID are required' });
  }

  const cleanStudentId = String(student_id).trim();

  const student = db.query(
    `SELECT s.student_id, s.full_name, s.year_of_study, g.group_name 
     FROM students s 
     JOIN groups g ON s.group_id = g.group_id 
     WHERE UPPER(s.student_id) = UPPER(?)`,
    [cleanStudentId]
  ).rows[0];

  if (!student) {
    return res.status(404).json({ 
      success: false, 
      not_found: true,
      error: 'Student ID was not found in the university database. Please talk with admin: @asliddin_tursunoff' 
    });
  }

  // Link telegram_id
  db.query(
    `UPDATE students 
     SET telegram_id = ?, telegram_username = ? 
     WHERE student_id = ?`,
    [telegram_id, telegram_username || null, student.student_id]
  );

  return res.json({
    success: true,
    student_id: student.student_id,
    full_name: student.full_name,
    group_name: student.group_name,
    year_of_study: student.year_of_study || 2,
  });
});

// 6.2 Jadval (Timetable)
// GET /api/students/:telegram_id/timetable/
app.get('/api/students/:telegram_id/timetable/', (req, res) => {
  try {
    const student = resolveStudent(req.params.telegram_id);
    if (!student) {
      return res.status(404).json({ error: 'Talaba topilmadi' });
    }
    const scheduleData = getEffectiveSchedule(student.student_id);
    res.json(scheduleData);
  } catch (err: any) {
    res.status(500).json({ error: err.message });
  }
});

// 6.3 Courses / Drop / Retake
// GET /api/students/:telegram_id/classes/
app.get('/api/students/:telegram_id/classes/', (req, res) => {
  try {
    const student = resolveStudent(req.params.telegram_id);
    if (!student) {
      return res.status(404).json({ error: 'Student not found' });
    }
    const classes = getStudentClasses(student.student_id);
    res.json({ classes });
  } catch (err: any) {
    res.status(500).json({ error: err.message });
  }
});

// GET /api/students/:telegram_id/retake-catalog/
app.get('/api/students/:telegram_id/retake-catalog/', (req, res) => {
  try {
    const student = resolveStudent(req.params.telegram_id);
    if (!student) {
      return res.status(404).json({ error: 'Student not found' });
    }
    const catalog = getRetakeCatalog(student.student_id);
    res.json(catalog);
  } catch (err: any) {
    res.status(500).json({ error: err.message });
  }
});

// POST /api/students/:telegram_id/enroll-retake/
app.post('/api/students/:telegram_id/enroll-retake/', (req, res) => {
  try {
    const student = resolveStudent(req.params.telegram_id);
    if (!student) {
      return res.status(404).json({ error: 'Student not found' });
    }
    const { class_id } = req.body;
    if (!class_id) {
      return res.status(400).json({ error: 'class_id is required' });
    }
    const result = enrollRetakeClass(student.student_id, Number(class_id));
    res.json(result);
  } catch (err: any) {
    res.status(500).json({ error: err.message });
  }
});

// POST /api/students/:telegram_id/drop/
app.post('/api/students/:telegram_id/drop/', (req, res) => {
  try {
    const student = resolveStudent(req.params.telegram_id);
    if (!student) {
      return res.status(404).json({ error: 'Student not found' });
    }
    const { class_id } = req.body;
    if (!class_id) {
      return res.status(400).json({ error: 'class_id is required' });
    }
    const result = dropClass(student.student_id, Number(class_id));
    res.json(result);
  } catch (err: any) {
    res.status(500).json({ error: err.message });
  }
});

// POST /api/students/:telegram_id/retake/
app.post('/api/students/:telegram_id/retake/', (req, res) => {
  try {
    const student = resolveStudent(req.params.telegram_id);
    if (!student) {
      return res.status(404).json({ error: 'Student not found' });
    }
    const { class_id } = req.body;
    if (!class_id) {
      return res.status(400).json({ error: 'class_id is required' });
    }
    const result = retakeClass(student.student_id, Number(class_id));
    res.json(result);
  } catch (err: any) {
    res.status(500).json({ error: err.message });
  }
});

// 6.4 Group switching & Rescheduling
// GET /api/subjects/:subject_id/available-groups/?student_telegram_id={id}
app.get('/api/subjects/:subject_id/available-groups/', (req, res) => {
  try {
    const subjectId = Number(req.params.subject_id);
    const studentIdParam = (req.query.student_telegram_id as string) || '';
    const student = resolveStudent(studentIdParam);
    if (!student) {
      return res.status(404).json({ error: 'Student not found' });
    }

    const options = getAvailableGroupsForSubject(subjectId, student.student_id);
    res.json({ options });
  } catch (err: any) {
    res.status(500).json({ error: err.message });
  }
});

// POST /api/students/:telegram_id/change-group/
app.post('/api/students/:telegram_id/change-group/', (req, res) => {
  try {
    const student = resolveStudent(req.params.telegram_id);
    if (!student) {
      return res.status(404).json({ error: 'Student not found' });
    }
    const { old_class_id, new_class_id, change_type } = req.body;
    if (!old_class_id || !new_class_id) {
      return res.status(400).json({ error: 'old_class_id and new_class_id are required' });
    }
    const type = change_type === 'permanent' ? 'permanent' : 'one_time';
    const result = changeStudentGroup(student.student_id, Number(old_class_id), Number(new_class_id), type);
    res.json(result);
  } catch (err: any) {
    res.status(500).json({ error: err.message });
  }
});

// POST /api/students/:telegram_id/revert-override/
app.post('/api/students/:telegram_id/revert-override/', (req, res) => {
  try {
    const student = resolveStudent(req.params.telegram_id);
    if (!student) {
      return res.status(404).json({ error: 'Student not found' });
    }
    const { subject_id } = req.body;
    if (!subject_id) {
      return res.status(400).json({ error: 'subject_id is required' });
    }
    const result = revertStudentOverride(student.student_id, Number(subject_id));
    res.json(result);
  } catch (err: any) {
    res.status(500).json({ error: err.message });
  }
});

// 6.5 Absence / Makeup
// GET /api/students/:telegram_id/absences/
app.get('/api/students/:telegram_id/absences/', (req, res) => {
  try {
    const student = resolveStudent(req.params.telegram_id);
    if (!student) {
      return res.status(404).json({ error: 'Student not found' });
    }
    const absences = getStudentAbsences(student.student_id);
    res.json({ absences });
  } catch (err: any) {
    res.status(500).json({ error: err.message });
  }
});

// GET /api/attendance/:session_id/makeup-options/?student_telegram_id={id}
app.get('/api/attendance/:session_id/makeup-options/', (req, res) => {
  try {
    const sessionId = Number(req.params.session_id);
    const studentIdParam = (req.query.student_telegram_id as string) || '';
    const student = resolveStudent(studentIdParam);
    if (!student) {
      return res.status(404).json({ error: 'Student not found' });
    }
    const options = suggestMakeupSessions(student.student_id, sessionId);
    res.json({ options });
  } catch (err: any) {
    res.status(500).json({ error: err.message });
  }
});

// POST /api/attendance/:session_id/makeup/
app.post('/api/attendance/:session_id/makeup/', (req, res) => {
  try {
    const sessionId = Number(req.params.session_id);
    const { student_telegram_id, makeup_session_id } = req.body;
    const student = resolveStudent(student_telegram_id);
    if (!student) {
      return res.status(404).json({ error: 'Student not found' });
    }
    const result = recordMakeup(student.student_id, sessionId, Number(makeup_session_id));
    res.json(result);
  } catch (err: any) {
    res.status(500).json({ error: err.message });
  }
});

// 6.6 Notification Settings
// GET /api/students/:telegram_id/notification-settings/
app.get('/api/students/:telegram_id/notification-settings/', (req, res) => {
  try {
    const student = resolveStudent(req.params.telegram_id);
    if (!student) {
      return res.status(404).json({ error: 'Student not found' });
    }
    const settings = getNotificationSettings(student.student_id);
    res.json(settings);
  } catch (err: any) {
    res.status(500).json({ error: err.message });
  }
});

// PATCH /api/students/:telegram_id/notification-settings/
app.patch('/api/students/:telegram_id/notification-settings/', (req, res) => {
  try {
    const student = resolveStudent(req.params.telegram_id);
    if (!student) {
      return res.status(404).json({ error: 'Student not found' });
    }
    const { enabled, minutes_before } = req.body;
    const updated = updateNotificationSettings(student.student_id, enabled, minutes_before);
    res.json({ success: true, ...updated });
  } catch (err: any) {
    res.status(500).json({ error: err.message });
  }
});

// 6.7 Ichki (faqat Bot uchun) — Notification scheduler
// GET /api/internal/upcoming-sessions/
app.get('/api/internal/upcoming-sessions/', requireInternalKey, (req, res) => {
  try {
    const notifications = getUpcomingSessionsForScheduler();
    res.json({ notifications });
  } catch (err: any) {
    res.status(500).json({ error: err.message });
  }
});

// POST /api/internal/upcoming-sessions/mark-sent/
app.post('/api/internal/upcoming-sessions/mark-sent/', requireInternalKey, (req, res) => {
  const { telegram_id, session_id } = req.body;
  if (!telegram_id || !session_id) {
    return res.status(400).json({ error: 'telegram_id va session_id kerak' });
  }
  const result = markNotificationSent(Number(telegram_id), Number(session_id));
  res.json(result);
});

// Helper for UI demo switcher & info
app.get('/api/demo/students', (req, res) => {
  const students = db.query(
    `SELECT s.student_id, s.full_name, s.telegram_id, s.telegram_username, g.group_name
     FROM students s
     JOIN groups g ON s.group_id = g.group_id
     ORDER BY s.student_id`
  ).rows;
  res.json({ students });
});

app.get('/api/system/status', (req, res) => {
  const studentCount = db.query('SELECT COUNT(*) as c FROM students').rows[0]?.c || 0;
  const classCount = db.query('SELECT COUNT(*) as c FROM classes').rows[0]?.c || 0;
  res.json({
    status: 'ok',
    database: db.isPostgres ? 'PostgreSQL (Railway)' : 'SQLite (Embedded with schema)',
    bot_active: true,
    bot_username: 'INS_gradesbot',
    student_count: studentCount,
    class_count: classCount,
  });
});

// ==========================================
// Vite Middleware / Static Server
// ==========================================
async function startServer() {
  if (process.env.NODE_ENV !== 'production') {
    const vite = await createViteServer({
      server: { middlewareMode: true },
      appType: 'spa',
    });
    app.use(vite.middlewares);
  } else {
    const distPath = path.join(process.cwd(), 'dist');
    app.use(express.static(distPath));
    app.get('*', (req, res) => {
      res.sendFile(path.join(distPath, 'index.html'));
    });
  }

  app.listen(PORT, '0.0.0.0', () => {
    console.log(`[Server] Universitet Timetable API listening on http://0.0.0.0:${PORT}`);

    // Launch Telegram Bot client
    const botService = new TelegramBotService(
      BOT_TOKEN,
      `http://127.0.0.1:${PORT}`,
      INTERNAL_KEY,
      APP_URL
    );
    botService.start().catch((err) => {
      console.warn('[Server] Telegram bot start error:', err.message);
    });
  });
}

startServer();

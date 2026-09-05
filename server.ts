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
const API_KEY = process.env.API_KEY || process.env.INTERNAL_API_KEY || process.env.INTERNAL_KEY || 'ins_secure_api_key_2026_default';
const BOT_TOKEN = process.env.TELEGRAM_BOT_TOKEN || '8234622386:AAGRh0DIzbn4BrG-gGBWiuTzMHu6l0chciE';
const APP_URL = process.env.APP_URL || '';

// Ephemeral session secret for web client handshake (master API_KEY is NEVER exposed to frontend)
const SESSION_SECRET = crypto.createHash('sha256').update(API_KEY).digest('hex');

// ==========================================
// 1. Rate Limiting Middleware (Basic Rate Limiting)
// ==========================================
const rateLimitMap = new Map<string, number[]>();
const RATE_LIMIT_MAX = 60; // 60 requests per minute
const RATE_LIMIT_WINDOW_MS = 60 * 1000;

app.use((req, res, next) => {
  if (req.method === 'OPTIONS') return next();

  const ip = req.ip || req.socket.remoteAddress || 'unknown';
  const now = Date.now();
  const timestamps = (rateLimitMap.get(ip) || []).filter((t) => now - t < RATE_LIMIT_WINDOW_MS);

  if (timestamps.length >= RATE_LIMIT_MAX) {
    const retryAfter = Math.ceil((timestamps[0] + RATE_LIMIT_WINDOW_MS - now) / 1000);
    res.setHeader('Retry-After', Math.max(1, retryAfter));
    res.setHeader('X-RateLimit-Limit', RATE_LIMIT_MAX);
    res.setHeader('X-RateLimit-Remaining', 0);
    return res.status(429).json({
      error: 'Too Many Requests',
      message: `Rate limit of ${RATE_LIMIT_MAX} requests per minute exceeded. Please try again later.`,
      retry_after_seconds: Math.max(1, retryAfter),
    });
  }

  timestamps.push(now);
  rateLimitMap.set(ip, timestamps);
  res.setHeader('X-RateLimit-Limit', RATE_LIMIT_MAX);
  res.setHeader('X-RateLimit-Remaining', Math.max(0, RATE_LIMIT_MAX - timestamps.length));
  next();
});

// ==========================================
// 2. Proper CORS Configuration
// ==========================================
const allowedOriginsConfig = (process.env.ALLOWED_ORIGINS || 'https://ins-grades.vercel.app,http://localhost:3000,http://localhost:5173')
  .split(',')
  .map((s) => s.trim())
  .filter(Boolean);

app.use((req, res, next) => {
  const origin = req.headers.origin;
  const isAllowedOrigin = origin && (
    allowedOriginsConfig.includes(origin) ||
    origin.endsWith('.vercel.app') ||
    origin.includes('telegram.org') ||
    origin.includes('localhost') ||
    origin.includes('127.0.0.1')
  );

  if (origin && isAllowedOrigin) {
    res.setHeader('Access-Control-Allow-Origin', origin);
  } else if (!origin) {
    res.setHeader('Access-Control-Allow-Origin', allowedOriginsConfig[0] || '*');
  } else {
    res.setHeader('Access-Control-Allow-Origin', allowedOriginsConfig[0] || origin);
  }

  res.setHeader('Access-Control-Allow-Methods', 'GET, POST, PUT, PATCH, DELETE, OPTIONS');
  res.setHeader(
    'Access-Control-Allow-Headers',
    'Origin, X-Requested-With, Content-Type, Accept, Authorization, X-API-Key, X-Session-Token, X-Internal-Key'
  );
  res.setHeader('Access-Control-Allow-Credentials', 'true');

  if (req.method === 'OPTIONS') {
    return res.sendStatus(200);
  }
  next();
});

app.use(express.json());

// ==========================================
// 3. Helper Functions & Auth
// ==========================================

function resolveStudent(idParam: string | number) {
  if (!idParam) return null;
  const isNumeric = /^\d+$/.test(String(idParam));
  let student: any = null;

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
       WHERE UPPER(s.student_id) = UPPER(?)`,
      [String(idParam)]
    ).rows[0];
  }

  return student || null;
}

function validateTelegramInitData(initData: string): { valid: boolean; user?: any } {
  if (!initData || !BOT_TOKEN) return { valid: false };
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

function verifySessionToken(token: string): boolean {
  if (!token || !token.includes(':')) return false;
  try {
    const parts = token.split(':');
    if (parts.length !== 3) return false;
    const [ip, tsStr, sig] = parts;
    const ts = Number(tsStr);
    if (isNaN(ts) || Date.now() - ts > 4 * 3600 * 1000) return false; // 4 hour expiry

    const expectedSig = crypto.createHmac('sha256', SESSION_SECRET).update(`${ip}:${tsStr}`).digest('hex');
    return crypto.timingSafeEqual(Buffer.from(sig), Buffer.from(expectedSig));
  } catch {
    return false;
  }
}

// Protected API authentication middleware
function requireApiAuth(req: express.Request, res: express.Response, next: express.NextFunction) {
  // 1. API Key Header
  const apiKeyHeader = req.headers['x-api-key'] as string;
  if (apiKeyHeader && apiKeyHeader === API_KEY) {
    return next();
  }

  // 2. Authorization Bearer or TelegramWebApp
  const authHeader = req.headers['authorization'] || '';
  if (authHeader.startsWith('Bearer ')) {
    const token = authHeader.slice(7).trim();
    if (token === API_KEY || verifySessionToken(token)) {
      return next();
    }
  }

  if (authHeader.startsWith('TelegramWebApp ')) {
    const initData = authHeader.slice(15).trim();
    const validation = validateTelegramInitData(initData);
    if (validation.valid) {
      return next();
    }
  }

  // 3. Ephemeral Session Token Header
  const sessionToken = req.headers['x-session-token'] as string;
  if (sessionToken && verifySessionToken(sessionToken)) {
    return next();
  }

  // 4. Internal secret key
  const internalKey = req.headers['x-internal-key'] as string;
  if (internalKey && internalKey === API_KEY) {
    return next();
  }

  // 5. Localhost loopback
  const ip = req.ip || req.socket.remoteAddress || '';
  if (ip.includes('127.0.0.1') || ip.includes('::1')) {
    return next();
  }

  return res.status(401).json({
    error: 'Unauthorized',
    message: 'Protected endpoint: Valid API key or authenticated Telegram session required.',
  });
}

// ==========================================
// 4. Public Endpoints
// ==========================================

// Health check with explicit PostgreSQL connection check
app.get(['/', '/api/health', '/api/health/'], (req, res) => {
  const isHealthy = db.isConnected;
  const statusPayload = {
    status: isHealthy ? 'healthy' : 'database_connection_error',
    service: 'INS Grades University Timetable API',
    security: 'API-Key & Telegram HMAC Enabled',
    database: 'Railway PostgreSQL',
    database_connected: isHealthy,
    database_error: isHealthy ? null : db.lastError || 'Railway PostgreSQL database is not connected.',
  };

  if (!isHealthy) {
    return res.status(503).json(statusPayload);
  }
  return res.json(statusPayload);
});

// Ephemeral session handshake for browser clients (never exposes API_KEY to frontend bundle)
app.post(['/api/auth/session', '/api/auth/session/'], (req, res) => {
  const ip = req.ip || req.socket.remoteAddress || 'client';
  const ts = Date.now().toString();
  const sig = crypto.createHmac('sha256', SESSION_SECRET).update(`${ip}:${ts}`).digest('hex');
  const sessionToken = `${ip}:${ts}:${sig}`;

  res.json({
    session_token: sessionToken,
    expires_in_seconds: 14400,
    auth_type: 'ephemeral_client_session',
  });
});

// ==========================================
// 5. Protected REST API Endpoints
// ==========================================

app.get(['/api/system/status', '/api/system/status/'], requireApiAuth, (req, res) => {
  try {
    const studentCount = db.query('SELECT COUNT(*) as c FROM students').rows[0]?.c || 0;
    const classCount = db.query('SELECT COUNT(*) as c FROM classes').rows[0]?.c || 0;
    res.json({
      status: 'ok',
      database: 'Railway PostgreSQL',
      database_connected: db.isConnected,
      bot_active: true,
      bot_username: 'INS_gradesbot',
      student_count: studentCount,
      class_count: classCount,
    });
  } catch (err: any) {
    res.status(503).json({ error: 'Database connection error', message: err.message });
  }
});

app.get(['/api/auth/me/:telegram_id', '/api/auth/me/:telegram_id/'], requireApiAuth, (req, res) => {
  try {
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
        year_of_study: student.year_of_study || 2,
        telegram_id: student.telegram_id,
        telegram_username: student.telegram_username,
      },
    });
  } catch (err: any) {
    res.status(503).json({ error: 'Database connection error', message: err.message });
  }
});

app.post(['/api/auth/link', '/api/auth/link/'], requireApiAuth, (req, res) => {
  try {
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
        error: `Student ID '${cleanStudentId}' was not found in university database.`,
      });
    }

    db.execute(
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
  } catch (err: any) {
    res.status(503).json({ error: 'Database connection error', message: err.message });
  }
});

app.get(['/api/students/:telegram_id/timetable', '/api/students/:telegram_id/timetable/'], requireApiAuth, (req, res) => {
  try {
    const student = resolveStudent(req.params.telegram_id);
    if (!student) {
      return res.status(404).json({ error: 'Student not found in PostgreSQL database.' });
    }
    const scheduleData = getEffectiveSchedule(student.student_id);
    res.json(scheduleData);
  } catch (err: any) {
    const statusCode = err.message?.includes('Database connection error') ? 503 : 500;
    res.status(statusCode).json({ error: err.message });
  }
});

app.get(['/api/students/:telegram_id/classes', '/api/students/:telegram_id/classes/'], requireApiAuth, (req, res) => {
  try {
    const student = resolveStudent(req.params.telegram_id);
    if (!student) {
      return res.status(404).json({ error: 'Student not found' });
    }
    const classes = getStudentClasses(student.student_id);
    res.json({ classes });
  } catch (err: any) {
    const statusCode = err.message?.includes('Database connection error') ? 503 : 500;
    res.status(statusCode).json({ error: err.message });
  }
});

app.get(['/api/students/:telegram_id/retake-catalog', '/api/students/:telegram_id/retake-catalog/'], requireApiAuth, (req, res) => {
  try {
    const student = resolveStudent(req.params.telegram_id);
    if (!student) {
      return res.status(404).json({ error: 'Student not found' });
    }
    const catalog = getRetakeCatalog(student.student_id);
    res.json(catalog);
  } catch (err: any) {
    const statusCode = err.message?.includes('Database connection error') ? 503 : 500;
    res.status(statusCode).json({ error: err.message });
  }
});

app.post(['/api/students/:telegram_id/enroll-retake', '/api/students/:telegram_id/enroll-retake/'], requireApiAuth, (req, res) => {
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
    const statusCode = err.message?.includes('Database connection error') ? 503 : 500;
    res.status(statusCode).json({ error: err.message });
  }
});

app.post(['/api/students/:telegram_id/drop', '/api/students/:telegram_id/drop/'], requireApiAuth, (req, res) => {
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
    const statusCode = err.message?.includes('Database connection error') ? 503 : 500;
    res.status(statusCode).json({ error: err.message });
  }
});

app.post(['/api/students/:telegram_id/retake', '/api/students/:telegram_id/retake/'], requireApiAuth, (req, res) => {
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
    const statusCode = err.message?.includes('Database connection error') ? 503 : 500;
    res.status(statusCode).json({ error: err.message });
  }
});

app.get(['/api/subjects/:subject_id/available-groups', '/api/subjects/:subject_id/available-groups/'], requireApiAuth, (req, res) => {
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
    const statusCode = err.message?.includes('Database connection error') ? 503 : 500;
    res.status(statusCode).json({ error: err.message });
  }
});

app.post(['/api/students/:telegram_id/change-group', '/api/students/:telegram_id/change-group/'], requireApiAuth, (req, res) => {
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
    const statusCode = err.message?.includes('Database connection error') ? 503 : 500;
    res.status(statusCode).json({ error: err.message });
  }
});

app.post(['/api/students/:telegram_id/revert-override', '/api/students/:telegram_id/revert-override/'], requireApiAuth, (req, res) => {
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
    const statusCode = err.message?.includes('Database connection error') ? 503 : 500;
    res.status(statusCode).json({ error: err.message });
  }
});

app.get(['/api/students/:telegram_id/absences', '/api/students/:telegram_id/absences/'], requireApiAuth, (req, res) => {
  try {
    const student = resolveStudent(req.params.telegram_id);
    if (!student) {
      return res.status(404).json({ error: 'Student not found' });
    }
    const absences = getStudentAbsences(student.student_id);
    res.json({ absences });
  } catch (err: any) {
    const statusCode = err.message?.includes('Database connection error') ? 503 : 500;
    res.status(statusCode).json({ error: err.message });
  }
});

app.get(['/api/attendance/:session_id/makeup-options', '/api/attendance/:session_id/makeup-options/'], requireApiAuth, (req, res) => {
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
    const statusCode = err.message?.includes('Database connection error') ? 503 : 500;
    res.status(statusCode).json({ error: err.message });
  }
});

app.post(['/api/attendance/:session_id/makeup', '/api/attendance/:session_id/makeup/'], requireApiAuth, (req, res) => {
  try {
    const sessionId = Number(req.params.session_id);
    const { student_telegram_id, makeup_session_id } = req.body;
    const student = resolveStudent(student_telegram_id);
    if (!student) {
      return res.status(404).json({ error: 'Student not found' });
    }
    if (!makeup_session_id) {
      return res.status(400).json({ error: 'makeup_session_id is required' });
    }
    const result = recordMakeup(student.student_id, sessionId, Number(makeup_session_id));
    res.json(result);
  } catch (err: any) {
    const statusCode = err.message?.includes('Database connection error') ? 503 : 500;
    res.status(statusCode).json({ error: err.message });
  }
});

app.get(['/api/students/:telegram_id/notification-settings', '/api/students/:telegram_id/notification-settings/'], requireApiAuth, (req, res) => {
  try {
    const student = resolveStudent(req.params.telegram_id);
    if (!student) {
      return res.status(404).json({ error: 'Student not found' });
    }
    const settings = getNotificationSettings(student.student_id);
    res.json(settings);
  } catch (err: any) {
    const statusCode = err.message?.includes('Database connection error') ? 503 : 500;
    res.status(statusCode).json({ error: err.message });
  }
});

app.patch(['/api/students/:telegram_id/notification-settings', '/api/students/:telegram_id/notification-settings/'], requireApiAuth, (req, res) => {
  try {
    const student = resolveStudent(req.params.telegram_id);
    if (!student) {
      return res.status(404).json({ error: 'Student not found' });
    }
    const { enabled, minutes_before } = req.body;
    const updated = updateNotificationSettings(student.student_id, enabled, minutes_before);
    res.json({ success: true, ...updated });
  } catch (err: any) {
    const statusCode = err.message?.includes('Database connection error') ? 503 : 500;
    res.status(statusCode).json({ error: err.message });
  }
});

// Internal bot endpoints
app.get(['/api/internal/upcoming-sessions', '/api/internal/upcoming-sessions/'], requireApiAuth, (req, res) => {
  try {
    const notifications = getUpcomingSessionsForScheduler();
    res.json({ notifications });
  } catch (err: any) {
    res.status(500).json({ error: err.message });
  }
});

app.post(['/api/internal/upcoming-sessions/mark-sent', '/api/internal/upcoming-sessions/mark-sent/'], requireApiAuth, (req, res) => {
  const { telegram_id, session_id } = req.body;
  if (!telegram_id || !session_id) {
    return res.status(400).json({ error: 'telegram_id and session_id are required' });
  }
  const result = markNotificationSent(Number(telegram_id), Number(session_id));
  res.json(result);
});

// ==========================================
// 6. Vite Middleware / Static Server
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
    console.log(`[Server] University Timetable API listening on http://0.0.0.0:${PORT}`);

    // Launch Telegram Bot client
    const botService = new TelegramBotService(
      BOT_TOKEN,
      `http://127.0.0.1:${PORT}`,
      API_KEY,
      APP_URL
    );
    botService.start().catch((err) => {
      console.warn('[Server] Telegram bot start error:', err.message);
    });
  });
}

startServer();

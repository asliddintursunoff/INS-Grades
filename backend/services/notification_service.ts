import { db } from '../db';

export function getNotificationSettings(studentId: string) {
  const settings = db.query(
    `SELECT enabled, minutes_before FROM notification_settings WHERE student_id = ?`,
    [studentId]
  ).rows[0];

  if (!settings) {
    return { enabled: true, minutes_before: 30 };
  }

  return {
    enabled: Boolean(settings.enabled),
    minutes_before: settings.minutes_before || 30,
  };
}

export function updateNotificationSettings(studentId: string, enabled?: boolean, minutesBefore?: number) {
  const existing = db.query(
    `SELECT student_id FROM notification_settings WHERE student_id = ?`,
    [studentId]
  ).rows[0];

  if (existing) {
    db.query(
      `UPDATE notification_settings 
       SET enabled = COALESCE(?, enabled), minutes_before = COALESCE(?, minutes_before)
       WHERE student_id = ?`,
      [enabled !== undefined ? (enabled ? 1 : 0) : null, minutesBefore ?? null, studentId]
    );
  } else {
    db.query(
      `INSERT INTO notification_settings (student_id, enabled, minutes_before) VALUES (?, ?, ?)`,
      [studentId, enabled !== undefined ? (enabled ? 1 : 0) : 1, minutesBefore || 30]
    );
  }

  return getNotificationSettings(studentId);
}

export function getUpcomingSessionsForScheduler() {
  const todayStr = new Date().toISOString().split('T')[0];
  const now = new Date();
  const currentMinutes = now.getHours() * 60 + now.getMinutes();

  // Find students who have enabled notifications and a linked telegram_id
  const students = db.query(
    `SELECT s.student_id, s.telegram_id, ns.minutes_before
     FROM students s
     JOIN notification_settings ns ON s.student_id = ns.student_id
     WHERE ns.enabled = 1 AND s.telegram_id IS NOT NULL`
  ).rows;

  const results: any[] = [];

  for (const student of students) {
    // Find sessions today for this student's enrolled classes
    const sessions = db.query(
      `SELECT 
         ls.session_id,
         ls.session_date,
         ls.start_time,
         ls.end_time,
         s.short_name AS subject_short,
         s.full_name AS subject_full,
         p.full_name AS professor,
         c.room
       FROM lecture_sessions ls
       JOIN classes c ON ls.class_id = c.class_id
       JOIN subjects s ON c.subject_id = s.subject_id
       JOIN professors p ON c.professor_id = p.professor_id
       JOIN student_class_enrollment sce ON sce.class_id = c.class_id AND sce.student_id = ? AND sce.status = 'active'
       WHERE ls.session_date = ?`,
      [student.student_id, todayStr]
    ).rows;

    for (const session of sessions) {
      const [sh, sm] = session.start_time.split(':').map(Number);
      const sessionMinutes = sh * 60 + (sm || 0);
      const diff = sessionMinutes - currentMinutes;

      // Check if it's within notification threshold (e.g. diff is <= minutes_before && diff > minutes_before - 5)
      // Or for testing, if diff is within window:
      if (diff <= student.minutes_before && diff >= 0) {
        // Check if already sent
        const alreadySent = db.query(
          `SELECT id FROM sent_notifications WHERE student_id = ? AND session_id = ?`,
          [student.student_id, session.session_id]
        ).rows.length > 0;

        if (!alreadySent) {
          results.push({
            telegram_id: student.telegram_id,
            session_id: session.session_id,
            subject_full: session.subject_full,
            subject_short: session.subject_short,
            professor: session.professor,
            room: session.room,
            start_time: session.start_time,
            end_time: session.end_time,
            minutes_before: student.minutes_before,
          });
        }
      }
    }
  }

  return results;
}

export function markNotificationSent(telegramId: number, sessionId: number) {
  const student = db.query(
    `SELECT student_id FROM students WHERE telegram_id = ?`,
    [telegramId]
  ).rows[0];

  if (!student) return { success: false, error: 'Student not found' };

  try {
    db.query(
      `INSERT OR IGNORE INTO sent_notifications (student_id, session_id) VALUES (?, ?)`,
      [student.student_id, sessionId]
    );
  } catch (e) {
    // ignore duplicate
  }

  return { success: true };
}

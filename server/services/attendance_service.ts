import { db } from '../db';
import { getEffectiveSchedule, hasTimeConflict } from './timetable_service';

export function getStudentAbsences(studentId: string) {
  const query = `
    SELECT 
      a.attendance_id,
      ls.session_id,
      s.short_name AS subject_short,
      s.full_name AS subject_full,
      ls.session_date,
      ls.start_time,
      ls.end_time,
      p.full_name AS professor,
      c.room,
      a.status,
      a.makeup_session_id
    FROM attendance a
    JOIN lecture_sessions ls ON a.session_id = ls.session_id
    JOIN classes c ON ls.class_id = c.class_id
    JOIN subjects s ON c.subject_id = s.subject_id
    JOIN professors p ON c.professor_id = p.professor_id
    WHERE a.student_id = ? AND a.status = 'absent'
    ORDER BY ls.session_date DESC
  `;
  return db.query(query, [studentId]).rows;
}

export function suggestMakeupSessions(studentId: string, missedSessionId: number) {
  // 1. Get missed session details
  const missed = db.query(
    `SELECT 
       ls.session_id,
       ls.session_date,
       ls.start_time,
       ls.end_time,
       c.class_id,
       c.subject_id,
       c.professor_id,
       c.group_id
     FROM lecture_sessions ls
     JOIN classes c ON ls.class_id = c.class_id
     WHERE ls.session_id = ?`,
    [missedSessionId]
  ).rows[0];

  if (!missed) {
    throw new Error('Sessiya topilmadi');
  }

  // 2. Get student details
  const student = db.query(
    `SELECT student_id, group_id FROM students WHERE student_id = ?`,
    [studentId]
  ).rows[0];

  if (!student) {
    throw new Error('Talaba topilmadi');
  }

  // 3. Find candidate future sessions for the SAME subject in OTHER groups
  const todayStr = new Date().toISOString().split('T')[0];
  const candidates = db.query(
    `SELECT 
       ls.session_id,
       ls.session_date,
       ls.start_time,
       ls.end_time,
       c.class_id,
       c.subject_id,
       c.professor_id,
       p.full_name AS professor,
       g.group_name,
       c.room
     FROM lecture_sessions ls
     JOIN classes c ON ls.class_id = c.class_id
     JOIN professors p ON c.professor_id = p.professor_id
     JOIN groups g ON c.group_id = g.group_id
     WHERE c.subject_id = ? 
       AND c.group_id != ?
       AND ls.session_date >= ?
     ORDER BY ls.session_date ASC`,
    [missed.subject_id, student.group_id, todayStr]
  ).rows;

  // 4. Filter by conflict with student's current timetable
  const effectiveSchedule = getEffectiveSchedule(studentId).schedule;

  const validCandidates = candidates.filter(cand => {
    const candDate = new Date(cand.session_date);
    // JS getDay(): 0=Sun, 1=Mon ... 6=Sat -> Convert to 1..7 (1=Mon)
    let dayOfWeek = candDate.getDay();
    if (dayOfWeek === 0) dayOfWeek = 7;

    const conflict = hasTimeConflict(effectiveSchedule, dayOfWeek, cand.start_time, cand.end_time);
    return !conflict.conflict;
  });

  // 5. Sort candidates:
  // 1) same professor first (cand.professor_id === missed.professor_id)
  // 2) date difference abs((cand.date - missed.date))
  // 3) time difference
  const missedDate = new Date(missed.session_date).getTime();
  const toMinutes = (t: string) => {
    const [h, m] = t.split(':').map(Number);
    return h * 60 + (m || 0);
  };
  const missedTime = toMinutes(missed.start_time);

  validCandidates.sort((a, b) => {
    const sameProfA = a.professor_id === missed.professor_id ? 0 : 1;
    const sameProfB = b.professor_id === missed.professor_id ? 0 : 1;
    if (sameProfA !== sameProfB) return sameProfA - sameProfB;

    const diffDateA = Math.abs(new Date(a.session_date).getTime() - missedDate);
    const diffDateB = Math.abs(new Date(b.session_date).getTime() - missedDate);
    if (diffDateA !== diffDateB) return diffDateA - diffDateB;

    const diffTimeA = Math.abs(toMinutes(a.start_time) - missedTime);
    const diffTimeB = Math.abs(toMinutes(b.start_time) - missedTime);
    return diffTimeA - diffTimeB;
  });

  const top5 = validCandidates.slice(0, 5);

  return top5.map((c, index) => ({
    session_id: c.session_id,
    rank: index + 1,
    same_professor: c.professor_id === missed.professor_id,
    professor: c.professor,
    group_name: c.group_name,
    session_date: c.session_date,
    start_time: c.start_time,
    end_time: c.end_time,
    room: c.room,
    recommended: index === 0,
  }));
}

export function recordMakeup(studentId: string, missedSessionId: number, makeupSessionId: number) {
  // Update attendance table
  db.query(
    `UPDATE attendance 
     SET status = 'made_up', makeup_session_id = ?
     WHERE student_id = ? AND session_id = ?`,
    [makeupSessionId, studentId, missedSessionId]
  );

  return {
    success: true,
    message: "Kelmagan darsingiz muvaffaqiyatli to'ldirildi",
  };
}

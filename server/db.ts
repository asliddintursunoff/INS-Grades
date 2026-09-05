import { Pool } from 'pg';
import dotenv from 'dotenv';

dotenv.config();

export class DatabaseManager {
  private pgPool: Pool | null = null;
  public isPostgres = false;
  private memoryStore: Record<string, any[]> = {};

  constructor() {
    this.initMemoryStore();
    this.initPostgres();
  }

  private async initPostgres() {
    const dbUrl = process.env.DATABASE_URL;
    if (dbUrl) {
      try {
        const pool = new Pool({
          connectionString: dbUrl,
          ssl: dbUrl.includes('railway.net') ? { rejectUnauthorized: false } : undefined,
          connectionTimeoutMillis: 3000,
        });

        const res = await pool.query('SELECT 1');
        if (res) {
          this.pgPool = pool;
          this.isPostgres = true;
          console.log('[DB] Connected to Railway PostgreSQL database successfully.');
        }
      } catch (err) {
        console.warn('[DB] Railway PostgreSQL not reachable yet. Using memory store.');
      }
    }
  }

  private initMemoryStore() {
    this.memoryStore = {
      professors: [
        { professor_id: 1, full_name: 'Prof. F. Atamurotov', email: 'atamurotov@university.uz' },
        { professor_id: 2, full_name: 'Prof. N. Karimov', email: 'karimov@university.uz' },
        { professor_id: 3, full_name: 'Prof. M. Siddiqov', email: 'siddiqov@university.uz' },
        { professor_id: 4, full_name: 'Prof. D. Umarova', email: 'umarova@university.uz' },
        { professor_id: 5, full_name: 'Prof. A. Rakhimov', email: 'rakhimov@university.uz' },
        { professor_id: 6, full_name: 'Prof. Z. Khusanov', email: 'khusanov@university.uz' },
        { professor_id: 7, full_name: 'Prof. S. Makhmudov', email: 'makhmudov@university.uz' },
        { professor_id: 8, full_name: 'Prof. G. Karimova', email: 'karimova@university.uz' },
        { professor_id: 9, full_name: 'Prof. T. Usmonov', email: 'usmonov@university.uz' },
        { professor_id: 10, full_name: 'Prof. L. Azizova', email: 'azizova@university.uz' },
      ],
      groups: [
        { group_id: 1, group_name: 'CIE26-3', timetable_image_url: 'https://images.unsplash.com/photo-1509062522246-3755977927d7' },
        { group_id: 2, group_name: 'CIE26-5', timetable_image_url: 'https://images.unsplash.com/photo-1523240795612-9a054b0db644' },
        { group_id: 3, group_name: 'CIE26-2', timetable_image_url: 'https://images.unsplash.com/photo-1516321318423-f06f85e504b3' },
        { group_id: 4, group_name: 'CIE26-1', timetable_image_url: 'https://images.unsplash.com/photo-1434030216411-0b793f4b4173' },
        { group_id: 5, group_name: 'CIE26-4', timetable_image_url: 'https://images.unsplash.com/photo-1524178232363-1fb2b075b655' },
        { group_id: 6, group_name: 'CSE25-1', timetable_image_url: 'https://images.unsplash.com/photo-1519452635265-7b1fbfd1e4e0' },
        { group_id: 7, group_name: 'CSE25-2', timetable_image_url: 'https://images.unsplash.com/photo-1497633762265-9d179a990aa6' },
        { group_id: 8, group_name: 'ECE25-1', timetable_image_url: 'https://images.unsplash.com/photo-1532094349884-543bc11b234d' },
      ],
      students: [
        { student_id: 'U2410252', full_name: 'Asliddin Xolmatov', group_id: 1, year_of_study: 2, telegram_id: 987654321, telegram_username: 'asliddin_dev' },
        { student_id: 'U2410253', full_name: 'Javohir Toshmatov', group_id: 1, year_of_study: 2, telegram_id: null, telegram_username: 'javohir_t' },
        { student_id: 'U2410254', full_name: 'Madina Alimova', group_id: 2, year_of_study: 2, telegram_id: null, telegram_username: 'madina_a' },
        { student_id: 'U2510101', full_name: 'Bekzod Rahimov', group_id: 4, year_of_study: 1, telegram_id: null, telegram_username: 'bekzod_r' },
      ],
      subjects: [
        { subject_id: 1, short_name: 'P1', full_name: 'Physics 1', year_level: 1 },
        { subject_id: 2, short_name: 'AE1', full_name: 'Academic English 1', year_level: 1 },
        { subject_id: 3, short_name: 'CS101', full_name: 'Computer Science 1', year_level: 1 },
        { subject_id: 4, short_name: 'M1', full_name: 'Calculus 1', year_level: 1 },
        { subject_id: 5, short_name: 'MATH102', full_name: 'Linear Algebra', year_level: 1 },
        { subject_id: 6, short_name: 'DM101', full_name: 'Discrete Mathematics', year_level: 1 },
        { subject_id: 7, short_name: 'CHEM101', full_name: 'General Chemistry', year_level: 1 },
        { subject_id: 8, short_name: 'CS201', full_name: 'Data Structures & Algorithms', year_level: 2 },
        { subject_id: 9, short_name: 'CS202', full_name: 'Object-Oriented Programming', year_level: 2 },
        { subject_id: 10, short_name: 'ECE201', full_name: 'Computer Architecture', year_level: 2 },
        { subject_id: 11, short_name: 'STAT201', full_name: 'Probability & Statistics', year_level: 2 },
        { subject_id: 12, short_name: 'CS203', full_name: 'Database Systems', year_level: 2 },
        { subject_id: 13, short_name: 'MATH201', full_name: 'Differential Equations', year_level: 2 },
        { subject_id: 14, short_name: 'CS301', full_name: 'Web Development & Cloud Systems', year_level: 3 },
        { subject_id: 15, short_name: 'CS302', full_name: 'Operating Systems', year_level: 3 },
      ],
      classes: [
        { class_id: 14, subject_id: 1, professor_id: 1, group_id: 1, room: 'A605' },
        { class_id: 22, subject_id: 1, professor_id: 1, group_id: 2, room: 'A605' },
        { class_id: 23, subject_id: 1, professor_id: 2, group_id: 3, room: 'B201' },
        { class_id: 24, subject_id: 1, professor_id: 1, group_id: 4, room: 'A605' },
        { class_id: 28, subject_id: 1, professor_id: 9, group_id: 5, room: 'A602' },
        { class_id: 15, subject_id: 2, professor_id: 2, group_id: 1, room: 'B201' },
        { class_id: 25, subject_id: 2, professor_id: 10, group_id: 2, room: 'B202' },
        { class_id: 29, subject_id: 2, professor_id: 10, group_id: 3, room: 'B203' },
        { class_id: 30, subject_id: 2, professor_id: 2, group_id: 4, room: 'B201' },
        { class_id: 31, subject_id: 2, professor_id: 10, group_id: 5, room: 'B204' },
        { class_id: 16, subject_id: 3, professor_id: 3, group_id: 1, room: 'C304' },
        { class_id: 26, subject_id: 3, professor_id: 3, group_id: 2, room: 'C305' },
        { class_id: 32, subject_id: 3, professor_id: 5, group_id: 3, room: 'C301' },
        { class_id: 33, subject_id: 3, professor_id: 3, group_id: 4, room: 'C302' },
        { class_id: 34, subject_id: 3, professor_id: 5, group_id: 5, room: 'C303' },
        { class_id: 17, subject_id: 4, professor_id: 4, group_id: 1, room: 'D102' },
        { class_id: 27, subject_id: 4, professor_id: 4, group_id: 2, room: 'D103' },
        { class_id: 35, subject_id: 4, professor_id: 7, group_id: 3, room: 'D104' },
        { class_id: 36, subject_id: 4, professor_id: 4, group_id: 4, room: 'D101' },
        { class_id: 37, subject_id: 4, professor_id: 7, group_id: 5, room: 'D105' },
        { class_id: 48, subject_id: 8, professor_id: 5, group_id: 1, room: 'C403' },
      ],
      group_timetable: [
        { slot_id: 1, group_id: 1, day_of_week: 1, start_time: '09:00', end_time: '10:30', class_id: 16 },
        { slot_id: 2, group_id: 1, day_of_week: 1, start_time: '10:45', end_time: '12:15', class_id: 17 },
        { slot_id: 3, group_id: 1, day_of_week: 2, start_time: '09:00', end_time: '10:00', class_id: 14 },
        { slot_id: 4, group_id: 1, day_of_week: 2, start_time: '10:15', end_time: '11:45', class_id: 15 },
        { slot_id: 5, group_id: 1, day_of_week: 3, start_time: '13:00', end_time: '14:30', class_id: 16 },
        { slot_id: 6, group_id: 1, day_of_week: 4, start_time: '09:00', end_time: '10:30', class_id: 17 },
        { slot_id: 7, group_id: 1, day_of_week: 5, start_time: '10:00', end_time: '11:30', class_id: 15 },
        { slot_id: 52, group_id: 1, day_of_week: 5, start_time: '13:00', end_time: '14:30', class_id: 48 },
      ],
      student_class_enrollment: [
        { enrollment_id: 1, student_id: 'U2410252', class_id: 14, status: 'active', enrolled_at: '2026-02-01T08:00:00', dropped_at: null },
        { enrollment_id: 2, student_id: 'U2410252', class_id: 15, status: 'active', enrolled_at: '2026-02-01T08:00:00', dropped_at: null },
        { enrollment_id: 3, student_id: 'U2410252', class_id: 16, status: 'active', enrolled_at: '2026-02-01T08:00:00', dropped_at: null },
        { enrollment_id: 4, student_id: 'U2410252', class_id: 17, status: 'active', enrolled_at: '2026-02-01T08:00:00', dropped_at: null },
        { enrollment_id: 5, student_id: 'U2410252', class_id: 48, status: 'active', enrolled_at: '2026-02-01T08:00:00', dropped_at: null },
      ],
      student_schedule_overrides: [],
      notification_settings: [
        { student_id: 'U2410252', enabled: 1, minutes_before: 30 },
      ],
      lecture_sessions: [
        { session_id: 501, class_id: 14, session_date: '2026-03-01', start_time: '09:00', end_time: '10:00' },
        { session_id: 610, class_id: 22, session_date: '2026-03-05', start_time: '10:00', end_time: '11:00' },
      ],
      attendance: [
        { attendance_id: 1, student_id: 'U2410252', session_id: 501, status: 'absent', makeup_session_id: null },
      ],
    };
  }

  public query(sql: string, params: any[] = []): { rows: any[] } {
    const rows = this.queryMemory(sql, params);
    if (this.pgPool) {
      let idx = 1;
      const pgSql = sql.replace(/\?/g, () => `$${idx++}`);
      this.pgPool.query(pgSql, params).catch(() => {});
    }
    return { rows };
  }

  public execute(sql: string, params: any[] = []): { changes: number; lastInsertRowid?: number } {
    if (this.pgPool) {
      let idx = 1;
      const pgSql = sql.replace(/\?/g, () => `$${idx++}`);
      this.pgPool.query(pgSql, params).catch(() => {});
    }
    return { changes: 1 };
  }

  private queryMemory(sql: string, params: any[] = []): any[] {
    const s = sql.toUpperCase();

    if (s.includes('COUNT(*) AS C FROM STUDENTS') || s.includes('COUNT(*) AS C')) {
      if (s.includes('FROM CLASSES')) return [{ c: this.memoryStore.classes.length }];
      return [{ c: this.memoryStore.students.length }];
    }

    if (s.includes('FROM STUDENTS S') && s.includes('ORDER BY S.STUDENT_ID')) {
      return this.memoryStore.students.map((st) => {
        const grp = this.memoryStore.groups.find((g) => g.group_id === st.group_id);
        return { ...st, group_name: grp?.group_name || 'CIE26-3' };
      });
    }

    if (s.includes('FROM STUDENTS S') && s.includes('TELEGRAM_ID = ?')) {
      const tgId = Number(params[0]);
      const st = this.memoryStore.students.find((x) => x.telegram_id === tgId);
      if (st) {
        const grp = this.memoryStore.groups.find((g) => g.group_id === st.group_id);
        return [{ ...st, group_name: grp?.group_name || 'CIE26-3' }];
      }
      return [];
    }

    if (s.includes('FROM STUDENTS S') && (s.includes('STUDENT_ID) = UPPER(?)') || s.includes('STUDENT_ID = ?'))) {
      const sid = String(params[0]).toUpperCase();
      const st = this.memoryStore.students.find((x) => x.student_id.toUpperCase() === sid);
      if (st) {
        const grp = this.memoryStore.groups.find((g) => g.group_id === st.group_id);
        return [{ ...st, group_name: grp?.group_name || 'CIE26-3' }];
      }
      return [];
    }

    if (s.includes('FROM STUDENTS S') && s.includes('LIMIT 1')) {
      const st = this.memoryStore.students[0];
      const grp = this.memoryStore.groups.find((g) => g.group_id === st.group_id);
      return [{ ...st, group_name: grp?.group_name || 'CIE26-3' }];
    }

    if (s.includes('FROM GROUP_TIMETABLE GT')) {
      const grpId = Number(params[0]) || 1;
      return this.memoryStore.group_timetable
        .filter((gt) => gt.group_id === grpId)
        .map((gt) => {
          const cls = this.memoryStore.classes.find((c) => c.class_id === gt.class_id);
          const sub = this.memoryStore.subjects.find((sb) => sb.subject_id === cls?.subject_id);
          const prof = this.memoryStore.professors.find((p) => p.professor_id === cls?.professor_id);
          const grp = this.memoryStore.groups.find((g) => g.group_id === gt.group_id);
          return {
            slot_id: gt.slot_id,
            day_of_week: gt.day_of_week,
            start_time: gt.start_time,
            end_time: gt.end_time,
            class_id: cls?.class_id || 14,
            subject_id: sub?.subject_id || 1,
            subject_short: sub?.short_name || 'CS',
            subject_full: sub?.full_name || 'Computer Science',
            professor: prof?.full_name || 'Prof. Faculty',
            room: cls?.room || 'A605',
            original_group: grp?.group_name || 'CIE26-3',
            actual_group: grp?.group_name || 'CIE26-3',
          };
        });
    }

    if (s.includes('FROM STUDENT_CLASS_ENROLLMENT E')) {
      return this.memoryStore.student_class_enrollment.map((e) => {
        const cls = this.memoryStore.classes.find((c) => c.class_id === e.class_id);
        const sub = this.memoryStore.subjects.find((sb) => sb.subject_id === cls?.subject_id);
        const prof = this.memoryStore.professors.find((p) => p.professor_id === cls?.professor_id);
        const grp = this.memoryStore.groups.find((g) => g.group_id === cls?.group_id);
        return {
          class_id: cls?.class_id,
          subject_id: sub?.subject_id,
          subject_short: sub?.short_name,
          subject_full: sub?.full_name,
          year_level: sub?.year_level || 1,
          professor: prof?.full_name,
          group_name: grp?.group_name,
          room: cls?.room,
          status: e.status,
          enrolled_at: e.enrolled_at,
          dropped_at: e.dropped_at,
        };
      });
    }

    if (s.includes('FROM ATTENDANCE A')) {
      return this.memoryStore.attendance.map((a) => {
        const sess = this.memoryStore.lecture_sessions.find((ls) => ls.session_id === a.session_id);
        const cls = this.memoryStore.classes.find((c) => c.class_id === sess?.class_id);
        const sub = this.memoryStore.subjects.find((s) => s.subject_id === cls?.subject_id);
        const prof = this.memoryStore.professors.find((p) => p.professor_id === cls?.professor_id);
        return {
          attendance_id: a.attendance_id,
          session_id: a.session_id,
          subject_short: sub?.short_name || 'P1',
          subject_full: sub?.full_name || 'Physics 1',
          session_date: sess?.session_date || '2026-03-01',
          start_time: sess?.start_time || '09:00',
          end_time: sess?.end_time || '10:00',
          professor: prof?.full_name || 'Prof. F. Atamurotov',
          room: cls?.room || 'A605',
          status: a.status,
          makeup_session_id: a.makeup_session_id,
        };
      });
    }

    if (s.includes('FROM NOTIFICATION_SETTINGS')) {
      return this.memoryStore.notification_settings;
    }

    if (s.includes('FROM SUBJECTS')) {
      return this.memoryStore.subjects;
    }

    if (s.includes('FROM CLASSES')) {
      return this.memoryStore.classes;
    }

    return [];
  }
}

export const db = new DatabaseManager();

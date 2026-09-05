import Database from 'better-sqlite3';
import { Pool } from 'pg';
import path from 'path';
import fs from 'fs';
import dotenv from 'dotenv';

dotenv.config();

export class DatabaseManager {
  private sqliteDb: Database.Database | null = null;
  private pgPool: Pool | null = null;
  public isPostgres = false;

  constructor() {
    this.init();
  }

  private init() {
    const dbUrl = process.env.DATABASE_URL;

    // Persistent local directory for SQLite
    const dataDir = path.join(process.cwd(), 'data');
    if (!fs.existsSync(dataDir)) {
      fs.mkdirSync(dataDir, { recursive: true });
    }

    const sqlitePath = path.join(dataDir, 'timetable.db');
    this.sqliteDb = new Database(sqlitePath);
    this.sqliteDb.pragma('journal_mode = WAL');
    this.sqliteDb.pragma('foreign_keys = ON');

    // Attempt PostgreSQL if URL provided
    if (dbUrl) {
      try {
        const pool = new Pool({
          connectionString: dbUrl,
          ssl: { rejectUnauthorized: false },
          connectionTimeoutMillis: 2000,
        });

        pool.on('error', () => {
          // Handled silently for background connection issues
        });

        pool.query('SELECT NOW()', (err) => {
          if (err) {
            this.isPostgres = false;
            this.pgPool = null;
            pool.end().catch(() => {});
            console.log('[DB] PostgreSQL unavailable. Using persistent SQLite database engine.');
          } else {
            console.log('[DB] Connected successfully to PostgreSQL on Railway!');
            this.pgPool = pool;
            this.isPostgres = true;
          }
        });
      } catch (err: any) {
        this.isPostgres = false;
        this.pgPool = null;
      }
    }

    this.initSchema();
    this.seedData();
  }

  public query(sql: string, params: any[] = []): { rows: any[]; rowCount: number } {
    if (this.sqliteDb) {
      let paramIndex = 1;
      const normalizedSql = sql.replace(/\$\d+/g, () => '?');
      const isSelect = /^\s*(SELECT|PRAGMA)/i.test(normalizedSql);

      if (isSelect) {
        const stmt = this.sqliteDb.prepare(normalizedSql);
        const rows = stmt.all(...params);
        return { rows, rowCount: rows.length };
      } else {
        const stmt = this.sqliteDb.prepare(normalizedSql);
        const info = stmt.run(...params);
        return { rows: [], rowCount: info.changes };
      }
    }
    return { rows: [], rowCount: 0 };
  }

  private initSchema() {
    if (!this.sqliteDb) return;

    this.sqliteDb.exec(`
      CREATE TABLE IF NOT EXISTS professors (
        professor_id INTEGER PRIMARY KEY AUTOINCREMENT,
        full_name TEXT NOT NULL,
        email TEXT UNIQUE
      );

      CREATE TABLE IF NOT EXISTS groups (
        group_id INTEGER PRIMARY KEY AUTOINCREMENT,
        group_name TEXT NOT NULL UNIQUE,
        timetable_image_url TEXT
      );

      CREATE TABLE IF NOT EXISTS students (
        student_id TEXT PRIMARY KEY,
        full_name TEXT NOT NULL,
        group_id INTEGER NOT NULL REFERENCES groups(group_id),
        year_of_study INTEGER NOT NULL DEFAULT 2,
        telegram_id INTEGER UNIQUE,
        telegram_username TEXT
      );

      CREATE TABLE IF NOT EXISTS subjects (
        subject_id INTEGER PRIMARY KEY AUTOINCREMENT,
        short_name TEXT NOT NULL,
        full_name TEXT NOT NULL,
        year_level INTEGER NOT NULL DEFAULT 1
      );

      CREATE TABLE IF NOT EXISTS classes (
        class_id INTEGER PRIMARY KEY AUTOINCREMENT,
        subject_id INTEGER NOT NULL REFERENCES subjects(subject_id),
        professor_id INTEGER NOT NULL REFERENCES professors(professor_id),
        group_id INTEGER NOT NULL REFERENCES groups(group_id),
        room TEXT
      );

      CREATE TABLE IF NOT EXISTS group_timetable (
        slot_id INTEGER PRIMARY KEY AUTOINCREMENT,
        group_id INTEGER NOT NULL REFERENCES groups(group_id),
        day_of_week INTEGER NOT NULL CHECK (day_of_week BETWEEN 1 AND 7),
        start_time TEXT NOT NULL,
        end_time TEXT NOT NULL,
        class_id INTEGER NOT NULL REFERENCES classes(class_id)
      );

      CREATE TABLE IF NOT EXISTS student_schedule_overrides (
        override_id INTEGER PRIMARY KEY AUTOINCREMENT,
        student_id TEXT NOT NULL REFERENCES students(student_id),
        day_of_week INTEGER NOT NULL CHECK (day_of_week BETWEEN 1 AND 7),
        start_time TEXT NOT NULL,
        end_time TEXT NOT NULL,
        class_id INTEGER NOT NULL REFERENCES classes(class_id),
        valid_from TEXT,
        valid_to TEXT
      );

      CREATE TABLE IF NOT EXISTS student_class_enrollment (
        enrollment_id INTEGER PRIMARY KEY AUTOINCREMENT,
        student_id TEXT NOT NULL REFERENCES students(student_id),
        class_id INTEGER NOT NULL REFERENCES classes(class_id),
        status TEXT NOT NULL DEFAULT 'active',
        enrolled_at TEXT DEFAULT CURRENT_TIMESTAMP,
        dropped_at TEXT NULL,
        UNIQUE (student_id, class_id)
      );

      CREATE TABLE IF NOT EXISTS homeworks (
        homework_id INTEGER PRIMARY KEY AUTOINCREMENT,
        class_id INTEGER NOT NULL REFERENCES classes(class_id),
        title TEXT NOT NULL,
        description TEXT,
        deadline TEXT NOT NULL
      );

      CREATE TABLE IF NOT EXISTS homework_submissions (
        submission_id INTEGER PRIMARY KEY AUTOINCREMENT,
        homework_id INTEGER NOT NULL REFERENCES homeworks(homework_id),
        student_id TEXT NOT NULL REFERENCES students(student_id),
        is_done INTEGER DEFAULT 0,
        is_active INTEGER DEFAULT 1,
        submitted_at TEXT NULL,
        grade REAL NULL,
        UNIQUE (homework_id, student_id)
      );

      CREATE TABLE IF NOT EXISTS lecture_sessions (
        session_id INTEGER PRIMARY KEY AUTOINCREMENT,
        class_id INTEGER NOT NULL REFERENCES classes(class_id),
        session_date TEXT NOT NULL,
        start_time TEXT NOT NULL,
        end_time TEXT NOT NULL,
        UNIQUE (class_id, session_date)
      );

      CREATE TABLE IF NOT EXISTS attendance (
        attendance_id INTEGER PRIMARY KEY AUTOINCREMENT,
        student_id TEXT NOT NULL REFERENCES students(student_id),
        session_id INTEGER NOT NULL REFERENCES lecture_sessions(session_id),
        status TEXT NOT NULL DEFAULT 'absent',
        makeup_session_id INTEGER NULL REFERENCES lecture_sessions(session_id),
        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
        UNIQUE (student_id, session_id)
      );

      CREATE TABLE IF NOT EXISTS notification_settings (
        student_id TEXT PRIMARY KEY REFERENCES students(student_id),
        enabled INTEGER DEFAULT 1,
        minutes_before INTEGER DEFAULT 30
      );

      CREATE TABLE IF NOT EXISTS sent_notifications (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        student_id TEXT NOT NULL,
        session_id INTEGER NOT NULL,
        sent_at TEXT DEFAULT CURRENT_TIMESTAMP,
        UNIQUE (student_id, session_id)
      );
    `);

    // Migrations for existing DB files
    try {
      this.sqliteDb.exec('ALTER TABLE students ADD COLUMN year_of_study INTEGER NOT NULL DEFAULT 2;');
    } catch {}
    try {
      this.sqliteDb.exec('ALTER TABLE subjects ADD COLUMN year_level INTEGER NOT NULL DEFAULT 1;');
    } catch {}
  }

  public seedData() {
    if (!this.sqliteDb) return;

    console.log('[DB] Seeding/Verifying comprehensive university timetable & classes...');

    // 1. Professors
    const professors = [
      { id: 1, name: 'Prof. F. Atamurotov', email: 'atamurotov@university.uz' },
      { id: 2, name: 'Prof. N. Karimov', email: 'karimov@university.uz' },
      { id: 3, name: 'Prof. M. Siddiqov', email: 'siddiqov@university.uz' },
      { id: 4, name: 'Prof. D. Umarova', email: 'umarova@university.uz' },
      { id: 5, name: 'Prof. A. Rakhimov', email: 'rakhimov@university.uz' },
      { id: 6, name: 'Prof. Z. Khusanov', email: 'khusanov@university.uz' },
      { id: 7, name: 'Prof. S. Makhmudov', email: 'makhmudov@university.uz' },
      { id: 8, name: 'Prof. G. Karimova', email: 'karimova@university.uz' },
      { id: 9, name: 'Prof. T. Usmonov', email: 'usmonov@university.uz' },
      { id: 10, name: 'Prof. L. Azizova', email: 'azizova@university.uz' },
    ];
    for (const p of professors) {
      this.sqliteDb.prepare(
        'INSERT OR REPLACE INTO professors (professor_id, full_name, email) VALUES (?, ?, ?)'
      ).run(p.id, p.name, p.email);
    }

    // 2. Groups
    const groups = [
      { id: 1, name: 'CIE26-3', img: 'https://images.unsplash.com/photo-1509062522246-3755977927d7?auto=format&fit=crop&w=1200&q=80' },
      { id: 2, name: 'CIE26-5', img: 'https://images.unsplash.com/photo-1523240795612-9a054b0db644?auto=format&fit=crop&w=1200&q=80' },
      { id: 3, name: 'CIE26-2', img: 'https://images.unsplash.com/photo-1516321318423-f06f85e504b3?auto=format&fit=crop&w=1200&q=80' },
      { id: 4, name: 'CIE26-1', img: 'https://images.unsplash.com/photo-1434030216411-0b793f4b4173?auto=format&fit=crop&w=1200&q=80' },
      { id: 5, name: 'CIE26-4', img: 'https://images.unsplash.com/photo-1524178232363-1fb2b075b655?auto=format&fit=crop&w=1200&q=80' },
      { id: 6, name: 'CSE25-1', img: 'https://images.unsplash.com/photo-1519452635265-7b1fbfd1e4e0?auto=format&fit=crop&w=1200&q=80' },
      { id: 7, name: 'CSE25-2', img: 'https://images.unsplash.com/photo-1497633762265-9d179a990aa6?auto=format&fit=crop&w=1200&q=80' },
      { id: 8, name: 'ECE25-1', img: 'https://images.unsplash.com/photo-1532094349884-543bc11b234d?auto=format&fit=crop&w=1200&q=80' },
    ];
    for (const g of groups) {
      this.sqliteDb.prepare(
        'INSERT OR REPLACE INTO groups (group_id, group_name, timetable_image_url) VALUES (?, ?, ?)'
      ).run(g.id, g.name, g.img);
    }

    // 3. Students
    const students = [
      { id: 'U2410252', name: 'Asliddin Xolmatov', group_id: 1, year: 2, tg_id: 987654321, tg_user: 'asliddin_dev' },
      { id: 'U2410253', name: 'Javohir Toshmatov', group_id: 1, year: 2, tg_id: null, tg_user: 'javohir_t' },
      { id: 'U2410254', name: 'Madina Alimova', group_id: 2, year: 2, tg_id: null, tg_user: 'madina_a' },
      { id: 'U2510101', name: 'Bekzod Rahimov', group_id: 4, year: 1, tg_id: null, tg_user: 'bekzod_r' },
    ];
    for (const s of students) {
      this.sqliteDb.prepare(
        'INSERT OR REPLACE INTO students (student_id, full_name, group_id, year_of_study, telegram_id, telegram_username) VALUES (?, ?, ?, ?, ?, ?)'
      ).run(s.id, s.name, s.group_id, s.year, s.tg_id, s.tg_user);
    }

    // 4. Subjects (spanned across Year 1, Year 2, and Year 3)
    const subjects = [
      // Year 1
      { id: 1, short: 'P1', full: 'Physics 1', year: 1 },
      { id: 2, short: 'AE1', full: 'Academic English 1', year: 1 },
      { id: 3, short: 'CS101', full: 'Computer Science 1', year: 1 },
      { id: 4, short: 'M1', full: 'Calculus 1', year: 1 },
      { id: 5, short: 'MATH102', full: 'Linear Algebra', year: 1 },
      { id: 6, short: 'DM101', full: 'Discrete Mathematics', year: 1 },
      { id: 7, short: 'CHEM101', full: 'General Chemistry', year: 1 },
      // Year 2
      { id: 8, short: 'CS201', full: 'Data Structures & Algorithms', year: 2 },
      { id: 9, short: 'CS202', full: 'Object-Oriented Programming', year: 2 },
      { id: 10, short: 'ECE201', full: 'Computer Architecture', year: 2 },
      { id: 11, short: 'STAT201', full: 'Probability & Statistics', year: 2 },
      { id: 12, short: 'CS203', full: 'Database Systems', year: 2 },
      { id: 13, short: 'MATH201', full: 'Differential Equations', year: 2 },
      // Year 3
      { id: 14, short: 'CS301', full: 'Web Development & Cloud Systems', year: 3 },
      { id: 15, short: 'CS302', full: 'Operating Systems', year: 3 },
    ];
    for (const sub of subjects) {
      this.sqliteDb.prepare(
        'INSERT OR REPLACE INTO subjects (subject_id, short_name, full_name, year_level) VALUES (?, ?, ?, ?)'
      ).run(sub.id, sub.short, sub.full, sub.year);
    }

    // 5. Classes (richly populated across groups)
    const classes = [
      // P1 (Subject 1)
      { id: 14, sub: 1, prof: 1, grp: 1, room: 'A605' }, // CIE26-3
      { id: 22, sub: 1, prof: 1, grp: 2, room: 'A605' }, // CIE26-5
      { id: 23, sub: 1, prof: 2, grp: 3, room: 'B201' }, // CIE26-2
      { id: 24, sub: 1, prof: 1, grp: 4, room: 'A605' }, // CIE26-1
      { id: 28, sub: 1, prof: 9, grp: 5, room: 'A602' }, // CIE26-4

      // AE1 (Subject 2)
      { id: 15, sub: 2, prof: 2, grp: 1, room: 'B201' }, // CIE26-3
      { id: 25, sub: 2, prof: 10, grp: 2, room: 'B202' }, // CIE26-5
      { id: 29, sub: 2, prof: 10, grp: 3, room: 'B203' }, // CIE26-2
      { id: 30, sub: 2, prof: 2, grp: 4, room: 'B201' }, // CIE26-1
      { id: 31, sub: 2, prof: 10, grp: 5, room: 'B204' }, // CIE26-4

      // CS101 (Subject 3)
      { id: 16, sub: 3, prof: 3, grp: 1, room: 'C304' }, // CIE26-3
      { id: 26, sub: 3, prof: 3, grp: 2, room: 'C305' }, // CIE26-5
      { id: 32, sub: 3, prof: 5, grp: 3, room: 'C301' }, // CIE26-2
      { id: 33, sub: 3, prof: 3, grp: 4, room: 'C302' }, // CIE26-1
      { id: 34, sub: 3, prof: 5, grp: 5, room: 'C303' }, // CIE26-4

      // M1 (Subject 4)
      { id: 17, sub: 4, prof: 4, grp: 1, room: 'D102' }, // CIE26-3
      { id: 27, sub: 4, prof: 4, grp: 2, room: 'D103' }, // CIE26-5
      { id: 35, sub: 4, prof: 7, grp: 3, room: 'D104' }, // CIE26-2
      { id: 36, sub: 4, prof: 4, grp: 4, room: 'D101' }, // CIE26-1
      { id: 37, sub: 4, prof: 7, grp: 5, room: 'D105' }, // CIE26-4

      // Linear Algebra (Subject 5)
      { id: 38, sub: 5, prof: 4, grp: 4, room: 'D101' }, // CIE26-1
      { id: 39, sub: 5, prof: 7, grp: 3, room: 'D102' }, // CIE26-2
      { id: 40, sub: 5, prof: 4, grp: 5, room: 'D103' }, // CIE26-4

      // Discrete Mathematics (Subject 6)
      { id: 41, sub: 6, prof: 7, grp: 4, room: 'C302' }, // CIE26-1
      { id: 42, sub: 6, prof: 7, grp: 3, room: 'C303' }, // CIE26-2
      { id: 43, sub: 6, prof: 3, grp: 2, room: 'C304' }, // CIE26-5

      // General Chemistry (Subject 7)
      { id: 44, sub: 7, prof: 9, grp: 4, room: 'Lab2' }, // CIE26-1
      { id: 45, sub: 7, prof: 9, grp: 5, room: 'Lab3' }, // CIE26-4

      // Year 2 Courses
      // CS201: Data Structures & Algorithms (Subject 8)
      { id: 46, sub: 8, prof: 5, grp: 6, room: 'C401' }, // CSE25-1
      { id: 47, sub: 8, prof: 5, grp: 7, room: 'C402' }, // CSE25-2
      { id: 48, sub: 8, prof: 5, grp: 1, room: 'C403' }, // CIE26-3

      // CS202: OOP (Subject 9)
      { id: 49, sub: 9, prof: 3, grp: 6, room: 'C404' }, // CSE25-1
      { id: 50, sub: 9, prof: 3, grp: 7, room: 'C405' }, // CSE25-2

      // ECE201: Computer Architecture (Subject 10)
      { id: 51, sub: 10, prof: 6, grp: 8, room: 'E201' }, // ECE25-1
      { id: 52, sub: 10, prof: 6, grp: 6, room: 'E202' }, // CSE25-1

      // STAT201: Probability & Statistics (Subject 11)
      { id: 53, sub: 11, prof: 7, grp: 6, room: 'D201' }, // CSE25-1
      { id: 54, sub: 11, prof: 7, grp: 7, room: 'D202' }, // CSE25-2

      // CS203: Database Systems (Subject 12)
      { id: 55, sub: 12, prof: 8, grp: 6, room: 'C406' }, // CSE25-1
      { id: 56, sub: 12, prof: 8, grp: 7, room: 'C407' }, // CSE25-2

      // MATH201: Differential Equations (Subject 13)
      { id: 57, sub: 13, prof: 4, grp: 6, room: 'D203' }, // CSE25-1
      { id: 58, sub: 13, prof: 4, grp: 8, room: 'D204' }, // ECE25-1
    ];
    for (const c of classes) {
      this.sqliteDb.prepare(
        'INSERT OR REPLACE INTO classes (class_id, subject_id, professor_id, group_id, room) VALUES (?, ?, ?, ?, ?)'
      ).run(c.id, c.sub, c.prof, c.grp, c.room);
    }

    // 6. Group Timetable Slots (Diverse days and times for rich rescheduling)
    const timetableSlots = [
      // CIE26-3 (Group 1 - Asliddin's Primary Schedule)
      { id: 1, grp: 1, day: 1, start: '09:00', end: '10:30', cls: 16 }, // Mon CS101
      { id: 2, grp: 1, day: 1, start: '10:45', end: '12:15', cls: 17 }, // Mon M1
      { id: 3, grp: 1, day: 2, start: '09:00', end: '10:00', cls: 14 }, // Tue P1
      { id: 4, grp: 1, day: 2, start: '10:15', end: '11:45', cls: 15 }, // Tue AE1
      { id: 5, grp: 1, day: 3, start: '13:00', end: '14:30', cls: 16 }, // Wed CS101
      { id: 6, grp: 1, day: 4, start: '09:00', end: '10:30', cls: 17 }, // Thu M1
      { id: 7, grp: 1, day: 5, start: '10:00', end: '11:30', cls: 15 }, // Fri AE1
      { id: 52, grp: 1, day: 5, start: '13:00', end: '14:30', cls: 48 }, // Fri CS201 Lab (CIE26-3)
      { id: 53, grp: 1, day: 3, start: '10:45', end: '12:15', cls: 17 }, // Wed M1 Session (CIE26-3)

      // CIE26-5 (Group 2)
      { id: 8, grp: 2, day: 2, start: '10:00', end: '11:00', cls: 22 }, // Tue P1
      { id: 9, grp: 2, day: 3, start: '09:00', end: '10:30', cls: 25 }, // Wed AE1
      { id: 10, grp: 2, day: 4, start: '13:00', end: '14:30', cls: 26 }, // Thu CS101
      { id: 11, grp: 2, day: 5, start: '09:00', end: '10:30', cls: 27 }, // Fri M1
      { id: 12, grp: 2, day: 1, start: '14:45', end: '16:15', cls: 43 }, // Mon DM101

      // CIE26-2 (Group 3)
      { id: 13, grp: 3, day: 2, start: '09:00', end: '10:00', cls: 23 }, // Tue P1
      { id: 14, grp: 3, day: 3, start: '14:45', end: '16:15', cls: 29 }, // Wed AE1
      { id: 15, grp: 3, day: 4, start: '10:45', end: '12:15', cls: 32 }, // Thu CS101
      { id: 16, grp: 3, day: 5, start: '13:00', end: '14:30', cls: 35 }, // Fri M1
      { id: 17, grp: 3, day: 1, start: '13:00', end: '14:30', cls: 39 }, // Mon Linear Algebra
      { id: 18, grp: 3, day: 4, start: '14:45', end: '16:15', cls: 42 }, // Thu DM101

      // CIE26-1 (Group 4)
      { id: 19, grp: 4, day: 3, start: '13:30', end: '14:30', cls: 24 }, // Wed P1
      { id: 20, grp: 4, day: 1, start: '10:45', end: '12:15', cls: 30 }, // Mon AE1
      { id: 21, grp: 4, day: 2, start: '13:00', end: '14:30', cls: 33 }, // Tue CS101
      { id: 22, grp: 4, day: 4, start: '14:45', end: '16:15', cls: 36 }, // Thu M1
      { id: 23, grp: 4, day: 5, start: '09:00', end: '10:30', cls: 38 }, // Fri Linear Algebra
      { id: 24, grp: 4, day: 2, start: '14:45', end: '16:15', cls: 41 }, // Tue DM101
      { id: 25, grp: 4, day: 3, start: '10:45', end: '12:15', cls: 44 }, // Wed Chemistry

      // CIE26-4 (Group 5)
      { id: 26, grp: 5, day: 4, start: '13:00', end: '14:00', cls: 28 }, // Thu P1
      { id: 27, grp: 5, day: 1, start: '14:45', end: '16:15', cls: 31 }, // Mon AE1
      { id: 28, grp: 5, day: 3, start: '09:00', end: '10:30', cls: 34 }, // Wed CS101
      { id: 29, grp: 5, day: 2, start: '16:30', end: '18:00', cls: 37 }, // Tue M1
      { id: 30, grp: 5, day: 5, start: '14:45', end: '16:15', cls: 40 }, // Fri Linear Algebra
      { id: 31, grp: 5, day: 2, start: '10:45', end: '12:15', cls: 45 }, // Tue Chemistry

      // CSE25-1 (Year 2 Group 6)
      { id: 32, grp: 6, day: 1, start: '14:45', end: '16:15', cls: 46 }, // Mon CS201 Data Structures
      { id: 33, grp: 6, day: 2, start: '13:00', end: '14:30', cls: 49 }, // Tue CS202 OOP
      { id: 34, grp: 6, day: 3, start: '10:45', end: '12:15', cls: 52 }, // Wed ECE201 Arch
      { id: 35, grp: 6, day: 4, start: '13:00', end: '14:30', cls: 53 }, // Thu STAT201 Stats
      { id: 36, grp: 6, day: 5, start: '13:00', end: '14:30', cls: 55 }, // Fri CS203 Databases
      { id: 37, grp: 6, day: 2, start: '14:45', end: '16:15', cls: 57 }, // Tue MATH201 Diff Eq

      // CSE25-2 (Year 2 Group 7)
      { id: 38, grp: 7, day: 2, start: '14:45', end: '16:15', cls: 47 }, // Tue CS201 Data Structures
      { id: 39, grp: 7, day: 3, start: '14:45', end: '16:15', cls: 50 }, // Wed CS202 OOP
      { id: 40, grp: 7, day: 4, start: '10:45', end: '12:15', cls: 54 }, // Thu STAT201 Stats
      { id: 41, grp: 7, day: 5, start: '14:45', end: '16:15', cls: 56 }, // Fri CS203 Databases

      // ECE25-1 (Year 2 Group 8)
      { id: 42, grp: 8, day: 1, start: '13:00', end: '14:30', cls: 51 }, // Mon ECE201 Arch
      { id: 43, grp: 8, day: 4, start: '14:45', end: '16:15', cls: 58 }, // Thu MATH201 Diff Eq

      // 2nd Lecture Sessions (demonstrating multi-session classes: 2 times/week)
      { id: 44, grp: 1, day: 4, start: '13:00', end: '14:00', cls: 14 }, // Thu P1 Session 2 (CIE26-3)
      { id: 45, grp: 3, day: 4, start: '13:00', end: '14:00', cls: 23 }, // Thu P1 Session 2 (CIE26-2)
      { id: 46, grp: 4, day: 5, start: '10:45', end: '11:45', cls: 24 }, // Fri P1 Session 2 (CIE26-1)
      { id: 47, grp: 3, day: 3, start: '10:45', end: '12:15', cls: 39 }, // Wed Linear Algebra Session 2 (CIE26-2)
      { id: 48, grp: 6, day: 3, start: '14:45', end: '16:15', cls: 46 }, // Wed CS201 Data Structures Session 2 (CSE25-1)
      { id: 49, grp: 7, day: 4, start: '14:45', end: '16:15', cls: 47 }, // Thu CS201 Data Structures Session 2 (CSE25-2)
      { id: 50, grp: 6, day: 5, start: '14:45', end: '16:15', cls: 49 }, // Fri CS202 OOP Session 2 (CSE25-1)
      { id: 51, grp: 7, day: 5, start: '09:00', end: '10:30', cls: 50 }, // Fri CS202 OOP Session 2 (CSE25-2)
    ];
    for (const slot of timetableSlots) {
      this.sqliteDb.prepare(
        'INSERT OR REPLACE INTO group_timetable (slot_id, group_id, day_of_week, start_time, end_time, class_id) VALUES (?, ?, ?, ?, ?, ?)'
      ).run(slot.id, slot.grp, slot.day, slot.start, slot.end, slot.cls);
    }

    // 7. Base Student Class Enrollments for U2410252
    const baseEnrollments = [14, 15, 16, 17];
    for (const clsId of baseEnrollments) {
      this.sqliteDb.prepare(
        "INSERT OR IGNORE INTO student_class_enrollment (student_id, class_id, status) VALUES ('U2410252', ?, 'active')"
      ).run(clsId);
    }

    // 8. Notification Settings
    this.sqliteDb.prepare(
      "INSERT OR IGNORE INTO notification_settings (student_id, enabled, minutes_before) VALUES ('U2410252', 1, 30)"
    ).run();

    // 9. Homeworks & Submissions
    const futureDate1 = new Date(Date.now() + 3 * 24 * 3600 * 1000).toISOString();
    const futureDate2 = new Date(Date.now() + 5 * 24 * 3600 * 1000).toISOString();
    const pastDate = new Date(Date.now() - 2 * 24 * 3600 * 1000).toISOString();

    const homeworksList = [
      { id: 1, cls: 14, title: 'Lab 1: Kinematics & Vectors', desc: 'Submit written laboratory analysis and calculation sheets', dl: futureDate1 },
      { id: 2, cls: 14, title: 'Problem Set 2: Newton Laws', desc: 'Solve exercises 7 through 15 from Chapter 4', dl: futureDate2 },
      { id: 3, cls: 14, title: 'Physics Quiz 1 Review', desc: 'Pre-quiz concept review on thermodynamics and forces', dl: pastDate },
      { id: 4, cls: 15, title: 'Essay 1: Academic Argumentation', desc: '500-word critical evaluation on technological ethics', dl: futureDate1 },
      { id: 5, cls: 16, title: 'Project 1: Python Data Processor', desc: 'Build a modular CLI program parsing structured CSV datasets', dl: futureDate2 },
      { id: 6, cls: 17, title: 'Calculus Assignment: Derivatives', desc: 'Complete problems on chain rule and implicit differentiation', dl: futureDate1 },
      { id: 7, cls: 46, title: 'DSA Lab: Balanced Binary Trees', desc: 'Implement AVL tree rebalancing algorithms in C++', dl: futureDate2 },
      { id: 8, cls: 55, title: 'SQL Milestone: Schema Normalization', desc: 'Design 3NF relational database schema with constraints', dl: futureDate2 },
    ];
    for (const hw of homeworksList) {
      this.sqliteDb.prepare(
        'INSERT OR REPLACE INTO homeworks (homework_id, class_id, title, description, deadline) VALUES (?, ?, ?, ?, ?)'
      ).run(hw.id, hw.cls, hw.title, hw.desc, hw.dl);
    }

    const submissions = [
      { hw: 1, st: 'U2410252', done: 0, active: 1 },
      { hw: 2, st: 'U2410252', done: 0, active: 1 },
      { hw: 3, st: 'U2410252', done: 1, active: 1 },
      { hw: 4, st: 'U2410252', done: 0, active: 1 },
      { hw: 5, st: 'U2410252', done: 0, active: 1 },
      { hw: 6, st: 'U2410252', done: 0, active: 1 },
    ];
    for (const sub of submissions) {
      this.sqliteDb.prepare(
        'INSERT OR IGNORE INTO homework_submissions (homework_id, student_id, is_done, is_active) VALUES (?, ?, ?, ?)'
      ).run(sub.hw, sub.st, sub.done, sub.active);
    }

    // 10. Lecture Sessions & Attendance
    const today = new Date();
    const formatDate = (d: Date) => d.toISOString().split('T')[0];
    const pastDateStr = formatDate(new Date(today.getTime() - 2 * 24 * 3600 * 1000));
    const futureDateStr1 = formatDate(new Date(today.getTime() + 1 * 24 * 3600 * 1000));
    const futureDateStr2 = formatDate(new Date(today.getTime() + 3 * 24 * 3600 * 1000));
    const futureDateStr3 = formatDate(new Date(today.getTime() + 4 * 24 * 3600 * 1000));

    const sessions = [
      { id: 501, cls: 14, date: pastDateStr, s: '09:00', e: '10:00' },
      { id: 610, cls: 22, date: futureDateStr1, s: '10:00', e: '11:00' },
      { id: 615, cls: 24, date: futureDateStr2, s: '13:30', e: '14:30' },
      { id: 620, cls: 23, date: futureDateStr3, s: '09:00', e: '10:00' },
    ];
    for (const sess of sessions) {
      this.sqliteDb.prepare(
        'INSERT OR REPLACE INTO lecture_sessions (session_id, class_id, session_date, start_time, end_time) VALUES (?, ?, ?, ?, ?)'
      ).run(sess.id, sess.cls, sess.date, sess.s, sess.e);
    }

    this.sqliteDb.prepare(
      "INSERT OR IGNORE INTO attendance (attendance_id, student_id, session_id, status) VALUES (1, 'U2410252', 501, 'absent')"
    ).run();

    console.log('[DB] Seeding completed successfully with extensive classes dataset.');
  }
}

export const db = new DatabaseManager();

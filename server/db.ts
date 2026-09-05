import { Pool } from 'pg';
import dotenv from 'dotenv';

dotenv.config();

export class DatabaseManager {
  private pgPool: Pool | null = null;
  public isConnected = false;
  public lastError: string | null = null;
  private cache: Record<string, any[]> = {
    professors: [],
    groups: [],
    students: [],
    subjects: [],
    classes: [],
    group_timetable: [],
    student_class_enrollment: [],
    student_schedule_overrides: [],
    notification_settings: [],
    lecture_sessions: [],
    attendance: [],
  };

  constructor() {
    this.initPostgres();
  }

  public async initPostgres() {
    const dbUrl = process.env.DATABASE_URL || process.env.DATABASE_PUBLIC_URL;
    const pghost = process.env.PGHOST;
    const pguser = process.env.PGUSER || 'postgres';
    const pgpass = process.env.PGPASSWORD;
    const pgport = parseInt(process.env.PGPORT || '5432', 10);
    const pgdb = process.env.PGDATABASE || 'railway';

    if (!dbUrl && (!pghost || !pgpass)) {
      this.isConnected = false;
      this.lastError = 'Database connection error: DATABASE_URL environment variable is missing. Please configure DATABASE_URL.';
      console.warn('[DB] ' + this.lastError);
      return;
    }

    const candidatePools: { desc: string; pool: Pool }[] = [];

    // Candidate 1: Explicit PG* variables if provided
    if (pghost && pgpass) {
      candidatePools.push({
        desc: `Railway PG* env vars (${pghost}:${pgport})`,
        pool: new Pool({
          host: pghost,
          port: pgport,
          user: pguser,
          password: pgpass,
          database: pgdb,
          ssl: pghost.includes('railway.internal') ? false : { rejectUnauthorized: false },
          connectionTimeoutMillis: 4000,
        }),
      });
    }

    // Candidate 2: Parsed DATABASE_URL with decodeURIComponent
    if (dbUrl) {
      try {
        const parsed = new URL(dbUrl.startsWith('postgres://') ? dbUrl.replace('postgres://', 'postgresql://') : dbUrl);
        const host = parsed.hostname;
        const port = parseInt(parsed.port || '5432', 10);
        const user = decodeURIComponent(parsed.username || 'postgres');
        const pass = decodeURIComponent(parsed.password || '');
        const dbname = parsed.pathname.replace(/^\//, '') || 'railway';
        const isInternal = host.includes('railway.internal') || host.includes('localhost');

        candidatePools.push({
          desc: `Parsed DATABASE_URL (host=${host}:${port}, user=${user})`,
          pool: new Pool({
            host,
            port,
            user,
            password: pass,
            database: dbname,
            ssl: isInternal ? false : { rejectUnauthorized: false },
            connectionTimeoutMillis: 4000,
          }),
        });
      } catch (pe) {
        // Ignore URL parse error
      }

      // Candidate 3: Raw connectionString
      candidatePools.push({
        desc: 'Direct connectionString',
        pool: new Pool({
          connectionString: dbUrl,
          ssl: dbUrl.includes('railway.net') ? { rejectUnauthorized: false } : undefined,
          connectionTimeoutMillis: 4000,
        }),
      });
    }

    let lastErr: any = null;
    for (const cand of candidatePools) {
      try {
        const res = await cand.pool.query('SELECT 1');
        if (res) {
          this.pgPool = cand.pool;
          this.isConnected = true;
          this.lastError = null;
          console.log(`[DB] Connected to Railway PostgreSQL successfully via ${cand.desc}.`);
          await this.syncCacheFromPostgres();
          return;
        }
      } catch (err: any) {
        lastErr = err;
        await cand.pool.end().catch(() => {});
      }
    }

    this.isConnected = false;
    this.lastError = `Database connection error: Could not connect to Railway PostgreSQL database across ${candidatePools.length} methods. Detail: ${lastErr?.message || lastErr}`;
    console.error('[DB] ' + this.lastError);
  }

  public async syncCacheFromPostgres() {
    if (!this.pgPool) return;
    try {
      const tables = [
        'professors',
        'groups',
        'students',
        'subjects',
        'classes',
        'group_timetable',
        'student_class_enrollment',
        'student_schedule_overrides',
        'notification_settings',
        'lecture_sessions',
        'attendance',
      ];

      for (const t of tables) {
        try {
          const r = await this.pgPool.query(`SELECT * FROM ${t}`);
          this.cache[t] = r.rows || [];
        } catch {
          this.cache[t] = [];
        }
      }
      console.log('[DB] Synchronized live data from PostgreSQL into cache.');
    } catch (e: any) {
      console.error('[DB] Failed to sync cache:', e);
    }
  }

  public query(sql: string, params: any[] = []): { rows: any[] } {
    if (!this.isConnected || !this.pgPool) {
      throw new Error(
        this.lastError ||
        'Database connection error: Railway PostgreSQL is not connected. Please verify DATABASE_URL.'
      );
    }

    // Direct background sync with pool if available
    if (this.pgPool) {
      let idx = 1;
      const pgSql = sql.replace(/\?/g, () => `$${idx++}`);
      this.pgPool.query(pgSql, params).catch((err) => {
        console.error('[DB] Async PG query error:', err.message);
      });
    }

    const rows = this.queryCached(sql, params);
    return { rows };
  }

  public async queryAsync(sql: string, params: any[] = []): Promise<any[]> {
    if (!this.isConnected || !this.pgPool) {
      throw new Error(
        this.lastError ||
        'Database connection error: Railway PostgreSQL is not connected. Please verify DATABASE_URL.'
      );
    }
    let idx = 1;
    const pgSql = sql.replace(/\?/g, () => `$${idx++}`);
    const res = await this.pgPool.query(pgSql, params);
    return res.rows || [];
  }

  public execute(sql: string, params: any[] = []): { changes: number; lastInsertRowid?: number } {
    if (!this.isConnected || !this.pgPool) {
      throw new Error(
        this.lastError ||
        'Database connection error: Railway PostgreSQL is not connected. Please verify DATABASE_URL.'
      );
    }

    if (this.pgPool) {
      let idx = 1;
      const pgSql = sql.replace(/\?/g, () => `$${idx++}`);
      this.pgPool.query(pgSql, params).then(() => {
        this.syncCacheFromPostgres().catch(() => {});
      }).catch((err) => {
        console.error('[DB] Async PG execute error:', err.message);
      });
    }

    return { changes: 1 };
  }

  public async executeAsync(sql: string, params: any[] = []): Promise<number> {
    if (!this.isConnected || !this.pgPool) {
      throw new Error(
        this.lastError ||
        'Database connection error: Railway PostgreSQL is not connected. Please verify DATABASE_URL.'
      );
    }
    let idx = 1;
    const pgSql = sql.replace(/\?/g, () => `$${idx++}`);
    const res = await this.pgPool.query(pgSql, params);
    return res.rowCount || 0;
  }

  private queryCached(sql: string, params: any[] = []): any[] {
    const s = sql.toUpperCase();

    if (s.includes('COUNT(*) AS C FROM STUDENTS') || s.includes('COUNT(*) AS C')) {
      if (s.includes('FROM CLASSES')) return [{ c: (this.cache.classes || []).length }];
      return [{ c: (this.cache.students || []).length }];
    }

    if (s.includes('FROM STUDENTS S') && s.includes('ORDER BY S.STUDENT_ID')) {
      return (this.cache.students || []).map((st) => {
        const grp = (this.cache.groups || []).find((g) => g.group_id === st.group_id);
        return { ...st, group_name: grp?.group_name || '' };
      });
    }

    if (s.includes('FROM STUDENTS S') && s.includes('TELEGRAM_ID = ?')) {
      const tgId = Number(params[0]);
      const st = (this.cache.students || []).find((x) => x.telegram_id === tgId);
      if (st) {
        const grp = (this.cache.groups || []).find((g) => g.group_id === st.group_id);
        return [{ ...st, group_name: grp?.group_name || '' }];
      }
      return [];
    }

    if (s.includes('FROM STUDENTS S') && (s.includes('STUDENT_ID) = UPPER(?)') || s.includes('STUDENT_ID = ?'))) {
      const sid = String(params[0]).toUpperCase();
      const st = (this.cache.students || []).find((x) => x.student_id?.toUpperCase() === sid);
      if (st) {
        const grp = (this.cache.groups || []).find((g) => g.group_id === st.group_id);
        return [{ ...st, group_name: grp?.group_name || '' }];
      }
      return [];
    }

    if (s.includes('FROM GROUP_TIMETABLE GT')) {
      const grpId = Number(params[0]) || 1;
      return (this.cache.group_timetable || [])
        .filter((gt) => gt.group_id === grpId)
        .map((gt) => {
          const cls = (this.cache.classes || []).find((c) => c.class_id === gt.class_id);
          const sub = (this.cache.subjects || []).find((sb) => sb.subject_id === cls?.subject_id);
          const prof = (this.cache.professors || []).find((p) => p.professor_id === cls?.professor_id);
          const grp = (this.cache.groups || []).find((g) => g.group_id === gt.group_id);
          return {
            slot_id: gt.slot_id,
            day_of_week: gt.day_of_week,
            start_time: gt.start_time,
            end_time: gt.end_time,
            class_id: cls?.class_id,
            subject_id: sub?.subject_id,
            subject_short: sub?.short_name || '',
            subject_full: sub?.full_name || '',
            professor: prof?.full_name || '',
            room: cls?.room || '',
            original_group: grp?.group_name || '',
            actual_group: grp?.group_name || '',
          };
        });
    }

    if (s.includes('FROM STUDENT_CLASS_ENROLLMENT E')) {
      const studentId = params[0] ? String(params[0]).toUpperCase() : '';
      return (this.cache.student_class_enrollment || [])
        .filter((e) => !studentId || e.student_id?.toUpperCase() === studentId)
        .map((e) => {
          const cls = (this.cache.classes || []).find((c) => c.class_id === e.class_id);
          const sub = (this.cache.subjects || []).find((sb) => sb.subject_id === cls?.subject_id);
          const prof = (this.cache.professors || []).find((p) => p.professor_id === cls?.professor_id);
          const grp = (this.cache.groups || []).find((g) => g.group_id === cls?.group_id);
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
      return (this.cache.attendance || []).map((a) => {
        const sess = (this.cache.lecture_sessions || []).find((ls) => ls.session_id === a.session_id);
        const cls = (this.cache.classes || []).find((c) => c.class_id === sess?.class_id);
        const sub = (this.cache.subjects || []).find((sb) => sb.subject_id === cls?.subject_id);
        const prof = (this.cache.professors || []).find((p) => p.professor_id === cls?.professor_id);
        return {
          attendance_id: a.attendance_id,
          session_id: a.session_id,
          subject_short: sub?.short_name || '',
          subject_full: sub?.full_name || '',
          session_date: sess?.session_date || '',
          start_time: sess?.start_time || '',
          end_time: sess?.end_time || '',
          professor: prof?.full_name || '',
          room: cls?.room || '',
          status: a.status,
          makeup_session_id: a.makeup_session_id,
        };
      });
    }

    if (s.includes('FROM NOTIFICATION_SETTINGS')) {
      return this.cache.notification_settings || [];
    }

    if (s.includes('FROM SUBJECTS')) {
      return this.cache.subjects || [];
    }

    if (s.includes('FROM CLASSES')) {
      return this.cache.classes || [];
    }

    return [];
  }
}

export const db = new DatabaseManager();

import { db } from '../db';

export function getStudentClasses(studentId: string) {
  const query = `
    SELECT 
      c.class_id,
      s.subject_id,
      s.short_name AS subject_short,
      s.full_name AS subject_full,
      COALESCE(s.year_level, 1) AS year_level,
      p.full_name AS professor,
      g.group_name,
      c.room,
      e.status,
      e.enrolled_at,
      e.dropped_at
    FROM student_class_enrollment e
    JOIN classes c ON e.class_id = c.class_id
    JOIN subjects s ON c.subject_id = s.subject_id
    JOIN professors p ON c.professor_id = p.professor_id
    JOIN groups g ON c.group_id = g.group_id
    WHERE e.student_id = ?
    ORDER BY 
      CASE WHEN e.status = 'active' THEN 0 ELSE 1 END,
      e.enrolled_at DESC
  `;
  const allRows = db.query(query, [studentId]).rows;
  
  // Deduplicate: Each unique subject_id MUST appear only once in the Courses view!
  const subjectMap = new Map<number, any>();
  for (const row of allRows) {
    if (!subjectMap.has(row.subject_id)) {
      subjectMap.set(row.subject_id, row);
    }
  }
  return Array.from(subjectMap.values()).sort((a, b) => a.subject_full.localeCompare(b.subject_full));
}

export function dropClass(studentId: string, classId: number) {
  // 1. Find subject_id
  const cls = db.query('SELECT subject_id FROM classes WHERE class_id = ?', [classId]).rows[0];
  const now = new Date().toISOString();

  if (cls) {
    // Drop all enrollment rows for this subject
    db.query(
      `UPDATE student_class_enrollment 
       SET status = 'dropped', dropped_at = ? 
       WHERE student_id = ? AND class_id IN (SELECT class_id FROM classes WHERE subject_id = ?)`,
      [now, studentId, cls.subject_id]
    );

    // Remove any schedule override for this subject so it is removed from the timetable
    db.query(
      `DELETE FROM student_schedule_overrides 
       WHERE student_id = ? AND class_id IN (SELECT class_id FROM classes WHERE subject_id = ?)`,
      [studentId, cls.subject_id]
    );
  } else {
    db.query(
      `UPDATE student_class_enrollment 
       SET status = 'dropped', dropped_at = ? 
       WHERE student_id = ? AND class_id = ?`,
      [now, studentId, classId]
    );
  }

  // 3. Cascade to homework submissions: deactivate submissions where deadline > now
  const homeworks = db.query(
    `SELECT h.homework_id 
     FROM homeworks h
     JOIN homework_submissions hs ON h.homework_id = hs.homework_id
     WHERE h.class_id = ? AND hs.student_id = ? AND h.deadline > ?`,
    [classId, studentId, now]
  ).rows;

  if (homeworks.length > 0) {
    const hwIds = homeworks.map((h) => h.homework_id);
    const placeholders = hwIds.map(() => '?').join(',');
    db.query(
      `UPDATE homework_submissions 
       SET is_active = 0 
       WHERE student_id = ? AND homework_id IN (${placeholders})`,
      [studentId, ...hwIds]
    );
  }

  return {
    success: true,
    message: 'Course successfully dropped',
    removed_homeworks_count: homeworks.length,
  };
}

export function retakeClass(studentId: string, classId: number) {
  // 1. Update enrollment status to active
  db.query(
    `UPDATE student_class_enrollment 
     SET status = 'active', dropped_at = NULL 
     WHERE student_id = ? AND class_id = ?`,
    [studentId, classId]
  );

  const student = db.query('SELECT group_id FROM students WHERE student_id = ?', [studentId]).rows[0];
  const cls = db.query('SELECT class_id, group_id, subject_id FROM classes WHERE class_id = ?', [classId]).rows[0];

  // If class is from a different group, ensure schedule slot is present in student_schedule_overrides
  if (student && cls && student.group_id !== cls.group_id) {
    const slots = db.query(
      `SELECT day_of_week, start_time, end_time FROM group_timetable WHERE class_id = ?`,
      [classId]
    ).rows;
    for (const slot of slots) {
      db.query(
        `INSERT INTO student_schedule_overrides (student_id, day_of_week, start_time, end_time, class_id)
         VALUES (?, ?, ?, ?, ?)`,
        [studentId, slot.day_of_week, slot.start_time, slot.end_time, classId]
      );
    }
  }

  // 2. Cascade to homework submissions: restore submissions where deadline > now
  const now = new Date().toISOString();
  const openHomeworks = db.query(
    `SELECT homework_id 
     FROM homeworks 
     WHERE class_id = ? AND deadline > ?`,
    [classId, now]
  ).rows;

  let restoredCount = 0;
  for (const hw of openHomeworks) {
    const existing = db.query(
      `SELECT submission_id FROM homework_submissions WHERE homework_id = ? AND student_id = ?`,
      [hw.homework_id, studentId]
    ).rows;

    if (existing.length > 0) {
      db.query(
        `UPDATE homework_submissions SET is_active = 1 WHERE submission_id = ?`,
        [existing[0].submission_id]
      );
      restoredCount++;
    } else {
      db.query(
        `INSERT INTO homework_submissions (homework_id, student_id, is_done, is_active) VALUES (?, ?, 0, 1)`,
        [hw.homework_id, studentId]
      );
      restoredCount++;
    }
  }

  return {
    success: true,
    message: 'Course successfully re-enrolled',
    restored_homeworks_count: restoredCount,
  };
}

export function getRetakeCatalog(studentId: string) {
  const student = db.query(
    `SELECT student_id, full_name, group_id, COALESCE(year_of_study, 2) AS year_of_study FROM students WHERE student_id = ?`,
    [studentId]
  ).rows[0];

  if (!student) {
    throw new Error(`Student ${studentId} not found`);
  }

  const userYear = Number(student.year_of_study) || 2;
  // Available course years: all academic year levels <= user's year
  // e.g. Year 2 student can take Year 1 (lower) or Year 2 (current)
  const availableYears: number[] = [];
  for (let y = 1; y <= userYear; y++) {
    availableYears.push(y);
  }

  const placeholders = availableYears.map(() => '?').join(',');
  const subjects = db.query(
    `SELECT 
       s.subject_id,
       s.short_name,
       s.full_name,
       COALESCE(s.year_level, 1) AS year_level
     FROM subjects s
     WHERE COALESCE(s.year_level, 1) IN (${placeholders})
     ORDER BY s.year_level ASC, s.full_name ASC`,
    availableYears
  ).rows;

  // Check enrollment status for each subject for this student
  const activeEnrollments = db.query(
    `SELECT c.subject_id, e.status, e.class_id 
     FROM student_class_enrollment e
     JOIN classes c ON e.class_id = c.class_id
     WHERE e.student_id = ?`,
    [studentId]
  ).rows;

  const subjectEnrollmentMap: Record<number, { status: string; class_id: number }> = {};
  for (const row of activeEnrollments) {
    // If student has multiple enrollments, prefer 'active'
    if (!subjectEnrollmentMap[row.subject_id] || row.status === 'active') {
      subjectEnrollmentMap[row.subject_id] = {
        status: row.status,
        class_id: row.class_id,
      };
    }
  }

  const enrichedSubjects = subjects.map((sub) => {
    const enr = subjectEnrollmentMap[sub.subject_id];
    return {
      subject_id: sub.subject_id,
      short_name: sub.short_name,
      full_name: sub.full_name,
      year_level: sub.year_level,
      enrollment_status: enr ? enr.status : 'none',
      is_enrolled: enr ? enr.status === 'active' : false,
      current_class_id: enr ? enr.class_id : null,
    };
  });

  return {
    student_id: student.student_id,
    student_name: student.full_name,
    student_year: userYear,
    available_years: availableYears,
    subjects: enrichedSubjects,
  };
}

export function enrollRetakeClass(studentId: string, classId: number) {
  const cls = db.query(
    `SELECT c.class_id, c.subject_id, c.group_id, s.full_name AS subject_name, s.short_name
     FROM classes c
     JOIN subjects s ON c.subject_id = s.subject_id
     WHERE c.class_id = ?`,
    [classId]
  ).rows[0];

  if (!cls) {
    throw new Error('Selected class section was not found');
  }

  const student = db.query('SELECT student_id, group_id FROM students WHERE student_id = ?', [studentId]).rows[0];
  if (!student) {
    throw new Error('Student not found');
  }

  // 1. Update or Insert enrollment
  const existingEnrollment = db.query(
    `SELECT enrollment_id FROM student_class_enrollment WHERE student_id = ? AND class_id = ?`,
    [studentId, classId]
  ).rows;

  if (existingEnrollment.length > 0) {
    db.query(
      `UPDATE student_class_enrollment SET status = 'active', dropped_at = NULL WHERE student_id = ? AND class_id = ?`,
      [studentId, classId]
    );
  } else {
    // If student had an enrollment in ANOTHER class for the same subject, deactivate it
    const sameSubjectEnrollments = db.query(
      `SELECT e.class_id FROM student_class_enrollment e
       JOIN classes c ON e.class_id = c.class_id
       WHERE e.student_id = ? AND c.subject_id = ?`,
      [studentId, cls.subject_id]
    ).rows;
    for (const se of sameSubjectEnrollments) {
      db.query(`UPDATE student_class_enrollment SET status = 'dropped' WHERE student_id = ? AND class_id = ?`, [studentId, se.class_id]);
    }

    db.query(
      `INSERT INTO student_class_enrollment (student_id, class_id, status) VALUES (?, ?, 'active')`,
      [studentId, classId]
    );
  }

  // 2. Clear old schedule overrides for this subject
  db.query(
    `DELETE FROM student_schedule_overrides 
     WHERE student_id = ? AND class_id IN (SELECT class_id FROM classes WHERE subject_id = ?)`,
    [studentId, cls.subject_id]
  );

  // 3. If class is not in student's base group, add to student_schedule_overrides
  const slots = db.query(
    `SELECT day_of_week, start_time, end_time FROM group_timetable WHERE class_id = ?`,
    [classId]
  ).rows;

  for (const slot of slots) {
    db.query(
      `INSERT INTO student_schedule_overrides (student_id, day_of_week, start_time, end_time, class_id)
       VALUES (?, ?, ?, ?, ?)`,
      [studentId, slot.day_of_week, slot.start_time, slot.end_time, classId]
    );
  }

  // 4. Cascade active homeworks for this class
  const now = new Date().toISOString();
  const openHomeworks = db.query(
    `SELECT homework_id FROM homeworks WHERE class_id = ? AND deadline > ?`,
    [classId, now]
  ).rows;

  let assignedCount = 0;
  for (const hw of openHomeworks) {
    const exists = db.query(
      `SELECT submission_id FROM homework_submissions WHERE homework_id = ? AND student_id = ?`,
      [hw.homework_id, studentId]
    ).rows;
    if (exists.length > 0) {
      db.query(`UPDATE homework_submissions SET is_active = 1 WHERE submission_id = ?`, [exists[0].submission_id]);
    } else {
      db.query(`INSERT INTO homework_submissions (homework_id, student_id, is_done, is_active) VALUES (?, ?, 0, 1)`, [hw.homework_id, studentId]);
    }
    assignedCount++;
  }

  return {
    success: true,
    message: `Successfully registered for retake course: ${cls.subject_name} (${cls.short_name})`,
    assigned_homeworks_count: assignedCount,
  };
}

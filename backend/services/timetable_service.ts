import { db } from '../db';

const DAY_NAMES: Record<number, string> = {
  1: 'Monday',
  2: 'Tuesday',
  3: 'Wednesday',
  4: 'Thursday',
  5: 'Friday',
  6: 'Saturday',
  7: 'Sunday',
};

const DAY_SHORT: Record<number, string> = {
  1: 'Mon',
  2: 'Tue',
  3: 'Wed',
  4: 'Thu',
  5: 'Fri',
  6: 'Sat',
  7: 'Sun',
};

export interface ScheduleItem {
  day_of_week: number;
  day_name: string;
  start_time: string;
  end_time: string;
  subject_id: number;
  subject_short: string;
  subject_full: string;
  professor: string;
  room: string;
  class_id: number;
  is_changed: boolean;
  is_one_time?: boolean;
  make_up_note?: string;
  reverts_next_week?: boolean;
  original_group: string;
  actual_group: string;
  session_number?: number;
  total_sessions?: number;
}

export function getEffectiveSchedule(studentId: string) {
  // 1. Get student info
  const student = db.query(
    `SELECT s.student_id, s.full_name, s.group_id, g.group_name, g.timetable_image_url
     FROM students s
     JOIN groups g ON s.group_id = g.group_id
     WHERE s.student_id = ?`,
    [studentId]
  ).rows[0];

  if (!student) {
    throw new Error(`Student not found: ${studentId}`);
  }

  // 2. Get base group timetable slots for the student's primary group
  const baseSlots = db.query(
    `SELECT 
       gt.slot_id,
       gt.day_of_week,
       gt.start_time,
       gt.end_time,
       c.class_id,
       s.subject_id,
       s.short_name AS subject_short,
       s.full_name AS subject_full,
       p.full_name AS professor,
       c.room,
       g.group_name AS original_group,
       g.group_name AS actual_group
     FROM group_timetable gt
     JOIN classes c ON gt.class_id = c.class_id
     JOIN subjects s ON c.subject_id = s.subject_id
     JOIN professors p ON c.professor_id = p.professor_id
     JOIN groups g ON gt.group_id = g.group_id
     WHERE gt.group_id = ?
       AND NOT EXISTS (
         SELECT 1 FROM student_class_enrollment sce 
         WHERE sce.student_id = ? AND sce.class_id = c.class_id AND sce.status = 'dropped'
       )
     ORDER BY gt.day_of_week, gt.start_time`,
    [student.group_id, studentId]
  ).rows;

  // 3. Get extra enrolled classes outside base group (e.g. retakes or electives)
  const extraEnrolledSlots = db.query(
    `SELECT 
       gt.slot_id,
       gt.day_of_week,
       gt.start_time,
       gt.end_time,
       c.class_id,
       s.subject_id,
       s.short_name AS subject_short,
       s.full_name AS subject_full,
       p.full_name AS professor,
       c.room,
       g.group_name AS original_group,
       g.group_name AS actual_group
     FROM student_class_enrollment sce
     JOIN classes c ON sce.class_id = c.class_id
     JOIN group_timetable gt ON gt.class_id = c.class_id
     JOIN subjects s ON c.subject_id = s.subject_id
     JOIN professors p ON c.professor_id = p.professor_id
     JOIN groups g ON c.group_id = g.group_id
     WHERE sce.student_id = ? AND sce.status = 'active' AND c.group_id != ?
     ORDER BY gt.day_of_week, gt.start_time`,
    [studentId, student.group_id]
  ).rows;

  // 4. Get one-time make-up overrides
  const overrides = db.query(
    `SELECT 
       sso.override_id,
       sso.day_of_week,
       sso.start_time,
       sso.end_time,
       c.class_id,
       s.subject_id,
       s.short_name AS subject_short,
       s.full_name AS subject_full,
       p.full_name AS professor,
       c.room,
       g.group_name AS actual_group
     FROM student_schedule_overrides sso
     JOIN classes c ON sso.class_id = c.class_id
     JOIN subjects s ON c.subject_id = s.subject_id
     JOIN professors p ON c.professor_id = p.professor_id
     JOIN groups g ON c.group_id = g.group_id
     WHERE sso.student_id = ?
     ORDER BY sso.day_of_week, sso.start_time`,
    [studentId]
  ).rows;

  // Map and merge: base slots overridden by subject
  const overriddenSubjectIds = new Set(overrides.map((o) => o.subject_id));
  const extraSubjectIds = new Set(extraEnrolledSlots.map((s) => s.subject_id));
  const schedule: ScheduleItem[] = [];

  // Add base slots that are not overridden by a one-time make-up AND not replaced by permanent section
  for (const slot of baseSlots) {
    if (!overriddenSubjectIds.has(slot.subject_id) && !extraSubjectIds.has(slot.subject_id)) {
      schedule.push({
        day_of_week: slot.day_of_week,
        day_name: DAY_NAMES[slot.day_of_week] || `Day ${slot.day_of_week}`,
        start_time: slot.start_time,
        end_time: slot.end_time,
        subject_id: slot.subject_id,
        subject_short: slot.subject_short,
        subject_full: slot.subject_full,
        professor: slot.professor,
        room: slot.room,
        class_id: slot.class_id,
        is_changed: false,
        is_one_time: false,
        original_group: student.group_name,
        actual_group: slot.actual_group,
      });
    }
  }

  // Add extra enrolled slots (permanently changed sections or retakes) that are not overridden
  for (const slot of extraEnrolledSlots) {
    if (!overriddenSubjectIds.has(slot.subject_id)) {
      const isPermanentChange = slot.actual_group !== student.group_name;
      schedule.push({
        day_of_week: slot.day_of_week,
        day_name: DAY_NAMES[slot.day_of_week] || `Day ${slot.day_of_week}`,
        start_time: slot.start_time,
        end_time: slot.end_time,
        subject_id: slot.subject_id,
        subject_short: slot.subject_short,
        subject_full: slot.subject_full,
        professor: slot.professor,
        room: slot.room,
        class_id: slot.class_id,
        is_changed: isPermanentChange,
        is_one_time: false,
        reverts_next_week: false,
        make_up_note: isPermanentChange ? `Permanent section (${slot.actual_group})` : undefined,
        original_group: student.group_name,
        actual_group: slot.actual_group,
      });
    }
  }

  // Add overrides (one-time make-up slots for current week)
  for (const o of overrides) {
    schedule.push({
      day_of_week: o.day_of_week,
      day_name: DAY_NAMES[o.day_of_week] || `Day ${o.day_of_week}`,
      start_time: o.start_time,
      end_time: o.end_time,
      subject_id: o.subject_id,
      subject_short: o.subject_short,
      subject_full: o.subject_full,
      professor: o.professor,
      room: o.room,
      class_id: o.class_id,
      is_changed: true,
      is_one_time: true,
      reverts_next_week: true,
      make_up_note: 'One-time make-up (this week only)',
      original_group: student.group_name,
      actual_group: o.actual_group,
    });
  }

  // Sort chronologically by day and start time
  schedule.sort((a, b) => {
    if (a.day_of_week !== b.day_of_week) return a.day_of_week - b.day_of_week;
    return a.start_time.localeCompare(b.start_time);
  });

  // Calculate session numbers for multi-session subjects (e.g. Session 1 of 2)
  const subjectSlotsCount: Record<number, number> = {};
  for (const item of schedule) {
    subjectSlotsCount[item.subject_id] = (subjectSlotsCount[item.subject_id] || 0) + 1;
  }

  const subjectCurrentSession: Record<number, number> = {};
  for (const item of schedule) {
    const total = subjectSlotsCount[item.subject_id] || 1;
    subjectCurrentSession[item.subject_id] = (subjectCurrentSession[item.subject_id] || 0) + 1;
    item.session_number = subjectCurrentSession[item.subject_id];
    item.total_sessions = total;
  }

  return {
    student_id: student.student_id,
    student_name: student.full_name,
    group_name: student.group_name,
    timetable_image_url: student.timetable_image_url,
    schedule,
  };
}

export function hasTimeConflict(
  schedule: ScheduleItem[],
  dayOfWeek: number,
  startTime: string,
  endTime: string,
  ignoreSubjectShort?: string
): { conflict: boolean; conflictSubject?: string } {
  const toMinutes = (t: string) => {
    const [h, m] = t.split(':').map(Number);
    return h * 60 + (m || 0);
  };

  const candStart = toMinutes(startTime);
  const candEnd = toMinutes(endTime);

  for (const item of schedule) {
    if (item.day_of_week === dayOfWeek) {
      if (ignoreSubjectShort && item.subject_short === ignoreSubjectShort) {
        continue;
      }
      const itemStart = toMinutes(item.start_time);
      const itemEnd = toMinutes(item.end_time);

      // Overlap: start1 < end2 && start2 < end1
      if (candStart < itemEnd && itemStart < candEnd) {
        return { conflict: true, conflictSubject: item.subject_short };
      }
    }
  }

  return { conflict: false };
}

export function getAvailableGroupsForSubject(subjectId: number, studentId: string) {
  // Get subject info
  const subject = db.query('SELECT short_name, full_name FROM subjects WHERE subject_id = ?', [subjectId]).rows[0];
  const subjectShort = subject ? subject.short_name : '';

  // Get student's current effective schedule
  const currentSchedule = getEffectiveSchedule(studentId).schedule;

  // Get student's own group
  const student = db.query('SELECT group_id FROM students WHERE student_id = ?', [studentId]).rows[0];
  const studentGroupId = student ? student.group_id : 0;

  // Find all class sections teaching this subject across all groups with all their timetable slots
  const rows = db.query(
    `SELECT 
       c.class_id,
       g.group_id,
       g.group_name,
       p.full_name AS professor,
       c.room,
       gt.day_of_week,
       gt.start_time,
       gt.end_time
     FROM classes c
     JOIN groups g ON c.group_id = g.group_id
     JOIN professors p ON c.professor_id = p.professor_id
     JOIN group_timetable gt ON c.class_id = gt.class_id
     WHERE c.subject_id = ?
     ORDER BY g.group_name, gt.day_of_week, gt.start_time`,
    [subjectId]
  ).rows;

  // Group slots by class_id
  const classMap = new Map<number, {
    class_id: number;
    group_id: number;
    group_name: string;
    professor: string;
    room: string;
    slots: Array<{
      day_of_week: number;
      day_name: string;
      day_short: string;
      start_time: string;
      end_time: string;
      room: string;
      is_upcoming: boolean;
    }>;
  }>();

  const now = new Date();
  let currentDay = now.getDay(); // 0 is Sunday, 1 is Monday...
  if (currentDay === 0) currentDay = 7;
  const currentHours = now.getHours().toString().padStart(2, '0');
  const currentMins = now.getMinutes().toString().padStart(2, '0');
  const currentTime = `${currentHours}:${currentMins}`;

  for (const row of rows) {
    if (!classMap.has(row.class_id)) {
      classMap.set(row.class_id, {
        class_id: row.class_id,
        group_id: row.group_id,
        group_name: row.group_name,
        professor: row.professor,
        room: row.room,
        slots: [],
      });
    }

    const isSlotUpcoming =
      row.day_of_week > currentDay ||
      (row.day_of_week === currentDay && row.start_time >= currentTime);

    classMap.get(row.class_id)!.slots.push({
      day_of_week: row.day_of_week,
      day_name: DAY_NAMES[row.day_of_week] || `Day ${row.day_of_week}`,
      day_short: DAY_SHORT[row.day_of_week] || `D${row.day_of_week}`,
      start_time: row.start_time,
      end_time: row.end_time,
      room: row.room,
      is_upcoming: isSlotUpcoming,
    });
  }

  const options = Array.from(classMap.values()).map((cls) => {
    const isOwnGroup = cls.group_id === studentGroupId;
    const sessionsPerWeek = cls.slots.length;
    const hasUpcoming = cls.slots.some((s) => s.is_upcoming);

    // Check conflict for ALL slots in this class section
    let hasConflict = false;
    let conflictReason: string | undefined = undefined;

    for (const slot of cls.slots) {
      const check = hasTimeConflict(
        currentSchedule,
        slot.day_of_week,
        slot.start_time,
        slot.end_time,
        subjectShort
      );
      if (check.conflict) {
        hasConflict = true;
        conflictReason = `Clashes on ${slot.day_name} (${slot.start_time}-${slot.end_time}) with ${check.conflictSubject}`;
        break;
      }
    }

    const isAvailable = !hasConflict;
    const isRecommended = isAvailable && !isOwnGroup && hasUpcoming;

    // Create readable time summary
    const timeSummary = cls.slots
      .map((s) => `${s.day_short} ${s.start_time}-${s.end_time}`)
      .join(' • ');

    const daysSummary = cls.slots
      .map((s) => s.day_short)
      .join(' & ');

    const firstSlot = cls.slots[0] || {
      day_of_week: 1,
      day_name: 'Monday',
      start_time: '09:00',
      end_time: '10:00',
    };

    return {
      class_id: cls.class_id,
      group_name: cls.group_name,
      professor: cls.professor,
      room: cls.room,
      sessions_per_week: sessionsPerWeek,
      slots: cls.slots,
      day_of_week: firstSlot.day_of_week,
      day_name: sessionsPerWeek > 1 ? daysSummary : firstSlot.day_name,
      start_time: firstSlot.start_time,
      end_time: firstSlot.end_time,
      time_summary: timeSummary,
      is_own_group: isOwnGroup,
      is_available: isAvailable,
      is_upcoming: hasUpcoming,
      upcoming_text: hasUpcoming ? 'Upcoming lesson this week' : 'Past slot this week',
      recommended: isRecommended,
      conflict_reason: conflictReason,
    };
  });

  // Sort: Available + Upcoming first, then Available, then rest
  options.sort((a, b) => {
    if (a.is_available !== b.is_available) return a.is_available ? -1 : 1;
    if (a.is_upcoming !== b.is_upcoming) return a.is_upcoming ? -1 : 1;
    if (a.is_own_group !== b.is_own_group) return a.is_own_group ? 1 : -1;
    return a.day_of_week - b.day_of_week;
  });

  return options;
}

export function changeStudentGroup(
  studentId: string, 
  oldClassId: number, 
  newClassId: number,
  changeType: 'one_time' | 'permanent' = 'one_time'
) {
  // 1. Fetch new class details and all its timetable slots
  const newClass = db.query(
    `SELECT c.class_id, c.subject_id, c.group_id, g.group_name 
     FROM classes c 
     JOIN groups g ON c.group_id = g.group_id
     WHERE c.class_id = ?`,
    [newClassId]
  ).rows[0];

  if (!newClass) {
    throw new Error('Selected class section was not found');
  }

  const newClassSlots = db.query(
    `SELECT day_of_week, start_time, end_time 
     FROM group_timetable 
     WHERE class_id = ?`,
    [newClassId]
  ).rows;

  if (newClassSlots.length === 0) {
    throw new Error('Selected class section has no scheduled timetable slots');
  }

  const student = db.query('SELECT group_id FROM students WHERE student_id = ?', [studentId]).rows[0];

  // 2. Remove any previous one-time overrides for this subject
  db.query(
    `DELETE FROM student_schedule_overrides 
     WHERE student_id = ? AND class_id IN (SELECT class_id FROM classes WHERE subject_id = ?)`,
    [studentId, newClass.subject_id]
  );

  // 3. If returning to student's primary group, update enrollment
  if (student && newClass.group_id === student.group_id) {
    db.query(
      `DELETE FROM student_class_enrollment 
       WHERE student_id = ? AND class_id IN (SELECT class_id FROM classes WHERE subject_id = ?) AND class_id != ?`,
      [studentId, newClass.subject_id, newClassId]
    );

    const existingEnr = db.query(
      `SELECT enrollment_id FROM student_class_enrollment WHERE student_id = ? AND class_id = ?`,
      [studentId, newClassId]
    ).rows;

    if (existingEnr.length > 0) {
      db.query(
        `UPDATE student_class_enrollment SET status = 'active', dropped_at = NULL WHERE student_id = ? AND class_id = ?`,
        [studentId, newClassId]
      );
    } else {
      db.query(
        `INSERT INTO student_class_enrollment (student_id, class_id, status) VALUES (?, ?, 'active')`,
        [studentId, newClassId]
      );
    }

    return {
      success: true,
      is_permanent: true,
      is_one_time: false,
      message: `Returned to primary group schedule (${newClass.group_name}) permanently.`,
    };
  }

  // 4. If Permanent Change requested:
  if (changeType === 'permanent') {
    db.query(
      `DELETE FROM student_class_enrollment 
       WHERE student_id = ? AND class_id IN (SELECT class_id FROM classes WHERE subject_id = ?)`,
      [studentId, newClass.subject_id]
    );

    db.query(
      `INSERT INTO student_class_enrollment (student_id, class_id, status) VALUES (?, ?, 'active')`,
      [studentId, newClassId]
    );

    return {
      success: true,
      is_permanent: true,
      is_one_time: false,
      message: `Permanently changed to section ${newClass.group_name} (${newClassSlots.length} sessions/week) for the semester! Your timetable is permanently updated.`,
    };
  }

  // 5. If One-Time Make-Up requested:
  for (const slot of newClassSlots) {
    db.query(
      `INSERT INTO student_schedule_overrides (student_id, day_of_week, start_time, end_time, class_id)
       VALUES (?, ?, ?, ?, ?)`,
      [studentId, slot.day_of_week, slot.start_time, slot.end_time, newClassId]
    );
  }

  return {
    success: true,
    is_one_time: true,
    is_permanent: false,
    message: `One-time make-up lesson scheduled for this week (${newClassSlots.length} ${newClassSlots.length === 1 ? 'session' : 'sessions'})! Your timetable will automatically revert to your primary group next week.`,
  };
}

export function revertStudentOverride(studentId: string, subjectId: number) {
  // Find primary group's class for this subject
  const student = db.query('SELECT group_id FROM students WHERE student_id = ?', [studentId]).rows[0];
  if (student) {
    const primaryClass = db.query(
      'SELECT class_id FROM classes WHERE subject_id = ? AND group_id = ?',
      [subjectId, student.group_id]
    ).rows[0];

    if (primaryClass) {
      db.query(
        `UPDATE student_class_enrollment SET class_id = ?, status = 'active', dropped_at = NULL 
         WHERE student_id = ? AND class_id IN (SELECT class_id FROM classes WHERE subject_id = ?)`,
        [primaryClass.class_id, studentId, subjectId]
      );
    }
  }

  db.query(
    `DELETE FROM student_schedule_overrides 
     WHERE student_id = ? AND class_id IN (SELECT class_id FROM classes WHERE subject_id = ?)`,
    [studentId, subjectId]
  );

  return {
    success: true,
    message: 'Reverted to primary group schedule successfully.',
  };
}

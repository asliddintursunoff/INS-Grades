export interface Student {
  student_id: string;
  full_name: string;
  telegram_id: number | null;
  telegram_username: string | null;
  group_name: string;
  year_of_study?: number;
}

export interface StudentClass {
  class_id: number;
  subject_id: number;
  subject_short: string;
  subject_full: string;
  year_level?: number;
  professor: string;
  group_name: string;
  room: string;
  status: 'active' | 'dropped';
  enrolled_at?: string;
  dropped_at?: string;
}

export interface ScheduleSlot {
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

export interface TimetableResponse {
  student_id?: string;
  student_name?: string;
  group_name: string;
  timetable_image_url: string;
  schedule: ScheduleSlot[];
}

export interface GroupTimeSlot {
  day_of_week: number;
  day_name: string;
  day_short?: string;
  start_time: string;
  end_time: string;
  room: string;
  is_upcoming?: boolean;
}

export interface AvailableGroupOption {
  class_id: number;
  group_name: string;
  professor: string;
  day_of_week: number;
  day_name: string;
  start_time: string;
  end_time: string;
  room: string;
  sessions_per_week?: number;
  slots?: GroupTimeSlot[];
  time_summary?: string;
  is_own_group: boolean;
  is_available: boolean;
  is_upcoming?: boolean;
  upcoming_text?: string;
  recommended?: boolean;
  conflict_reason?: string;
}

export interface AbsenceItem {
  attendance_id: number;
  session_id: number;
  subject_short: string;
  subject_full: string;
  session_date: string;
  start_time: string;
  end_time: string;
  professor: string;
  room: string;
  status: string;
  makeup_session_id?: number | null;
}

export interface MakeupOption {
  session_id: number;
  rank: number;
  same_professor: boolean;
  professor: string;
  group_name: string;
  session_date: string;
  start_time: string;
  end_time: string;
  room: string;
  recommended: boolean;
}

export interface NotificationSettings {
  enabled: boolean;
  minutes_before: number;
}

export interface RetakeSubject {
  subject_id: number;
  short_name: string;
  full_name: string;
  year_level: number;
  enrollment_status: 'active' | 'dropped' | 'none';
  is_enrolled: boolean;
  current_class_id?: number | null;
}

export interface RetakeCatalogResponse {
  student_id: string;
  student_name: string;
  student_year: number;
  available_years: number[];
  subjects: RetakeSubject[];
}

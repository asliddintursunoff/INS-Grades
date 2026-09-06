import os
import datetime
import uuid
import re
import random
from typing import Optional
from django.db import connection, transaction, models
from django.db.models import Sum, Count, Avg, Q
from django.db.models.functions import TruncMonth
from django.utils import timezone
from django.http import HttpResponse, HttpResponseRedirect
from django.shortcuts import get_object_or_404
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework import status, viewsets

from .models import (
    Professor,
    Group,
    Student,
    Subject,
    CourseClass,
    GroupTimetableSlot,
    ScheduleOverride,
    StudentClassEnrollment,
    Homework,
    HomeworkSubmission,
    LectureSession,
    Attendance,
    NotificationSettings,
    SentNotification,
    ClassNotificationLog,
    PaymentTransaction,
    PaymentAuditLog,
    BotUser,
)
from .serializers import (
    ProfessorSerializer,
    GroupSerializer,
    StudentSerializer,
    SubjectSerializer,
    CourseClassSerializer,
    GroupTimetableSlotSerializer,
    ScheduleOverrideSerializer,
    HomeworkSerializer,
    HomeworkSubmissionSerializer,
    LectureSessionSerializer,
    AttendanceSerializer,
    NotificationSettingsSerializer,
)

DAY_NAMES = {
    1: "Monday",
    2: "Tuesday",
    3: "Wednesday",
    4: "Thursday",
    5: "Friday",
    6: "Saturday",
    7: "Sunday",
}

def get_group_s3_url(group_name: str, existing_url: Optional[str] = None) -> str:
    """Returns valid public S3 URL for a group's timetable screenshot."""
    if existing_url and (existing_url.startswith("http://") or existing_url.startswith("https://")):
        return existing_url
    sanitized = re.sub(r"[^A-Za-z0-9_.-]+", "_", group_name or "").strip("._") or "group"
    endpoint = (os.getenv("S3_ENDPOINT_URL") or os.getenv("AWS_ENDPOINT_URL_S3") or "").rstrip("/")
    bucket = os.getenv("S3_BUCKET_NAME") or os.getenv("AWS_STORAGE_BUCKET_NAME") or os.getenv("BUCKET_NAME") or ""
    if endpoint and bucket:
        return f"{endpoint}/{bucket}/timetables/{sanitized}.png"
    return f"/static/timetables/{sanitized}.png"


def get_timetable_image(request, group_name):
    """
    Proxy or direct fetch timetable screenshot from Tigris/S3.
    Enables secure image rendering even if S3 bucket is private.
    """
    clean_name = group_name.replace('.png', '')
    sanitized = re.sub(r"[^A-Za-z0-9_.-]+", "_", clean_name).strip("._") or "group"
    key = f"timetables/{sanitized}.png"

    s3_key_id = (
        os.getenv("S3_ACCESS_KEY_ID")
        or os.getenv("AWS_ACCESS_KEY_ID")
        or os.getenv("ACCESS_KEY_ID")
        or ""
    ).strip()
    s3_secret = (
        os.getenv("S3_SECRET_ACCESS_KEY")
        or os.getenv("AWS_SECRET_ACCESS_KEY")
        or os.getenv("SECRET_ACCESS_KEY")
        or os.getenv("S3_SECRET_KEY")
        or os.getenv("AWS_SECRET_KEY")
        or os.getenv("TIGRIS_SECRET_ACCESS_KEY")
        or os.getenv("S3_SECRET")
        or os.getenv("SECRET_KEY")
        or ""
    ).strip()
    bucket = os.getenv("S3_BUCKET_NAME") or os.getenv("AWS_STORAGE_BUCKET_NAME") or os.getenv("BUCKET_NAME") or ""
    endpoint = (os.getenv("S3_ENDPOINT_URL") or os.getenv("AWS_ENDPOINT_URL_S3") or "").rstrip("/")

    if s3_secret:
        try:
            import boto3
            from botocore.config import Config
            s3 = boto3.client(
                "s3",
                endpoint_url=endpoint,
                region_name="auto",
                aws_access_key_id=s3_key_id,
                aws_secret_access_key=s3_secret,
                config=Config(s3={"addressing_style": "path"})
            )
            obj = s3.get_object(Bucket=bucket, Key=key)
            img_bytes = obj["Body"].read()
            resp = HttpResponse(img_bytes, content_type="image/png")
            resp["Cache-Control"] = "public, max-age=86400"
            return resp
        except Exception:
            pass

    return HttpResponseRedirect(f"{endpoint}/{bucket}/{key}")



def resolve_student_obj(id_param: Optional[str]) -> Optional[Student]:
    """Resolves student by telegram_id (if numeric) or student_id."""
    if not id_param:
        return None
    id_str = str(id_param).strip()
    if id_str.isdigit():
        s = Student.objects.select_related('group').filter(telegram_id=int(id_str)).first()
        if s:
            return s
    return Student.objects.select_related('group').filter(student_id__iexact=id_str).first()


def parse_group_name(group_name: str):
    """
    Parses IUT group name into (major, year_code, year_level, faculty, section).
    Examples:
      - 'CSE25-1' -> major='CSE', year_code='25', year_level=2, faculty='SOCIE', section='1'
      - 'CIE26-8' -> major='CIE', year_code='26', year_level=1, faculty='SOCIE', section='8'
      - 'BM26-1'  -> major='BM', year_code='26', year_level=1, faculty='SBL', section='1'
      - 'SBL(B)25-2' -> major='SBL(B)', year_code='25', year_level=2, faculty='SBL', section='2'
    """
    name = (group_name or '').strip()
    m = re.match(r'^([A-Za-z]+(?:\([A-Za-z]+\))?)(\d{2})(?:-(\d+))?$', name)
    if m:
        major = m.group(1).upper()
        year_code = m.group(2)
        section = m.group(3) or ''
        year_level = {'26': 1, '25': 2, '24': 3, '23': 4}.get(year_code, 1)
        faculty = 'SBL' if (major.startswith('SBL') or major.startswith('BM')) else 'SOCIE'
        return {
            'major': major,
            'year_code': year_code,
            'year_level': year_level,
            'faculty': faculty,
            'section': section,
        }
    is_sbl = 'SBL' in name.upper() or 'BM' in name.upper()
    return {
        'major': name.upper(),
        'year_code': '26',
        'year_level': 1,
        'faculty': 'SBL' if is_sbl else 'SOCIE',
        'section': '',
    }


def is_upcoming_slot(day_of_week: int, start_time: str) -> bool:
    """
    Checks whether this lesson slot is still upcoming in the current calendar week in Asia/Tashkent timezone.
    On weekends (Saturday & Sunday), all weekday lessons of the upcoming week are considered upcoming.
    """
    try:
        from zoneinfo import ZoneInfo
        now = datetime.datetime.now(ZoneInfo("Asia/Tashkent"))
    except Exception:
        now = datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=5)))

    current_day = now.isoweekday()  # 1=Monday ... 7=Sunday
    if current_day in [6, 7]:
        return True

    if day_of_week > current_day:
        return True
    elif day_of_week == current_day:
        parts = str(start_time).strip().split(':')
        slot_minutes = int(parts[0]) * 60 + int(parts[1])
        curr_minutes = now.hour * 60 + now.minute
        return slot_minutes >= curr_minutes
    return False


def check_slot_conflict(student: Optional[Student], target_slot: GroupTimetableSlot, ignore_slot_id=None, ignore_subject_id=None):
    """
    Verifies whether target_slot overlaps in time with any active class the student has on that day.
    Ignores the specific slot being replaced (ignore_slot_id).
    """
    if not student or not student.group:
        return False, None

    overrides = ScheduleOverride.objects.filter(student=student, day_of_week=target_slot.day_of_week).select_related('course_class__subject')
    overridden_slot_ids = set()
    for ov in overrides:
        if ov.valid_from:
            digs = re.findall(r'\d+', ov.valid_from)
            if digs:
                overridden_slot_ids.add(int(digs[0]))

    def to_minutes(t_str):
        p = str(t_str).strip().split(':')
        return int(p[0]) * 60 + int(p[1])

    t_start = to_minutes(target_slot.start_time)
    t_end = to_minutes(target_slot.end_time)

    # 1. Base slots for student group
    base_slots = GroupTimetableSlot.objects.filter(
        group=student.group,
        day_of_week=target_slot.day_of_week
    ).select_related('course_class__subject')

    for bs in base_slots:
        if ignore_slot_id and str(bs.slot_id) == str(ignore_slot_id):
            continue
        if bs.slot_id in overridden_slot_ids:
            continue
        if ignore_subject_id and bs.course_class.subject_id == int(ignore_subject_id):
            continue
        b_start = to_minutes(bs.start_time)
        b_end = to_minutes(bs.end_time)
        if max(t_start, b_start) < min(t_end, b_end):
            return True, f"Conflicts with {bs.course_class.subject.short_name} ({bs.start_time}-{bs.end_time})"

    # 2. Overrides
    for ov in overrides:
        if ignore_slot_id and str(ov.override_id) == str(ignore_slot_id):
            continue
        if ignore_subject_id and ov.course_class.subject_id == int(ignore_subject_id):
            continue
        o_start = to_minutes(ov.start_time)
        o_end = to_minutes(ov.end_time)
        if max(t_start, o_start) < min(t_end, o_end):
            return True, f"Conflicts with {ov.course_class.subject.short_name} ({ov.start_time}-{ov.end_time})"

    return False, None


def is_class_eligible_for_student(c_major: str, c_year: int, c_faculty: str, stud_major: str, stud_year: int, stud_faculty: str):
    """
    Determines whether a course class belongs to the student's eligible degree stream and year.
    """
    if c_year > stud_year:
        return False
    if stud_faculty != c_faculty:
        return False
    if stud_faculty == 'SOCIE':
        if c_year == 1:
            if stud_major == 'IT':
                return c_major == 'IT'
            return c_major in ['CIE', 'SOCIE']
        else:
            if stud_major == c_major:
                return True
            if stud_major in ['AI', 'DS'] and c_major in ['AI', 'DS']:
                return True
            if stud_major in ['CSE', 'ICE'] and c_major in ['CSE', 'ICE'] and c_year >= 3:
                return True
            return False
    else:  # SBL
        if stud_major == 'BM':
            return c_major == 'BM'
        else:  # SBL(B), SBL(L)
            return c_major.startswith('SBL')



@api_view(['GET'])
@permission_classes([AllowAny])
def health_check(request):
    """Health check endpoint confirming Django & Database status."""
    db_connected = False
    db_error = None
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1;")
            cursor.fetchone()
            db_connected = True
    except Exception as e:
        db_error = str(e)

    vendor = connection.vendor.title() if hasattr(connection, 'vendor') else 'PostgreSQL'

    return Response({
        "status": "healthy" if db_connected else "database_disconnected",
        "service": "INS Grades University Timetable API (Django REST Framework)",
        "database": f"Railway {vendor}",
        "database_connected": db_connected,
        "database_error": db_error,
        "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat()
    })


@api_view(['GET'])
@permission_classes([AllowAny])
def system_status(request):
    """System status check required by frontend Mini App."""
    student_count = 0
    class_count = 0
    db_connected = False
    db_error = None

    try:
        student_count = Student.objects.count()
        class_count = CourseClass.objects.count()
        db_connected = True
    except Exception as e:
        db_error = str(e)

    return Response({
        "status": "ok",
        "database": "Railway PostgreSQL",
        "database_connected": db_connected,
        "database_error": db_error,
        "bot_active": True,
        "bot_username": "INS_gradesbot",
        "student_count": student_count,
        "class_count": class_count,
    })


@api_view(['GET'])
@permission_classes([AllowAny])
def demo_students(request):
    """Returns available students list for Mini App initialization."""
    students = list(Student.objects.select_related('group').all().order_by('student_id'))

    # If database has zero students, auto-seed a default student for group 1 so app never opens blank
    if not students:
        first_group = Group.objects.filter(group_name__icontains='CIE').first() or Group.objects.first()
        if first_group:
            default_student = Student.objects.create(
                student_id="U2410252",
                full_name="Asliddin Xolmatov",
                group=first_group,
                year_of_study=2,
            )
            # Auto-enroll default student into group classes
            for cc in CourseClass.objects.filter(group=first_group):
                StudentClassEnrollment.objects.get_or_create(student=default_student, course_class=cc, defaults={'status': 'active'})
            students = [default_student]

    results = []
    for s in students:
        group_name = s.group.group_name if s.group else ""
        img_url = get_group_s3_url(group_name, s.group.timetable_image_url if s.group else None)

        results.append({
            "student_id": s.student_id,
            "full_name": s.full_name,
            "telegram_id": s.telegram_id,
            "telegram_username": s.telegram_username,
            "group_name": group_name,
            "year_of_study": s.year_of_study or 2,
            "timetable_image_url": img_url,
            "is_premium": getattr(s, 'has_premium', False),
            "plan": "premium" if getattr(s, 'has_premium', False) else "free",
            "premium_expires_at": s.premium_expires_at.isoformat() if getattr(s, 'premium_expires_at', None) else None,
        })

    return Response({
        "students": results,
        "database_connected": True
    })


@api_view(['POST', 'GET'])
@permission_classes([AllowAny])
def auth_session(request):
    """Ephemeral session token handshake for web browser clients."""
    token = f"session_{uuid.uuid4().hex}"
    return Response({
        "session_token": token,
        "expires_in_seconds": 14400,
        "auth_type": "ephemeral_client_session"
    })


@api_view(['GET'])
@permission_classes([AllowAny])
def auth_me(request, telegram_id):
    """Looks up student account associated with a Telegram ID."""
    student = resolve_student_obj(str(telegram_id))
    if not student:
        return Response({"found": False})

    group_name = student.group.group_name if student.group else ""
    img_url = get_group_s3_url(group_name, student.group.timetable_image_url if student.group else None)

    return Response({
        "found": True,
        "student": {
            "student_id": student.student_id,
            "full_name": student.full_name,
            "group_name": group_name,
            "year_of_study": student.year_of_study or 2,
            "telegram_id": student.telegram_id,
            "telegram_username": student.telegram_username,
            "timetable_image_url": img_url,
            "is_premium": getattr(student, 'has_premium', False),
            "plan": "premium" if getattr(student, 'has_premium', False) else "free",
            "premium_expires_at": student.premium_expires_at.isoformat() if getattr(student, 'premium_expires_at', None) else None,
        }
    })


@api_view(['POST'])
@permission_classes([AllowAny])
def auth_link(request):
    """Links a Student ID to a Telegram account."""
    student_id = request.data.get('student_id', '').strip()
    telegram_id = request.data.get('telegram_id')
    telegram_username = request.data.get('telegram_username', '')

    if not student_id or not telegram_id:
        return Response(
            {"success": False, "error": "Student ID and Telegram ID are required"},
            status=status.HTTP_400_BAD_REQUEST
        )

    student = Student.objects.select_related('group').filter(student_id__iexact=student_id).first()
    if not student:
        return Response(
            {
                "success": False,
                "not_found": True,
                "error": f"Student ID '{student_id}' was not found in university database."
            },
            status=status.HTTP_404_NOT_FOUND
        )

    # Prevent telegram_id unique constraint conflict
    Student.objects.filter(telegram_id=telegram_id).exclude(student_id=student.student_id).update(telegram_id=None)

    student.telegram_id = telegram_id
    if telegram_username:
        student.telegram_username = telegram_username
    student.save()

    return Response({
        "success": True,
        "student": {
            "student_id": student.student_id,
            "full_name": student.full_name,
            "group_name": student.group.group_name if student.group else "",
            "year_of_study": student.year_of_study or 2,
            "telegram_id": student.telegram_id,
            "telegram_username": student.telegram_username,
            "is_premium": getattr(student, 'has_premium', False),
            "plan": "premium" if getattr(student, 'has_premium', False) else "free",
            "premium_expires_at": student.premium_expires_at.isoformat() if getattr(student, 'premium_expires_at', None) else None,
        },
        "student_id": student.student_id,
        "full_name": student.full_name,
        "group_name": student.group.group_name if student.group else "",
        "year_of_study": student.year_of_study or 2,
        "is_premium": getattr(student, 'has_premium', False),
        "plan": "premium" if getattr(student, 'has_premium', False) else "free",
        "premium_expires_at": student.premium_expires_at.isoformat() if getattr(student, 'premium_expires_at', None) else None,
    })


@api_view(['POST'])
@permission_classes([AllowAny])
def register_student(request):
    """
    Registers or updates a student profile, links Telegram ID,
    and automatically enrolls the student into all course classes in the chosen group.
    """
    student_id = str(request.data.get('student_id', '')).strip().upper()
    full_name = str(request.data.get('full_name', '')).strip()
    group_name = str(request.data.get('group_name', '')).strip()
    group_id = request.data.get('group_id')
    year_of_study = request.data.get('year_of_study', 1)
    telegram_id = request.data.get('telegram_id')
    telegram_username = request.data.get('telegram_username', '')

    if not student_id:
        return Response({"success": False, "error": "student_id is required"}, status=status.HTTP_400_BAD_REQUEST)

    # Resolve group
    group = None
    if group_id:
        group = Group.objects.filter(group_id=group_id).first()
    if not group and group_name:
        group = Group.objects.filter(group_name__iexact=group_name).first()

    if not group:
        return Response(
            {"success": False, "error": f"Group '{group_name or group_id}' not found in database"},
            status=status.HTTP_404_NOT_FOUND
        )

    # Unlink any existing student with same telegram_id
    if telegram_id:
        Student.objects.filter(telegram_id=int(telegram_id)).exclude(student_id=student_id).update(telegram_id=None)

    # 1. Create or update Student
    student = Student.objects.filter(student_id__iexact=student_id).first()
    if not student:
        student = Student.objects.create(
            student_id=student_id,
            full_name=full_name or f"Student {student_id}",
            group=group,
            year_of_study=int(year_of_study) if year_of_study else 1,
            telegram_id=int(telegram_id) if telegram_id else None,
            telegram_username=telegram_username or None,
        )
    else:
        student.group = group
        if full_name and (student.full_name.startswith("Student ") or not student.full_name):
            student.full_name = full_name
        elif full_name:
            student.full_name = full_name
        if year_of_study:
            student.year_of_study = int(year_of_study)
        if telegram_id:
            student.telegram_id = int(telegram_id)
        if telegram_username:
            student.telegram_username = telegram_username
        student.save()

    # 2. Automatically enroll student in every lesson/course class for this group
    group_classes = CourseClass.objects.filter(group=group)
    enrolled_count = 0
    for cc in group_classes:
        _, created = StudentClassEnrollment.objects.get_or_create(
            student=student,
            course_class=cc,
            defaults={'status': 'active'}
        )
        if created:
            enrolled_count += 1

    # 3. Ensure Notification Settings
    NotificationSettings.objects.get_or_create(
        student=student,
        defaults={'enabled': 1, 'minutes_before': 30}
    )

    group_name_str = group.group_name
    img_url = get_group_s3_url(group_name_str, group.timetable_image_url)

    return Response({
        "success": True,
        "message": f"Student {student.student_id} successfully registered and enrolled in {group_classes.count()} courses.",
        "student": {
            "student_id": student.student_id,
            "full_name": student.full_name,
            "group_name": group_name_str,
            "group_id": group.group_id,
            "year_of_study": student.year_of_study,
            "telegram_id": student.telegram_id,
            "timetable_image_url": img_url,
        },
        "enrolled_count": group_classes.count()
    })


# Standard Model ViewSets
class ProfessorViewSet(viewsets.ModelViewSet):
    queryset = Professor.objects.all()
    serializer_class = ProfessorSerializer


class GroupViewSet(viewsets.ModelViewSet):
    queryset = Group.objects.all()
    serializer_class = GroupSerializer


class SubjectViewSet(viewsets.ModelViewSet):
    queryset = Subject.objects.all()
    serializer_class = SubjectSerializer


class CourseClassViewSet(viewsets.ModelViewSet):
    queryset = CourseClass.objects.select_related('subject', 'professor', 'group').all()
    serializer_class = CourseClassSerializer


class StudentViewSet(viewsets.ModelViewSet):
    queryset = Student.objects.select_related('group').all()
    serializer_class = StudentSerializer

    def get_queryset(self):
        qs = super().get_queryset()
        telegram_id = self.request.query_params.get('telegram_id')
        if telegram_id:
            qs = qs.filter(telegram_id=telegram_id)
        group_id = self.request.query_params.get('group_id')
        if group_id:
            qs = qs.filter(group_id=group_id)
        return qs


def build_student_schedule_list(student):
    """Computes the effective weekly timetable for a student, handling overrides, dropped classes, and retakes."""
    group = student.group
    group_name = group.group_name if group else ""

    # 1. Dropped class IDs and subjects for this student
    dropped_class_ids = set(
        StudentClassEnrollment.objects.filter(
            student=student, status='dropped'
        ).values_list('course_class_id', flat=True)
    )
    dropped_subject_ids = set(
        StudentClassEnrollment.objects.filter(
            student=student, status='dropped'
        ).values_list('course_class__subject_id', flat=True)
    )
    active_subject_ids = set(
        StudentClassEnrollment.objects.filter(
            student=student, status='active'
        ).values_list('course_class__subject_id', flat=True)
    )
    truly_dropped_subject_ids = dropped_subject_ids - active_subject_ids

    # 2. Base group slots (excluding explicitly dropped classes or dropped subjects)
    base_slots = GroupTimetableSlot.objects.filter(group=group).select_related(
        'course_class__subject', 'course_class__professor', 'course_class__group'
    ).exclude(
        course_class_id__in=dropped_class_ids
    ).exclude(
        course_class__subject_id__in=truly_dropped_subject_ids
    ).order_by('day_of_week', 'start_time')

    # 3. Extra enrolled classes outside base group (retakes or electives)
    extra_enrollments = StudentClassEnrollment.objects.filter(
        student=student, status='active'
    ).exclude(course_class__group=group).select_related(
        'course_class__subject', 'course_class__professor', 'course_class__group'
    )
    extra_class_ids = [e.course_class_id for e in extra_enrollments]
    extra_slots = GroupTimetableSlot.objects.filter(
        course_class_id__in=extra_class_ids
    ).exclude(
        course_class_id__in=dropped_class_ids
    ).exclude(
        course_class__subject_id__in=truly_dropped_subject_ids
    ).select_related(
        'course_class__subject', 'course_class__professor', 'course_class__group'
    ).order_by('day_of_week', 'start_time')

    # 4. Schedule overrides (excluding dropped classes or dropped subjects)
    overrides = ScheduleOverride.objects.filter(student=student).exclude(
        course_class_id__in=dropped_class_ids
    ).exclude(
        course_class__subject_id__in=truly_dropped_subject_ids
    ).select_related(
        'course_class__subject', 'course_class__professor', 'course_class__group'
    ).order_by('day_of_week', 'start_time')

    # Collect overridden slot IDs and subjects
    overridden_slot_ids = set()
    legacy_overridden_subject_ids = set()
    for ov in overrides:
        if ov.valid_from:
            digits = re.findall(r'\d+', str(ov.valid_from))
            if digits:
                overridden_slot_ids.add(int(digits[0]))
            else:
                legacy_overridden_subject_ids.add(ov.course_class.subject_id)
        else:
            legacy_overridden_subject_ids.add(ov.course_class.subject_id)

    extra_subject_ids = {slot.course_class.subject_id for slot in extra_slots}
    override_subject_ids = {ov.course_class.subject_id for ov in overrides}

    schedule = []

    # Add base slots (omit if specific slot is overridden, or entire subject overridden, or extra)
    for slot in base_slots:
        cc = slot.course_class
        if slot.slot_id in overridden_slot_ids:
            continue
        if not overridden_slot_ids and cc.subject_id in legacy_overridden_subject_ids:
            continue
        if cc.subject_id in extra_subject_ids:
            continue
        if cc.subject_id in override_subject_ids:
            continue

        schedule.append({
            "slot_id": slot.slot_id,
            "day_of_week": slot.day_of_week,
            "day_name": DAY_NAMES.get(slot.day_of_week, f"Day {slot.day_of_week}"),
            "start_time": slot.start_time,
            "end_time": slot.end_time,
            "subject_id": cc.subject.subject_id,
            "subject_short": cc.subject.short_name,
            "subject_full": cc.subject.full_name,
            "subject": cc.subject.full_name,
            "professor": cc.professor.full_name,
            "room": cc.room or "TBA",
            "class_id": cc.class_id,
            "is_changed": False,
            "is_override": False,
            "is_one_time": False,
            "original_group": group_name,
            "actual_group": group_name,
        })

    # Add extra slots (omit if already in override_subject_ids)
    for slot in extra_slots:
        cc = slot.course_class
        if cc.subject_id in override_subject_ids:
            continue
        if slot.slot_id in overridden_slot_ids:
            continue
        if not overridden_slot_ids and cc.subject_id in legacy_overridden_subject_ids:
            continue
        is_perm = cc.group.group_name != group_name
        schedule.append({
            "slot_id": slot.slot_id,
            "day_of_week": slot.day_of_week,
            "day_name": DAY_NAMES.get(slot.day_of_week, f"Day {slot.day_of_week}"),
            "start_time": slot.start_time,
            "end_time": slot.end_time,
            "subject_id": cc.subject.subject_id,
            "subject_short": cc.subject.short_name,
            "subject_full": cc.subject.full_name,
            "subject": cc.subject.full_name,
            "professor": cc.professor.full_name,
            "room": cc.room or "TBA",
            "class_id": cc.class_id,
            "is_changed": is_perm,
            "is_override": False,
            "is_one_time": False,
            "original_group": group_name,
            "actual_group": cc.group.group_name,
        })

    # Add overrides
    for ov in overrides:
        cc = ov.course_class
        is_one_time = True
        if ov.valid_to and "permanent" in str(ov.valid_to).lower():
            is_one_time = False

        orig_slot_val = None
        if ov.valid_from:
            digs = re.findall(r'\d+', str(ov.valid_from))
            if digs:
                orig_slot_val = int(digs[0])

        schedule.append({
            "slot_id": ov.override_id,
            "day_of_week": ov.day_of_week,
            "day_name": DAY_NAMES.get(ov.day_of_week, f"Day {ov.day_of_week}"),
            "start_time": ov.start_time,
            "end_time": ov.end_time,
            "subject_id": cc.subject.subject_id,
            "subject_short": cc.subject.short_name,
            "subject_full": cc.subject.full_name,
            "subject": cc.subject.full_name,
            "professor": cc.professor.full_name,
            "room": cc.room or "TBA",
            "class_id": cc.class_id,
            "is_changed": True,
            "is_override": True,
            "is_one_time": is_one_time,
            "reverts_next_week": is_one_time,
            "original_group": group_name,
            "actual_group": cc.group.group_name,
            "original_slot_id": orig_slot_val,
        })

    schedule.sort(key=lambda x: (x["day_of_week"], x["start_time"]))

    subj_counts = {}
    for item in schedule:
        sid = item["subject_id"]
        subj_counts[sid] = subj_counts.get(sid, 0) + 1

    subj_curr = {}
    for item in schedule:
        sid = item["subject_id"]
        subj_curr[sid] = subj_curr.get(sid, 0) + 1
        item["session_number"] = subj_curr[sid]
        item["total_sessions"] = subj_counts[sid]

    return schedule


# Specialized Timetable & Student Operations
@api_view(['GET'])
@permission_classes([AllowAny])
def get_student_timetable(request, student_id):
    """Retrieve full weekly schedule with overrides and S3 photo for a student."""
    student = resolve_student_obj(student_id)
    if not student:
        return Response({"error": f"Student not found: {student_id}"}, status=status.HTTP_404_NOT_FOUND)

    group = student.group
    group_name = group.group_name if group else ""
    image_url = get_group_s3_url(group_name, group.timetable_image_url if group else None)
    schedule = build_student_schedule_list(student)

    return Response({
        "student": StudentSerializer(student).data,
        "student_id": student.student_id,
        "student_name": student.full_name,
        "group_name": group_name,
        "timetable_image_url": image_url,
        "schedule": schedule,
        "timetable": schedule,
        "is_premium": getattr(student, 'has_premium', False),
        "plan": "premium" if getattr(student, 'has_premium', False) else "free",
    })


@api_view(['GET'])
@permission_classes([AllowAny])
def get_group_timetable(request, group_id):
    """Retrieve base timetable slots for a group."""
    group = get_object_or_404(Group, group_id=group_id)
    image_url = get_group_s3_url(group.group_name, group.timetable_image_url)

    slots = GroupTimetableSlot.objects.filter(group=group).select_related(
        'course_class__subject', 'course_class__professor'
    ).order_by('day_of_week', 'start_time')

    return Response({
        "group": GroupSerializer(group).data,
        "group_name": group.group_name,
        "timetable_image_url": image_url,
        "slots": GroupTimetableSlotSerializer(slots, many=True).data
    })


@api_view(['GET'])
@permission_classes([AllowAny])
def student_classes(request, student_id):
    """Returns active and dropped course classes for a student."""
    student = resolve_student_obj(student_id)
    if not student:
        return Response({"error": "Student not found"}, status=status.HTTP_404_NOT_FOUND)

    enrollments = StudentClassEnrollment.objects.filter(
        student=student
    ).select_related('course_class__subject', 'course_class__professor', 'course_class__group')

    classes_list = []
    for e in enrollments:
        cc = e.course_class
        classes_list.append({
            "class_id": cc.class_id,
            "subject_id": cc.subject.subject_id,
            "subject_short": cc.subject.short_name,
            "subject_full": cc.subject.full_name,
            "year_level": cc.subject.year_level,
            "professor": cc.professor.full_name,
            "group_name": cc.group.group_name,
            "room": cc.room or "TBA",
            "status": e.status,
            "enrolled_at": e.enrolled_at.isoformat() if e.enrolled_at else None,
            "dropped_at": e.dropped_at.isoformat() if e.dropped_at else None,
        })

    return Response({"classes": classes_list})


@api_view(['POST'])
@permission_classes([AllowAny])
def student_drop_class(request, student_id):
    """Marks a course class as dropped for a student and removes it from schedule."""
    student = resolve_student_obj(student_id)
    if not student:
        return Response({"error": "Student not found"}, status=status.HTTP_404_NOT_FOUND)

    if not getattr(student, 'has_premium', False):
        return Response({
            "error": "Kursni bekor qilish (Drop) faqat Premium foydalanuvchilar uchun mavjud.",
            "requires_premium": True,
            "plan": "free",
            "price": "10 000 so'm/oyiga"
        }, status=status.HTTP_403_FORBIDDEN)

    class_id = request.data.get('class_id')
    subject_id = request.data.get('subject_id')
    if not class_id and not subject_id:
        return Response({"error": "class_id or subject_id is required"}, status=status.HTTP_400_BAD_REQUEST)

    cc = None
    if class_id:
        cc = CourseClass.objects.filter(class_id=int(class_id)).select_related('subject').first()

    target_subject_id = subject_id or (cc.subject_id if cc else None)

    if target_subject_id:
        StudentClassEnrollment.objects.filter(
            student=student, course_class__subject_id=target_subject_id
        ).update(status='dropped', dropped_at=datetime.datetime.now(datetime.timezone.utc))
        ScheduleOverride.objects.filter(
            student=student, course_class__subject_id=target_subject_id
        ).delete()
    elif class_id:
        StudentClassEnrollment.objects.filter(
            student=student, course_class_id=class_id
        ).update(status='dropped', dropped_at=datetime.datetime.now(datetime.timezone.utc))
        ScheduleOverride.objects.filter(
            student=student, course_class_id=class_id
        ).delete()

    return Response({"success": True, "message": "Course successfully dropped and removed from schedule"})


@api_view(['POST'])
@permission_classes([AllowAny])
def student_retake_class(request, student_id):
    """Re-enrolls a previously dropped course class."""
    student = resolve_student_obj(student_id)
    if not student:
        return Response({"error": "Student not found"}, status=status.HTTP_404_NOT_FOUND)

    if not getattr(student, 'has_premium', False):
        return Response({
            "error": "Kursni qayta o'qish (Retake) faqat Premium foydalanuvchilar uchun mavjud.",
            "requires_premium": True,
            "plan": "free",
            "price": "10 000 so'm/oyiga"
        }, status=status.HTTP_403_FORBIDDEN)

    class_id = request.data.get('class_id')
    if not class_id:
        return Response({"error": "class_id is required"}, status=status.HTTP_400_BAD_REQUEST)

    enr, created = StudentClassEnrollment.objects.get_or_create(
        student=student,
        course_class_id=class_id,
        defaults={'status': 'active'}
    )
    if not created:
        enr.status = 'active'
        enr.dropped_at = None
        enr.save()

    # Restore ScheduleOverride if class is outside student's base group
    cc = CourseClass.objects.filter(class_id=class_id).first()
    if cc and student.group_id != cc.group_id:
        ScheduleOverride.objects.filter(student=student, course_class__subject=cc.subject).delete()
        slots = GroupTimetableSlot.objects.filter(course_class=cc).order_by('day_of_week', 'start_time')
        for idx, slot in enumerate(slots, 1):
            ScheduleOverride.objects.create(
                student=student,
                day_of_week=slot.day_of_week,
                start_time=slot.start_time,
                end_time=slot.end_time,
                course_class=cc,
                valid_to=f"session_{idx}:permanent"
            )

    return Response({"success": True, "message": "Course successfully re-enrolled"})


@api_view(['GET'])
@permission_classes([AllowAny])
def student_retake_catalog(request, student_id):
    """Returns course catalog available for retakes up to the student's study year."""
    student = resolve_student_obj(student_id)
    if not student:
        return Response({"error": "Student not found"}, status=status.HTTP_404_NOT_FOUND)

    stud_info = parse_group_name(student.group.group_name if student.group else "")
    user_year = student.year_of_study or stud_info['year_level']
    stud_major = stud_info['major']
    stud_faculty = stud_info['faculty']

    available_years = list(range(1, user_year + 1))

    # All classes with group and subject
    classes = CourseClass.objects.select_related('group', 'subject', 'professor')

    # Subject enrollment mapping
    enrollments = {
        e.course_class.subject_id: e
        for e in StudentClassEnrollment.objects.filter(student=student).select_related('course_class')
    }

    # Build catalog filtering by major/faculty and year <= user_year
    subject_map = {}
    for c in classes:
        c_info = parse_group_name(c.group.group_name)
        c_major = c_info['major']
        c_yr = c_info['year_level']
        c_fac = c_info['faculty']

        is_elective = c.subject.short_name in ['BK1-R', 'BK1-U', 'Mental Education'] and c_yr <= user_year
        is_eligible = is_elective or is_class_eligible_for_student(
            c_major, c_yr, c_fac, stud_major, user_year, stud_faculty
        )

        if not is_eligible:
            continue

        sid = c.subject.subject_id
        if sid not in subject_map:
            subject_map[sid] = {
                'subject': c.subject,
                'year_level': c_yr,
                'faculty': c_fac,
                'majors': {c_major},
            }
        else:
            subject_map[sid]['majors'].add(c_major)
            if c_yr < subject_map[sid]['year_level']:
                subject_map[sid]['year_level'] = c_yr

    subj_list = []
    for sid, info in sorted(subject_map.items(), key=lambda x: (x[1]['year_level'], x[1]['subject'].full_name)):
        s = info['subject']
        enr = enrollments.get(s.subject_id)
        enr_status = enr.status if enr else 'none'
        subj_list.append({
            "subject_id": s.subject_id,
            "short_name": s.short_name,
            "full_name": s.full_name,
            "year_level": info['year_level'],
            "faculty": info['faculty'],
            "majors": sorted(list(info['majors'])),
            "enrollment_status": enr_status,
            "is_enrolled": (enr_status == 'active'),
            "current_class_id": enr.course_class_id if enr else None,
        })

    return Response({
        "student_id": student.student_id,
        "student_name": student.full_name,
        "student_year": user_year,
        "student_major": stud_major,
        "student_faculty": stud_faculty,
        "available_years": available_years,
        "subjects": subj_list,
    })


@api_view(['POST'])
@permission_classes([AllowAny])
def student_enroll_retake(request, student_id):
    """Enrolls student in a retake class section."""
    student = resolve_student_obj(student_id)
    if not student:
        return Response({"error": "Student not found"}, status=status.HTTP_404_NOT_FOUND)

    if not getattr(student, 'has_premium', False):
        return Response({
            "error": "Retake kursga yozilish faqat Premium foydalanuvchilar uchun mavjud.",
            "requires_premium": True,
            "plan": "free",
            "price": "10 000 so'm/oyiga"
        }, status=status.HTTP_403_FORBIDDEN)

    class_id = request.data.get('class_id')
    if not class_id:
        return Response({"error": "class_id is required"}, status=status.HTTP_400_BAD_REQUEST)

    cc = get_object_or_404(CourseClass.objects.select_related('subject', 'group', 'professor'), class_id=class_id)

    # Deactivate other enrollments for same subject
    StudentClassEnrollment.objects.filter(
        student=student, course_class__subject=cc.subject
    ).exclude(course_class_id=class_id).update(status='dropped')

    enr, _ = StudentClassEnrollment.objects.get_or_create(
        student=student,
        course_class=cc,
        defaults={'status': 'active'}
    )
    enr.status = 'active'
    enr.dropped_at = None
    enr.save()

    # If class is outside student base group, add override slots
    if student.group_id != cc.group_id:
        ScheduleOverride.objects.filter(student=student, course_class__subject=cc.subject).delete()
        slots = GroupTimetableSlot.objects.filter(course_class=cc).order_by('day_of_week', 'start_time')
        for idx, slot in enumerate(slots, 1):
            ScheduleOverride.objects.create(
                student=student,
                day_of_week=slot.day_of_week,
                start_time=slot.start_time,
                end_time=slot.end_time,
                course_class=cc,
                valid_to=f"session_{idx}:permanent"
            )

    return Response({
        "success": True,
        "message": f"Successfully registered for retake course: {cc.subject.full_name} ({cc.subject.short_name})"
    })


@api_view(['GET'])
@permission_classes([AllowAny])
def subject_available_groups(request, subject_id):
    """
    Returns available class sections for a subject.
    Enforces strict rules:
      1. SAME PROFESSOR: University rules mandate attending the same professor's lecture.
      2. SAME MAJOR & YEAR: Class section must be within the student's degree stream and course year.
      3. PER-SESSION FILTERING: If session_number is specified (e.g. 1 or 2), only returns that
         individual session's slot, preventing cross-session replacement.
    """
    subject = get_object_or_404(Subject, subject_id=subject_id)
    student_param = request.query_params.get('student_telegram_id') or request.query_params.get('student_id')
    student = resolve_student_obj(student_param)
    student_group_id = student.group_id if student else None

    stud_info = parse_group_name(student.group.group_name if student and student.group else '')
    stud_major = stud_info['major']
    stud_yr_code = stud_info['year_code']
    stud_yr_level = stud_info['year_level']
    stud_faculty = stud_info['faculty']

    # Current class and professor resolution
    current_class = None
    class_id_param = request.query_params.get('class_id') or request.query_params.get('current_class_id')
    slot_id_param = request.query_params.get('slot_id')

    if class_id_param and str(class_id_param).isdigit():
        current_class = CourseClass.objects.filter(class_id=int(class_id_param), subject=subject).select_related('professor', 'group').first()

    if not current_class and slot_id_param and str(slot_id_param).isdigit():
        base_slot = GroupTimetableSlot.objects.filter(slot_id=int(slot_id_param), course_class__subject=subject).select_related('course_class__professor', 'course_class__group').first()
        if base_slot:
            current_class = base_slot.course_class
        else:
            ov = ScheduleOverride.objects.filter(override_id=int(slot_id_param), course_class__subject=subject).select_related('course_class__professor', 'course_class__group').first()
            if ov:
                current_class = ov.course_class

    if not current_class and student:
        enr = StudentClassEnrollment.objects.filter(
            student=student, course_class__subject_id=subject_id, status='active'
        ).select_related('course_class__professor', 'course_class__group').first()
        if enr:
            current_class = enr.course_class
        elif student.group:
            current_class = CourseClass.objects.filter(
                group=student.group, subject_id=subject_id
            ).select_related('professor', 'group').first()

    # Cohort target resolution:
    # If the student is taking this class (e.g. freshman class while student is sophomore),
    # the available alternative sections belong to the course's cohort (current_class.group),
    # NOT the student's personal degree year!
    if current_class:
        curr_info = parse_group_name(current_class.group.group_name if current_class.group else '')
        target_yr_code = curr_info['year_code'] or stud_yr_code
        target_major = curr_info['major'] or stud_major
        target_faculty = curr_info['faculty'] or stud_faculty
    else:
        target_yr_code = stud_yr_code
        target_major = stud_major
        target_faculty = stud_faculty

    # Determine session number
    session_num = None
    session_num_param = request.query_params.get('session_number')
    if session_num_param and str(session_num_param).isdigit():
        session_num = int(session_num_param)
    elif slot_id_param and current_class:
        # Check if slot_id is an override with session tag in valid_to
        ov = ScheduleOverride.objects.filter(override_id=int(slot_id_param), course_class__subject=subject).first()
        if ov and ov.valid_to:
            digs = re.findall(r'session_(\d+)', ov.valid_to)
            if digs:
                session_num = int(digs[0])
        if not session_num:
            # Auto-detect which session this slot corresponds to (e.g. 1st or 2nd slot in week)
            c_slots = list(GroupTimetableSlot.objects.filter(course_class=current_class).order_by('day_of_week', 'start_time'))
            for idx, s in enumerate(c_slots, 1):
                if str(s.slot_id) == str(slot_id_param):
                    session_num = idx
                    break

    # Build candidate classes query
    classes_qs = CourseClass.objects.filter(subject=subject).select_related('group', 'professor')

    if current_class:
        # STRICT PROFESSOR FILTER: Must be taught by the same professor!
        classes_qs = classes_qs.filter(professor=current_class.professor)

        # STRICT MAJOR & COHORT YEAR FILTER:
        # e.g. CIE26 for freshman or CSE25 for sophomore
        if target_major and target_yr_code:
            major_matched = classes_qs.filter(group__group_name__startswith=f"{target_major}{target_yr_code}")
            if major_matched.exists():
                classes_qs = major_matched
            else:
                cand_list = [
                    c for c in classes_qs
                    if parse_group_name(c.group.group_name)['faculty'] == target_faculty
                    and parse_group_name(c.group.group_name)['year_code'] == target_yr_code
                ]
                if cand_list:
                    classes_qs = cand_list
    else:
        # Browsing without current class (e.g. retake catalog)
        if target_faculty:
            cand_list = [c for c in classes_qs if parse_group_name(c.group.group_name)['faculty'] == target_faculty]
            if cand_list:
                classes_qs = cand_list

    # Ensure list
    candidate_classes = list(classes_qs)

    # Determine current active slot timing to filter out duplicate/combined sections at the exact same hour
    curr_active_slot = None
    if slot_id_param and str(slot_id_param).isdigit():
        curr_active_slot = GroupTimetableSlot.objects.filter(slot_id=int(slot_id_param)).first()
        if not curr_active_slot:
            curr_active_slot = ScheduleOverride.objects.filter(override_id=int(slot_id_param)).first()
    if not curr_active_slot and current_class:
        curr_slots = list(GroupTimetableSlot.objects.filter(course_class=current_class).order_by('day_of_week', 'start_time'))
        if session_num and 1 <= session_num <= len(curr_slots):
            curr_active_slot = curr_slots[session_num - 1]

    options = []
    for c in candidate_classes:
        all_slots = list(GroupTimetableSlot.objects.filter(course_class=c).order_by('day_of_week', 'start_time'))
        if not all_slots:
            continue

        total_sessions = len(all_slots)

        if session_num and 1 <= session_num <= total_sessions:
            # Single session mode: ONLY return the requested session slot
            target_slot = all_slots[session_num - 1]

            # EXCLUDE DUPLICATE COMBINED SECTIONS:
            # If another group has this exact same lecture at the exact same day and time with the same professor,
            # it is not an alternative time — do not show it!
            if curr_active_slot:
                if (target_slot.day_of_week == curr_active_slot.day_of_week and
                    target_slot.start_time == curr_active_slot.start_time and
                    target_slot.end_time == curr_active_slot.end_time and
                    c.group_id != student_group_id):
                    continue

            has_conflict, conflict_reason = check_slot_conflict(
                student, target_slot, ignore_slot_id=slot_id_param, ignore_subject_id=subject_id if session_num is None else None
            )
            is_own = (c.group_id == student_group_id)

            options.append({
                "class_id": c.class_id,
                "slot_id": target_slot.slot_id,
                "group_name": c.group.group_name,
                "professor": c.professor.full_name,
                "day_of_week": target_slot.day_of_week,
                "day_name": DAY_NAMES.get(target_slot.day_of_week, f"Day {target_slot.day_of_week}"),
                "start_time": target_slot.start_time,
                "end_time": target_slot.end_time,
                "room": c.room or "TBA",
                "session_number": session_num,
                "total_sessions": total_sessions,
                "sessions_per_week": 1,
                "slots": [{
                    "slot_id": target_slot.slot_id,
                    "day_of_week": target_slot.day_of_week,
                    "day_name": DAY_NAMES.get(target_slot.day_of_week, f"Day {target_slot.day_of_week}"),
                    "start_time": target_slot.start_time,
                    "end_time": target_slot.end_time,
                    "room": c.room or "TBA",
                    "session_number": session_num,
                    "is_upcoming": is_upcoming_slot(target_slot.day_of_week, target_slot.start_time),
                }],
                "time_summary": f"{DAY_NAMES.get(target_slot.day_of_week, '')} {target_slot.start_time}-{target_slot.end_time}",
                "is_own_group": is_own,
                "is_available": not has_conflict,
                "is_upcoming": is_upcoming_slot(target_slot.day_of_week, target_slot.start_time),
                "recommended": is_own,
                "conflict_reason": conflict_reason if has_conflict else None,
            })
        else:
            # Full class mode (all sessions) - for retake catalog registration
            primary_slot = all_slots[0]
            time_sum = ", ".join([f"{DAY_NAMES.get(s.day_of_week, '')} {s.start_time}-{s.end_time}" for s in all_slots])
            is_own = (c.group_id == student_group_id)

            has_conflict = False
            conflict_reason = None
            for s in all_slots:
                conf, r = check_slot_conflict(student, s, ignore_subject_id=subject_id)
                if conf:
                    has_conflict = True
                    conflict_reason = r
                    break

            slot_list = [{
                "slot_id": s.slot_id,
                "day_of_week": s.day_of_week,
                "day_name": DAY_NAMES.get(s.day_of_week, f"Day {s.day_of_week}"),
                "start_time": s.start_time,
                "end_time": s.end_time,
                "room": c.room or "TBA",
                "session_number": idx,
                "is_upcoming": is_upcoming_slot(s.day_of_week, s.start_time),
            } for idx, s in enumerate(all_slots, 1)]

            options.append({
                "class_id": c.class_id,
                "slot_id": primary_slot.slot_id,
                "group_name": c.group.group_name,
                "professor": c.professor.full_name,
                "day_of_week": primary_slot.day_of_week,
                "day_name": DAY_NAMES.get(primary_slot.day_of_week, f"Day {primary_slot.day_of_week}"),
                "start_time": primary_slot.start_time,
                "end_time": primary_slot.end_time,
                "room": c.room or "TBA",
                "session_number": 1,
                "total_sessions": total_sessions,
                "sessions_per_week": total_sessions,
                "slots": slot_list,
                "time_summary": time_sum,
                "is_own_group": is_own,
                "is_available": not has_conflict,
                "is_upcoming": any(is_upcoming_slot(s.day_of_week, s.start_time) for s in all_slots),
                "recommended": is_own,
                "conflict_reason": conflict_reason if has_conflict else None,
            })

    return Response({
        "options": options,
        "session_number": session_num,
        "professor": current_class.professor.full_name if current_class else None,
        "subject_name": subject.full_name,
    })


@api_view(['POST'])
@permission_classes([AllowAny])
def student_change_group(request, student_id):
    """
    Applies section change for a student.
    Supports:
      1. Single Session Change: If session_number or original_slot_id is provided,
         overrides ONLY that specific session, leaving the other session with the student's base group.
      2. Full Course Change: Switches all sessions of the course to the new group.
    """
    student = resolve_student_obj(student_id)
    if not student:
        return Response({"error": "Student not found"}, status=status.HTTP_404_NOT_FOUND)

    if not getattr(student, 'has_premium', False):
        return Response({
            "error": "Dars jadvali va vaqtini o'zgartirish faqat Premium foydalanuvchilar uchun mavjud.",
            "requires_premium": True,
            "plan": "free",
            "price": "10 000 so'm/oyiga"
        }, status=status.HTTP_403_FORBIDDEN)

    new_class_id = request.data.get('new_class_id')
    change_type = request.data.get('change_type', 'permanent')
    target_slot_id = request.data.get('target_slot_id')
    original_slot_id = request.data.get('original_slot_id')
    session_number = request.data.get('session_number')

    if not new_class_id:
        return Response({"error": "new_class_id is required"}, status=status.HTTP_400_BAD_REQUEST)

    new_class = get_object_or_404(CourseClass.objects.select_related('subject', 'group', 'professor'), class_id=new_class_id)
    subj = new_class.subject

    # Reverting back to own base group
    if student.group_id == new_class.group_id:
        if original_slot_id:
            ScheduleOverride.objects.filter(student=student, valid_from__contains=str(original_slot_id)).delete()
        else:
            ScheduleOverride.objects.filter(student=student, course_class__subject=subj).delete()

        return Response({
            "success": True,
            "mode": "reverted",
            "message": f"Successfully reverted {subj.short_name} back to your primary group {new_class.group.group_name}."
        })

    # 1. Single Session Override
    if session_number or original_slot_id or target_slot_id:
        # Find target slot of new_class
        target_slot = None
        if target_slot_id:
            target_slot = GroupTimetableSlot.objects.filter(slot_id=int(target_slot_id), course_class=new_class).first()
        if not target_slot and session_number:
            new_slots = list(GroupTimetableSlot.objects.filter(course_class=new_class).order_by('day_of_week', 'start_time'))
            idx = int(session_number) - 1
            if 0 <= idx < len(new_slots):
                target_slot = new_slots[idx]

        # Find original base slot being replaced
        orig_slot = None
        if original_slot_id:
            orig_slot = GroupTimetableSlot.objects.filter(slot_id=int(original_slot_id)).first()
        if not orig_slot and session_number and student.group:
            base_slots = list(GroupTimetableSlot.objects.filter(group=student.group, course_class__subject=subj).order_by('day_of_week', 'start_time'))
            idx = int(session_number) - 1
            if 0 <= idx < len(base_slots):
                orig_slot = base_slots[idx]

        if target_slot:
            # Delete any previous override for this specific slot or session
            if orig_slot:
                ScheduleOverride.objects.filter(student=student, valid_from__contains=str(orig_slot.slot_id)).delete()
            if session_number:
                ScheduleOverride.objects.filter(student=student, course_class__subject=subj, valid_to__startswith=f"session_{session_number}").delete()

            ScheduleOverride.objects.create(
                student=student,
                course_class=new_class,
                day_of_week=target_slot.day_of_week,
                start_time=target_slot.start_time,
                end_time=target_slot.end_time,
                valid_from=str(orig_slot.slot_id) if orig_slot else '',
                valid_to=f"session_{session_number or 1}:{change_type}"
            )

            session_label = f"Session {session_number} of " if session_number else ""
            timing_label = f" ({DAY_NAMES.get(target_slot.day_of_week, '')} {target_slot.start_time}-{target_slot.end_time})"

            return Response({
                "success": True,
                "mode": change_type,
                "session_number": session_number,
                "message": f"Successfully moved {session_label}{subj.full_name} ({subj.short_name}) to section {new_class.group.group_name}{timing_label} with Prof. {new_class.professor.full_name}."
            })

    # 2. Full Course Change (both sessions)
    if change_type == 'permanent':
        StudentClassEnrollment.objects.filter(
            student=student, course_class__subject=subj
        ).update(status='dropped', dropped_at=datetime.datetime.now(datetime.timezone.utc))

        ScheduleOverride.objects.filter(student=student, course_class__subject=subj).delete()

        enr, _ = StudentClassEnrollment.objects.get_or_create(
            student=student, course_class=new_class,
            defaults={'status': 'active'}
        )
        enr.status = 'active'
        enr.dropped_at = None
        enr.save()

        return Response({
            "success": True,
            "mode": "permanent",
            "message": f"Permanently moved {subj.full_name} ({subj.short_name}) to section {new_class.group.group_name} with Prof. {new_class.professor.full_name}."
        })
    else:
        ScheduleOverride.objects.filter(student=student, course_class__subject=subj).delete()
        slots = GroupTimetableSlot.objects.filter(course_class=new_class).order_by('day_of_week', 'start_time')
        for idx, s in enumerate(slots, 1):
            ScheduleOverride.objects.create(
                student=student,
                day_of_week=s.day_of_week,
                start_time=s.start_time,
                end_time=s.end_time,
                course_class=new_class,
                valid_to=f"session_{idx}:one_time"
            )

        return Response({
            "success": True,
            "mode": "one_time",
            "message": f"Scheduled one-time make-up lessons with section {new_class.group.group_name} for this week."
        })


@api_view(['POST'])
@permission_classes([AllowAny])
def student_revert_override(request, student_id):
    """Reverts one-time or permanent section change back to primary group schedule."""
    student = resolve_student_obj(student_id)
    if not student:
        return Response({"error": "Student not found"}, status=status.HTTP_404_NOT_FOUND)

    if not getattr(student, 'has_premium', False):
        return Response({
            "error": "Dars jadvalini o'zgartirish faqat Premium foydalanuvchilar uchun mavjud.",
            "requires_premium": True,
            "plan": "free",
            "price": "10 000 so'm/oyiga"
        }, status=status.HTTP_403_FORBIDDEN)

    subject_id = request.data.get('subject_id')
    slot_id = request.data.get('slot_id') or request.data.get('original_slot_id')

    if slot_id:
        deleted, _ = ScheduleOverride.objects.filter(
            student=student, valid_from__contains=str(slot_id)
        ).delete()
        if not deleted:
            ScheduleOverride.objects.filter(student=student, override_id=slot_id).delete()
        return Response({
            "success": True,
            "message": "Successfully reverted session back to your primary group timetable."
        })

    if not subject_id:
        return Response({"error": "subject_id or slot_id is required"}, status=status.HTTP_400_BAD_REQUEST)

    ScheduleOverride.objects.filter(student=student, course_class__subject_id=subject_id).delete()

    base_class = CourseClass.objects.filter(group=student.group, subject_id=subject_id).first()
    if base_class:
        StudentClassEnrollment.objects.filter(
            student=student, course_class__subject_id=subject_id
        ).exclude(course_class=base_class).update(status='dropped')

        enr, _ = StudentClassEnrollment.objects.get_or_create(
            student=student, course_class=base_class,
            defaults={'status': 'active'}
        )
        enr.status = 'active'
        enr.dropped_at = None
        enr.save()

    return Response({
        "success": True,
        "message": "Successfully reverted schedule back to your primary group timetable."
    })


@api_view(['GET'])
@permission_classes([AllowAny])
def student_absences(request, student_id):
    """Retrieves student absence records."""
    student = resolve_student_obj(student_id)
    if not student:
        return Response({"error": "Student not found"}, status=status.HTTP_404_NOT_FOUND)

    records = Attendance.objects.filter(student=student, status='absent').select_related(
        'session__course_class__subject', 'session__course_class__professor', 'session__course_class__group'
    ).order_by('-session__session_date')

    absences_list = []
    for a in records:
        s = a.session
        cc = s.course_class
        absences_list.append({
            "attendance_id": a.attendance_id,
            "session_id": s.session_id,
            "subject_short": cc.subject.short_name,
            "subject_full": cc.subject.full_name,
            "session_date": s.session_date,
            "start_time": s.start_time,
            "end_time": s.end_time,
            "professor": cc.professor.full_name,
            "room": cc.room or "TBA",
            "status": a.status,
            "makeup_session_id": a.makeup_session_id,
        })

    return Response({"absences": absences_list})


@api_view(['GET'])
@permission_classes([AllowAny])
def session_makeup_options(request, session_id):
    """Suggests candidate future sessions for making up a missed lecture."""
    missed = get_object_or_404(
        LectureSession.objects.select_related('course_class__subject', 'course_class__group'),
        session_id=session_id
    )
    student_param = request.query_params.get('student_telegram_id', '')
    student = resolve_student_obj(student_param)
    student_group_id = student.group_id if student else None

    candidates = LectureSession.objects.filter(
        course_class__subject=missed.course_class.subject
    ).exclude(
        course_class__group_id=student_group_id
    ).select_related('course_class__group', 'course_class__professor')[:5]

    options = []
    for idx, c in enumerate(candidates):
        cc = c.course_class
        options.append({
            "session_id": c.session_id,
            "rank": idx + 1,
            "same_professor": (cc.professor_id == missed.course_class.professor_id),
            "professor": cc.professor.full_name,
            "group_name": cc.group.group_name,
            "session_date": c.session_date,
            "start_time": c.start_time,
            "end_time": c.end_time,
            "room": cc.room or "TBA",
            "recommended": (idx == 0),
        })

    return Response({"options": options})


@api_view(['POST'])
@permission_classes([AllowAny])
def session_record_makeup(request, session_id):
    """Records completion of a make-up lecture for an absence."""
    student_param = request.data.get('student_telegram_id', '')
    makeup_session_id = request.data.get('makeup_session_id')
    student = resolve_student_obj(student_param)
    if not student:
        return Response({"error": "Student not found"}, status=status.HTTP_404_NOT_FOUND)

    Attendance.objects.filter(
        student=student, session_id=session_id
    ).update(status='made_up', makeup_session_id=makeup_session_id)

    return Response({
        "success": True,
        "message": "Kelmagan darsingiz muvaffaqiyatli to'ldirildi"
    })


@api_view(['GET', 'POST', 'PATCH'])
@permission_classes([AllowAny])
def student_notification_settings(request, student_id):
    """Gets or updates notification preferences for a student."""
    student = resolve_student_obj(student_id)
    if not student:
        return Response({"error": "Student not found"}, status=status.HTTP_404_NOT_FOUND)

    setting, _ = NotificationSettings.objects.get_or_create(
        student=student,
        defaults={'enabled': 1, 'minutes_before': 30}
    )

    if request.method in ('POST', 'PATCH'):
        enabled = request.data.get('enabled')
        minutes_before = request.data.get('minutes_before')

        if enabled:
            if not getattr(student, 'has_premium', False):
                return Response({
                    "error": "Telegram orqali dars eslatmalarini yoqish faqat Premium foydalanuvchilar uchun mavjud.",
                    "requires_premium": True,
                    "plan": "free",
                    "price": "10 000 so'm/oyiga"
                }, status=status.HTTP_403_FORBIDDEN)

        if enabled is not None:
            setting.enabled = 1 if enabled else 0
        if minutes_before is not None:
            setting.minutes_before = int(minutes_before)
        setting.save()

    return Response({
        "enabled": bool(setting.enabled),
        "minutes_before": setting.minutes_before,
        "is_premium": getattr(student, 'has_premium', False),
    })


@api_view(['GET', 'POST'])
@permission_classes([AllowAny])
def student_premium_manage(request, student_id):
    """View and manage subscription plan for a student."""
    student = resolve_student_obj(student_id)
    if not student:
        return Response({"error": "Student not found"}, status=status.HTTP_404_NOT_FOUND)

    if request.method == 'POST':
        action = request.data.get('action')
        is_premium_val = request.data.get('is_premium')
        duration_days = int(request.data.get('duration_days', 30))

        if action == 'deactivate' or is_premium_val is False:
            student.is_premium = False
            student.premium_expires_at = None
            student.save()
            msg = "Premium obunasi bekor qilindi (Free tarif)."
        else:
            student.is_premium = True
            student.premium_expires_at = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(days=duration_days)
            student.save()
            msg = f"Premium tarif muvaffaqiyatli faollashtirildi ({duration_days} kunga)."

        return Response({
            "success": True,
            "message": msg,
            "student_id": student.student_id,
            "is_premium": student.has_premium,
            "plan": "premium" if student.has_premium else "free",
            "premium_expires_at": student.premium_expires_at.isoformat() if student.premium_expires_at else None,
            "price": "10 000 so'm/oyiga"
        })

    return Response({
        "student_id": student.student_id,
        "student_name": student.full_name,
        "is_premium": student.has_premium,
        "plan": "premium" if student.has_premium else "free",
        "price": "10 000 so'm/oyiga",
        "premium_expires_at": student.premium_expires_at.isoformat() if student.premium_expires_at else None,
        "features": [
            "Dars vaqtlarini o'zgartirish (Make-up va Doimiy almashtirish)",
            "Retake va Drop kurslarni boshqarish",
            "Telegram avtomatik dars eslatmalari",
        ]
    })


# Direct alias to avoid re-wrapping Request in Request
link_telegram = auth_link


@api_view(['GET', 'POST'])
@permission_classes([AllowAny])
def student_homework(request, student_id):
    """List homework for a student or update homework status."""
    student = resolve_student_obj(student_id)
    if not student:
        return Response({"error": "Student not found"}, status=status.HTTP_404_NOT_FOUND)

    if request.method == 'GET':
        homeworks = Homework.objects.filter(
            course_class__group=student.group
        ).select_related('course_class__subject', 'course_class__professor')

        submissions = {
            s.homework_id: s for s in HomeworkSubmission.objects.filter(student=student)
        }

        results = []
        for hw in homeworks:
            sub = submissions.get(hw.homework_id)
            results.append({
                "homework_id": hw.homework_id,
                "title": hw.title,
                "description": hw.description,
                "deadline": hw.deadline,
                "subject": hw.course_class.subject.full_name,
                "subject_short": hw.course_class.subject.short_name,
                "professor": hw.course_class.professor.full_name,
                "is_done": bool(sub.is_done) if sub else False,
                "grade": sub.grade if sub else None,
                "submitted_at": sub.submitted_at if sub else None
            })

        return Response(results)

    elif request.method == 'POST':
        homework_id = request.data.get('homework_id')
        is_done = request.data.get('is_done', True)
        if not homework_id:
            return Response({"error": "homework_id is required."}, status=status.HTTP_400_BAD_REQUEST)

        hw = get_object_or_404(Homework, homework_id=homework_id)
        sub, created = HomeworkSubmission.objects.get_or_create(
            homework=hw,
            student=student,
            defaults={'is_done': 1 if is_done else 0, 'submitted_at': datetime.datetime.now(datetime.timezone.utc)}
        )
        if not created:
            sub.is_done = 1 if is_done else 0
            if is_done and not sub.submitted_at:
                sub.submitted_at = datetime.datetime.now(datetime.timezone.utc)
            sub.save()

        return Response({
            "message": "Homework status updated.",
            "homework_id": hw.homework_id,
            "is_done": bool(sub.is_done)
        })


@api_view(['GET'])
@permission_classes([AllowAny])
def student_attendance(request, student_id):
    """Retrieve attendance and absence counts for a student."""
    student = resolve_student_obj(student_id)
    if not student:
        return Response({"error": "Student not found"}, status=status.HTTP_404_NOT_FOUND)

    records = Attendance.objects.filter(student=student).select_related(
        'session__course_class__subject', 'session__course_class__professor'
    ).order_by('-session__session_date')

    absent_count = records.filter(status='absent', makeup_session__isnull=True).count()
    present_count = records.filter(status='present').count()
    excused_count = records.filter(status='excused').count()

    return Response({
        "student": StudentSerializer(student).data,
        "summary": {
            "absent": absent_count,
            "present": present_count,
            "excused": excused_count,
            "total_records": records.count()
        },
        "records": AttendanceSerializer(records, many=True).data
    })


# Direct alias to avoid re-wrapping Request in Request
notification_settings = student_notification_settings


@api_view(['GET'])
@permission_classes([AllowAny])
def get_pending_class_alerts(request):
    """
    Returns pending class reminder alerts that should be dispatched right now.
    Evaluates students with registered Telegram IDs in Asia/Tashkent timezone.
    Filters by individual student's chosen minutes_before setting.
    Idempotent: skips any class already marked sent in ClassNotificationLog for today.
    """
    sim_time_param = request.query_params.get('simulated_time')
    if sim_time_param:
        try:
            now = datetime.datetime.fromisoformat(sim_time_param)
        except Exception:
            now = datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=5)))
    else:
        try:
            from zoneinfo import ZoneInfo
            now = datetime.datetime.now(ZoneInfo("Asia/Tashkent"))
        except Exception:
            now = datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=5)))

    current_day = now.isoweekday()  # 1=Monday ... 7=Sunday
    today_date = now.date()
    today_date_str = today_date.isoformat()
    current_minutes = now.hour * 60 + now.minute

    # On Sunday, universities are closed - no alerts needed
    if current_day == 7:
        return Response({
            "alerts": [],
            "status": "sunday_off",
            "server_time": now.strftime("%Y-%m-%d %H:%M:%S")
        })

    # Between 21:00 and 07:00, no classes take place
    if now.hour < 7 or now.hour >= 21:
        return Response({
            "alerts": [],
            "status": "outside_lecture_hours",
            "server_time": now.strftime("%Y-%m-%d %H:%M:%S")
        })

    # Query active students with telegram_id who are on PREMIUM plan
    students = Student.objects.filter(
        telegram_id__isnull=False,
        is_premium=True
    ).select_related('group', 'notification_settings')

    # Prefetch sent logs for today to avoid N+1 queries
    sent_logs = set(
        ClassNotificationLog.objects.filter(
            notification_date=today_date
        ).values_list('student_id', 'slot_key')
    )

    pending_alerts = []

    for student in students:
        # Extra verification for active premium period
        if not getattr(student, 'has_premium', False):
            continue

        # Check settings
        notif_setting = getattr(student, 'notification_settings', None)
        if notif_setting and not notif_setting.enabled:
            continue

        minutes_before = notif_setting.minutes_before if notif_setting else 30

        # Compute student schedule
        schedule = build_student_schedule_list(student)

        # Check today's slots
        for slot in schedule:
            if slot.get('day_of_week') != current_day:
                continue

            time_parts = str(slot.get('start_time', '')).strip().split(':')
            if len(time_parts) < 2:
                continue

            slot_start_min = int(time_parts[0]) * 60 + int(time_parts[1])
            diff_min = slot_start_min - current_minutes

            # Trigger alert when diff is within the target window (e.g. within [0, minutes_before])
            if 0 <= diff_min <= minutes_before:
                slot_key = f"{slot['subject_short']}_{slot['start_time']}_{current_day}"
                if (student.student_id, slot_key) in sent_logs:
                    continue

                pending_alerts.append({
                    "student_id": student.student_id,
                    "student_name": student.full_name,
                    "telegram_id": student.telegram_id,
                    "subject_full": slot['subject_full'],
                    "subject_short": slot['subject_short'],
                    "professor": slot['professor'],
                    "room": slot['room'],
                    "actual_group": slot['actual_group'],
                    "day_name": slot['day_name'],
                    "start_time": slot['start_time'],
                    "end_time": slot['end_time'],
                    "minutes_left": diff_min,
                    "is_one_time": slot.get('is_one_time', False),
                    "slot_key": slot_key,
                    "notification_date": today_date_str,
                })

    return Response({
        "alerts": pending_alerts,
        "count": len(pending_alerts),
        "server_time": now.strftime("%Y-%m-%d %H:%M:%S")
    })


@api_view(['POST'])
@permission_classes([AllowAny])
def mark_class_alert_sent(request):
    """Records delivery of a class reminder to prevent duplicate messages."""
    student_id = request.data.get('student_id')
    slot_key = request.data.get('slot_key')
    notification_date_str = request.data.get('notification_date')

    if not student_id or not slot_key:
        return Response({"error": "student_id and slot_key are required"}, status=status.HTTP_400_BAD_REQUEST)

    student = resolve_student_obj(student_id)
    if not student:
        return Response({"error": "Student not found"}, status=status.HTTP_404_NOT_FOUND)

    try:
        n_date = datetime.date.fromisoformat(notification_date_str) if notification_date_str else timezone.localdate()
    except ValueError:
        n_date = timezone.localdate()

    ClassNotificationLog.objects.get_or_create(
        student=student,
        notification_date=n_date,
        slot_key=slot_key
    )

    return Response({"success": True, "message": "Alert marked as sent"})


def extract_uzs_amount(text: str, base_amount: int = 10000) -> Optional[int]:
    """
    Intelligently extracts the incoming top-up payment amount in UZS from SMS / notification texts.
    Strictly ignores debits/expenses (e.g. 'To'lov', '➖').
    Extracts amount from deposit lines (e.g. '➕ 10.216,00 UZS').
    Prioritizes amounts matching the [base_amount, base_amount + 300] variance window.
    """
    if not text:
        return None

    lower_text = text.lower()

    # Reject debits / expenses:
    if "➖" in text:
        return None
    if ("to'lov" in lower_text or "oplata" in lower_text or "spisanie" in lower_text) and not (
        "to'ldirish" in lower_text or "popolnenie" in lower_text or "пополнение" in lower_text or "tushdi" in lower_text
    ):
        return None

    # 1. Priority 1: Deposit lines with '+' or '➕' (e.g. Humo/Uzcard notifications: '➕ 10.216,00 UZS')
    # Matches '➕ 10.216,00 UZS', '+ 10.216,00 UZS', '➕10216 UZS', '+10150'
    plus_matches = re.findall(r'[➕\+]\s*([\d\s\.]+)(?:,\d{2})?\s*(?:uzs|so\'?m|som)?', text, re.IGNORECASE)
    for match in plus_matches:
        # Humo uses '.' as thousands separator: 10.216 -> 10216
        cleaned = re.sub(r'[\s\.]', '', match.strip())
        if cleaned.isdigit():
            val = int(cleaned)
            if base_amount <= val <= base_amount + 300:
                return val
            elif val >= base_amount:
                return val

    # 2. Priority 2: Look for 5-digit number in the range [base_amount, base_amount + 300]
    # e.g. 10216, 10.216, 10 216 (ignoring numbers preceded by minus or balance symbol 💰)
    salt_candidates = re.findall(r'(?<![-–—➖\d])(10[\s\.]?[0-3]\d\d)(?!\d)', text)
    for cand in salt_candidates:
        clean = re.sub(r'[\s\.]', '', cand)
        if clean.isdigit():
            val = int(clean)
            if base_amount <= val <= base_amount + 300:
                return val

    # 3. Priority 3: Explicit top-up keywords (tushdi, popolnenie, vnesenie)
    currency_patterns = [
        r'(?:tushdi|vnesenie|popolnenie|kirim)\s*:?\s*([\d\s\.]+)(?:,\d{2})?\s*(?:uzs|so\'m|som|sum)',
    ]
    for pattern in currency_patterns:
        matches = re.findall(pattern, text, re.IGNORECASE)
        for match in matches:
            cleaned = re.sub(r'[\s\.]', '', match.strip())
            if cleaned.isdigit():
                val = int(cleaned)
                if val >= 1000:
                    return val

    return None


@api_view(['POST'])
@permission_classes([AllowAny])
def payment_create(request):
    """
    Creates a new pending payment transaction with a unique dynamic salt (001-300).
    Atomically ensures no two concurrent users receive the same exact amount.
    """
    student_id = request.data.get('student_id')
    if not student_id:
        return Response({"error": "student_id is required"}, status=status.HTTP_400_BAD_REQUEST)

    student = resolve_student_obj(student_id)
    if not student:
        return Response({"error": "Student not found"}, status=status.HTTP_404_NOT_FOUND)

    card_number = os.getenv('PAYMENT_CARD_NUMBER', '')
    card_holder = os.getenv('PAYMENT_CARD_HOLDER', '')
    base_amount = int(os.getenv('BASE_PREMIUM_PRICE', '10000'))
    timeout_minutes = int(os.getenv('PAYMENT_TIMEOUT_MINUTES', '5'))

    now = timezone.now()

    with transaction.atomic():
        # Clean up any expired transactions
        PaymentTransaction.objects.select_for_update().filter(
            status='pending', expires_at__lte=now
        ).update(status='expired')

        # Check if student already has an active pending transaction with > 30s remaining
        existing_tx = PaymentTransaction.objects.select_for_update().filter(
            student=student,
            status='pending',
            expires_at__gt=now + datetime.timedelta(seconds=30)
        ).order_by('-created_at').first()

        if existing_tx:
            seconds_remaining = max(0, int((existing_tx.expires_at - now).total_seconds()))
            return Response({
                "success": True,
                "transaction_id": str(existing_tx.transaction_id),
                "base_amount": existing_tx.base_amount,
                "salt": existing_tx.salt,
                "total_amount": existing_tx.total_amount,
                "formatted_amount": f"{existing_tx.total_amount:,}".replace(",", " "),
                "card_number": existing_tx.card_number,
                "card_holder": existing_tx.card_holder,
                "expires_at": existing_tx.expires_at.isoformat(),
                "seconds_remaining": seconds_remaining,
                "status": existing_tx.status,
                "is_reused": True
            })

        # Reserve a unique salt from 1 to 300
        active_salts = set(
            PaymentTransaction.objects.select_for_update()
            .filter(status='pending', expires_at__gt=now)
            .values_list('salt', flat=True)
        )

        available_salts = [s for s in range(1, 301) if s not in active_salts]
        if not available_salts:
            return Response({
                "error": "Hozirda barcha to'lov liniyalari band. Iltimos 1-2 daqiqadan so'ng qayta urinib ko'ring.",
                "retry_after_seconds": 60
            }, status=status.HTTP_429_TOO_MANY_REQUESTS)

        chosen_salt = random.choice(available_salts)
        total_amount = base_amount + chosen_salt
        expires_at = now + datetime.timedelta(minutes=timeout_minutes)

        tx = PaymentTransaction.objects.create(
            student=student,
            base_amount=base_amount,
            salt=chosen_salt,
            total_amount=total_amount,
            card_number=card_number,
            card_holder=card_holder,
            status='pending',
            expires_at=expires_at,
        )

    return Response({
        "success": True,
        "transaction_id": str(tx.transaction_id),
        "base_amount": tx.base_amount,
        "salt": tx.salt,
        "total_amount": tx.total_amount,
        "formatted_amount": f"{tx.total_amount:,}".replace(",", " "),
        "card_number": tx.card_number,
        "card_holder": tx.card_holder,
        "expires_at": tx.expires_at.isoformat(),
        "seconds_remaining": timeout_minutes * 60,
        "status": tx.status
    }, status=status.HTTP_201_CREATED)


@api_view(['GET'])
@permission_classes([AllowAny])
def payment_status(request, transaction_id):
    """
    Checks status of a payment transaction. Automatically transitions to expired if time has elapsed.
    """
    try:
        tx = PaymentTransaction.objects.select_related('student').get(transaction_id=transaction_id)
    except (PaymentTransaction.DoesNotExist, ValueError):
        return Response({"error": "Transaction not found"}, status=status.HTTP_404_NOT_FOUND)

    now = timezone.now()
    if tx.status == 'pending' and now > tx.expires_at:
        tx.status = 'expired'
        tx.save(update_fields=['status'])

    seconds_left = max(0, int((tx.expires_at - now).total_seconds())) if tx.status == 'pending' else 0
    student = tx.student

    return Response({
        "transaction_id": str(tx.transaction_id),
        "status": tx.status,
        "total_amount": tx.total_amount,
        "seconds_remaining": seconds_left,
        "is_premium": student.has_premium,
        "premium_expires_at": student.premium_expires_at.isoformat() if student.premium_expires_at else None,
        "completed_at": tx.completed_at.isoformat() if tx.completed_at else None
    })


@api_view(['POST'])
@permission_classes([AllowAny])
def payment_cancel(request, transaction_id):
    """Cancels a pending payment transaction so its salt is immediately available for others."""
    try:
        tx = PaymentTransaction.objects.get(transaction_id=transaction_id)
    except (PaymentTransaction.DoesNotExist, ValueError):
        return Response({"error": "Transaction not found"}, status=status.HTTP_404_NOT_FOUND)

    if tx.status == 'pending':
        tx.status = 'cancelled'
        tx.save(update_fields=['status'])

    return Response({"success": True, "status": tx.status})


@api_view(['POST'])
@permission_classes([AllowAny])
def payment_process_incoming_sms(request):
    """
    Internal endpoint called by Telethon worker when an incoming SMS / notification arrives.
    Extracts amount, matches pending transaction, activates 30 days of Premium, records audit log.
    """
    expected_secret = os.getenv('PAYMENT_SECRET_KEY', '')
    provided_secret = request.headers.get('X-Payment-Secret') or request.GET.get('secret') or request.data.get('secret')

    if provided_secret != expected_secret:
        return Response({"error": "Unauthorized"}, status=status.HTTP_401_UNAUTHORIZED)

    raw_message = request.data.get('raw_message', '').strip()
    sender = request.data.get('sender', '').strip()
    telegram_message_id = request.data.get('telegram_message_id')

    if not raw_message:
        return Response({"error": "raw_message is required"}, status=status.HTTP_400_BAD_REQUEST)

    # Idempotency check: Don't process the same Telegram message twice
    if telegram_message_id and PaymentTransaction.objects.filter(telegram_message_id=str(telegram_message_id)).exists():
        return Response({
            "success": True,
            "duplicate": True,
            "message": "Message already processed successfully."
        })

    base_price = int(os.getenv('BASE_PREMIUM_PRICE', '10000'))
    amount = extract_uzs_amount(raw_message, base_amount=base_price)

    if not amount:
        PaymentAuditLog.objects.create(
            sender=sender,
            raw_message=raw_message,
            extracted_amount=None,
            is_matched=False,
            error_details="No valid UZS payment amount could be parsed from message text."
        )
        return Response({
            "success": True,
            "matched": False,
            "reason": "No valid amount extracted",
            "raw_message": raw_message
        })

    now = timezone.now()

    with transaction.atomic():
        # Match against active pending transactions with this exact amount
        tx = (
            PaymentTransaction.objects.select_for_update()
            .select_related('student')
            .filter(total_amount=amount, status='pending', expires_at__gt=now)
            .order_by('created_at')
            .first()
        )

        if tx:
            tx.status = 'completed'
            tx.completed_at = now
            if telegram_message_id:
                tx.telegram_message_id = str(telegram_message_id)
            tx.save()

            # Activate 30 days of Premium for the student
            student = tx.student
            student.is_premium = True
            current_expiry = student.premium_expires_at if (student.premium_expires_at and student.premium_expires_at > now) else now
            student.premium_expires_at = current_expiry + datetime.timedelta(days=30)
            student.save(update_fields=['is_premium', 'premium_expires_at'])

            PaymentAuditLog.objects.create(
                sender=sender,
                raw_message=raw_message,
                extracted_amount=amount,
                matched_transaction=tx,
                is_matched=True
            )

            return Response({
                "success": True,
                "matched": True,
                "transaction_id": str(tx.transaction_id),
                "student_id": student.student_id,
                "student_name": student.full_name,
                "amount": amount,
                "premium_expires_at": student.premium_expires_at.isoformat()
            })
        else:
            # Unmatched payment (e.g. sent after 5 minutes expired, or wrong amount)
            PaymentAuditLog.objects.create(
                sender=sender,
                raw_message=raw_message,
                extracted_amount=amount,
                is_matched=False,
                error_details=f"Received {amount} UZS but no active pending transaction matched this exact amount."
            )

            return Response({
                "success": True,
                "matched": False,
                "extracted_amount": amount,
                "reason": "No active pending transaction matched this exact amount."
            })


@api_view(['POST'])
@permission_classes([AllowAny])
def track_bot_activity(request):
    """
    Called by the Telegram bot whenever any user interacts with it.
    Tracks bot users, last active time, username, and links student profile if present.
    """
    data = request.data
    telegram_id = data.get('telegram_id')
    if not telegram_id:
        return Response({"error": "telegram_id required"}, status=status.HTTP_400_BAD_REQUEST)

    username = data.get('username') or ''
    first_name = data.get('first_name') or ''
    last_name = data.get('last_name') or ''

    student = Student.objects.filter(telegram_id=telegram_id).first()

    bot_user, created = BotUser.objects.get_or_create(
        telegram_id=telegram_id,
        defaults={
            'username': username,
            'first_name': first_name,
            'last_name': last_name,
            'student': student,
            'is_active': True,
        }
    )
    if not created:
        bot_user.username = username or bot_user.username
        bot_user.first_name = first_name or bot_user.first_name
        bot_user.last_name = last_name or bot_user.last_name
        if student and not bot_user.student:
            bot_user.student = student
        bot_user.is_active = True
        bot_user.save()

    return Response({"success": True, "created": created})


@api_view(['GET'])
@permission_classes([AllowAny])
def get_admin_stats(request):
    """
    Returns complete analytics & statistics for the admin dashboard:
    - All-time earnings
    - Current month's earnings
    - Today's earnings
    - Monthly purchases and revenue breakdown
    - Total bot users
    - Users who accessed the bot today
    - Active bot users
    - Active premium students count
    """
    api_key = request.headers.get('X-API-KEY') or request.GET.get('api_key')
    expected_key = os.getenv('API_KEY', '')
    if expected_key and api_key != expected_key and not (request.user and request.user.is_staff):
        return Response({"error": "Unauthorized"}, status=status.HTTP_401_UNAUTHORIZED)

    now = timezone.localtime(timezone.now())
    today = now.date()
    current_year = now.year
    current_month = now.month

    completed_txs = PaymentTransaction.objects.filter(status='completed')
    total_revenue = completed_txs.aggregate(s=models.Sum('total_amount'))['s'] or 0
    total_base_revenue = completed_txs.aggregate(s=models.Sum('base_amount'))['s'] or 0
    total_purchases_count = completed_txs.count()

    month_txs = completed_txs.filter(
        completed_at__year=current_year, completed_at__month=current_month
    )
    month_revenue = month_txs.aggregate(s=models.Sum('total_amount'))['s'] or 0
    month_purchases_count = month_txs.count()

    today_txs = completed_txs.filter(completed_at__date=today)
    today_revenue = today_txs.aggregate(s=models.Sum('total_amount'))['s'] or 0
    today_purchases_count = today_txs.count()

    from django.db.models.functions import TruncMonth
    monthly_sales_qs = (
        completed_txs.annotate(month=TruncMonth('completed_at'))
        .values('month')
        .annotate(
            count=models.Count('transaction_id'),
            total_sum=models.Sum('total_amount'),
            avg_sum=models.Avg('total_amount'),
        )
        .order_by('-month')
    )

    monthly_sales = [
        {
            "month": item['month'].strftime('%Y-%m') if item['month'] else 'N/A',
            "count": item['count'],
            "total_amount": item['total_sum'] or 0,
            "avg_amount": round(item['avg_sum'] or 0),
        }
        for item in monthly_sales_qs
    ]

    total_bot_users = BotUser.objects.count()
    today_bot_users = BotUser.objects.filter(last_active_at__date=today).count()
    active_bot_users = BotUser.objects.filter(
        models.Q(student__isnull=False) | models.Q(last_active_at__gte=now - datetime.timedelta(days=30))
    ).count()

    total_students = Student.objects.count()
    linked_students = Student.objects.filter(telegram_id__isnull=False).count()
    active_premium_students = Student.objects.filter(
        is_premium=True,
        premium_expires_at__gt=now
    ).count()

    return Response({
        "total_revenue": total_revenue,
        "total_base_revenue": total_base_revenue,
        "total_purchases_count": total_purchases_count,
        "month_revenue": month_revenue,
        "month_purchases_count": month_purchases_count,
        "today_revenue": today_revenue,
        "today_purchases_count": today_purchases_count,
        "monthly_sales": monthly_sales,
        "total_bot_users": total_bot_users,
        "today_bot_users": today_bot_users,
        "active_bot_users": active_bot_users,
        "total_students": total_students,
        "linked_students": linked_students,
        "active_premium_students": active_premium_students,
    })


@api_view(['GET'])
@permission_classes([AllowAny])
def get_bot_broadcast_recipients(request):
    """
    Returns all unique Telegram IDs who can receive broadcast announcements.
    Combines registered BotUser IDs and Student telegram_ids.
    """
    api_key = request.headers.get('X-API-KEY') or request.GET.get('api_key')
    expected_key = os.getenv('API_KEY', '')
    if expected_key and api_key != expected_key and not (request.user and request.user.is_staff):
        return Response({"error": "Unauthorized"}, status=status.HTTP_401_UNAUTHORIZED)

    bot_user_ids = set(BotUser.objects.filter(is_active=True).values_list('telegram_id', flat=True))
    student_ids = set(Student.objects.filter(telegram_id__isnull=False).values_list('telegram_id', flat=True))
    all_recipients = list(bot_user_ids.union(student_ids))

    return Response({
        "total": len(all_recipients),
        "recipients": all_recipients,
    })


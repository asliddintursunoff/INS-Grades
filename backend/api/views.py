import os
import datetime
import uuid
import re
from typing import Optional
from django.db import connection
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

DEFAULT_S3_BASE = "https://t3.storageapi.dev/resilient-module-m3qmihat/timetables"


def get_group_s3_url(group_name: str, existing_url: Optional[str] = None) -> str:
    """Returns valid public S3 URL for a group's timetable screenshot."""
    if existing_url and (existing_url.startswith("http://") or existing_url.startswith("https://")):
        return existing_url
    sanitized = re.sub(r"[^A-Za-z0-9_.-]+", "_", group_name or "").strip("._") or "group"
    return f"{DEFAULT_S3_BASE}/{sanitized}.png"


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
        or "tid_sJKHMdAQGSDbJgIZUOoZltQsaWuUlbGaundBPOmwCdvQIJjMfJ"
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
    bucket = os.getenv("S3_BUCKET_NAME") or os.getenv("AWS_STORAGE_BUCKET_NAME") or os.getenv("BUCKET_NAME") or "resilient-module-m3qmihat"
    endpoint = (os.getenv("S3_ENDPOINT_URL") or os.getenv("AWS_ENDPOINT_URL_S3") or "https://t3.storageapi.dev").rstrip("/")

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
        },
        "student_id": student.student_id,
        "full_name": student.full_name,
        "group_name": student.group.group_name if student.group else "",
        "year_of_study": student.year_of_study or 2,
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

    # 1. Dropped class IDs for this student
    dropped_class_ids = set(
        StudentClassEnrollment.objects.filter(
            student=student, status='dropped'
        ).values_list('course_class_id', flat=True)
    )

    # 2. Base group slots (excluding explicitly dropped classes)
    base_slots = GroupTimetableSlot.objects.filter(group=group).select_related(
        'course_class__subject', 'course_class__professor', 'course_class__group'
    ).exclude(course_class_id__in=dropped_class_ids).order_by('day_of_week', 'start_time')

    # 3. Extra enrolled classes outside base group (retakes or electives)
    extra_enrollments = StudentClassEnrollment.objects.filter(
        student=student, status='active'
    ).exclude(course_class__group=group).select_related(
        'course_class__subject', 'course_class__professor', 'course_class__group'
    )
    extra_class_ids = [e.course_class_id for e in extra_enrollments]
    extra_slots = GroupTimetableSlot.objects.filter(
        course_class_id__in=extra_class_ids
    ).select_related(
        'course_class__subject', 'course_class__professor', 'course_class__group'
    ).order_by('day_of_week', 'start_time')

    # 4. Schedule overrides
    overrides = ScheduleOverride.objects.filter(student=student).select_related(
        'course_class__subject', 'course_class__professor', 'course_class__group'
    ).order_by('day_of_week', 'start_time')

    overridden_subject_ids = {ov.course_class.subject_id for ov in overrides}
    extra_subject_ids = {slot.course_class.subject_id for slot in extra_slots}

    schedule = []

    # Add base slots (if not overridden by one-time makeup and not replaced by permanent extra)
    for slot in base_slots:
        cc = slot.course_class
        if cc.subject_id not in overridden_subject_ids and cc.subject_id not in extra_subject_ids:
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

    # Add extra slots (permanently changed sections or retakes)
    for slot in extra_slots:
        cc = slot.course_class
        if cc.subject_id not in overridden_subject_ids:
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

    # Add one-time overrides
    for ov in overrides:
        cc = ov.course_class
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
            "is_one_time": True,
            "reverts_next_week": True,
            "original_group": group_name,
            "actual_group": cc.group.group_name,
        })

    schedule.sort(key=lambda x: (x["day_of_week"], x["start_time"]))

    # Calculate session numbers for multi-session subjects (e.g. Session 1 of 2)
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

    return Response({
        "student": StudentSerializer(student).data,
        "student_id": student.student_id,
        "student_name": student.full_name,
        "group_name": group_name,
        "timetable_image_url": image_url,
        "schedule": schedule,
        "timetable": schedule,
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
    """Marks a course class as dropped for a student."""
    student = resolve_student_obj(student_id)
    if not student:
        return Response({"error": "Student not found"}, status=status.HTTP_404_NOT_FOUND)

    class_id = request.data.get('class_id')
    if not class_id:
        return Response({"error": "class_id is required"}, status=status.HTTP_400_BAD_REQUEST)

    enr = StudentClassEnrollment.objects.filter(student=student, course_class_id=class_id).first()
    if enr:
        enr.status = 'dropped'
        enr.dropped_at = datetime.datetime.now(datetime.timezone.utc)
        enr.save()

    return Response({"success": True, "message": "Course successfully dropped"})


@api_view(['POST'])
@permission_classes([AllowAny])
def student_retake_class(request, student_id):
    """Re-enrolls a previously dropped course class."""
    student = resolve_student_obj(student_id)
    if not student:
        return Response({"error": "Student not found"}, status=status.HTTP_404_NOT_FOUND)

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

    return Response({"success": True, "message": "Course successfully re-enrolled"})


@api_view(['GET'])
@permission_classes([AllowAny])
def student_retake_catalog(request, student_id):
    """Returns course catalog available for retakes up to the student's study year."""
    student = resolve_student_obj(student_id)
    if not student:
        return Response({"error": "Student not found"}, status=status.HTTP_404_NOT_FOUND)

    user_year = student.year_of_study or 2
    available_years = list(range(1, user_year + 1))

    subjects = Subject.objects.filter(year_level__in=available_years).order_by('year_level', 'full_name')

    enrollments = {
        e.course_class.subject_id: e
        for e in StudentClassEnrollment.objects.filter(student=student).select_related('course_class')
    }

    subj_list = []
    for s in subjects:
        enr = enrollments.get(s.subject_id)
        enr_status = enr.status if enr else 'none'
        subj_list.append({
            "subject_id": s.subject_id,
            "short_name": s.short_name,
            "full_name": s.full_name,
            "year_level": s.year_level,
            "enrollment_status": enr_status,
            "is_enrolled": (enr_status == 'active'),
            "current_class_id": enr.course_class_id if enr else None,
        })

    return Response({
        "student_id": student.student_id,
        "student_name": student.full_name,
        "student_year": user_year,
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

    class_id = request.data.get('class_id')
    if not class_id:
        return Response({"error": "class_id is required"}, status=status.HTTP_400_BAD_REQUEST)

    cc = get_object_or_404(CourseClass.objects.select_related('subject', 'group'), class_id=class_id)

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
        slots = GroupTimetableSlot.objects.filter(course_class=cc)
        for slot in slots:
            ScheduleOverride.objects.create(
                student=student,
                day_of_week=slot.day_of_week,
                start_time=slot.start_time,
                end_time=slot.end_time,
                course_class=cc,
            )

    return Response({
        "success": True,
        "message": f"Successfully registered for retake course: {cc.subject.full_name} ({cc.subject.short_name})"
    })


@api_view(['GET'])
@permission_classes([AllowAny])
def subject_available_groups(request, subject_id):
    """Returns all class sections teaching a subject across all groups."""
    subject = get_object_or_404(Subject, subject_id=subject_id)
    student_param = request.query_params.get('student_telegram_id', '')
    student = resolve_student_obj(student_param)
    student_group_id = student.group_id if student else None

    classes = CourseClass.objects.filter(subject=subject).select_related('group', 'professor')

    options = []
    for c in classes:
        slots = GroupTimetableSlot.objects.filter(course_class=c).order_by('day_of_week', 'start_time')
        slot_list = []
        for s in slots:
            slot_list.append({
                "day_of_week": s.day_of_week,
                "day_name": DAY_NAMES.get(s.day_of_week, f"Day {s.day_of_week}"),
                "start_time": s.start_time,
                "end_time": s.end_time,
                "room": c.room or "TBA",
                "is_upcoming": True,
            })

        primary_slot = slot_list[0] if slot_list else None
        time_sum = ", ".join([f"{s['day_name']} {s['start_time']}-{s['end_time']}" for s in slot_list])
        is_own = (c.group_id == student_group_id)

        options.append({
            "class_id": c.class_id,
            "group_name": c.group.group_name,
            "professor": c.professor.full_name,
            "day_of_week": primary_slot["day_of_week"] if primary_slot else 1,
            "day_name": primary_slot["day_name"] if primary_slot else "TBA",
            "start_time": primary_slot["start_time"] if primary_slot else "09:00",
            "end_time": primary_slot["end_time"] if primary_slot else "10:30",
            "room": c.room or "TBA",
            "sessions_per_week": len(slot_list),
            "slots": slot_list,
            "time_summary": time_sum,
            "is_own_group": is_own,
            "is_available": True,
            "is_upcoming": True,
            "recommended": is_own,
        })

    return Response({"options": options})


@api_view(['POST'])
@permission_classes([AllowAny])
def student_change_group(request, student_id):
    """Applies permanent or one-time make-up section change for a student."""
    student = resolve_student_obj(student_id)
    if not student:
        return Response({"error": "Student not found"}, status=status.HTTP_404_NOT_FOUND)

    new_class_id = request.data.get('new_class_id')
    change_type = request.data.get('change_type', 'permanent')

    new_class = get_object_or_404(CourseClass.objects.select_related('subject', 'group'), class_id=new_class_id)
    subj = new_class.subject

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
            "message": f"Permanently moved {subj.full_name} ({subj.short_name}) to section {new_class.group.group_name}."
        })
    else:
        ScheduleOverride.objects.filter(student=student, course_class__subject=subj).delete()
        slots = GroupTimetableSlot.objects.filter(course_class=new_class)
        for s in slots:
            ScheduleOverride.objects.create(
                student=student,
                day_of_week=s.day_of_week,
                start_time=s.start_time,
                end_time=s.end_time,
                course_class=new_class,
            )

        return Response({
            "success": True,
            "mode": "one_time",
            "message": f"Scheduled one-time make-up lesson with section {new_class.group.group_name} for this week."
        })


@api_view(['POST'])
@permission_classes([AllowAny])
def student_revert_override(request, student_id):
    """Reverts one-time or permanent section change back to primary group schedule."""
    student = resolve_student_obj(student_id)
    if not student:
        return Response({"error": "Student not found"}, status=status.HTTP_404_NOT_FOUND)

    subject_id = request.data.get('subject_id')
    if not subject_id:
        return Response({"error": "subject_id is required"}, status=status.HTTP_400_BAD_REQUEST)

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
        "message": "Schedule reverted back to your regular primary group timetable."
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
        if enabled is not None:
            setting.enabled = 1 if enabled else 0
        if minutes_before is not None:
            setting.minutes_before = int(minutes_before)
        setting.save()

    return Response({
        "enabled": bool(setting.enabled),
        "minutes_before": setting.minutes_before,
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

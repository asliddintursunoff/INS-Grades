import datetime
from django.db import connection
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
        db_connected = False
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
def get_student_timetable(request, student_id):
    """Retrieve full weekly schedule with overrides for a student."""
    student = get_object_or_404(Student.objects.select_related('group'), student_id=student_id)

    # 1. Base group timetable slots
    base_slots = GroupTimetableSlot.objects.filter(group=student.group).select_related(
        'course_class__subject', 'course_class__professor', 'course_class__group'
    ).order_by('day_of_week', 'start_time')

    # 2. Overrides for this student
    overrides = ScheduleOverride.objects.filter(student=student).select_related(
        'course_class__subject', 'course_class__professor', 'course_class__group'
    )

    override_map = {}
    for ov in overrides:
        override_map[(ov.day_of_week, ov.start_time)] = ov

    schedule = []
    for slot in base_slots:
        key = (slot.day_of_week, slot.start_time)
        if key in override_map:
            ov = override_map[key]
            cc = ov.course_class
            schedule.append({
                "slot_id": slot.slot_id,
                "day_of_week": ov.day_of_week,
                "start_time": ov.start_time,
                "end_time": ov.end_time,
                "subject": cc.subject.full_name,
                "subject_short": cc.subject.short_name,
                "professor": cc.professor.full_name,
                "room": cc.room,
                "is_override": True,
            })
        else:
            cc = slot.course_class
            schedule.append({
                "slot_id": slot.slot_id,
                "day_of_week": slot.day_of_week,
                "start_time": slot.start_time,
                "end_time": slot.end_time,
                "subject": cc.subject.full_name,
                "subject_short": cc.subject.short_name,
                "professor": cc.professor.full_name,
                "room": cc.room,
                "is_override": False,
            })

    return Response({
        "student": StudentSerializer(student).data,
        "student_id": student.student_id,
        "student_name": student.full_name,
        "group_name": student.group.group_name if student.group else "",
        "timetable_image_url": student.group.timetable_image_url if (student.group and student.group.timetable_image_url) else "",
        "timetable": schedule,
        "schedule": schedule,
    })


@api_view(['GET'])
def get_group_timetable(request, group_id):
    """Retrieve base timetable slots for a group."""
    group = get_object_or_404(Group, group_id=group_id)
    slots = GroupTimetableSlot.objects.filter(group=group).select_related(
        'course_class__subject', 'course_class__professor'
    ).order_by('day_of_week', 'start_time')

    return Response({
        "group": GroupSerializer(group).data,
        "group_name": group.group_name,
        "timetable_image_url": group.timetable_image_url or "",
        "slots": GroupTimetableSlotSerializer(slots, many=True).data
    })


@api_view(['POST'])
def link_telegram(request):
    """Link a student_id to a Telegram account (telegram_id and optional username)."""
    student_id = request.data.get('student_id')
    telegram_id = request.data.get('telegram_id')
    telegram_username = request.data.get('telegram_username', '')

    if not student_id or not telegram_id:
        return Response(
            {"error": "student_id and telegram_id are required."},
            status=status.HTTP_400_BAD_REQUEST
        )

    student = get_object_or_404(Student, student_id=student_id)
    student.telegram_id = telegram_id
    if telegram_username:
        student.telegram_username = telegram_username
    student.save()

    return Response({
        "message": f"Successfully linked student {student.full_name} to Telegram ID {telegram_id}.",
        "student": StudentSerializer(student).data
    })


@api_view(['GET', 'POST'])
def student_homework(request, student_id):
    """List homework for a student or update homework status."""
    student = get_object_or_404(Student, student_id=student_id)

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
def student_attendance(request, student_id):
    """Retrieve attendance and absence counts for a student."""
    student = get_object_or_404(Student, student_id=student_id)
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


@api_view(['GET', 'POST'])
def notification_settings(request, student_id):
    """Get or update notification preferences for a student."""
    student = get_object_or_404(Student, student_id=student_id)
    setting, _ = NotificationSettings.objects.get_or_create(
        student=student,
        defaults={'enabled': 1, 'minutes_before': 30}
    )

    if request.method == 'POST':
        enabled = request.data.get('enabled')
        minutes_before = request.data.get('minutes_before')
        if enabled is not None:
            setting.enabled = 1 if enabled else 0
        if minutes_before is not None:
            setting.minutes_before = int(minutes_before)
        setting.save()

    return Response(NotificationSettingsSerializer(setting).data)

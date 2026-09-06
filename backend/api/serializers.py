from rest_framework import serializers
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

class ProfessorSerializer(serializers.ModelSerializer):
    class Meta:
        model = Professor
        fields = '__all__'


class GroupSerializer(serializers.ModelSerializer):
    class Meta:
        model = Group
        fields = '__all__'


class SubjectSerializer(serializers.ModelSerializer):
    class Meta:
        model = Subject
        fields = '__all__'


class CourseClassSerializer(serializers.ModelSerializer):
    subject = SubjectSerializer(read_only=True)
    professor = ProfessorSerializer(read_only=True)
    group = GroupSerializer(read_only=True)

    class Meta:
        model = CourseClass
        fields = '__all__'


class StudentSerializer(serializers.ModelSerializer):
    group = GroupSerializer(read_only=True)
    group_name = serializers.CharField(source='group.group_name', read_only=True)
    timetable_image_url = serializers.CharField(source='group.timetable_image_url', read_only=True, default='')
    is_premium = serializers.BooleanField(source='has_premium', read_only=True)
    plan = serializers.SerializerMethodField()

    def get_plan(self, obj):
        return 'premium' if getattr(obj, 'has_premium', False) else 'free'

    class Meta:
        model = Student
        fields = [
            'student_id',
            'full_name',
            'group',
            'group_name',
            'timetable_image_url',
            'year_of_study',
            'telegram_id',
            'telegram_username',
            'is_premium',
            'plan',
            'premium_expires_at',
        ]


class GroupTimetableSlotSerializer(serializers.ModelSerializer):
    course_class = CourseClassSerializer(read_only=True)

    class Meta:
        model = GroupTimetableSlot
        fields = '__all__'


class ScheduleOverrideSerializer(serializers.ModelSerializer):
    course_class = CourseClassSerializer(read_only=True)

    class Meta:
        model = ScheduleOverride
        fields = '__all__'


class HomeworkSubmissionSerializer(serializers.ModelSerializer):
    class Meta:
        model = HomeworkSubmission
        fields = '__all__'


class HomeworkSerializer(serializers.ModelSerializer):
    course_class = CourseClassSerializer(read_only=True)
    submissions = HomeworkSubmissionSerializer(many=True, read_only=True)

    class Meta:
        model = Homework
        fields = '__all__'


class LectureSessionSerializer(serializers.ModelSerializer):
    course_class = CourseClassSerializer(read_only=True)

    class Meta:
        model = LectureSession
        fields = '__all__'


class AttendanceSerializer(serializers.ModelSerializer):
    session = LectureSessionSerializer(read_only=True)

    class Meta:
        model = Attendance
        fields = '__all__'


class NotificationSettingsSerializer(serializers.ModelSerializer):
    class Meta:
        model = NotificationSettings
        fields = '__all__'

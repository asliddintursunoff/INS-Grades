from django.contrib import admin
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

@admin.register(Professor)
class ProfessorAdmin(admin.ModelAdmin):
    list_display = ('professor_id', 'full_name', 'email')
    search_fields = ('full_name', 'email')

@admin.register(Group)
class GroupAdmin(admin.ModelAdmin):
    list_display = ('group_id', 'group_name')
    search_fields = ('group_name',)

@admin.register(Student)
class StudentAdmin(admin.ModelAdmin):
    list_display = ('student_id', 'full_name', 'group', 'year_of_study', 'telegram_id')
    list_filter = ('group', 'year_of_study')
    search_fields = ('student_id', 'full_name', 'telegram_username')

@admin.register(Subject)
class SubjectAdmin(admin.ModelAdmin):
    list_display = ('subject_id', 'short_name', 'full_name', 'year_level')
    list_filter = ('year_level',)
    search_fields = ('short_name', 'full_name')

@admin.register(CourseClass)
class CourseClassAdmin(admin.ModelAdmin):
    list_display = ('class_id', 'subject', 'professor', 'group', 'room')
    list_filter = ('group', 'subject')

@admin.register(GroupTimetableSlot)
class GroupTimetableSlotAdmin(admin.ModelAdmin):
    list_display = ('slot_id', 'group', 'day_of_week', 'start_time', 'end_time', 'course_class')
    list_filter = ('group', 'day_of_week')

@admin.register(Homework)
class HomeworkAdmin(admin.ModelAdmin):
    list_display = ('homework_id', 'course_class', 'title', 'deadline')

@admin.register(Attendance)
class AttendanceAdmin(admin.ModelAdmin):
    list_display = ('attendance_id', 'student', 'session', 'status', 'created_at')
    list_filter = ('status',)

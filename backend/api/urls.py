from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    health_check,
    ProfessorViewSet,
    GroupViewSet,
    SubjectViewSet,
    CourseClassViewSet,
    StudentViewSet,
    get_student_timetable,
    get_group_timetable,
    link_telegram,
    student_homework,
    student_attendance,
    notification_settings,
)

router = DefaultRouter()
router.register(r'professors', ProfessorViewSet)
router.register(r'groups', GroupViewSet)
router.register(r'subjects', SubjectViewSet)
router.register(r'classes', CourseClassViewSet)
router.register(r'students', StudentViewSet)

urlpatterns = [
    path('health/', health_check, name='health_check'),
    path('timetable/student/<str:student_id>/', get_student_timetable, name='student_timetable'),
    path('timetable/group/<int:group_id>/', get_group_timetable, name='group_timetable'),
    path('students/link-telegram/', link_telegram, name='link_telegram'),
    path('homework/student/<str:student_id>/', student_homework, name='student_homework'),
    path('attendance/student/<str:student_id>/', student_attendance, name='student_attendance'),
    path('notifications/settings/<str:student_id>/', notification_settings, name='notification_settings'),
    path('', include(router.urls)),
]

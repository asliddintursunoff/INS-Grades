from django.urls import path, re_path, include
from rest_framework.routers import DefaultRouter
from .views import (
    health_check,
    system_status,
    demo_students,
    auth_session,
    auth_me,
    auth_link,
    get_student_timetable,
    get_group_timetable,
    student_classes,
    student_drop_class,
    student_retake_class,
    student_retake_catalog,
    student_enroll_retake,
    subject_available_groups,
    student_change_group,
    student_revert_override,
    student_absences,
    session_makeup_options,
    session_record_makeup,
    student_notification_settings,
    link_telegram,
    student_homework,
    student_attendance,
    ProfessorViewSet,
    GroupViewSet,
    SubjectViewSet,
    CourseClassViewSet,
    StudentViewSet,
)

router = DefaultRouter()
router.register(r'professors', ProfessorViewSet)
router.register(r'groups', GroupViewSet)
router.register(r'subjects', SubjectViewSet)
router.register(r'classes', CourseClassViewSet)
router.register(r'students', StudentViewSet)

urlpatterns = [
    # Health & System Status
    re_path(r'^health/?$', health_check, name='health_check'),
    re_path(r'^system/status/?$', system_status, name='system_status'),

    # Mini App Initial Data & Auth Handshake
    re_path(r'^demo/students/?$', demo_students, name='demo_students'),
    re_path(r'^auth/session/?$', auth_session, name='auth_session'),
    re_path(r'^auth/me/(?P<telegram_id>[^/]+)/?$', auth_me, name='auth_me'),
    re_path(r'^auth/link/?$', auth_link, name='auth_link'),
    re_path(r'^students/link-telegram/?$', link_telegram, name='link_telegram'),

    # Timetable Operations
    re_path(r'^students/(?P<student_id>[^/]+)/timetable/?$', get_student_timetable, name='student_timetable_direct'),
    re_path(r'^timetable/student/(?P<student_id>[^/]+)/?$', get_student_timetable, name='student_timetable_legacy'),
    re_path(r'^timetable/group/(?P<group_id>\d+)/?$', get_group_timetable, name='group_timetable'),

    # Classes, Drop & Retake
    re_path(r'^students/(?P<student_id>[^/]+)/classes/?$', student_classes, name='student_classes'),
    re_path(r'^students/(?P<student_id>[^/]+)/drop/?$', student_drop_class, name='student_drop'),
    re_path(r'^students/(?P<student_id>[^/]+)/retake/?$', student_retake_class, name='student_retake'),
    re_path(r'^students/(?P<student_id>[^/]+)/retake-catalog/?$', student_retake_catalog, name='student_retake_catalog'),
    re_path(r'^students/(?P<student_id>[^/]+)/enroll-retake/?$', student_enroll_retake, name='student_enroll_retake'),

    # Section / Group Switching & Overrides
    re_path(r'^subjects/(?P<subject_id>\d+)/available-groups/?$', subject_available_groups, name='subject_available_groups'),
    re_path(r'^students/(?P<student_id>[^/]+)/change-group/?$', student_change_group, name='student_change_group'),
    re_path(r'^students/(?P<student_id>[^/]+)/revert-override/?$', student_revert_override, name='student_revert_override'),

    # Attendance & Makeup Lessons
    re_path(r'^students/(?P<student_id>[^/]+)/absences/?$', student_absences, name='student_absences'),
    re_path(r'^attendance/student/(?P<student_id>[^/]+)/?$', student_attendance, name='student_attendance'),
    re_path(r'^attendance/(?P<session_id>\d+)/makeup-options/?$', session_makeup_options, name='session_makeup_options'),
    re_path(r'^attendance/(?P<session_id>\d+)/makeup/?$', session_record_makeup, name='session_record_makeup'),

    # Homework
    re_path(r'^homework/student/(?P<student_id>[^/]+)/?$', student_homework, name='student_homework'),

    # Notifications Settings
    re_path(r'^students/(?P<student_id>[^/]+)/notification-settings/?$', student_notification_settings, name='student_notification_settings'),
    re_path(r'^notifications/settings/(?P<student_id>[^/]+)/?$', student_notification_settings, name='notifications_settings_legacy'),

    # ModelViewSet CRUD Router
    path('', include(router.urls)),
]

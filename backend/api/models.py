import uuid
from django.db import models
from django.utils import timezone

class Professor(models.Model):
    professor_id = models.AutoField(primary_key=True)
    full_name = models.CharField(max_length=255)
    email = models.EmailField(max_length=255, unique=True, null=True, blank=True)

    class Meta:
        db_table = 'professors'
        verbose_name = 'Professor'
        verbose_name_plural = 'Professors'

    def __str__(self):
        return self.full_name


class Group(models.Model):
    group_id = models.AutoField(primary_key=True)
    group_name = models.CharField(max_length=100, unique=True)
    timetable_image_url = models.TextField(null=True, blank=True)

    class Meta:
        db_table = 'groups'
        verbose_name = 'Group'
        verbose_name_plural = 'Groups'

    def __str__(self):
        return self.group_name


class Student(models.Model):
    student_id = models.CharField(max_length=50, primary_key=True)
    full_name = models.CharField(max_length=255)
    group = models.ForeignKey(Group, on_delete=models.CASCADE, db_column='group_id', related_name='students')
    year_of_study = models.IntegerField(default=2)
    telegram_id = models.BigIntegerField(unique=True, null=True, blank=True)
    telegram_username = models.CharField(max_length=100, null=True, blank=True)
    is_premium = models.BooleanField(default=False)
    premium_expires_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = 'students'
        verbose_name = 'Student'
        verbose_name_plural = 'Students'

    @property
    def has_premium(self):
        if not self.is_premium:
            return False
        if self.premium_expires_at:
            import datetime
            now_utc = datetime.datetime.now(datetime.timezone.utc)
            if self.premium_expires_at < now_utc:
                return False
        return True

    def __str__(self):
        return f"{self.full_name} ({self.student_id})"


class Subject(models.Model):
    subject_id = models.AutoField(primary_key=True)
    short_name = models.CharField(max_length=50)
    full_name = models.CharField(max_length=255)
    year_level = models.IntegerField(default=1)

    class Meta:
        db_table = 'subjects'
        verbose_name = 'Subject'
        verbose_name_plural = 'Subjects'

    def __str__(self):
        return f"{self.full_name} ({self.short_name})"


class CourseClass(models.Model):
    class_id = models.AutoField(primary_key=True)
    subject = models.ForeignKey(Subject, on_delete=models.CASCADE, db_column='subject_id', related_name='classes')
    professor = models.ForeignKey(Professor, on_delete=models.CASCADE, db_column='professor_id', related_name='classes')
    group = models.ForeignKey(Group, on_delete=models.CASCADE, db_column='group_id', related_name='classes')
    room = models.CharField(max_length=50, null=True, blank=True)

    class Meta:
        db_table = 'classes'
        verbose_name = 'Class'
        verbose_name_plural = 'Classes'

    def __str__(self):
        return f"{self.subject.short_name} - {self.group.group_name} ({self.room})"


class GroupTimetableSlot(models.Model):
    slot_id = models.AutoField(primary_key=True)
    group = models.ForeignKey(Group, on_delete=models.CASCADE, db_column='group_id', related_name='timetable_slots')
    day_of_week = models.IntegerField()  # 1=Monday ... 7=Sunday
    start_time = models.CharField(max_length=10)
    end_time = models.CharField(max_length=10)
    course_class = models.ForeignKey(CourseClass, on_delete=models.CASCADE, db_column='class_id', related_name='timetable_slots')

    class Meta:
        db_table = 'group_timetable'
        verbose_name = 'Timetable Slot'
        verbose_name_plural = 'Timetable Slots'


class ScheduleOverride(models.Model):
    override_id = models.AutoField(primary_key=True)
    student = models.ForeignKey(Student, on_delete=models.CASCADE, db_column='student_id', related_name='schedule_overrides')
    day_of_week = models.IntegerField()
    start_time = models.CharField(max_length=10)
    end_time = models.CharField(max_length=10)
    course_class = models.ForeignKey(CourseClass, on_delete=models.CASCADE, db_column='class_id', related_name='schedule_overrides')
    valid_from = models.CharField(max_length=50, null=True, blank=True)
    valid_to = models.CharField(max_length=50, null=True, blank=True)

    class Meta:
        db_table = 'student_schedule_overrides'
        verbose_name = 'Schedule Override'
        verbose_name_plural = 'Schedule Overrides'


class StudentClassEnrollment(models.Model):
    enrollment_id = models.AutoField(primary_key=True)
    student = models.ForeignKey(Student, on_delete=models.CASCADE, db_column='student_id', related_name='enrollments')
    course_class = models.ForeignKey(CourseClass, on_delete=models.CASCADE, db_column='class_id', related_name='enrollments')
    status = models.CharField(max_length=50, default='active')
    enrolled_at = models.DateTimeField(auto_now_add=True)
    dropped_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = 'student_class_enrollment'
        unique_together = ('student', 'course_class')
        verbose_name = 'Enrollment'
        verbose_name_plural = 'Enrollments'


class Homework(models.Model):
    homework_id = models.AutoField(primary_key=True)
    course_class = models.ForeignKey(CourseClass, on_delete=models.CASCADE, db_column='class_id', related_name='homeworks')
    title = models.CharField(max_length=255)
    description = models.TextField(null=True, blank=True)
    deadline = models.CharField(max_length=100)

    class Meta:
        db_table = 'homeworks'
        verbose_name = 'Homework'
        verbose_name_plural = 'Homeworks'


class HomeworkSubmission(models.Model):
    submission_id = models.AutoField(primary_key=True)
    homework = models.ForeignKey(Homework, on_delete=models.CASCADE, db_column='homework_id', related_name='submissions')
    student = models.ForeignKey(Student, on_delete=models.CASCADE, db_column='student_id', related_name='homework_submissions')
    is_done = models.IntegerField(default=0)
    is_active = models.IntegerField(default=1)
    submitted_at = models.DateTimeField(null=True, blank=True)
    grade = models.FloatField(null=True, blank=True)

    class Meta:
        db_table = 'homework_submissions'
        unique_together = ('homework', 'student')
        verbose_name = 'Homework Submission'
        verbose_name_plural = 'Homework Submissions'


class LectureSession(models.Model):
    session_id = models.AutoField(primary_key=True)
    course_class = models.ForeignKey(CourseClass, on_delete=models.CASCADE, db_column='class_id', related_name='lecture_sessions')
    session_date = models.CharField(max_length=50)
    start_time = models.CharField(max_length=10)
    end_time = models.CharField(max_length=10)

    class Meta:
        db_table = 'lecture_sessions'
        unique_together = ('course_class', 'session_date')
        verbose_name = 'Lecture Session'
        verbose_name_plural = 'Lecture Sessions'


class Attendance(models.Model):
    attendance_id = models.AutoField(primary_key=True)
    student = models.ForeignKey(Student, on_delete=models.CASCADE, db_column='student_id', related_name='attendance_records')
    session = models.ForeignKey(LectureSession, on_delete=models.CASCADE, db_column='session_id', related_name='attendances')
    status = models.CharField(max_length=50, default='absent')
    makeup_session = models.ForeignKey(LectureSession, on_delete=models.SET_NULL, db_column='makeup_session_id', null=True, blank=True, related_name='makeups')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'attendance'
        unique_together = ('student', 'session')
        verbose_name = 'Attendance'
        verbose_name_plural = 'Attendances'


class NotificationSettings(models.Model):
    student = models.OneToOneField(Student, on_delete=models.CASCADE, db_column='student_id', primary_key=True, related_name='notification_settings')
    enabled = models.IntegerField(default=1)
    minutes_before = models.IntegerField(default=30)

    class Meta:
        db_table = 'notification_settings'
        verbose_name = 'Notification Setting'
        verbose_name_plural = 'Notification Settings'


class SentNotification(models.Model):
    id = models.AutoField(primary_key=True)
    student = models.ForeignKey(Student, on_delete=models.CASCADE, db_column='student_id', related_name='sent_notifications')
    session = models.ForeignKey(LectureSession, on_delete=models.CASCADE, db_column='session_id', related_name='sent_notifications')
    sent_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'sent_notifications'
        verbose_name = 'Sent Notification'
        verbose_name_plural = 'Sent Notifications'


class ClassNotificationLog(models.Model):
    id = models.AutoField(primary_key=True)
    student = models.ForeignKey(Student, on_delete=models.CASCADE, db_column='student_id', related_name='class_reminders')
    notification_date = models.DateField()
    slot_key = models.CharField(max_length=100)
    sent_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'class_notification_logs'
        unique_together = ('student', 'notification_date', 'slot_key')
        verbose_name = 'Class Notification Log'
        verbose_name_plural = 'Class Notification Logs'


class PaymentTransaction(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('completed', 'Completed'),
        ('expired', 'Expired'),
        ('cancelled', 'Cancelled'),
    ]

    transaction_id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    student = models.ForeignKey(Student, on_delete=models.CASCADE, db_column='student_id', related_name='payments')
    base_amount = models.IntegerField(default=10000)
    salt = models.IntegerField(db_index=True)
    total_amount = models.IntegerField(db_index=True)
    card_number = models.CharField(max_length=30)
    card_holder = models.CharField(max_length=100, default='Asliddin Tursunov')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending', db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField(db_index=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    telegram_message_id = models.CharField(max_length=100, null=True, blank=True, unique=True)

    class Meta:
        db_table = 'payment_transactions'
        indexes = [
            models.Index(fields=['status', 'total_amount', 'expires_at']),
        ]
        verbose_name = 'Payment Transaction'
        verbose_name_plural = 'Payment Transactions'

    @property
    def is_expired(self):
        return self.status == 'pending' and timezone.now() > self.expires_at

    def __str__(self):
        return f"Payment {self.transaction_id} - {self.student_id} - {self.total_amount} UZS ({self.status})"


class PaymentAuditLog(models.Model):
    log_id = models.AutoField(primary_key=True)
    sender = models.CharField(max_length=100, null=True, blank=True)
    raw_message = models.TextField()
    extracted_amount = models.IntegerField(null=True, blank=True)
    matched_transaction = models.ForeignKey(
        PaymentTransaction, on_delete=models.SET_NULL, null=True, blank=True, related_name='audit_logs'
    )
    is_matched = models.BooleanField(default=False)
    error_details = models.TextField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'payment_audit_logs'
        ordering = ['-created_at']
        verbose_name = 'Payment Audit Log'
        verbose_name_plural = 'Payment Audit Logs'

    def __str__(self):
        return f"Audit {self.log_id} - {self.extracted_amount} UZS - Matched: {self.is_matched}"

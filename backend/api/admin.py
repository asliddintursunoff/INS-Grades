from django.contrib import admin
from django.utils import timezone
from django.utils.html import format_html
from django.db import models
from django.db.models import Sum, Count, Avg, Q
from django.db.models.functions import TruncMonth
import datetime

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
    PaymentTransaction,
    PaymentAuditLog,
    BotUser,
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

@admin.register(PaymentTransaction)
class PaymentTransactionAdmin(admin.ModelAdmin):
    list_display = ('transaction_id_short', 'student_info', 'formatted_amount', 'status_badge', 'created_at', 'completed_at')
    list_filter = ('status', 'created_at', 'completed_at')
    search_fields = ('student__student_id', 'student__full_name', 'total_amount', 'card_number')
    readonly_fields = ('transaction_id', 'created_at', 'completed_at')

    def transaction_id_short(self, obj):
        return str(obj.transaction_id)[:8] + "..."
    transaction_id_short.short_description = "Tx ID"

    def student_info(self, obj):
        return f"{obj.student.full_name} ({obj.student.student_id})"
    student_info.short_description = "Talaba"

    def formatted_amount(self, obj):
        return f"{obj.total_amount:,} UZS".replace(',', ' ')
    formatted_amount.short_description = "Summa"

    def status_badge(self, obj):
        colors = {
            'completed': '#10b981',
            'pending': '#f59e0b',
            'expired': '#94a3b8',
            'cancelled': '#ef4444'
        }
        color = colors.get(obj.status, '#6b7280')
        return format_html(
            '<span style="background:{}; color:#fff; padding:3px 8px; border-radius:10px; font-size:11px; font-weight:bold;">{}</span>',
            color, obj.status.upper()
        )
    status_badge.short_description = "Holat"


@admin.register(PaymentAuditLog)
class PaymentAuditLogAdmin(admin.ModelAdmin):
    list_display = ('log_id', 'sender', 'extracted_amount', 'is_matched', 'created_at')
    list_filter = ('is_matched', 'created_at')
    search_fields = ('raw_message', 'sender', 'extracted_amount')


@admin.register(BotUser)
class BotUserAdmin(admin.ModelAdmin):
    list_display = ('telegram_id', 'username', 'first_name', 'last_name', 'student_info', 'created_at', 'last_active_at', 'is_active')
    list_filter = ('is_active', 'created_at', 'last_active_at')
    search_fields = ('telegram_id', 'username', 'first_name', 'last_name', 'student__student_id', 'student__full_name')
    readonly_fields = ('created_at', 'last_active_at')

    def student_info(self, obj):
        if obj.student:
            return f"{obj.student.full_name} ({obj.student.student_id})"
        return "-"
    student_info.short_description = "Ulangan Talaba"


# ------------------------------------------------------------------------------
# Django Admin Dashboard & Live Statistics Hook
# ------------------------------------------------------------------------------
admin.site.site_header = "INS Grades Boshqaruv & Statistika Paneli"
admin.site.site_title = "INS Grades Admin"
admin.site.index_title = "Universitet Dars Jadvali & Moliyaviy Analitika"

original_admin_index = admin.site.index

def custom_admin_index(request, extra_context=None):
    extra_context = extra_context or {}
    now = timezone.now()
    today = now.date()
    current_year = now.year
    current_month = now.month

    completed_txs = PaymentTransaction.objects.filter(status='completed')
    total_revenue = completed_txs.aggregate(s=Sum('total_amount'))['s'] or 0
    total_purchases_count = completed_txs.count()

    month_txs = completed_txs.filter(
        completed_at__year=current_year, completed_at__month=current_month
    )
    month_revenue = month_txs.aggregate(s=Sum('total_amount'))['s'] or 0
    month_purchases_count = month_txs.count()

    today_txs = completed_txs.filter(completed_at__date=today)
    today_revenue = today_txs.aggregate(s=Sum('total_amount'))['s'] or 0
    today_purchases_count = today_txs.count()

    monthly_sales_qs = (
        completed_txs.annotate(month=TruncMonth('completed_at'))
        .values('month')
        .annotate(
            count=Count('transaction_id'),
            total_sum=Sum('total_amount'),
            avg_sum=Avg('total_amount'),
        )
        .order_by('-month')
    )

    monthly_sales = []
    for item in monthly_sales_qs:
        m = item['month']
        monthly_sales.append({
            'month_str': m.strftime('%Y-%m (%B)') if m else 'N/A',
            'count': item['count'],
            'total_amount_fmt': f"{item['total_sum']:,}".replace(',', ' '),
            'avg_amount_fmt': f"{round(item['avg_sum'] or 0):,}".replace(',', ' '),
        })

    total_bot_users = BotUser.objects.count()
    today_bot_users = BotUser.objects.filter(last_active_at__date=today).count()
    active_bot_users = BotUser.objects.filter(
        Q(student__isnull=False) | Q(last_active_at__gte=now - datetime.timedelta(days=30))
    ).count()

    total_students = Student.objects.count()
    linked_students = Student.objects.filter(telegram_id__isnull=False).count()
    active_premium_students = Student.objects.filter(
        is_premium=True,
        premium_expires_at__gt=now
    ).count()

    recent_transactions = completed_txs.select_related('student').order_by('-completed_at')[:8]

    def fmt_price(n):
        return f"{n:,}".replace(',', ' ')

    extra_context.update({
        'total_revenue_fmt': fmt_price(total_revenue),
        'total_purchases_count': total_purchases_count,
        'month_revenue_fmt': fmt_price(month_revenue),
        'month_purchases_count': month_purchases_count,
        'today_revenue_fmt': fmt_price(today_revenue),
        'today_purchases_count': today_purchases_count,
        'monthly_sales': monthly_sales,
        'total_bot_users': total_bot_users,
        'today_bot_users': today_bot_users,
        'active_bot_users': active_bot_users,
        'total_students': total_students,
        'linked_students': linked_students,
        'active_premium_students': active_premium_students,
        'recent_transactions': recent_transactions,
    })
    return original_admin_index(request, extra_context=extra_context)

admin.site.index = custom_admin_index


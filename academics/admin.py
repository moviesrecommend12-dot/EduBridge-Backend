from django.contrib import admin
from .models import (
    AcademicYear,
    ClassRoom,
    Section,
    Subject,
    TeachingAssignment,
    Schedule,
    Attendance,
    Grade,
    Assignment,
    AssignmentSubmission,
    PromotionRun,
    TeacherUploadedFile,
    Announcement,
    StudentYearResult,
    SubjectYearResult,
)


@admin.register(ClassRoom)
class ClassRoomAdmin(admin.ModelAdmin):
    list_display = ('name', 'grade_level')
    search_fields = ('name', 'grade_level')


@admin.register(Section)
class SectionAdmin(admin.ModelAdmin):
    list_display = ('name', 'classroom')
    list_filter = ('classroom',)
    search_fields = ('name', 'classroom__name')


@admin.register(Subject)
class SubjectAdmin(admin.ModelAdmin):
    list_display = ('name', 'code')
    search_fields = ('name', 'code')


@admin.register(AcademicYear)
class AcademicYearAdmin(admin.ModelAdmin):
    list_display = ('name', 'start_date', 'end_date', 'is_active')
    list_filter = ('is_active',)
    search_fields = ('name',)


@admin.register(StudentYearResult)
class StudentYearResultAdmin(admin.ModelAdmin):
    list_display = (
        'student',
        'academic_year',
        'average_percentage',
        'failed_subjects_count',
        'status',
        'is_published',
        'published_at',
        'calculated_at',
    )
    list_filter = ('academic_year', 'status', 'is_published')
    search_fields = ('student__student_code', 'student__user__username')
    readonly_fields = ('calculated_at', 'published_at')


@admin.register(SubjectYearResult)
class SubjectYearResultAdmin(admin.ModelAdmin):
    list_display = (
        'student',
        'subject',
        'academic_year',
        'percentage',
        'is_failed',
    )
    list_filter = ('academic_year', 'subject', 'is_failed')
    search_fields = ('student__student_code', 'student__user__username', 'subject__name')


@admin.register(PromotionRun)
class PromotionRunAdmin(admin.ModelAdmin):
    list_display = (
        'academic_year',
        'created_by',
        'created_at',
        'total_students',
        'promoted_count',
        'failed_count',
        'needs_review_count',
    )
    list_filter = ('academic_year', 'created_at')
    readonly_fields = ('created_at',)


@admin.register(TeachingAssignment)
class TeachingAssignmentAdmin(admin.ModelAdmin):
    list_display = ('teacher', 'classroom', 'section', 'subject', 'is_active')
    list_filter = ('classroom', 'section', 'subject', 'is_active')
    search_fields = (
        'teacher__user__username',
        'teacher__user__first_name',
        'teacher__user__last_name',
        'subject__name',
        'subject__code',
        'classroom__name',
        'section__name',
    )


@admin.register(Schedule)
class ScheduleAdmin(admin.ModelAdmin):
    list_display = ('section', 'subject', 'teacher', 'day_of_week', 'start_time', 'end_time', 'room_name')
    list_filter = ('day_of_week', 'classroom', 'section', 'subject')
    search_fields = ('section__name', 'subject__name', 'teacher__user__username')


@admin.register(Attendance)
class AttendanceAdmin(admin.ModelAdmin):
    list_display = ('student', 'subject', 'date', 'status', 'teacher')
    list_filter = ('status', 'date', 'subject')
    search_fields = ('student__student_code', 'student__user__username', 'subject__name')


@admin.register(Grade)
class GradeAdmin(admin.ModelAdmin):
    list_display = ('student', 'subject', 'title', 'score', 'max_score', 'date', 'teacher')
    list_filter = ('subject', 'date')
    search_fields = ('student__student_code', 'student__user__username', 'title')


@admin.register(Assignment)
class AssignmentAdmin(admin.ModelAdmin):
    list_display = ('title', 'teacher', 'classroom', 'section', 'subject', 'due_date', 'created_at')
    list_filter = ('classroom', 'section', 'subject', 'due_date')
    search_fields = ('title', 'teacher__user__username', 'subject__name')


@admin.register(AssignmentSubmission)
class AssignmentSubmissionAdmin(admin.ModelAdmin):
    list_display = ('assignment', 'student', 'status', 'grade', 'submitted_at', 'updated_at')
    list_filter = ('status', 'assignment__subject', 'assignment__section')
    search_fields = (
        'assignment__title',
        'student__student_code',
        'student__user__username',
        'student__user__first_name',
        'student__user__last_name',
    )
    readonly_fields = ('submitted_at', 'updated_at')


@admin.register(TeacherUploadedFile)
class TeacherUploadedFileAdmin(admin.ModelAdmin):
    list_display = ('title', 'teacher', 'section', 'subject', 'file_type', 'created_at')
    list_filter = ('file_type', 'classroom', 'section', 'subject')
    search_fields = ('title', 'teacher__user__username', 'subject__name')


@admin.register(Announcement)
class AnnouncementAdmin(admin.ModelAdmin):
    list_display = ('title', 'teacher', 'classroom', 'section', 'created_at')
    list_filter = ('classroom', 'section', 'created_at')
    search_fields = ('title', 'message', 'teacher__user__username')

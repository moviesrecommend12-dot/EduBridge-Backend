from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import (
    User,
    StudentProfile,
    ParentProfile,
    TeacherProfile,
    ParentStudentLink,
    ParentLinkingCode,
)


@admin.register(User)
class CustomUserAdmin(UserAdmin):
    list_display = ('username', 'email', 'role', 'is_active', 'is_staff', 'is_superuser')
    list_filter = ('role', 'is_active', 'is_staff', 'is_superuser')
    search_fields = ('username', 'email', 'first_name', 'last_name')
    ordering = ('username',)

    fieldsets = UserAdmin.fieldsets + (
        ('EduBridge Role Info', {
            'fields': ('role', 'phone')
        }),
    )

    add_fieldsets = UserAdmin.add_fieldsets + (
        ('EduBridge Role Info', {
            'fields': ('role', 'phone')
        }),
    )


@admin.register(StudentProfile)
class StudentProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'student_code', 'classroom', 'section')
    list_filter = ('classroom', 'section')
    search_fields = (
        'user__username',
        'user__first_name',
        'user__last_name',
        'student_code',
    )


@admin.register(ParentProfile)
class ParentProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'national_id')
    search_fields = (
        'user__username',
        'user__first_name',
        'user__last_name',
        'national_id',
    )


@admin.register(TeacherProfile)
class TeacherProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'employee_code', 'specialization')
    search_fields = (
        'user__username',
        'user__first_name',
        'user__last_name',
        'employee_code',
        'specialization',
    )


@admin.register(ParentStudentLink)
class ParentStudentLinkAdmin(admin.ModelAdmin):
    list_display = ('parent', 'student', 'relationship', 'created_at')
    list_filter = ('relationship',)
    search_fields = (
        'parent__user__username',
        'student__user__username',
        'student__student_code',
    )


@admin.register(ParentLinkingCode)
class ParentLinkingCodeAdmin(admin.ModelAdmin):
    list_display = ('code', 'student', 'is_used', 'expires_at', 'created_at')
    list_filter = ('is_used',)
    search_fields = ('code', 'student__student_code', 'student__user__username')
    readonly_fields = ('code', 'created_at')
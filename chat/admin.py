from django.contrib import admin

from .models import ChatRoom, Message


@admin.register(ChatRoom)
class ChatRoomAdmin(admin.ModelAdmin):
    list_display = (
        'id',
        'parent',
        'teacher',
        'student',
        'is_active',
        'updated_at',
    )
    list_filter = ('is_active', 'created_at')
    search_fields = (
        'parent__user__username',
        'teacher__user__username',
        'student__student_code',
        'student__user__username',
    )


@admin.register(Message)
class MessageAdmin(admin.ModelAdmin):
    list_display = (
        'id',
        'room',
        'sender',
        'is_read',
        'created_at',
    )
    list_filter = ('is_read', 'created_at')
    search_fields = (
        'sender__username',
        'content',
    )
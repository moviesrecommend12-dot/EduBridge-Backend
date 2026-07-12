from django.contrib import admin
from .models import (
    Notification,
    NotificationPreference,
    NotificationTemplate,
    PushDelivery,
    PushDevice,
)


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = (
        'recipient',
        'notification_type',
        'title',
        'is_read',
        'created_at',
    )
    list_filter = ('notification_type', 'is_read', 'created_at')
    search_fields = (
        'recipient__username',
        'recipient__first_name',
        'recipient__last_name',
        'title',
        'message',
        'deep_link',
    )
    readonly_fields = ('created_at', 'read_at')


@admin.register(PushDevice)
class PushDeviceAdmin(admin.ModelAdmin):
    list_display = (
        'user',
        'platform',
        'app_name',
        'is_active',
        'last_seen_at',
        'last_error',
    )
    list_filter = ('platform', 'app_name', 'is_active', 'created_at')
    search_fields = (
        'user__username',
        'user__first_name',
        'user__last_name',
        'device_id',
        'token',
    )
    readonly_fields = (
        'created_at',
        'updated_at',
        'last_seen_at',
        'deactivated_at',
    )


@admin.register(NotificationPreference)
class NotificationPreferenceAdmin(admin.ModelAdmin):
    list_display = (
        'user',
        'push_enabled',
        'quiet_hours_enabled',
        'language',
        'updated_at',
    )
    list_filter = (
        'push_enabled',
        'quiet_hours_enabled',
        'language',
    )
    search_fields = (
        'user__username',
        'user__first_name',
        'user__last_name',
    )
    readonly_fields = ('created_at', 'updated_at')


@admin.register(NotificationTemplate)
class NotificationTemplateAdmin(admin.ModelAdmin):
    list_display = (
        'key',
        'language',
        'notification_type',
        'is_active',
        'updated_at',
    )
    list_filter = ('language', 'notification_type', 'is_active')
    search_fields = ('key', 'title_template', 'message_template')
    readonly_fields = ('created_at', 'updated_at')


@admin.register(PushDelivery)
class PushDeliveryAdmin(admin.ModelAdmin):
    list_display = (
        'notification',
        'device',
        'status',
        'error_code',
        'attempted_at',
        'created_at',
    )
    list_filter = ('status', 'error_code', 'created_at')
    search_fields = (
        'notification__title',
        'notification__recipient__username',
        'device__user__username',
        'device__token',
    )
    readonly_fields = (
        'notification',
        'device',
        'status',
        'provider_message_id',
        'error_code',
        'error_message',
        'attempted_at',
        'created_at',
        'updated_at',
    )

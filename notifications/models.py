from django.conf import settings
from django.db import models


class Notification(models.Model):
    class Type(models.TextChoices):
        GENERAL = 'GENERAL', 'General'
        GRADE = 'GRADE', 'Grade'
        ATTENDANCE = 'ATTENDANCE', 'Attendance'
        ASSIGNMENT = 'ASSIGNMENT', 'Assignment'
        ANNOUNCEMENT = 'ANNOUNCEMENT', 'Announcement'
        INVOICE = 'INVOICE', 'Invoice'
        PAYMENT = 'PAYMENT', 'Payment'
        MESSAGE = 'MESSAGE', 'Message'

    recipient = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='notifications'
    )
    notification_type = models.CharField(
        max_length=20,
        choices=Type.choices,
        default=Type.GENERAL
    )
    title = models.CharField(max_length=200)
    message = models.TextField()

    related_object_type = models.CharField(max_length=50, blank=True)
    related_object_id = models.PositiveBigIntegerField(null=True, blank=True)
    deep_link = models.CharField(max_length=255, blank=True)

    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    read_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.recipient} - {self.title}"


class PushDevice(models.Model):
    class Platform(models.TextChoices):
        ANDROID = 'ANDROID', 'Android'
        IOS = 'IOS', 'iOS'
        WEB = 'WEB', 'Web'
        OTHER = 'OTHER', 'Other'

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='push_devices',
    )
    token = models.CharField(max_length=512, unique=True)
    platform = models.CharField(
        max_length=20,
        choices=Platform.choices,
        default=Platform.OTHER,
    )
    app_name = models.CharField(max_length=80, default='orbiet_flutter')
    device_id = models.CharField(max_length=120, blank=True)
    is_active = models.BooleanField(default=True)
    last_seen_at = models.DateTimeField(auto_now=True)
    last_error = models.CharField(max_length=255, blank=True)
    deactivated_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            models.Index(fields=['user', 'is_active']),
            models.Index(fields=['platform', 'is_active']),
        ]
        ordering = ['-last_seen_at']

    def __str__(self):
        return f"{self.user} - {self.platform}"


class NotificationPreference(models.Model):
    class Language(models.TextChoices):
        AR = 'AR', 'Arabic'
        EN = 'EN', 'English'

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='notification_preference',
    )
    push_enabled = models.BooleanField(default=True)
    in_app_enabled = models.BooleanField(default=True)
    general_enabled = models.BooleanField(default=True)
    grade_enabled = models.BooleanField(default=True)
    attendance_enabled = models.BooleanField(default=True)
    assignment_enabled = models.BooleanField(default=True)
    announcement_enabled = models.BooleanField(default=True)
    invoice_enabled = models.BooleanField(default=True)
    payment_enabled = models.BooleanField(default=True)
    message_enabled = models.BooleanField(default=True)
    quiet_hours_enabled = models.BooleanField(default=False)
    quiet_start = models.TimeField(null=True, blank=True)
    quiet_end = models.TimeField(null=True, blank=True)
    timezone = models.CharField(max_length=64, default='UTC')
    language = models.CharField(
        max_length=5,
        choices=Language.choices,
        default=Language.AR,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['user__username']

    def allows_type(self, notification_type):
        mapping = {
            Notification.Type.GENERAL: self.general_enabled,
            Notification.Type.GRADE: self.grade_enabled,
            Notification.Type.ATTENDANCE: self.attendance_enabled,
            Notification.Type.ASSIGNMENT: self.assignment_enabled,
            Notification.Type.ANNOUNCEMENT: self.announcement_enabled,
            Notification.Type.INVOICE: self.invoice_enabled,
            Notification.Type.PAYMENT: self.payment_enabled,
            Notification.Type.MESSAGE: self.message_enabled,
        }
        return mapping.get(notification_type, True)

    def is_quiet_time(self, current_time):
        if not self.quiet_hours_enabled or not self.quiet_start or not self.quiet_end:
            return False

        if self.quiet_start < self.quiet_end:
            return self.quiet_start <= current_time < self.quiet_end

        return current_time >= self.quiet_start or current_time < self.quiet_end

    def __str__(self):
        return f"{self.user} notification preferences"


class NotificationTemplate(models.Model):
    key = models.CharField(max_length=100)
    notification_type = models.CharField(
        max_length=20,
        choices=Notification.Type.choices,
        default=Notification.Type.GENERAL,
    )
    language = models.CharField(
        max_length=5,
        choices=NotificationPreference.Language.choices,
        default=NotificationPreference.Language.AR,
    )
    title_template = models.CharField(max_length=200)
    message_template = models.TextField()
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['key', 'language']
        constraints = [
            models.UniqueConstraint(
                fields=['key', 'language'],
                name='unique_notification_template_language',
            ),
        ]

    def __str__(self):
        return f"{self.key} ({self.language})"


class PushDelivery(models.Model):
    class Status(models.TextChoices):
        PENDING = 'PENDING', 'Pending'
        SKIPPED = 'SKIPPED', 'Skipped'
        SENT = 'SENT', 'Sent'
        FAILED = 'FAILED', 'Failed'
        INVALID_TOKEN = 'INVALID_TOKEN', 'Invalid token'

    notification = models.ForeignKey(
        Notification,
        on_delete=models.CASCADE,
        related_name='push_deliveries',
    )
    device = models.ForeignKey(
        PushDevice,
        on_delete=models.CASCADE,
        related_name='deliveries',
    )
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
    )
    provider_message_id = models.CharField(max_length=255, blank=True)
    error_code = models.CharField(max_length=100, blank=True)
    error_message = models.CharField(max_length=255, blank=True)
    attempted_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        constraints = [
            models.UniqueConstraint(
                fields=['notification', 'device'],
                name='unique_push_delivery_per_device',
            ),
        ]
        indexes = [
            models.Index(fields=['status', 'created_at']),
            models.Index(fields=['notification', 'status']),
        ]

    def __str__(self):
        return f"{self.notification_id} -> {self.device_id}: {self.status}"

import json
import logging
from urllib import error, request
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from django.conf import settings
from django.utils import timezone

from accounts.models import ParentStudentLink
from .models import (
    Notification,
    NotificationPreference,
    NotificationTemplate,
    PushDelivery,
    PushDevice,
)

logger = logging.getLogger(__name__)


def fcm_is_configured():
    return bool(settings.FCM_SERVER_KEY)


def get_notification_preference(user):
    preference, _ = NotificationPreference.objects.get_or_create(user=user)
    return preference


class SafeTemplateContext(dict):
    def __missing__(self, key):
        return '{' + key + '}'


def render_template_string(template, context):
    return template.format_map(SafeTemplateContext(context or {}))


def render_notification_template(template_key, recipient, fallback_title, fallback_message, context=None):
    if not template_key:
        return fallback_title, fallback_message

    preference = get_notification_preference(recipient)

    template = NotificationTemplate.objects.filter(
        key=template_key,
        language=preference.language,
        is_active=True,
    ).first()

    if not template and preference.language != NotificationPreference.Language.AR:
        template = NotificationTemplate.objects.filter(
            key=template_key,
            language=NotificationPreference.Language.AR,
            is_active=True,
        ).first()

    if not template:
        return fallback_title, fallback_message

    return (
        render_template_string(template.title_template, context),
        render_template_string(template.message_template, context),
    )


def create_notification_for_user(
    recipient,
    notification_type,
    title,
    message,
    related_object_type='',
    related_object_id=None,
    deep_link='',
    template_key='',
    context=None,
):
    rendered_title, rendered_message = render_notification_template(
        template_key=template_key,
        recipient=recipient,
        fallback_title=title,
        fallback_message=message,
        context=context,
    )

    return Notification.objects.create(
        recipient=recipient,
        notification_type=notification_type,
        title=rendered_title,
        message=rendered_message,
        related_object_type=related_object_type,
        related_object_id=related_object_id,
        deep_link=deep_link,
    )


def current_time_for_preference(preference):
    try:
        tz = ZoneInfo(preference.timezone)
    except ZoneInfoNotFoundError:
        tz = ZoneInfo(settings.TIME_ZONE)

    return timezone.now().astimezone(tz).time()


def build_deep_link(notification):
    if notification.deep_link:
        return notification.deep_link

    if not notification.related_object_type or not notification.related_object_id:
        return ''

    object_type = notification.related_object_type.lower()
    route_map = {
        'attendance': 'attendance',
        'grade': 'grades',
        'assignment': 'assignments',
        'assignmentsubmission': 'assignment-submissions',
        'announcement': 'announcements',
        'feeinvoice': 'invoices',
        'invoice': 'invoices',
        'payment': 'payments',
        'receipt': 'receipts',
        'chatroom': 'chat/rooms',
    }
    route = route_map.get(object_type)

    if not route:
        return ''

    return f"orbiet://{route}/{notification.related_object_id}"


def build_push_payload(notification):
    deep_link = build_deep_link(notification)
    data = {
        'notification_id': str(notification.id),
        'notification_type': notification.notification_type,
        'related_object_type': notification.related_object_type or '',
        'related_object_id': (
            str(notification.related_object_id)
            if notification.related_object_id is not None
            else ''
        ),
        'deep_link': deep_link,
    }

    return {
        'notification': {
            'title': notification.title,
            'body': notification.message,
        },
        'data': data,
    }


def record_delivery(notification, device, status, **kwargs):
    PushDelivery.objects.update_or_create(
        notification=notification,
        device=device,
        defaults={
            'status': status,
            'attempted_at': timezone.now(),
            **kwargs,
        },
    )


def record_skipped_deliveries(notification, devices, reason):
    for device in devices:
        record_delivery(
            notification,
            device,
            PushDelivery.Status.SKIPPED,
            error_code=reason,
            error_message=reason.replace('_', ' ').title(),
        )


def send_fcm_message(devices, notification):
    devices = list(devices)

    if not devices:
        return {
            'sent': 0,
            'failed': 0,
            'skipped': 0,
        }

    if not fcm_is_configured():
        record_skipped_deliveries(notification, devices, 'FCM_NOT_CONFIGURED')
        return {
            'sent': 0,
            'failed': 0,
            'skipped': len(devices),
        }

    payload = build_push_payload(notification)
    payload['registration_ids'] = [device.token for device in devices]
    payload['priority'] = 'high'

    body = json.dumps(payload).encode('utf-8')
    req = request.Request(
        settings.FCM_API_URL,
        data=body,
        headers={
            'Authorization': f'key={settings.FCM_SERVER_KEY}',
            'Content-Type': 'application/json',
        },
        method='POST',
    )

    try:
        with request.urlopen(req, timeout=settings.FCM_TIMEOUT_SECONDS) as response:
            response_data = json.loads(response.read().decode('utf-8'))
    except (error.URLError, TimeoutError, json.JSONDecodeError) as exc:
        logger.warning('FCM push request failed: %s', exc)
        for device in devices:
            record_delivery(
                notification,
                device,
                PushDelivery.Status.FAILED,
                error_code='FCM_REQUEST_FAILED',
                error_message=str(exc)[:255],
            )
        return {'sent': 0, 'failed': len(devices), 'error': str(exc)}

    results = response_data.get('results', [])

    for device, result in zip(devices, results):
        error_code = result.get('error')
        message_id = result.get('message_id', '')

        if error_code in {'NotRegistered', 'InvalidRegistration'}:
            PushDevice.objects.filter(id=device.id).update(
                is_active=False,
                last_error=error_code,
                deactivated_at=timezone.now(),
            )
            record_delivery(
                notification,
                device,
                PushDelivery.Status.INVALID_TOKEN,
                error_code=error_code,
                error_message=error_code,
            )
        elif error_code:
            record_delivery(
                notification,
                device,
                PushDelivery.Status.FAILED,
                error_code=error_code,
                error_message=error_code,
            )
        else:
            record_delivery(
                notification,
                device,
                PushDelivery.Status.SENT,
                provider_message_id=message_id,
            )

    return {
        'sent': response_data.get('success', 0),
        'failed': response_data.get('failure', 0),
        'canonical_ids': response_data.get('canonical_ids', 0),
    }


def send_push_for_notification(notification):
    preference = get_notification_preference(notification.recipient)
    devices = PushDevice.objects.filter(
        user=notification.recipient,
        is_active=True,
    )
    devices = list(devices)

    if not preference.push_enabled:
        record_skipped_deliveries(notification, devices, 'PUSH_DISABLED')
        return {'sent': 0, 'failed': 0, 'skipped': len(devices)}

    if not preference.allows_type(notification.notification_type):
        record_skipped_deliveries(notification, devices, 'TYPE_DISABLED')
        return {'sent': 0, 'failed': 0, 'skipped': len(devices)}

    if preference.is_quiet_time(current_time_for_preference(preference)):
        record_skipped_deliveries(notification, devices, 'QUIET_HOURS')
        return {'sent': 0, 'failed': 0, 'skipped': len(devices)}

    return send_fcm_message(devices, notification)


def queue_push_for_notification(notification):
    if not getattr(settings, 'PUSH_NOTIFICATIONS_USE_CELERY', False):
        return send_push_for_notification(notification)

    try:
        from .tasks import send_push_notification_task
    except ImportError as exc:
        logger.warning('Celery push queue unavailable, sending inline: %s', exc)
        return send_push_for_notification(notification)

    delay = getattr(send_push_notification_task, 'delay', None)
    if not delay:
        logger.warning('Celery task has no delay method, sending push inline')
        return send_push_for_notification(notification)

    try:
        delay(notification.id)
    except Exception as exc:
        logger.warning('Celery push enqueue failed, sending inline: %s', exc)
        return send_push_for_notification(notification)

    return {'queued': True}


def notify_student_and_parents(
    student,
    notification_type,
    title,
    message,
    related_object_type='',
    related_object_id=None,
    deep_link='',
    template_key='',
    context=None,
):
    recipients = [student.user]

    parent_user_ids = ParentStudentLink.objects.filter(
        student=student
    ).values_list(
        'parent__user_id',
        flat=True
    )

    recipients.extend(parent_user_ids)

    for recipient in recipients:
        recipient_id = recipient.id if hasattr(recipient, 'id') else recipient
        recipient = (
            recipient
            if hasattr(recipient, 'id')
            else student.user.__class__.objects.get(id=recipient_id)
        )
        create_notification_for_user(
            recipient=recipient,
            notification_type=notification_type,
            title=title,
            message=message,
            related_object_type=related_object_type,
            related_object_id=related_object_id,
            deep_link=deep_link,
            template_key=template_key,
            context=context,
        )


def notify_section_students(
    section,
    notification_type,
    title,
    message,
    related_object_type='',
    related_object_id=None,
    deep_link='',
    template_key='',
    context=None,
):
    students = section.students.select_related('user').all()

    for student in students:
        notify_student_and_parents(
            student=student,
            notification_type=notification_type,
            title=title,
            message=message,
            related_object_type=related_object_type,
            related_object_id=related_object_id,
            deep_link=deep_link,
            template_key=template_key,
            context=context,
        )

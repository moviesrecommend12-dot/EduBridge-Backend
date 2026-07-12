import logging

from django.core.exceptions import ObjectDoesNotExist

try:
    from celery import shared_task
except ImportError:
    shared_task = None

logger = logging.getLogger(__name__)


def send_push_notification(notification_id):
    from .models import Notification
    from .services import send_push_for_notification

    try:
        notification = Notification.objects.select_related('recipient').get(
            id=notification_id,
        )
    except ObjectDoesNotExist:
        logger.warning('Push notification task skipped missing notification %s', notification_id)
        return {'sent': 0, 'failed': 0, 'skipped': 0, 'missing': True}

    return send_push_for_notification(notification)


def run_notification_reminders():
    from .reminders import NotificationReminderRunner

    runner = NotificationReminderRunner()
    return runner.run(dry_run=False)


if shared_task:
    send_push_notification_task = shared_task(
        name='notifications.send_push_notification',
        bind=False,
        max_retries=3,
        default_retry_delay=30,
    )(send_push_notification)
    run_notification_reminders_task = shared_task(
        name='notifications.run_notification_reminders',
        bind=False,
    )(run_notification_reminders)
else:
    send_push_notification_task = send_push_notification
    run_notification_reminders_task = run_notification_reminders

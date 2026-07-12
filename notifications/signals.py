from django.db import transaction
from django.db.models.signals import post_save
from django.dispatch import receiver

from .models import Notification
from .services import send_push_for_notification


@receiver(post_save, sender=Notification)
def send_push_after_notification_create(sender, instance, created, **kwargs):
    if not created:
        return

    transaction.on_commit(lambda: send_push_for_notification(instance))

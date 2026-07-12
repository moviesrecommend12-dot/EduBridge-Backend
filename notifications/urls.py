from django.urls import path
from .views import (
    notification_detail,
    notification_preferences,
    push_device_detail,
    push_device_list_create,
    push_delivery_list,
    notification_list,
    unread_count,
    mark_notification_read,
    mark_all_read,
)

urlpatterns = [
    path('', notification_list, name='notification-list'),
    path('<int:notification_id>/', notification_detail, name='notification-detail'),
    path('preferences/', notification_preferences, name='notification-preferences'),
    path('deliveries/', push_delivery_list, name='push-delivery-list'),
    path('devices/', push_device_list_create, name='push-device-list-create'),
    path('devices/<int:device_id>/', push_device_detail, name='push-device-detail'),
    path('unread-count/', unread_count, name='notification-unread-count'),
    path('<int:notification_id>/read/', mark_notification_read, name='notification-read'),
    path('read-all/', mark_all_read, name='notification-read-all'),
]

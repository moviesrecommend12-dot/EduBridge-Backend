from django.utils import timezone
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from .models import Notification, NotificationPreference, PushDelivery, PushDevice
from .serializers import (
    NotificationPreferenceSerializer,
    NotificationSerializer,
    PushDeliverySerializer,
    PushDeviceSerializer,
    PushDeviceUpdateSerializer,
)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def notification_list(request):
    notifications = Notification.objects.filter(
        recipient=request.user
    )

    serializer = NotificationSerializer(notifications, many=True)
    return Response(serializer.data)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def notification_detail(request, notification_id):
    try:
        notification = Notification.objects.get(
            id=notification_id,
            recipient=request.user,
        )
    except Notification.DoesNotExist:
        return Response(
            {'detail': 'Notification not found.'},
            status=status.HTTP_404_NOT_FOUND,
        )

    return Response(NotificationSerializer(notification).data)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def unread_count(request):
    count = Notification.objects.filter(
        recipient=request.user,
        is_read=False
    ).count()

    return Response({'unread_count': count})


@api_view(['PATCH'])
@permission_classes([IsAuthenticated])
def mark_notification_read(request, notification_id):
    try:
        notification = Notification.objects.get(
            id=notification_id,
            recipient=request.user
        )
    except Notification.DoesNotExist:
        return Response(
            {'detail': 'Notification not found.'},
            status=status.HTTP_404_NOT_FOUND
        )

    if not notification.is_read:
        notification.is_read = True
        notification.read_at = timezone.now()
        notification.save(update_fields=['is_read', 'read_at'])

    return Response(NotificationSerializer(notification).data)


@api_view(['PATCH'])
@permission_classes([IsAuthenticated])
def mark_all_read(request):
    Notification.objects.filter(
        recipient=request.user,
        is_read=False
    ).update(
        is_read=True,
        read_at=timezone.now()
    )

    return Response({'detail': 'All notifications marked as read.'})


@api_view(['GET', 'PATCH'])
@permission_classes([IsAuthenticated])
def notification_preferences(request):
    preference, _ = NotificationPreference.objects.get_or_create(
        user=request.user,
    )

    if request.method == 'GET':
        return Response(NotificationPreferenceSerializer(preference).data)

    serializer = NotificationPreferenceSerializer(
        preference,
        data=request.data,
        partial=True,
    )

    if serializer.is_valid():
        serializer.save()
        return Response(serializer.data)

    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def push_delivery_list(request):
    deliveries = PushDelivery.objects.select_related(
        'notification',
        'device',
    ).filter(
        notification__recipient=request.user,
    )[:100]

    serializer = PushDeliverySerializer(deliveries, many=True)
    return Response(serializer.data)


@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated])
def push_device_list_create(request):
    if request.method == 'GET':
        devices = PushDevice.objects.filter(user=request.user)
        serializer = PushDeviceSerializer(devices, many=True)
        return Response(serializer.data)

    serializer = PushDeviceSerializer(
        data=request.data,
        context={'request': request},
    )

    if serializer.is_valid():
        device = serializer.save()
        return Response(
            PushDeviceSerializer(device).data,
            status=status.HTTP_201_CREATED,
        )

    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(['PATCH', 'DELETE'])
@permission_classes([IsAuthenticated])
def push_device_detail(request, device_id):
    try:
        device = PushDevice.objects.get(id=device_id, user=request.user)
    except PushDevice.DoesNotExist:
        return Response(
            {'detail': 'Push device not found.'},
            status=status.HTTP_404_NOT_FOUND,
        )

    if request.method == 'DELETE':
        device.is_active = False
        device.save(update_fields=['is_active', 'updated_at'])
        return Response(status=status.HTTP_204_NO_CONTENT)

    serializer = PushDeviceUpdateSerializer(
        device,
        data=request.data,
        partial=True,
    )

    if serializer.is_valid():
        serializer.save()
        return Response(PushDeviceSerializer(device).data)

    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

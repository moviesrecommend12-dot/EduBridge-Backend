from django.utils import timezone
from rest_framework import serializers

from .models import (
    Notification,
    NotificationPreference,
    PushDelivery,
    PushDevice,
)
from .services import build_deep_link


class NotificationSerializer(serializers.ModelSerializer):
    deep_link = serializers.SerializerMethodField()

    class Meta:
        model = Notification
        fields = [
            'id',
            'notification_type',
            'title',
            'message',
            'related_object_type',
            'related_object_id',
            'deep_link',
            'is_read',
            'created_at',
            'read_at',
        ]

    def get_deep_link(self, obj):
        return build_deep_link(obj)


class PushDeviceSerializer(serializers.ModelSerializer):
    token = serializers.CharField(write_only=True, trim_whitespace=True)

    class Meta:
        model = PushDevice
        fields = [
            'id',
            'token',
            'platform',
            'app_name',
            'device_id',
            'is_active',
            'last_seen_at',
            'created_at',
            'updated_at',
        ]
        read_only_fields = [
            'id',
            'is_active',
            'last_seen_at',
            'created_at',
            'updated_at',
        ]

    def validate_token(self, value):
        if len(value) < 20:
            raise serializers.ValidationError('Device token is too short.')
        if len(value) > 512:
            raise serializers.ValidationError('Device token is too long.')
        return value

    def create(self, validated_data):
        request = self.context['request']
        token = validated_data.pop('token')

        device, _ = PushDevice.objects.update_or_create(
            token=token,
            defaults={
                **validated_data,
                'user': request.user,
                'is_active': True,
                'last_error': '',
                'deactivated_at': None,
            },
        )
        return device


class PushDeviceUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = PushDevice
        fields = [
            'platform',
            'app_name',
            'device_id',
            'is_active',
        ]

    def update(self, instance, validated_data):
        if validated_data.get('is_active') is True:
            validated_data['deactivated_at'] = None
            validated_data['last_error'] = ''
        elif validated_data.get('is_active') is False:
            validated_data['deactivated_at'] = timezone.now()

        return super().update(instance, validated_data)


class NotificationPreferenceSerializer(serializers.ModelSerializer):
    class Meta:
        model = NotificationPreference
        fields = [
            'push_enabled',
            'in_app_enabled',
            'general_enabled',
            'grade_enabled',
            'attendance_enabled',
            'assignment_enabled',
            'announcement_enabled',
            'invoice_enabled',
            'payment_enabled',
            'message_enabled',
            'quiet_hours_enabled',
            'quiet_start',
            'quiet_end',
            'timezone',
            'language',
            'created_at',
            'updated_at',
        ]
        read_only_fields = ['created_at', 'updated_at']

    def validate(self, attrs):
        quiet_enabled = attrs.get(
            'quiet_hours_enabled',
            getattr(self.instance, 'quiet_hours_enabled', False),
        )
        quiet_start = attrs.get(
            'quiet_start',
            getattr(self.instance, 'quiet_start', None),
        )
        quiet_end = attrs.get(
            'quiet_end',
            getattr(self.instance, 'quiet_end', None),
        )

        if quiet_enabled and (not quiet_start or not quiet_end):
            raise serializers.ValidationError(
                'quiet_start and quiet_end are required when quiet hours are enabled.'
            )

        return attrs


class PushDeliverySerializer(serializers.ModelSerializer):
    notification_title = serializers.CharField(
        source='notification.title',
        read_only=True,
    )
    notification_type = serializers.CharField(
        source='notification.notification_type',
        read_only=True,
    )
    notification_deep_link = serializers.SerializerMethodField()
    device_platform = serializers.CharField(
        source='device.platform',
        read_only=True,
    )
    device_app_name = serializers.CharField(
        source='device.app_name',
        read_only=True,
    )
    device_identifier = serializers.CharField(
        source='device.device_id',
        read_only=True,
    )
    device_is_active = serializers.BooleanField(
        source='device.is_active',
        read_only=True,
    )

    class Meta:
        model = PushDelivery
        fields = [
            'id',
            'notification',
            'notification_title',
            'notification_type',
            'notification_deep_link',
            'device',
            'device_platform',
            'device_app_name',
            'device_identifier',
            'device_is_active',
            'status',
            'provider_message_id',
            'error_code',
            'error_message',
            'attempted_at',
            'created_at',
            'updated_at',
        ]

    def get_notification_deep_link(self, obj):
        return build_deep_link(obj.notification)

from rest_framework import serializers

from .models import ChatRoom, Message


class MessageSerializer(serializers.ModelSerializer):
    sender = serializers.SerializerMethodField()

    class Meta:
        model = Message
        fields = [
            'id',
            'room',
            'sender',
            'content',
            'is_read',
            'created_at',
            'read_at',
        ]
        read_only_fields = [
            'id',
            'room',
            'sender',
            'is_read',
            'created_at',
            'read_at',
        ]

    def get_sender(self, obj):
        return {
            'id': obj.sender.id,
            'username': obj.sender.username,
            'full_name': (
                obj.sender.get_full_name()
                or obj.sender.username
            ),
            'role': obj.sender.role,
        }


class ChatRoomSerializer(serializers.ModelSerializer):
    parent = serializers.SerializerMethodField()
    teacher = serializers.SerializerMethodField()
    student = serializers.SerializerMethodField()
    last_message = serializers.SerializerMethodField()
    unread_count = serializers.SerializerMethodField()

    class Meta:
        model = ChatRoom
        fields = [
            'id',
            'parent',
            'teacher',
            'student',
            'is_active',
            'last_message',
            'unread_count',
            'created_at',
            'updated_at',
        ]

    def get_parent(self, obj):
        user = obj.parent.user
        return {
            'id': obj.parent.id,
            'user_id': user.id,
            'name': user.get_full_name() or user.username,
        }

    def get_teacher(self, obj):
        user = obj.teacher.user
        return {
            'id': obj.teacher.id,
            'user_id': user.id,
            'name': user.get_full_name() or user.username,
            'employee_code': obj.teacher.employee_code,
        }

    def get_student(self, obj):
        user = obj.student.user
        return {
            'id': obj.student.id,
            'user_id': user.id,
            'name': user.get_full_name() or user.username,
            'student_code': obj.student.student_code,
        }

    def get_last_message(self, obj):
        message = obj.messages.select_related('sender').last()

        if not message:
            return None

        return MessageSerializer(message).data

    def get_unread_count(self, obj):
        request = self.context.get('request')

        if not request or not request.user.is_authenticated:
            return 0

        return obj.messages.filter(
            is_read=False
        ).exclude(
            sender=request.user
        ).count()
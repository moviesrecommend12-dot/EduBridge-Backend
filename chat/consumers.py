from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncJsonWebsocketConsumer
from django.utils import timezone

from notifications.models import Notification
from notifications.services import create_notification_for_user
from .models import ChatRoom, Message


class ChatConsumer(AsyncJsonWebsocketConsumer):
    async def connect(self):
        self.room_id = self.scope['url_route']['kwargs']['room_id']
        self.group_name = f'chat_room_{self.room_id}'
        self.user = self.scope.get('user')

        if not self.user or not self.user.is_authenticated:
            await self.close(code=4401)
            return

        allowed = await self.can_access_room()

        if not allowed:
            await self.close(code=4403)
            return

        await self.channel_layer.group_add(
            self.group_name,
            self.channel_name,
        )

        await self.accept()

        await self.send_json({
            'type': 'connection_established',
            'room_id': int(self.room_id),
            'user_id': self.user.id,
            'message': 'WebSocket connected successfully.',
        })

    async def disconnect(self, close_code):
        if hasattr(self, 'group_name'):
            await self.channel_layer.group_discard(
                self.group_name,
                self.channel_name,
            )

    async def receive_json(self, content, **kwargs):
        message_type = content.get('type', 'chat_message')

        if message_type == 'chat_message':
            message_content = str(
                content.get('content', '')
            ).strip()

            if not message_content:
                await self.send_json({
                    'type': 'error',
                    'message': 'Message content is required.',
                })
                return

            message = await self.create_message(message_content)

            await self.channel_layer.group_send(
                self.group_name,
                {
                    'type': 'broadcast_message',
                    'message': message,
                }
            )

        elif message_type == 'mark_read':
            updated_count = await self.mark_messages_read()

            await self.send_json({
                'type': 'messages_read',
                'updated_count': updated_count,
            })

        else:
            await self.send_json({
                'type': 'error',
                'message': 'Unsupported message type.',
            })

    async def broadcast_message(self, event):
        await self.send_json({
            'type': 'chat_message',
            'message': event['message'],
        })

    @database_sync_to_async
    def can_access_room(self):
        try:
            room = ChatRoom.objects.select_related(
                'parent__user',
                'teacher__user',
            ).get(
                id=self.room_id,
                is_active=True,
            )
        except ChatRoom.DoesNotExist:
            return False

        if self.user.role == 'PARENT':
            return room.parent.user_id == self.user.id

        if self.user.role == 'TEACHER':
            return room.teacher.user_id == self.user.id

        return False

    @database_sync_to_async
    def create_message(self, content):
        room = ChatRoom.objects.select_related(
            'parent__user',
            'teacher__user',
        ).get(
            id=self.room_id,
            is_active=True,
        )

        message = Message.objects.create(
            room=room,
            sender=self.user,
            content=content,
        )

        if self.user.role == 'PARENT':
            recipient = room.teacher.user
        else:
            recipient = room.parent.user

        create_notification_for_user(
            recipient=recipient,
            notification_type=Notification.Type.MESSAGE,
            title='New chat message',
            message=(
                f'New message from '
                f'{self.user.get_full_name() or self.user.username}'
            ),
            related_object_type='ChatRoom',
            related_object_id=room.id,
            template_key='chat_message',
            context={
                'sender_name': self.user.get_full_name() or self.user.username,
            },
        )

        room.updated_at = timezone.now()
        room.save(update_fields=['updated_at'])

        return {
            'id': message.id,
            'room_id': room.id,
            'content': message.content,
            'is_read': message.is_read,
            'created_at': message.created_at.isoformat(),
            'sender': {
                'id': self.user.id,
                'username': self.user.username,
                'full_name': (
                    self.user.get_full_name()
                    or self.user.username
                ),
                'role': self.user.role,
            },
        }

    @database_sync_to_async
    def mark_messages_read(self):
        return Message.objects.filter(
            room_id=self.room_id,
            is_read=False,
        ).exclude(
            sender=self.user,
        ).update(
            is_read=True,
            read_at=timezone.now(),
        )

from django.urls import path

from .views import (
    create_room,
    mark_room_read,
    room_list,
    room_messages,
    send_message,
)

urlpatterns = [
    path('rooms/', room_list, name='chat-room-list'),
    path('rooms/create/', create_room, name='chat-room-create'),
    path(
        'rooms/<int:room_id>/messages/',
        room_messages,
        name='chat-room-messages',
    ),
    path(
        'rooms/<int:room_id>/messages/send/',
        send_message,
        name='chat-send-message',
    ),
    path(
        'rooms/<int:room_id>/read/',
        mark_room_read,
        name='chat-mark-room-read',
    ),
]
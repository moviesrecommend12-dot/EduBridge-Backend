from django.db.models import Q
from django.utils import timezone
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from notifications.models import Notification
from notifications.services import create_notification_for_user
from academics.models import TeachingAssignment
from accounts.models import ParentProfile, ParentStudentLink, TeacherProfile

from .models import ChatRoom, Message
from .serializers import ChatRoomSerializer, MessageSerializer


def room_queryset_for_user(user):
    queryset = ChatRoom.objects.select_related(
        'parent',
        'parent__user',
        'teacher',
        'teacher__user',
        'student',
        'student__user',
    )

    if user.role == 'PARENT':
        return queryset.filter(parent__user=user)

    if user.role == 'TEACHER':
        return queryset.filter(teacher__user=user)

    return queryset.none()


def user_can_access_room(user, room):
    if user.role == 'PARENT':
        return room.parent.user_id == user.id

    if user.role == 'TEACHER':
        return room.teacher.user_id == user.id

    return False


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def room_list(request):
    if request.user.role not in ['PARENT', 'TEACHER']:
        return Response(
            {'detail': 'Only parents and teachers can access chat.'},
            status=status.HTTP_403_FORBIDDEN
        )

    rooms = room_queryset_for_user(request.user)
    serializer = ChatRoomSerializer(
        rooms,
        many=True,
        context={'request': request},
    )
    return Response(serializer.data)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def create_room(request):
    if request.user.role != 'PARENT':
        return Response(
            {'detail': 'Only parents can start a chat room.'},
            status=status.HTTP_403_FORBIDDEN
        )

    student_id = request.data.get('student_id')
    teacher_id = request.data.get('teacher_id')

    if not student_id or not teacher_id:
        return Response(
            {
                'detail': (
                    'student_id and teacher_id are required.'
                )
            },
            status=status.HTTP_400_BAD_REQUEST
        )

    try:
        parent_profile = request.user.parent_profile
    except ParentProfile.DoesNotExist:
        return Response(
            {'detail': 'Parent profile not found.'},
            status=status.HTTP_404_NOT_FOUND
        )

    try:
        parent_link = ParentStudentLink.objects.select_related(
            'student'
        ).get(
            parent=parent_profile,
            student_id=student_id,
        )
    except ParentStudentLink.DoesNotExist:
        return Response(
            {
                'detail': (
                    'This student is not linked to your account.'
                )
            },
            status=status.HTTP_403_FORBIDDEN
        )

    try:
        teacher = TeacherProfile.objects.select_related(
            'user'
        ).get(id=teacher_id)
    except TeacherProfile.DoesNotExist:
        return Response(
            {'detail': 'Teacher not found.'},
            status=status.HTTP_404_NOT_FOUND
        )

    student = parent_link.student

    teacher_is_allowed = TeachingAssignment.objects.filter(
        teacher=teacher,
        section=student.section,
        is_active=True,
    ).exists()

    if not teacher_is_allowed:
        return Response(
            {
                'detail': (
                    'This teacher does not teach the selected student.'
                )
            },
            status=status.HTTP_403_FORBIDDEN
        )

    room, created = ChatRoom.objects.get_or_create(
        parent=parent_profile,
        teacher=teacher,
        student=student,
        defaults={'is_active': True},
    )

    if not room.is_active:
        room.is_active = True
        room.save(update_fields=['is_active', 'updated_at'])

    serializer = ChatRoomSerializer(
        room,
        context={'request': request},
    )

    return Response(
        serializer.data,
        status=(
            status.HTTP_201_CREATED
            if created
            else status.HTTP_200_OK
        )
    )


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def room_messages(request, room_id):
    try:
        room = room_queryset_for_user(
            request.user
        ).get(id=room_id, is_active=True)
    except ChatRoom.DoesNotExist:
        return Response(
            {'detail': 'Chat room not found.'},
            status=status.HTTP_404_NOT_FOUND
        )

    messages = room.messages.select_related('sender').all()

    serializer = MessageSerializer(messages, many=True)
    return Response(serializer.data)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def send_message(request, room_id):
    try:
        room = ChatRoom.objects.select_related(
            'parent__user',
            'teacher__user',
            'student__user',
        ).get(id=room_id, is_active=True)
    except ChatRoom.DoesNotExist:
        return Response(
            {'detail': 'Chat room not found.'},
            status=status.HTTP_404_NOT_FOUND
        )

    if not user_can_access_room(request.user, room):
        return Response(
            {
                'detail': (
                    'You are not allowed to access this chat room.'
                )
            },
            status=status.HTTP_403_FORBIDDEN
        )

    content = str(request.data.get('content', '')).strip()

    if not content:
        return Response(
            {'content': ['This field is required.']},
            status=status.HTTP_400_BAD_REQUEST
        )

    message = Message.objects.create(
        room=room,
        sender=request.user,
        content=content,
    )
    if request.user.role == 'PARENT':
        recipient = room.teacher.user
    else:
        recipient = room.parent.user

    create_notification_for_user(
        recipient=recipient,
        notification_type=Notification.Type.MESSAGE,
        title='New chat message',
        message=(
            f'New message from '
            f'{request.user.get_full_name() or request.user.username}'
        ),
        related_object_type='ChatRoom',
        related_object_id=room.id,
        template_key='chat_message',
        context={
            'sender_name': request.user.get_full_name() or request.user.username,
        },
    )

    room.save(update_fields=['updated_at'])

    serializer = MessageSerializer(message)
    return Response(
        serializer.data,
        status=status.HTTP_201_CREATED
    )


@api_view(['PATCH'])
@permission_classes([IsAuthenticated])
def mark_room_read(request, room_id):
    try:
        room = ChatRoom.objects.select_related(
            'parent__user',
            'teacher__user',
        ).get(id=room_id, is_active=True)
    except ChatRoom.DoesNotExist:
        return Response(
            {'detail': 'Chat room not found.'},
            status=status.HTTP_404_NOT_FOUND
        )

    if not user_can_access_room(request.user, room):
        return Response(
            {'detail': 'You cannot access this chat room.'},
            status=status.HTTP_403_FORBIDDEN
        )

    updated = Message.objects.filter(
        room=room,
        is_read=False,
    ).exclude(
        sender=request.user
    ).update(
        is_read=True,
        read_at=timezone.now(),
    )

    return Response({
        'detail': 'Messages marked as read.',
        'updated_count': updated,
    })

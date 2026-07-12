from django.conf import settings
from django.db import models


class ChatRoom(models.Model):
    parent = models.ForeignKey(
        'accounts.ParentProfile',
        on_delete=models.CASCADE,
        related_name='chat_rooms',
    )
    teacher = models.ForeignKey(
        'accounts.TeacherProfile',
        on_delete=models.CASCADE,
        related_name='chat_rooms',
    )
    student = models.ForeignKey(
        'accounts.StudentProfile',
        on_delete=models.CASCADE,
        related_name='chat_rooms',
    )

    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['parent', 'teacher', 'student'],
                name='unique_parent_teacher_student_chat'
            )
        ]
        ordering = ['-updated_at']

    def __str__(self):
        return (
            f'{self.parent} ↔ {self.teacher} '
            f'about {self.student}'
        )


class Message(models.Model):
    room = models.ForeignKey(
        ChatRoom,
        on_delete=models.CASCADE,
        related_name='messages',
    )
    sender = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='sent_chat_messages',
    )

    content = models.TextField()
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    read_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['created_at']

    def __str__(self):
        return f'{self.sender} - {self.content[:40]}'
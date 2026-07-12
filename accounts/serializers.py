from django.db import transaction
from rest_framework import serializers
from rest_framework_simplejwt.tokens import RefreshToken

from .models import (
    User,
    StudentProfile,
    ParentProfile,
    ParentStudentLink,
    ParentLinkingCode,
)

class ParentRegisterSerializer(serializers.Serializer):
    username = serializers.CharField(max_length=150)
    password = serializers.CharField(write_only=True, min_length=8)
    first_name = serializers.CharField(max_length=150)
    last_name = serializers.CharField(max_length=150)
    email = serializers.EmailField(required=False, allow_blank=True)
    phone = serializers.CharField(max_length=20, required=False, allow_blank=True)
    national_id = serializers.CharField(max_length=50, required=False, allow_blank=True)
    address = serializers.CharField(required=False, allow_blank=True)
    linking_code = serializers.CharField(max_length=12)
    relationship = serializers.CharField(max_length=50, required=False, allow_blank=True)

    def validate_username(self, value):
        if User.objects.filter(username__iexact=value).exists():
            raise serializers.ValidationError("Username already exists.")
        return value

    def validate_linking_code(self, value):
        code = value.strip().upper()

        try:
            linking_code = ParentLinkingCode.objects.select_related('student').get(code=code)
        except ParentLinkingCode.DoesNotExist:
            raise serializers.ValidationError("Invalid linking code.")

        if linking_code.is_used:
            raise serializers.ValidationError("This linking code has already been used.")

        if linking_code.is_expired:
            raise serializers.ValidationError("This linking code has expired.")

        return code

    @transaction.atomic
    def create(self, validated_data):
        code_value = validated_data.pop('linking_code').strip().upper()
        relationship = validated_data.pop('relationship', '')

        national_id = validated_data.pop('national_id', '')
        address = validated_data.pop('address', '')

        password = validated_data.pop('password')

        linking_code = ParentLinkingCode.objects.select_related('student').get(code=code_value)
        student = linking_code.student

        user = User.objects.create(
            username=validated_data.get('username'),
            first_name=validated_data.get('first_name'),
            last_name=validated_data.get('last_name'),
            email=validated_data.get('email', ''),
            phone=validated_data.get('phone', ''),
            role=User.Role.PARENT,
        )
        user.set_password(password)
        user.save()

        parent_profile = ParentProfile.objects.create(
            user=user,
            national_id=national_id,
            address=address,
        )

        ParentStudentLink.objects.create(
            parent=parent_profile,
            student=student,
            relationship=relationship,
        )

        linking_code.is_used = True
        linking_code.save()

        refresh = RefreshToken.for_user(user)

        return {
            'refresh': str(refresh),
            'access': str(refresh.access_token),
            'user': {
                'id': user.id,
                'username': user.username,
                'email': user.email,
                'first_name': user.first_name,
                'last_name': user.last_name,
                'role': user.role,
                'phone': user.phone,
            },
            'linked_student': {
                'id': student.id,
                'student_code': student.student_code,
                'name': student.user.get_full_name() or student.user.username,
            }
        }

class StudentProfileSerializer(serializers.ModelSerializer):
    user = serializers.SerializerMethodField()
    classroom = serializers.SerializerMethodField()
    section = serializers.SerializerMethodField()

    class Meta:
        model = StudentProfile
        fields = [
            'id',
            'user',
            'student_code',
            'date_of_birth',
            'address',
            'classroom',
            'section',
        ]

    def get_user(self, obj):
        return {
            'id': obj.user.id,
            'username': obj.user.username,
            'email': obj.user.email,
            'first_name': obj.user.first_name,
            'last_name': obj.user.last_name,
            'full_name': obj.user.get_full_name(),
            'phone': obj.user.phone,
            'role': obj.user.role,
        }

    def get_classroom(self, obj):
        if not obj.classroom:
            return None

        return {
            'id': obj.classroom.id,
            'name': obj.classroom.name,
            'grade_level': obj.classroom.grade_level,
        }

    def get_section(self, obj):
        if not obj.section:
            return None

        return {
            'id': obj.section.id,
            'name': obj.section.name,
        }
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework_simplejwt.views import TokenObtainPairView
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from .models import ParentProfile, ParentStudentLink, StudentProfile
from .serializers import ParentRegisterSerializer, StudentProfileSerializer

class CustomTokenObtainPairSerializer(TokenObtainPairSerializer):
    def validate(self, attrs):
        data = super().validate(attrs)

        user = self.user
        data['user'] = {
            'id': user.id,
            'username': user.username,
            'email': user.email,
            'first_name': user.first_name,
            'last_name': user.last_name,
            'role': user.role,
            'phone': user.phone,
        }

        return data


class CustomTokenObtainPairView(TokenObtainPairView):
    serializer_class = CustomTokenObtainPairSerializer


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def me(request):
    user = request.user

    return Response({
        'id': user.id,
        'username': user.username,
        'email': user.email,
        'first_name': user.first_name,
        'last_name': user.last_name,
        'role': user.role,
        'phone': user.phone,
    })


@api_view(['POST'])
@permission_classes([AllowAny])
def parent_register(request):
    serializer = ParentRegisterSerializer(data=request.data)

    if serializer.is_valid():
        data = serializer.save()
        return Response(data, status=status.HTTP_201_CREATED)

    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def student_profile(request):
    user = request.user

    if user.role != 'STUDENT':
        return Response(
            {'detail': 'Only students can access this endpoint.'},
            status=status.HTTP_403_FORBIDDEN
        )

    try:
        profile = user.student_profile
    except StudentProfile.DoesNotExist:
        return Response(
            {'detail': 'Student profile not found.'},
            status=status.HTTP_404_NOT_FOUND
        )

    serializer = StudentProfileSerializer(profile)
    return Response(serializer.data)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def parent_children(request):
    user = request.user

    if user.role != 'PARENT':
        return Response(
            {'detail': 'Only parents can access this endpoint.'},
            status=status.HTTP_403_FORBIDDEN
        )

    try:
        parent_profile = user.parent_profile
    except ParentProfile.DoesNotExist:
        return Response(
            {'detail': 'Parent profile not found.'},
            status=status.HTTP_404_NOT_FOUND
        )

    links = ParentStudentLink.objects.select_related(
        'student',
        'student__user',
        'student__classroom',
        'student__section',
    ).filter(parent=parent_profile)

    students = [link.student for link in links]
    serializer = StudentProfileSerializer(students, many=True)

    return Response(serializer.data)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def parent_child_detail(request, student_id):
    user = request.user

    if user.role != 'PARENT':
        return Response(
            {'detail': 'Only parents can access this endpoint.'},
            status=status.HTTP_403_FORBIDDEN
        )

    try:
        parent_profile = user.parent_profile
    except ParentProfile.DoesNotExist:
        return Response(
            {'detail': 'Parent profile not found.'},
            status=status.HTTP_404_NOT_FOUND
        )

    try:
        link = ParentStudentLink.objects.select_related(
            'student',
            'student__user',
            'student__classroom',
            'student__section',
        ).get(parent=parent_profile, student_id=student_id)
    except ParentStudentLink.DoesNotExist:
        return Response(
            {'detail': 'You are not allowed to access this student.'},
            status=status.HTTP_403_FORBIDDEN
        )

    serializer = StudentProfileSerializer(link.student)
    return Response(serializer.data)

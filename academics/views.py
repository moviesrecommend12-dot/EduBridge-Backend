from rest_framework import status
from rest_framework.decorators import api_view, parser_classes, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.response import Response
from django.utils import timezone

from accounts.models import ParentProfile, ParentStudentLink, StudentProfile, TeacherProfile
from .models import (
    AcademicYear,
    TeachingAssignment,
    Schedule,
    Attendance,
    Grade,
    Assignment,
    AssignmentSubmission,
    StudentYearResult,
    TeacherUploadedFile,
    Announcement,
)
from .serializers import (
    AcademicYearSerializer,
    TeachingAssignmentSerializer,
    TeacherStudentSerializer,
    ScheduleSerializer,
    AttendanceSerializer,
    GradeSerializer,
    AssignmentSerializer,
    AssignmentSubmissionCreateSerializer,
    AssignmentSubmissionReviewSerializer,
    AssignmentSubmissionSerializer,
    PromotionRunSerializer,
    StudentYearResultSerializer,
    TeacherUploadedFileSerializer,
    AnnouncementSerializer,
    TeacherAttendanceCreateSerializer,
    TeacherGradeCreateSerializer,
    TeacherAssignmentCreateSerializer,
    TeacherAnnouncementCreateSerializer,
    TeacherUploadedFileCreateSerializer,
)
from notifications.models import Notification
from notifications.services import (
    create_notification_for_user,
    notify_student_and_parents,
    notify_section_students,
)
from .services import calculate_promotion_results


def get_teacher_profile_or_error(user):
    if user.role != 'TEACHER':
        return None, Response(
            {'detail': 'Only teachers can access this endpoint.'},
            status=status.HTTP_403_FORBIDDEN
        )

    try:
        return user.teacher_profile, None
    except TeacherProfile.DoesNotExist:
        return None, Response(
            {'detail': 'Teacher profile not found.'},
            status=status.HTTP_404_NOT_FOUND
        )
    
def teacher_has_assignment(teacher_profile, section_id, subject_id):
    return TeachingAssignment.objects.filter(
        teacher=teacher_profile,
        section_id=section_id,
        subject_id=subject_id,
        is_active=True,
    ).exists()


def teacher_can_access_assignment(teacher_profile, assignment):
    return teacher_has_assignment(
        teacher_profile,
        assignment.section_id,
        assignment.subject_id,
    )


def submission_queryset():
    return AssignmentSubmission.objects.select_related(
        'assignment',
        'assignment__teacher',
        'assignment__teacher__user',
        'assignment__subject',
        'assignment__classroom',
        'assignment__section',
        'student',
        'student__user',
    )


def is_admin_user(user):
    return user.is_authenticated and (user.is_superuser or user.role == 'ADMIN')


def get_active_academic_year():
    return AcademicYear.objects.filter(is_active=True).order_by('-start_date').first()

def get_student_profile_or_error(user):
    if user.role != 'STUDENT':
        return None, Response(
            {'detail': 'Only students can access this endpoint.'},
            status=status.HTTP_403_FORBIDDEN
        )

    try:
        return user.student_profile, None
    except StudentProfile.DoesNotExist:
        return None, Response(
            {'detail': 'Student profile not found.'},
            status=status.HTTP_404_NOT_FOUND
        )


def get_parent_child_or_error(user, student_id):
    if user.role != 'PARENT':
        return None, Response(
            {'detail': 'Only parents can access this endpoint.'},
            status=status.HTTP_403_FORBIDDEN
        )

    try:
        parent_profile = user.parent_profile
    except ParentProfile.DoesNotExist:
        return None, Response(
            {'detail': 'Parent profile not found.'},
            status=status.HTTP_404_NOT_FOUND
        )

    try:
        link = ParentStudentLink.objects.select_related('student').get(
            parent=parent_profile,
            student_id=student_id
        )
        return link.student, None
    except ParentStudentLink.DoesNotExist:
        return None, Response(
            {'detail': 'You are not allowed to access this student.'},
            status=status.HTTP_403_FORBIDDEN
        )


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def teacher_assignments(request):
    teacher_profile, error = get_teacher_profile_or_error(request.user)
    if error:
        return error

    assignments = TeachingAssignment.objects.select_related(
        'teacher',
        'teacher__user',
        'classroom',
        'section',
        'subject',
    ).filter(
        teacher=teacher_profile,
        is_active=True,
    )

    serializer = TeachingAssignmentSerializer(assignments, many=True)
    return Response(serializer.data)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def teacher_students(request):
    teacher_profile, error = get_teacher_profile_or_error(request.user)
    if error:
        return error

    assignments = TeachingAssignment.objects.filter(
        teacher=teacher_profile,
        is_active=True,
    )

    section_ids = assignments.values_list('section_id', flat=True).distinct()

    students = StudentProfile.objects.select_related(
        'user',
        'classroom',
        'section',
    ).filter(
        section_id__in=section_ids
    ).distinct()

    serializer = TeacherStudentSerializer(students, many=True)
    return Response(serializer.data)


def student_schedule_response(request, student):
    schedules = Schedule.objects.select_related(
        'classroom',
        'section',
        'subject',
        'teacher',
        'teacher__user',
    ).filter(section=student.section)

    serializer = ScheduleSerializer(schedules, many=True)
    return Response(serializer.data)


def student_attendance_response(student):
    records = Attendance.objects.select_related(
        'student',
        'student__user',
        'subject',
        'teacher',
        'teacher__user',
    ).filter(student=student)

    serializer = AttendanceSerializer(records, many=True)
    return Response(serializer.data)


def student_grades_response(student):
    grades = Grade.objects.select_related(
        'student',
        'student__user',
        'subject',
        'teacher',
        'teacher__user',
    ).filter(student=student)

    serializer = GradeSerializer(grades, many=True)
    return Response(serializer.data)


def student_assignments_response(student):
    assignments = Assignment.objects.select_related(
        'teacher',
        'teacher__user',
        'classroom',
        'section',
        'subject',
    ).filter(section=student.section)

    serializer = AssignmentSerializer(assignments, many=True)
    return Response(serializer.data)


def student_files_response(request, student):
    files = TeacherUploadedFile.objects.select_related(
        'teacher',
        'teacher__user',
        'subject',
        'assignment',
        'classroom',
        'section',
    ).filter(section=student.section)

    serializer = TeacherUploadedFileSerializer(files, many=True, context={'request': request})
    return Response(serializer.data)


def student_announcements_response(student):
    announcements = Announcement.objects.select_related(
        'teacher',
        'teacher__user',
        'classroom',
        'section',
    ).filter(section=student.section)

    serializer = AnnouncementSerializer(announcements, many=True)
    return Response(serializer.data)


def student_submissions_response(request, student):
    submissions = submission_queryset().filter(student=student)
    serializer = AssignmentSubmissionSerializer(
        submissions,
        many=True,
        context={'request': request},
    )
    return Response(serializer.data)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def student_schedule(request):
    student, error = get_student_profile_or_error(request.user)
    if error:
        return error
    return student_schedule_response(request, student)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def student_attendance(request):
    student, error = get_student_profile_or_error(request.user)
    if error:
        return error
    return student_attendance_response(student)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def student_grades(request):
    student, error = get_student_profile_or_error(request.user)
    if error:
        return error
    return student_grades_response(student)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def student_assignments(request):
    student, error = get_student_profile_or_error(request.user)
    if error:
        return error
    return student_assignments_response(student)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def student_files(request):
    student, error = get_student_profile_or_error(request.user)
    if error:
        return error
    return student_files_response(request, student)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def student_announcements(request):
    student, error = get_student_profile_or_error(request.user)
    if error:
        return error
    return student_announcements_response(student)


@api_view(['POST'])
@parser_classes([MultiPartParser, FormParser])
@permission_classes([IsAuthenticated])
def student_submit_assignment(request, assignment_id):
    student, error = get_student_profile_or_error(request.user)
    if error:
        return error

    try:
        assignment = Assignment.objects.select_related(
            'teacher',
            'teacher__user',
            'section',
            'subject',
        ).get(id=assignment_id)
    except Assignment.DoesNotExist:
        return Response(
            {'detail': 'Assignment not found.'},
            status=status.HTTP_404_NOT_FOUND
        )

    if assignment.section_id != student.section_id:
        return Response(
            {'detail': 'You can only submit assignments for your section.'},
            status=status.HTTP_403_FORBIDDEN
        )

    serializer = AssignmentSubmissionCreateSerializer(data=request.data)
    if not serializer.is_valid():
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    existing_submission = AssignmentSubmission.objects.filter(
        assignment=assignment,
        student=student,
    ).first()

    today = timezone.localdate()
    is_late = bool(assignment.due_date and today > assignment.due_date)

    if existing_submission:
        if existing_submission.file:
            existing_submission.file.delete(save=False)

        existing_submission.file = serializer.validated_data['file']
        existing_submission.text_answer = serializer.validated_data.get(
            'text_answer',
            '',
        )
        existing_submission.status = (
            AssignmentSubmission.Status.LATE
            if is_late
            else AssignmentSubmission.Status.RESUBMITTED
        )
        existing_submission.teacher_note = ''
        existing_submission.grade = None
        existing_submission.save()
        submission = existing_submission
    else:
        submission = AssignmentSubmission.objects.create(
            assignment=assignment,
            student=student,
            file=serializer.validated_data['file'],
            text_answer=serializer.validated_data.get('text_answer', ''),
            status=(
                AssignmentSubmission.Status.LATE
                if is_late
                else AssignmentSubmission.Status.SUBMITTED
            ),
        )

    create_notification_for_user(
        recipient=assignment.teacher.user,
        notification_type=Notification.Type.ASSIGNMENT,
        title='Assignment submitted',
        message=(
            f'{student.user.get_full_name() or student.user.username} '
            f'submitted {assignment.title}.'
        ),
        related_object_type='AssignmentSubmission',
        related_object_id=submission.id,
        template_key='assignment_submitted',
        context={
            'student_name': student.user.get_full_name() or student.user.username,
            'assignment_title': assignment.title,
        },
    )

    response_serializer = AssignmentSubmissionSerializer(
        submission,
        context={'request': request},
    )
    return Response(response_serializer.data, status=status.HTTP_201_CREATED)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def student_submissions(request):
    student, error = get_student_profile_or_error(request.user)
    if error:
        return error
    return student_submissions_response(request, student)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def student_assignment_submission(request, assignment_id):
    student, error = get_student_profile_or_error(request.user)
    if error:
        return error

    try:
        submission = submission_queryset().get(
            student=student,
            assignment_id=assignment_id,
        )
    except AssignmentSubmission.DoesNotExist:
        return Response(
            {'detail': 'Submission not found.'},
            status=status.HTTP_404_NOT_FOUND
        )

    serializer = AssignmentSubmissionSerializer(
        submission,
        context={'request': request},
    )
    return Response(serializer.data)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def parent_child_schedule(request, student_id):
    student, error = get_parent_child_or_error(request.user, student_id)
    if error:
        return error
    return student_schedule_response(request, student)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def parent_child_attendance(request, student_id):
    student, error = get_parent_child_or_error(request.user, student_id)
    if error:
        return error
    return student_attendance_response(student)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def parent_child_grades(request, student_id):
    student, error = get_parent_child_or_error(request.user, student_id)
    if error:
        return error
    return student_grades_response(student)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def parent_child_assignments(request, student_id):
    student, error = get_parent_child_or_error(request.user, student_id)
    if error:
        return error
    return student_assignments_response(student)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def parent_child_files(request, student_id):
    student, error = get_parent_child_or_error(request.user, student_id)
    if error:
        return error
    return student_files_response(request, student)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def parent_child_announcements(request, student_id):
    student, error = get_parent_child_or_error(request.user, student_id)
    if error:
        return error
    return student_announcements_response(student)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def parent_child_submissions(request, student_id):
    student, error = get_parent_child_or_error(request.user, student_id)
    if error:
        return error
    return student_submissions_response(request, student)
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def teacher_create_attendance(request):
    teacher_profile, error = get_teacher_profile_or_error(request.user)
    if error:
        return error

    serializer = TeacherAttendanceCreateSerializer(data=request.data)

    if serializer.is_valid():
        student = serializer.validated_data['student']
        subject = serializer.validated_data['subject']

        if not teacher_has_assignment(teacher_profile, student.section_id, subject.id):
            return Response(
                {'detail': 'You are not allowed to record attendance for this student and subject.'},
                status=status.HTTP_403_FORBIDDEN
            )

        attendance = serializer.save(teacher=teacher_profile)
        notify_student_and_parents(
            student=attendance.student,
            notification_type=Notification.Type.ATTENDANCE,
            title='Attendance updated',
            message=(
                f'Attendance for {attendance.subject.name} '
                f'on {attendance.date}: {attendance.status}'
            ),
            related_object_type='Attendance',
            related_object_id=attendance.id,
            template_key='attendance_created',
            context={
                'subject_name': attendance.subject.name,
                'date': attendance.date,
                'status': attendance.status,
            },
        )
        return Response(AttendanceSerializer(attendance).data, status=status.HTTP_201_CREATED)

    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def teacher_create_grade(request):
    teacher_profile, error = get_teacher_profile_or_error(request.user)
    if error:
        return error

    serializer = TeacherGradeCreateSerializer(data=request.data)

    if serializer.is_valid():
        student = serializer.validated_data['student']
        subject = serializer.validated_data['subject']

        if not teacher_has_assignment(teacher_profile, student.section_id, subject.id):
            return Response(
                {'detail': 'You are not allowed to add grades for this student and subject.'},
                status=status.HTTP_403_FORBIDDEN
            )

        grade = serializer.save(teacher=teacher_profile)
        notify_student_and_parents(
            student=grade.student,
            notification_type=Notification.Type.GRADE,
            title='New grade added',
            message=(
                f'{grade.title} - {grade.subject.name}: '
                f'{grade.score}/{grade.max_score}'
            ),
            related_object_type='Grade',
            related_object_id=grade.id,
            template_key='grade_created',
            context={
                'grade_title': grade.title,
                'subject_name': grade.subject.name,
                'score': grade.score,
                'max_score': grade.max_score,
            },
        )
        return Response(GradeSerializer(grade).data, status=status.HTTP_201_CREATED)

    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def teacher_create_assignment(request):
    teacher_profile, error = get_teacher_profile_or_error(request.user)
    if error:
        return error

    serializer = TeacherAssignmentCreateSerializer(data=request.data)

    if serializer.is_valid():
        section = serializer.validated_data['section']
        subject = serializer.validated_data['subject']

        if not teacher_has_assignment(teacher_profile, section.id, subject.id):
            return Response(
                {'detail': 'You are not allowed to create assignments for this section and subject.'},
                status=status.HTTP_403_FORBIDDEN
            )

        assignment = serializer.save(teacher=teacher_profile)
        notify_section_students(
            section=assignment.section,
            notification_type=Notification.Type.ASSIGNMENT,
            title='New assignment',
            message=f'{assignment.title} - {assignment.subject.name}',
            related_object_type='Assignment',
            related_object_id=assignment.id,
            template_key='assignment_created',
            context={
                'assignment_title': assignment.title,
                'subject_name': assignment.subject.name,
                'due_date': assignment.due_date,
            },
        )
        return Response(AssignmentSerializer(assignment).data, status=status.HTTP_201_CREATED)

    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def teacher_create_announcement(request):
    teacher_profile, error = get_teacher_profile_or_error(request.user)
    if error:
        return error

    serializer = TeacherAnnouncementCreateSerializer(data=request.data)

    if serializer.is_valid():
        section = serializer.validated_data['section']

        allowed = TeachingAssignment.objects.filter(
            teacher=teacher_profile,
            section=section,
            is_active=True,
        ).exists()

        if not allowed:
            return Response(
                {'detail': 'You are not allowed to create announcements for this section.'},
                status=status.HTTP_403_FORBIDDEN
            )

        announcement = serializer.save(teacher=teacher_profile)
        notify_section_students(
            section=announcement.section,
            notification_type=Notification.Type.ANNOUNCEMENT,
            title=announcement.title,
            message=announcement.message,
            related_object_type='Announcement',
            related_object_id=announcement.id,
            template_key='announcement_created',
            context={
                'announcement_title': announcement.title,
                'announcement_message': announcement.message,
            },
        )
        return Response(AnnouncementSerializer(announcement).data, status=status.HTTP_201_CREATED)

    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def teacher_upload_file(request):
    teacher_profile, error = get_teacher_profile_or_error(request.user)
    if error:
        return error

    serializer = TeacherUploadedFileCreateSerializer(data=request.data)

    if serializer.is_valid():
        section = serializer.validated_data['section']
        subject = serializer.validated_data['subject']

        if not teacher_has_assignment(teacher_profile, section.id, subject.id):
            return Response(
                {'detail': 'You are not allowed to upload files for this section and subject.'},
                status=status.HTTP_403_FORBIDDEN
            )

        uploaded_file = serializer.save(teacher=teacher_profile)
        return Response(
            TeacherUploadedFileSerializer(uploaded_file, context={'request': request}).data,
            status=status.HTTP_201_CREATED
        )

    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def teacher_assignment_submissions(request, assignment_id):
    teacher_profile, error = get_teacher_profile_or_error(request.user)
    if error:
        return error

    try:
        assignment = Assignment.objects.select_related(
            'section',
            'subject',
        ).get(id=assignment_id)
    except Assignment.DoesNotExist:
        return Response(
            {'detail': 'Assignment not found.'},
            status=status.HTTP_404_NOT_FOUND
        )

    if not teacher_can_access_assignment(teacher_profile, assignment):
        return Response(
            {'detail': 'You are not allowed to view submissions for this assignment.'},
            status=status.HTTP_403_FORBIDDEN
        )

    submissions = submission_queryset().filter(assignment=assignment)
    serializer = AssignmentSubmissionSerializer(
        submissions,
        many=True,
        context={'request': request},
    )
    return Response(serializer.data)


@api_view(['PATCH'])
@permission_classes([IsAuthenticated])
def teacher_review_submission(request, submission_id):
    teacher_profile, error = get_teacher_profile_or_error(request.user)
    if error:
        return error

    try:
        submission = submission_queryset().get(id=submission_id)
    except AssignmentSubmission.DoesNotExist:
        return Response(
            {'detail': 'Submission not found.'},
            status=status.HTTP_404_NOT_FOUND
        )

    if not teacher_can_access_assignment(teacher_profile, submission.assignment):
        return Response(
            {'detail': 'You are not allowed to review this submission.'},
            status=status.HTTP_403_FORBIDDEN
        )

    data = request.data.copy()
    data['status'] = AssignmentSubmission.Status.REVIEWED

    serializer = AssignmentSubmissionReviewSerializer(
        submission,
        data=data,
        partial=True,
    )

    if serializer.is_valid():
        submission = serializer.save(status=AssignmentSubmission.Status.REVIEWED)

        notify_student_and_parents(
            student=submission.student,
            notification_type=Notification.Type.ASSIGNMENT,
            title='Assignment reviewed',
            message=f'{submission.assignment.title} has been reviewed.',
            related_object_type='AssignmentSubmission',
            related_object_id=submission.id,
            template_key='assignment_reviewed',
            context={
                'assignment_title': submission.assignment.title,
                'status': submission.status,
            },
        )

        response_serializer = AssignmentSubmissionSerializer(
            submission,
            context={'request': request},
        )
        return Response(response_serializer.data)

    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated])
def admin_academic_years(request):
    if not is_admin_user(request.user):
        return Response(
            {'detail': 'Only admins can access this endpoint.'},
            status=status.HTTP_403_FORBIDDEN
        )

    if request.method == 'GET':
        years = AcademicYear.objects.all()
        serializer = AcademicYearSerializer(years, many=True)
        return Response(serializer.data)

    serializer = AcademicYearSerializer(data=request.data)

    if serializer.is_valid():
        academic_year = serializer.save()

        if academic_year.is_active:
            AcademicYear.objects.exclude(id=academic_year.id).update(is_active=False)

        return Response(
            AcademicYearSerializer(academic_year).data,
            status=status.HTTP_201_CREATED,
        )

    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def admin_calculate_promotion_run(request):
    if not is_admin_user(request.user):
        return Response(
            {'detail': 'Only admins can calculate promotion results.'},
            status=status.HTTP_403_FORBIDDEN
        )

    academic_year_id = request.data.get('academic_year_id')

    if not academic_year_id:
        return Response(
            {'academic_year_id': ['This field is required.']},
            status=status.HTTP_400_BAD_REQUEST
        )

    try:
        academic_year = AcademicYear.objects.get(id=academic_year_id)
    except AcademicYear.DoesNotExist:
        return Response(
            {'detail': 'Academic year not found.'},
            status=status.HTTP_404_NOT_FOUND
        )

    promotion_run = calculate_promotion_results(
        academic_year=academic_year,
        created_by=request.user,
    )

    return Response(PromotionRunSerializer(promotion_run).data, status=status.HTTP_201_CREATED)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def admin_promotion_results(request):
    if not is_admin_user(request.user):
        return Response(
            {'detail': 'Only admins can view promotion results.'},
            status=status.HTTP_403_FORBIDDEN
        )

    academic_year_id = request.GET.get('academic_year_id')
    status_filter = request.GET.get('status', '').strip()

    results = StudentYearResult.objects.select_related(
        'student',
        'student__user',
        'student__classroom',
        'student__section',
        'academic_year',
    )

    if academic_year_id:
        results = results.filter(academic_year_id=academic_year_id)

    valid_statuses = {choice[0] for choice in StudentYearResult.Status.choices}
    if status_filter in valid_statuses:
        results = results.filter(status=status_filter)

    serializer = StudentYearResultSerializer(results, many=True)
    return Response(serializer.data)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def admin_promotion_result_detail(request, student_result_id):
    if not is_admin_user(request.user):
        return Response(
            {'detail': 'Only admins can view promotion results.'},
            status=status.HTTP_403_FORBIDDEN
        )

    try:
        result = StudentYearResult.objects.select_related(
            'student',
            'student__user',
            'student__classroom',
            'student__section',
            'academic_year',
        ).get(id=student_result_id)
    except StudentYearResult.DoesNotExist:
        return Response(
            {'detail': 'Promotion result not found.'},
            status=status.HTTP_404_NOT_FOUND
        )

    serializer = StudentYearResultSerializer(result)
    return Response(serializer.data)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def student_year_result(request):
    student, error = get_student_profile_or_error(request.user)
    if error:
        return error

    academic_year = get_active_academic_year()
    if not academic_year:
        return Response(
            {'detail': 'No active academic year found.'},
            status=status.HTTP_404_NOT_FOUND
        )

    try:
        result = StudentYearResult.objects.select_related(
            'student',
            'student__user',
            'student__classroom',
            'student__section',
            'academic_year',
        ).get(student=student, academic_year=academic_year)
    except StudentYearResult.DoesNotExist:
        return Response(
            {'detail': 'Year result not found.'},
            status=status.HTTP_404_NOT_FOUND
        )

    if not result.is_published:
        return Response(
            {'detail': 'Year result has not been published yet.'},
            status=status.HTTP_404_NOT_FOUND
        )

    serializer = StudentYearResultSerializer(result)
    return Response(serializer.data)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def parent_child_year_result(request, student_id):
    student, error = get_parent_child_or_error(request.user, student_id)
    if error:
        return error

    academic_year = get_active_academic_year()
    if not academic_year:
        return Response(
            {'detail': 'No active academic year found.'},
            status=status.HTTP_404_NOT_FOUND
        )

    try:
        result = StudentYearResult.objects.select_related(
            'student',
            'student__user',
            'student__classroom',
            'student__section',
            'academic_year',
        ).get(student=student, academic_year=academic_year)
    except StudentYearResult.DoesNotExist:
        return Response(
            {'detail': 'Year result not found.'},
            status=status.HTTP_404_NOT_FOUND
        )

    if not result.is_published:
        return Response(
            {'detail': 'Year result has not been published yet.'},
            status=status.HTTP_404_NOT_FOUND
        )

    serializer = StudentYearResultSerializer(result)
    return Response(serializer.data)

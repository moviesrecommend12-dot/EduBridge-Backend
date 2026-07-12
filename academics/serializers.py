from rest_framework import serializers
from accounts.models import StudentProfile
from .models import (
    AcademicYear,
    TeachingAssignment,
    Schedule,
    Attendance,
    Grade,
    Assignment,
    AssignmentSubmission,
    PromotionRun,
    StudentYearResult,
    SubjectYearResult,
    TeacherUploadedFile,
    Announcement,
)


class AcademicYearSerializer(serializers.ModelSerializer):
    class Meta:
        model = AcademicYear
        fields = ['id', 'name', 'start_date', 'end_date', 'is_active']

    def validate(self, attrs):
        start_date = attrs.get('start_date', getattr(self.instance, 'start_date', None))
        end_date = attrs.get('end_date', getattr(self.instance, 'end_date', None))

        if start_date and end_date and end_date <= start_date:
            raise serializers.ValidationError(
                {'end_date': 'End date must be after start date.'}
            )

        return attrs


class SubjectYearResultSerializer(serializers.ModelSerializer):
    subject = serializers.SerializerMethodField()

    class Meta:
        model = SubjectYearResult
        fields = [
            'id',
            'subject',
            'average_score',
            'max_score',
            'percentage',
            'is_failed',
        ]

    def get_subject(self, obj):
        return {
            'id': obj.subject.id,
            'name': obj.subject.name,
            'code': obj.subject.code,
        }


class StudentYearResultSerializer(serializers.ModelSerializer):
    student = serializers.SerializerMethodField()
    academic_year = AcademicYearSerializer(read_only=True)
    subjects = serializers.SerializerMethodField()

    class Meta:
        model = StudentYearResult
        fields = [
            'id',
            'student',
            'academic_year',
            'average_percentage',
            'failed_subjects_count',
            'status',
            'calculated_at',
            'is_published',
            'published_at',
            'notes',
            'subjects',
        ]

    def get_student(self, obj):
        return {
            'id': obj.student.id,
            'student_code': obj.student.student_code,
            'name': obj.student.user.get_full_name() or obj.student.user.username,
            'classroom': obj.student.classroom.name if obj.student.classroom else None,
            'section': obj.student.section.name if obj.student.section else None,
        }

    def get_subjects(self, obj):
        subjects = SubjectYearResult.objects.select_related('subject').filter(
            student=obj.student,
            academic_year=obj.academic_year,
        )
        return SubjectYearResultSerializer(subjects, many=True).data


class PromotionRunSerializer(serializers.ModelSerializer):
    academic_year = AcademicYearSerializer(read_only=True)

    class Meta:
        model = PromotionRun
        fields = [
            'id',
            'academic_year',
            'created_at',
            'total_students',
            'promoted_count',
            'failed_count',
            'needs_review_count',
        ]


class TeachingAssignmentSerializer(serializers.ModelSerializer):
    teacher = serializers.SerializerMethodField()
    classroom = serializers.SerializerMethodField()
    section = serializers.SerializerMethodField()
    subject = serializers.SerializerMethodField()

    class Meta:
        model = TeachingAssignment
        fields = ['id', 'teacher', 'classroom', 'section', 'subject', 'is_active']

    def get_teacher(self, obj):
        return {
            'id': obj.teacher.id,
            'name': obj.teacher.user.get_full_name() or obj.teacher.user.username,
            'employee_code': obj.teacher.employee_code,
        }

    def get_classroom(self, obj):
        return {
            'id': obj.classroom.id,
            'name': obj.classroom.name,
            'grade_level': obj.classroom.grade_level,
        }

    def get_section(self, obj):
        return {
            'id': obj.section.id,
            'name': obj.section.name,
        }

    def get_subject(self, obj):
        return {
            'id': obj.subject.id,
            'name': obj.subject.name,
            'code': obj.subject.code,
        }


class TeacherStudentSerializer(serializers.ModelSerializer):
    user = serializers.SerializerMethodField()
    classroom = serializers.SerializerMethodField()
    section = serializers.SerializerMethodField()

    class Meta:
        model = StudentProfile
        fields = ['id', 'student_code', 'user', 'classroom', 'section']

    def get_user(self, obj):
        return {
            'id': obj.user.id,
            'username': obj.user.username,
            'full_name': obj.user.get_full_name() or obj.user.username,
            'email': obj.user.email,
            'phone': obj.user.phone,
        }

    def get_classroom(self, obj):
        if not obj.classroom:
            return None
        return {'id': obj.classroom.id, 'name': obj.classroom.name}

    def get_section(self, obj):
        if not obj.section:
            return None
        return {'id': obj.section.id, 'name': obj.section.name}


class ScheduleSerializer(serializers.ModelSerializer):
    subject = serializers.SerializerMethodField()
    teacher = serializers.SerializerMethodField()
    classroom = serializers.SerializerMethodField()
    section = serializers.SerializerMethodField()

    class Meta:
        model = Schedule
        fields = [
            'id',
            'classroom',
            'section',
            'subject',
            'teacher',
            'day_of_week',
            'start_time',
            'end_time',
            'room_name',
        ]

    def get_subject(self, obj):
        return {'id': obj.subject.id, 'name': obj.subject.name, 'code': obj.subject.code}

    def get_teacher(self, obj):
        return {
            'id': obj.teacher.id,
            'name': obj.teacher.user.get_full_name() or obj.teacher.user.username,
        }

    def get_classroom(self, obj):
        return {'id': obj.classroom.id, 'name': obj.classroom.name}

    def get_section(self, obj):
        return {'id': obj.section.id, 'name': obj.section.name}


class AttendanceSerializer(serializers.ModelSerializer):
    student = serializers.SerializerMethodField()
    subject = serializers.SerializerMethodField()
    teacher = serializers.SerializerMethodField()

    class Meta:
        model = Attendance
        fields = ['id', 'student', 'subject', 'teacher', 'date', 'status', 'note', 'created_at']

    def get_student(self, obj):
        return {
            'id': obj.student.id,
            'student_code': obj.student.student_code,
            'name': obj.student.user.get_full_name() or obj.student.user.username,
        }

    def get_subject(self, obj):
        return {'id': obj.subject.id, 'name': obj.subject.name, 'code': obj.subject.code}

    def get_teacher(self, obj):
        if not obj.teacher:
            return None
        return {
            'id': obj.teacher.id,
            'name': obj.teacher.user.get_full_name() or obj.teacher.user.username,
        }


class GradeSerializer(serializers.ModelSerializer):
    student = serializers.SerializerMethodField()
    subject = serializers.SerializerMethodField()
    teacher = serializers.SerializerMethodField()

    class Meta:
        model = Grade
        fields = ['id', 'student', 'subject', 'teacher', 'title', 'score', 'max_score', 'note', 'date', 'created_at']

    def get_student(self, obj):
        return {
            'id': obj.student.id,
            'student_code': obj.student.student_code,
            'name': obj.student.user.get_full_name() or obj.student.user.username,
        }

    def get_subject(self, obj):
        return {'id': obj.subject.id, 'name': obj.subject.name, 'code': obj.subject.code}

    def get_teacher(self, obj):
        if not obj.teacher:
            return None
        return {
            'id': obj.teacher.id,
            'name': obj.teacher.user.get_full_name() or obj.teacher.user.username,
        }


class AssignmentSerializer(serializers.ModelSerializer):
    teacher = serializers.SerializerMethodField()
    classroom = serializers.SerializerMethodField()
    section = serializers.SerializerMethodField()
    subject = serializers.SerializerMethodField()

    class Meta:
        model = Assignment
        fields = [
            'id',
            'teacher',
            'classroom',
            'section',
            'subject',
            'title',
            'description',
            'due_date',
            'created_at',
        ]

    def get_teacher(self, obj):
        return {
            'id': obj.teacher.id,
            'name': obj.teacher.user.get_full_name() or obj.teacher.user.username,
        }

    def get_classroom(self, obj):
        return {'id': obj.classroom.id, 'name': obj.classroom.name}

    def get_section(self, obj):
        return {'id': obj.section.id, 'name': obj.section.name}

    def get_subject(self, obj):
        return {'id': obj.subject.id, 'name': obj.subject.name, 'code': obj.subject.code}


class AssignmentSubmissionSerializer(serializers.ModelSerializer):
    assignment = serializers.SerializerMethodField()
    student = serializers.SerializerMethodField()
    file_url = serializers.SerializerMethodField()

    class Meta:
        model = AssignmentSubmission
        fields = [
            'id',
            'assignment',
            'student',
            'file',
            'file_url',
            'text_answer',
            'status',
            'teacher_note',
            'grade',
            'submitted_at',
            'updated_at',
        ]

    def get_assignment(self, obj):
        return {
            'id': obj.assignment.id,
            'title': obj.assignment.title,
            'subject': {
                'id': obj.assignment.subject.id,
                'name': obj.assignment.subject.name,
                'code': obj.assignment.subject.code,
            },
            'due_date': obj.assignment.due_date,
        }

    def get_student(self, obj):
        return {
            'id': obj.student.id,
            'student_code': obj.student.student_code,
            'name': obj.student.user.get_full_name() or obj.student.user.username,
        }

    def get_file_url(self, obj):
        request = self.context.get('request')
        if obj.file and request:
            return request.build_absolute_uri(obj.file.url)
        if obj.file:
            return obj.file.url
        return None


class AssignmentSubmissionCreateSerializer(serializers.Serializer):
    file = serializers.FileField()
    text_answer = serializers.CharField(required=False, allow_blank=True)

    def validate_file(self, value):
        allowed_extensions = ('.pdf', '.png', '.jpg', '.jpeg', '.gif', '.doc', '.docx')
        filename = value.name.lower()

        if not filename.endswith(allowed_extensions):
            raise serializers.ValidationError(
                'Only PDF, image, DOC, and DOCX files are allowed.'
            )

        return value


class AssignmentSubmissionReviewSerializer(serializers.ModelSerializer):
    class Meta:
        model = AssignmentSubmission
        fields = ['teacher_note', 'grade', 'status']

    def validate_status(self, value):
        if value != AssignmentSubmission.Status.REVIEWED:
            raise serializers.ValidationError('Review status must be REVIEWED.')
        return value


class TeacherUploadedFileSerializer(serializers.ModelSerializer):
    file_url = serializers.SerializerMethodField()
    teacher = serializers.SerializerMethodField()
    subject = serializers.SerializerMethodField()

    class Meta:
        model = TeacherUploadedFile
        fields = [
            'id',
            'title',
            'file',
            'file_url',
            'file_type',
            'teacher',
            'subject',
            'assignment',
            'created_at',
        ]

    def get_file_url(self, obj):
        request = self.context.get('request')
        if obj.file and request:
            return request.build_absolute_uri(obj.file.url)
        if obj.file:
            return obj.file.url
        return None

    def get_teacher(self, obj):
        return {
            'id': obj.teacher.id,
            'name': obj.teacher.user.get_full_name() or obj.teacher.user.username,
        }

    def get_subject(self, obj):
        return {'id': obj.subject.id, 'name': obj.subject.name, 'code': obj.subject.code}


class AnnouncementSerializer(serializers.ModelSerializer):
    teacher = serializers.SerializerMethodField()
    classroom = serializers.SerializerMethodField()
    section = serializers.SerializerMethodField()

    class Meta:
        model = Announcement
        fields = ['id', 'teacher', 'classroom', 'section', 'title', 'message', 'created_at']

    def get_teacher(self, obj):
        if not obj.teacher:
            return None
        return {
            'id': obj.teacher.id,
            'name': obj.teacher.user.get_full_name() or obj.teacher.user.username,
        }

    def get_classroom(self, obj):
        return {'id': obj.classroom.id, 'name': obj.classroom.name}

    def get_section(self, obj):
        return {'id': obj.section.id, 'name': obj.section.name}


class TeacherAttendanceCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Attendance
        fields = ['student', 'subject', 'date', 'status', 'note']


class TeacherGradeCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Grade
        fields = ['student', 'subject', 'title', 'score', 'max_score', 'note', 'date']


class TeacherAssignmentCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Assignment
        fields = ['classroom', 'section', 'subject', 'title', 'description', 'due_date']


class TeacherAnnouncementCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Announcement
        fields = ['classroom', 'section', 'title', 'message']


class TeacherUploadedFileCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = TeacherUploadedFile
        fields = [
            'assignment',
            'classroom',
            'section',
            'subject',
            'title',
            'file',
            'file_type',
        ]

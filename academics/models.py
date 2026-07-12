from django.conf import settings
from django.db import models


class ClassRoom(models.Model):
    name = models.CharField(max_length=100)
    grade_level = models.CharField(max_length=50, blank=True)
    description = models.TextField(blank=True)

    class Meta:
        ordering = ['name']

    def __str__(self):
        return self.name


class Section(models.Model):
    classroom = models.ForeignKey(
        ClassRoom,
        on_delete=models.CASCADE,
        related_name='sections'
    )
    name = models.CharField(max_length=50)

    class Meta:
        unique_together = ('classroom', 'name')
        ordering = ['classroom__name', 'name']

    def __str__(self):
        return f"{self.classroom.name} - {self.name}"


class Subject(models.Model):
    name = models.CharField(max_length=100)
    code = models.CharField(max_length=30, unique=True)
    description = models.TextField(blank=True)

    class Meta:
        ordering = ['name']

    def __str__(self):
        return f"{self.name} ({self.code})"


class AcademicYear(models.Model):
    name = models.CharField(max_length=20, unique=True)
    start_date = models.DateField()
    end_date = models.DateField()
    is_active = models.BooleanField(default=False)

    class Meta:
        ordering = ['-start_date', 'name']

    def __str__(self):
        return self.name


class StudentYearResult(models.Model):
    class Status(models.TextChoices):
        PROMOTED = 'PROMOTED', 'Promoted'
        FAILED = 'FAILED', 'Failed'
        NEEDS_REVIEW = 'NEEDS_REVIEW', 'Needs review'

    student = models.ForeignKey(
        'accounts.StudentProfile',
        on_delete=models.CASCADE,
        related_name='year_results'
    )
    academic_year = models.ForeignKey(
        AcademicYear,
        on_delete=models.CASCADE,
        related_name='student_results'
    )
    average_percentage = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        null=True,
        blank=True
    )
    failed_subjects_count = models.PositiveIntegerField(default=0)
    status = models.CharField(max_length=20, choices=Status.choices)
    calculated_at = models.DateTimeField(auto_now=True)
    is_published = models.BooleanField(default=False)
    published_at = models.DateTimeField(null=True, blank=True)
    notes = models.TextField(blank=True)

    class Meta:
        unique_together = ('student', 'academic_year')
        ordering = ['student__student_code']

    def __str__(self):
        return f"{self.student} - {self.academic_year} - {self.status}"


class SubjectYearResult(models.Model):
    student = models.ForeignKey(
        'accounts.StudentProfile',
        on_delete=models.CASCADE,
        related_name='subject_year_results'
    )
    subject = models.ForeignKey(
        Subject,
        on_delete=models.CASCADE,
        related_name='subject_year_results'
    )
    academic_year = models.ForeignKey(
        AcademicYear,
        on_delete=models.CASCADE,
        related_name='subject_results'
    )
    average_score = models.DecimalField(max_digits=8, decimal_places=2)
    max_score = models.DecimalField(max_digits=8, decimal_places=2)
    percentage = models.DecimalField(max_digits=5, decimal_places=2)
    is_failed = models.BooleanField(default=False)

    class Meta:
        unique_together = ('student', 'subject', 'academic_year')
        ordering = ['subject__name']

    def __str__(self):
        return f"{self.student} - {self.subject} - {self.percentage}%"


class PromotionRun(models.Model):
    academic_year = models.ForeignKey(
        AcademicYear,
        on_delete=models.CASCADE,
        related_name='promotion_runs'
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='promotion_runs'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    total_students = models.PositiveIntegerField(default=0)
    promoted_count = models.PositiveIntegerField(default=0)
    failed_count = models.PositiveIntegerField(default=0)
    needs_review_count = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.academic_year} - {self.created_at:%Y-%m-%d %H:%M}"


class TeachingAssignment(models.Model):
    teacher = models.ForeignKey(
        'accounts.TeacherProfile',
        on_delete=models.CASCADE,
        related_name='teaching_assignments'
    )
    classroom = models.ForeignKey(
        ClassRoom,
        on_delete=models.CASCADE,
        related_name='teaching_assignments'
    )
    section = models.ForeignKey(
        Section,
        on_delete=models.CASCADE,
        related_name='teaching_assignments'
    )
    subject = models.ForeignKey(
        Subject,
        on_delete=models.CASCADE,
        related_name='teaching_assignments'
    )
    is_active = models.BooleanField(default=True)

    class Meta:
        unique_together = ('teacher', 'classroom', 'section', 'subject')
        ordering = ['teacher__user__username', 'classroom__name', 'section__name', 'subject__name']

    def __str__(self):
        return f"{self.teacher} - {self.classroom} - {self.section} - {self.subject}"


class Schedule(models.Model):
    class DayOfWeek(models.TextChoices):
        MONDAY = 'MONDAY', 'Monday'
        TUESDAY = 'TUESDAY', 'Tuesday'
        WEDNESDAY = 'WEDNESDAY', 'Wednesday'
        THURSDAY = 'THURSDAY', 'Thursday'
        FRIDAY = 'FRIDAY', 'Friday'
        SATURDAY = 'SATURDAY', 'Saturday'
        SUNDAY = 'SUNDAY', 'Sunday'

    classroom = models.ForeignKey(ClassRoom, on_delete=models.CASCADE, related_name='schedules')
    section = models.ForeignKey(Section, on_delete=models.CASCADE, related_name='schedules')
    subject = models.ForeignKey(Subject, on_delete=models.CASCADE, related_name='schedules')
    teacher = models.ForeignKey('accounts.TeacherProfile', on_delete=models.CASCADE, related_name='schedules')

    day_of_week = models.CharField(max_length=20, choices=DayOfWeek.choices)
    start_time = models.TimeField()
    end_time = models.TimeField()
    room_name = models.CharField(max_length=100, blank=True)

    class Meta:
        ordering = ['day_of_week', 'start_time']

    def __str__(self):
        return f"{self.section} - {self.subject} - {self.day_of_week} {self.start_time}"


class Attendance(models.Model):
    class Status(models.TextChoices):
        PRESENT = 'PRESENT', 'Present'
        ABSENT = 'ABSENT', 'Absent'
        LATE = 'LATE', 'Late'
        EXCUSED = 'EXCUSED', 'Excused'

    student = models.ForeignKey('accounts.StudentProfile', on_delete=models.CASCADE, related_name='attendance_records')
    teacher = models.ForeignKey('accounts.TeacherProfile', on_delete=models.SET_NULL, null=True, blank=True, related_name='attendance_records')
    subject = models.ForeignKey(Subject, on_delete=models.CASCADE, related_name='attendance_records')

    date = models.DateField()
    status = models.CharField(max_length=20, choices=Status.choices)
    note = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('student', 'subject', 'date')
        ordering = ['-date']

    def __str__(self):
        return f"{self.student} - {self.subject} - {self.date} - {self.status}"


class Grade(models.Model):
    student = models.ForeignKey('accounts.StudentProfile', on_delete=models.CASCADE, related_name='grades')
    teacher = models.ForeignKey('accounts.TeacherProfile', on_delete=models.SET_NULL, null=True, blank=True, related_name='grades')
    subject = models.ForeignKey(Subject, on_delete=models.CASCADE, related_name='grades')

    title = models.CharField(max_length=150)
    score = models.DecimalField(max_digits=6, decimal_places=2)
    max_score = models.DecimalField(max_digits=6, decimal_places=2, default=100)
    note = models.TextField(blank=True)

    date = models.DateField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-date', 'subject__name']

    def __str__(self):
        return f"{self.student} - {self.subject} - {self.title}: {self.score}/{self.max_score}"


class Assignment(models.Model):
    teacher = models.ForeignKey('accounts.TeacherProfile', on_delete=models.CASCADE, related_name='assignments')
    classroom = models.ForeignKey(ClassRoom, on_delete=models.CASCADE, related_name='assignments')
    section = models.ForeignKey(Section, on_delete=models.CASCADE, related_name='assignments')
    subject = models.ForeignKey(Subject, on_delete=models.CASCADE, related_name='assignments')

    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    due_date = models.DateField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.title} - {self.section} - {self.subject}"


class AssignmentSubmission(models.Model):
    class Status(models.TextChoices):
        SUBMITTED = 'SUBMITTED', 'Submitted'
        LATE = 'LATE', 'Late'
        REVIEWED = 'REVIEWED', 'Reviewed'
        RESUBMITTED = 'RESUBMITTED', 'Resubmitted'

    assignment = models.ForeignKey(
        Assignment,
        on_delete=models.CASCADE,
        related_name='submissions'
    )
    student = models.ForeignKey(
        'accounts.StudentProfile',
        on_delete=models.CASCADE,
        related_name='assignment_submissions'
    )
    file = models.FileField(upload_to='assignment_submissions/')
    text_answer = models.TextField(blank=True)
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.SUBMITTED
    )
    teacher_note = models.TextField(blank=True)
    grade = models.DecimalField(
        max_digits=6,
        decimal_places=2,
        null=True,
        blank=True
    )
    submitted_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('assignment', 'student')
        ordering = ['-updated_at']

    def __str__(self):
        return f"{self.student} - {self.assignment} - {self.status}"


class TeacherUploadedFile(models.Model):
    class FileType(models.TextChoices):
        PDF = 'PDF', 'PDF'
        IMAGE = 'IMAGE', 'Image'
        OTHER = 'OTHER', 'Other'

    teacher = models.ForeignKey('accounts.TeacherProfile', on_delete=models.CASCADE, related_name='uploaded_files')
    assignment = models.ForeignKey(Assignment, on_delete=models.CASCADE, null=True, blank=True, related_name='files')

    classroom = models.ForeignKey(ClassRoom, on_delete=models.CASCADE, related_name='uploaded_files')
    section = models.ForeignKey(Section, on_delete=models.CASCADE, related_name='uploaded_files')
    subject = models.ForeignKey(Subject, on_delete=models.CASCADE, related_name='uploaded_files')

    title = models.CharField(max_length=200)
    file = models.FileField(upload_to='teacher_uploads/')
    file_type = models.CharField(max_length=20, choices=FileType.choices, default=FileType.OTHER)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.title} - {self.teacher}"


class Announcement(models.Model):
    teacher = models.ForeignKey(
        'accounts.TeacherProfile',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='announcements'
    )
    classroom = models.ForeignKey(ClassRoom, on_delete=models.CASCADE, related_name='announcements')
    section = models.ForeignKey(Section, on_delete=models.CASCADE, related_name='announcements')

    title = models.CharField(max_length=200)
    message = models.TextField()

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.title} - {self.section}"

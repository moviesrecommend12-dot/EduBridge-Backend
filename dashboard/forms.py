from django import forms
from django.contrib.auth import get_user_model
from django.core.exceptions import NON_FIELD_ERRORS
from django.db import transaction

from academics.models import (
    AcademicYear,
    Announcement,
    Assignment,
    Attendance,
    ClassRoom,
    Grade,
    Schedule,
    Section,
    Subject,
    AssignmentSubmission,
    TeacherUploadedFile,
    TeachingAssignment,
)
from finance.models import FeeInvoice
from notifications.models import Notification, NotificationPreference, NotificationTemplate
from accounts.models import (
    ParentLinkingCode,
    ParentProfile,
    StudentProfile,
    TeacherProfile,
)

User = get_user_model()

SCHEDULE_DAY_CHOICES = [
    ("MONDAY", "الإثنين"),
    ("TUESDAY", "الثلاثاء"),
    ("WEDNESDAY", "الأربعاء"),
    ("THURSDAY", "الخميس"),
    ("FRIDAY", "الجمعة"),
    ("SATURDAY", "السبت"),
    ("SUNDAY", "الأحد"),
]

ATTENDANCE_STATUS_CHOICES = [
    ("PRESENT", "حاضر"),
    ("ABSENT", "غائب"),
    ("LATE", "متأخر"),
    ("EXCUSED", "معذور"),
]

FILE_TYPE_CHOICES = [
    ("PDF", "PDF"),
    ("IMAGE", "صورة"),
    ("OTHER", "أخرى"),
]


class StudentCreateForm(forms.Form):
    username = forms.CharField(max_length=150, label="اسم المستخدم")
    password = forms.CharField(
        min_length=8, widget=forms.PasswordInput, label="كلمة المرور"
    )
    first_name = forms.CharField(max_length=150, label="الاسم الأول")
    last_name = forms.CharField(max_length=150, label="اسم العائلة")
    email = forms.EmailField(required=False, label="البريد الإلكتروني")
    phone = forms.CharField(max_length=20, required=False, label="رقم الهاتف")
    student_code = forms.CharField(max_length=30, label="رقم الطالب")
    date_of_birth = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={"type": "date"}),
        label="تاريخ الميلاد",
    )
    address = forms.CharField(
        required=False, widget=forms.Textarea(attrs={"rows": 3}), label="العنوان"
    )
    classroom = forms.ModelChoiceField(queryset=ClassRoom.objects.all(), label="الصف")
    section = forms.ModelChoiceField(
        queryset=Section.objects.select_related("classroom"), label="الشعبة"
    )

    def clean_username(self):
        username = self.cleaned_data["username"]

        if User.objects.filter(username__iexact=username).exists():
            raise forms.ValidationError("اسم المستخدم مستخدم مسبقًا.")

        return username

    def clean_student_code(self):
        student_code = self.cleaned_data["student_code"]

        if StudentProfile.objects.filter(student_code__iexact=student_code).exists():
            raise forms.ValidationError("رقم الطالب مستخدم مسبقًا.")

        return student_code

    def clean(self):
        cleaned_data = super().clean()

        classroom = cleaned_data.get("classroom")
        section = cleaned_data.get("section")

        if classroom and section:
            if section.classroom_id != classroom.id:
                self.add_error("section", "هذه الشعبة لا تتبع الصف المختار.")

        return cleaned_data

    @transaction.atomic
    def save(self):
        user = User.objects.create_user(
            username=self.cleaned_data["username"],
            password=self.cleaned_data["password"],
            first_name=self.cleaned_data["first_name"],
            last_name=self.cleaned_data["last_name"],
            email=self.cleaned_data.get("email", ""),
            phone=self.cleaned_data.get("phone", ""),
            role=User.Role.STUDENT,
        )

        student = StudentProfile.objects.create(
            user=user,
            student_code=self.cleaned_data["student_code"],
            date_of_birth=self.cleaned_data.get("date_of_birth"),
            address=self.cleaned_data.get("address", ""),
            classroom=self.cleaned_data["classroom"],
            section=self.cleaned_data["section"],
        )

        linking_code = ParentLinkingCode.objects.create(student=student)

        return student, linking_code


class StudentUpdateForm(forms.Form):
    first_name = forms.CharField(max_length=150, label="الاسم الأول")
    last_name = forms.CharField(max_length=150, label="اسم العائلة")
    email = forms.EmailField(required=False, label="البريد الإلكتروني")
    phone = forms.CharField(max_length=20, required=False, label="رقم الهاتف")
    student_code = forms.CharField(max_length=30, label="رقم الطالب")
    date_of_birth = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={"type": "date"}),
        label="تاريخ الميلاد",
    )
    address = forms.CharField(
        required=False, widget=forms.Textarea(attrs={"rows": 3}), label="العنوان"
    )
    classroom = forms.ModelChoiceField(queryset=ClassRoom.objects.all(), label="الصف")
    section = forms.ModelChoiceField(
        queryset=Section.objects.select_related("classroom"), label="الشعبة"
    )

    def __init__(self, *args, student=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.student = student

        if student and not self.is_bound:
            self.initial.update(
                {
                    "first_name": student.user.first_name,
                    "last_name": student.user.last_name,
                    "email": student.user.email,
                    "phone": student.user.phone,
                    "student_code": student.student_code,
                    "date_of_birth": student.date_of_birth,
                    "address": student.address,
                    "classroom": student.classroom,
                    "section": student.section,
                }
            )

    def clean_student_code(self):
        student_code = self.cleaned_data["student_code"]
        queryset = StudentProfile.objects.filter(student_code__iexact=student_code)

        if self.student:
            queryset = queryset.exclude(id=self.student.id)

        if queryset.exists():
            raise forms.ValidationError("رقم الطالب مستخدم مسبقًا.")

        return student_code

    def clean(self):
        cleaned_data = super().clean()
        classroom = cleaned_data.get("classroom")
        section = cleaned_data.get("section")

        if classroom and section:
            if section.classroom_id != classroom.id:
                self.add_error("section", "هذه الشعبة لا تتبع الصف المختار.")

        return cleaned_data


class NotificationBroadcastForm(forms.Form):
    AUDIENCE_ALL = "ALL"
    AUDIENCE_ROLE = "ROLE"
    AUDIENCE_CLASSROOM = "CLASSROOM"
    AUDIENCE_SECTION = "SECTION"
    AUDIENCE_CHOICES = [
        (AUDIENCE_ALL, "كل المستخدمين"),
        (AUDIENCE_ROLE, "حسب الدور"),
        (AUDIENCE_CLASSROOM, "حسب الصف"),
        (AUDIENCE_SECTION, "حسب الشعبة"),
    ]

    audience = forms.ChoiceField(choices=AUDIENCE_CHOICES, label="الجمهور")
    role = forms.ChoiceField(choices=[], required=False, label="الدور")
    classroom = forms.ModelChoiceField(
        queryset=ClassRoom.objects.none(),
        required=False,
        label="الصف",
    )
    section = forms.ModelChoiceField(
        queryset=Section.objects.none(),
        required=False,
        label="الشعبة",
    )
    notification_type = forms.ChoiceField(
        choices=Notification.Type.choices,
        label="نوع الإشعار",
    )
    title = forms.CharField(max_length=200, label="العنوان")
    message = forms.CharField(
        widget=forms.Textarea(attrs={"rows": 5}),
        label="الرسالة",
    )
    deep_link = forms.CharField(
        max_length=255,
        required=False,
        label="رابط Flutter اختياري",
        help_text="مثال: orbiet://announcements/12",
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["role"].choices = [("", "اختر الدور")] + list(User.Role.choices)
        self.fields["classroom"].queryset = ClassRoom.objects.order_by("name")
        self.fields["section"].queryset = Section.objects.select_related(
            "classroom"
        ).order_by("classroom__name", "name")

    def clean(self):
        cleaned_data = super().clean()
        audience = cleaned_data.get("audience")
        role = cleaned_data.get("role")
        classroom = cleaned_data.get("classroom")
        section = cleaned_data.get("section")

        if audience == self.AUDIENCE_ROLE and not role:
            self.add_error("role", "اختر الدور المطلوب.")

        if audience == self.AUDIENCE_CLASSROOM and not classroom:
            self.add_error("classroom", "اختر الصف المطلوب.")

        if audience == self.AUDIENCE_SECTION and not section:
            self.add_error("section", "اختر الشعبة المطلوبة.")

        if classroom and section and section.classroom_id != classroom.id:
            self.add_error("section", "هذه الشعبة لا تتبع الصف المختار.")

        return cleaned_data

    @transaction.atomic
    def save(self):
        student = self.student
        user = student.user

        user.first_name = self.cleaned_data["first_name"]
        user.last_name = self.cleaned_data["last_name"]
        user.email = self.cleaned_data.get("email", "")
        user.phone = self.cleaned_data.get("phone", "")
        user.save()

        student.student_code = self.cleaned_data["student_code"]
        student.date_of_birth = self.cleaned_data.get("date_of_birth")
        student.address = self.cleaned_data.get("address", "")
        student.classroom = self.cleaned_data["classroom"]
        student.section = self.cleaned_data["section"]
        student.save()

        return student


class TeacherCreateForm(forms.Form):
    username = forms.CharField(max_length=150, label="اسم المستخدم")
    password = forms.CharField(
        min_length=8, widget=forms.PasswordInput, label="كلمة المرور"
    )
    first_name = forms.CharField(max_length=150, label="الاسم الأول")
    last_name = forms.CharField(max_length=150, label="اسم العائلة")
    email = forms.EmailField(required=False, label="البريد الإلكتروني")
    phone = forms.CharField(max_length=20, required=False, label="رقم الهاتف")
    employee_code = forms.CharField(max_length=30, label="رقم الموظف")
    specialization = forms.CharField(max_length=100, required=False, label="التخصص")
    bio = forms.CharField(
        required=False, widget=forms.Textarea(attrs={"rows": 3}), label="نبذة"
    )

    def clean_username(self):
        username = self.cleaned_data["username"]

        if User.objects.filter(username__iexact=username).exists():
            raise forms.ValidationError("اسم المستخدم مستخدم مسبقًا.")

        return username

    def clean_employee_code(self):
        from accounts.models import TeacherProfile

        employee_code = self.cleaned_data["employee_code"]

        if TeacherProfile.objects.filter(employee_code__iexact=employee_code).exists():
            raise forms.ValidationError("رقم الموظف مستخدم مسبقًا.")

        return employee_code

    @transaction.atomic
    def save(self):
        from accounts.models import TeacherProfile

        user = User.objects.create_user(
            username=self.cleaned_data["username"],
            password=self.cleaned_data["password"],
            first_name=self.cleaned_data["first_name"],
            last_name=self.cleaned_data["last_name"],
            email=self.cleaned_data.get("email", ""),
            phone=self.cleaned_data.get("phone", ""),
            role=User.Role.TEACHER,
        )

        return TeacherProfile.objects.create(
            user=user,
            employee_code=self.cleaned_data["employee_code"],
            specialization=self.cleaned_data.get("specialization", ""),
            bio=self.cleaned_data.get("bio", ""),
        )


class TeacherUpdateForm(forms.Form):
    first_name = forms.CharField(max_length=150, label="الاسم الأول")
    last_name = forms.CharField(max_length=150, label="اسم العائلة")
    email = forms.EmailField(required=False, label="البريد الإلكتروني")
    phone = forms.CharField(max_length=20, required=False, label="رقم الهاتف")
    employee_code = forms.CharField(max_length=30, label="رقم الموظف")
    specialization = forms.CharField(max_length=100, required=False, label="التخصص")
    bio = forms.CharField(
        required=False, widget=forms.Textarea(attrs={"rows": 3}), label="نبذة"
    )

    def __init__(self, *args, teacher=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.teacher = teacher

        if teacher and not self.is_bound:
            self.initial.update(
                {
                    "first_name": teacher.user.first_name,
                    "last_name": teacher.user.last_name,
                    "email": teacher.user.email,
                    "phone": teacher.user.phone,
                    "employee_code": teacher.employee_code,
                    "specialization": teacher.specialization,
                    "bio": teacher.bio,
                }
            )

    def clean_employee_code(self):
        from accounts.models import TeacherProfile

        employee_code = self.cleaned_data["employee_code"]

        queryset = TeacherProfile.objects.filter(employee_code__iexact=employee_code)

        if self.teacher:
            queryset = queryset.exclude(id=self.teacher.id)

        if queryset.exists():
            raise forms.ValidationError("رقم الموظف مستخدم مسبقًا.")

        return employee_code

    @transaction.atomic
    def save(self):
        teacher = self.teacher
        user = teacher.user

        user.first_name = self.cleaned_data["first_name"]
        user.last_name = self.cleaned_data["last_name"]
        user.email = self.cleaned_data.get("email", "")
        user.phone = self.cleaned_data.get("phone", "")
        user.save()

        teacher.employee_code = self.cleaned_data["employee_code"]
        teacher.specialization = self.cleaned_data.get("specialization", "")
        teacher.bio = self.cleaned_data.get("bio", "")
        teacher.save()

        return teacher


class ParentUpdateForm(forms.Form):
    first_name = forms.CharField(max_length=150, label="الاسم الأول")
    last_name = forms.CharField(max_length=150, label="اسم العائلة")
    email = forms.EmailField(required=False, label="البريد الإلكتروني")
    phone = forms.CharField(max_length=20, required=False, label="رقم الهاتف")
    national_id = forms.CharField(max_length=50, required=False, label="الرقم الوطني")
    address = forms.CharField(
        required=False, widget=forms.Textarea(attrs={"rows": 3}), label="العنوان"
    )

    def __init__(self, *args, parent=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.parent = parent

        if parent and not self.is_bound:
            self.initial.update(
                {
                    "first_name": parent.user.first_name,
                    "last_name": parent.user.last_name,
                    "email": parent.user.email,
                    "phone": parent.user.phone,
                    "national_id": parent.national_id,
                    "address": parent.address,
                }
            )

    @transaction.atomic
    def save(self):
        parent = self.parent
        user = parent.user

        user.first_name = self.cleaned_data["first_name"]
        user.last_name = self.cleaned_data["last_name"]
        user.email = self.cleaned_data.get("email", "")
        user.phone = self.cleaned_data.get("phone", "")
        user.save()

        parent.national_id = self.cleaned_data.get("national_id", "")
        parent.address = self.cleaned_data.get("address", "")
        parent.save()

        return parent


class ClassRoomForm(forms.ModelForm):
    class Meta:
        model = ClassRoom
        fields = ["name", "grade_level", "description"]
        labels = {
            "name": "اسم الصف",
            "grade_level": "المستوى الدراسي",
            "description": "الوصف",
        }
        widgets = {
            "description": forms.Textarea(attrs={"rows": 3}),
        }


class SectionForm(forms.ModelForm):
    class Meta:
        model = Section
        fields = ["classroom", "name"]
        labels = {
            "classroom": "الصف",
            "name": "اسم الشعبة",
        }


class SubjectForm(forms.ModelForm):
    class Meta:
        model = Subject
        fields = ["name", "code", "description"]
        labels = {
            "name": "اسم المادة",
            "code": "رمز المادة",
            "description": "الوصف",
        }
        widgets = {
            "description": forms.Textarea(attrs={"rows": 3}),
        }


class AcademicYearForm(forms.ModelForm):
    class Meta:
        model = AcademicYear
        fields = ["name", "start_date", "end_date", "is_active"]
        labels = {
            "name": "اسم السنة الدراسية",
            "start_date": "تاريخ البداية",
            "end_date": "تاريخ النهاية",
            "is_active": "السنة النشطة",
        }
        widgets = {
            "start_date": forms.DateInput(attrs={"type": "date"}),
            "end_date": forms.DateInput(attrs={"type": "date"}),
        }

    def clean(self):
        cleaned_data = super().clean()
        start_date = cleaned_data.get("start_date")
        end_date = cleaned_data.get("end_date")

        if start_date and end_date and end_date <= start_date:
            self.add_error("end_date", "تاريخ النهاية يجب أن يكون بعد تاريخ البداية.")

        return cleaned_data


class TeachingAssignmentForm(forms.ModelForm):
    class Meta:
        model = TeachingAssignment
        fields = ["teacher", "classroom", "section", "subject", "is_active"]
        labels = {
            "teacher": "المعلم",
            "classroom": "الصف",
            "section": "الشعبة",
            "subject": "المادة",
            "is_active": "فعال",
        }
        error_messages = {
            NON_FIELD_ERRORS: {
                "unique_together": "يوجد إسناد تدريسي بنفس المعلم والصف والشعبة والمادة.",
            },
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["teacher"].queryset = TeacherProfile.objects.select_related(
            "user"
        ).order_by("user__first_name", "user__last_name", "employee_code")
        self.fields["classroom"].queryset = ClassRoom.objects.order_by("name")
        self.fields["section"].queryset = Section.objects.select_related(
            "classroom"
        ).order_by("classroom__name", "name")
        self.fields["subject"].queryset = Subject.objects.order_by("name")

    def clean(self):
        cleaned_data = super().clean()

        classroom = cleaned_data.get("classroom")
        section = cleaned_data.get("section")

        if classroom and section and section.classroom_id != classroom.id:
            self.add_error("section", "هذه الشعبة لا تتبع الصف المختار.")

        return cleaned_data


class FeeInvoiceForm(forms.ModelForm):
    class Meta:
        model = FeeInvoice
        fields = [
            "student",
            "title",
            "description",
            "amount",
            "currency",
            "due_date",
            "status",
        ]
        labels = {
            "student": "الطالب",
            "title": "عنوان الفاتورة",
            "description": "الوصف",
            "amount": "المبلغ",
            "currency": "العملة",
            "due_date": "تاريخ الاستحقاق",
            "status": "الحالة",
        }
        widgets = {
            "description": forms.Textarea(attrs={"rows": 3}),
            "due_date": forms.DateInput(attrs={"type": "date"}),
            "amount": forms.NumberInput(attrs={"min": "0.01", "step": "0.01"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["student"].queryset = StudentProfile.objects.select_related(
            "user", "classroom", "section"
        ).order_by("student_code")

    def clean_amount(self):
        amount = self.cleaned_data["amount"]

        if amount <= 0:
            raise forms.ValidationError("يجب أن يكون المبلغ أكبر من صفر.")

        return amount

    def clean_currency(self):
        currency = self.cleaned_data["currency"].strip().lower()

        if not currency:
            raise forms.ValidationError("العملة مطلوبة.")

        return currency


class ScheduleForm(forms.ModelForm):
    class Meta:
        model = Schedule
        fields = [
            "teacher",
            "classroom",
            "section",
            "subject",
            "day_of_week",
            "start_time",
            "end_time",
            "room_name",
        ]
        labels = {
            "teacher": "المعلم",
            "classroom": "الصف",
            "section": "الشعبة",
            "subject": "المادة",
            "day_of_week": "اليوم",
            "start_time": "وقت البداية",
            "end_time": "وقت النهاية",
            "room_name": "الغرفة",
        }
        widgets = {
            "start_time": forms.TimeInput(attrs={"type": "time"}),
            "end_time": forms.TimeInput(attrs={"type": "time"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["teacher"].queryset = TeacherProfile.objects.select_related(
            "user"
        ).order_by("user__first_name", "user__last_name", "employee_code")
        self.fields["classroom"].queryset = ClassRoom.objects.order_by("name")
        self.fields["section"].queryset = Section.objects.select_related(
            "classroom"
        ).order_by("classroom__name", "name")
        self.fields["subject"].queryset = Subject.objects.order_by("name")
        self.fields["day_of_week"].choices = SCHEDULE_DAY_CHOICES

    def clean(self):
        cleaned_data = super().clean()

        classroom = cleaned_data.get("classroom")
        section = cleaned_data.get("section")
        start_time = cleaned_data.get("start_time")
        end_time = cleaned_data.get("end_time")

        if classroom and section and section.classroom_id != classroom.id:
            self.add_error("section", "هذه الشعبة لا تتبع الصف المختار.")

        if start_time and end_time and end_time <= start_time:
            self.add_error("end_time", "وقت النهاية يجب أن يكون بعد وقت البداية.")

        return cleaned_data


class AttendanceForm(forms.ModelForm):
    class Meta:
        model = Attendance
        fields = ["student", "teacher", "subject", "date", "status", "note"]
        labels = {
            "student": "الطالب",
            "teacher": "المعلم",
            "subject": "المادة",
            "date": "التاريخ",
            "status": "الحالة",
            "note": "ملاحظة",
        }
        widgets = {
            "date": forms.DateInput(attrs={"type": "date"}),
            "note": forms.Textarea(attrs={"rows": 3}),
        }
        error_messages = {
            NON_FIELD_ERRORS: {
                "unique_together": "يوجد سجل حضور لهذا الطالب في نفس المادة والتاريخ.",
            },
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["student"].queryset = StudentProfile.objects.select_related(
            "user", "classroom", "section"
        ).order_by("student_code")
        self.fields["teacher"].queryset = TeacherProfile.objects.select_related(
            "user"
        ).order_by("user__first_name", "user__last_name", "employee_code")
        self.fields["subject"].queryset = Subject.objects.order_by("name")
        self.fields["status"].choices = ATTENDANCE_STATUS_CHOICES


class GradeForm(forms.ModelForm):
    class Meta:
        model = Grade
        fields = [
            "student",
            "teacher",
            "subject",
            "title",
            "score",
            "max_score",
            "note",
            "date",
        ]
        labels = {
            "student": "الطالب",
            "teacher": "المعلم",
            "subject": "المادة",
            "title": "عنوان الدرجة",
            "score": "الدرجة",
            "max_score": "الدرجة العظمى",
            "note": "ملاحظة",
            "date": "التاريخ",
        }
        widgets = {
            "date": forms.DateInput(attrs={"type": "date"}),
            "score": forms.NumberInput(attrs={"min": "0", "step": "0.01"}),
            "max_score": forms.NumberInput(attrs={"min": "0.01", "step": "0.01"}),
            "note": forms.Textarea(attrs={"rows": 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["student"].queryset = StudentProfile.objects.select_related(
            "user", "classroom", "section"
        ).order_by("student_code")
        self.fields["teacher"].queryset = TeacherProfile.objects.select_related(
            "user"
        ).order_by("user__first_name", "user__last_name", "employee_code")
        self.fields["subject"].queryset = Subject.objects.order_by("name")

    def clean(self):
        cleaned_data = super().clean()

        score = cleaned_data.get("score")
        max_score = cleaned_data.get("max_score")

        if score is not None and score < 0:
            self.add_error("score", "الدرجة لا يمكن أن تكون سالبة.")

        if max_score is not None and max_score <= 0:
            self.add_error("max_score", "الدرجة العظمى يجب أن تكون أكبر من صفر.")

        if score is not None and max_score is not None and score > max_score:
            self.add_error("score", "الدرجة لا يمكن أن تتجاوز الدرجة العظمى.")

        return cleaned_data


class AssignmentForm(forms.ModelForm):
    class Meta:
        model = Assignment
        fields = [
            "teacher",
            "classroom",
            "section",
            "subject",
            "title",
            "description",
            "due_date",
        ]
        labels = {
            "teacher": "المعلم",
            "classroom": "الصف",
            "section": "الشعبة",
            "subject": "المادة",
            "title": "عنوان الواجب",
            "description": "الوصف",
            "due_date": "تاريخ التسليم",
        }
        widgets = {
            "description": forms.Textarea(attrs={"rows": 3}),
            "due_date": forms.DateInput(attrs={"type": "date"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["teacher"].queryset = TeacherProfile.objects.select_related(
            "user"
        ).order_by("user__first_name", "user__last_name", "employee_code")
        self.fields["classroom"].queryset = ClassRoom.objects.order_by("name")
        self.fields["section"].queryset = Section.objects.select_related(
            "classroom"
        ).order_by("classroom__name", "name")
        self.fields["subject"].queryset = Subject.objects.order_by("name")

    def clean(self):
        cleaned_data = super().clean()

        classroom = cleaned_data.get("classroom")
        section = cleaned_data.get("section")

        if classroom and section and section.classroom_id != classroom.id:
            self.add_error("section", "هذه الشعبة لا تتبع الصف المختار.")

        return cleaned_data


class AssignmentSubmissionReviewForm(forms.ModelForm):
    class Meta:
        model = AssignmentSubmission
        fields = ["status", "teacher_note", "grade"]
        labels = {
            "status": "الحالة",
            "teacher_note": "ملاحظة المراجعة",
            "grade": "درجة المراجعة",
        }
        widgets = {
            "teacher_note": forms.Textarea(attrs={"rows": 4}),
            "grade": forms.NumberInput(attrs={"min": "0", "step": "0.01"}),
        }

    def clean_grade(self):
        grade = self.cleaned_data.get("grade")

        if grade is not None and grade < 0:
            raise forms.ValidationError("الدرجة لا يمكن أن تكون سالبة.")

        return grade


class TeacherUploadedFileForm(forms.ModelForm):
    class Meta:
        model = TeacherUploadedFile
        fields = [
            "teacher",
            "assignment",
            "classroom",
            "section",
            "subject",
            "title",
            "file",
            "file_type",
        ]
        labels = {
            "teacher": "المعلم",
            "assignment": "الواجب",
            "classroom": "الصف",
            "section": "الشعبة",
            "subject": "المادة",
            "title": "عنوان الملف",
            "file": "الملف",
            "file_type": "نوع الملف",
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["teacher"].queryset = TeacherProfile.objects.select_related(
            "user"
        ).order_by("user__first_name", "user__last_name", "employee_code")
        self.fields["assignment"].queryset = Assignment.objects.select_related(
            "classroom", "section", "subject", "teacher__user"
        ).order_by("-created_at")
        self.fields["assignment"].required = False
        self.fields["classroom"].queryset = ClassRoom.objects.order_by("name")
        self.fields["section"].queryset = Section.objects.select_related(
            "classroom"
        ).order_by("classroom__name", "name")
        self.fields["subject"].queryset = Subject.objects.order_by("name")
        self.fields["file_type"].choices = FILE_TYPE_CHOICES

    def clean(self):
        cleaned_data = super().clean()

        classroom = cleaned_data.get("classroom")
        section = cleaned_data.get("section")
        subject = cleaned_data.get("subject")
        teacher = cleaned_data.get("teacher")
        assignment = cleaned_data.get("assignment")

        if classroom and section and section.classroom_id != classroom.id:
            self.add_error("section", "هذه الشعبة لا تتبع الصف المختار.")

        if assignment:
            if classroom and assignment.classroom_id != classroom.id:
                self.add_error("assignment", "الواجب المختار لا يتبع الصف المحدد.")
            if section and assignment.section_id != section.id:
                self.add_error("assignment", "الواجب المختار لا يتبع الشعبة المحددة.")
            if subject and assignment.subject_id != subject.id:
                self.add_error("assignment", "الواجب المختار لا يتبع المادة المحددة.")
            if teacher and assignment.teacher_id != teacher.id:
                self.add_error("assignment", "الواجب المختار لا يتبع المعلم المحدد.")

        return cleaned_data


class AnnouncementForm(forms.ModelForm):
    class Meta:
        model = Announcement
        fields = ["teacher", "classroom", "section", "title", "message"]
        labels = {
            "teacher": "المعلم",
            "classroom": "الصف",
            "section": "الشعبة",
            "title": "عنوان الإعلان",
            "message": "نص الإعلان",
        }
        widgets = {
            "message": forms.Textarea(attrs={"rows": 4}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["teacher"].queryset = TeacherProfile.objects.select_related(
            "user"
        ).order_by("user__first_name", "user__last_name", "employee_code")
        self.fields["teacher"].required = False
        self.fields["classroom"].queryset = ClassRoom.objects.order_by("name")
        self.fields["section"].queryset = Section.objects.select_related(
            "classroom"
        ).order_by("classroom__name", "name")

    def clean(self):
        cleaned_data = super().clean()

        classroom = cleaned_data.get("classroom")
        section = cleaned_data.get("section")

        if classroom and section and section.classroom_id != classroom.id:
            self.add_error("section", "هذه الشعبة لا تتبع الصف المختار.")

        return cleaned_data


class NotificationReminderForm(forms.Form):
    invoice_days = forms.IntegerField(
        min_value=0,
        label="أيام تذكير الفواتير",
        help_text="الفواتير غير المدفوعة المستحقة حتى هذا العدد من الأيام القادمة.",
    )
    assignment_days = forms.IntegerField(
        min_value=0,
        label="أيام تذكير الواجبات",
        help_text="الواجبات المستحقة حتى هذا العدد من الأيام القادمة.",
    )
    absence_window_days = forms.IntegerField(
        min_value=1,
        label="نافذة الغياب بالأيام",
        help_text="عدد الأيام السابقة المستخدمة لحساب الغياب المتكرر.",
    )
    absence_threshold = forms.IntegerField(
        min_value=1,
        label="حد الغياب المتكرر",
        help_text="يرسل التنبيه عندما يصل الطالب إلى هذا العدد من الغيابات.",
    )


class NotificationPreferenceForm(forms.ModelForm):
    class Meta:
        model = NotificationPreference
        fields = [
            "push_enabled",
            "in_app_enabled",
            "general_enabled",
            "grade_enabled",
            "attendance_enabled",
            "assignment_enabled",
            "announcement_enabled",
            "invoice_enabled",
            "payment_enabled",
            "message_enabled",
            "quiet_hours_enabled",
            "quiet_start",
            "quiet_end",
            "timezone",
            "language",
        ]
        labels = {
            "push_enabled": "تفعيل Push",
            "in_app_enabled": "تفعيل إشعارات داخل التطبيق",
            "general_enabled": "الإشعارات العامة",
            "grade_enabled": "الدرجات",
            "attendance_enabled": "الحضور",
            "assignment_enabled": "الواجبات",
            "announcement_enabled": "الإعلانات",
            "invoice_enabled": "الفواتير",
            "payment_enabled": "المدفوعات",
            "message_enabled": "الشات",
            "quiet_hours_enabled": "تفعيل Quiet hours",
            "quiet_start": "بداية Quiet hours",
            "quiet_end": "نهاية Quiet hours",
            "timezone": "المنطقة الزمنية",
            "language": "لغة القوالب",
        }
        widgets = {
            "quiet_start": forms.TimeInput(attrs={"type": "time"}),
            "quiet_end": forms.TimeInput(attrs={"type": "time"}),
        }

    def clean(self):
        cleaned_data = super().clean()

        quiet_hours_enabled = cleaned_data.get("quiet_hours_enabled")
        quiet_start = cleaned_data.get("quiet_start")
        quiet_end = cleaned_data.get("quiet_end")

        if quiet_hours_enabled and (not quiet_start or not quiet_end):
            raise forms.ValidationError(
                "عند تفعيل Quiet hours يجب تحديد وقت البداية والنهاية."
            )

        return cleaned_data


class NotificationTemplateForm(forms.ModelForm):
    class Meta:
        model = NotificationTemplate
        fields = [
            "notification_type",
            "title_template",
            "message_template",
            "is_active",
        ]
        labels = {
            "notification_type": "نوع الإشعار",
            "title_template": "قالب العنوان",
            "message_template": "قالب الرسالة",
            "is_active": "القالب فعال",
        }
        widgets = {
            "message_template": forms.Textarea(attrs={"rows": 5}),
        }

    def clean_title_template(self):
        title_template = self.cleaned_data["title_template"].strip()
        if not title_template:
            raise forms.ValidationError("قالب العنوان مطلوب.")
        return title_template

    def clean_message_template(self):
        message_template = self.cleaned_data["message_template"].strip()
        if not message_template:
            raise forms.ValidationError("قالب الرسالة مطلوب.")
        return message_template

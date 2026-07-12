from pathlib import Path
from datetime import timedelta
import importlib.util
import mimetypes

from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import user_passes_test
from django.http import FileResponse, Http404
from django.shortcuts import render
from django.contrib import messages
from django.shortcuts import redirect
from django.urls import reverse
from django.db.models import Q
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.utils.dateparse import parse_date
from django.views.decorators.clickjacking import xframe_options_sameorigin
from django.views.decorators.http import require_POST
from .forms import StudentCreateForm, StudentUpdateForm

from accounts.models import (
    ParentProfile,
    ParentStudentLink,
    StudentProfile,
    TeacherProfile,
    ParentLinkingCode,
)
from academics.models import (
    AcademicYear,
    Announcement,
    Assignment,
    Attendance,
    ClassRoom,
    Grade,
    Schedule,
    Subject,
    Section,
    AssignmentSubmission,
    PromotionRun,
    StudentYearResult,
    SubjectYearResult,
    TeacherUploadedFile,
    TeachingAssignment,
)
from academics.services import calculate_promotion_results
from finance.models import FeeInvoice, Payment, Receipt
from notifications.models import (
    Notification,
    NotificationPreference,
    NotificationTemplate,
    PushDelivery,
    PushDevice,
)
from notifications.services import notify_student_and_parents, send_fcm_message
from notifications.reminders import NotificationReminderRunner
from accounts.models import TeacherProfile
from .forms import (
    ATTENDANCE_STATUS_CHOICES,
    AcademicYearForm,
    AnnouncementForm,
    AssignmentForm,
    AssignmentSubmissionReviewForm,
    AttendanceForm,
    ClassRoomForm,
    FILE_TYPE_CHOICES,
    FeeInvoiceForm,
    GradeForm,
    NotificationBroadcastForm,
    NotificationPreferenceForm,
    NotificationReminderForm,
    NotificationTemplateForm,
    ParentUpdateForm,
    ScheduleForm,
    SCHEDULE_DAY_CHOICES,
    SectionForm,
    StudentCreateForm,
    StudentUpdateForm,
    SubjectForm,
    TeacherUploadedFileForm,
    TeachingAssignmentForm,
    TeacherCreateForm,
    TeacherUpdateForm,
)


def is_admin_user(user):
    return user.is_authenticated and (user.is_superuser or user.role == "ADMIN")


@user_passes_test(is_admin_user, login_url="/admin/login/")
def dashboard_home(request):
    context = {
        "students_count": StudentProfile.objects.count(),
        "parents_count": ParentProfile.objects.count(),
        "teachers_count": TeacherProfile.objects.count(),
        "classrooms_count": ClassRoom.objects.count(),
        "subjects_count": Subject.objects.count(),
        "attendance_count": Attendance.objects.count(),
        "assignments_count": Assignment.objects.count(),
        "invoices_count": FeeInvoice.objects.count(),
        "paid_invoices_count": FeeInvoice.objects.filter(
            status=FeeInvoice.Status.PAID
        ).count(),
        "payments_count": Payment.objects.filter(status=Payment.Status.PAID).count(),
        "receipts_count": Receipt.objects.count(),
    }

    return render(request, "dashboard/home.html", context)


@user_passes_test(is_admin_user, login_url="/admin/login/")
def student_create(request):
    if request.method == "POST":
        form = StudentCreateForm(request.POST)

        if form.is_valid():
            student, linking_code = form.save()

            messages.success(
                request,
                (
                    f"تم إنشاء الطالب {student} بنجاح. "
                    f"كود ربط ولي الأمر: {linking_code.code}"
                ),
            )

            return redirect("dashboard:student-create")
    else:
        form = StudentCreateForm()

    return render(request, "dashboard/student_create.html", {"form": form})


@user_passes_test(is_admin_user, login_url="/admin/login/")
def student_list(request):
    query = request.GET.get("q", "").strip()

    students = StudentProfile.objects.select_related(
        "user",
        "classroom",
        "section",
    )

    if query:
        students = students.filter(
            Q(student_code__icontains=query)
            | Q(user__username__icontains=query)
            | Q(user__first_name__icontains=query)
            | Q(user__last_name__icontains=query)
            | Q(user__email__icontains=query)
        )

    students = students.order_by("student_code")

    return render(
        request,
        "dashboard/student_list.html",
        {
            "students": students,
            "query": query,
        },
    )


@user_passes_test(is_admin_user, login_url="/admin/login/")
def student_update(request, student_id):
    student = get_object_or_404(
        StudentProfile.objects.select_related(
            "user",
            "classroom",
            "section",
        ),
        id=student_id,
    )

    if request.method == "POST":
        form = StudentUpdateForm(request.POST, student=student)

        if form.is_valid():
            form.save()

            messages.success(request, "تم تحديث بيانات الطالب بنجاح.")

            return redirect("dashboard:student-list")
    else:
        form = StudentUpdateForm(student=student)

    return render(
        request,
        "dashboard/student_update.html",
        {
            "form": form,
            "student": student,
        },
    )


@user_passes_test(is_admin_user, login_url="/admin/login/")
def student_delete_confirm(request, student_id):
    student = get_object_or_404(
        StudentProfile.objects.select_related("user"), id=student_id
    )

    return render(
        request, "dashboard/student_delete_confirm.html", {"student": student}
    )


@require_POST
@user_passes_test(is_admin_user, login_url="/admin/login/")
def student_delete(request, student_id):
    student = get_object_or_404(
        StudentProfile.objects.select_related("user"), id=student_id
    )

    user = student.user
    student_name = user.get_full_name() or user.username

    user.delete()

    messages.success(request, f"تم حذف الطالب {student_name} بنجاح.")

    return redirect("dashboard:student-list")


@require_POST
@user_passes_test(is_admin_user, login_url="/admin/login/")
def regenerate_parent_code(request, student_id):
    student = get_object_or_404(StudentProfile, id=student_id)

    ParentLinkingCode.objects.filter(student=student, is_used=False).delete()

    linking_code = ParentLinkingCode.objects.create(student=student)

    messages.success(request, f"تم إنشاء كود جديد: {linking_code.code}")

    return redirect("dashboard:student-list")


@user_passes_test(is_admin_user, login_url="/admin/login/")
def teacher_list(request):
    query = request.GET.get("q", "").strip()

    teachers = TeacherProfile.objects.select_related("user")

    if query:
        teachers = teachers.filter(
            Q(employee_code__icontains=query)
            | Q(user__username__icontains=query)
            | Q(user__first_name__icontains=query)
            | Q(user__last_name__icontains=query)
            | Q(specialization__icontains=query)
        )

    return render(
        request,
        "dashboard/teacher_list.html",
        {
            "teachers": teachers.order_by("employee_code"),
            "query": query,
        },
    )


@user_passes_test(is_admin_user, login_url="/admin/login/")
def teacher_create(request):
    if request.method == "POST":
        form = TeacherCreateForm(request.POST)

        if form.is_valid():
            teacher = form.save()

            messages.success(request, f"تم إنشاء المعلم {teacher} بنجاح.")

            return redirect("dashboard:teacher-list")
    else:
        form = TeacherCreateForm()

    return render(request, "dashboard/teacher_create.html", {"form": form})


@user_passes_test(is_admin_user, login_url="/admin/login/")
def teacher_update(request, teacher_id):
    teacher = get_object_or_404(
        TeacherProfile.objects.select_related("user"), id=teacher_id
    )

    if request.method == "POST":
        form = TeacherUpdateForm(request.POST, teacher=teacher)

        if form.is_valid():
            form.save()
            messages.success(request, "تم تحديث بيانات المعلم بنجاح.")
            return redirect("dashboard:teacher-list")
    else:
        form = TeacherUpdateForm(teacher=teacher)

    return render(
        request,
        "dashboard/teacher_update.html",
        {
            "form": form,
            "teacher": teacher,
        },
    )


@user_passes_test(is_admin_user, login_url="/admin/login/")
def parent_list(request):
    query = request.GET.get("q", "").strip()

    parents = ParentProfile.objects.select_related("user").prefetch_related(
        "student_links__student__user"
    )

    if query:
        parents = parents.filter(
            Q(user__username__icontains=query)
            | Q(user__first_name__icontains=query)
            | Q(user__last_name__icontains=query)
            | Q(user__email__icontains=query)
            | Q(user__phone__icontains=query)
            | Q(national_id__icontains=query)
        ).distinct()

    return render(
        request,
        "dashboard/parent_list.html",
        {
            "parents": parents.order_by("user__first_name"),
            "query": query,
        },
    )


@user_passes_test(is_admin_user, login_url="/admin/login/")
def parent_update(request, parent_id):
    parent = get_object_or_404(
        ParentProfile.objects.select_related("user"), id=parent_id
    )

    if request.method == "POST":
        form = ParentUpdateForm(request.POST, parent=parent)

        if form.is_valid():
            form.save()

            messages.success(request, "تم تحديث بيانات ولي الأمر بنجاح.")

            return redirect("dashboard:parent-list")
    else:
        form = ParentUpdateForm(parent=parent)

    return render(
        request,
        "dashboard/parent_update.html",
        {
            "form": form,
            "parent": parent,
        },
    )


@user_passes_test(is_admin_user, login_url="/admin/login/")
def parent_delete_confirm(request, parent_id):
    parent = get_object_or_404(
        ParentProfile.objects.select_related("user"), id=parent_id
    )

    return render(request, "dashboard/parent_delete_confirm.html", {"parent": parent})


@require_POST
@user_passes_test(is_admin_user, login_url="/admin/login/")
def parent_delete(request, parent_id):
    parent = get_object_or_404(
        ParentProfile.objects.select_related("user"), id=parent_id
    )

    user = parent.user
    parent_name = user.get_full_name() or user.username

    user.delete()

    messages.success(request, f"تم حذف ولي الأمر {parent_name} بنجاح.")

    return redirect("dashboard:parent-list")


@user_passes_test(is_admin_user, login_url="/admin/login/")
def classroom_list(request):
    classrooms = ClassRoom.objects.prefetch_related("sections").order_by("name")

    return render(request, "dashboard/classroom_list.html", {"classrooms": classrooms})


@user_passes_test(is_admin_user, login_url="/admin/login/")
def classroom_create(request):
    if request.method == "POST":
        form = ClassRoomForm(request.POST)

        if form.is_valid():
            form.save()
            messages.success(request, "تم إنشاء الصف بنجاح.")
            return redirect("dashboard:classroom-list")
    else:
        form = ClassRoomForm()

    return render(
        request,
        "dashboard/classroom_form.html",
        {
            "form": form,
            "page_title": "إضافة صف",
            "button_text": "إنشاء الصف",
        },
    )


@user_passes_test(is_admin_user, login_url="/admin/login/")
def classroom_update(request, classroom_id):
    classroom = get_object_or_404(ClassRoom, id=classroom_id)

    if request.method == "POST":
        form = ClassRoomForm(request.POST, instance=classroom)

        if form.is_valid():
            form.save()
            messages.success(request, "تم تحديث الصف بنجاح.")
            return redirect("dashboard:classroom-list")
    else:
        form = ClassRoomForm(instance=classroom)

    return render(
        request,
        "dashboard/classroom_form.html",
        {
            "form": form,
            "page_title": "تعديل الصف",
            "button_text": "حفظ التعديلات",
        },
    )


@require_POST
@user_passes_test(is_admin_user, login_url="/admin/login/")
def classroom_delete(request, classroom_id):
    classroom = get_object_or_404(ClassRoom, id=classroom_id)

    classroom.delete()

    messages.success(request, "تم حذف الصف بنجاح.")
    return redirect("dashboard:classroom-list")


@user_passes_test(is_admin_user, login_url="/admin/login/")
def section_list(request):
    sections = Section.objects.select_related("classroom").order_by(
        "classroom__name", "name"
    )

    return render(request, "dashboard/section_list.html", {"sections": sections})


@user_passes_test(is_admin_user, login_url="/admin/login/")
def section_create(request):
    if request.method == "POST":
        form = SectionForm(request.POST)

        if form.is_valid():
            form.save()
            messages.success(request, "تم إنشاء الشعبة بنجاح.")
            return redirect("dashboard:section-list")
    else:
        form = SectionForm()

    return render(
        request,
        "dashboard/section_form.html",
        {
            "form": form,
            "page_title": "إضافة شعبة",
            "button_text": "إنشاء الشعبة",
        },
    )


@user_passes_test(is_admin_user, login_url="/admin/login/")
def section_update(request, section_id):
    section = get_object_or_404(Section, id=section_id)

    if request.method == "POST":
        form = SectionForm(request.POST, instance=section)

        if form.is_valid():
            form.save()
            messages.success(request, "تم تحديث الشعبة بنجاح.")
            return redirect("dashboard:section-list")
    else:
        form = SectionForm(instance=section)

    return render(
        request,
        "dashboard/section_form.html",
        {
            "form": form,
            "page_title": "تعديل الشعبة",
            "button_text": "حفظ التعديلات",
        },
    )


@require_POST
@user_passes_test(is_admin_user, login_url="/admin/login/")
def section_delete(request, section_id):
    section = get_object_or_404(Section, id=section_id)

    section.delete()

    messages.success(request, "تم حذف الشعبة بنجاح.")
    return redirect("dashboard:section-list")


@user_passes_test(is_admin_user, login_url="/admin/login/")
def subject_list(request):
    query = request.GET.get("q", "").strip()

    subjects = Subject.objects.all()

    if query:
        subjects = subjects.filter(Q(name__icontains=query) | Q(code__icontains=query))

    return render(
        request,
        "dashboard/subject_list.html",
        {
            "subjects": subjects.order_by("name"),
            "query": query,
        },
    )


@user_passes_test(is_admin_user, login_url="/admin/login/")
def subject_create(request):
    if request.method == "POST":
        form = SubjectForm(request.POST)

        if form.is_valid():
            form.save()
            messages.success(request, "تم إنشاء المادة بنجاح.")
            return redirect("dashboard:subject-list")
    else:
        form = SubjectForm()

    return render(
        request,
        "dashboard/subject_form.html",
        {
            "form": form,
            "page_title": "إضافة مادة",
            "button_text": "إنشاء المادة",
        },
    )


@user_passes_test(is_admin_user, login_url="/admin/login/")
def subject_update(request, subject_id):
    subject = get_object_or_404(Subject, id=subject_id)

    if request.method == "POST":
        form = SubjectForm(request.POST, instance=subject)

        if form.is_valid():
            form.save()
            messages.success(request, "تم تحديث المادة بنجاح.")
            return redirect("dashboard:subject-list")
    else:
        form = SubjectForm(instance=subject)

    return render(
        request,
        "dashboard/subject_form.html",
        {
            "form": form,
            "page_title": "تعديل المادة",
            "button_text": "حفظ التعديلات",
        },
    )


@require_POST
@user_passes_test(is_admin_user, login_url="/admin/login/")
def subject_delete(request, subject_id):
    subject = get_object_or_404(Subject, id=subject_id)

    subject.delete()

    messages.success(request, "تم حذف المادة بنجاح.")
    return redirect("dashboard:subject-list")


@user_passes_test(is_admin_user, login_url="/admin/login/")
def academic_year_list(request):
    academic_years = AcademicYear.objects.order_by("-start_date", "name")

    return render(
        request,
        "dashboard/academic_year_list.html",
        {"academic_years": academic_years},
    )


@user_passes_test(is_admin_user, login_url="/admin/login/")
def academic_year_create(request):
    if request.method == "POST":
        form = AcademicYearForm(request.POST)

        if form.is_valid():
            academic_year = form.save()

            if academic_year.is_active:
                AcademicYear.objects.exclude(id=academic_year.id).update(
                    is_active=False
                )

            messages.success(request, "تم إنشاء السنة الدراسية بنجاح.")
            return redirect("dashboard:academic-year-list")
    else:
        form = AcademicYearForm()

    return render(
        request,
        "dashboard/academic_year_form.html",
        {
            "form": form,
            "page_title": "إضافة سنة دراسية",
            "button_text": "إنشاء السنة",
        },
    )


@require_POST
@user_passes_test(is_admin_user, login_url="/admin/login/")
def academic_year_set_active(request, academic_year_id):
    academic_year = get_object_or_404(AcademicYear, id=academic_year_id)

    AcademicYear.objects.exclude(id=academic_year.id).update(is_active=False)
    academic_year.is_active = True
    academic_year.save(update_fields=["is_active"])

    messages.success(request, "تم تعيين السنة الدراسية كسنة نشطة.")
    return redirect("dashboard:academic-year-list")


@user_passes_test(is_admin_user, login_url="/admin/login/")
def promotion_results(request):
    academic_year_id = request.GET.get("academic_year", "").strip()
    status_filter = request.GET.get("status", "").strip()

    selected_academic_year = int(academic_year_id) if academic_year_id.isdigit() else None

    academic_years = AcademicYear.objects.order_by("-start_date", "name")
    active_year = academic_years.filter(is_active=True).first()

    if not selected_academic_year and active_year:
        selected_academic_year = active_year.id

    results = StudentYearResult.objects.select_related(
        "student",
        "student__user",
        "student__classroom",
        "student__section",
        "academic_year",
    )

    if selected_academic_year:
        results = results.filter(academic_year_id=selected_academic_year)
    else:
        results = results.none()

    valid_statuses = {choice[0] for choice in StudentYearResult.Status.choices}
    if status_filter in valid_statuses:
        results = results.filter(status=status_filter)

    status_names = dict(StudentYearResult.Status.choices)
    results = list(results.order_by("student__student_code"))
    for result in results:
        result.status_name = status_names.get(result.status, result.status)

    latest_run = None
    if selected_academic_year:
        latest_run = PromotionRun.objects.filter(
            academic_year_id=selected_academic_year
        ).first()

    return render(
        request,
        "dashboard/promotion_results.html",
        {
            "academic_years": academic_years,
            "results": results,
            "latest_run": latest_run,
            "status_choices": StudentYearResult.Status.choices,
            "selected_academic_year": selected_academic_year,
            "selected_status": status_filter,
        },
    )


@require_POST
@user_passes_test(is_admin_user, login_url="/admin/login/")
def promotion_calculate(request):
    academic_year_id = request.POST.get("academic_year", "").strip()

    if not academic_year_id.isdigit():
        messages.error(request, "اختر سنة دراسية صالحة قبل حساب النتائج.")
        return redirect("dashboard:promotion-results")

    academic_year = get_object_or_404(AcademicYear, id=int(academic_year_id))
    promotion_run = calculate_promotion_results(academic_year, created_by=request.user)

    messages.success(
        request,
        (
            "تم حساب النتائج. "
            f"المجموع: {promotion_run.total_students}، "
            f"مترفع: {promotion_run.promoted_count}، "
            f"راسب: {promotion_run.failed_count}، "
            f"بحاجة لمراجعة: {promotion_run.needs_review_count}."
        ),
    )
    return redirect(f"{reverse('dashboard:promotion-results')}?academic_year={academic_year.id}")


@require_POST
@user_passes_test(is_admin_user, login_url="/admin/login/")
def promotion_publish(request):
    academic_year_id = request.POST.get("academic_year", "").strip()

    if not academic_year_id.isdigit():
        messages.error(request, "اختر سنة دراسية صالحة قبل نشر النتائج.")
        return redirect("dashboard:promotion-results")

    academic_year = get_object_or_404(AcademicYear, id=int(academic_year_id))
    results = StudentYearResult.objects.select_related(
        "student",
        "student__user",
    ).filter(academic_year=academic_year)

    published_count = 0
    now = timezone.now()

    for result in results:
        if not result.is_published:
            result.is_published = True
            result.published_at = now
            result.save(update_fields=["is_published", "published_at"])
            published_count += 1

            notify_student_and_parents(
                student=result.student,
                notification_type=Notification.Type.GENERAL,
                title="Year result published",
                message=f"Your year result for {academic_year.name} is now available.",
                related_object_type="StudentYearResult",
                related_object_id=result.id,
            )

    messages.success(
        request,
        f"تم نشر نتائج {published_count} طالب وإرسال الإشعارات.",
    )
    return redirect(f"{reverse('dashboard:promotion-results')}?academic_year={academic_year.id}")


@user_passes_test(is_admin_user, login_url="/admin/login/")
def promotion_result_detail(request, result_id):
    result = get_object_or_404(
        StudentYearResult.objects.select_related(
            "student",
            "student__user",
            "student__classroom",
            "student__section",
            "academic_year",
        ),
        id=result_id,
    )

    subject_results = SubjectYearResult.objects.select_related("subject").filter(
        student=result.student,
        academic_year=result.academic_year,
    )

    status_names = dict(StudentYearResult.Status.choices)
    result.status_name = status_names.get(result.status, result.status)

    return render(
        request,
        "dashboard/promotion_result_detail.html",
        {
            "result": result,
            "subject_results": subject_results,
        },
    )


@user_passes_test(is_admin_user, login_url="/admin/login/")
def teaching_assignment_list(request):
    teaching_assignments = TeachingAssignment.objects.select_related(
        "teacher__user",
        "classroom",
        "section",
        "subject",
    ).order_by(
        "teacher__user__first_name",
        "teacher__user__last_name",
        "classroom__name",
        "section__name",
        "subject__name",
    )

    return render(
        request,
        "dashboard/teaching_assignment_list.html",
        {"teaching_assignments": teaching_assignments},
    )


@user_passes_test(is_admin_user, login_url="/admin/login/")
def teaching_assignment_create(request):
    if request.method == "POST":
        form = TeachingAssignmentForm(request.POST)

        if form.is_valid():
            form.save()
            messages.success(request, "تم إنشاء الإسناد التدريسي بنجاح.")
            return redirect("dashboard:teaching-assignment-list")
    else:
        form = TeachingAssignmentForm()

    return render(
        request,
        "dashboard/teaching_assignment_form.html",
        {
            "form": form,
            "page_title": "إضافة إسناد تدريسي",
            "button_text": "إنشاء الإسناد",
        },
    )


@user_passes_test(is_admin_user, login_url="/admin/login/")
def teaching_assignment_update(request, teaching_assignment_id):
    teaching_assignment = get_object_or_404(
        TeachingAssignment.objects.select_related(
            "teacher__user",
            "classroom",
            "section",
            "subject",
        ),
        id=teaching_assignment_id,
    )

    if request.method == "POST":
        form = TeachingAssignmentForm(request.POST, instance=teaching_assignment)

        if form.is_valid():
            form.save()
            messages.success(request, "تم تحديث الإسناد التدريسي بنجاح.")
            return redirect("dashboard:teaching-assignment-list")
    else:
        form = TeachingAssignmentForm(instance=teaching_assignment)

    return render(
        request,
        "dashboard/teaching_assignment_form.html",
        {
            "form": form,
            "page_title": "تعديل الإسناد التدريسي",
            "button_text": "حفظ التعديلات",
        },
    )


@require_POST
@user_passes_test(is_admin_user, login_url="/admin/login/")
def teaching_assignment_delete(request, teaching_assignment_id):
    teaching_assignment = get_object_or_404(
        TeachingAssignment, id=teaching_assignment_id
    )

    teaching_assignment.delete()

    messages.success(request, "تم حذف الإسناد التدريسي بنجاح.")
    return redirect("dashboard:teaching-assignment-list")


@user_passes_test(is_admin_user, login_url="/admin/login/")
def invoice_list(request):
    query = request.GET.get("q", "").strip()
    status_filter = request.GET.get("status", "").strip()

    invoices = FeeInvoice.objects.select_related(
        "student__user",
        "student__classroom",
        "student__section",
    )

    if query:
        invoices = invoices.filter(
            Q(title__icontains=query)
            | Q(description__icontains=query)
            | Q(student__student_code__icontains=query)
            | Q(student__user__username__icontains=query)
            | Q(student__user__first_name__icontains=query)
            | Q(student__user__last_name__icontains=query)
        )

    valid_statuses = {choice[0] for choice in FeeInvoice.Status.choices}
    if status_filter in valid_statuses:
        invoices = invoices.filter(status=status_filter)

    return render(
        request,
        "dashboard/invoice_list.html",
        {
            "invoices": invoices.order_by("-created_at"),
            "query": query,
            "status_filter": status_filter,
        },
    )


@user_passes_test(is_admin_user, login_url="/admin/login/")
def invoice_create(request):
    if request.method == "POST":
        form = FeeInvoiceForm(request.POST)

        if form.is_valid():
            form.save()
            messages.success(request, "تم إنشاء الفاتورة بنجاح.")
            return redirect("dashboard:invoice-list")
    else:
        form = FeeInvoiceForm()

    return render(
        request,
        "dashboard/invoice_form.html",
        {
            "form": form,
            "page_title": "إضافة فاتورة",
            "button_text": "إنشاء الفاتورة",
        },
    )


@user_passes_test(is_admin_user, login_url="/admin/login/")
def invoice_update(request, invoice_id):
    invoice = get_object_or_404(
        FeeInvoice.objects.select_related("student__user"),
        id=invoice_id,
    )

    if request.method == "POST":
        form = FeeInvoiceForm(request.POST, instance=invoice)

        if form.is_valid():
            form.save()
            messages.success(request, "تم تحديث الفاتورة بنجاح.")
            return redirect("dashboard:invoice-list")
    else:
        form = FeeInvoiceForm(instance=invoice)

    return render(
        request,
        "dashboard/invoice_form.html",
        {
            "form": form,
            "page_title": "تعديل الفاتورة",
            "button_text": "حفظ التعديلات",
        },
    )


@require_POST
@user_passes_test(is_admin_user, login_url="/admin/login/")
def invoice_delete(request, invoice_id):
    invoice = get_object_or_404(FeeInvoice, id=invoice_id)

    invoice.delete()

    messages.success(request, "تم حذف الفاتورة بنجاح.")
    return redirect("dashboard:invoice-list")


@user_passes_test(is_admin_user, login_url="/admin/login/")
def payment_list(request):
    query = request.GET.get("q", "").strip()
    status_filter = request.GET.get("status", "").strip()

    payments = Payment.objects.select_related(
        "invoice",
        "invoice__student__user",
        "parent__user",
        "receipt",
    )

    if query:
        payments = payments.filter(
            Q(invoice__title__icontains=query)
            | Q(invoice__student__student_code__icontains=query)
            | Q(invoice__student__user__username__icontains=query)
            | Q(invoice__student__user__first_name__icontains=query)
            | Q(invoice__student__user__last_name__icontains=query)
            | Q(parent__user__username__icontains=query)
            | Q(parent__user__first_name__icontains=query)
            | Q(parent__user__last_name__icontains=query)
            | Q(stripe_checkout_session_id__icontains=query)
            | Q(stripe_payment_intent_id__icontains=query)
        )

    valid_statuses = {choice[0] for choice in Payment.Status.choices}
    if status_filter in valid_statuses:
        payments = payments.filter(status=status_filter)

    return render(
        request,
        "dashboard/payment_list.html",
        {
            "payments": payments.order_by("-created_at"),
            "query": query,
            "status_filter": status_filter,
            "receipts_count": Receipt.objects.count(),
        },
    )


@user_passes_test(is_admin_user, login_url="/admin/login/")
def receipt_list(request):
    query = request.GET.get("q", "").strip()

    receipts = Receipt.objects.select_related(
        "payment",
        "payment__invoice",
        "payment__invoice__student__user",
        "payment__parent__user",
    )

    if query:
        receipts = receipts.filter(
            Q(receipt_number__icontains=query)
            | Q(payment__invoice__title__icontains=query)
            | Q(payment__invoice__student__student_code__icontains=query)
            | Q(payment__invoice__student__user__username__icontains=query)
            | Q(payment__invoice__student__user__first_name__icontains=query)
            | Q(payment__invoice__student__user__last_name__icontains=query)
            | Q(payment__parent__user__username__icontains=query)
            | Q(payment__parent__user__first_name__icontains=query)
            | Q(payment__parent__user__last_name__icontains=query)
            | Q(payment__stripe_checkout_session_id__icontains=query)
            | Q(payment__stripe_payment_intent_id__icontains=query)
        )

    return render(
        request,
        "dashboard/receipt_list.html",
        {
            "receipts": receipts.order_by("-issued_at"),
            "query": query,
        },
    )


@user_passes_test(is_admin_user, login_url="/admin/login/")
def receipt_detail(request, receipt_id):
    receipt = get_object_or_404(
        Receipt.objects.select_related(
            "payment",
            "payment__invoice",
            "payment__invoice__student__user",
            "payment__invoice__student__classroom",
            "payment__invoice__student__section",
            "payment__parent__user",
        ),
        id=receipt_id,
    )

    return render(
        request,
        "dashboard/receipt_detail.html",
        {"receipt": receipt},
    )


@user_passes_test(is_admin_user, login_url="/admin/login/")
def schedule_list(request):
    classroom_id = request.GET.get("classroom", "").strip()
    section_id = request.GET.get("section", "").strip()
    day_filter = request.GET.get("day", "").strip()
    teacher_id = request.GET.get("teacher", "").strip()
    selected_classroom = int(classroom_id) if classroom_id.isdigit() else None
    selected_section = int(section_id) if section_id.isdigit() else None
    selected_teacher = int(teacher_id) if teacher_id.isdigit() else None

    schedules = Schedule.objects.select_related(
        "teacher__user",
        "classroom",
        "section",
        "subject",
    )

    if selected_classroom:
        schedules = schedules.filter(classroom_id=selected_classroom)

    if selected_section:
        schedules = schedules.filter(section_id=selected_section)

    valid_days = {choice[0] for choice in SCHEDULE_DAY_CHOICES}
    if day_filter in valid_days:
        schedules = schedules.filter(day_of_week=day_filter)

    if selected_teacher:
        schedules = schedules.filter(teacher_id=selected_teacher)

    schedules = list(schedules.order_by("day_of_week", "start_time"))
    day_names = dict(SCHEDULE_DAY_CHOICES)
    for schedule in schedules:
        schedule.day_name = day_names.get(schedule.day_of_week, schedule.day_of_week)

    return render(
        request,
        "dashboard/schedule_list.html",
        {
            "schedules": schedules,
            "classrooms": ClassRoom.objects.order_by("name"),
            "sections": Section.objects.select_related("classroom").order_by(
                "classroom__name", "name"
            ),
            "teachers": TeacherProfile.objects.select_related("user").order_by(
                "user__first_name", "user__last_name", "employee_code"
            ),
            "day_choices": SCHEDULE_DAY_CHOICES,
            "selected_classroom": selected_classroom,
            "selected_section": selected_section,
            "selected_day": day_filter,
            "selected_teacher": selected_teacher,
        },
    )


@user_passes_test(is_admin_user, login_url="/admin/login/")
def schedule_create(request):
    if request.method == "POST":
        form = ScheduleForm(request.POST)

        if form.is_valid():
            form.save()
            messages.success(request, "تم إنشاء الجدول بنجاح.")
            return redirect("dashboard:schedule-list")
    else:
        form = ScheduleForm()

    return render(
        request,
        "dashboard/schedule_form.html",
        {
            "form": form,
            "page_title": "إضافة جدول",
            "button_text": "إنشاء الجدول",
        },
    )


@user_passes_test(is_admin_user, login_url="/admin/login/")
def schedule_update(request, schedule_id):
    schedule = get_object_or_404(
        Schedule.objects.select_related(
            "teacher__user",
            "classroom",
            "section",
            "subject",
        ),
        id=schedule_id,
    )

    if request.method == "POST":
        form = ScheduleForm(request.POST, instance=schedule)

        if form.is_valid():
            form.save()
            messages.success(request, "تم تحديث الجدول بنجاح.")
            return redirect("dashboard:schedule-list")
    else:
        form = ScheduleForm(instance=schedule)

    return render(
        request,
        "dashboard/schedule_form.html",
        {
            "form": form,
            "page_title": "تعديل الجدول",
            "button_text": "حفظ التعديلات",
        },
    )


@require_POST
@user_passes_test(is_admin_user, login_url="/admin/login/")
def schedule_delete(request, schedule_id):
    schedule = get_object_or_404(Schedule, id=schedule_id)

    schedule.delete()

    messages.success(request, "تم حذف الجدول بنجاح.")
    return redirect("dashboard:schedule-list")


@user_passes_test(is_admin_user, login_url="/admin/login/")
def attendance_list(request):
    student_id = request.GET.get("student", "").strip()
    classroom_id = request.GET.get("classroom", "").strip()
    subject_id = request.GET.get("subject", "").strip()
    date_filter = request.GET.get("date", "").strip()
    status_filter = request.GET.get("status", "").strip()

    selected_student = int(student_id) if student_id.isdigit() else None
    selected_classroom = int(classroom_id) if classroom_id.isdigit() else None
    selected_subject = int(subject_id) if subject_id.isdigit() else None

    attendance_records = Attendance.objects.select_related(
        "student__user",
        "student__classroom",
        "student__section",
        "teacher__user",
        "subject",
    )

    if selected_student:
        attendance_records = attendance_records.filter(student_id=selected_student)

    if selected_classroom:
        attendance_records = attendance_records.filter(
            student__classroom_id=selected_classroom
        )

    if selected_subject:
        attendance_records = attendance_records.filter(subject_id=selected_subject)

    parsed_date = parse_date(date_filter) if date_filter else None
    if parsed_date:
        attendance_records = attendance_records.filter(date=parsed_date)

    valid_statuses = {choice[0] for choice in ATTENDANCE_STATUS_CHOICES}
    if status_filter in valid_statuses:
        attendance_records = attendance_records.filter(status=status_filter)

    status_names = dict(ATTENDANCE_STATUS_CHOICES)
    attendance_records = list(attendance_records.order_by("-date", "student__student_code"))
    for attendance in attendance_records:
        attendance.status_name = status_names.get(attendance.status, attendance.status)

    return render(
        request,
        "dashboard/attendance_list.html",
        {
            "attendance_records": attendance_records,
            "students": StudentProfile.objects.select_related(
                "user", "classroom", "section"
            ).order_by("student_code"),
            "classrooms": ClassRoom.objects.order_by("name"),
            "subjects": Subject.objects.order_by("name"),
            "status_choices": ATTENDANCE_STATUS_CHOICES,
            "selected_student": selected_student,
            "selected_classroom": selected_classroom,
            "selected_subject": selected_subject,
            "selected_date": date_filter,
            "selected_status": status_filter,
        },
    )


@user_passes_test(is_admin_user, login_url="/admin/login/")
def attendance_create(request):
    if request.method == "POST":
        form = AttendanceForm(request.POST)

        if form.is_valid():
            form.save()
            messages.success(request, "تم إنشاء سجل الحضور بنجاح.")
            return redirect("dashboard:attendance-list")
    else:
        form = AttendanceForm()

    return render(
        request,
        "dashboard/attendance_form.html",
        {
            "form": form,
            "page_title": "إضافة سجل حضور",
            "button_text": "إنشاء سجل الحضور",
        },
    )


@user_passes_test(is_admin_user, login_url="/admin/login/")
def attendance_update(request, attendance_id):
    attendance = get_object_or_404(
        Attendance.objects.select_related(
            "student__user",
            "teacher__user",
            "subject",
        ),
        id=attendance_id,
    )

    if request.method == "POST":
        form = AttendanceForm(request.POST, instance=attendance)

        if form.is_valid():
            form.save()
            messages.success(request, "تم تحديث سجل الحضور بنجاح.")
            return redirect("dashboard:attendance-list")
    else:
        form = AttendanceForm(instance=attendance)

    return render(
        request,
        "dashboard/attendance_form.html",
        {
            "form": form,
            "page_title": "تعديل سجل حضور",
            "button_text": "حفظ التعديلات",
        },
    )


@require_POST
@user_passes_test(is_admin_user, login_url="/admin/login/")
def attendance_delete(request, attendance_id):
    attendance = get_object_or_404(Attendance, id=attendance_id)

    attendance.delete()

    messages.success(request, "تم حذف سجل الحضور بنجاح.")
    return redirect("dashboard:attendance-list")


@user_passes_test(is_admin_user, login_url="/admin/login/")
def grade_list(request):
    student_id = request.GET.get("student", "").strip()
    subject_id = request.GET.get("subject", "").strip()
    date_filter = request.GET.get("date", "").strip()

    selected_student = int(student_id) if student_id.isdigit() else None
    selected_subject = int(subject_id) if subject_id.isdigit() else None

    grades = Grade.objects.select_related(
        "student__user",
        "student__classroom",
        "student__section",
        "teacher__user",
        "subject",
    )

    if selected_student:
        grades = grades.filter(student_id=selected_student)

    if selected_subject:
        grades = grades.filter(subject_id=selected_subject)

    parsed_date = parse_date(date_filter) if date_filter else None
    if parsed_date:
        grades = grades.filter(date=parsed_date)

    return render(
        request,
        "dashboard/grade_list.html",
        {
            "grades": grades.order_by("-date", "student__student_code"),
            "students": StudentProfile.objects.select_related(
                "user", "classroom", "section"
            ).order_by("student_code"),
            "subjects": Subject.objects.order_by("name"),
            "selected_student": selected_student,
            "selected_subject": selected_subject,
            "selected_date": date_filter,
        },
    )


@user_passes_test(is_admin_user, login_url="/admin/login/")
def grade_create(request):
    if request.method == "POST":
        form = GradeForm(request.POST)

        if form.is_valid():
            form.save()
            messages.success(request, "تم إنشاء الدرجة بنجاح.")
            return redirect("dashboard:grade-list")
    else:
        form = GradeForm()

    return render(
        request,
        "dashboard/grade_form.html",
        {
            "form": form,
            "page_title": "إضافة درجة",
            "button_text": "إنشاء الدرجة",
        },
    )


@user_passes_test(is_admin_user, login_url="/admin/login/")
def grade_update(request, grade_id):
    grade = get_object_or_404(
        Grade.objects.select_related(
            "student__user",
            "teacher__user",
            "subject",
        ),
        id=grade_id,
    )

    if request.method == "POST":
        form = GradeForm(request.POST, instance=grade)

        if form.is_valid():
            form.save()
            messages.success(request, "تم تحديث الدرجة بنجاح.")
            return redirect("dashboard:grade-list")
    else:
        form = GradeForm(instance=grade)

    return render(
        request,
        "dashboard/grade_form.html",
        {
            "form": form,
            "page_title": "تعديل درجة",
            "button_text": "حفظ التعديلات",
        },
    )


@require_POST
@user_passes_test(is_admin_user, login_url="/admin/login/")
def grade_delete(request, grade_id):
    grade = get_object_or_404(Grade, id=grade_id)

    grade.delete()

    messages.success(request, "تم حذف الدرجة بنجاح.")
    return redirect("dashboard:grade-list")


@user_passes_test(is_admin_user, login_url="/admin/login/")
def assignment_list(request):
    classroom_id = request.GET.get("classroom", "").strip()
    section_id = request.GET.get("section", "").strip()
    subject_id = request.GET.get("subject", "").strip()
    teacher_id = request.GET.get("teacher", "").strip()

    selected_classroom = int(classroom_id) if classroom_id.isdigit() else None
    selected_section = int(section_id) if section_id.isdigit() else None
    selected_subject = int(subject_id) if subject_id.isdigit() else None
    selected_teacher = int(teacher_id) if teacher_id.isdigit() else None

    assignments = Assignment.objects.select_related(
        "teacher__user",
        "classroom",
        "section",
        "subject",
    )

    if selected_classroom:
        assignments = assignments.filter(classroom_id=selected_classroom)

    if selected_section:
        assignments = assignments.filter(section_id=selected_section)

    if selected_subject:
        assignments = assignments.filter(subject_id=selected_subject)

    if selected_teacher:
        assignments = assignments.filter(teacher_id=selected_teacher)

    return render(
        request,
        "dashboard/assignment_list.html",
        {
            "assignments": assignments.order_by("-created_at"),
            "classrooms": ClassRoom.objects.order_by("name"),
            "sections": Section.objects.select_related("classroom").order_by(
                "classroom__name", "name"
            ),
            "subjects": Subject.objects.order_by("name"),
            "teachers": TeacherProfile.objects.select_related("user").order_by(
                "user__first_name", "user__last_name", "employee_code"
            ),
            "selected_classroom": selected_classroom,
            "selected_section": selected_section,
            "selected_subject": selected_subject,
            "selected_teacher": selected_teacher,
        },
    )


@user_passes_test(is_admin_user, login_url="/admin/login/")
def assignment_create(request):
    if request.method == "POST":
        form = AssignmentForm(request.POST)

        if form.is_valid():
            form.save()
            messages.success(request, "تم إنشاء الواجب بنجاح.")
            return redirect("dashboard:assignment-list")
    else:
        form = AssignmentForm()

    return render(
        request,
        "dashboard/assignment_form.html",
        {
            "form": form,
            "page_title": "إضافة واجب",
            "button_text": "إنشاء الواجب",
        },
    )


@user_passes_test(is_admin_user, login_url="/admin/login/")
def assignment_update(request, assignment_id):
    assignment = get_object_or_404(
        Assignment.objects.select_related(
            "teacher__user",
            "classroom",
            "section",
            "subject",
        ),
        id=assignment_id,
    )

    if request.method == "POST":
        form = AssignmentForm(request.POST, instance=assignment)

        if form.is_valid():
            form.save()
            messages.success(request, "تم تحديث الواجب بنجاح.")
            return redirect("dashboard:assignment-list")
    else:
        form = AssignmentForm(instance=assignment)

    return render(
        request,
        "dashboard/assignment_form.html",
        {
            "form": form,
            "page_title": "تعديل واجب",
            "button_text": "حفظ التعديلات",
        },
    )


@require_POST
@user_passes_test(is_admin_user, login_url="/admin/login/")
def assignment_delete(request, assignment_id):
    assignment = get_object_or_404(Assignment, id=assignment_id)

    assignment.delete()

    messages.success(request, "تم حذف الواجب بنجاح.")
    return redirect("dashboard:assignment-list")


@user_passes_test(is_admin_user, login_url="/admin/login/")
def assignment_submission_list(request):
    classroom_id = request.GET.get("classroom", "").strip()
    section_id = request.GET.get("section", "").strip()
    subject_id = request.GET.get("subject", "").strip()
    status_filter = request.GET.get("status", "").strip()

    selected_classroom = int(classroom_id) if classroom_id.isdigit() else None
    selected_section = int(section_id) if section_id.isdigit() else None
    selected_subject = int(subject_id) if subject_id.isdigit() else None

    submissions = AssignmentSubmission.objects.select_related(
        "assignment",
        "assignment__classroom",
        "assignment__section",
        "assignment__subject",
        "student",
        "student__user",
    )

    if selected_classroom:
        submissions = submissions.filter(assignment__classroom_id=selected_classroom)

    if selected_section:
        submissions = submissions.filter(assignment__section_id=selected_section)

    if selected_subject:
        submissions = submissions.filter(assignment__subject_id=selected_subject)

    valid_statuses = {choice[0] for choice in AssignmentSubmission.Status.choices}
    if status_filter in valid_statuses:
        submissions = submissions.filter(status=status_filter)

    status_names = dict(AssignmentSubmission.Status.choices)
    submissions = list(submissions.order_by("-updated_at"))
    for submission in submissions:
        submission.status_name = status_names.get(
            submission.status,
            submission.status,
        )

    return render(
        request,
        "dashboard/assignment_submission_list.html",
        {
            "submissions": submissions,
            "classrooms": ClassRoom.objects.order_by("name"),
            "sections": Section.objects.select_related("classroom").order_by(
                "classroom__name", "name"
            ),
            "subjects": Subject.objects.order_by("name"),
            "status_choices": AssignmentSubmission.Status.choices,
            "selected_classroom": selected_classroom,
            "selected_section": selected_section,
            "selected_subject": selected_subject,
            "selected_status": status_filter,
        },
    )


@user_passes_test(is_admin_user, login_url="/admin/login/")
def assignment_submission_detail(request, submission_id):
    submission = get_object_or_404(
        AssignmentSubmission.objects.select_related(
            "assignment",
            "assignment__classroom",
            "assignment__section",
            "assignment__subject",
            "student",
            "student__user",
        ),
        id=submission_id,
    )

    status_names = dict(AssignmentSubmission.Status.choices)
    submission.status_name = status_names.get(submission.status, submission.status)

    return render(
        request,
        "dashboard/assignment_submission_detail.html",
        {"submission": submission},
    )


@xframe_options_sameorigin
@user_passes_test(is_admin_user, login_url="/admin/login/")
def assignment_submission_open(request, submission_id):
    submission = get_object_or_404(AssignmentSubmission, id=submission_id)

    if not submission.file:
        raise Http404("File not found.")

    try:
        file_handle = submission.file.open("rb")
    except FileNotFoundError as exc:
        raise Http404("File not found.") from exc

    filename = Path(submission.file.name).name
    content_type = mimetypes.guess_type(filename)[0] or "application/octet-stream"

    return FileResponse(
        file_handle,
        as_attachment=False,
        content_type=content_type,
        filename=filename,
    )


@user_passes_test(is_admin_user, login_url="/admin/login/")
def assignment_submission_review(request, submission_id):
    submission = get_object_or_404(
        AssignmentSubmission.objects.select_related(
            "assignment",
            "assignment__subject",
            "student",
            "student__user",
        ),
        id=submission_id,
    )

    if request.method == "POST":
        form = AssignmentSubmissionReviewForm(request.POST, instance=submission)

        if form.is_valid():
            submission = form.save()
            if submission.status == AssignmentSubmission.Status.REVIEWED:
                notify_student_and_parents(
                    student=submission.student,
                    notification_type=Notification.Type.ASSIGNMENT,
                    title="Assignment reviewed",
                    message=f"{submission.assignment.title} has been reviewed.",
                    related_object_type="AssignmentSubmission",
                    related_object_id=submission.id,
                )
            messages.success(request, "تم حفظ مراجعة التسليم بنجاح.")
            return redirect("dashboard:assignment-submission-detail", submission.id)
    else:
        form = AssignmentSubmissionReviewForm(instance=submission)

    return render(
        request,
        "dashboard/assignment_submission_review.html",
        {
            "form": form,
            "submission": submission,
            "page_title": "مراجعة تسليم واجب",
            "button_text": "حفظ المراجعة",
        },
    )


@user_passes_test(is_admin_user, login_url="/admin/login/")
def uploaded_file_list(request):
    classroom_id = request.GET.get("classroom", "").strip()
    section_id = request.GET.get("section", "").strip()
    subject_id = request.GET.get("subject", "").strip()
    file_type = request.GET.get("file_type", "").strip()

    selected_classroom = int(classroom_id) if classroom_id.isdigit() else None
    selected_section = int(section_id) if section_id.isdigit() else None
    selected_subject = int(subject_id) if subject_id.isdigit() else None

    uploaded_files = TeacherUploadedFile.objects.select_related(
        "teacher__user",
        "assignment",
        "classroom",
        "section",
        "subject",
    )

    if selected_classroom:
        uploaded_files = uploaded_files.filter(classroom_id=selected_classroom)

    if selected_section:
        uploaded_files = uploaded_files.filter(section_id=selected_section)

    if selected_subject:
        uploaded_files = uploaded_files.filter(subject_id=selected_subject)

    valid_file_types = {choice[0] for choice in TeacherUploadedFile.FileType.choices}
    if file_type in valid_file_types:
        uploaded_files = uploaded_files.filter(file_type=file_type)

    file_type_names = dict(FILE_TYPE_CHOICES)
    uploaded_files = list(uploaded_files.order_by("-created_at"))
    for uploaded_file in uploaded_files:
        uploaded_file.file_type_name = file_type_names.get(
            uploaded_file.file_type, uploaded_file.file_type
        )

    return render(
        request,
        "dashboard/uploaded_file_list.html",
        {
            "uploaded_files": uploaded_files,
            "classrooms": ClassRoom.objects.order_by("name"),
            "sections": Section.objects.select_related("classroom").order_by(
                "classroom__name", "name"
            ),
            "subjects": Subject.objects.order_by("name"),
            "file_type_choices": FILE_TYPE_CHOICES,
            "selected_classroom": selected_classroom,
            "selected_section": selected_section,
            "selected_subject": selected_subject,
            "selected_file_type": file_type,
        },
    )


@user_passes_test(is_admin_user, login_url="/admin/login/")
def uploaded_file_create(request):
    if request.method == "POST":
        form = TeacherUploadedFileForm(request.POST, request.FILES)

        if form.is_valid():
            form.save()
            messages.success(request, "تم رفع الملف بنجاح.")
            return redirect("dashboard:uploaded-file-list")
    else:
        form = TeacherUploadedFileForm()

    return render(
        request,
        "dashboard/uploaded_file_form.html",
        {
            "form": form,
            "page_title": "رفع ملف",
            "button_text": "رفع الملف",
        },
    )


@user_passes_test(is_admin_user, login_url="/admin/login/")
def uploaded_file_detail(request, uploaded_file_id):
    uploaded_file = get_object_or_404(
        TeacherUploadedFile.objects.select_related(
            "teacher__user",
            "assignment",
            "classroom",
            "section",
            "subject",
        ),
        id=uploaded_file_id,
    )

    uploaded_file.file_type_name = dict(FILE_TYPE_CHOICES).get(
        uploaded_file.file_type, uploaded_file.file_type
    )

    return render(
        request,
        "dashboard/uploaded_file_detail.html",
        {"uploaded_file": uploaded_file},
    )


@xframe_options_sameorigin
@user_passes_test(is_admin_user, login_url="/admin/login/")
def uploaded_file_open(request, uploaded_file_id):
    uploaded_file = get_object_or_404(TeacherUploadedFile, id=uploaded_file_id)

    if not uploaded_file.file:
        raise Http404("File not found.")

    try:
        file_handle = uploaded_file.file.open("rb")
    except FileNotFoundError as exc:
        raise Http404("File not found.") from exc

    filename = Path(uploaded_file.file.name).name
    content_type = mimetypes.guess_type(filename)[0] or "application/octet-stream"

    return FileResponse(
        file_handle,
        as_attachment=False,
        content_type=content_type,
        filename=filename,
    )


@require_POST
@user_passes_test(is_admin_user, login_url="/admin/login/")
def uploaded_file_delete(request, uploaded_file_id):
    uploaded_file = get_object_or_404(TeacherUploadedFile, id=uploaded_file_id)

    if uploaded_file.file:
        uploaded_file.file.delete(save=False)

    uploaded_file.delete()

    messages.success(request, "تم حذف الملف بنجاح.")
    return redirect("dashboard:uploaded-file-list")


@user_passes_test(is_admin_user, login_url="/admin/login/")
def announcement_list(request):
    classroom_id = request.GET.get("classroom", "").strip()
    section_id = request.GET.get("section", "").strip()
    teacher_id = request.GET.get("teacher", "").strip()

    selected_classroom = int(classroom_id) if classroom_id.isdigit() else None
    selected_section = int(section_id) if section_id.isdigit() else None
    selected_teacher = int(teacher_id) if teacher_id.isdigit() else None

    announcements = Announcement.objects.select_related(
        "teacher__user",
        "classroom",
        "section",
    )

    if selected_classroom:
        announcements = announcements.filter(classroom_id=selected_classroom)

    if selected_section:
        announcements = announcements.filter(section_id=selected_section)

    if selected_teacher:
        announcements = announcements.filter(teacher_id=selected_teacher)

    return render(
        request,
        "dashboard/announcement_list.html",
        {
            "announcements": announcements.order_by("-created_at"),
            "classrooms": ClassRoom.objects.order_by("name"),
            "sections": Section.objects.select_related("classroom").order_by(
                "classroom__name", "name"
            ),
            "teachers": TeacherProfile.objects.select_related("user").order_by(
                "user__first_name", "user__last_name", "employee_code"
            ),
            "selected_classroom": selected_classroom,
            "selected_section": selected_section,
            "selected_teacher": selected_teacher,
        },
    )


@user_passes_test(is_admin_user, login_url="/admin/login/")
def announcement_create(request):
    if request.method == "POST":
        form = AnnouncementForm(request.POST)

        if form.is_valid():
            form.save()
            messages.success(request, "تم إنشاء الإعلان بنجاح.")
            return redirect("dashboard:announcement-list")
    else:
        form = AnnouncementForm()

    return render(
        request,
        "dashboard/announcement_form.html",
        {
            "form": form,
            "page_title": "إضافة إعلان",
            "button_text": "إنشاء الإعلان",
        },
    )


@user_passes_test(is_admin_user, login_url="/admin/login/")
def announcement_update(request, announcement_id):
    announcement = get_object_or_404(
        Announcement.objects.select_related("teacher__user", "classroom", "section"),
        id=announcement_id,
    )

    if request.method == "POST":
        form = AnnouncementForm(request.POST, instance=announcement)

        if form.is_valid():
            form.save()
            messages.success(request, "تم تحديث الإعلان بنجاح.")
            return redirect("dashboard:announcement-list")
    else:
        form = AnnouncementForm(instance=announcement)

    return render(
        request,
        "dashboard/announcement_form.html",
        {
            "form": form,
            "page_title": "تعديل إعلان",
            "button_text": "حفظ التعديلات",
        },
    )


@require_POST
@user_passes_test(is_admin_user, login_url="/admin/login/")
def announcement_delete(request, announcement_id):
    announcement = get_object_or_404(Announcement, id=announcement_id)

    announcement.delete()

    messages.success(request, "تم حذف الإعلان بنجاح.")
    return redirect("dashboard:announcement-list")


@user_passes_test(is_admin_user, login_url="/admin/login/")
def notification_list(request):
    user_id = request.GET.get("user", "").strip()
    notification_type = request.GET.get("type", "").strip()
    status_filter = request.GET.get("status", "").strip()
    related_object_type = request.GET.get("related_object_type", "").strip()
    date_from = request.GET.get("date_from", "").strip()
    date_to = request.GET.get("date_to", "").strip()

    selected_user = int(user_id) if user_id.isdigit() else None
    parsed_date_from = parse_date(date_from) if date_from else None
    parsed_date_to = parse_date(date_to) if date_to else None

    notifications = Notification.objects.select_related("recipient")

    if selected_user:
        notifications = notifications.filter(recipient_id=selected_user)

    valid_types = {choice[0] for choice in Notification.Type.choices}
    if notification_type in valid_types:
        notifications = notifications.filter(notification_type=notification_type)

    if status_filter == "read":
        notifications = notifications.filter(is_read=True)
    elif status_filter == "unread":
        notifications = notifications.filter(is_read=False)

    if related_object_type:
        notifications = notifications.filter(
            related_object_type__icontains=related_object_type
        )

    if parsed_date_from:
        notifications = notifications.filter(created_at__date__gte=parsed_date_from)

    if parsed_date_to:
        notifications = notifications.filter(created_at__date__lte=parsed_date_to)

    summary = {
        "total": notifications.count(),
        "read": notifications.filter(is_read=True).count(),
        "unread": notifications.filter(is_read=False).count(),
        "with_deep_link": notifications.exclude(deep_link="").count(),
    }

    type_names = dict(Notification.Type.choices)
    notifications = list(notifications.order_by("-created_at")[:500])
    for notification in notifications:
        notification.type_name = type_names.get(
            notification.notification_type,
            notification.notification_type,
        )

    User = get_user_model()

    return render(
        request,
        "dashboard/notification_list.html",
        {
            "notifications": notifications,
            "summary": summary,
            "users": User.objects.order_by("username"),
            "type_choices": Notification.Type.choices,
            "selected_user": selected_user,
            "selected_type": notification_type,
            "selected_status": status_filter,
            "selected_related_object_type": related_object_type,
            "selected_date_from": date_from,
            "selected_date_to": date_to,
        },
    )


@user_passes_test(is_admin_user, login_url="/admin/login/")
def notification_detail(request, notification_id):
    notification = get_object_or_404(
        Notification.objects.select_related("recipient"),
        id=notification_id,
    )
    deliveries = PushDelivery.objects.select_related(
        "device",
        "device__user",
    ).filter(
        notification=notification,
    ).order_by("-created_at")

    type_names = dict(Notification.Type.choices)
    notification.type_name = type_names.get(
        notification.notification_type,
        notification.notification_type,
    )

    return render(
        request,
        "dashboard/notification_detail.html",
        {
            "notification": notification,
            "deliveries": deliveries,
        },
    )


@require_POST
@user_passes_test(is_admin_user, login_url="/admin/login/")
def notification_toggle_read(request, notification_id):
    notification = get_object_or_404(Notification, id=notification_id)

    if notification.is_read:
        notification.is_read = False
        notification.read_at = None
        messages.success(request, "تم جعل الإشعار غير مقروء.")
    else:
        notification.is_read = True
        notification.read_at = timezone.now()
        messages.success(request, "تم جعل الإشعار مقروءًا.")

    notification.save(update_fields=["is_read", "read_at"])

    return redirect("dashboard:notification-list")


@require_POST
@user_passes_test(is_admin_user, login_url="/admin/login/")
def notification_delete(request, notification_id):
    notification = get_object_or_404(Notification, id=notification_id)

    notification.delete()

    messages.success(request, "تم حذف الإشعار بنجاح.")
    return redirect("dashboard:notification-list")


def resolve_broadcast_recipients(form):
    User = get_user_model()
    audience = form.cleaned_data["audience"]

    if audience == NotificationBroadcastForm.AUDIENCE_ALL:
        return User.objects.filter(is_active=True).order_by("username")

    if audience == NotificationBroadcastForm.AUDIENCE_ROLE:
        return User.objects.filter(
            is_active=True,
            role=form.cleaned_data["role"],
        ).order_by("username")

    if audience == NotificationBroadcastForm.AUDIENCE_CLASSROOM:
        students = StudentProfile.objects.filter(
            classroom=form.cleaned_data["classroom"],
            user__is_active=True,
        )
    else:
        students = StudentProfile.objects.filter(
            section=form.cleaned_data["section"],
            user__is_active=True,
        )

    student_user_ids = students.values_list("user_id", flat=True)
    parent_user_ids = ParentStudentLink.objects.filter(
        student_id__in=students.values_list("id", flat=True),
        parent__user__is_active=True,
    ).values_list("parent__user_id", flat=True)

    recipient_ids = set(student_user_ids) | set(parent_user_ids)
    return User.objects.filter(id__in=recipient_ids).order_by("username")


@user_passes_test(is_admin_user, login_url="/admin/login/")
def notification_broadcast(request):
    if request.method == "POST":
        form = NotificationBroadcastForm(request.POST)
        if form.is_valid():
            recipients = list(resolve_broadcast_recipients(form))

            if not recipients:
                messages.error(request, "لا يوجد مستخدمون مطابقون لهذا الجمهور.")
                return render(
                    request,
                    "dashboard/notification_broadcast.html",
                    {"form": form},
                )

            for recipient in recipients:
                Notification.objects.create(
                    recipient=recipient,
                    notification_type=form.cleaned_data["notification_type"],
                    title=form.cleaned_data["title"],
                    message=form.cleaned_data["message"],
                    deep_link=form.cleaned_data.get("deep_link", ""),
                )

            messages.success(
                request,
                f"تم إرسال الإشعار إلى {len(recipients)} مستخدم.",
            )
            return redirect("dashboard:notification-list")
    else:
        form = NotificationBroadcastForm()

    return render(
        request,
        "dashboard/notification_broadcast.html",
        {"form": form},
    )


@user_passes_test(is_admin_user, login_url="/admin/login/")
def notification_reminder_center(request):
    initial = {
        "invoice_days": settings.REMINDER_INVOICE_DAYS_BEFORE,
        "assignment_days": settings.REMINDER_ASSIGNMENT_DAYS_BEFORE,
        "absence_window_days": settings.REMINDER_ABSENCE_WINDOW_DAYS,
        "absence_threshold": settings.REMINDER_ABSENCE_THRESHOLD,
    }
    result = None
    mode = None

    if request.method == "POST":
        form = NotificationReminderForm(request.POST)
        if form.is_valid():
            mode = request.POST.get("action", "dry_run")
            dry_run = mode != "send"
            runner = NotificationReminderRunner(
                invoice_days=form.cleaned_data["invoice_days"],
                assignment_days=form.cleaned_data["assignment_days"],
                absence_window_days=form.cleaned_data["absence_window_days"],
                absence_threshold=form.cleaned_data["absence_threshold"],
            )
            result = runner.run(dry_run=dry_run)

            total = sum(result.values())
            if dry_run:
                messages.success(
                    request,
                    f"المعاينة اكتملت: يوجد {total} تذكير قابل للإرسال بدون إنشاء إشعارات.",
                )
            else:
                messages.success(
                    request,
                    f"تم إنشاء {total} تذكير. لن يتكرر نفس التذكير لنفس المستخدم اليوم.",
                )
    else:
        form = NotificationReminderForm(initial=initial)

    return render(
        request,
        "dashboard/notification_reminder_center.html",
        {
            "form": form,
            "result": result,
            "mode": mode,
        },
    )


@user_passes_test(is_admin_user, login_url="/admin/login/")
def notification_preference_list(request):
    user_id = request.GET.get("user", "").strip()
    role = request.GET.get("role", "").strip()

    User = get_user_model()
    users = User.objects.order_by("username")

    for user in users:
        NotificationPreference.objects.get_or_create(user=user)

    preferences = NotificationPreference.objects.select_related("user")

    selected_user = int(user_id) if user_id.isdigit() else None
    if selected_user:
        preferences = preferences.filter(user_id=selected_user)

    valid_roles = {choice[0] for choice in User.Role.choices}
    if role in valid_roles:
        preferences = preferences.filter(user__role=role)

    return render(
        request,
        "dashboard/notification_preference_list.html",
        {
            "preferences": preferences.order_by("user__username"),
            "users": users,
            "role_choices": User.Role.choices,
            "selected_user": selected_user,
            "selected_role": role,
        },
    )


@user_passes_test(is_admin_user, login_url="/admin/login/")
def notification_preference_update(request, preference_id):
    preference = get_object_or_404(
        NotificationPreference.objects.select_related("user"),
        id=preference_id,
    )

    if request.method == "POST":
        form = NotificationPreferenceForm(request.POST, instance=preference)
        if form.is_valid():
            form.save()
            messages.success(request, "تم تحديث تفضيلات الإشعارات بنجاح.")
            return redirect("dashboard:notification-preference-list")
    else:
        form = NotificationPreferenceForm(instance=preference)

    return render(
        request,
        "dashboard/notification_preference_form.html",
        {
            "form": form,
            "preference": preference,
            "page_title": "تعديل تفضيلات الإشعارات",
            "button_text": "حفظ التفضيلات",
        },
    )


@user_passes_test(is_admin_user, login_url="/admin/login/")
def notification_template_list(request):
    query = request.GET.get("q", "").strip()
    language = request.GET.get("language", "").strip()
    notification_type = request.GET.get("type", "").strip()

    templates = NotificationTemplate.objects.all()

    if query:
        templates = templates.filter(
            Q(key__icontains=query)
            | Q(title_template__icontains=query)
            | Q(message_template__icontains=query)
        )

    valid_languages = {choice[0] for choice in NotificationPreference.Language.choices}
    if language in valid_languages:
        templates = templates.filter(language=language)

    valid_types = {choice[0] for choice in Notification.Type.choices}
    if notification_type in valid_types:
        templates = templates.filter(notification_type=notification_type)

    return render(
        request,
        "dashboard/notification_template_list.html",
        {
            "templates": templates.order_by("key", "language"),
            "language_choices": NotificationPreference.Language.choices,
            "type_choices": Notification.Type.choices,
            "selected_query": query,
            "selected_language": language,
            "selected_type": notification_type,
        },
    )


@user_passes_test(is_admin_user, login_url="/admin/login/")
def notification_template_update(request, template_id):
    template = get_object_or_404(NotificationTemplate, id=template_id)

    if request.method == "POST":
        form = NotificationTemplateForm(request.POST, instance=template)
        if form.is_valid():
            form.save()
            messages.success(request, "تم تحديث قالب الإشعار بنجاح.")
            return redirect("dashboard:notification-template-list")
    else:
        form = NotificationTemplateForm(instance=template)

    return render(
        request,
        "dashboard/notification_template_form.html",
        {
            "form": form,
            "template": template,
            "page_title": "تعديل قالب الإشعار",
            "button_text": "حفظ القالب",
        },
    )


@user_passes_test(is_admin_user, login_url="/admin/login/")
def push_device_list(request):
    user_id = request.GET.get("user", "").strip()
    platform = request.GET.get("platform", "").strip()
    status_filter = request.GET.get("status", "").strip()

    selected_user = int(user_id) if user_id.isdigit() else None

    devices = PushDevice.objects.select_related("user")

    if selected_user:
        devices = devices.filter(user_id=selected_user)

    valid_platforms = {choice[0] for choice in PushDevice.Platform.choices}
    if platform in valid_platforms:
        devices = devices.filter(platform=platform)

    if status_filter == "active":
        devices = devices.filter(is_active=True)
    elif status_filter == "inactive":
        devices = devices.filter(is_active=False)

    User = get_user_model()

    return render(
        request,
        "dashboard/push_device_list.html",
        {
            "devices": devices.order_by("-last_seen_at"),
            "users": User.objects.order_by("username"),
            "platform_choices": PushDevice.Platform.choices,
            "selected_user": selected_user,
            "selected_platform": platform,
            "selected_status": status_filter,
        },
    )


@user_passes_test(is_admin_user, login_url="/admin/login/")
@require_POST
def push_device_toggle_active(request, device_id):
    device = get_object_or_404(PushDevice.objects.select_related("user"), id=device_id)

    if device.is_active:
        device.is_active = False
        device.deactivated_at = timezone.now()
        device.last_error = device.last_error or "Disabled from dashboard"
        message = "تم تعطيل جهاز Push بنجاح."
    else:
        device.is_active = True
        device.deactivated_at = None
        device.last_error = ""
        message = "تم تفعيل جهاز Push بنجاح."

    device.save(update_fields=["is_active", "deactivated_at", "last_error", "updated_at"])
    messages.success(request, message)
    return redirect("dashboard:push-device-list")


@user_passes_test(is_admin_user, login_url="/admin/login/")
@require_POST
def push_device_send_test(request, device_id):
    device = get_object_or_404(PushDevice.objects.select_related("user"), id=device_id)

    notification = Notification(
        recipient=device.user,
        notification_type=Notification.Type.GENERAL,
        title="Orbiet push test",
        message="This is a test notification from the Orbiet dashboard.",
        related_object_type="PushDevice",
        related_object_id=device.id,
        deep_link="orbiet://notifications/test",
    )
    notification._skip_auto_push = True
    notification.save()

    result = send_fcm_message([device], notification)

    if result.get("sent"):
        messages.success(request, "تم إرسال إشعار الاختبار للجهاز المحدد.")
    elif result.get("skipped"):
        messages.warning(
            request,
            "تم إنشاء إشعار الاختبار لكن لم يتم إرساله لأن FCM غير مضبوط أو الجهاز غير جاهز.",
        )
    else:
        messages.error(request, "فشل إرسال إشعار الاختبار. راجع سجل Push لمعرفة السبب.")

    return redirect("dashboard:notification-detail", notification_id=notification.id)


@user_passes_test(is_admin_user, login_url="/admin/login/")
def push_delivery_list(request):
    user_id = request.GET.get("user", "").strip()
    status_filter = request.GET.get("status", "").strip()
    platform = request.GET.get("platform", "").strip()
    error_code = request.GET.get("error_code", "").strip()
    date_from = request.GET.get("date_from", "").strip()
    date_to = request.GET.get("date_to", "").strip()

    selected_user = int(user_id) if user_id.isdigit() else None
    parsed_date_from = parse_date(date_from) if date_from else None
    parsed_date_to = parse_date(date_to) if date_to else None

    deliveries = PushDelivery.objects.select_related(
        "notification",
        "notification__recipient",
        "device",
        "device__user",
    )

    if selected_user:
        deliveries = deliveries.filter(notification__recipient_id=selected_user)

    valid_statuses = {choice[0] for choice in PushDelivery.Status.choices}
    if status_filter in valid_statuses:
        deliveries = deliveries.filter(status=status_filter)

    valid_platforms = {choice[0] for choice in PushDevice.Platform.choices}
    if platform in valid_platforms:
        deliveries = deliveries.filter(device__platform=platform)

    if error_code:
        deliveries = deliveries.filter(error_code__icontains=error_code)

    if parsed_date_from:
        deliveries = deliveries.filter(created_at__date__gte=parsed_date_from)

    if parsed_date_to:
        deliveries = deliveries.filter(created_at__date__lte=parsed_date_to)

    summary = {
        "total": deliveries.count(),
        "sent": deliveries.filter(status=PushDelivery.Status.SENT).count(),
        "failed": deliveries.filter(status=PushDelivery.Status.FAILED).count(),
        "skipped": deliveries.filter(status=PushDelivery.Status.SKIPPED).count(),
        "invalid": deliveries.filter(status=PushDelivery.Status.INVALID_TOKEN).count(),
        "pending": deliveries.filter(status=PushDelivery.Status.PENDING).count(),
    }

    User = get_user_model()

    return render(
        request,
        "dashboard/push_delivery_list.html",
        {
            "deliveries": deliveries.order_by("-created_at")[:500],
            "users": User.objects.order_by("username"),
            "status_choices": PushDelivery.Status.choices,
            "platform_choices": PushDevice.Platform.choices,
            "summary": summary,
            "selected_user": selected_user,
            "selected_status": status_filter,
            "selected_platform": platform,
            "selected_error_code": error_code,
            "selected_date_from": date_from,
            "selected_date_to": date_to,
        },
    )


@user_passes_test(is_admin_user, login_url="/admin/login/")
def push_delivery_detail(request, delivery_id):
    delivery = get_object_or_404(
        PushDelivery.objects.select_related(
            "notification",
            "notification__recipient",
            "device",
            "device__user",
        ),
        id=delivery_id,
    )

    return render(
        request,
        "dashboard/push_delivery_detail.html",
        {
            "delivery": delivery,
        },
    )


@user_passes_test(is_admin_user, login_url="/admin/login/")
@require_POST
def push_delivery_retry(request, delivery_id):
    delivery = get_object_or_404(
        PushDelivery.objects.select_related(
            "notification",
            "notification__recipient",
            "device",
            "device__user",
        ),
        id=delivery_id,
    )

    if not delivery.device.is_active:
        messages.error(request, "لا يمكن إعادة المحاولة لأن جهاز Push غير فعال.")
        return redirect("dashboard:push-delivery-detail", delivery_id=delivery.id)

    result = send_fcm_message([delivery.device], delivery.notification)

    if result.get("sent"):
        messages.success(request, "تمت إعادة محاولة إرسال Push بنجاح.")
    elif result.get("skipped"):
        messages.warning(
            request,
            "تم تسجيل إعادة المحاولة لكنها لم ترسل لأن FCM غير مضبوط أو الإرسال غير جاهز.",
        )
    else:
        messages.error(request, "فشلت إعادة محاولة إرسال Push. راجع كود الخطأ في التفاصيل.")

    return redirect("dashboard:push-delivery-detail", delivery_id=delivery.id)


@user_passes_test(is_admin_user, login_url="/admin/login/")
def push_diagnostics(request):
    since = timezone.now() - timedelta(hours=24)
    recent_deliveries = PushDelivery.objects.filter(created_at__gte=since)
    invalid_device_ids = PushDelivery.objects.filter(
        status=PushDelivery.Status.INVALID_TOKEN,
        device__is_active=True,
    ).values_list("device_id", flat=True).distinct()

    delivery_summary = {
        "total": PushDelivery.objects.count(),
        "last_24h": recent_deliveries.count(),
        "sent_24h": recent_deliveries.filter(status=PushDelivery.Status.SENT).count(),
        "failed_24h": recent_deliveries.filter(status=PushDelivery.Status.FAILED).count(),
        "skipped_24h": recent_deliveries.filter(status=PushDelivery.Status.SKIPPED).count(),
        "invalid_24h": recent_deliveries.filter(
            status=PushDelivery.Status.INVALID_TOKEN
        ).count(),
    }

    device_summary = {
        "total": PushDevice.objects.count(),
        "active": PushDevice.objects.filter(is_active=True).count(),
        "inactive": PushDevice.objects.filter(is_active=False).count(),
        "android": PushDevice.objects.filter(platform=PushDevice.Platform.ANDROID).count(),
        "ios": PushDevice.objects.filter(platform=PushDevice.Platform.IOS).count(),
        "web": PushDevice.objects.filter(platform=PushDevice.Platform.WEB).count(),
        "active_invalid": PushDevice.objects.filter(id__in=invalid_device_ids).count(),
    }

    context = {
        "fcm_configured": bool(settings.FCM_SERVER_KEY),
        "fcm_api_url": settings.FCM_API_URL,
        "fcm_timeout_seconds": settings.FCM_TIMEOUT_SECONDS,
        "celery_installed": bool(importlib.util.find_spec("celery")),
        "push_uses_celery": settings.PUSH_NOTIFICATIONS_USE_CELERY,
        "celery_broker_url": settings.CELERY_BROKER_URL,
        "reminders_use_celery_beat": settings.REMINDERS_USE_CELERY_BEAT,
        "reminders_beat_time": f"{settings.REMINDERS_BEAT_HOUR:02d}:{settings.REMINDERS_BEAT_MINUTE:02d}",
        "device_summary": device_summary,
        "delivery_summary": delivery_summary,
        "recent_errors": PushDelivery.objects.exclude(error_code="").order_by(
            "-created_at"
        )[:10],
    }

    return render(request, "dashboard/push_diagnostics.html", context)


@user_passes_test(is_admin_user, login_url="/admin/login/")
@require_POST
def push_deactivate_invalid_devices(request):
    invalid_device_ids = PushDelivery.objects.filter(
        status=PushDelivery.Status.INVALID_TOKEN,
        device__is_active=True,
    ).values_list("device_id", flat=True).distinct()

    updated_count = PushDevice.objects.filter(id__in=invalid_device_ids).update(
        is_active=False,
        deactivated_at=timezone.now(),
        last_error="Invalid token delivery",
    )

    if updated_count:
        messages.success(request, f"تم تعطيل {updated_count} جهاز Push بسبب token غير صالح.")
    else:
        messages.info(request, "لا توجد أجهزة Push فعالة لديها token غير صالح.")

    return redirect("dashboard:push-diagnostics")


@user_passes_test(is_admin_user, login_url="/admin/login/")
def push_flutter_contract(request):
    return render(request, "dashboard/push_flutter_contract.html")

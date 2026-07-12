from datetime import timedelta

from django.conf import settings
from django.db.models import Count
from django.utils import timezone

from accounts.models import ParentStudentLink, StudentProfile
from academics.models import Assignment, AssignmentSubmission, Attendance
from finance.models import FeeInvoice
from notifications.models import Notification
from notifications.services import create_notification_for_user


class NotificationReminderRunner:
    def __init__(
        self,
        invoice_days=None,
        assignment_days=None,
        absence_window_days=None,
        absence_threshold=None,
        today=None,
    ):
        self.invoice_days = (
            settings.REMINDER_INVOICE_DAYS_BEFORE
            if invoice_days is None
            else invoice_days
        )
        self.assignment_days = (
            settings.REMINDER_ASSIGNMENT_DAYS_BEFORE
            if assignment_days is None
            else assignment_days
        )
        self.absence_window_days = (
            settings.REMINDER_ABSENCE_WINDOW_DAYS
            if absence_window_days is None
            else absence_window_days
        )
        self.absence_threshold = (
            settings.REMINDER_ABSENCE_THRESHOLD
            if absence_threshold is None
            else absence_threshold
        )
        self.today = today or timezone.localdate()

    def run(self, dry_run=False):
        return {
            'invoice_reminders': self.send_invoice_reminders(dry_run=dry_run),
            'assignment_reminders': self.send_assignment_reminders(dry_run=dry_run),
            'absence_reminders': self.send_absence_reminders(dry_run=dry_run),
        }

    def send_invoice_reminders(self, dry_run):
        due_until = self.today + timedelta(days=max(self.invoice_days, 0))
        created_count = 0

        invoices = FeeInvoice.objects.select_related(
            'student',
            'student__user',
        ).filter(
            status=FeeInvoice.Status.UNPAID,
            due_date__isnull=False,
            due_date__lte=due_until,
        )

        for invoice in invoices:
            for recipient in self.student_recipients(invoice.student):
                created_count += self.create_once_per_day(
                    recipient=recipient,
                    notification_type=Notification.Type.INVOICE,
                    title='Invoice due reminder',
                    message=f'Invoice "{invoice.title}" is due on {invoice.due_date}.',
                    related_object_type='FeeInvoiceReminder',
                    related_object_id=invoice.id,
                    deep_link=f'orbiet://invoices/{invoice.id}',
                    template_key='reminder_invoice_due',
                    context={
                        'invoice_title': invoice.title,
                        'due_date': invoice.due_date,
                        'amount': invoice.amount,
                        'currency': invoice.currency.upper(),
                    },
                    dry_run=dry_run,
                )

        return created_count

    def send_assignment_reminders(self, dry_run):
        due_until = self.today + timedelta(days=max(self.assignment_days, 0))
        created_count = 0

        assignments = Assignment.objects.select_related(
            'section',
            'subject',
        ).filter(
            due_date__isnull=False,
            due_date__gte=self.today,
            due_date__lte=due_until,
        )

        for assignment in assignments:
            submitted_student_ids = AssignmentSubmission.objects.filter(
                assignment=assignment,
            ).values_list('student_id', flat=True)

            students = StudentProfile.objects.select_related('user').filter(
                section=assignment.section,
            ).exclude(id__in=submitted_student_ids)

            for student in students:
                for recipient in self.student_recipients(student):
                    created_count += self.create_once_per_day(
                        recipient=recipient,
                        notification_type=Notification.Type.ASSIGNMENT,
                        title='Assignment due reminder',
                        message=f'Assignment "{assignment.title}" is due on {assignment.due_date}.',
                        related_object_type='AssignmentReminder',
                        related_object_id=assignment.id,
                        deep_link=f'orbiet://assignments/{assignment.id}',
                        template_key='reminder_assignment_due',
                        context={
                            'assignment_title': assignment.title,
                            'due_date': assignment.due_date,
                            'subject_name': assignment.subject.name,
                        },
                        dry_run=dry_run,
                    )

        return created_count

    def send_absence_reminders(self, dry_run):
        window_start = self.today - timedelta(days=max(self.absence_window_days, 1) - 1)
        created_count = 0

        repeated_absences = Attendance.objects.filter(
            status=Attendance.Status.ABSENT,
            date__gte=window_start,
            date__lte=self.today,
        ).values('student_id').annotate(
            absence_count=Count('id'),
        ).filter(
            absence_count__gte=max(self.absence_threshold, 1),
        )

        student_ids = [item['student_id'] for item in repeated_absences]
        absence_counts = {
            item['student_id']: item['absence_count']
            for item in repeated_absences
        }

        students = StudentProfile.objects.select_related('user').filter(
            id__in=student_ids,
        )

        for student in students:
            absence_count = absence_counts.get(student.id, 0)
            for recipient in self.student_recipients(student):
                created_count += self.create_once_per_day(
                    recipient=recipient,
                    notification_type=Notification.Type.ATTENDANCE,
                    title='Repeated absence alert',
                    message=f'{student} has {absence_count} recorded absences.',
                    related_object_type='RepeatedAbsenceReminder',
                    related_object_id=student.id,
                    deep_link=f'orbiet://attendance?student_id={student.id}',
                    template_key='reminder_repeated_absence',
                    context={
                        'student_name': student.user.get_full_name() or student.user.username,
                        'absence_count': absence_count,
                    },
                    dry_run=dry_run,
                )

        return created_count

    def student_recipients(self, student):
        yield student.user

        parent_users = ParentStudentLink.objects.select_related(
            'parent',
            'parent__user',
        ).filter(
            student=student,
        )

        for link in parent_users:
            yield link.parent.user

    def create_once_per_day(
        self,
        recipient,
        notification_type,
        title,
        message,
        related_object_type,
        related_object_id,
        deep_link,
        template_key,
        context,
        dry_run,
    ):
        exists = Notification.objects.filter(
            recipient=recipient,
            notification_type=notification_type,
            related_object_type=related_object_type,
            related_object_id=related_object_id,
            created_at__date=self.today,
        ).exists()

        if exists:
            return 0

        if dry_run:
            return 1

        create_notification_for_user(
            recipient=recipient,
            notification_type=notification_type,
            title=title,
            message=message,
            related_object_type=related_object_type,
            related_object_id=related_object_id,
            deep_link=deep_link,
            template_key=template_key,
            context=context,
        )
        return 1

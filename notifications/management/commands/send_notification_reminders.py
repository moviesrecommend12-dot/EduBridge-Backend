from django.conf import settings
from django.core.management.base import BaseCommand

from notifications.reminders import NotificationReminderRunner


class Command(BaseCommand):
    help = 'Send automatic reminders for invoices, assignments, and repeated absences.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Calculate reminders without creating notifications.',
        )
        parser.add_argument(
            '--invoice-days',
            type=int,
            default=settings.REMINDER_INVOICE_DAYS_BEFORE,
            help='Send invoice reminders for due dates up to this many days ahead.',
        )
        parser.add_argument(
            '--assignment-days',
            type=int,
            default=settings.REMINDER_ASSIGNMENT_DAYS_BEFORE,
            help='Send assignment reminders for due dates up to this many days ahead.',
        )
        parser.add_argument(
            '--absence-window-days',
            type=int,
            default=settings.REMINDER_ABSENCE_WINDOW_DAYS,
            help='Count absences within this many previous days.',
        )
        parser.add_argument(
            '--absence-threshold',
            type=int,
            default=settings.REMINDER_ABSENCE_THRESHOLD,
            help='Send repeated absence reminders when absence count reaches this number.',
        )

    def handle(self, *args, **options):
        runner = NotificationReminderRunner(
            invoice_days=options['invoice_days'],
            assignment_days=options['assignment_days'],
            absence_window_days=options['absence_window_days'],
            absence_threshold=options['absence_threshold'],
        )
        counts = runner.run(dry_run=options['dry_run'])

        mode = 'DRY RUN' if options['dry_run'] else 'SENT'
        self.stdout.write(
            self.style.SUCCESS(
                f'{mode}: invoices={counts["invoice_reminders"]}, '
                f'assignments={counts["assignment_reminders"]}, '
                f'absences={counts["absence_reminders"]}'
            )
        )

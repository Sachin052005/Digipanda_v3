"""
Management command to execute scheduled installment reminder evaluation.
Can be executed via Windows Task Scheduler, Linux Cron, or Celery Beat:
    python manage.py send_installment_reminders
    python manage.py send_installment_reminders --date 2026-10-15
"""

from datetime import datetime
from django.core.management.base import BaseCommand
from django.utils import timezone
from services.email_service import process_installment_reminders_batch


class Command(BaseCommand):
    help = "Evaluates upcoming, due, and overdue fee installments and dispatches automated email reminders."

    def add_arguments(self, parser):
        parser.add_argument(
            '--date',
            type=str,
            dest='target_date',
            default='',
            help='Target evaluation date in YYYY-MM-DD format (defaults to current server date).'
        )

    def handle(self, *args, **options):
        date_str = options.get('target_date', '').strip()
        if date_str:
            try:
                target_date = datetime.strptime(date_str, '%Y-%m-%d').date()
            except ValueError:
                self.stdout.write(self.style.ERROR(f"Invalid date format '{date_str}'. Expected YYYY-MM-DD."))
                return
        else:
            target_date = timezone.localdate()

        self.stdout.write(self.style.MIGRATE_HEADING(f"Processing Installment Reminders for evaluation date: {target_date}"))

        summary = process_installment_reminders_batch(target_date=target_date)

        self.stdout.write(self.style.SUCCESS(f"  7 Days Upcoming : {summary.get('upcoming_7_days', 0)}"))
        self.stdout.write(self.style.SUCCESS(f"  1 Day Upcoming  : {summary.get('upcoming_1_day', 0)}"))
        self.stdout.write(self.style.SUCCESS(f"  Due Today       : {summary.get('due_today', 0)}"))
        self.stdout.write(self.style.SUCCESS(f"  3 Days Overdue  : {summary.get('overdue_3_days', 0)}"))
        self.stdout.write(self.style.SUCCESS(f"  Weekly Overdue  : {summary.get('overdue_weekly', 0)}"))
        if summary.get('errors', 0) > 0:
            self.stdout.write(self.style.WARNING(f"  Errors encountered: {summary['errors']}"))
        else:
            self.stdout.write(self.style.SUCCESS("  Errors: 0"))

        total_sent = sum(v for k, v in summary.items() if k != 'errors')
        self.stdout.write(self.style.SUCCESS(f"Total reminders sent: {total_sent}"))

from datetime import datetime
from django.core.management.base import BaseCommand
from django.utils import timezone
from finance.services import process_renewal_alerts_batch


class Command(BaseCommand):
    help = "Evaluates scheduled renewal alerts and dispatches notifications to Branch Financial Head and Branch Head."

    def add_arguments(self, parser):
        parser.add_argument(
            '--date',
            type=str,
            dest='target_date',
            default='',
            help='Evaluation date in YYYY-MM-DD format (defaults to current date).'
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

        self.stdout.write(self.style.MIGRATE_HEADING(f"Evaluating Renewal Alerts for date: {target_date}"))
        summary = process_renewal_alerts_batch(target_date=target_date)

        self.stdout.write(self.style.SUCCESS(f"  Alerts evaluated   : {summary['alerts_evaluated']}"))
        self.stdout.write(self.style.SUCCESS(f"  Notifications sent : {summary['notifications_sent']}"))

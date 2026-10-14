from django.core.management.base import BaseCommand
from leads.assignment import run_lead_sla_escalation

class Command(BaseCommand):
    help = 'Run automated lead SLA escalation and reassignment for neglected leads'

    def add_arguments(self, parser):
        parser.add_argument(
            '--stale-hours',
            type=int,
            default=24,
            help='Hours uncontacted before a New lead is escalated (default: 24)'
        )
        parser.add_argument(
            '--untouched-days',
            type=int,
            default=7,
            help='Days without touch before an in-progress lead is reassigned (default: 7)'
        )

    def handle(self, *args, **options):
        stale_hours = options['stale_hours']
        untouched_days = options['untouched_days']

        self.stdout.write(self.style.NOTICE(
            f"Checking leads breaching SLA (Fresh > {stale_hours}h, Untouched > {untouched_days}d)..."
        ))

        summary = run_lead_sla_escalation(
            stale_hours=stale_hours,
            untouched_days=untouched_days,
            triggered_by=None
        )

        self.stdout.write(self.style.SUCCESS(
            f"SLA Escalation Complete: "
            f"{summary['escalated_fresh']} fresh leads escalated, "
            f"{summary['escalated_untouched']} untouched leads reassigned, "
            f"{summary['notified_managers']} managers alerted."
        ))

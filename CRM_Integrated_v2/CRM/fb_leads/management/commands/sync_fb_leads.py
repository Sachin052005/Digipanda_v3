import time
import logging
from django.core.management.base import BaseCommand
from django.utils import timezone

from fb_leads.crm import push_to_crm
from fb_leads.facebook import sync_all_leads
from fb_leads.models import FacebookLead
from fb_leads.scheduler import run_auto_sync_cycle

log = logging.getLogger("crm")


class Command(BaseCommand):
    help = (
        "Synchronize leads from Facebook Lead Ads into the CRM. "
        "Supports one-off execution, --crm-only (re-link unmapped leads), "
        "or --loop for continuous background auto-sync."
    )

    def add_arguments(self, parser):
        parser.add_argument("--crm-only", action="store_true", help="Only push saved Facebook leads to the CRM")
        parser.add_argument("--loop", action="store_true", help="Run continuously in a loop as a daemon worker")
        parser.add_argument("--interval", type=int, default=180, help="Loop interval in seconds (default: 180s = 3 mins)")

    def handle(self, *args, **options):
        if options["loop"]:
            interval = max(30, options["interval"])
            self.stdout.write(self.style.SUCCESS(f"Starting Facebook Leads Auto-Sync daemon (checking every {interval}s)..."))
            try:
                while True:
                    timestamp = timezone.now().strftime("%Y-%m-%d %H:%M:%S")
                    try:
                        ran = run_auto_sync_cycle()
                        if ran:
                            self.stdout.write(self.style.SUCCESS(f"[{timestamp}] Auto-sync cycle completed."))
                        else:
                            self.stdout.write(f"[{timestamp}] Checked pages - none due.")
                    except Exception as exc:
                        self.stderr.write(self.style.ERROR(f"[{timestamp}] Error in auto-sync cycle: {exc}"))

                    # Retry unmapped leads
                    pushed = errors = 0
                    for fb in FacebookLead.objects.filter(lead__isnull=True)[:100]:
                        if push_to_crm(fb):
                            pushed += 1
                        else:
                            errors += 1
                    if pushed:
                        self.stdout.write(self.style.SUCCESS(f"[{timestamp}] Pushed {pushed} previously pending lead(s) to CRM."))

                    time.sleep(interval)
            except KeyboardInterrupt:
                self.stdout.write(self.style.WARNING("Auto-Sync daemon stopped by user."))
            return

        # Default one-off execution
        if not options["crm_only"]:
            try:
                n = sync_all_leads()
                self.stdout.write(self.style.SUCCESS(f"{n} new Facebook lead(s) downloaded."))
            except Exception as exc:
                self.stderr.write(self.style.ERROR(f"Download failed: {exc}"))

        pushed = errors = 0
        for fb in FacebookLead.objects.filter(lead__isnull=True):
            if push_to_crm(fb):
                pushed += 1
            else:
                errors += 1
        self.stdout.write(
            self.style.SUCCESS(
                f"{pushed} Facebook lead(s) added to the CRM, {errors} could not be added "
                f"(see Facebook Leads page → Show errors)."
            )
        )

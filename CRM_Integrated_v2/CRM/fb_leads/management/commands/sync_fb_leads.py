from django.core.management.base import BaseCommand

from fb_leads.crm import push_to_crm
from fb_leads.facebook import sync_all_leads
from fb_leads.models import FacebookLead


class Command(BaseCommand):
    help = ("Pull all leads from every lead form on the Facebook Page and add them to the CRM "
            "(source Facebook). --crm-only: don't call Facebook, just add saved Facebook leads that "
            "aren't in the CRM yet (e.g. after importing them from the old fb_leads project).")

    def add_arguments(self, parser):
        parser.add_argument("--crm-only", action="store_true", help="Only push saved Facebook leads to the CRM")

    def handle(self, *args, **options):
        if not options["crm_only"]:
            n = sync_all_leads()
            self.stdout.write(self.style.SUCCESS(f"{n} new Facebook lead(s) downloaded."))
        pushed = errors = 0
        for fb in FacebookLead.objects.filter(lead__isnull=True):
            if push_to_crm(fb):
                pushed += 1
            else:
                errors += 1
        self.stdout.write(self.style.SUCCESS(f"{pushed} Facebook lead(s) added to the CRM, {errors} could not be added "
                                             f"(see Facebook Leads page → Show errors)."))

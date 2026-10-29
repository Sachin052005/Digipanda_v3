"""
Django management command to audit and safely remediate duplicate leads in the database.
Supports:
--dry-run: Lists all duplicate groups and shows proposed merges without database changes.
--execute: Safely executes atomic merge of duplicates into primary leads with full audit logging.
"""
import sys
from django.core.management.base import BaseCommand
from django.db import transaction
from django.db.models import Count
from leads.models import Lead
from leads.normalizers import normalize_phone_number
from leads.merge_service import LeadMergeService

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')


class Command(BaseCommand):
    help = "Detect, inspect, and safely remediate duplicate leads."

    def add_arguments(self, parser):
        parser.add_argument(
            '--execute',
            action='store_true',
            help='Execute the remediation and commit changes to the database.',
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Simulate remediation without altering the database (default).',
        )

    def handle(self, *args, **options):
        execute_mode = options.get('execute', False)
        dry_run = not execute_mode

        self.stdout.write(self.style.MIGRATE_HEADING(
            f"=== CRM DUPLICATE LEAD REMEDIATION ENGINE ({'EXECUTE' if execute_mode else 'DRY RUN'}) ==="
        ))

        # Group leads by normalized phone
        all_leads = Lead.objects.all().order_by('id')
        phone_groups = {}
        for lead in all_leads:
            norm = normalize_phone_number(lead.phone)
            if not norm:
                continue
            phone_groups.setdefault(norm, []).append(lead)

        duplicate_groups = {k: v for k, v in phone_groups.items() if len(v) > 1}
        self.stdout.write(f"Found {len(duplicate_groups)} duplicate phone groups.")

        total_merged = 0

        for norm_phone, lead_list in duplicate_groups.items():
            self.stdout.write(f"\n--- Group for Phone: {norm_phone} ({len(lead_list)} leads) ---")

            # Selection algorithm:
            # 1. Lead with active enrollment
            # 2. Lead with most activities/calls/followups
            # 3. Oldest lead (created_at ASC)
            def score_lead(l):
                score = 0
                if hasattr(l, 'enrollment'):
                    score += 1000
                score += getattr(l, 'calls', Lead.objects.none()).count() * 10
                score += getattr(l, 'followups', Lead.objects.none()).count() * 10
                return score

            sorted_leads = sorted(
                lead_list,
                key=lambda l: (score_lead(l), -(l.created_at.timestamp() if l.created_at else 0)),
                reverse=True
            )

            primary = sorted_leads[0]
            duplicates = sorted_leads[1:]

            self.stdout.write(
                self.style.SUCCESS(f"  [PRIMARY] Lead #{primary.id} - '{primary.name}' (Created: {primary.created_at})")
            )

            for dup in duplicates:
                self.stdout.write(
                    f"  [DUPLICATE] Lead #{dup.id} - '{dup.name}' (Created: {dup.created_at}) -> Merge into #{primary.id}"
                )

                if execute_mode:
                    with transaction.atomic():
                        report = LeadMergeService.merge_leads(primary, dup, dry_run=False)
                        self.stdout.write(self.style.SUCCESS(
                            f"    Successfully merged #{dup.id} into #{primary.id}: {report['fields_enriched']}"
                        ))
                        total_merged += 1
                else:
                    report = LeadMergeService.merge_leads(primary, dup, dry_run=True)
                    self.stdout.write(
                        f"    [DRY-RUN] Would enrich: {report['fields_enriched']}, reparent: {report['relations_reparented']}"
                    )
                    total_merged += 1

        self.stdout.write(self.style.MIGRATE_HEADING(
            f"\nRemediation {'completed' if execute_mode else 'simulation finished'}: {total_merged} duplicate records processed."
        ))

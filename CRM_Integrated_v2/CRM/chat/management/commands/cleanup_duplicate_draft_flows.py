from django.core.management.base import BaseCommand
from django.db.models import Q
from chat.models import AutomationFlow, AutomationFlowVersion, UserFlowSession


class Command(BaseCommand):
    help = "Prunes runaway duplicate draft workflows created by the recursive auto-fork bug."

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Simulate cleanup without deleting any records',
        )

    def handle(self, *args, **options):
        dry_run = options.get('dry_run', False)

        # Find workflows with redundant intermediate drafts
        # For each (business_account_id, normalized name), keep:
        # 1. Any published flow
        # 2. The single newest draft flow (with highest version/id)
        # Prune all older intermediate draft clones
        all_flows = AutomationFlow.objects.all().order_by('business_account_id', 'name', '-id')

        grouped = {}
        for f in all_flows:
            key = (f.business_account_id, (f.slug or f.name).strip().lower())
            grouped.setdefault(key, []).append(f)

        to_delete_ids = []

        for key, flow_list in grouped.items():
            drafts = [f for f in flow_list if f.status == AutomationFlow.STATUS_DRAFT]
            if len(drafts) > 1:
                # Keep the newest draft
                keep_draft = drafts[0]
                orphans = drafts[1:]
                for o in orphans:
                    # Safety check: make sure no active user sessions exist on this draft
                    active_sessions = UserFlowSession.objects.filter(flow=o).count()
                    if active_sessions == 0:
                        to_delete_ids.append(o.id)
                    else:
                        self.stdout.write(self.style.WARNING(f"Skipping draft {o.id} because it has {active_sessions} active sessions."))

        self.stdout.write(f"Found {len(to_delete_ids)} runaway duplicate draft flows to prune.")

        if to_delete_ids:
            if dry_run:
                self.stdout.write(self.style.NOTICE(f"[DRY RUN] Would delete IDs: {to_delete_ids[:10]}... (total {len(to_delete_ids)})"))
            else:
                # Delete version links if any
                AutomationFlowVersion.objects.filter(flow_id__in=to_delete_ids).delete()
                deleted_count, _ = AutomationFlow.objects.filter(id__in=to_delete_ids).delete()
                self.stdout.write(self.style.SUCCESS(f"Successfully pruned {deleted_count} duplicate draft flows."))
        else:
            self.stdout.write(self.style.SUCCESS("No duplicate draft flows found to prune."))

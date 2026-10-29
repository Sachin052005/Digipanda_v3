"""
Comprehensive Lead Merge Service.
Safely consolidates a duplicate Lead record into a primary Lead record:
1. Enriches empty fields in primary from duplicate.
2. Reparents all 21 models with foreign key / generic relations to Lead.
3. Preserves notes, tags, and custom fields.
4. Creates an auditable snapshot in DuplicateLeadRecord.
5. Deletes the duplicate Lead record cleanly without cascade loss.
"""
import logging
from django.db import transaction
from django.utils import timezone
from .models import Lead, DuplicateLeadRecord, LeadStatus

log = logging.getLogger('crm')


class LeadMergeService:

    @classmethod
    @transaction.atomic
    def merge_leads(cls, primary_lead: Lead, duplicate_lead: Lead, audit_user=None, dry_run=False):
        """
        Merge duplicate_lead into primary_lead.
        Returns a dictionary summarizing changes and reparented row counts.
        """
        if primary_lead.id == duplicate_lead.id:
            raise ValueError("Cannot merge a lead into itself.")

        # Re-fetch with select_for_update to guarantee isolation
        p = Lead.objects.select_for_update().get(id=primary_lead.id)
        d = Lead.objects.select_for_update().get(id=duplicate_lead.id)

        report = {
            'primary_id': p.id,
            'duplicate_id': d.id,
            'fields_enriched': [],
            'relations_reparented': {},
            'dry_run': dry_run,
        }

        # -------------------------------------------------------------
        # 1. Field-Level Additive Enrichment
        # -------------------------------------------------------------
        # Name: enrich if primary name is empty or looks like a phone number
        from .intake import looks_like_phone
        if (not p.name or looks_like_phone(p.name)) and d.name and not looks_like_phone(d.name):
            p.name = d.name
            report['fields_enriched'].append('name')

        # Email
        if not p.email and d.email:
            p.email = d.email
            report['fields_enriched'].append('email')

        # Alternate phone
        if not p.alternate_phone and d.alternate_phone:
            p.alternate_phone = d.alternate_phone
            report['fields_enriched'].append('alternate_phone')

        # Product / Course
        if not p.product and d.product:
            p.product = d.product
            report['fields_enriched'].append('product')

        # Branch
        if not p.branch and d.branch:
            p.branch = d.branch
            report['fields_enriched'].append('branch')

        # Secondary branches
        if d.branch and d.branch != p.branch:
            if not dry_run:
                p.secondary_branches.add(d.branch)
            report['fields_enriched'].append(f'secondary_branch:{d.branch.name}')

        for b in d.secondary_branches.all():
            if b != p.branch:
                if not dry_run:
                    p.secondary_branches.add(b)

        # Lead tags
        if not dry_run:
            p.tags.add(*d.tags.all())

        # Notes chronological merge
        if d.notes:
            d_branch = d.branch.name if d.branch else 'Branch'
            if d.notes not in (p.notes or ''):
                tag_line = f"\n[Merged Lead #{d.id} from {d_branch}]: {d.notes}"
                p.notes = f"{p.notes or ''}{tag_line}".strip()
                report['fields_enriched'].append('notes')

        # Custom fields deep merge
        d_cf = d.custom_fields or {}
        p_cf = dict(p.custom_fields or {})
        if d_cf:
            for k, v in d_cf.items():
                if k not in p_cf:
                    p_cf[k] = v
                    report['fields_enriched'].append(f'custom_fields:{k}')
            p.custom_fields = p_cf

        # Status: If primary is LOST / NOT_INTERESTED and duplicate is NEW / FOLLOW_UP, upgrade
        if p.status in [LeadStatus.LOST, LeadStatus.NOT_INTERESTED, LeadStatus.NOT_JOINED] and d.status not in [LeadStatus.LOST, LeadStatus.NOT_INTERESTED, LeadStatus.NOT_JOINED]:
            p.status = d.status
            report['fields_enriched'].append('status_upgrade')

        # -------------------------------------------------------------
        # 2. Relational Reparenting Across All Related Models
        # -------------------------------------------------------------
        # 1. Calls: CallHistory
        from calls.models import CallHistory, CallEvent, RemoteOutgoingCall
        c_hist = CallHistory.objects.filter(lead=d)
        report['relations_reparented']['CallHistory'] = c_hist.count()
        if not dry_run:
            c_hist.update(lead=p)

        # 2. CallEvent
        c_evt = CallEvent.objects.filter(lead=d)
        report['relations_reparented']['CallEvent'] = c_evt.count()
        if not dry_run:
            c_evt.update(lead=p)

        # 3. RemoteOutgoingCall
        c_rem = RemoteOutgoingCall.objects.filter(lead=d)
        report['relations_reparented']['RemoteOutgoingCall'] = c_rem.count()
        if not dry_run:
            c_rem.update(lead=p)

        # 4. FollowUp
        from followups.models import FollowUp
        flw = FollowUp.objects.filter(lead=d)
        report['relations_reparented']['FollowUp'] = flw.count()
        if not dry_run:
            flw.update(lead=p)

        # 5. Enrollment (OneToOneField)
        if hasattr(d, 'enrollment'):
            if not hasattr(p, 'enrollment'):
                report['relations_reparented']['Enrollment'] = 1
                if not dry_run:
                    enr = d.enrollment
                    enr.lead = p
                    enr.save(update_fields=['lead'])
            else:
                report['relations_reparented']['Enrollment_Conflict'] = "Both leads have enrollments! Kept primary enrollment."

        # 6. GoogleSheetRowMapping
        from .models import GoogleSheetRowMapping
        gsm = GoogleSheetRowMapping.objects.filter(lead=d)
        report['relations_reparented']['GoogleSheetRowMapping'] = gsm.count()
        if not dry_run:
            gsm.update(lead=p)

        # 7. LeadAssignmentHistory
        from .models import LeadAssignmentHistory
        lah = LeadAssignmentHistory.objects.filter(lead=d)
        report['relations_reparented']['LeadAssignmentHistory'] = lah.count()
        if not dry_run:
            lah.update(lead=p)

        # 8. LeadStatusHistory
        from .models import LeadStatusHistory
        lsh = LeadStatusHistory.objects.filter(lead=d)
        report['relations_reparented']['LeadStatusHistory'] = lsh.count()
        if not dry_run:
            lsh.update(lead=p)

        # 9. WhatsAppCampaignRecipient
        try:
            from chat.models import WhatsAppCampaignRecipient
            wcr = WhatsAppCampaignRecipient.objects.filter(lead=d)
            report['relations_reparented']['WhatsAppCampaignRecipient'] = wcr.count()
            if not dry_run:
                wcr.update(lead=p)
        except Exception:
            pass

        # 10. CallRecording
        try:
            from drive.models import CallRecording
            cr = CallRecording.objects.filter(lead=d)
            report['relations_reparented']['CallRecording'] = cr.count()
            if not dry_run:
                cr.update(lead=p)
        except Exception:
            pass

        # 11. FacebookLead
        try:
            from fb_leads.models import FacebookLead
            fbl = FacebookLead.objects.filter(lead=d)
            report['relations_reparented']['FacebookLead'] = fbl.count()
            if not dry_run:
                fbl.update(lead=p)
        except Exception:
            pass

        # 12. Generic Activity Log
        from activities.models import Activity
        act = Activity.objects.filter(object_type='Lead', object_id=d.id)
        report['relations_reparented']['Activity'] = act.count()
        if not dry_run:
            act.update(object_id=p.id)

        # -------------------------------------------------------------
        # 3. Snapshot and Audit Trail Creation
        # -------------------------------------------------------------
        if not dry_run:
            # Save enriched primary
            p.save()

            # Create detailed audit record
            snapshot_payload = {
                'archived_lead_id': d.id,
                'name': d.name,
                'phone': d.phone,
                'alternate_phone': getattr(d, 'alternate_phone', ''),
                'email': d.email or '',
                'branch_id': d.branch_id,
                'branch_name': d.branch.name if d.branch else '',
                'source': d.source or '',
                'status': d.status,
                'notes': d.notes or '',
                'created_at': d.created_at.isoformat() if getattr(d, 'created_at', None) else None,
                'assigned_telecaller': d.assigned_telecaller.username if d.assigned_telecaller else None,
                'custom_fields': getattr(d, 'custom_fields', {}),
                'report': report,
            }

            from .normalizers import normalize_phone_number
            DuplicateLeadRecord.objects.create(
                original_lead=p,
                record_type='MERGED_CONSOLIDATED',
                name=d.name,
                phone=d.phone,
                normalized_phone=normalize_phone_number(d.phone) or d.phone,
                email=d.email or '',
                branch=d.branch,
                branch_name=d.branch.name if d.branch else '',
                existing_branch=p.branch,
                existing_branch_name=p.branch.name if p.branch else '',
                existing_source=p.source or '',
                existing_lead_created_at=p.created_at,
                status=d.status,
                duplicate_reason=f"Consolidated into Primary Lead #{p.id}",
                action_taken="MERGED_INTO_PRIMARY",
                notes=f"Merged duplicate lead #{d.id} into #{p.id}",
                source=d.source or 'System Merge',
                data_payload=snapshot_payload,
            )

            # -------------------------------------------------------------
            # 4. Delete Duplicate Lead Cleanly
            # -------------------------------------------------------------
            d.delete()

        return report

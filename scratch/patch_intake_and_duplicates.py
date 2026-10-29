# -*- coding: utf-8 -*-
"""
Patch intake.py and duplicates.py to support dedicated duplicate record_types and pre-merge snapshots.
"""

# 1. Update leads/duplicates.py
dup_path = 'D:/CRM_Integrated_v2/CRM_Integrated_v2/CRM/leads/duplicates.py'
with open(dup_path, 'r', encoding='utf-8') as f:
    dup_text = f.read()

old_delete_block = """            # Re-parent related foreign keys
            FollowUp.objects.filter(lead=dup).update(lead=primary_lead)
            CallHistory.objects.filter(lead=dup).update(lead=primary_lead)
            dup.sheet_mappings.update(lead=primary_lead)
            Activity.objects.filter(object_type='Lead', object_id=dup.id).update(object_id=primary_lead.id)

            # Delete the redundant duplicate record
            dup.delete()"""

new_delete_block = """            # Re-parent related foreign keys
            FollowUp.objects.filter(lead=dup).update(lead=primary_lead)
            CallHistory.objects.filter(lead=dup).update(lead=primary_lead)
            dup.sheet_mappings.update(lead=primary_lead)
            Activity.objects.filter(object_type='Lead', object_id=dup.id).update(object_id=primary_lead.id)

            # Snapshot the merged duplicate lead into DuplicateLeadRecord before deleting from Lead table
            from .models import DuplicateLeadRecord
            dup_payload = {
                'archived_lead_id': dup.id,
                'name': dup.name,
                'phone': dup.phone,
                'alternate_phone': getattr(dup, 'alternate_phone', ''),
                'email': dup.email or '',
                'branch_id': dup.branch_id,
                'branch_name': dup.branch.name if dup.branch else '',
                'secondary_branches': [b.name for b in dup.secondary_branches.all()],
                'channel': dup.channel.name if dup.channel else '',
                'source': dup.source or '',
                'status': dup.status,
                'rating': getattr(dup, 'rating', 0),
                'notes': dup.notes or '',
                'created_at': dup.created_at.isoformat() if getattr(dup, 'created_at', None) else None,
                'assigned_telecaller': dup.assigned_telecaller.username if dup.assigned_telecaller else None,
                'assigned_counselor': dup.assigned_counselor.username if dup.assigned_counselor else None,
                'custom_fields': getattr(dup, 'custom_fields', {}),
            }

            DuplicateLeadRecord.objects.create(
                original_lead=primary_lead,
                record_type='MERGED_ARCHIVE',
                name=dup.name,
                phone=dup.phone,
                normalized_phone=normalize_phone(dup.phone),
                email=dup.email or '',
                branch=dup.branch,
                branch_name=dup.branch.name if dup.branch else '',
                existing_branch=primary_lead.branch,
                existing_branch_name=primary_lead.branch.name if primary_lead.branch else '',
                existing_source=primary_lead.source or '',
                existing_lead_created_at=primary_lead.created_at,
                status=dup.status,
                duplicate_reason=f"Manually consolidated into Primary Lead #{primary_lead.id}",
                action_taken="MERGED_INTO_PRIMARY",
                notes=dup.notes or f"Merged into Lead #{primary_lead.id}",
                source=dup.source or 'Manual Merge',
                data_payload=dup_payload
            )

            # Delete the redundant duplicate record from active Lead table
            dup.delete()"""

if old_delete_block in dup_text:
    dup_text = dup_text.replace(old_delete_block, new_delete_block)
    with open(dup_path, 'w', encoding='utf-8') as f:
        f.write(dup_text)
    print("Successfully patched keep_single_lead_for_group in leads/duplicates.py!")
else:
    print("Warning: old_delete_block not found in leads/duplicates.py")


# 2. Update leads/intake.py
intake_path = 'D:/CRM_Integrated_v2/CRM_Integrated_v2/CRM/leads/intake.py'
with open(intake_path, 'r', encoding='utf-8') as f:
    intake_text = f.read()

# In Rule A (<= 10 days)
old_intake_rule_a = """                dup_rec = DuplicateLeadRecord.objects.create(
                    original_lead=existing_lead,
                    name=clean_name or existing_lead.name,"""

new_intake_rule_a = """                dup_rec = DuplicateLeadRecord.objects.create(
                    original_lead=existing_lead,
                    record_type='INCOMING_DUPLICATE',
                    name=clean_name or existing_lead.name,"""

if old_intake_rule_a in intake_text:
    intake_text = intake_text.replace(old_intake_rule_a, new_intake_rule_a)
    print("Patched Rule A in leads/intake.py!")

# In Rule B (> 10 days)
old_intake_rule_b = """                dup_rec = DuplicateLeadRecord.objects.create(
                    original_lead=existing_lead,
                    name=clean_name or existing_lead.name,"""

# The second occurrence is Rule B
parts = intake_text.split(old_intake_rule_a)
if len(parts) == 2:
    # After first replace, the second occurrence will still be old_intake_rule_a
    intake_text = parts[0] + new_intake_rule_a + parts[1].replace(
        old_intake_rule_a,
        """                dup_rec = DuplicateLeadRecord.objects.create(
                    original_lead=existing_lead,
                    record_type='REENQUIRY_DUPLICATE',
                    name=clean_name or existing_lead.name,"""
    )
    print("Patched Rule B in leads/intake.py!")

with open(intake_path, 'w', encoding='utf-8') as f:
    f.write(intake_text)
print("Updated leads/intake.py successfully!")

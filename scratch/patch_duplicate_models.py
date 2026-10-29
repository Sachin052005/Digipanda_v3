# -*- coding: utf-8 -*-
import os

path = 'D:/CRM_Integrated_v2/CRM_Integrated_v2/CRM/leads/models.py'
with open(path, 'r', encoding='utf-8') as f:
    text = f.read()

old_block = """class DuplicateLeadRecord(models.Model):
    \"\"\"
    Stores duplicate submission details and audit trail for a lead.
    Tracks cross-source duplicate detections under the 10-day rule.
    \"\"\"
    original_lead = models.ForeignKey(
        Lead,
        on_delete=models.CASCADE,
        related_name='duplicate_records'
    )"""

new_block = """class DuplicateLeadRecord(models.Model):
    \"\"\"
    Stores duplicate submission details and audit trail for a lead in a dedicated separate table.
    Tracks cross-source duplicate detections under the 10-day rule and pre-merge archives.
    \"\"\"
    RECORD_TYPE_CHOICES = [
        ('INCOMING_DUPLICATE', 'Incoming Duplicate (<= 10 Days)'),
        ('REENQUIRY_DUPLICATE', 'Re-enquiry Duplicate (> 10 Days)'),
        ('MERGED_ARCHIVE', 'Merged / Consolidated Lead Archive'),
        ('MANUAL_PROMOTED', 'Promoted to Independent Lead'),
    ]

    original_lead = models.ForeignKey(
        Lead,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='duplicate_records'
    )
    record_type = models.CharField(
        max_length=50,
        choices=RECORD_TYPE_CHOICES,
        default='INCOMING_DUPLICATE',
        db_index=True
    )"""

if old_block in text:
    text = text.replace(old_block, new_block)
    # Also add index on record_type and submitted_at
    old_meta = """    class Meta:
        ordering = ['-submitted_at']
        indexes = [
            models.Index(fields=['source', 'provider_event_id'], name='idx_dup_lead_src_event'),
            models.Index(fields=['normalized_phone'], name='idx_dup_lead_norm_phone'),
        ]"""

    new_meta = """    class Meta:
        ordering = ['-submitted_at']
        indexes = [
            models.Index(fields=['source', 'provider_event_id'], name='idx_dup_lead_src_event'),
            models.Index(fields=['normalized_phone'], name='idx_dup_lead_norm_phone'),
            models.Index(fields=['record_type', 'submitted_at'], name='idx_dup_lead_type_sub'),
        ]"""
    if old_meta in text:
        text = text.replace(old_meta, new_meta)
    with open(path, 'w', encoding='utf-8') as f:
        f.write(text)
    print("Successfully patched leads/models.py DuplicateLeadRecord!")
else:
    print("Error: old_block not found in leads/models.py")

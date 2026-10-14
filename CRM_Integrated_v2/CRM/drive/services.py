"""
Call recording helpers (the Google Drive folder sync was removed; recordings come from the
CRM Call Sync Android app).

    find_lead_by_phone()                  lead for a 10-digit number (phone or alternate phone)
    retry_matching_unmatched_recordings() link UNMATCHED recordings to leads created later
    get_user_recordings_queryset()        recordings a user may see / play (role-scoped)
"""
import logging

from django.db.models import Q

from leads.duplicates import normalize_phone
from leads.models import Lead

from .models import CallRecording

logger = logging.getLogger('crm')


def find_lead_by_phone(normalized_phone: str):
    """
    Searches the CRM Lead database for a lead matching the normalized 10-digit mobile number.
    Checks primary phone and alternate phone.
    """
    if not normalized_phone or len(normalized_phone) < 10:
        return None

    lead = Lead.objects.filter(
        Q(phone=normalized_phone) |
        Q(phone=f"+91{normalized_phone}") |
        Q(phone=f"+91 {normalized_phone}") |
        Q(phone=f"0{normalized_phone}") |
        Q(phone__endswith=normalized_phone) |
        Q(alternate_phone=normalized_phone) |
        Q(alternate_phone__endswith=normalized_phone)
    ).order_by('pk').first()
    if lead:
        return lead

    # Numbers formatted with spaces/dashes
    candidates = Lead.objects.filter(
        Q(phone__icontains=normalized_phone[-10:]) |
        Q(alternate_phone__icontains=normalized_phone[-10:])
    )
    for c in candidates:
        if normalize_phone(c.phone) == normalized_phone or normalize_phone(c.alternate_phone) == normalized_phone:
            return c
    return None


def retry_matching_unmatched_recordings(user=None) -> int:
    """Links UNMATCHED recordings to leads that exist now. Returns how many were matched."""
    from calls.sync_services import find_lead_by_phone as find_any_format
    matched_count = 0
    for rec in CallRecording.objects.filter(match_status='UNMATCHED').exclude(normalized_mobile_number=''):
        lead = find_any_format(rec.normalized_mobile_number)
        if lead:
            rec.lead = lead
            rec.match_status = 'MATCHED'
            rec.unmatched_reason = ''
            rec.save(update_fields=['lead', 'match_status', 'unmatched_reason', 'updated_at'])
            matched_count += 1
    return matched_count


def get_user_recordings_queryset(user):
    """
    Recordings a user may see (same rules as playback in drive.views.drive_stream_recording):
    - ADMIN: all (matched and unmatched)
    - SALES_HEAD: leads / telecallers in the sales head's branches
    - BRANCH_HEAD: leads / telecallers in their branch
    - COUNSELOR: leads assigned to them
    - TELECALLER: recordings from their phone, or of leads assigned to them
    """
    if not user.is_authenticated:
        return CallRecording.objects.none()
    base = CallRecording.objects.select_related('lead', 'telecaller')

    if user.is_admin_user:
        return base.all()

    if user.is_sales_head_user:
        from accounts.permissions import get_accessible_branch_ids
        branch_ids = get_accessible_branch_ids(user)
        return base.filter(
            Q(lead__assigned_sales_head=user) |
            Q(lead__branch_id__in=branch_ids) |
            Q(telecaller__branch_id__in=branch_ids)
        ).distinct()

    if user.is_branch_head_user:
        return base.filter(Q(lead__branch_id=user.branch_id) | Q(telecaller__branch_id=user.branch_id)).distinct()

    if user.is_counselor_user:
        return base.filter(lead__assigned_counselor=user)

    if user.is_telecaller_user:
        return base.filter(Q(telecaller=user) | Q(lead__assigned_telecaller=user)).distinct()

    return CallRecording.objects.none()

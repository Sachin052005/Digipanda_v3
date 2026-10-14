"""
One way for outside channels to create or update CRM leads: WhatsApp chats, Facebook Lead Ads,
Google Ads calls (CRM Call Sync app).

    intake_lead()            create a new lead, or update the existing one for that phone number
    direct_assign()          give a lead to one telecaller (history + counters + activity)
    system_change_status()   status change made by automation (no logged-in user)
    resolve_branch()         CRM Branch from free text ("Velachery", "T Nagar branch", ...)
    resolve_product()        CRM Product (course) from free text

Rules (same as the rest of the CRM):
- One lead per phone number: phone OR alternate phone, last 10 digits, any format.
- First source wins: an existing lead keeps its source, status, telecaller and branch.
  The new touch is added to its timeline (lead.notes) and Activity log.
- Blanks are filled, team edits are never overwritten.
- A NEW lead is assigned with the branch percentage engine (leads.assignment.assign_new_lead).
  No branch / no 100% setup -> "Pending Assignment", exactly like Google Sheet / Form leads.
"""
import logging

from django.db.models import Count, F, Q
from django.utils import timezone

from accounts.models import User, UserRole
from activities.utils import log_activity
from branches.models import Branch

from dataclasses import dataclass
from typing import Any, Optional
from django.db import transaction
from .models import (
    Lead, LeadAssignmentHistory, LeadOwnerType, LeadStatus,
    LeadStatusHistory, TelecallerLeadSetup, DuplicateLeadRecord
)

log = logging.getLogger('crm')


@dataclass
class IntakeResult:
    lead: Any
    created: bool
    action_taken: str  # 'CREATED_NEW', 'RETAINED_WITHIN_10_DAYS', 'UPDATED_AFTER_10_DAYS', 'IDEMPOTENT_IGNORED'
    duplicate_record: Optional[Any] = None
    field_changes: Optional[dict] = None
    elapsed_days: Optional[float] = None

    def __iter__(self):
        yield self.lead
        yield self.created


# ------------------------------------------------------------------ small helpers


def _sync():
    from calls import sync_services
    return sync_services


def phone10(raw):
    return _sync().phone10(raw)


def find_lead_by_phone(raw):
    return _sync().find_lead_by_phone(raw)


def add_note(lead, text):
    return _sync().add_lead_note(lead, text)


def looks_like_phone(value):
    value = str(value or '').strip()
    return bool(value) and all(ch.isdigit() or ch in '+-() ' for ch in value)


def get_channel(name):
    """The CRM Channel with this name (created if missing, e.g. 'WhatsApp', 'Facebook', 'Google Ads')."""
    if not name:
        return None
    from lead_channels.models import Channel
    channel = Channel.objects.filter(name__iexact=name).first()
    if channel is None:
        channel = Channel.objects.create(name=name)
    return channel


def resolve_branch(value):
    """Match free text to a CRM branch: exact name, then 'contains' either way. None if no match."""
    text = str(value or '').strip()
    if not text:
        return None
    branches = list(Branch.objects.all())
    low = text.lower()
    for b in branches:
        if b.name.lower() == low:
            return b
    norm = lambda s: ''.join(ch for ch in s.lower() if ch.isalnum())
    nlow = norm(text)
    for b in branches:
        nb = norm(b.name)
        if nb and (nb in nlow or nlow in nb):
            return b
    return None


def resolve_product(value):
    """Match a course name to a CRM Product. None if no match."""
    from products.models import Product
    text = str(value or '').strip()
    if not text:
        return None
    return (Product.objects.filter(name__iexact=text).first()
            or Product.objects.filter(name__icontains=text).first()
            or next((p for p in Product.objects.all() if p.name and p.name.lower() in text.lower()), None))


def default_branch(setting_name):
    from django.conf import settings
    name = getattr(settings, setting_name, '') or ''
    return Branch.objects.filter(name__iexact=name.strip()).first() if name.strip() else None


def branch_sales_head(branch):
    """Same choice as leads.assignment: the branch's sales head with the fewest leads."""
    if branch is None:
        return None
    return (
        User.objects.filter(role=UserRole.SALES_HEAD, branch_access__branch=branch, is_active=True)
        .annotate(cnt=Count('manager_leads')).order_by('cnt', 'id').first()
    )


def notify(user, title, message, kind='info'):
    if user is None:
        return
    try:
        from activities.services import create_notification
        create_notification(recipient=user, title=title, message=message, notification_type=kind)
    except Exception:
        log.exception("Notification failed for %s", user)


# ------------------------------------------------------------------ assignment / status

def direct_assign(lead, telecaller, reason, by=None):
    """Assign a lead to one telecaller (keeps CRM bookkeeping consistent with assign_new_lead)."""
    previous = lead.assigned_telecaller
    branch = lead.branch or telecaller.branch
    lead.branch = branch
    lead.assigned_telecaller = telecaller
    lead.assigned_sales_head = lead.assigned_sales_head or branch_sales_head(branch)
    lead.current_owner_type = LeadOwnerType.TELECALLER
    lead.assignment_status = 'Assigned'
    lead.pending_assignment_reason = ''
    lead.assigned_at = timezone.now()
    lead.save(update_fields=['branch', 'assigned_telecaller', 'assigned_sales_head', 'current_owner_type',
                             'assignment_status', 'pending_assignment_reason', 'assigned_at', 'updated_at'])
    LeadAssignmentHistory.objects.create(
        lead=lead, from_user=previous, to_user=telecaller,
        from_role=UserRole.TELECALLER if previous else '', to_role=UserRole.TELECALLER,
        branch=branch, reason=reason[:255],
        assigned_by=by if getattr(by, 'is_authenticated', False) else None,
    )
    if branch is not None:
        TelecallerLeadSetup.objects.filter(telecaller=telecaller, branch=branch).update(
            current_leads_assigned=F('current_leads_assigned') + 1, updated_at=timezone.now())
    name = telecaller.get_full_name() or telecaller.username
    log_activity(user=by or telecaller, action="Lead Auto-Assigned",
                 description=f"Lead '{lead.name}' assigned to {name} ({reason}).",
                 object_type="Lead", object_id=lead.pk)
    return True


def auto_assign(lead, source, by=None):
    """Branch percentage engine. Returns True if the lead got a telecaller."""
    from .assignment import assign_new_lead
    return assign_new_lead(lead, branch=lead.branch, source=source, triggered_by=by)


def system_change_status(lead, new_status, remarks=''):
    """Status change made by an automation (no user): history row + same side effects as the CRM."""
    valid = dict(LeadStatus.choices)
    if new_status not in valid:
        # accept labels case-insensitively ("follow-up", "Interested")
        match = next((v for v in valid if v.lower() == str(new_status).strip().lower()), None)
        if match is None:
            raise ValueError(f"Unknown lead status '{new_status}'")
        new_status = match
    old = lead.status
    if old == new_status:
        return False
    lead.status = new_status
    lead.save(update_fields=['status', 'updated_at'])
    LeadStatusHistory.objects.create(lead=lead, old_status=old, new_status=new_status, changed_by=None,
                                     remarks=remarks[:1000])
    if new_status == LeadStatus.VISIT_SCHEDULED and not lead.assigned_counselor_id:
        from .handoff_service import auto_handoff_lead_to_counselor
        auto_handoff_lead_to_counselor(lead, triggered_by=None)
    return True


# ------------------------------------------------------------------ intake

def intake_lead(
    *,
    phone,
    source,
    channel_name='',
    name='',
    email='',
    branch=None,
    product=None,
    note='',
    activity_user=None,
    provider_event_id=None,
    incoming_timestamp=None,
    data_payload=None,
):
    """
    Centralized cross-source lead intake and duplicate governance engine.
    Returns an IntakeResult (which unpacks as (lead, created) for backward compatibility).

    Business Rules:
    1. Phone normalization to clean 10 digits; cross-branch matching on phone & alternate_phone.
    2. Idempotency: suppresses duplicate updates/notifications if provider_event_id already exists.
    3. Concurrency: atomic transaction with select_for_update() row lock on existing lead.
    4. <= 10 Days: Preserves existing lead untouched (no branch change, no status change, no reassignment).
       Records DuplicateLeadRecord with action_taken='RETAINED_WITHIN_10_DAYS' and notifies assigned staff.
    5. > 10 Days: Preserves existing lead ID and history. Updates branch if changed, fills blank fields,
       reopens status to NEW, appends re-enquiry timeline note, re-assigns if branch changed,
       records DuplicateLeadRecord with action_taken='UPDATED_AFTER_10_DAYS' and field_changes,
       and notifies staff via transaction.on_commit.
    6. No match: Creates new lead, auto-assigns via branch engine, notifies telecaller,
       action_taken='CREATED_NEW'.
    """
    raw_phone = str(phone or '').strip()
    number = phone10(phone)
    if not number:
        raise ValueError(f"Invalid phone number: {phone!r}")

    clean_name = '' if looks_like_phone(name) else str(name or '').strip()[:150]
    clean_email = str(email or '').strip().lower()[:254]
    clean_event_id = str(provider_event_id).strip() if provider_event_id else None

    # Step 1: Idempotency Check per source
    if clean_event_id:
        existing_audit = DuplicateLeadRecord.objects.filter(
            source=source,
            provider_event_id=clean_event_id
        ).select_related('original_lead').first()
        if existing_audit:
            log.info("Idempotent event %s for source %s ignored.", clean_event_id, source)
            return IntakeResult(
                lead=existing_audit.original_lead,
                created=False,
                action_taken="IDEMPOTENT_IGNORED",
                duplicate_record=existing_audit,
                elapsed_days=existing_audit.elapsed_days,
                field_changes={},
            )

    # Step 2: Atomic Transaction with Concurrency Lock
    with transaction.atomic():
        target_10 = number[-10:] if len(number) >= 10 else number
        match_q = Q(phone=number) | Q(phone__endswith=target_10) | Q(alternate_phone__endswith=target_10)

        existing_lead = (
            Lead.objects.select_for_update()
            .filter(match_q)
            .order_by('id')
            .first()
        )

        if existing_lead is None and clean_email:
            existing_lead = (
                Lead.objects.select_for_update()
                .filter(email__iexact=clean_email)
                .order_by('id')
                .first()
            )

        if existing_lead is None:
            tail = number[-4:]
            for cand in Lead.objects.select_for_update().filter(Q(phone__endswith=tail) | Q(alternate_phone__endswith=tail)).order_by('id'):
                if phone10(cand.phone) == number or phone10(cand.alternate_phone) == number:
                    existing_lead = cand
                    break


        now_ts = incoming_timestamp or timezone.now()

        # Step 3: Handle Existing Match (10-Day Rule)
        if existing_lead is not None:
            # Timestamp-based elapsed calculation using original incoming timestamp
            elapsed_seconds = (now_ts - existing_lead.created_at).total_seconds()
            elapsed_days = max(0.0, elapsed_seconds / 86400.0)

            # -------------------------------------------------------------
            # RULE A: <= 10 Days -> RETAINED_WITHIN_10_DAYS
            # -------------------------------------------------------------
            if elapsed_days <= 10.0:
                dup_rec = DuplicateLeadRecord.objects.create(
                    original_lead=existing_lead,
                    name=clean_name or existing_lead.name,
                    phone=raw_phone or existing_lead.phone,
                    normalized_phone=number,
                    email=clean_email or existing_lead.email,
                    branch=branch,
                    branch_name=branch.name if branch else (data_payload.get('branch_name', '') if isinstance(data_payload, dict) else ''),
                    existing_branch=existing_lead.branch,
                    existing_branch_name=existing_lead.branch.name if existing_lead.branch else '',
                    existing_source=existing_lead.source,
                    existing_lead_created_at=existing_lead.created_at,
                    elapsed_days=round(elapsed_days, 2),
                    status=existing_lead.status,
                    duplicate_reason=f"Duplicate submission within 10 days ({round(elapsed_days, 1)} days elapsed since original).",
                    action_taken="RETAINED_WITHIN_10_DAYS",
                    field_changes={},
                    notes=note or f"Duplicate submission from {source} within 10 days.",
                    source=source,
                    provider_event_id=clean_event_id,
                    processing_status="PROCESSED",
                    notification_status="PENDING",
                    data_payload=data_payload if isinstance(data_payload, dict) else {},
                )

                log_activity(
                    user=activity_user,
                    action="Duplicate Lead Retained (<=10 Days)",
                    description=(
                        f"Duplicate submission for lead '{existing_lead.name}' ({existing_lead.phone}) from {source} "
                        f"detected within 10 days ({round(elapsed_days, 1)} days). Original lead #{existing_lead.id} retained unchanged."
                    ),
                    object_type="Lead",
                    object_id=existing_lead.pk
                )

                if note:
                    add_note(existing_lead, note)


                # Safe notification via transaction.on_commit
                recipient = (
                    existing_lead.assigned_telecaller
                    or existing_lead.assigned_sales_head
                    or branch_sales_head(existing_lead.branch)
                )
                if recipient:
                    def _dispatch_notify_dup(recip=recipient, rec_id=dup_rec.id, lead_id=existing_lead.id,
                                             lead_name=existing_lead.name, lead_ph=existing_lead.phone,
                                             src=source, days=round(elapsed_days, 1)):
                        try:
                            from activities.services import create_notification
                            create_notification(
                                recipient=recip,
                                title=f"Duplicate Lead Submission ({src})",
                                message=f"Duplicate submission for lead '{lead_name}' ({lead_ph}) was detected within 10 days ({days} days elapsed) from {src}.",
                                notification_type="duplicate_lead",
                                link=f"/admin/leads/{lead_id}/"
                            )
                            DuplicateLeadRecord.objects.filter(id=rec_id).update(notification_status="SENT")
                        except Exception:
                            log.exception("Notification dispatch failed for duplicate lead %s", lead_id)
                    transaction.on_commit(_dispatch_notify_dup)

                return IntakeResult(
                    lead=existing_lead,
                    created=False,
                    action_taken="RETAINED_WITHIN_10_DAYS",
                    duplicate_record=dup_rec,
                    elapsed_days=elapsed_days,
                    field_changes={},
                )

            # -------------------------------------------------------------
            # RULE B: > 10 Days -> UPDATED_AFTER_10_DAYS (Preserve Lead ID)
            # -------------------------------------------------------------
            else:
                field_changes = {}
                old_branch = existing_lead.branch
                branch_changed = False

                if branch and existing_lead.branch != branch:
                    field_changes['branch'] = {
                        'old': old_branch.name if old_branch else None,
                        'new': branch.name
                    }
                    if old_branch:
                        existing_lead.secondary_branches.add(old_branch)
                    existing_lead.branch = branch
                    branch_changed = True

                if clean_name and (not existing_lead.name or looks_like_phone(existing_lead.name)):
                    field_changes['name'] = {'old': existing_lead.name, 'new': clean_name}
                    existing_lead.name = clean_name

                if clean_email and not existing_lead.email:
                    field_changes['email'] = {'old': existing_lead.email, 'new': clean_email}
                    existing_lead.email = clean_email

                if product and not existing_lead.product:
                    field_changes['product'] = {'old': None, 'new': product.name}
                    existing_lead.product = product

                if channel_name and not existing_lead.channel:
                    chan = get_channel(channel_name)
                    if chan:
                        field_changes['channel'] = {'old': None, 'new': chan.name}
                        existing_lead.channel = chan

                old_status = existing_lead.status
                if old_status != LeadStatus.NEW:
                    field_changes['status'] = {'old': old_status, 'new': LeadStatus.NEW}
                    existing_lead.status = LeadStatus.NEW
                    LeadStatusHistory.objects.create(
                        lead=existing_lead,
                        old_status=old_status,
                        new_status=LeadStatus.NEW,
                        changed_by=activity_user if getattr(activity_user, 'is_authenticated', False) else None,
                        remarks=f"Re-enquiry after {round(elapsed_days, 1)} days via {source}"
                    )

                timeline_note = f"[Re-Enquiry - {source} ({round(elapsed_days, 1)} days later)]: {note or 'Re-submitted lead details'}"
                add_note(existing_lead, timeline_note)

                existing_lead.save()

                if branch_changed or not existing_lead.assigned_telecaller_id:
                    auto_assign(existing_lead, source, by=activity_user)
                    existing_lead.refresh_from_db()
                    if existing_lead.assigned_telecaller:
                        field_changes['assigned_telecaller'] = {
                            'new': existing_lead.assigned_telecaller.username
                        }

                log_activity(
                    user=activity_user,
                    action="Lead Re-enquiry (>10 Days)",
                    description=(
                        f"Existing lead #{existing_lead.id} '{existing_lead.name}' ({existing_lead.phone}) "
                        f"re-enquired via {source} after {round(elapsed_days, 1)} days. Preserved lead ID and updated record."
                    ),
                    object_type="Lead",
                    object_id=existing_lead.pk
                )

                dup_rec = DuplicateLeadRecord.objects.create(
                    original_lead=existing_lead,
                    name=clean_name or existing_lead.name,
                    phone=raw_phone or existing_lead.phone,
                    normalized_phone=number,
                    email=clean_email or existing_lead.email,
                    branch=existing_lead.branch,
                    branch_name=existing_lead.branch.name if existing_lead.branch else '',
                    existing_branch=old_branch,
                    existing_branch_name=old_branch.name if old_branch else '',
                    existing_source=existing_lead.source,
                    existing_lead_created_at=existing_lead.created_at,
                    elapsed_days=round(elapsed_days, 2),
                    status=existing_lead.status,
                    duplicate_reason=f"Re-enquiry after {round(elapsed_days, 1)} days. Lead updated and reactivated under existing ID #{existing_lead.id}.",
                    action_taken="UPDATED_AFTER_10_DAYS",
                    field_changes=field_changes,
                    notes=note or f"Re-enquiry from {source} after {round(elapsed_days, 1)} days.",
                    source=source,
                    provider_event_id=clean_event_id,
                    processing_status="PROCESSED",
                    notification_status="PENDING",
                    data_payload=data_payload if isinstance(data_payload, dict) else {},
                )

                recipient = (
                    existing_lead.assigned_telecaller
                    or existing_lead.assigned_sales_head
                    or branch_sales_head(existing_lead.branch)
                )
                if recipient:
                    def _dispatch_notify_upd(recip=recipient, rec_id=dup_rec.id, lead_id=existing_lead.id,
                                             lead_name=existing_lead.name, lead_ph=existing_lead.phone,
                                             src=source, days=round(elapsed_days, 1)):
                        try:
                            from activities.services import create_notification
                            create_notification(
                                recipient=recip,
                                title=f"Re-Enquiry Lead ({src})",
                                message=f"Lead '{lead_name}' ({lead_ph}) re-enquired after {days} days via {src}. Record reactivated and assigned.",
                                notification_type="lead_assigned",
                                link=f"/admin/leads/{lead_id}/"
                            )
                            DuplicateLeadRecord.objects.filter(id=rec_id).update(notification_status="SENT")
                        except Exception:
                            log.exception("Notification dispatch failed for re-enquiry lead %s", lead_id)
                    transaction.on_commit(_dispatch_notify_upd)

                return IntakeResult(
                    lead=existing_lead,
                    created=False,
                    action_taken="UPDATED_AFTER_10_DAYS",
                    duplicate_record=dup_rec,
                    elapsed_days=elapsed_days,
                    field_changes=field_changes,
                )

        # -----------------------------------------------------------------
        # RULE C: No Match -> CREATED_NEW
        # -----------------------------------------------------------------
        lead = Lead.objects.create(
            name=clean_name or number,
            phone=number,
            email=clean_email,
            channel=get_channel(channel_name) if channel_name else None,
            status=LeadStatus.NEW,
            source=source,
            branch=branch,
            product=product,
            current_owner_type=LeadOwnerType.UNASSIGNED,
            assignment_status='Unassigned',
        )
        add_note(lead, f"New lead from {source}" + (f" — {note}" if note else ''))
        log_activity(
            user=activity_user, action="Lead Created",
            description=f"New lead '{lead.name}' ({lead.phone}) from {source}"
                        + (f" for branch '{branch.name}'." if branch else "."),
            object_type="Lead", object_id=lead.pk
        )
        auto_assign(lead, source, by=activity_user)
        lead.refresh_from_db()

        if lead.assigned_telecaller_id:
            def _dispatch_notify_new(recip=lead.assigned_telecaller, l_id=lead.id,
                                     l_name=lead.name, l_ph=lead.phone, src=source):
                try:
                    notify(recip, f"New {src} lead",
                           f"{l_name} ({l_ph}) was assigned to you from {src}.", kind='lead_assigned')
                except Exception:
                    log.exception("New lead notification failed for lead %s", l_id)
            transaction.on_commit(_dispatch_notify_new)

        return IntakeResult(
            lead=lead,
            created=True,
            action_taken="CREATED_NEW",
            duplicate_record=None,
            elapsed_days=None,
            field_changes=None,
        )


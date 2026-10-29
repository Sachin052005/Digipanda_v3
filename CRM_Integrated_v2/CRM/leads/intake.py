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
    LeadStatusHistory, TelecallerLeadSetup, DuplicateLeadRecord, VisitorStatus
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


from .normalizers import normalize_phone_number, normalize_email
from .merge_service import LeadMergeService


def phone10(raw):
    normalized = normalize_phone_number(raw)
    if normalized and not normalized.startswith('+'):
        return normalized[-10:] if len(normalized) >= 10 else normalized
    return _sync().phone10(raw)


def find_lead_by_phone(raw):
    return _sync().find_lead_by_phone(raw)


def add_note(lead, text):
    return _sync().add_lead_note(lead, text)


def looks_like_phone(value):
    value = str(value or '').strip()
    return bool(value) and all(ch.isdigit() or ch in '+-() ' for ch in value)


TERMINAL_PROTECTED_STATUSES = ('Enrolled', 'Converted', 'Payment Completed', 'Joined')
PLACEHOLDER_NAMES = {'', 'n/a', 'na', 'null', 'none', 'undefined', 'unknown'}


def is_placeholder_name(val):
    """
    Returns True if the name is empty, placeholder, or generated from phone/source.
    """
    if not val:
        return True
    import re
    v = str(val).strip().lower()
    if v in PLACEHOLDER_NAMES:
        return True
    if looks_like_phone(val) or re.sub(r'\D', '', val) == val:
        return True
    if any(p in v for p in ('google sheets lead', 'walk-in lead', 'sheet lead', 'form lead', 'new lead', 'offline lead', 'lead (')):
        return True
    return False


def is_potential_family_member(incoming_name, existing_name):
    """
    Checks if an incoming name is substantially different from an existing contact's name,
    suggesting a sibling, parent, or family member sharing the same phone number.
    Returns True if both names are non-empty and have distinctly different first/given names.
    """
    import re
    if not incoming_name or not existing_name:
        return False
    if looks_like_phone(existing_name) or looks_like_phone(incoming_name):
        return False
    if is_placeholder_name(existing_name) or is_placeholder_name(incoming_name):
        return False
    in_clean = re.sub(r'[^\w\s]', '', str(incoming_name).lower()).strip()
    ex_clean = re.sub(r'[^\w\s]', '', str(existing_name).lower()).strip()
    in_words = in_clean.split()
    ex_words = ex_clean.split()
    if not in_words or not ex_words:
        return False

    stop_words = {'mr', 'mrs', 'ms', 'dr', 'master', 'baby'}
    while in_words and in_words[0] in stop_words:
        in_words.pop(0)
    while ex_words and ex_words[0] in stop_words:
        ex_words.pop(0)

    if not in_words or not ex_words:
        return False

    in_first = in_words[0]
    ex_first = ex_words[0]

    # If first names are identical, they represent the same person
    if in_first == ex_first:
        return False

    # If one first name is just an initial of the other (e.g. 'r' and 'rahul'), treat as same person
    if (len(in_first) == 1 and ex_first.startswith(in_first)) or (len(ex_first) == 1 and in_first.startswith(ex_first)):
        return False

    # Distinct given names sharing phone number -> Potential sibling / family member!
    return True


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


def get_product_display_name(p):
    if not p:
        return ''
    return getattr(p, 'name', str(p))

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


def direct_assign_counselor(lead, counselor, reason, by=None):
    """Assign a lead directly to a counselor (e.g. from phone receiver or front desk)."""
    previous = lead.assigned_counselor
    branch = lead.branch or counselor.branch
    lead.branch = branch
    lead.assigned_counselor = counselor
    lead.assigned_sales_head = lead.assigned_sales_head or branch_sales_head(branch)
    lead.current_owner_type = LeadOwnerType.COUNSELOR
    lead.assignment_status = 'Assigned'
    lead.pending_assignment_reason = ''
    lead.assigned_at = timezone.now()
    lead.save(update_fields=['branch', 'assigned_counselor', 'assigned_sales_head', 'current_owner_type',
                             'assignment_status', 'pending_assignment_reason', 'assigned_at', 'updated_at'])
    LeadAssignmentHistory.objects.create(
        lead=lead, from_user=previous, to_user=counselor,
        from_role=UserRole.COUNSELOR if previous else '', to_role=UserRole.COUNSELOR,
        branch=branch, reason=reason[:255],
        assigned_by=by if getattr(by, 'is_authenticated', False) else None,
    )
    name = counselor.get_full_name() or counselor.username
    log_activity(user=by or counselor, action="Lead Auto-Assigned",
                 description=f"Lead '{lead.name}' assigned to Counselor {name} ({reason}).",
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
    phone='',
    source='Intake',
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
    alternate_phone='',
    center_visit_date=None,
    visitor_status=None,
    token_number=None,
):
    """
    Centralized cross-source lead intake and duplicate governance engine.
    Returns an IntakeResult (which unpacks as (lead, created) for backward compatibility).

    Core Business Invariants:
    1. One Person == One Primary Lead Record across all intake pathways.
    2. The 10-day rule applies to branch assignment and reactivation routing only, NEVER duplicate creation.
    3. Blank incoming values never erase existing populated CRM fields.
    4. Terminal statuses ('Enrolled', 'Converted', 'Payment Completed') are strictly protected from status resets.
    5. Concurrency: atomic transaction with select_for_update() row lock on existing lead.
    6. <= 10 Days: Preserves existing lead branch; registers secondary branch; fills blank fields;
       records DuplicateLeadRecord with action_taken='RETAINED_WITHIN_10_DAYS' and notifies assigned staff.
    7. > 10 Days: Preserves existing lead ID and history. Updates branch if explicitly provided and changed;
       fills blank fields; reactivates status to NEW (unless Enrolled/Converted); appends re-enquiry timeline note;
       re-assigns if branch changed; records DuplicateLeadRecord with action_taken='UPDATED_AFTER_10_DAYS'.
    8. No match: Creates single new lead, auto-assigns via branch engine, action_taken='CREATED_NEW'.
    """
    raw_phone = str(phone or '').strip()
    number = phone10(phone) if phone else ''
    if not number and raw_phone.startswith('NoPhone-'):
        number = raw_phone
    if not number and raw_phone:
        norm_raw = normalize_phone_number(raw_phone)
        if norm_raw:
            number = norm_raw

    clean_name = '' if looks_like_phone(name) else str(name or '').strip()[:150]
    clean_email = normalize_email(email) or ''
    clean_event_id = str(provider_event_id).strip() if provider_event_id else None
    alt_phone_raw = str(alternate_phone or '').strip()
    norm_alt = normalize_phone_number(alt_phone_raw) if alt_phone_raw else ''

    # Normalize product/course if given as string
    if isinstance(product, str) and product.strip():
        resolved_prod = resolve_product(product)
        if resolved_prod:
            product = resolved_prod

    if not number and not clean_email:
        raise ValueError(f"At least a valid phone number or email address is required for lead intake (got phone={phone!r}, email={email!r}).")

    # Step 1: Idempotency Check per source
    if clean_event_id:
        existing_lead_by_event = Lead.objects.filter(
            custom_fields__provider_event_id=clean_event_id
        ).first()
        if not existing_lead_by_event:
            existing_audit = DuplicateLeadRecord.objects.filter(
                provider_event_id=clean_event_id
            ).select_related('original_lead').first()
            if existing_audit and existing_audit.original_lead:
                existing_lead_by_event = existing_audit.original_lead
        if existing_lead_by_event:
            log.info("Idempotent event %s for source %s ignored.", clean_event_id, source)
            return IntakeResult(
                lead=existing_lead_by_event,
                created=False,
                action_taken="IDEMPOTENT_IGNORED",
                duplicate_record=None,
                elapsed_days=0.0,
                field_changes={},
            )

    # Step 2: Atomic Transaction with Concurrency Lock
    with transaction.atomic():
        match_q = None
        if number:
            if number.startswith('+'):
                match_q = Q(normalized_phone=number) | Q(phone=number) | Q(alternate_phone=number)
            elif number.startswith('NoPhone-'):
                match_q = Q(phone=number)
            else:
                target_10 = number[-10:] if len(number) >= 10 else number
                match_q = Q(normalized_phone=target_10) | Q(phone=number) | Q(phone__endswith=target_10) | Q(alternate_phone__endswith=target_10)

        existing_lead = None
        if match_q:
            existing_lead = (
                Lead.objects.select_for_update()
                .filter(match_q)
                .order_by('id')
                .first()
            )

        lead_by_email = None
        if clean_email:
            lead_by_email = (
                Lead.objects.select_for_update()
                .filter(email__iexact=clean_email)
                .order_by('id')
                .first()
            )

        is_ambiguous_match = False
        if existing_lead and lead_by_email and existing_lead.id != lead_by_email.id:
            is_ambiguous_match = True

        if existing_lead is None and clean_email:
            existing_lead = lead_by_email

        if existing_lead is None and number and not number.startswith('+') and not number.startswith('NoPhone-'):
            tail = number[-4:]
            for cand in Lead.objects.select_for_update().filter(Q(phone__endswith=tail) | Q(alternate_phone__endswith=tail)).order_by('id'):
                if phone10(cand.phone) == number or phone10(cand.alternate_phone) == number:
                    existing_lead = cand
                    break

        now_ts = incoming_timestamp or timezone.now()

        # Step 3: Handle Existing Match (10-Day Rule)
        if existing_lead is not None:
            elapsed_seconds = (now_ts - existing_lead.created_at).total_seconds()
            elapsed_days = max(0.0, elapsed_seconds / 86400.0)

            # Check for family / sibling sharing contact
            is_family_member = is_potential_family_member(clean_name, existing_lead.name)

            # -------------------------------------------------------------
            # RULE A: <= 10 Days -> RETAINED_WITHIN_10_DAYS
            # -------------------------------------------------------------
            if elapsed_days <= 10.0:
                if is_ambiguous_match:
                    dup_action = "AMBIGUOUS_MATCH_FLAGGED"
                    dup_reason = (
                        f"Ambiguous match: Phone {number} matches Lead #{existing_lead.id} ('{existing_lead.name}') "
                        f"while Email {clean_email} matches Lead #{lead_by_email.id} ('{lead_by_email.name}'). Review required."
                    )
                elif is_family_member:
                    dup_action = "FAMILY_MEMBER_POTENTIAL_DUPLICATE"
                    dup_reason = (
                        f"Potential family member / sibling sharing phone {number}: Incoming name '{clean_name}' "
                        f"differs from student '{existing_lead.name}'. Preserved student record and flagged relationship."
                    )
                else:
                    dup_action = "RETAINED_WITHIN_10_DAYS"
                    dup_reason = f"Duplicate submission within 10 days ({round(elapsed_days, 1)} days elapsed since original)."

                dup_rec = DuplicateLeadRecord.objects.create(
                    original_lead=existing_lead,
                    record_type='INCOMING_DUPLICATE',
                    name=clean_name or existing_lead.name,
                    phone=raw_phone or existing_lead.phone,
                    normalized_phone=number or existing_lead.normalized_phone,
                    email=clean_email or existing_lead.email,
                    branch=branch,
                    branch_name=branch.name if branch else (data_payload.get('branch_name', '') if isinstance(data_payload, dict) else ''),
                    existing_branch=existing_lead.branch,
                    existing_branch_name=existing_lead.branch.name if existing_lead.branch else '',
                    existing_source=existing_lead.source,
                    existing_lead_created_at=existing_lead.created_at,
                    elapsed_days=round(elapsed_days, 2),
                    status=existing_lead.status,
                    duplicate_reason=dup_reason,
                    action_taken=dup_action,
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

                if is_family_member:
                    add_note(existing_lead, f"👨‍👩‍👧 Potential Family/Sibling Enquiry: Incoming name '{clean_name}' (course: {get_product_display_name(product) if product else 'N/A'}) submitted with same phone number. Verify relationship on call.")

                # Fill blank fields on existing lead if missing, and track new information
                filled_fields = []
                new_info_notes = []

                if clean_email and not existing_lead.email:
                    existing_lead.email = clean_email
                    filled_fields.append('email')
                elif clean_email and clean_email.lower() != (existing_lead.email or '').lower():
                    cf = dict(existing_lead.custom_fields or {})
                    cf['secondary_email'] = clean_email
                    existing_lead.custom_fields = cf
                    filled_fields.append('custom_fields')

                if not is_family_member and clean_name:
                    if is_placeholder_name(existing_lead.name):
                        existing_lead.name = clean_name
                        filled_fields.append('name')
                    elif clean_name != existing_lead.name:
                        cf = dict(existing_lead.custom_fields or {})
                        aliases = list(cf.get('aliases', []))
                        if clean_name not in aliases:
                            aliases.append(clean_name)
                            cf['aliases'] = aliases
                            existing_lead.custom_fields = cf
                            filled_fields.append('custom_fields')

                if norm_alt and not existing_lead.alternate_phone and norm_alt != existing_lead.phone:
                    existing_lead.alternate_phone = norm_alt
                    filled_fields.append('alternate_phone')

                if product:
                    if hasattr(product, 'pk'):
                        if not existing_lead.product:
                            existing_lead.product = product
                            filled_fields.append('product')
                        elif existing_lead.product_id != product.pk:
                            cf = dict(existing_lead.custom_fields or {})
                            cf['latest_course_enquiry'] = get_product_display_name(product)
                            cf['latest_course_enquiry_date'] = timezone.now().strftime('%Y-%m-%d %H:%M:%S')
                            existing_lead.custom_fields = cf
                            filled_fields.append('custom_fields')
                            prev_p = existing_lead.product.name if existing_lead.product else 'None'
                            new_info_notes.append(f"New course interest: {get_product_display_name(product)} (Previous: {prev_p})")
                    else:
                        cf = dict(existing_lead.custom_fields or {})
                        cf['latest_course_enquiry'] = str(product)
                        cf['latest_course_enquiry_date'] = timezone.now().strftime('%Y-%m-%d %H:%M:%S')
                        existing_lead.custom_fields = cf
                        filled_fields.append('custom_fields')
                        new_info_notes.append(f"Course interest: {product}")

                if branch:
                    if not existing_lead.branch:
                        existing_lead.branch = branch
                        filled_fields.append('branch')
                    elif existing_lead.branch_id != branch.id:
                        existing_lead.secondary_branches.add(branch)
                        cf = dict(existing_lead.custom_fields or {})
                        cf['latest_branch_enquiry'] = branch.name
                        cf['secondary_branch_name'] = branch.name
                        existing_lead.custom_fields = cf
                        filled_fields.append('custom_fields')
                        new_info_notes.append(f"Enquired via branch line: {branch.name}")

                if center_visit_date:
                    existing_lead.center_visit_date = center_visit_date
                    filled_fields.append('center_visit_date')
                if visitor_status:
                    existing_lead.visitor_status = visitor_status
                    filled_fields.append('visitor_status')
                if token_number:
                    existing_lead.token_number = token_number
                    filled_fields.append('token_number')

                # Stage protection: Never downgrade terminal/enrolled leads
                if existing_lead.status in TERMINAL_PROTECTED_STATUSES:
                    pass
                elif existing_lead.status in [LeadStatus.LOST, LeadStatus.NOT_INTERESTED, LeadStatus.NOT_JOINED]:
                    old_st = existing_lead.status
                    existing_lead.status = LeadStatus.FOLLOW_UP
                    filled_fields.append('status')
                    LeadStatusHistory.objects.create(
                        lead=existing_lead,
                        old_status=old_st,
                        new_status=LeadStatus.FOLLOW_UP,
                        changed_by=None,
                        remarks="Reopened due to incoming duplicate enquiry with new information"
                    )
                    new_info_notes.append(f"Reopened from {old_st} to Follow-up")

                if filled_fields:
                    filled_fields.append('updated_at')
                    existing_lead.save(update_fields=list(set(filled_fields)))

                if new_info_notes:
                    add_note(existing_lead, "🔔 Re-Enquiry Updates: " + "; ".join(new_info_notes))

                if isinstance(data_payload, dict) and data_payload:
                    try:
                        from .qualification import autofill_lead_qualification
                        autofill_lead_qualification(existing_lead, data_payload, source=source, preserve_manual_edits=True)
                    except Exception as e:
                        log.warning("Autofill qualification failed for duplicate lead %s: %s", existing_lead.id, e)

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
                    action_taken=dup_action,
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
                # If branch is not specified, preserve current branch (do not guess)

                if not is_family_member and clean_name:
                    if is_placeholder_name(existing_lead.name):
                        field_changes['name'] = {'old': existing_lead.name, 'new': clean_name}
                        existing_lead.name = clean_name
                    elif clean_name != existing_lead.name:
                        cf = dict(existing_lead.custom_fields or {})
                        aliases = list(cf.get('aliases', []))
                        if clean_name not in aliases:
                            aliases.append(clean_name)
                            cf['aliases'] = aliases
                            existing_lead.custom_fields = cf
                elif is_family_member:
                    add_note(existing_lead, f"👨‍👩‍👧 Potential Family/Sibling Re-enquiry: Incoming name '{clean_name}' differs from student '{existing_lead.name}'. Retained original student name.")

                if clean_email and not existing_lead.email:
                    field_changes['email'] = {'old': existing_lead.email, 'new': clean_email}
                    existing_lead.email = clean_email
                elif clean_email and clean_email.lower() != (existing_lead.email or '').lower():
                    cf = dict(existing_lead.custom_fields or {})
                    cf['secondary_email'] = clean_email
                    existing_lead.custom_fields = cf

                if norm_alt and not existing_lead.alternate_phone and norm_alt != existing_lead.phone:
                    existing_lead.alternate_phone = norm_alt

                if product:
                    if hasattr(product, 'pk'):
                        if not existing_lead.product:
                            field_changes['product'] = {'old': None, 'new': get_product_display_name(product)}
                            existing_lead.product = product
                        elif existing_lead.product_id != product.pk:
                            cf = dict(existing_lead.custom_fields or {})
                            cf['latest_course_enquiry'] = get_product_display_name(product)
                            cf['latest_course_enquiry_date'] = timezone.now().strftime('%Y-%m-%d %H:%M:%S')
                            existing_lead.custom_fields = cf
                            prev_p = existing_lead.product.name if existing_lead.product else 'None'
                            add_note(existing_lead, f"🔔 Re-enquiry for course: {get_product_display_name(product)} (Original: {prev_p})")
                    else:
                        cf = dict(existing_lead.custom_fields or {})
                        cf['latest_course_enquiry'] = str(product)
                        cf['latest_course_enquiry_date'] = timezone.now().strftime('%Y-%m-%d %H:%M:%S')
                        existing_lead.custom_fields = cf
                        add_note(existing_lead, f"🔔 Re-enquiry for course: {product}")

                if channel_name and not existing_lead.channel:
                    chan = get_channel(channel_name)
                    if chan:
                        field_changes['channel'] = {'old': None, 'new': chan.name}
                        existing_lead.channel = chan

                if center_visit_date:
                    existing_lead.center_visit_date = center_visit_date
                if visitor_status:
                    existing_lead.visitor_status = visitor_status
                if token_number:
                    existing_lead.token_number = token_number

                # Stage protection: Never downgrade terminal/enrolled leads to NEW
                old_status = existing_lead.status
                if old_status in TERMINAL_PROTECTED_STATUSES:
                    log.info("Lead #%s is in protected terminal status '%s'; preserving status during re-enquiry.", existing_lead.id, old_status)
                elif old_status != LeadStatus.NEW:
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

                if isinstance(data_payload, dict) and data_payload:
                    try:
                        from .qualification import autofill_lead_qualification
                        autofill_lead_qualification(existing_lead, data_payload, source=source, preserve_manual_edits=True)
                    except Exception as e:
                        log.warning("Autofill qualification failed for re-enquiry lead %s: %s", existing_lead.id, e)

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

                dup_action = "FAMILY_MEMBER_POTENTIAL_DUPLICATE" if is_family_member else "UPDATED_AFTER_10_DAYS"
                dup_reason = (
                    f"Re-enquiry with different student name '{clean_name}' (existing: '{existing_lead.name}') on phone {number}. "
                    f"Preserved original student record and flagged family relationship."
                    if is_family_member else
                    f"Re-enquiry after {round(elapsed_days, 1)} days. Lead updated and reactivated under existing ID #{existing_lead.id}."
                )
                dup_rec = DuplicateLeadRecord.objects.create(
                    original_lead=existing_lead,
                    record_type='REENQUIRY_DUPLICATE',
                    name=clean_name or existing_lead.name,
                    phone=raw_phone or existing_lead.phone,
                    normalized_phone=number or existing_lead.normalized_phone,
                    email=clean_email or existing_lead.email,
                    branch=existing_lead.branch,
                    branch_name=existing_lead.branch.name if existing_lead.branch else '',
                    existing_branch=old_branch,
                    existing_branch_name=old_branch.name if old_branch else '',
                    existing_source=existing_lead.source,
                    existing_lead_created_at=existing_lead.created_at,
                    elapsed_days=round(elapsed_days, 2),
                    status=existing_lead.status,
                    duplicate_reason=dup_reason,
                    action_taken=dup_action,
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
                    action_taken=dup_action,
                    duplicate_record=dup_rec,
                    elapsed_days=elapsed_days,
                    field_changes=field_changes,
                )

        # -----------------------------------------------------------------
        # RULE C: No Match -> CREATED_NEW
        # -----------------------------------------------------------------
        is_offline_lead = (
            str(source or '').strip().lower() in ('google sheets', 'walk-in', 'walk-in qr form') or
            str(channel_name or '').strip().lower() in ('google sheets', 'walk-in', 'walk-in qr form')
        )
        norm_phone_val = ''
        if number:
            norm_phone_val = number[-10:] if (len(number) >= 10 and not number.startswith('+') and not number.startswith('NoPhone-')) else number

        fallback_disp = number or clean_email or 'Lead'
        if len(fallback_disp) >= 10 and fallback_disp.isdigit():
            fallback_disp = fallback_disp[-10:]

        lead = Lead.objects.create(
            name=clean_name or f"Lead ({fallback_disp})",
            phone=number or raw_phone,
            normalized_phone=norm_phone_val,
            alternate_phone=norm_alt,
            email=clean_email,
            channel=get_channel(channel_name) if channel_name else None,
            status=LeadStatus.NEW,
            source=source,
            is_offline=is_offline_lead,
            branch=branch,
            product=product if hasattr(product, 'pk') else None,
            current_owner_type=LeadOwnerType.UNASSIGNED,
            assignment_status='Unassigned',
            center_visit_date=center_visit_date,
            visitor_status=visitor_status or VisitorStatus.WAITING,
            token_number=token_number or '',
        )
        if product and not hasattr(product, 'pk'):
            cf = dict(lead.custom_fields or {})
            cf['course_enquiry'] = str(product)
            lead.custom_fields = cf
            lead.save(update_fields=['custom_fields'])

        if isinstance(data_payload, dict) and data_payload:
            try:
                from .qualification import autofill_lead_qualification
                autofill_lead_qualification(lead, data_payload, source=source, preserve_manual_edits=False)
            except Exception as e:
                log.warning("Autofill qualification failed for new lead %s: %s", lead.id, e)

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

        if clean_event_id:
            cf = dict(lead.custom_fields or {})
            cf['provider_event_id'] = clean_event_id
            events = list(cf.get('provider_event_ids', []))
            if clean_event_id not in events:
                events.append(clean_event_id)
            cf['provider_event_ids'] = events
            lead.custom_fields = cf
            lead.save(update_fields=['custom_fields'])

        return IntakeResult(
            lead=lead,
            created=True,
            action_taken="CREATED_NEW",
            duplicate_record=None,
            elapsed_days=None,
            field_changes=None,
        )


class CentralizedLeadIntakeService:
    """
    Authoritative Centralized Service for Lead Ingestion, Intelligent Identity Matching,
    10-Day Branch Assignment Governance, and Progressive Field Enrichment.
    Ensures that One Person remains One Lead Record across all CRM intake sources.
    """
    @classmethod
    def ingest(
        cls,
        *,
        phone='',
        source='Intake',
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
        alternate_phone='',
        center_visit_date=None,
        visitor_status=None,
        token_number=None,
    ) -> IntakeResult:
        return intake_lead(
            phone=phone,
            source=source,
            channel_name=channel_name,
            name=name,
            email=email,
            branch=branch,
            product=product,
            note=note,
            activity_user=activity_user,
            provider_event_id=provider_event_id,
            incoming_timestamp=incoming_timestamp,
            data_payload=data_payload,
            alternate_phone=alternate_phone,
            center_visit_date=center_visit_date,
            visitor_status=visitor_status,
            token_number=token_number,
        )

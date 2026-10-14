"""
WhatsApp chats -> CRM leads (source "WhatsApp").

    lead_for_conversation()          the CRM lead for a chat (by phone number), or None
    ensure_lead_for_conversation()   every incoming WhatsApp message: create / touch the lead
    sync_answers()                   flow answers (question / buttons / list / save data) -> lead
    set_lead_status()                "Lead Status" automation step
    assign_lead()                    "Assign Telecaller" automation step
    conversations_for_user()         role-scoped chats for the inbox

Branch of a NEW WhatsApp lead: the WhatsApp number's CRM branch (Business Account -> CRM branch),
else settings.WHATSAPP_DEFAULT_BRANCH, else a branch the student picks in the flow
(variable branch / branch_name / location / selected_branch). Without a branch the lead is
"Pending Assignment" until one is known, exactly like other CRM leads.
"""
import logging
from datetime import timedelta

from django.db.models import Q
from django.utils import timezone

from accounts.models import UserRole
from leads import intake
from leads.models import Lead, LeadStatus

log = logging.getLogger('crm')

SOURCE = "WhatsApp"
CHANNEL = "WhatsApp"

# Flow variable name -> what it fills on the CRM lead. Anything else goes to the timeline.
NAME_KEYS = {'name', 'full_name', 'student_name', 'customer_name'}
EMAIL_KEYS = {'email', 'email_id'}
COURSE_KEYS = {'course', 'course_name', 'selected_course'}
BRANCH_KEYS = {'branch', 'branch_name', 'selected_branch', 'location', 'preferred_branch'}
SKIP_KEYS = {'course_id'}
SYNC_STATE_KEY = '_crm_synced'


def lead_for_conversation(conversation):
    if not conversation or not conversation.phone_number:
        return None
    return intake.find_lead_by_phone(conversation.phone_number)


def _branch_for(conversation):
    biz = getattr(conversation, 'business_account', None)
    if biz is not None and getattr(biz, 'crm_branch_id', None):
        return biz.crm_branch
    return intake.default_branch('WHATSAPP_DEFAULT_BRANCH')


def ensure_lead_for_conversation(conversation, conversation_created=False):
    """
    Called for every incoming WhatsApp message. Returns (lead, created).
    - New number           -> new WhatsApp lead (status New), auto-assigned in its branch
    - Number already a lead -> same lead (Facebook / Google Call / manual stay as they are);
                               a timeline line is added when a NEW chat starts
    """
    if not conversation.phone_number or not intake.phone10(conversation.phone_number):
        return None, False
    biz = conversation.business_account
    existing = lead_for_conversation(conversation)
    if existing is not None and not conversation_created:
        # Ongoing chat: nothing to record on every single message.
        if not existing.assigned_telecaller_id and not existing.branch_id:
            branch = _branch_for(conversation)
            if branch is not None:
                existing.branch = branch
                existing.save(update_fields=['branch', 'updated_at'])
                intake.auto_assign(existing, SOURCE)
        return existing, False

    note = "Started a WhatsApp chat" + (f" on {biz.name}" if biz else "")
    try:
        return intake.intake_lead(
            phone=conversation.phone_number,
            source=SOURCE,
            channel_name=CHANNEL,
            name=conversation.customer_name,
            branch=_branch_for(conversation),
            note=note,
            provider_event_id=f"wa_conv_{conversation.id}_{intake.phone10(conversation.phone_number)}" if conversation_created else None,
            incoming_timestamp=conversation.last_message_time or timezone.now(),
            data_payload={'conversation_id': conversation.id, 'customer_name': conversation.customer_name},
        )

    except ValueError as exc:
        log.warning("WhatsApp lead not created for %s: %s", conversation.phone_number, exc)
        return None, False


def _pretty(key):
    return str(key).replace('_', ' ').strip().title()


def sync_answers(lead, collected_data):
    """
    Copy flow answers onto the CRM lead. Mutates collected_data[SYNC_STATE_KEY] so each answer is
    recorded once (the caller saves the session). Returns {variable: value} that changed.
    """
    if lead is None or not collected_data:
        return {}
    synced = dict(collected_data.get(SYNC_STATE_KEY) or {})
    changed = {}
    fields = set()
    timeline = []

    for key, value in collected_data.items():
        k = str(key).strip().lower()
        if not k or k.startswith('_') or k in SKIP_KEYS:
            continue
        value = '' if value is None else str(value).strip()
        if not value or synced.get(k) == value:
            continue
        synced[k] = value
        changed[k] = value

        if k in NAME_KEYS:
            if not lead.name or intake.looks_like_phone(lead.name) or lead.source == SOURCE:
                if lead.name != value[:150]:
                    lead.name = value[:150]
                    fields.add('name')
        elif k in EMAIL_KEYS:
            if '@' in value and not lead.email:
                lead.email = value.lower()[:254]
                fields.add('email')
        elif k in COURSE_KEYS:
            product = intake.resolve_product(value)
            if product is not None and not lead.product_id:
                lead.product = product
                fields.add('product')
        elif k in BRANCH_KEYS:
            branch = intake.resolve_branch(value)
            if branch is not None and not lead.branch_id:
                lead.branch = branch
                fields.add('branch')
        timeline.append(f"{_pretty(k)}: {value}")

    collected_data[SYNC_STATE_KEY] = synced
    if fields:
        lead.save(update_fields=sorted(fields) + ['updated_at'])
    if timeline:
        intake.add_note(lead, "WhatsApp answers — " + "; ".join(timeline))
    if 'branch' in fields and not lead.assigned_telecaller_id:
        intake.auto_assign(lead, SOURCE)
    return changed


def set_lead_status(lead, status, follow_up_hours=None):
    """'Lead Status' step. Returns True if the status changed. Optional follow-up after N hours."""
    changed = intake.system_change_status(lead, status, remarks="WhatsApp automation")
    lead.refresh_from_db()
    text = f"WhatsApp automation set status to {lead.status}"
    if follow_up_hours:
        from followups.models import FollowUp, FollowUpStatus
        due = timezone.localtime(timezone.now() + timedelta(hours=float(follow_up_hours)))
        owner = lead.assigned_telecaller or lead.assigned_counselor
        FollowUp.objects.create(
            lead=lead, assigned_user=owner, manager=lead.assigned_sales_head, telecaller=lead.assigned_telecaller,
            follow_up_date=due.date(), follow_up_time=due.time().replace(second=0, microsecond=0),
            status=FollowUpStatus.PENDING, notes="Follow-up scheduled by WhatsApp automation",
        )
        text += f" (follow up {due:%d %b %Y, %I:%M %p})"
    if changed or follow_up_hours:
        intake.add_note(lead, text)
    return changed


def assign_lead(lead, mode='auto', telecaller_id=None, only_if_unassigned=False):
    """'Assign Telecaller' step. Returns the assigned telecaller (User) or None if nothing changed."""
    from accounts.models import User
    if only_if_unassigned and lead.assigned_telecaller_id:
        return None
    if mode == 'specific':
        tc = User.get_telecallers_queryset().filter(pk=telecaller_id, is_active=True).first()
        if tc is None:
            raise ValueError(f"Telecaller #{telecaller_id} doesn't exist or is inactive")
        if lead.assigned_telecaller_id == tc.pk:
            return None
        intake.direct_assign(lead, tc, reason="WhatsApp automation")
    else:
        if not lead.branch_id:
            raise ValueError("Lead has no branch yet, so it can't be auto-assigned "
                             "(set the WhatsApp number's CRM branch, or ask the branch in the flow)")
        previous = lead.assigned_telecaller_id
        intake.auto_assign(lead, SOURCE)
        lead.refresh_from_db()
        if lead.assigned_telecaller_id == previous:
            return None
    lead.refresh_from_db()
    return lead.assigned_telecaller


# ------------------------------------------------------------------ inbox access

def _phones_tail(qs):
    tails = set()
    for phone, alt in qs.values_list('phone', 'alternate_phone'):
        for p in (phone, alt):
            n = intake.phone10(p)
            if n:
                tails.add(n[-10:])
    return tails


def can_use_inbox(user):
    return bool(user and user.is_authenticated and user.is_active)


def can_manage_automation(user):
    """Flow builder, WhatsApp numbers: Admin and Sales Head."""
    return bool(user and user.is_authenticated and (user.is_admin_user or user.is_sales_head_user))


def conversations_for_user(user, qs):
    """Admin: every chat. Others: chats whose number belongs to a lead they can see."""
    if not can_use_inbox(user):
        return qs.none()
    if user.is_admin_user:
        return qs
    from accounts.permissions import get_accessible_branch_ids
    if user.role == UserRole.SALES_HEAD:
        leads = Lead.objects.filter(Q(branch_id__in=get_accessible_branch_ids(user)) | Q(assigned_sales_head=user))
    elif user.role == UserRole.BRANCH_HEAD:
        leads = Lead.objects.filter(Q(branch_id=user.branch_id) | Q(assigned_branch_head=user))
    elif user.role == UserRole.COUNSELOR:
        leads = Lead.objects.filter(Q(assigned_counselor=user) | Q(branch_id=user.branch_id))
    elif user.is_telecaller_user:
        leads = Lead.objects.filter(assigned_telecaller=user)
    else:
        return qs.none()
    tails = _phones_tail(leads)
    if not tails:
        return qs.none()
    ids = [cid for cid, phone in qs.values_list('id', 'phone_number')
           if (intake.phone10(phone) or '')[-10:] in tails]
    return qs.filter(id__in=ids)


def can_open_conversation(user, conversation):
    from .models import Conversation
    return conversations_for_user(user, Conversation.objects.filter(pk=conversation.pk)).exists()

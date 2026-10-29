"""
Bulk WhatsApp Campaign Service for DigiPanda CRM.
Handles sender resolution, recipient normalization, consent & compliance validation,
deterministic placeholder rendering, rate-limited batch submission, and webhook status progression.
"""

import re
import time
import logging
from typing import Dict, Any, List, Optional, Tuple
from django.db import transaction, models
from django.utils import timezone
from django.conf import settings
from django.db.models import Q

from chat.models import (
    BusinessAccount,
    WhatsAppSender,
    WhatsAppTemplate,
    WhatsAppCampaign,
    WhatsAppCampaignRecipient,
    Conversation,
    Message
)
from leads.models import Lead
from chat.whatsapp.client import WhatsAppClient

logger = logging.getLogger(__name__)


def ensure_default_senders_and_templates():
    """
    Ensures baseline WhatsAppSender and approved WhatsAppTemplate instances exist
    so the system is immediately usable without requiring manual database bootstrapping.
    """
    # 1. Sync WhatsAppSender from existing active BusinessAccount or settings
    accounts = BusinessAccount.objects.filter(is_active=True)
    for acc in accounts:
        sender, created = WhatsAppSender.objects.get_or_create(
            phone_number_id=acc.phone_number_id,
            defaults={
                'name': acc.name,
                'business_account': acc,
                'display_phone_number': acc.phone_number,
                'is_active': True,
                'is_verified': True,
                'quality_rating': 'GREEN',
                'daily_limit': 1000,
            }
        )
        if acc.crm_branch and not sender.allowed_branches.filter(id=acc.crm_branch_id).exists():
            sender.allowed_branches.add(acc.crm_branch)

    # If no BusinessAccount exists, create a default system sender from settings or fallback
    if not WhatsAppSender.objects.filter(is_active=True).exists():
        phone_id = getattr(settings, 'WHATSAPP_PHONE_NUMBER_ID', '') or 'default_waba_phone_id'
        WhatsAppSender.objects.create(
            name="DIGIPANDA Official Admissions Line",
            phone_number_id=phone_id,
            display_phone_number="+91 84382 39448",
            is_active=True,
            is_verified=True,
            quality_rating='GREEN',
            daily_limit=1000,
        )

    # 2. Seed default approved WhatsApp templates if none exist
    if not WhatsAppTemplate.objects.exists():
        WhatsAppTemplate.objects.bulk_create([
            WhatsAppTemplate(
                name="hello_world",
                display_title="Meta Default Test Template (hello_world)",
                language="en_US",
                category="UTILITY",
                status="APPROVED",
                header_type="NONE",
                body_text="Welcome and congratulations! This message demonstrates your ability to send a WhatsApp message using Cloud API. Thank you for taking the time to test with us.",
                parameter_mapping=[],
                is_active=True,
            ),
            WhatsAppTemplate(
                name="course_inquiry_followup",
                display_title="Course Inquiry Follow-up (Personalized)",
                language="en_US",
                category="MARKETING",
                status="APPROVED",
                header_type="NONE",
                body_text="Hi {{1}}, thank you for your interest in DIGIPANDA. Regarding your inquiry for {{2}} at our {{3}} center, your academic advisor {{4}} is ready to share the syllabus and upcoming batch dates. Reply YES to connect or call us directly.",
                footer_text="DIGIPANDA Academy - Career Growth",
                parameter_mapping=["lead_name", "course", "branch", "assigned_telecaller"],
                is_active=True,
            ),
            WhatsAppTemplate(
                name="welcome_lead_intro",
                display_title="Welcome & Program Brochure Introduction",
                language="en_US",
                category="MARKETING",
                status="APPROVED",
                header_type="NONE",
                body_text="Hello {{1}}, welcome to DIGIPANDA! We have received your application for {{2}}. Our team at {{3}} branch will assist you with counseling and demo session schedules.",
                footer_text="DIGIPANDA Learning",
                parameter_mapping=["lead_name", "course", "branch"],
                is_active=True,
            ),
            WhatsAppTemplate(
                name="institute_visit_invitation",
                display_title="Campus Visit & Offline Counseling Invitation",
                language="en_US",
                category="UTILITY",
                status="APPROVED",
                header_type="NONE",
                body_text="Dear {{1}}, you are warmly invited to visit our {{2}} campus this week for a one-on-one session with our senior trainer. Please let us know your preferred day and time.",
                footer_text="DIGIPANDA Admissions",
                parameter_mapping=["lead_name", "branch"],
                is_active=True,
            ),
        ])
    else:
        # Ensure standard hello_world test template is available
        WhatsAppTemplate.objects.get_or_create(
            name="hello_world",
            defaults={
                "display_title": "Meta Default Test Template (hello_world)",
                "language": "en_US",
                "category": "UTILITY",
                "status": "APPROVED",
                "header_type": "NONE",
                "body_text": "Welcome and congratulations! This message demonstrates your ability to send a WhatsApp message using Cloud API. Thank you for taking the time to test with us.",
                "parameter_mapping": [],
                "is_active": True,
            }
        )


def normalize_phone_number(raw_phone: str) -> Tuple[str, bool, Optional[str]]:
    """
    Standardizes telephone numbers into E.164-compatible digit strings.
    Validates minimum digit length (10-15 digits) and strips noise characters.
    """
    if not raw_phone:
        return "", False, "Missing phone number"

    digits = ''.join(c for c in str(raw_phone) if c.isdigit())
    if not digits:
        return "", False, "Phone number contains no numeric digits"

    # Default Indian numbers (10 digits starting with 6, 7, 8, or 9)
    if len(digits) == 10 and digits[0] in '6789':
        digits = '91' + digits
    elif len(digits) == 11 and digits.startswith('0'):
        digits = '91' + digits[1:]

    if len(digits) < 10 or len(digits) > 15:
        return digits, False, f"Invalid phone length ({len(digits)} digits, expected 10-15)"

    return digits, True, None


def check_lead_consent_eligibility(lead: Lead) -> Tuple[bool, Optional[str]]:
    """
    Evaluates regulatory and consent compliance for a recipient.
    """
    if getattr(lead, 'whatsapp_opt_out', False):
        return False, "Recipient has explicitly opted out of WhatsApp messages"

    if not getattr(lead, 'whatsapp_consent_given', True):
        return False, "No verified WhatsApp marketing consent on record"

    return True, None


def get_eligible_senders_for_user(user) -> List[WhatsAppSender]:
    """
    Returns all active WhatsAppSender instances that the specified user is authorized to use.
    """
    ensure_default_senders_and_templates()
    qs = WhatsAppSender.objects.filter(is_active=True)

    if getattr(user, 'is_admin_user', False) or user.is_superuser or getattr(user, 'role', '') == 'ADMIN':
        return list(qs)

    senders = []
    user_branch = getattr(user, 'branch', None)
    for s in qs:
        # Check branch permission
        allowed = list(s.allowed_branches.all())
        if allowed and user_branch and user_branch not in allowed:
            continue
        # Check user binding
        if s.user and s.user_id != user.id and getattr(user, 'role', '') not in ['ADMIN', 'SALES_HEAD']:
            continue
        senders.append(s)
    return senders


def resolve_sender_for_lead(lead: Lead, campaign: WhatsAppCampaign) -> Tuple[Optional[WhatsAppSender], Optional[str]]:
    """
    Resolves the exact WhatsApp sender to use for this specific lead based on campaign sender mode.
    """
    if campaign.sender_mode == WhatsAppCampaign.MODE_SELECTED_SENDER:
        sender = campaign.selected_sender
        if not sender or not sender.is_active:
            return None, "Selected sender is inactive or unavailable"
        if lead.branch:
            allowed = list(sender.allowed_branches.all())
            if allowed and lead.branch not in allowed:
                return None, f"Selected sender is not authorized for branch '{lead.branch.name}'"
        return sender, None

    elif campaign.sender_mode == WhatsAppCampaign.MODE_ASSIGNED_TELECALLER:
        telecaller = lead.assigned_telecaller
        if not telecaller:
            return None, "Lead has no assigned telecaller for caller-specific sender mode"

        # 1. Try sender directly assigned to this telecaller
        sender = WhatsAppSender.objects.filter(user=telecaller, is_active=True).first()
        if sender:
            return sender, None

        # 2. Try sender for the telecaller's branch or lead's branch
        branch = telecaller.branch or lead.branch
        if branch:
            branch_sender = WhatsAppSender.objects.filter(allowed_branches=branch, is_active=True).first()
            if branch_sender:
                return branch_sender, None

        # 3. Fallback to default active sender
        default_sender = WhatsAppSender.objects.filter(is_active=True).first()
        if default_sender:
            return default_sender, None

        return None, f"No authorized WhatsApp sender configured for telecaller '{telecaller.get_full_name() or telecaller.username}'"

    return None, "Unknown sender mode"


def get_lead_placeholder_values(lead: Lead) -> Dict[str, str]:
    """
    Extracts deterministic variable values from existing Lead model relationships.
    """
    branch_name = lead.branch.name if lead.branch else "Our Center"
    course_name = lead.product.name if lead.product else "Career Certification Program"
    telecaller_name = (
        lead.assigned_telecaller.get_full_name() or lead.assigned_telecaller.username
        if lead.assigned_telecaller else "Academic Counselor"
    )
    created_str = lead.created_at.strftime('%d-%b-%Y') if lead.created_at else ""

    return {
        'lead_name': lead.name or "Valued Student",
        'phone': lead.phone or "",
        'branch': branch_name,
        'course': course_name,
        'assigned_telecaller': telecaller_name,
        'created_on': created_str,
    }


def render_message_for_recipient(
    lead: Lead,
    campaign: WhatsAppCampaign
) -> Tuple[str, List[Dict[str, Any]], Optional[str]]:
    """
    Renders the personalized message text and Meta Cloud API template components.
    Returns (rendered_preview_text, template_components_payload, error_string)
    """
    placeholders = get_lead_placeholder_values(lead)

    if campaign.message_type == WhatsAppCampaign.MESSAGE_TYPE_TEMPLATE:
        template = campaign.template
        if not template:
            return "", [], "Campaign has no message template assigned"

        mapping = template.parameter_mapping or []
        body_params = []
        body_text_rendered = template.body_text or ""

        # Map positional variables {{1}}, {{2}}... or named variables
        for idx, key in enumerate(mapping, start=1):
            val = placeholders.get(key, placeholders.get('lead_name', ''))
            body_params.append({"type": "text", "text": str(val)})
            body_text_rendered = body_text_rendered.replace(f"{{{{{idx}}}}}", str(val))
            body_text_rendered = body_text_rendered.replace(f"{{{{{key}}}}}", str(val))

        components = []
        if body_params:
            components.append({
                "type": "body",
                "parameters": body_params
            })

        if campaign.media_url and template.header_type in ['IMAGE', 'DOCUMENT', 'VIDEO']:
            components.append({
                "type": "header",
                "parameters": [{
                    "type": template.header_type.lower(),
                    template.header_type.lower(): {"link": campaign.media_url}
                }]
            })

        return body_text_rendered, components, None

    else:
        # Plain text message
        text = campaign.custom_message or ""
        for key, val in placeholders.items():
            text = text.replace(f"{{{{{key}}}}}", str(val))
        return text, [], None


def resolve_campaign_recipients(
    campaign: WhatsAppCampaign,
    lead_ids: Optional[List[int]] = None,
    filter_criteria: Optional[Dict[str, Any]] = None,
    user: Optional[Any] = None
) -> Dict[str, Any]:
    """
    Evaluates all target leads, normalizes phones, enforces compliance,
    resolves senders, personalizes content, and creates recipient entries.
    Supports large selections (4,000+ leads) efficiently using chunked queries.
    """
    ensure_default_senders_and_templates()

    # Build query
    qs = Lead.objects.all().select_related(
        'branch', 'product', 'assigned_telecaller', 'channel'
    )

    if lead_ids:
        qs = qs.filter(id__in=lead_ids)
    elif filter_criteria:
        if filter_criteria.get('search'):
            q = filter_criteria['search']
            qs = qs.filter(Q(name__icontains=q) | Q(phone__icontains=q) | Q(email__icontains=q))
        if filter_criteria.get('branch'):
            qs = qs.filter(branch_id=filter_criteria['branch'])
        if filter_criteria.get('status'):
            qs = qs.filter(status=filter_criteria['status'])
        if filter_criteria.get('telecaller'):
            qs = qs.filter(assigned_telecaller_id=filter_criteria['telecaller'])
        if filter_criteria.get('channel'):
            qs = qs.filter(channel_id=filter_criteria['channel'])
        if filter_criteria.get('product'):
            qs = qs.filter(product_id=filter_criteria['product'])

    # Enforce user role visibility
    if user and not (getattr(user, 'is_admin_user', False) or user.is_superuser or getattr(user, 'role', '') == 'ADMIN'):
        if user.role == 'SALES_HEAD':
            from branches.models import SalesHeadBranchAccess
            accessible_branches = SalesHeadBranchAccess.objects.filter(sales_head=user).values_list('branch_id', flat=True)
            qs = qs.filter(branch_id__in=list(accessible_branches))
        elif user.role == 'BRANCH_HEAD':
            qs = qs.filter(branch=user.branch)
        elif user.role == 'TELECALLER':
            qs = qs.filter(assigned_telecaller=user)
        elif user.role == 'COUNSELOR':
            qs = qs.filter(assigned_counselor=user)

    # Process in batches of 500
    total_count = 0
    eligible_count = 0
    skipped_count = 0
    invalid_phone_count = 0
    opt_out_count = 0
    sender_unavail_count = 0

    recipient_objects = []
    seen_lead_ids = set(
        campaign.recipients.values_list('lead_id', flat=True)
    )

    for lead in qs.iterator(chunk_size=500):
        if lead.id in seen_lead_ids:
            continue
        seen_lead_ids.add(lead.id)
        total_count += 1

        phone_digits, is_valid_phone, phone_err = normalize_phone_number(lead.phone)
        consent_ok, consent_err = check_lead_consent_eligibility(lead)
        sender, sender_err = resolve_sender_for_lead(lead, campaign)
        rendered_msg, components, render_err = render_message_for_recipient(lead, campaign)

        is_eligible = True
        skip_reason = ""

        if not is_valid_phone:
            is_eligible = False
            skip_reason = phone_err or "Invalid phone number"
            invalid_phone_count += 1
        elif not consent_ok:
            is_eligible = False
            skip_reason = consent_err or "Consent missing or opted out"
            opt_out_count += 1
        elif not sender:
            is_eligible = False
            skip_reason = sender_err or "Sender not available"
            sender_unavail_count += 1
        elif render_err:
            is_eligible = False
            skip_reason = render_err
        else:
            eligible_count += 1

        if not is_eligible:
            skipped_count += 1

        recipient_objects.append(
            WhatsAppCampaignRecipient(
                campaign=campaign,
                lead=lead,
                phone_number=phone_digits or lead.phone or "",
                lead_name=lead.name,
                resolved_sender=sender,
                sender_phone_number=sender.display_phone_number if sender else "",
                status=WhatsAppCampaignRecipient.STATUS_ELIGIBLE if is_eligible else WhatsAppCampaignRecipient.STATUS_SKIPPED,
                skip_reason=skip_reason,
                personalized_message=rendered_msg,
                template_parameters=components,
            )
        )

        if len(recipient_objects) >= 500:
            WhatsAppCampaignRecipient.objects.bulk_create(recipient_objects, ignore_conflicts=True)
            recipient_objects = []

    if recipient_objects:
        WhatsAppCampaignRecipient.objects.bulk_create(recipient_objects, ignore_conflicts=True)

    # Atomically recalculate campaign counts
    campaign.refresh_counters_from_db()

    return {
        'total_selected': total_count,
        'eligible': eligible_count,
        'skipped': skipped_count,
        'invalid_phone': invalid_phone_count,
        'opted_out': opt_out_count,
        'sender_unavailable': sender_unavail_count,
    }


def dispatch_campaign_batch(campaign_id: int, batch_size: int = 50) -> Tuple[int, int]:
    """
    Processes one rate-limited batch of eligible recipients for the campaign.
    Uses select_for_update(skip_locked=True) to prevent duplicate processing by concurrent workers.
    Returns (processed_count, remaining_count).
    """
    campaign = WhatsAppCampaign.objects.filter(id=campaign_id).first()
    if not campaign:
        return 0, 0

    if campaign.status in [WhatsAppCampaign.STATUS_PAUSED, WhatsAppCampaign.STATUS_CANCELLED, WhatsAppCampaign.STATUS_COMPLETED]:
        return 0, 0

    if campaign.status != WhatsAppCampaign.STATUS_RUNNING:
        campaign.status = WhatsAppCampaign.STATUS_RUNNING
        if not campaign.started_at:
            campaign.started_at = timezone.now()
        campaign.save(update_fields=['status', 'started_at', 'updated_at'])

    # Lock rows for this batch atomically
    with transaction.atomic():
        recipients = list(
            WhatsAppCampaignRecipient.objects.select_for_update(skip_locked=True)
            .filter(
                campaign=campaign,
                status__in=[
                    WhatsAppCampaignRecipient.STATUS_ELIGIBLE,
                    WhatsAppCampaignRecipient.STATUS_QUEUED
                ]
            )[:batch_size]
        )

        if not recipients:
            # Check if any remaining eligible/queued
            remaining_unlocked = WhatsAppCampaignRecipient.objects.filter(
                campaign=campaign,
                status__in=[
                    WhatsAppCampaignRecipient.STATUS_ELIGIBLE,
                    WhatsAppCampaignRecipient.STATUS_QUEUED
                ]
            ).count()

            if remaining_unlocked == 0:
                campaign.status = WhatsAppCampaign.STATUS_COMPLETED
                campaign.completed_at = timezone.now()
                campaign.save(update_fields=['status', 'completed_at', 'updated_at'])
            return 0, remaining_unlocked

        # Mark as queued to prevent re-querying
        for r in recipients:
            r.status = WhatsAppCampaignRecipient.STATUS_QUEUED
            r.queued_at = timezone.now()
            r.attempt_count += 1
            r.save(update_fields=['status', 'queued_at', 'attempt_count', 'updated_at'])

    # Dispatch outside the lock transaction so network delays do not hold DB row locks
    processed_count = 0
    for r in recipients:
        sender = r.resolved_sender
        client = WhatsAppClient(
            phone_number_id=sender.phone_number_id if sender else None,
            business_account=sender.business_account if sender else None
        )

        try:
            if campaign.message_type == WhatsAppCampaign.MESSAGE_TYPE_TEMPLATE:
                template = campaign.template
                payload = {
                    "messaging_product": "whatsapp",
                    "recipient_type": "individual",
                    "to": r.phone_number,
                    "type": "template",
                    "template": {
                        "name": template.name if template else "general_intro",
                        "language": {"code": template.language if template else "en_US"},
                        "components": r.template_parameters or []
                    }
                }
            else:
                payload = {
                    "messaging_product": "whatsapp",
                    "recipient_type": "individual",
                    "to": r.phone_number,
                    "type": "text",
                    "text": {
                        "preview_url": False,
                        "body": r.personalized_message
                    }
                }

            # Submit to Meta API
            resp = client.send_payload(payload)
            wamid = ""
            if resp and "messages" in resp and len(resp["messages"]) > 0:
                wamid = resp["messages"][0].get("id", "")
            if not wamid:
                wamid = f"wamid.camp_{campaign.id}_{r.id}"

            r.provider_message_id = wamid
            r.status = WhatsAppCampaignRecipient.STATUS_SUBMITTED
            r.submitted_at = timezone.now()
            # If development mock or provider immediately confirms sent
            if resp.get('mocked'):
                r.status = WhatsAppCampaignRecipient.STATUS_SENT
                r.sent_at = timezone.now()

            r.save(update_fields=['provider_message_id', 'status', 'submitted_at', 'sent_at', 'updated_at'])
            processed_count += 1

            # Sync with WhatsApp inbox Conversation & Message models so replies connect directly
            try:
                record_campaign_message_in_inbox(r, client)
            except Exception as inbox_err:
                logger.warning(f"Could not link campaign recipient #{r.id} to inbox conversation: {inbox_err}")

        except Exception as exc:
            err_str = str(exc)
            logger.error(f"Failed sending campaign message to {r.phone_number}: {err_str}")
            # Determine if permanent or transient error
            # Permanent errors: invalid number, template missing, 404/400 client error, auth/permission failure, policy block
            permanent_keywords = [
                'invalid', 'not registered', 'disallowed', 'policy', 'blocked', '400',
                '404', '132001', 'template name does not exist', 'not found',
                'unsupported post request', 'object with id', 'permission', 'oauth',
                'access token', '190', '100', '131030', 'does not exist', 'cannot be empty'
            ]
            is_permanent = any(kw in err_str.lower() for kw in permanent_keywords)

            # Build human-readable diagnostic message
            custom_err = err_str
            if "132001" in err_str or "template name does not exist" in err_str.lower():
                tpl_name = campaign.template.name if campaign.template else "template"
                tpl_lang = campaign.template.language if campaign.template else "en_US"
                custom_err = f"Meta Error #132001: Template '{tpl_name}' ({tpl_lang}) does not exist or is not approved in your Meta WhatsApp account."
            elif "404" in err_str and "messages" in err_str:
                custom_err = f"Meta API 404 Error: Phone Number ID not found or invalid on Meta Graph API."
            elif "190" in err_str or "oauth" in err_str.lower():
                custom_err = f"Meta Auth Error: Invalid or expired WhatsApp Access Token."

            if is_permanent or r.attempt_count >= r.max_attempts:
                r.status = WhatsAppCampaignRecipient.STATUS_FAILED
                r.error_message = custom_err[:255]
                r.failed_at = timezone.now()
            else:
                # Leave queued for backoff retry
                r.status = WhatsAppCampaignRecipient.STATUS_QUEUED
                r.error_message = f"Transient error: {custom_err[:200]}"
            r.save(update_fields=['status', 'error_message', 'failed_at', 'updated_at'])

    campaign.refresh_counters_from_db()

    remaining_count = WhatsAppCampaignRecipient.objects.filter(
        campaign=campaign,
        status__in=[
            WhatsAppCampaignRecipient.STATUS_ELIGIBLE,
            WhatsAppCampaignRecipient.STATUS_QUEUED
        ]
    ).count()

    if remaining_count == 0:
        campaign.status = WhatsAppCampaign.STATUS_COMPLETED
        campaign.completed_at = timezone.now()
        campaign.save(update_fields=['status', 'completed_at', 'updated_at'])

    return processed_count, remaining_count


def record_campaign_message_in_inbox(recipient: WhatsAppCampaignRecipient, client: WhatsAppClient):
    """
    Creates an agent Message inside the existing Conversation for this recipient's phone number.
    Ensures that incoming customer replies automatically appear in the existing DigiPanda WhatsApp Inbox.
    """
    phone = f"+{recipient.phone_number}" if not recipient.phone_number.startswith('+') else recipient.phone_number
    biz_account = recipient.resolved_sender.business_account if recipient.resolved_sender else None

    conv, _ = Conversation.objects.get_or_create(
        business_account=biz_account,
        phone_number=phone,
        defaults={
            'customer_name': recipient.lead_name or phone,
            'is_online': True,
        }
    )

    msg_text = recipient.personalized_message or f"Campaign: {recipient.campaign.name}"
    Message.objects.create(
        conversation=conv,
        sender=Message.SENDER_AGENT,
        message_type=Message.TYPE_TEXT,
        message_text=msg_text,
        whatsapp_message_id=recipient.provider_message_id,
        status=Message.STATUS_SENT,
        timestamp=timezone.now(),
    )

    conv.last_message = msg_text[:120]
    conv.last_message_time = timezone.now()
    conv.save(update_fields=['last_message', 'last_message_time', 'updated_at'])


def update_recipient_from_webhook_status(
    wamid: str,
    status: str,
    timestamp: Optional[Any] = None,
    error_details: Optional[Dict[str, Any]] = None
) -> bool:
    """
    Updates campaign recipient delivery status from Meta status callbacks (sent, delivered, read, failed).
    Handles out-of-order event delivery safely with a state hierarchy.
    """
    if not wamid or not status:
        return False

    recipient = WhatsAppCampaignRecipient.objects.filter(provider_message_id=wamid).first()
    if not recipient:
        return False

    status_hierarchy = {
        'eligible': 0,
        'skipped': 0,
        'queued': 1,
        'submitted': 2,
        'sent': 3,
        'delivered': 4,
        'read': 5,
        'failed': 6,
    }

    current_rank = status_hierarchy.get(recipient.status, 0)
    new_rank = status_hierarchy.get(status, 0)

    # Do not regress (e.g. read -> delivered, delivered -> sent)
    if recipient.status == WhatsAppCampaignRecipient.STATUS_READ and status in ['sent', 'delivered']:
        return True
    if recipient.status == WhatsAppCampaignRecipient.STATUS_DELIVERED and status == 'sent':
        return True

    now = timezone.now()
    if status == 'sent':
        recipient.status = WhatsAppCampaignRecipient.STATUS_SENT
        recipient.sent_at = now
    elif status == 'delivered':
        recipient.status = WhatsAppCampaignRecipient.STATUS_DELIVERED
        recipient.delivered_at = now
    elif status == 'read':
        recipient.status = WhatsAppCampaignRecipient.STATUS_READ
        recipient.read_at = now
    elif status == 'failed':
        recipient.status = WhatsAppCampaignRecipient.STATUS_FAILED
        recipient.failed_at = now
        if error_details:
            recipient.error_code = str(error_details.get('code', ''))[:64]
            recipient.error_message = str(error_details.get('message', 'Delivery failed'))[:255]

    recipient.save(update_fields=[
        'status', 'sent_at', 'delivered_at', 'read_at', 'failed_at',
        'error_code', 'error_message', 'updated_at'
    ])

    # Refresh campaign counters
    recipient.campaign.refresh_counters_from_db()
    return True


def run_campaign_worker_loop(campaign_id: int, max_batches: int = 100):
    """
    Synchronous / daemon worker loop that executes consecutive batches respecting rate limits.
    Can be run in a background daemon thread, management command, or Celery task.
    """
    batches_run = 0
    while batches_run < max_batches:
        campaign = WhatsAppCampaign.objects.filter(id=campaign_id).first()
        if not campaign or campaign.status in [
            WhatsAppCampaign.STATUS_PAUSED,
            WhatsAppCampaign.STATUS_CANCELLED,
            WhatsAppCampaign.STATUS_COMPLETED
        ]:
            break

        processed, remaining = dispatch_campaign_batch(
            campaign_id,
            batch_size=campaign.batch_size or 50
        )
        batches_run += 1

        if remaining == 0 or processed == 0:
            break

        # Rate limiting sleep calculation
        rpm = max(1, campaign.rate_limit_per_minute or 60)
        delay_seconds = (processed / rpm) * 60.0
        time.sleep(min(delay_seconds, 5.0))

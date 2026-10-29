from .intake import CentralizedLeadIntakeService, IntakeResult
import re
from datetime import timedelta
from collections import defaultdict
from django.db import transaction
from django.db.models import Count, Q
from django.utils import timezone
from .models import Lead
from branches.models import Branch
from activities.utils import log_activity


def normalize_phone(phone):
    """
    Normalizes a phone number.
    - Surrogate markers (e.g. 'NoPhone-...') are preserved untouched.
    - Domestic Indian numbers: strips '+91', '91' (12-digit), leading '0' (11-digit),
      and formats to canonical 10 digits (e.g. '9876543210').
    - International numbers (with leading '+' or '00', or non-Indian >10 digits):
      formats to clean E.164 format with leading '+' (e.g. '+447911123456', '+14155552671').
    """
    if not phone:
        return ''
    raw = str(phone).strip()
    if raw.startswith('NoPhone-'):
        return raw

    # Strip URI prefixes common in Facebook Lead Ads and sheets (e.g., 'p:+91...', 'tel:+91...', 'ph:...')
    raw = re.sub(r'^(?:p|tel|phone|ph)\s*:\s*', '', raw, flags=re.IGNORECASE).strip()

    # Convert international dialing prefix '00' to '+'
    if raw.startswith('00'):
        raw = '+' + raw[2:].lstrip()

    is_international_prefix = raw.startswith('+')
    digits = re.sub(r'\D', '', raw)

    if not digits:
        return ''

    # Check for Indian numbers:
    # 1. Starts with 91 and has 12 digits (e.g. +91 9876543210 or 919876543210)
    if len(digits) == 12 and digits.startswith('91'):
        return digits[2:]

    # 2. Starts with 0 and has 11 digits (e.g. 09876543210)
    if len(digits) == 11 and digits.startswith('0') and not is_international_prefix:
        return digits[1:]

    # 3. Exactly 10 digits (domestic Indian standard mobile/landline)
    if len(digits) == 10 and not is_international_prefix:
        return digits

    # If explicitly prefixed with '+' or entered as international number (>10 digits)
    if is_international_prefix or len(digits) > 10:
        return f"+{digits}"

    # Fallback for short local/extension digits
    return digits


def normalize_email(email):
    """
    Normalizes an email address to lowercase stripped string.
    """
    if not email:
        return ''
    return str(email).strip().lower()


def find_duplicate_lead(phone=None, email=None, name=None, exclude_id=None):
    """
    Checks whether a matching lead already exists in the CRM.
    Matches primarily by normalized phone number, then by email address,
    and optionally checks matching name + normalized phone.
    """
    clean_phone = normalize_phone(phone)
    clean_email = normalize_email(email)

    qs = Lead.objects.all()
    if exclude_id:
        qs = qs.exclude(id=exclude_id)

    # 1. Match by phone
    if clean_phone and not clean_phone.startswith('NoPhone-'):
        if clean_phone.startswith('+'):
            lead_by_phone = qs.filter(
                Q(normalized_phone=clean_phone) | Q(phone=clean_phone) | Q(alternate_phone=clean_phone)
            ).first()
            if lead_by_phone:
                return lead_by_phone
        elif len(clean_phone) >= 10:
            target_10 = clean_phone[-10:]
            # Priority 1: Exact match on normalized_phone
            lead_by_phone = qs.filter(normalized_phone=target_10).first()
            if not lead_by_phone:
                lead_by_phone = qs.filter(
                    (Q(phone=clean_phone) | Q(phone__endswith=target_10) | Q(alternate_phone__endswith=target_10))
                    & ~Q(normalized_phone__startswith='+')
                    & ~Q(phone__startswith='+')
                ).first()
            if lead_by_phone:
                return lead_by_phone
        else:
            lead_by_phone = qs.filter(phone=clean_phone).first()
            if lead_by_phone:
                return lead_by_phone

    # 2. Match by email
    if clean_email:
        lead_by_email = qs.filter(email__iexact=clean_email).first()
        if lead_by_email:
            return lead_by_email

    return None


def find_all_matching_leads(phone=None, email=None, name=None, exclude_id=None):
    """
    Finds all matching lead records in the CRM matching normalized phone, email, or name.
    Does not perform automatic merge; allows review of multiple possible matching records.
    """
    clean_phone = normalize_phone(phone)
    clean_email = normalize_email(email)

    qs = Lead.objects.all().select_related('branch', 'assigned_counselor', 'assigned_telecaller', 'channel')
    if exclude_id:
        qs = qs.exclude(id=exclude_id)

    matches_dict = {}

    if clean_phone and not clean_phone.startswith('NoPhone-'):
        if clean_phone.startswith('+'):
            phone_matches = qs.filter(
                Q(normalized_phone=clean_phone) | Q(phone=clean_phone) | Q(alternate_phone=clean_phone)
            )
        elif len(clean_phone) >= 10:
            target_10 = clean_phone[-10:]
            phone_matches = qs.filter(
                Q(normalized_phone=target_10) |
                (
                    (Q(phone=clean_phone) | Q(phone__endswith=target_10) | Q(alternate_phone__endswith=target_10))
                    & ~Q(normalized_phone__startswith='+')
                    & ~Q(phone__startswith='+')
                )
            )
        else:
            phone_matches = qs.filter(phone=clean_phone)
        for ld in phone_matches:
            matches_dict[ld.id] = ld

    if clean_email:
        email_matches = qs.filter(email__iexact=clean_email)
        for ld in email_matches:
            matches_dict[ld.id] = ld

    return list(matches_dict.values())



def handle_incoming_lead_duplicate(existing_lead, incoming_data, branch=None, user=None, source_label='Import', provider_event_id=None, incoming_timestamp=None):
    """
    Applies the centralized 10-day duplicate rule to an incoming lead match.
    If <= 10 days: Retains existing lead untouched, creates DuplicateLeadRecord audit record, notifies user.
    If > 10 days: Updates existing lead (preserving lead ID), changes branch if applicable, reactivates status to NEW,
                 creates DuplicateLeadRecord with field_changes, and notifies user.
    """
    from leads.intake import intake_lead
    phone = incoming_data.get('phone') or incoming_data.get('mobile') or existing_lead.phone
    name = incoming_data.get('name') or incoming_data.get('lead name') or existing_lead.name
    email = incoming_data.get('email') or existing_lead.email
    notes = incoming_data.get('notes') or incoming_data.get('remarks') or ''
    channel_name = incoming_data.get('channel') or ''

    prod_obj = incoming_data.get('product')
    if isinstance(prod_obj, str) and prod_obj:
        from products.models import Product
        prod_obj = Product.objects.filter(name__iexact=prod_obj).first()

    # Create a JSON-safe payload for DuplicateLeadRecord audit
    safe_payload = {}
    if isinstance(incoming_data, dict):
        for k, v in incoming_data.items():
            if hasattr(v, 'name'):
                safe_payload[k] = v.name
            elif hasattr(v, 'pk'):
                safe_payload[k] = v.pk
            else:
                safe_payload[k] = str(v) if v is not None else ''

    result = intake_lead(
        phone=phone,
        source=source_label,
        channel_name=channel_name if isinstance(channel_name, str) else getattr(channel_name, 'name', ''),
        name=name,
        email=email,
        branch=branch or existing_lead.branch,
        product=prod_obj,
        note=notes,
        activity_user=user,
        provider_event_id=provider_event_id,
        incoming_timestamp=incoming_timestamp,
        data_payload=safe_payload,
    )
    return result.lead



def detect_all_duplicate_groups():
    """
    Scans the CRM database to detect all duplicate lead groups.
    Groups are identified by:
    1. Multiple Lead records with the same normalized phone number.
    2. Multiple Lead records with the same email.
    3. A single Lead record that has multiple branches associated (secondary_branches).

    Returns:
        tuple (groups_list, total_groups_count)
    """
    all_leads = Lead.objects.all().select_related('branch', 'channel', 'product').prefetch_related('secondary_branches')

    # Map by normalized phone
    phone_to_leads = defaultdict(list)
    email_to_leads = defaultdict(list)
    multi_branch_leads = []

    for lead in all_leads:
        clean_phone = normalize_phone(lead.phone)
        if clean_phone and len(clean_phone) >= 7 and not clean_phone.startswith('NoPhone-'):
            target_key = clean_phone[-10:] if len(clean_phone) >= 10 else clean_phone
            phone_to_leads[target_key].append(lead)

        clean_email = normalize_email(lead.email)
        if clean_email:
            email_to_leads[clean_email].append(lead)

        if lead.secondary_branches.exists():
            multi_branch_leads.append(lead)

    processed_lead_ids = set()
    groups = []
    group_counter = 1

    # 1. Process phone duplicate groups (multiple DB records)
    for target_key, leads in phone_to_leads.items():
        if len(leads) > 1:
            group_leads = [l for l in leads if l.id not in processed_lead_ids]
            if len(group_leads) >= 2:
                # Collect all unique branches across these leads
                branches = []
                for l in group_leads:
                    for b in l.get_all_branches():
                        if b and b.name not in branches:
                            branches.append(b.name)

                primary = group_leads[0]
                groups.append({
                    'group_id': group_counter,
                    'group_label': f"Duplicate Group {group_counter:02d}",
                    'name': primary.name,
                    'phone': primary.phone,
                    'email': primary.email or '',
                    'branches': branches,
                    'lead_ids': [l.id for l in group_leads],
                    'lead_ids_str': ','.join(str(l.id) for l in group_leads),
                    'leads': group_leads,
                    'is_single_record': False,
                    'lead_count': len(group_leads),
                })
                group_counter += 1
                for l in group_leads:
                    processed_lead_ids.add(l.id)

    # 2. Process email duplicate groups (multiple DB records)
    for clean_email, leads in email_to_leads.items():
        if len(leads) > 1:
            group_leads = [l for l in leads if l.id not in processed_lead_ids]
            if len(group_leads) >= 2:
                branches = []
                for l in group_leads:
                    for b in l.get_all_branches():
                        if b and b.name not in branches:
                            branches.append(b.name)

                primary = group_leads[0]
                groups.append({
                    'group_id': group_counter,
                    'group_label': f"Duplicate Group {group_counter:02d}",
                    'name': primary.name,
                    'phone': primary.phone,
                    'email': clean_email,
                    'branches': branches,
                    'lead_ids': [l.id for l in group_leads],
                    'lead_ids_str': ','.join(str(l.id) for l in group_leads),
                    'leads': group_leads,
                    'is_single_record': False,
                    'lead_count': len(group_leads),
                })
                group_counter += 1
                for l in group_leads:
                    processed_lead_ids.add(l.id)

    # 3. Process leads that already maintain multiple branches under a single record
    for lead in multi_branch_leads:
        if lead.id not in processed_lead_ids:
            branches = lead.get_all_branch_names()
            if len(branches) >= 2:
                groups.append({
                    'group_id': group_counter,
                    'group_label': f"Duplicate Group {group_counter:02d}",
                    'name': lead.name,
                    'phone': lead.phone,
                    'email': lead.email or '',
                    'branches': branches,
                    'lead_ids': [lead.id],
                    'lead_ids_str': str(lead.id),
                    'leads': [lead],
                    'is_single_record': True,
                    'lead_count': 1,
                })
                group_counter += 1
                processed_lead_ids.add(lead.id)

    return groups, len(groups)


def keep_single_lead_for_group(lead_ids, user=None):
    """
    Consolidates multiple duplicate Lead records into a single unique Lead record.
    - Picks the primary lead (earliest created / most complete).
    - Transfers and retains valid details (email, notes, alternate phones, products).
    - Merges branches into primary_lead.secondary_branches.
    - Re-parents calls, follow-ups, activity logs, and sheet mappings to the primary lead.
    - Deletes duplicate copies, retaining exactly ONE unique lead record.
    - Logs audit activity.
    """
    if isinstance(lead_ids, str):
        lead_ids = [int(i.strip()) for i in lead_ids.split(',') if i.strip().isdigit()]

    if not lead_ids:
        raise ValueError("No valid lead IDs provided for consolidation.")

    with transaction.atomic():
        leads = list(Lead.objects.filter(id__in=lead_ids).order_by('id'))
        if not leads:
            raise ValueError("No leads found matching the provided IDs.")

        if len(leads) == 1:
            # Already a single record!
            primary_lead = leads[0]
            log_activity(
                user=user,
                action="Single Lead Maintained",
                description=f"Confirmed single unique lead '{primary_lead.name}' ({primary_lead.phone}) across branches: {', '.join(primary_lead.get_all_branch_names())}.",
                object_type="Lead",
                object_id=primary_lead.id
            )
            return primary_lead

        primary_lead = leads[0]
        other_leads = leads[1:]

        from followups.models import FollowUp
        from calls.models import CallHistory
        from activities.models import Activity

        for dup in other_leads:
            # Merge branch
            if dup.branch and dup.branch != primary_lead.branch:
                primary_lead.secondary_branches.add(dup.branch)
            for b in dup.secondary_branches.all():
                if b != primary_lead.branch:
                    primary_lead.secondary_branches.add(b)

            # Merge email
            if not primary_lead.email and dup.email:
                primary_lead.email = dup.email

            # Merge alt phone
            if not primary_lead.alternate_phone and dup.alternate_phone:
                primary_lead.alternate_phone = dup.alternate_phone

            # Merge product
            if not primary_lead.product and dup.product:
                primary_lead.product = dup.product

            # Merge channel
            if not primary_lead.channel and dup.channel:
                primary_lead.channel = dup.channel

            # Merge notes
            if dup.notes:
                b_name = dup.branch.name if dup.branch else 'Branch'
                if dup.notes not in (primary_lead.notes or ''):
                    if primary_lead.notes:
                        primary_lead.notes = f"{primary_lead.notes}\n[Merged from {b_name}]: {dup.notes}".strip()
                    else:
                        primary_lead.notes = f"[Merged from {b_name}]: {dup.notes}"

            # Re-parent related foreign keys
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
            dup.delete()

        primary_lead.save()

        log_activity(
            user=user,
            action="Duplicate Leads Consolidated",
            description=f"Consolidated duplicate records for '{primary_lead.name}' ({primary_lead.phone}) into single unique lead #{primary_lead.id}. Maintained branches: {', '.join(primary_lead.get_all_branch_names())}.",
            object_type="Lead",
            object_id=primary_lead.id
        )

        return primary_lead


def process_incoming_lead_with_10day_rule(
    lead_data,
    branch=None,
    source="Google Form",
    user=None,
    provider_event_id=None,
    incoming_timestamp=None,
):
    """
    Standardized entry point enforcing the 10-day duplicate detection and update rule.
    Routes directly through centralized leads.intake.intake_lead.
    Preserves existing lead ID and history for renewals (>10 days) and retains existing
    lead unchanged for submissions within 10 days.

    Returns:
        tuple (lead, is_duplicate, duplicate_record)
    """
    from leads.intake import intake_lead

    name = str(lead_data.get('name') or lead_data.get('lead name') or '').strip()
    phone = str(lead_data.get('phone') or lead_data.get('phone_number') or lead_data.get('mobile') or '').strip()
    email = str(lead_data.get('email') or '').strip()
    notes = str(lead_data.get('notes') or lead_data.get('remarks') or '').strip()

    incoming_branch = branch
    if not incoming_branch:
        branch_str = str(lead_data.get('branch') or lead_data.get('Branch') or '').strip()
        if branch_str:
            incoming_branch = Branch.objects.filter(name__iexact=branch_str).first() or \
                              Branch.objects.filter(name__icontains=branch_str).first()

    result = intake_lead(
        phone=phone,
        source=source,
        name=name,
        email=email,
        branch=incoming_branch,
        note=notes,
        activity_user=user,
        provider_event_id=provider_event_id,
        incoming_timestamp=incoming_timestamp,
        data_payload=lead_data if isinstance(lead_data, dict) else {},
    )

    is_duplicate = (result.action_taken == 'RETAINED_WITHIN_10_DAYS')
    return (result.lead, is_duplicate, result.duplicate_record)



def mask_phone(phone):
    """
    Formats 10-digit phone numbers as: 98765xxxxx (first 5 digits + xxxxx).
    Preserves non-standard or already masked phones.
    """
    if not phone:
        return ''
    raw = str(phone).strip()
    if raw.endswith('xxxxx') and len(raw) == 10:
        return raw
    clean = normalize_phone(raw)
    if len(clean) == 10 and clean.isdigit():
        return clean[:5] + 'xxxxx'
    elif len(raw) == 10 and raw.isdigit():
        return raw[:5] + 'xxxxx'
    return raw


def process_spreadsheet_row_duplicate_rules(row_data, headers=None, connection=None, user=None):
    """
    Implements Duplicate Flow (Sections 8, 9, 10, 11) for rows detected in a connected Google Spreadsheet:
    Row found in spreadsheet
           │
           ▼
    Check lead details (phone, email, name)
           │
           ├── Lead does NOT exist ──► Normal Lead
           │
           └── Lead exists
                 │
                 ├── Same Branch ──► Duplicate
                 │
                 └── Different Branch
                       │
                       ├── Within 10 Days ──► Duplicate (warning banner, status DUPLICATE)
                       │
                       └── After 10 Days ──► New / Normal Lead
    
    Returns:
        tuple (lead_or_existing, is_duplicate, duplicate_record)
    """
    from .models import DuplicateLeadRecord, LeadStatus, GoogleSheetRowMapping
    from .assignment import assign_lead_to_branch_telecaller
    from lead_channels.models import Channel

    # Convert row_data to dict if needed
    row_dict = {}
    if isinstance(row_data, dict):
        row_dict = dict(row_data)
    elif isinstance(row_data, (list, tuple)) and headers:
        for idx, h in enumerate(headers):
            if idx < len(row_data):
                row_dict[h] = row_data[idx]

    # Helper to find values case-insensitively
    def get_val(*keywords):
        for k, v in row_dict.items():
            if str(k).startswith('_'):
                continue
            k_lower = str(k).strip().lower()
            if any(kw in k_lower for kw in keywords):
                if v is not None and str(v).strip():
                    return str(v).strip()
        return ''

    name = get_val('name', 'student', 'applicant')
    phone = get_val('phone', 'mobile', 'contact')
    email = get_val('email')
    branch_str = get_val('branch', 'location', 'center', 'city')
    notes_str = get_val('notes', 'remarks', 'query', 'course', 'product')

    source_label = connection.name if connection else 'Google Sheets'

    # Skip completely empty trailing rows
    if not name and not phone and not email:
        return (None, False, None)

    # Clean fallback name for WhatsApp / online inquiries with mobile/email only
    if not name:
        if phone:
            clean_p = re.sub(r'[^0-9]', '', str(phone))
            disp_p = clean_p[-10:] if len(clean_p) >= 10 else clean_p
            name = f"{source_label} Lead ({disp_p})"
        elif email:
            name = f"{source_label} Lead ({email.split('@')[0]})"
        else:
            name = f"{source_label} Lead"

    row_idx = row_dict.get('_row_index', 0)
    row_id = ''
    if connection:
        row_id = f"{connection.spreadsheet_id}_{connection.worksheet_name or 'Sheet1'}_row_{row_idx}"

    # Check if already processed
    if connection and row_id:
        existing_mapping = GoogleSheetRowMapping.objects.filter(
            connection=connection,
            row_identifier=row_id
        ).select_related('lead').first()
        if existing_mapping:
            return (existing_mapping.lead, False, None)

        existing_dup = DuplicateLeadRecord.objects.filter(
            original_lead__sheet_mappings__connection=connection,
            name=name,
            phone=phone
        ).first() if (name and phone) else None
        if existing_dup:
            return (existing_dup.original_lead, True, existing_dup)

    # Resolve incoming branch
    incoming_branch = None
    if branch_str:
        incoming_branch = Branch.objects.filter(Q(name__iexact=branch_str) | Q(name__icontains=branch_str)).first()

    if not incoming_branch and connection:
        if connection.branch:
            incoming_branch = connection.branch
        elif connection.name:
            for b in Branch.objects.filter(status='Active'):
                if b.name.lower() in connection.name.lower():
                    incoming_branch = b
                    break

    if not incoming_branch and user and hasattr(user, 'branch') and user.branch:
        incoming_branch = user.branch

    clean_payload = {}
    for k, v in row_dict.items():
        if not str(k).startswith('_'):
            clean_payload[str(k)] = str(v) if v is not None else ''

    source_label = connection.name if connection else 'Google Sheets'

    # Check for existing lead by details
    existing_lead = find_duplicate_lead(phone=phone, email=email, name=name)

    if existing_lead:
        now = timezone.now()
        time_diff = now - existing_lead.created_at
        days_diff = time_diff.total_seconds() / 86400.0

        is_same_branch = (
            (existing_lead.branch and incoming_branch and existing_lead.branch == incoming_branch) or
            (not existing_lead.branch and not incoming_branch)
        )

        if is_same_branch:
            # ─────────────────────────────────────────────────────────
            # SAME BRANCH -> DUPLICATE!
            # ─────────────────────────────────────────────────────────
            dup_rec = DuplicateLeadRecord.objects.create(
                original_lead=existing_lead,
                name=name or existing_lead.name,
                phone=phone or existing_lead.phone,
                email=email or existing_lead.email,
                branch=incoming_branch,
                branch_name=incoming_branch.name if incoming_branch else (existing_lead.branch.name if existing_lead.branch else 'Same Branch'),
                status='DUPLICATE',
                notes=notes_str or 'Same lead details detected in same branch.',
                source=source_label,
                data_payload=clean_payload
            )
            return (existing_lead, True, dup_rec)

        elif days_diff <= 10.0:
            # ─────────────────────────────────────────────────────────
            # DIFFERENT BRANCH WITHIN 10 DAYS -> DUPLICATE!
            # ─────────────────────────────────────────────────────────
            dup_rec = DuplicateLeadRecord.objects.create(
                original_lead=existing_lead,
                name=name or existing_lead.name,
                phone=phone or existing_lead.phone,
                email=email or existing_lead.email,
                branch=incoming_branch,
                branch_name=incoming_branch.name if incoming_branch else 'Different Branch',
                status='DUPLICATE',
                notes='⚠ Same lead details detected in another branch within 10 days.',
                source=source_label,
                data_payload=clean_payload
            )

            if incoming_branch and incoming_branch != existing_lead.branch:
                existing_lead.secondary_branches.add(incoming_branch)

            return (existing_lead, True, dup_rec)

        else:
            # ─────────────────────────────────────────────────────────
            # DIFFERENT BRANCH AFTER 10 DAYS -> ENRICH EXISTING PRIMARY (NO DUPLICATE LEAD CREATION)
            # ─────────────────────────────────────────────────────────
            with transaction.atomic():
                orig_branch_name = existing_lead.branch.name if existing_lead.branch else 'Original Branch'
                new_branch_name = incoming_branch.name if incoming_branch else 'New Branch'

                re_enquiry_note = f"[Re-Enquiry - {source_label} ({round(days_diff, 1)} days later)]: Enquired for {new_branch_name}."
                if existing_lead.notes:
                    existing_lead.notes = f"{existing_lead.notes}\n{re_enquiry_note}".strip()
                else:
                    existing_lead.notes = re_enquiry_note

                if incoming_branch and incoming_branch != existing_lead.branch:
                    existing_lead.secondary_branches.add(incoming_branch)

                if email and not existing_lead.email:
                    existing_lead.email = email
                if name and (not existing_lead.name or normalize_phone(existing_lead.name)):
                    existing_lead.name = name

                existing_lead.status = LeadStatus.FOLLOW_UP
                existing_lead.save()

                dup_rec = DuplicateLeadRecord.objects.create(
                    original_lead=existing_lead,
                    record_type='REENQUIRY_DUPLICATE',
                    name=name or existing_lead.name,
                    phone=phone or existing_lead.phone,
                    email=email or existing_lead.email,
                    branch=incoming_branch,
                    branch_name=new_branch_name,
                    status='Enriched Re-Enquiry (>10 Days)',
                    notes=f"Re-enquiry after {round(days_diff, 1)} days in {new_branch_name}. Existing primary lead #{existing_lead.id} enriched and preserved.",
                    source=source_label,
                    data_payload=clean_payload
                )

                if connection and row_id:
                    GoogleSheetRowMapping.objects.get_or_create(
                        connection=connection,
                        row_identifier=row_id,
                        defaults={'lead': existing_lead, 'row_index': row_idx, 'source_status': 'Active'}
                    )

                return (existing_lead, False, dup_rec)

    else:
        # ─────────────────────────────────────────────────────────
        # NO EXISTING LEAD -> BRAND NEW LEAD!
        # ─────────────────────────────────────────────────────────
        # Channel/Source attribution: use the connection's selected Channel/Source
        # (the admin-selected marketing attribution), not a hardcoded "Google Sheets".
        channel = (connection.channel if connection else None) or (
            Channel.objects.filter(name__icontains='Google Sheets').first() or
            Channel.objects.first()
        )

        new_lead = Lead.objects.create(
            name=name or 'Spreadsheet Lead',
            phone=phone or '',
            email=email or '',
            branch=incoming_branch,
            channel=channel,
            source=source_label,
            is_offline=True,
            status=LeadStatus.NEW,
            notes=notes_str or f"Imported from {source_label}"
        )

        assign_lead_to_branch_telecaller(new_lead, branch=incoming_branch, source=source_label, triggered_by=user)

        if connection and row_id:
            GoogleSheetRowMapping.objects.get_or_create(
                connection=connection,
                row_identifier=row_id,
                defaults={'lead': new_lead, 'row_index': row_idx, 'source_status': 'Active'}
            )

        return (new_lead, False, None)



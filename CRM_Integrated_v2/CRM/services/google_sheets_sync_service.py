import datetime
import hashlib
import json
import logging
import re
from typing import Any, Dict, List, Optional, Tuple
from django.db import transaction
from django.utils import timezone
from django.contrib.auth import get_user_model

from .google_sheets_service import fetch_sheet
from .google_sheets_parser import normalize_header_name
from .intelligent_matching_engine import (
    match_all_columns,
    get_active_crm_entities,
    normalize_header,
    AUTHORITATIVE_FIELD_INVENTORY,
)
from leads.models import (
    Lead,
    LeadStatus,
    GoogleSheetConnection,
    GoogleSheetRowMapping,
    GoogleSheetSyncHistory,
)
from leads.assignment import assign_new_lead
from leads.duplicates import (
    find_duplicate_lead,
    normalize_phone,
    normalize_email,
)
from lead_channels.models import Channel
from branches.models import Branch
from products.models import Product

logger = logging.getLogger('crm')


def compute_row_hash(data_dict: dict) -> str:
    """Computes deterministic SHA-256 hash for mapped fields to detect cell changes."""
    canonical = json.dumps(data_dict, sort_keys=True, default=str)
    return hashlib.sha256(canonical.encode('utf-8')).hexdigest()


def get_field_value(row_dict: dict, mapped_col: Optional[str], *candidate_names: str) -> str:
    """
    Retrieves cell value safely with exact match, fallback candidate names,
    and normalized key lookup.
    """
    if mapped_col and mapped_col in row_dict and row_dict[mapped_col] is not None:
        v = str(row_dict[mapped_col]).strip()
        if v:
            return v

    for cand in candidate_names:
        if cand and cand in row_dict and row_dict[cand] is not None:
            v = str(row_dict[cand]).strip()
            if v:
                return v

    # Normalized lookup
    norm_map = {normalize_header(k): v for k, v in row_dict.items() if k is not None}
    search_keys = ([mapped_col] if mapped_col else []) + list(candidate_names)
    for sk in search_keys:
        if sk:
            nsk = normalize_header(str(sk))
            if nsk in norm_map and norm_map[nsk] is not None:
                v = str(norm_map[nsk]).strip()
                if v:
                    return v

    return ''


def parse_flexible_date(val: Any) -> Optional[datetime.date]:
    """Parses various date formats from spreadsheets into date object."""
    if not val:
        return None
    s = str(val).strip()
    for fmt in ('%Y-%m-%d', '%d/%m/%Y', '%m/%d/%Y', '%d-%m-%Y', '%Y/%m/%d', '%d.%m.%Y'):
        try:
            return datetime.datetime.strptime(s, fmt).date()
        except ValueError:
            pass
    return None


from .status_classifier import classify_sheet_status


def sync_connection(
    connection: GoogleSheetConnection,
    triggered_by=None,
    headers: Optional[List[str]] = None,
    rows: Optional[List[dict]] = None,
    dry_run: bool = False,
    custom_field_mapping: Optional[dict] = None
) -> dict:
    """
    Synchronizes a connected Google Sheet directly into MySQL using Django ORM.
    Leverages Intelligent Column Matching Engine (Exact, Aliases, Tamil/Hindi, Fuzzy & Patterns).

    Features:
    - In-place non-destructive updates: Blank spreadsheet cells never erase existing CRM data.
    - Identity resolution: Row Identifier -> 10-digit Phone -> Normalized Email.
    - Full lead qualification autofill & custom unmapped field preservation in custom_fields['all_answers'].
    - Optional dry_run mode returning projected counts and proposed actions without DB persistence.
    """
    start_time = timezone.now()
    prefix = "[Dry-Run] " if dry_run else ""
    logger.info(
        f"{prefix}Synchronizing Google Sheet '{connection.name}' (ID: {connection.spreadsheet_id}, Tab: {connection.worksheet_name})."
    )

    if not connection.is_active and not dry_run:
        return {
            'success': True,
            'status': 'Paused',
            'total_rows': 0,
            'created': 0,
            'updated': 0,
            'unchanged': 0,
            'skipped': 0,
            'errors': 0,
            'last_synced_at': start_time.isoformat(),
            'message': 'Connection is currently paused.'
        }

    # Step 1: Fetch latest sheet data if not pre-supplied
    if headers is None and rows is None:
        try:
            gid_val = getattr(connection, 'gid', None) or '0'
            headers, rows = fetch_sheet(
                spreadsheet_id=connection.spreadsheet_id,
                gid=gid_val,
                sheet_name=connection.worksheet_name
            )
        except PermissionError as e:
            err_msg = str(e)
            logger.warning(f"Public access denied for sheet '{connection.name}': {err_msg}")
            if not dry_run:
                _record_failed_sync(connection, err_msg)
            return {
                'success': False,
                'status': 'Failed',
                'total_rows': 0,
                'created': 0,
                'updated': 0,
                'unchanged': 0,
                'skipped': 0,
                'errors': 1,
                'last_synced_at': timezone.now().isoformat(),
                'error_messages': [err_msg]
            }
        except Exception as e:
            err_msg = f"Network or fetch error: {e}"
            logger.error(f"Error fetching sheet '{connection.name}': {err_msg}")
            if not dry_run:
                _record_failed_sync(connection, err_msg)
            return {
                'success': False,
                'status': 'Failed',
                'total_rows': 0,
                'created': 0,
                'updated': 0,
                'unchanged': 0,
                'skipped': 0,
                'errors': 1,
                'last_synced_at': timezone.now().isoformat(),
                'error_messages': [err_msg]
            }

    if not headers or not any(headers):
        err_msg = (
            f"The Google Sheet '{connection.name}' returned no columns or headers. "
            "Please ensure the sheet contains column headers and is shared publicly."
        )
        logger.warning(err_msg)
        if not dry_run:
            _record_failed_sync(connection, err_msg)
        return {
            'success': False,
            'status': 'Failed',
            'total_rows': 0,
            'created': 0,
            'updated': 0,
            'unchanged': 0,
            'skipped': 0,
            'errors': 1,
            'last_synced_at': timezone.now().isoformat(),
            'error_messages': [err_msg]
        }

    # Step 2: Intelligent Multi-Engine Header & Pattern Matching
    active_entities = get_active_crm_entities()
    prior_mapping = dict(custom_field_mapping or connection.field_mapping or {})
    # Strip runtime transport arrays if present in stored JSON
    existing_profile = {k: v for k, v in prior_mapping.items() if k not in ('headers', 'rows', 'meta') and isinstance(v, str)}

    matching_spec = match_all_columns(
        headers=headers,
        sample_rows=rows or [],
        active_entities=active_entities,
        existing_mapping=existing_profile
    )

    # Honor explicit user confirmed overrides if column still exists in sheet
    reconciled_mapping: Dict[str, str] = dict(matching_spec['field_to_header'])
    for field_name, mapped_col in existing_profile.items():
        if mapped_col and mapped_col in headers:
            reconciled_mapping[field_name] = mapped_col

    total_rows = len(rows or [])
    created_count = 0
    updated_count = 0
    unchanged_count = 0
    skipped_count = 0
    errors_list: list[str] = []
    seen_row_identifiers: set[str] = set()
    sample_preview_actions: list[dict] = []

    default_channel = connection.channel
    if not default_channel:
        default_channel = Channel.objects.filter(name__iexact='Google Sheets').first() or Channel.objects.first()

    # Column pointers
    name_col = reconciled_mapping.get('name')
    first_name_col = reconciled_mapping.get('first_name')
    last_name_col = reconciled_mapping.get('last_name')
    phone_col = reconciled_mapping.get('phone')
    alt_phone_col = reconciled_mapping.get('alternate_phone')
    email_col = reconciled_mapping.get('email')
    product_col = reconciled_mapping.get('product')
    branch_col = reconciled_mapping.get('branch')
    channel_col = reconciled_mapping.get('channel')
    status_col = reconciled_mapping.get('status')
    notes_col = reconciled_mapping.get('notes')
    gender_col = reconciled_mapping.get('gender')
    class_mode_col = reconciled_mapping.get('class_mode')
    walkin_date_col = reconciled_mapping.get('walkin_date')
    counselor_col = reconciled_mapping.get('assigned_counselor')
    location_col = reconciled_mapping.get('location')

    # All headers mapped to specific CRM fields
    mapped_header_names = set(filter(None, reconciled_mapping.values()))
    unmapped_headers = [h for h in headers if h not in mapped_header_names]

    # Pre-fetch Counselor lookup dictionary
    User = get_user_model()
    counselor_users = list(User.objects.filter(is_active=True))
    counselor_lookup = {u.username.lower(): u for u in counselor_users}
    for u in counselor_users:
        if u.first_name:
            counselor_lookup[u.first_name.lower()] = u
            if u.last_name:
                counselor_lookup[f"{u.first_name} {u.last_name}".lower()] = u

    # Step 3: Process rows inside an atomic transaction (or simulate if dry_run)
    savepoint = None
    if dry_run:
        # In dry-run, we create an atomic block and roll back at the end
        atomic_context = transaction.atomic()
    else:
        atomic_context = transaction.atomic()

    with atomic_context:
        for loop_idx, r in enumerate(rows or [], start=2):
            if isinstance(r, (list, tuple)):
                r_dict = {'_row_index': loop_idx}
                for c_idx, h in enumerate(headers):
                    if c_idx < len(r):
                        r_dict[h] = str(r[c_idx]).strip()
                r = r_dict

            row_idx = r.get('_row_index') or loop_idx
            gid_part = getattr(connection, 'gid', None) or '0'
            row_id = f"{connection.spreadsheet_id}_{gid_part}_{connection.worksheet_name}_row_{row_idx}"
            legacy_row_id = f"{connection.spreadsheet_id}_{connection.worksheet_name}_row_{row_idx}"
            candidate_row_ids = [row_id, legacy_row_id]
            seen_row_identifiers.add(row_id)
            seen_row_identifiers.add(legacy_row_id)

            # Extract cell values with multi-candidate fallbacks
            name_val = get_field_value(r, name_col, 'Full name', 'Full Name', 'Name', 'Lead Name', 'Student Name', 'Candidate Name', 'பெயர்')
            if not name_val and (first_name_col or last_name_col):
                fn = get_field_value(r, first_name_col, 'First Name', 'FirstName', 'First')
                ln = get_field_value(r, last_name_col, 'Last Name', 'LastName', 'Last')
                name_val = f"{fn} {ln}".strip()

            phone_val = get_field_value(r, phone_col, 'Phone number', 'Phone Number', 'Mobile Number', 'Mobile number', 'Phone', 'Mobile', 'Contact', 'கைபேசி', 'தொலைபேசி')
            alt_phone_val = get_field_value(r, alt_phone_col, 'Alternate Phone', 'Alt Phone', 'Alternate Mobile', 'Secondary Phone')
            email_val = get_field_value(r, email_col, 'Email', 'Email Address', 'Mail Id', 'Mail', 'மின்னஞ்சல்')
            product_val = get_field_value(r, product_col, 'Product', 'Course', 'Wat course are you looking for ?', 'What course are you looking for?', 'Courses', 'Interested Course', 'படிப்பு')
            branch_val = get_field_value(r, branch_col, 'Branch', 'City', 'Preferred Branch', 'Location', 'Center', 'கிளை')
            channel_val = get_field_value(r, channel_col, 'Channel', 'Lead Source', 'Source', 'Platform')
            status_val = get_field_value(r, status_col, 'Status', 'Lead Status')
            notes_val = get_field_value(r, notes_col, 'Notes', 'Remarks', 'Comments / Questions', 'What you looking for?', 'What is your current status?', 'Comments', 'Feedback', 'குறிப்புகள்')
            gender_val = get_field_value(r, gender_col, 'Gender', 'Sex', 'பாலினம்')
            class_mode_val = get_field_value(r, class_mode_col, 'Class Mode', 'Learning Mode', 'Mode', 'Preference', 'பயிற்சி முறை')
            walkin_date_val = get_field_value(r, walkin_date_col, 'Walk-in Date', 'Visit Date', 'Appointment Date', 'வருகை தேதி')
            counselor_val = get_field_value(r, counselor_col, 'Counselor', 'Assigned Counselor', 'Telecaller', 'ஆலோசகர்')
            location_val = get_field_value(r, location_col, 'Location', 'City', 'Place', 'Native', 'இடம்')

            # Empty row detection
            if not name_val and not phone_val and not email_val:
                skipped_count += 1
                continue

            # Fallback name for WhatsApp / web forms with phone only
            if not name_val:
                if phone_val:
                    digits = re.sub(r'[^0-9]', '', str(phone_val))
                    disp_digits = digits[-10:] if len(digits) >= 10 else digits
                    name_val = f"{connection.name} Lead ({disp_digits})"
                elif email_val:
                    name_val = f"{connection.name} Lead ({email_val.split('@')[0]})"
                else:
                    name_val = f"{connection.name} Lead"

            # If phone column contains text remarks instead of digits, capture note and handle gracefully
            p_digits = re.sub(r'\D', '', str(phone_val))
            if phone_val and len(p_digits) < 7 and not str(phone_val).startswith('NoPhone-'):
                phone_remark = str(phone_val).strip()
                notes_val = f"{notes_val} | [Phone Note]: {phone_remark}".strip(' |')
                if not sheet_call_note:
                    sheet_call_note = phone_remark
                phone_val = ''

            # Validate contactability
            if not phone_val and not email_val:
                if name_val:
                    phone_val = f"NoPhone-{connection.id}-{row_idx}"[:20]
                else:
                    errors_list.append(f"Row {row_idx}: Both Phone and Email are missing.")
                    skipped_count += 1
                    continue

            # Normalization
            norm_phone = normalize_phone(phone_val)
            if norm_phone:
                phone_val = norm_phone
            if len(phone_val) > 20:
                phone_val = phone_val[:20]

            email_val = normalize_email(email_val)
            norm_alt = normalize_phone(alt_phone_val)
            if norm_alt:
                alt_phone_val = norm_alt

            # Resolve Foreign Keys: Branch, Product, Channel, Counselor
            branch_obj = connection.branch
            if branch_val:
                b_found = Branch.objects.filter(name__icontains=branch_val).first()
                if b_found:
                    branch_obj = b_found
            if not branch_obj:
                branch_obj = Branch.objects.filter(status='Active').first() or Branch.objects.first()

            product_obj = None
            if product_val:
                product_obj = Product.objects.filter(name__icontains=product_val).first()

            channel_obj = default_channel
            if channel_val:
                c_found = Channel.objects.filter(name__icontains=channel_val).first()
                if c_found:
                    channel_obj = c_found

            counselor_obj = None
            if counselor_val:
                counselor_clean = counselor_val.strip().lower()
                counselor_obj = counselor_lookup.get(counselor_clean)
                if not counselor_obj:
                    for name_key, u in counselor_lookup.items():
                        if counselor_clean in name_key or name_key in counselor_clean:
                            counselor_obj = u
                            break

            resolved_date = parse_flexible_date(walkin_date_val)

            resolved_status = LeadStatus.NEW
            sheet_call_note = None
            classified_call_status = None
            classified_call_outcome = None
            if status_val:
                s_clean = status_val.strip()
                resolved_status, classified_call_status, classified_call_outcome = classify_sheet_status(s_clean)
                sheet_call_note = s_clean

            # Preserve unmapped form fields in lead.custom_fields['all_answers'] and append to notes
            unmapped_answers: Dict[str, str] = {}
            extra_field_strings: list[str] = []

            for h in unmapped_headers:
                hv = r.get(h)
                if hv is not None and str(hv).strip():
                    unmapped_answers[h] = str(hv).strip()
                    extra_field_strings.append(f"{h}: {str(hv).strip()}")

            if gender_val and 'gender' not in [normalize_header(x.split(':')[0]) for x in extra_field_strings]:
                extra_field_strings.insert(0, f"Gender: {gender_val}")

            if class_mode_val and 'mode' not in [normalize_header(x.split(':')[0]) for x in extra_field_strings]:
                extra_field_strings.append(f"Class Mode: {class_mode_val}")

            if extra_field_strings:
                extra_str = " | ".join(extra_field_strings)
                notes_val = f"{notes_val} | [Form Data]: {extra_str}".strip(' |')

            # Build hash for change detection
            mapped_snapshot = {
                'name': name_val,
                'phone': phone_val,
                'email': email_val,
                'alternate_phone': alt_phone_val,
                'product': product_obj.id if product_obj else None,
                'branch': branch_obj.id if branch_obj else None,
                'status': resolved_status,
                'notes': notes_val,
                'class_mode': class_mode_val,
                'walkin_date': str(resolved_date) if resolved_date else None,
                'call_notes': sheet_call_note,
            }
            row_hash = compute_row_hash(mapped_snapshot)

            # Check existing RowMapping (idempotent upsert via external row identifier)
            row_mapping = GoogleSheetRowMapping.objects.filter(
                connection=connection,
                row_identifier__in=candidate_row_ids
            ).select_related('lead').first()

            if row_mapping:
                lead = row_mapping.lead
                if row_mapping.row_identifier != row_id and not dry_run:
                    row_mapping.row_identifier = row_id
                    row_mapping.save(update_fields=['row_identifier', 'updated_at'])
                if row_mapping.row_data_hash != row_hash:
                    # In-place non-destructive update: Sheet -> CRM (protect non-blanks)
                    if not dry_run:
                        if name_val and lead.name != name_val:
                            lead.name = name_val
                        if phone_val and lead.phone != phone_val:
                            lead.phone = phone_val
                            lead.normalized_phone = normalize_phone(phone_val)
                        if email_val and lead.email != email_val:
                            lead.email = email_val
                        if alt_phone_val and getattr(lead, 'alternate_phone', None) != alt_phone_val:
                            lead.alternate_phone = alt_phone_val
                        if product_obj and lead.product != product_obj:
                            lead.product = product_obj
                        if branch_obj and lead.branch != branch_obj:
                            lead.branch = branch_obj
                        if counselor_obj and (not lead.assigned_counselor or lead.assigned_counselor != counselor_obj):
                            lead.assigned_counselor = counselor_obj
                            lead.assignment_status = 'Assigned'
                        if resolved_status and lead.status != resolved_status:
                            lead.status = resolved_status
                        if resolved_date and not lead.center_visit_date:
                            lead.center_visit_date = resolved_date
                        if notes_val and notes_val not in (lead.notes or ''):
                            lead.notes = f"{lead.notes or ''}\n[Sheet Update]: {notes_val}".strip()

                        # Preserve unmapped form answers & custom fields
                        lead_custom = dict(lead.custom_fields or {})
                        if class_mode_val:
                            lead_custom['class_mode'] = class_mode_val
                            if 'demo' in class_mode_val.lower():
                                lead_custom['join_preference'] = 'Demo Class'
                            elif 'online' in class_mode_val.lower():
                                lead_custom['join_preference'] = 'Online'
                            elif 'offline' in class_mode_val.lower() or 'classroom' in class_mode_val.lower():
                                lead_custom['join_preference'] = 'Classroom'
                            elif 'hybrid' in class_mode_val.lower():
                                lead_custom['join_preference'] = 'Hybrid'
                        if status_val:
                            lead_custom['sheet_status'] = status_val
                        if sheet_call_note:
                            lead_custom['call_notes'] = sheet_call_note
                            call_note_tag = f"[Call Notes]: {sheet_call_note}"
                            if call_note_tag not in (lead.notes or ''):
                                lead.notes = f"{lead.notes or ''}\n{call_note_tag}".strip()
                            try:
                                from calls.models import CallHistory, CallStatus, CallOutcome
                                call_caller = counselor_obj or triggered_by or connection.created_by
                                if not CallHistory.objects.filter(lead=lead, notes=sheet_call_note).exists():
                                    CallHistory.objects.create(
                                        lead=lead,
                                        caller=call_caller,
                                        telecaller=counselor_obj if (counselor_obj and getattr(counselor_obj, 'role', '') == 'TELECALLER') else None,
                                        manager=counselor_obj if (counselor_obj and getattr(counselor_obj, 'role', '') in ('BRANCH_HEAD', 'SALES_HEAD', 'ADMIN')) else None,
                                        call_status=classified_call_status or CallStatus.CONNECTED,
                                        call_outcome=classified_call_outcome or CallOutcome.FOLLOW_UP_REQUIRED,
                                        notes=sheet_call_note,
                                        notes_completed=True,
                                        duration=60,
                                        call_started_at=timezone.now(),
                                        call_ended_at=timezone.now(),
                                    )
                            except Exception as e:
                                logger.info(f"Call history sync note: {e}")
                        if location_val:
                            lead_custom['location'] = location_val
                        if unmapped_answers:
                            current_answers = dict(lead_custom.get('all_answers', {}))
                            current_answers.update(unmapped_answers)
                            lead_custom['all_answers'] = current_answers
                        lead.custom_fields = lead_custom

                        lead.save()

                        from leads.qualification import autofill_lead_qualification
                        autofill_lead_qualification(lead, dict(r), source='Google Sheets', preserve_manual_edits=True)

                        row_mapping.row_data_hash = row_hash
                        row_mapping.row_index = row_idx
                        row_mapping.source_status = 'Active'
                        row_mapping.save()

                    updated_count += 1
                    if len(sample_preview_actions) < 10:
                        sample_preview_actions.append({
                            'row': row_idx,
                            'action': 'UPDATE',
                            'name': name_val,
                            'phone': phone_val,
                            'reason': 'Row data modified in sheet; CRM updated in-place.'
                        })
                else:
                    # Content unchanged
                    if not dry_run:
                        if row_mapping.source_status != 'Active' or row_mapping.row_index != row_idx:
                            row_mapping.source_status = 'Active'
                            row_mapping.row_index = row_idx
                            row_mapping.save(update_fields=['source_status', 'row_index', 'updated_at'])
                    unchanged_count += 1
                    if len(sample_preview_actions) < 10:
                        sample_preview_actions.append({
                            'row': row_idx,
                            'action': 'UNCHANGED',
                            'name': name_val,
                            'phone': phone_val,
                            'reason': 'Row data hash identical to CRM record.'
                        })

            else:
                # Row not yet mapped: process through centralized intake & 10-day duplicate governance
                from leads.intake import intake_lead
                from leads.qualification import autofill_lead_qualification

                row_payload = dict(r)
                row_payload.update(mapped_snapshot)
                if unmapped_answers:
                    row_payload['all_answers'] = unmapped_answers

                if not dry_run:
                    from leads.intake import phone10, CentralizedLeadIntakeService
                    p10 = phone10(phone_val)
                    clean_phone = phone_val if p10 else (phone_val or f"NoPhone-{connection.id}-{row_idx}")
                    intake_res = CentralizedLeadIntakeService.ingest(
                        phone=clean_phone,
                        source='Google Sheets',
                        channel_name=channel_obj.name if channel_obj else 'Google Sheets',
                        name=name_val or f"{connection.name} Lead",
                        email=email_val,
                        branch=branch_obj,
                        product=product_obj,
                        note=notes_val,
                        activity_user=triggered_by or connection.created_by,
                        provider_event_id=row_id,
                        data_payload=row_payload,
                    )
                    target_lead = intake_res.lead
                    is_new_lead = intake_res.created

                    autofill_lead_qualification(target_lead, row_payload, source='Google Sheets')

                    # Extra fields persistence
                    save_fields = ['updated_at']
                    if resolved_status and target_lead.status != resolved_status:
                        target_lead.status = resolved_status
                        save_fields.append('status')
                    if alt_phone_val and not target_lead.alternate_phone:
                        target_lead.alternate_phone = alt_phone_val
                        save_fields.append('alternate_phone')
                    if counselor_obj and not target_lead.assigned_counselor:
                        target_lead.assigned_counselor = counselor_obj
                        target_lead.assignment_status = 'Assigned'
                        save_fields.extend(['assigned_counselor', 'assignment_status'])
                    if resolved_date and not target_lead.center_visit_date:
                        target_lead.center_visit_date = resolved_date
                        save_fields.append('center_visit_date')

                    t_custom = dict(target_lead.custom_fields or {})
                    if class_mode_val:
                        t_custom['class_mode'] = class_mode_val
                        if 'demo' in class_mode_val.lower():
                            t_custom['join_preference'] = 'Demo Class'
                        elif 'online' in class_mode_val.lower():
                            t_custom['join_preference'] = 'Online'
                        elif 'offline' in class_mode_val.lower() or 'classroom' in class_mode_val.lower():
                            t_custom['join_preference'] = 'Classroom'
                        elif 'hybrid' in class_mode_val.lower():
                            t_custom['join_preference'] = 'Hybrid'
                    if status_val:
                        t_custom['sheet_status'] = status_val
                    if sheet_call_note:
                        t_custom['call_notes'] = sheet_call_note
                        call_note_tag = f"[Call Notes]: {sheet_call_note}"
                        if call_note_tag not in (target_lead.notes or ''):
                            target_lead.notes = f"{target_lead.notes or ''}\n{call_note_tag}".strip()
                            save_fields.append('notes')
                        try:
                            from calls.models import CallHistory, CallStatus, CallOutcome
                            call_caller = counselor_obj or triggered_by or connection.created_by
                            if not CallHistory.objects.filter(lead=target_lead, notes=sheet_call_note).exists():
                                CallHistory.objects.create(
                                    lead=target_lead,
                                    caller=call_caller,
                                    telecaller=counselor_obj if (counselor_obj and getattr(counselor_obj, 'role', '') == 'TELECALLER') else None,
                                    manager=counselor_obj if (counselor_obj and getattr(counselor_obj, 'role', '') in ('BRANCH_HEAD', 'SALES_HEAD', 'ADMIN')) else None,
                                    call_status=classified_call_status or CallStatus.CONNECTED,
                                    call_outcome=classified_call_outcome or CallOutcome.FOLLOW_UP_REQUIRED,
                                    notes=sheet_call_note,
                                    notes_completed=True,
                                    duration=60,
                                    call_started_at=timezone.now(),
                                    call_ended_at=timezone.now(),
                                )
                        except Exception as e:
                            logger.info(f"Call history intake note: {e}")
                    if location_val:
                        t_custom['location'] = location_val
                    if unmapped_answers:
                        t_custom['all_answers'] = unmapped_answers
                    target_lead.custom_fields = t_custom
                    save_fields.append('custom_fields')

                    if is_new_lead:
                        target_lead.is_offline = True
                        target_lead.visitor_status = 'Waiting'
                        if not counselor_obj:
                            target_lead.assignment_status = 'Pending Assignment'
                        else:
                            target_lead.assignment_status = 'Assigned'
                        save_fields.extend(['is_offline', 'visitor_status', 'assignment_status'])
                        target_lead.save(update_fields=save_fields)
                        created_count += 1
                    else:
                        target_lead.save(update_fields=save_fields)
                        updated_count += 1

                    GoogleSheetRowMapping.objects.create(
                        connection=connection,
                        lead=target_lead,
                        row_identifier=row_id,
                        row_index=row_idx,
                        row_data_hash=row_hash,
                        source_status='Active'
                    )
                else:
                    # In dry-run mode, check if phone or email matches existing lead
                    existing_dup = find_duplicate_lead(phone=phone_val, email=email_val)
                    if existing_dup:
                        updated_count += 1
                        act = 'EXISTING_MATCH'
                        reason = f"Matches existing lead #{existing_dup.id} ({existing_dup.name})"
                    else:
                        created_count += 1
                        act = 'CREATE'
                        reason = "New unique lead; will be created in CRM"

                    if len(sample_preview_actions) < 10:
                        sample_preview_actions.append({
                            'row': row_idx,
                            'action': act,
                            'name': name_val,
                            'phone': phone_val,
                            'reason': reason
                        })

        # Check for deleted rows from sheet
        if total_rows > 0 and not dry_run:
            removed_mappings = GoogleSheetRowMapping.objects.filter(
                connection=connection,
                source_status='Active'
            ).exclude(row_identifier__in=seen_row_identifiers)
            if removed_mappings.exists():
                removed_mappings.update(source_status='Removed from source', updated_at=timezone.now())

        if dry_run:
            # Force rollback so dry-run never alters MySQL
            transaction.set_rollback(True)

    # Step 4: Audit sync history & update connection state (if not dry_run)
    sync_status = 'Success'
    if errors_list and (created_count > 0 or updated_count > 0 or unchanged_count > 0):
        sync_status = 'Completed with Errors'
    elif errors_list and created_count == 0 and updated_count == 0 and unchanged_count == 0:
        sync_status = 'Failed'

    if not dry_run:
        GoogleSheetSyncHistory.objects.create(
            connection=connection,
            rows_checked=total_rows,
            new_leads=created_count,
            updated_leads=updated_count,
            skipped=skipped_count + unchanged_count,
            failed=len(errors_list),
            assigned_leads=created_count,
            status=sync_status,
            error_summary="\n".join(errors_list[:50])
        )

        # Store rich mapping metadata in connection.field_mapping
        reconciled_mapping['headers'] = headers
        reconciled_mapping['rows'] = rows
        reconciled_mapping['meta'] = {
            'column_mappings': matching_spec['column_mappings'],
            'unmapped_headers': unmapped_headers,
            'high_confidence_count': matching_spec['high_confidence_count'],
            'medium_confidence_count': matching_spec['medium_confidence_count'],
            'low_confidence_count': matching_spec['low_confidence_count'],
            'last_inspected_at': timezone.now().isoformat()
        }

        connection.field_mapping = reconciled_mapping
        connection.last_sync_time = timezone.now()
        connection.last_sync_status = sync_status
        connection.last_sync_error = "\n".join(errors_list[:5]) if errors_list else ""
        connection.total_leads_imported = connection.row_mappings.count()
        connection.connection_status = 'ACTIVE'
        connection.save(update_fields=[
            'field_mapping', 'last_sync_time', 'last_sync_status',
            'last_sync_error', 'total_leads_imported', 'connection_status', 'updated_at'
        ])

    logger.info(
        f"{prefix}Sync completed for '{connection.name}': Status={sync_status} | Rows={total_rows} | "
        f"Created={created_count} | Updated={updated_count} | Unchanged={unchanged_count} | Skipped={skipped_count} | Errors={len(errors_list)}"
    )

    return {
        'success': sync_status in ('Success', 'Completed with Errors'),
        'status': sync_status,
        'dry_run': dry_run,
        'total_rows': total_rows,
        'rows_checked': total_rows,
        'created': created_count,
        'new_leads': created_count,
        'updated': updated_count,
        'updated_leads': updated_count,
        'unchanged': unchanged_count,
        'skipped': skipped_count,
        'errors': len(errors_list),
        'failed': len(errors_list),
        'assigned_leads': created_count,
        'last_synced_at': (connection.last_sync_time or timezone.now()).isoformat(),
        'error_messages': errors_list,
        'errors_list': errors_list,
        'field_mapping': reconciled_mapping,
        'column_mappings': matching_spec['column_mappings'],
        'unmapped_headers': unmapped_headers,
        'sample_preview_actions': sample_preview_actions,
        'message': f"{prefix}Sync complete! {total_rows} rows checked: {created_count} created, {updated_count} updated, {unchanged_count} unchanged, {skipped_count} skipped."
    }


def _record_failed_sync(connection: GoogleSheetConnection, err_msg: str):
    """Safely updates connection and writes audit record on connection/fetch error."""
    now = timezone.now()
    GoogleSheetSyncHistory.objects.create(
        connection=connection,
        rows_checked=0,
        new_leads=0,
        updated_leads=0,
        skipped=0,
        failed=1,
        status='Failed',
        error_summary=err_msg
    )
    connection.last_sync_time = now
    connection.last_sync_status = 'Failed'
    connection.last_sync_error = err_msg
    connection.connection_status = 'ACTIVE'
    connection.save(update_fields=['last_sync_time', 'last_sync_status', 'last_sync_error', 'connection_status', 'updated_at'])

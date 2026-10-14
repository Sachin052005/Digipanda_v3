"""
Lead Detail Service
Handles structured field extraction, column mapping, inline editing, navigation tracking,
and metadata for the modern full lead-details interface.
"""

import re
from datetime import datetime, date
from django.utils import timezone
from django.db.models import Q
from django.core.exceptions import ValidationError, PermissionDenied

from accounts.models import User, UserRole
from branches.models import Branch
from lead_channels.models import Channel
from products.models import Product
from accounts.permissions import can_edit_lead, can_assign_lead, get_accessible_branch_ids
from leads.duplicates import normalize_phone, normalize_email, find_duplicate_lead
from activities.utils import log_activity
from .models import Lead, LeadStatus, LeadOwnerType
from calls.models import CallHistory, CallOutcome, CallStatus
from followups.models import FollowUp, FollowUpStatus
from .handoff_service import change_lead_status, reassign_lead


FIELD_KEY_TO_CANONICAL_LABEL = {
    'name': 'Name',
    'phone': 'Phone',
    'email': 'Email',
    'degree': 'Degree',
    'passed_out': 'PassedOut',
    'base_branch': 'Base Branch',
    'working_status': 'Working status',
    'assignee_name': 'Assignee Name',
    'assignee': 'Assignee Name',
    'pref_exam_loc': 'Preferred Exam Location',
    'purpose': 'Purpose',
    'pref_branch': 'Preferred Branch',
    'total_experience': 'Total Experience',
    'pipeline_substatus': 'Pipeline Sub-Status',
    'status': 'Status',
    'college': 'College',
    'join_preference': 'How would you like to join the course',
    'lead_source': 'Lead Source 1',
    'retargeted': 'Retargeted',
    'courses': 'Courses',
    'current_ctc': 'Current CTC',
    'expected_ctc': 'Expected CTC',
    'designation': 'Designation',
    'location': 'Location',
    'center_visit': 'Center Visit Scheduled Date',
}

FIELD_KEY_ALIASES = {
    'degree': ['degree', 'qualification', 'education'],
    'passed_out': ['passedout', 'passed out', 'year of pass', 'passing year', 'yop'],
    'working_status': ['working status', 'employment status', 'working', 'job status', 'status of work'],
    'pref_exam_loc': ['preferred exam location', 'exam location', 'exam city', 'pref exam loc'],
    'purpose': ['purpose', 'objective', 'reason', 'intent'],
    'pref_branch': ['preferred branch', 'pref branch'],
    'total_experience': ['total experience', 'experience', 'exp', 'work experience'],
    'college': ['college', 'university', 'institution', 'college name'],
    'join_preference': ['how would you like to join the course', 'joining preference', 'mode', 'course mode', 'batch mode'],
    'retargeted': ['retargeted', 'retarget', 're-target', 'is retargeted'],
    'current_ctc': ['current ctc', 'ctc', 'current salary', 'salary'],
    'expected_ctc': ['expected ctc', 'exp ctc', 'expected salary'],
    'designation': ['designation', 'role', 'current role', 'job title'],
    'location': ['location', 'city', 'native', 'address'],
    'center_visit': ['center visit scheduled date', 'visit date', 'scheduled visit'],
    'lead_source': ['lead source', 'source', 'lead source 1'],
    'courses': ['courses', 'course', 'domain', 'subject'],
}


def format_relative_time(dt):
    """Formats a datetime into relative human time (e.g. '1h ago', '2d ago')."""
    if not dt:
        return 'Empty'
    now = timezone.now()
    diff = now - dt
    total_seconds = int(diff.total_seconds())

    if total_seconds < 60:
        return 'Just now'
    elif total_seconds < 3600:
        mins = total_seconds // 60
        return f"{mins}m ago"
    elif total_seconds < 86400:
        hours = total_seconds // 3600
        return f"{hours}h ago"
    elif total_seconds < 86400 * 7:
        days = total_seconds // 86400
        return f"{days}d ago"
    else:
        return dt.strftime('%d %b, %Y')


def extract_parsed_lead_attributes(notes_text):
    """
    Extracts key-value attributes from lead.notes if stored in string formats
    (e.g., 'Degree: B.Tech | PassedOut: 2024 | College: Anna Univ').
    """
    if not notes_text:
        return {}

    clean = notes_text
    clean = re.sub(r'\[Sheet Update\]:?', '', clean)
    clean = re.sub(r'\[Form Data\]:?', '', clean)

    attrs = {}

    def add_key_variants(key_str, val_str):
        k_raw = key_str.strip().lower()
        if not k_raw or k_raw == 'timestamp':
            return
        v = val_str.strip()
        attrs[k_raw] = v
        # underscored version
        k_under = k_raw.replace(' ', '_').replace('-', '_')
        attrs[k_under] = v
        # space separated version
        k_space = k_under.replace('_', ' ')
        attrs[k_space] = v
        # special handling for passedout / passed_out
        if 'passedout' in k_raw:
            attrs['passed_out'] = v
            attrs['passedout'] = v
            attrs['passed out'] = v
        if 'preferred_branch' in k_under:
            attrs['pref_branch'] = v
        if 'preferred_exam' in k_under or 'pref_exam' in k_under:
            attrs['pref_exam_location'] = v
            attrs['pref_exam_loc'] = v
            attrs['pref_exam'] = v

    for line in clean.splitlines():
        line = line.strip()
        if not line or line.startswith('['):
            continue
        if '|' in line:
            tokens = line.split('|')
            for token in tokens:
                token = token.strip()
                if ':' in token:
                    k, v = token.split(':', 1)
                    add_key_variants(k, v)
        elif ':' in line and not line.startswith('http'):
            k, v = line.split(':', 1)
            add_key_variants(k, v)

    return attrs


def update_lead_notes_attribute(notes_text, field_key, new_value):
    """
    Updates or inserts a key-value attribute inside lead.notes without disturbing
    existing timestamp logs or other piped/unpiped notes.
    """
    aliases = FIELD_KEY_ALIASES.get(field_key, [field_key.lower()])
    canonical_label = FIELD_KEY_TO_CANONICAL_LABEL.get(field_key, field_key.replace('_', ' ').title())
    new_val_clean = str(new_value or '').strip()

    lines = (notes_text or '').splitlines()
    found = False
    new_lines = []
    piped_line_index = -1

    for line in lines:
        line_stripped = line.strip()
        # Preserve log lines [YYYY-MM-DD...] exactly as-is
        if line_stripped.startswith('[') and ']' in line_stripped and re.match(r'^\[\d{4}-\d{2}-\d{2}', line_stripped):
            new_lines.append(line)
            continue

        if '|' in line:
            piped_line_index = len(new_lines)
            tokens = [t.strip() for t in line.split('|')]
            new_tokens = []
            for t in tokens:
                if ':' in t:
                    k, v = t.split(':', 1)
                    k_norm = k.strip().lower()
                    if k_norm in aliases:
                        found = True
                        if new_val_clean and new_val_clean not in ('Empty', '-'):
                            new_tokens.append(f"{canonical_label}: {new_val_clean}")
                        continue
                new_tokens.append(t)
            joined = " | ".join([t for t in new_tokens if t])
            if joined:
                new_lines.append(joined)
        elif ':' in line and not line_stripped.startswith('http'):
            k, v = line.split(':', 1)
            k_norm = k.strip().lower()
            if k_norm in aliases:
                found = True
                if new_val_clean and new_val_clean not in ('Empty', '-'):
                    new_lines.append(f"{canonical_label}: {new_val_clean}")
                continue
            new_lines.append(line)
        else:
            new_lines.append(line)

    if not found and new_val_clean and new_val_clean not in ('Empty', '-'):
        if piped_line_index >= 0 and piped_line_index < len(new_lines):
            new_lines[piped_line_index] = new_lines[piped_line_index] + f" | {canonical_label}: {new_val_clean}"
        else:
            new_lines.append(f"{canonical_label}: {new_val_clean}")

    return "\n".join([l for l in new_lines if l.strip()])


def build_lead_detail_context(lead, user=None):
    """
    Constructs a rich dictionary containing all header info, navigation,
    two-column structured fields (Column 1 and Column 2), inline edit metadata,
    and call-logging context.
    """
    # 1. Notes parsed attributes lookup
    notes_attrs = extract_parsed_lead_attributes(lead.notes)

    def find_val(keys, default=''):
        for k in keys:
            if k in notes_attrs and notes_attrs[k]:
                return notes_attrs[k]
        return default

    # 2. Assignee info & avatar initials
    assignee = lead.assigned_telecaller or lead.assigned_counselor or lead.assigned_sales_head
    if assignee:
        assignee_name = assignee.get_full_name() or assignee.username
        parts = assignee_name.strip().split()
        if len(parts) >= 2:
            assignee_initials = (parts[0][0] + parts[1][0]).upper()
        else:
            assignee_initials = assignee_name[:2].upper()
    else:
        assignee_name = 'Unassigned'
        assignee_initials = 'UN'

    # 3. Format Phone
    phone_raw = str(lead.phone or '').strip()
    clean_digits = normalize_phone(phone_raw)
    if clean_digits:
        phone_display = f"+91 {clean_digits}" if len(clean_digits) == 10 else clean_digits
        whatsapp_phone = f"91{clean_digits}" if len(clean_digits) == 10 else clean_digits
    else:
        phone_display = phone_raw
        whatsapp_phone = ''

    # Lookup associated WhatsApp Conversation if exists
    chat_conversation = None
    try:
        from chat.models import Conversation
        from chat.whatsapp.webhook import format_phone_e164
        e164 = format_phone_e164(phone_raw)
        if e164:
            chat_conversation = Conversation.objects.filter(phone_number=e164).first()
        if not chat_conversation and clean_digits:
            chat_conversation = Conversation.objects.filter(phone_number__endswith=clean_digits[-10:]).first()
    except Exception:
        pass

    # 4. Dates & Relative Time
    captured_on_str = format_relative_time(lead.created_at)
    created_on_str = format_relative_time(lead.created_at)
    modified_on_str = format_relative_time(lead.updated_at)

    latest_status_hist = lead.status_history.order_by('-created_at').first()
    status_updated_str = format_relative_time(latest_status_hist.created_at) if latest_status_hist else modified_on_str

    latest_call = lead.calls.order_by('-call_started_at').first()
    if latest_call and latest_call.call_started_at:
        last_activity_on_str = format_relative_time(latest_call.call_started_at)
        last_activity_type = f"Call ({latest_call.call_outcome or latest_call.call_status})"
    elif lead.notes:
        last_activity_on_str = modified_on_str
        last_activity_type = "User Note"
    else:
        last_activity_on_str = created_on_str
        last_activity_type = "Lead Ingested"

    # 5. Field values mapping
    val_degree = find_val(['degree', 'qualification', 'education'])
    val_passed_out = find_val(['passedout', 'passed out', 'year of pass', 'passing year', 'yop'])
    val_purpose = find_val(['purpose', 'objective', 'reason', 'intent'])
    val_base_branch = lead.branch.name if lead.branch else find_val(['branch', 'base branch'])
    val_pref_branch = ", ".join(lead.get_all_branch_names()) if lead.secondary_branches.exists() else find_val(['preferred branch', 'pref branch'])
    val_working_status = find_val(['working status', 'employment status', 'working', 'job status', 'status of work'])
    val_total_exp = find_val(['total experience', 'experience', 'exp', 'work experience'])
    val_pref_exam_loc = find_val(['preferred exam location', 'exam location', 'exam city'])
    val_join_pref = find_val(['how would you like to join the course', 'joining preference', 'mode', 'course mode', 'batch mode'])
    val_lead_source = lead.channel.name if lead.channel else (lead.source or find_val(['lead source', 'source']))
    val_college = find_val(['college', 'university', 'institution', 'college name'])
    val_retargeted = find_val(['retargeted', 'retarget', 're-target', 'is retargeted'])
    val_capture_freq = find_val(['capture frequency', 'frequency', 'import count'], '1')
    val_designation = find_val(['designation', 'role', 'current role', 'job title'])
    val_courses = lead.product.name if lead.product else find_val(['courses', 'course', 'domain', 'subject'])
    val_location = find_val(['location', 'city', 'native', 'address']) or (lead.branch.city if lead.branch and hasattr(lead.branch, 'city') else '')
    val_current_ctc = find_val(['current ctc', 'ctc', 'current salary', 'salary'])
    val_expected_ctc = find_val(['expected ctc', 'exp ctc', 'expected salary'])

    # Center Visit Scheduled Date (check followups or notes)
    visit_followup = lead.followups.filter(Q(status=FollowUpStatus.PENDING) | Q(notes__icontains='visit')).order_by('follow_up_date').first()
    if visit_followup and visit_followup.follow_up_date:
        val_center_visit = f"{visit_followup.follow_up_date.strftime('%d/%m/%Y')} {visit_followup.follow_up_time.strftime('%H:%M:%S') if visit_followup.follow_up_time else ''}".strip()
        val_center_visit_raw = f"{visit_followup.follow_up_date.strftime('%Y-%m-%d')}T{visit_followup.follow_up_time.strftime('%H:%M') if visit_followup.follow_up_time else '10:00'}"
    else:
        val_center_visit = find_val(['center visit scheduled date', 'visit date', 'scheduled visit'])
        val_center_visit_raw = ''

    # Dropdown Options for Inline Editing
    branch_options = [{'value': b.name, 'label': b.name} for b in Branch.objects.filter(status='Active').order_by('name')]
    product_options = [{'value': p.name, 'label': p.name} for p in Product.objects.filter(status='Active').order_by('name')]
    channel_options = [{'value': c.name, 'label': c.name} for c in Channel.objects.filter(status='Active').order_by('name')]
    status_options = [{'value': s[0], 'label': s[1]} for s in LeadStatus.choices]
    working_status_options = [{'value': s, 'label': s} for s in ['Working professional', 'Student', 'Looking for job', 'Fresher', 'Career Gap', 'Freelancer', 'Other']]
    purpose_options = [{'value': p, 'label': p} for p in ['Career Transition', 'Upskilling', 'Placement Assistance', 'Higher Studies', 'Certification', 'Interview Preparation', 'Other']]
    join_pref_options = [{'value': j, 'label': j} for j in ['Online', 'Classroom', 'Hybrid', 'Weekend Batch', 'Weekday Batch']]
    retargeted_options = [{'value': 'Yes', 'label': 'Yes'}, {'value': 'No', 'label': 'No'}]

    can_assign = can_assign_lead(user, lead) if user and user.is_authenticated else False
    if can_assign:
        users_qs = User.objects.filter(is_active=True, role__in=[UserRole.TELECALLER, UserRole.COUNSELOR, UserRole.SALES_HEAD])
        if lead.branch_id:
            users_qs = users_qs.filter(Q(branch_id=lead.branch_id) | Q(role=UserRole.SALES_HEAD))
        assignee_options = [{'value': u.username, 'label': f"{u.get_full_name() or u.username} ({u.role})"} for u in users_qs.order_by('username')]
        assignee_options.insert(0, {'value': '', 'label': '-- Unassigned --'})
    else:
        assignee_options = []

    can_change_base_branch = user.is_admin_user or getattr(user, 'role', '') == UserRole.SALES_HEAD if user and user.is_authenticated else False

    # 6. Column 1 Fields (Left Column)
    col1_fields = [
        {
            'key': 'phone',
            'label': 'Phone',
            'type': 'phone',
            'control_type': 'phone',
            'is_editable': True,
            'icon': 'phone',
            'badge': 'SIM',
            'flag': '🇮🇳',
            'value': phone_display,
            'raw_value': lead.phone or '',
            'is_empty': not bool(lead.phone),
        },
        {
            'key': 'degree',
            'label': 'Degree',
            'type': 'text',
            'control_type': 'text',
            'is_editable': True,
            'icon': 'T',
            'value': val_degree or 'Empty',
            'raw_value': val_degree or '',
            'is_empty': not bool(val_degree),
        },
        {
            'key': 'passed_out',
            'label': 'PassedOut',
            'type': 'text',
            'control_type': 'number',
            'is_editable': True,
            'icon': 'T',
            'value': val_passed_out or 'Empty',
            'raw_value': val_passed_out or '',
            'is_empty': not bool(val_passed_out),
        },
        {
            'key': 'base_branch',
            'label': 'Base Branch',
            'type': 'select',
            'control_type': 'select',
            'is_editable': can_change_base_branch,
            'read_only_reason': 'Base Branch modification requires administrator or sales head authorization.' if not can_change_base_branch else '',
            'options': branch_options,
            'icon': 'select',
            'value': val_base_branch or 'Empty',
            'raw_value': lead.branch.name if lead.branch else (val_base_branch or ''),
            'is_empty': not bool(val_base_branch),
        },
        {
            'key': 'working_status',
            'label': 'Working status',
            'type': 'select',
            'control_type': 'select',
            'is_editable': True,
            'options': working_status_options,
            'icon': 'select',
            'value': val_working_status or 'Empty',
            'raw_value': val_working_status or '',
            'is_empty': not bool(val_working_status),
        },
        {
            'key': 'assignee_name',
            'label': 'Assignee Name',
            'type': 'text',
            'control_type': 'select',
            'is_editable': can_assign,
            'read_only_reason': 'Lead reassignment requires manager or administrator authorization.' if not can_assign else '',
            'options': assignee_options,
            'icon': 'T',
            'value': assignee_name if assignee_name != 'Unassigned' else 'Empty',
            'raw_value': assignee.username if assignee else '',
            'is_empty': assignee_name == 'Unassigned',
        },
        {
            'key': 'join_preference',
            'label': 'How would you like to join the course',
            'type': 'text',
            'control_type': 'select',
            'is_editable': True,
            'options': join_pref_options,
            'icon': 'T',
            'value': val_join_pref or 'Empty',
            'raw_value': val_join_pref or '',
            'is_empty': not bool(val_join_pref),
        },
        {
            'key': 'lead_source',
            'label': 'Lead Source 1',
            'type': 'select',
            'control_type': 'select',
            'is_editable': True,
            'options': channel_options,
            'icon': 'select',
            'value': val_lead_source or 'Empty',
            'raw_value': lead.channel.name if lead.channel else (lead.source or val_lead_source or ''),
            'is_empty': not bool(val_lead_source),
        },
        {
            'key': 'retargeted',
            'label': 'Retargeted',
            'type': 'select',
            'control_type': 'select',
            'is_editable': True,
            'options': retargeted_options,
            'icon': 'select',
            'value': val_retargeted or 'Empty',
            'raw_value': val_retargeted or '',
            'is_empty': not bool(val_retargeted),
        },
        {
            'key': 'captured_on',
            'label': 'Captured On',
            'type': 'date',
            'is_editable': False,
            'read_only_reason': 'System-managed field: Automatically calculated from intake timestamp.',
            'icon': 'calendar',
            'value': captured_on_str,
            'raw_value': str(lead.created_at),
            'info_tooltip': lead.created_at.strftime('%Y-%m-%d %H:%M') if lead.created_at else '',
            'is_empty': False,
        },
        {
            'key': 'last_activity_on',
            'label': 'Last Activity On',
            'type': 'date',
            'is_editable': False,
            'read_only_reason': 'System-managed field: Automatically updated from calls and interactions.',
            'icon': 'calendar',
            'value': last_activity_on_str,
            'raw_value': last_activity_on_str,
            'info_tooltip': 'Latest call or status interaction',
            'is_empty': False,
        },
        {
            'key': 'modified_on',
            'label': 'Modified On',
            'type': 'date',
            'is_editable': False,
            'read_only_reason': 'System-managed field: Automatically updated on record save.',
            'icon': 'calendar',
            'value': modified_on_str,
            'raw_value': str(lead.updated_at),
            'info_tooltip': lead.updated_at.strftime('%Y-%m-%d %H:%M') if lead.updated_at else '',
            'is_empty': False,
        },
        {
            'key': 'designation',
            'label': 'Designation',
            'type': 'text',
            'control_type': 'text',
            'is_editable': True,
            'icon': 'T',
            'value': val_designation or 'Empty',
            'raw_value': val_designation or '',
            'is_empty': not bool(val_designation),
        },
        {
            'key': 'location',
            'label': 'Location',
            'type': 'text',
            'control_type': 'text',
            'is_editable': True,
            'icon': 'T',
            'value': val_location or 'Empty',
            'raw_value': val_location or '',
            'is_empty': not bool(val_location),
        },
        {
            'key': 'expected_ctc',
            'label': 'Expected CTC',
            'type': 'text',
            'control_type': 'text',
            'is_editable': True,
            'icon': 'T',
            'value': val_expected_ctc or 'Empty',
            'raw_value': val_expected_ctc or '',
            'is_empty': not bool(val_expected_ctc),
        },
    ]

    # 7. Column 2 Fields (Right Column)
    col2_fields = [
        {
            'key': 'pref_exam_loc',
            'label': 'Preferred Exam Location',
            'type': 'text',
            'control_type': 'text',
            'is_editable': True,
            'icon': 'T',
            'value': val_pref_exam_loc or 'Empty',
            'raw_value': val_pref_exam_loc or '',
            'is_empty': not bool(val_pref_exam_loc),
        },
        {
            'key': 'purpose',
            'label': 'Purpose',
            'type': 'select',
            'control_type': 'select',
            'is_editable': True,
            'options': purpose_options,
            'icon': 'select',
            'value': val_purpose or 'Empty',
            'raw_value': val_purpose or '',
            'is_empty': not bool(val_purpose),
        },
        {
            'key': 'pref_branch',
            'label': 'Preferred Branch',
            'type': 'select',
            'control_type': 'select',
            'is_editable': True,
            'options': branch_options,
            'icon': 'select',
            'value': val_pref_branch or 'Empty',
            'raw_value': val_pref_branch or '',
            'is_empty': not bool(val_pref_branch),
        },
        {
            'key': 'total_experience',
            'label': 'Total Experience',
            'type': 'text',
            'control_type': 'text',
            'is_editable': True,
            'icon': 'T',
            'value': val_total_exp or 'Empty',
            'raw_value': val_total_exp or '',
            'is_empty': not bool(val_total_exp),
        },
        {
            'key': 'pipeline_substatus',
            'label': 'Pipeline Sub-Status',
            'type': 'select',
            'control_type': 'select',
            'is_editable': True,
            'options': status_options,
            'icon': 'select',
            'value': lead.status or 'Empty',
            'raw_value': lead.status or '',
            'is_empty': not bool(lead.status),
        },
        {
            'key': 'college',
            'label': 'College',
            'type': 'select',
            'control_type': 'text',
            'is_editable': True,
            'icon': 'select',
            'value': val_college or 'Empty',
            'raw_value': val_college or '',
            'is_empty': not bool(val_college),
        },
        {
            'key': 'capture_frequency',
            'label': 'Capture Frequency',
            'type': 'number',
            'is_editable': False,
            'read_only_reason': 'System-managed field: Automatically calculated from lead deduplication frequency.',
            'icon': '#',
            'value': val_capture_freq or '1',
            'raw_value': val_capture_freq or '1',
            'is_empty': False,
        },
        {
            'key': 'created_on',
            'label': 'Created On',
            'type': 'date',
            'is_editable': False,
            'read_only_reason': 'System-managed field: Original record creation timestamp.',
            'icon': 'calendar',
            'value': created_on_str,
            'raw_value': str(lead.created_at),
            'info_tooltip': lead.created_at.strftime('%Y-%m-%d %H:%M') if lead.created_at else '',
            'is_empty': False,
        },
        {
            'key': 'last_activity_type',
            'label': 'Last Activity Type',
            'type': 'select',
            'is_editable': False,
            'read_only_reason': 'System-managed field: Generated automatically based on the latest interaction type.',
            'icon': 'select',
            'value': last_activity_type,
            'raw_value': last_activity_type,
            'is_empty': False,
        },
        {
            'key': 'status_updated_on',
            'label': 'Status Last Updated On',
            'type': 'date',
            'is_editable': False,
            'read_only_reason': 'System-managed field: Timestamp of when the pipeline status last changed.',
            'icon': 'calendar',
            'value': status_updated_str,
            'raw_value': status_updated_str,
            'info_tooltip': 'Timestamp of last status modification',
            'is_empty': False,
        },
        {
            'key': 'courses',
            'label': 'Courses',
            'type': 'select',
            'control_type': 'select',
            'is_editable': True,
            'options': product_options,
            'icon': 'select',
            'value': val_courses or 'Empty',
            'raw_value': lead.product.name if lead.product else (val_courses or ''),
            'is_empty': not bool(val_courses),
        },
        {
            'key': 'current_ctc',
            'label': 'Current CTC',
            'type': 'text',
            'control_type': 'text',
            'is_editable': True,
            'icon': 'T',
            'value': val_current_ctc or 'Empty',
            'raw_value': val_current_ctc or '',
            'is_empty': not bool(val_current_ctc),
        },
        {
            'key': 'center_visit',
            'label': 'Center Visit Scheduled Date',
            'type': 'date',
            'control_type': 'datetime',
            'is_editable': True,
            'icon': 'calendar',
            'value': val_center_visit or 'DD/MM/YYYY HH:mm:ss',
            'raw_value': val_center_visit_raw,
            'is_empty': not bool(val_center_visit),
        },
    ]

    # 8. Navigation position (< Prev, Next >, position "X of Y")
    nav = get_lead_navigation(lead, user)

    return {
        'lead': lead,
        'assignee_name': assignee_name,
        'assignee_initials': assignee_initials,
        'col1_fields': col1_fields,
        'col2_fields': col2_fields,
        'whatsapp_phone': whatsapp_phone,
        'phone_display': phone_display,
        'chat_conversation': chat_conversation,
        'lead_status_choices': LeadStatus.choices,
        'call_outcome_choices': CallOutcome.choices,
        'call_status_choices': CallStatus.choices,
        'nav': nav,
    }


def update_lead_attribute(lead, user, field_key, new_value, request=None):
    """
    Updates an editable field on the Lead (direct model field, related model, or structured notes attribute).
    Validates permissions, phone normalization and duplicates, choices, and logs activity.
    """
    if not can_edit_lead(user, lead):
        raise PermissionDenied("You do not have permission to edit this lead.")

    val_str = str(new_value or '').strip()
    old_display = ''
    new_display = val_str or 'Empty'
    field_label = FIELD_KEY_TO_CANONICAL_LABEL.get(field_key, field_key.replace('_', ' ').title())

    # System managed check
    readonly_keys = [
        'captured_on', 'created_on', 'modified_on', 'last_activity_on',
        'last_activity_type', 'status_updated_on', 'capture_frequency'
    ]
    if field_key in readonly_keys:
        raise ValidationError(f"'{field_label}' is a system-managed field and cannot be directly modified.")

    # 1. Lead Name
    if field_key == 'name':
        if not val_str:
            raise ValidationError("Lead name cannot be empty.")
        old_display = lead.name
        lead.name = val_str
        lead.save(update_fields=['name', 'updated_at'])
        new_display = lead.name

    # 2. Phone
    elif field_key == 'phone':
        if not val_str:
            raise ValidationError("Phone number cannot be empty.")
        clean_phone = normalize_phone(val_str)
        if len(clean_phone) < 10:
            raise ValidationError("Please enter a valid 10-digit phone number.")
        conflict = find_duplicate_lead(phone=clean_phone, exclude_id=lead.id)
        if conflict:
            raise ValidationError(
                f"Phone number '{clean_phone}' is already associated with lead '{conflict.name}' (ID #{conflict.id}). Cannot assign a duplicate phone number."
            )
        old_display = lead.phone
        lead.phone = clean_phone
        lead.save(update_fields=['phone', 'updated_at'])
        new_display = f"+91 {clean_phone}" if len(clean_phone) == 10 else clean_phone

    # 3. Email
    elif field_key == 'email':
        old_display = lead.email or 'Empty'
        if val_str:
            clean_email = normalize_email(val_str)
            if '@' not in clean_email or '.' not in clean_email.split('@')[-1]:
                raise ValidationError("Please enter a valid email address.")
            lead.email = clean_email
        else:
            lead.email = ''
        lead.save(update_fields=['email', 'updated_at'])
        new_display = lead.email or 'Empty'

    # 4. Base Branch
    elif field_key == 'base_branch':
        can_change_branch = user.is_admin_user or getattr(user, 'role', '') == UserRole.SALES_HEAD
        if not can_change_branch:
            raise PermissionDenied("Only administrators and sales heads can modify the lead's base branch.")
        old_display = lead.branch.name if lead.branch else 'Empty'
        if val_str and val_str != 'Empty':
            target_branch = Branch.objects.filter(Q(name__iexact=val_str) | Q(id=val_str if val_str.isdigit() else 0), status='Active').first()
            if not target_branch:
                raise ValidationError(f"Branch '{val_str}' not found or inactive.")
            lead.branch = target_branch
            new_display = target_branch.name
        else:
            lead.branch = None
            new_display = 'Empty'
        lead.save(update_fields=['branch', 'updated_at'])
        lead.notes = update_lead_notes_attribute(lead.notes, 'base_branch', new_display if new_display != 'Empty' else '')
        lead.save(update_fields=['notes'])

    # 5. Assignee Name
    elif field_key in ('assignee_name', 'assignee'):
        if not can_assign_lead(user, lead):
            raise PermissionDenied("You do not have permission to reassign this lead.")
        old_assignee = lead.assigned_telecaller or lead.assigned_counselor or lead.assigned_sales_head
        old_display = old_assignee.get_full_name() or old_assignee.username if old_assignee else 'Unassigned'
        if val_str and val_str.lower() not in ('unassigned', 'empty', ''):
            target_user = User.objects.filter(
                Q(username__iexact=val_str) | Q(id=val_str if val_str.isdigit() else 0),
                is_active=True
            ).first()
            if not target_user:
                raise ValidationError(f"Staff member '{val_str}' not found.")
            if target_user.branch_id and lead.branch_id and target_user.branch_id != lead.branch_id and not user.is_admin_user:
                raise ValidationError(f"Staff member '{target_user.username}' belongs to a different branch.")
            if target_user.role == UserRole.TELECALLER:
                lead.assigned_telecaller = target_user
                lead.current_owner_type = LeadOwnerType.TELECALLER
            elif target_user.role == UserRole.COUNSELOR:
                lead.assigned_counselor = target_user
                lead.current_owner_type = LeadOwnerType.COUNSELOR
            elif target_user.role == UserRole.SALES_HEAD:
                lead.assigned_sales_head = target_user
                lead.current_owner_type = LeadOwnerType.SALES_HEAD
            elif target_user.role == UserRole.BRANCH_HEAD:
                lead.assigned_branch_head = target_user
                lead.current_owner_type = LeadOwnerType.BRANCH_HEAD
            lead.save()
            new_display = target_user.get_full_name() or target_user.username
        else:
            lead.assigned_telecaller = None
            lead.current_owner_type = LeadOwnerType.UNASSIGNED
            lead.save()
            new_display = 'Unassigned'
        lead.notes = update_lead_notes_attribute(lead.notes, 'assignee_name', new_display if new_display != 'Unassigned' else '')
        lead.save(update_fields=['notes'])

    # 6. Status / Pipeline Sub-Status
    elif field_key in ('status', 'pipeline_substatus'):
        valid_choices = [c[0] for c in LeadStatus.choices]
        if val_str not in valid_choices:
            raise ValidationError(f"Invalid status '{val_str}'.")
        old_display = lead.status
        change_lead_status(lead, val_str, user, remarks="Updated via Inline Lead Details Edit")
        new_display = lead.status

    # 7. Courses
    elif field_key == 'courses':
        old_display = lead.product.name if lead.product else 'Empty'
        if val_str and val_str != 'Empty':
            prod = Product.objects.filter(Q(name__iexact=val_str) | Q(id=val_str if val_str.isdigit() else 0), status='Active').first()
            lead.product = prod
            new_display = prod.name if prod else val_str
        else:
            lead.product = None
            new_display = 'Empty'
        lead.save(update_fields=['product', 'updated_at'])
        lead.notes = update_lead_notes_attribute(lead.notes, 'courses', new_display if new_display != 'Empty' else '')
        lead.save(update_fields=['notes'])

    # 8. Lead Source 1
    elif field_key == 'lead_source':
        old_display = lead.channel.name if lead.channel else (lead.source or 'Empty')
        if val_str and val_str != 'Empty':
            ch = Channel.objects.filter(Q(name__iexact=val_str) | Q(id=val_str if val_str.isdigit() else 0), status='Active').first()
            lead.channel = ch
            lead.source = ch.name if ch else val_str
            new_display = ch.name if ch else val_str
        else:
            lead.channel = None
            new_display = 'Empty'
        lead.save(update_fields=['channel', 'source', 'updated_at'])
        lead.notes = update_lead_notes_attribute(lead.notes, 'lead_source', new_display if new_display != 'Empty' else '')
        lead.save(update_fields=['notes'])

    # 9. Center Visit Scheduled Date
    elif field_key == 'center_visit':
        old_visit = lead.followups.filter(Q(status=FollowUpStatus.PENDING) | Q(notes__icontains='visit')).order_by('follow_up_date').first()
        old_display = f"{old_visit.follow_up_date} {old_visit.follow_up_time or ''}".strip() if old_visit else 'Empty'
        if val_str and val_str != 'Empty':
            parsed_dt = None
            for fmt in ('%Y-%m-%dT%H:%M', '%Y-%m-%d %H:%M', '%d/%m/%Y %H:%M:%S', '%d/%m/%Y %H:%M', '%Y-%m-%d'):
                try:
                    parsed_dt = datetime.strptime(val_str, fmt)
                    break
                except ValueError:
                    pass
            if not parsed_dt:
                raise ValidationError("Please provide a valid date/time format (YYYY-MM-DD HH:mm).")
            followup = old_visit or FollowUp(lead=lead, assigned_user=user)
            followup.follow_up_date = parsed_dt.date()
            followup.follow_up_time = parsed_dt.time()
            followup.status = FollowUpStatus.PENDING
            followup.notes = (followup.notes or '') + " [Center Visit Scheduled]"
            followup.save()
            new_display = f"{parsed_dt.strftime('%d/%m/%Y %H:%M:%S')}"
            lead.notes = update_lead_notes_attribute(lead.notes, 'center_visit', new_display)
            lead.save(update_fields=['notes'])
        else:
            if old_visit:
                old_visit.status = FollowUpStatus.CANCELLED
                old_visit.save()
            lead.notes = update_lead_notes_attribute(lead.notes, 'center_visit', '')
            lead.save(update_fields=['notes'])
            new_display = 'Empty'

    # 10. Preferred Branch
    elif field_key == 'pref_branch':
        old_display = ", ".join(lead.get_all_branch_names()) if lead.secondary_branches.exists() else 'Empty'
        if val_str and val_str != 'Empty':
            b = Branch.objects.filter(Q(name__iexact=val_str) | Q(id=val_str if val_str.isdigit() else 0), status='Active').first()
            if b:
                lead.secondary_branches.add(b)
            lead.notes = update_lead_notes_attribute(lead.notes, 'pref_branch', val_str)
            lead.save(update_fields=['notes'])
            new_display = val_str
        else:
            lead.secondary_branches.clear()
            lead.notes = update_lead_notes_attribute(lead.notes, 'pref_branch', '')
            lead.save(update_fields=['notes'])
            new_display = 'Empty'

    # 11. PassedOut
    elif field_key == 'passed_out':
        old_parsed = extract_parsed_lead_attributes(lead.notes)
        old_display = old_parsed.get('passed_out') or 'Empty'
        if val_str and val_str != 'Empty':
            clean_digits = re.sub(r'\D', '', val_str)
            if clean_digits and len(clean_digits) == 4:
                year_num = int(clean_digits)
                if not (1970 <= year_num <= 2040):
                    raise ValidationError("Please enter a valid passing year (between 1970 and 2040).")
                val_str = str(year_num)
        lead.notes = update_lead_notes_attribute(lead.notes, 'passed_out', val_str if val_str != 'Empty' else '')
        lead.save(update_fields=['notes', 'updated_at'])
        new_display = val_str if val_str != 'Empty' else 'Empty'

    # 12. Custom Notes Attributes
    else:
        old_parsed = extract_parsed_lead_attributes(lead.notes)
        old_display = old_parsed.get(field_key) or 'Empty'
        lead.notes = update_lead_notes_attribute(lead.notes, field_key, val_str if val_str != 'Empty' else '')
        lead.save(update_fields=['notes', 'updated_at'])
        new_display = val_str if val_str != 'Empty' else 'Empty'

    # Record Activity Log
    log_activity(
        user=user,
        action="Lead Field Updated",
        description=f"Updated '{field_label}' from '{old_display}' to '{new_display}' for lead '{lead.name}' (#{lead.id}).",
        object_type="Lead",
        object_id=lead.pk,
        request=request
    )

    clean_wa = normalize_phone(lead.phone)
    wa_url = f"https://wa.me/91{clean_wa}" if clean_wa and len(clean_wa) == 10 else f"https://wa.me/{clean_wa}" if clean_wa else ""

    assignee = lead.assigned_telecaller or lead.assigned_counselor or lead.assigned_sales_head
    assignee_name = assignee.get_full_name() or assignee.username if assignee else 'Unassigned'
    parts = assignee_name.strip().split()
    assignee_initials = (parts[0][0] + parts[1][0]).upper() if len(parts) >= 2 else assignee_name[:2].upper()

    return {
        'success': True,
        'field': field_key,
        'value': new_display,
        'raw_value': val_str,
        'is_empty': (new_display in ('Empty', '', '-', 'DD/MM/YYYY HH:mm:ss')),
        'lead_name': lead.name,
        'lead_phone': lead.phone,
        'lead_status': lead.status,
        'assignee_name': assignee_name,
        'assignee_initials': assignee_initials,
        'whatsapp_url': wa_url,
        'message': f"{field_label} updated successfully.",
    }


def get_lead_navigation(lead, user=None):
    """
    Computes prev_lead_id, next_lead_id, current_index, and total_leads_count
    for the current user's scope.
    """
    base_qs = Lead.objects.all()
    if user and user.is_authenticated:
        if getattr(user, 'is_telecaller_user', False):
            base_qs = base_qs.filter(assigned_telecaller=user)
        elif getattr(user, 'is_counselor_user', False):
            base_qs = base_qs.filter(assigned_counselor=user)
        elif getattr(user, 'is_branch_head_user', False) and user.branch_id:
            base_qs = base_qs.filter(branch_id=user.branch_id)
        elif getattr(user, 'is_sales_head_user', False):
            from accounts.permissions import get_accessible_branch_ids
            b_ids = get_accessible_branch_ids(user)
            base_qs = base_qs.filter(Q(branch_id__in=b_ids) | Q(assigned_sales_head=user))

    total_count = base_qs.count()
    if total_count == 0:
        total_count = 1

    lead_ids = list(base_qs.order_by('-created_at').values_list('id', flat=True))
    try:
        idx = lead_ids.index(lead.id)
        current_index = idx + 1
        prev_lead_id = lead_ids[idx - 1] if idx > 0 else None
        next_lead_id = lead_ids[idx + 1] if idx < len(lead_ids) - 1 else None
    except ValueError:
        current_index = 1
        prev_lead_id = None
        next_lead_id = None

    return {
        'current_index': current_index,
        'total_count': total_count,
        'prev_lead_id': prev_lead_id,
        'next_lead_id': next_lead_id,
    }

import re
import json
import hashlib
import logging
from django.conf import settings
from django.utils import timezone
from django.db import transaction
from django.db.models import Count, Q
from accounts.models import User, UserRole
from branches.models import Branch
from lead_channels.models import Channel
from products.models import Product
from activities.utils import log_activity
from .models import (
    Lead,
    LeadStatus,
    GoogleSheetConnection,
    GoogleSheetRowMapping,
    GoogleSheetSyncHistory
)
from .assignment import assign_lead_automatically, assign_new_lead
from .duplicates import find_duplicate_lead, handle_incoming_lead_duplicate, normalize_phone, normalize_email
from .google_sheets_service import (
    extract_spreadsheet_id,
    fetch_spreadsheet_metadata,
    fetch_sheet_data,
    normalize_header,
    check_google_auth_status,
    start_desktop_oauth_flow,
    disconnect_google_oauth,
    get_google_sheets_client
)

logger = logging.getLogger('crm')

# Google Form dynamic header matching definitions
HEADER_PATTERNS = {
    'name': [
        'full name', 'fullname', 'name', 'lead name', 'student name',
        'candidate name', 'applicant name', 'client name', 'person name',
        'student', 'candidate'
    ],
    'first_name': [
        'first name', 'firstname', 'given name'
    ],
    'last_name': [
        'last name', 'lastname', 'surname', 'family name'
    ],
    'phone': [
        'phone number', 'phonenumber', 'phone', 'mobile number',
        'mobilenumber', 'mobile', 'contact number', 'contactnumber',
        'contact', 'whatsapp number', 'whatsapp', 'contact phone',
        'phone no', 'phoneno', 'mobile no', 'mobileno', 'contact no', 'contactno',
        'tel', 'telephone', 'cell', 'cell phone'
    ],
    'alternate_phone': [
        'alternate phone', 'alternate mobile', 'alt phone', 'alt mobile',
        'secondary phone', 'alternate number', 'second phone', 'alternate contact',
        'alt phone no', 'alt mobile no'
    ],
    'email': [
        'email address', 'emailaddress', 'email', 'e mail',
        'e mail address', 'mail id', 'mailid', 'email id', 'emailid', 'mail'
    ],
    'product': [
        'interested course', 'interested product', 'course', 'product',
        'program', 'interested in', 'course interested', 'course name', 'stream',
        'wat course are you looking for ?', 'wat course are you looking for',
        'what course are you looking for ?', 'what course are you looking for',
        'courses'
    ],
    'branch': [
        'branch', 'center', 'branch center', 'location', 'city',
        'preferred branch', 'preferred location', 'campus', 'preferred center'
    ],
    'channel': [
        'channel', 'lead source', 'source', 'platform', 'campaign', 'channel name'
    ],
    'status': [
        'status', 'lead status'
    ],
    'notes': [
        'notes', 'remarks', 'comments', 'feedback', 'message', 'query',
        'comments / questions', 'comments/questions',
        'what you looking for?', 'what you looking for',
        'what is your current status?', 'what is your current status',
        'requirement', 'conservation step', 'qualification'
    ],
    'gender': [
        'gender', 'sex'
    ],
    'synced': [
        'synced', 'is synced', 'sync status'
    ],
    'timestamp': [
        'timestamp', 'time stamp', 'submission date', 'submitted at', 'date'
    ]
}


def detect_column_mapping(headers: list[str]) -> dict:
    """
    Intelligently maps raw Google Sheet headers to CRM Lead fields.
    Handles Google Form variations automatically.
    Returns: dict with field names as keys and raw sheet header strings as values.
    """
    mapping = {}
    normalized_headers = [(h, normalize_header(h)) for h in headers]

    # Pass 1: Exact matches against defined patterns
    for field, patterns in HEADER_PATTERNS.items():
        if field in mapping:
            continue
        for raw_h, norm_h in normalized_headers:
            if norm_h in patterns:
                mapping[field] = raw_h
                break

    # Pass 2: Containment heuristics for critical fields if unmapped
    for raw_h, norm_h in normalized_headers:
        if 'phone' not in mapping and any(p in norm_h for p in ['phone', 'mobile', 'contact']):
            if not any(alt in norm_h for alt in ['alt', 'alternate', 'second']):
                mapping['phone'] = raw_h
        if 'email' not in mapping and any(p in norm_h for p in ['email', 'mail']):
            mapping['email'] = raw_h
        if 'name' not in mapping and any(p in norm_h for p in ['name', 'student', 'candidate']):
            if not any(sub in norm_h for sub in ['first', 'last', 'user', 'channel', 'branch', 'product']):
                mapping['name'] = raw_h

    return mapping


def validate_spreadsheet_access(spreadsheet_url: str, worksheet_name: str = None):
    """
    Validates spreadsheet URL/ID, checks OAuth permissions, verifies worksheet exists,
    and returns available column headers.
    Returns: (is_valid, spreadsheet_id, worksheet_name, headers, sheet_title, error_message)
    """
    spreadsheet_id = extract_spreadsheet_id(spreadsheet_url)
    if not spreadsheet_id:
        return False, None, None, [], '', "Invalid Google Spreadsheet URL."

    try:
        meta = fetch_spreadsheet_metadata(spreadsheet_id)
    except FileNotFoundError as e:
        return False, spreadsheet_id, worksheet_name, [], '', str(e)
    except PermissionError as e:
        return False, spreadsheet_id, worksheet_name, [], '', str(e)
    except Exception as e:
        return False, spreadsheet_id, worksheet_name, [], '', str(e)

    sheet_title = meta.get('title', 'Google Sheet')
    available_tabs = meta.get('tabs', [])

    if not available_tabs:
        return False, spreadsheet_id, None, [], sheet_title, "The Google Sheet does not contain any worksheets/tabs."

    resolved_worksheet = worksheet_name
    if not resolved_worksheet or resolved_worksheet.strip() == '':
        form_tab = next((t for t in available_tabs if t.strip().lower() == 'form responses 1'), None)
        sheet1_tab = next((t for t in available_tabs if t.strip().lower() == 'sheet1'), None)
        resolved_worksheet = form_tab or sheet1_tab or available_tabs[0]
    else:
        # Match case-insensitively
        matched = next((t for t in available_tabs if t.strip().lower() == resolved_worksheet.strip().lower()), None)
        if matched:
            resolved_worksheet = matched
        else:
            # Fallback to Form Responses 1, Sheet1, or first tab
            form_tab = next((t for t in available_tabs if t.strip().lower() == 'form responses 1'), None)
            sheet1_tab = next((t for t in available_tabs if t.strip().lower() == 'sheet1'), None)
            resolved_worksheet = form_tab or sheet1_tab or available_tabs[0]

    try:
        headers, _ = fetch_sheet_data(spreadsheet_id, resolved_worksheet)
        if not headers:
            return False, spreadsheet_id, resolved_worksheet, [], sheet_title, "The Google Sheet does not contain any lead records or headers."
        return True, spreadsheet_id, resolved_worksheet, headers, sheet_title, None
    except Exception as e:
        return False, spreadsheet_id, resolved_worksheet, [], sheet_title, str(e)


def fetch_spreadsheet_rows(spreadsheet_id: str, worksheet_name: str):
    """
    Fetches rows using the OAuth Google Sheets API client.
    Maintained for backwards compatibility.
    """
    return fetch_sheet_data(spreadsheet_id, worksheet_name)


def compute_mapped_hash(data_dict: dict) -> str:
    """
    Computes a deterministic SHA-256 hash for mapped fields to detect row content changes.
    """
    canonical_str = json.dumps(data_dict, sort_keys=True)
    return hashlib.sha256(canonical_str.encode('utf-8')).hexdigest()


def assign_lead_to_team(lead: Lead, branch: Branch = None, method: str = 'Automatic'):
    """
    Applies role-based assignment rules:
    - Lead -> Branch -> Active Sales Head (with access to that branch) -> Active Telecaller in that branch.
    """
    if method != 'Automatic':
        return

    managers = User.objects.filter(role=UserRole.SALES_HEAD, is_active=True)
    if branch:
        branch_managers = managers.filter(branch_access__branch=branch)
        if branch_managers.exists():
            managers = branch_managers

    assigned_sales_head = managers.annotate(cnt=Count('manager_leads')).order_by('cnt', 'id').first()
    if assigned_sales_head:
        lead.assigned_sales_head = assigned_sales_head

        # Find telecallers in this branch
        telecallers = User.objects.filter(
            role=UserRole.TELECALLER,
            is_active=True
        )
        if branch:
            branch_tc = telecallers.filter(branch=branch)
            if branch_tc.exists():
                telecallers = branch_tc

        assigned_telecaller = telecallers.annotate(cnt=Count('telecaller_leads')).order_by('cnt', 'id').first()
        if assigned_telecaller:
            lead.assigned_telecaller = assigned_telecaller


def sync_google_sheet(connection: GoogleSheetConnection, triggered_by=None, headers=None, rows=None):
    """
    Authoritative synchronization delegator for GoogleSheetConnection:
    Delegates directly to the centralized Intelligent Google Sheets Synchronization Engine
    (services.google_sheets_sync_service.sync_connection).
    """
    logger.info(f"Google Sheets synchronization started for '{connection.name}' (ID: {connection.spreadsheet_id}).")
    if headers is None and rows is None:
        try:
            h, r = fetch_sheet_data(connection.spreadsheet_id, connection.worksheet_name)
            if h is not None and r is not None:
                headers, rows = h, r
        except Exception:
            pass

    try:
        from services.google_sheets_sync_service import sync_connection
        res = sync_connection(
            connection=connection,
            dry_run=False,
            triggered_by=triggered_by,
            headers=headers,
            rows=rows
        )
        return {
            'status': res.get('status', 'Completed'),
            'rows_checked': res.get('total_rows', 0),
            'new_leads': res.get('created', 0),
            'updated_leads': res.get('updated', 0),
            'skipped': res.get('skipped', 0),
            'failed': res.get('errors', 0),
            'assigned_leads': res.get('created', 0) + res.get('updated', 0),
            'errors': res.get('error_messages', [])
        }
    except Exception as e:
        logger.error(f"Synchronization error for '{connection.name}': {e}", exc_info=True)
        return {
            'status': 'Failed',
            'rows_checked': 0,
            'new_leads': 0,
            'updated_leads': 0,
            'skipped': 0,
            'failed': 1,
            'assigned_leads': 0,
            'errors': [str(e)]
        }


def sync_all_active_spreadsheets(triggered_by=None) -> list[dict]:
    """
    Synchronizes all active GoogleSheetConnection records in the CRM.
    Used by background workers, schedulers, and admin batch actions.
    """
    results = []
    active_conns = GoogleSheetConnection.objects.filter(is_active=True).order_by('id')
    for conn in active_conns:
        try:
            res = sync_google_sheet(conn, triggered_by=triggered_by)
            results.append({'connection_id': conn.id, 'name': conn.name, 'result': res})
        except Exception as e:
            logger.error(f"Error syncing spreadsheet '{conn.name}': {e}")
            results.append({'connection_id': conn.id, 'name': conn.name, 'error': str(e)})
    return results


def sync_default_environment_sheet(triggered_by=None) -> tuple[GoogleSheetConnection | None, dict]:
    """
    Synchronizes the Google Sheet configured in environment variables (GOOGLE_SHEET_ID and GOOGLE_SHEET_TAB).
    Creates or updates the GoogleSheetConnection record automatically.
    Returns: (connection, result_dict)
    """
    sheet_id = getattr(settings, 'GOOGLE_SHEET_ID', '') or os.getenv('GOOGLE_SHEET_ID', '')
    sheet_tab = getattr(settings, 'GOOGLE_SHEET_TAB', 'Form Responses 1') or os.getenv('GOOGLE_SHEET_TAB', 'Form Responses 1')

    if not sheet_id:
        return None, {
            'status': 'Failed',
            'rows_checked': 0,
            'new_leads': 0,
            'updated_leads': 0,
            'skipped': 0,
            'failed': 1,
            'errors': ["GOOGLE_SHEET_ID is not configured in environment or settings."]
        }

    conn, _ = GoogleSheetConnection.objects.get_or_create(
        spreadsheet_id=sheet_id,
        worksheet_name=sheet_tab,
        defaults={
            'name': f"Form Responses ({sheet_id[:8]})",
            'spreadsheet_url': f"https://docs.google.com/spreadsheets/d/{sheet_id}/edit",
            'assignment_method': 'Automatic',
            'created_by': triggered_by,
            'last_sync_status': 'Connected'
        }
    )

    result = sync_google_sheet(conn, triggered_by=triggered_by)
    return conn, result

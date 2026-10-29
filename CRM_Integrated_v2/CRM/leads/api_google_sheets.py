import json
import logging
from django.http import JsonResponse, HttpResponseNotAllowed
from django.shortcuts import get_object_or_404
from django.views.decorators.csrf import csrf_exempt
from django.utils import timezone
from accounts.permissions import admin_required

from services.google_sheets_service import (
    validate_url,
    extract_spreadsheet_id,
    extract_gid,
    fetch_sheet,
)
from services.google_sheets_sync_service import sync_connection
from services.intelligent_matching_engine import (
    match_all_columns,
    get_active_crm_entities,
    AUTHORITATIVE_FIELD_INVENTORY,
)
from .models import GoogleSheetConnection, GoogleSheetRowMapping, Lead

logger = logging.getLogger('crm')


def _parse_request_body(request) -> dict:
    """Helper to parse JSON payload or POST form parameters."""
    if request.body:
        try:
            return json.loads(request.body.decode('utf-8'))
        except Exception:
            pass
    return request.POST.dict()


@admin_required
def api_google_sheets_list(request):
    """
    GET /api/google-sheets/
    Returns list of all connected Google Sheet sources stored in MySQL.
    """
    if request.method != 'GET':
        return HttpResponseNotAllowed(['GET'])

    if request.user.is_authenticated and getattr(request.user, 'is_receptionist_user', False):
        return JsonResponse({'success': False, 'error': 'Permission denied: Receptionists cannot manage Google Sheets.'}, status=403)

    sheets = GoogleSheetConnection.objects.all().order_by('-created_at')
    data = []
    for s in sheets:
        sync_iso = s.last_sync_time.isoformat() if s.last_sync_time else None
        data.append({
            'id': s.id,
            'name': s.name,
            'sheet_url': s.spreadsheet_url,
            'spreadsheet_id': s.spreadsheet_id,
            'gid': s.gid or '0',
            'worksheet_name': s.worksheet_name,
            'is_active': s.is_active,
            'connection_status': s.connection_status,
            'last_sync_status': s.last_sync_status,
            'last_synced_at': sync_iso,
            'last_sync_error': s.last_sync_error,
            'total_leads_imported': s.total_leads_imported or s.row_mappings.count(),
            'field_mapping': s.field_mapping or {},
            'created_at': s.created_at.isoformat(),
        })

    return JsonResponse({
        'success': True,
        'count': len(data),
        'sources': data
    })


@admin_required
def api_google_sheets_connect(request):
    """
    POST /api/google-sheets/connect/
    Connects a new publicly accessible Google Sheet URL into MySQL.
    """
    if request.method != 'POST':
        return HttpResponseNotAllowed(['POST'])

    if request.user.is_authenticated and getattr(request.user, 'is_receptionist_user', False):
        return JsonResponse({'success': False, 'error': 'Permission denied: Receptionists cannot manage Google Sheets.'}, status=403)

    payload = _parse_request_body(request)
    sheet_url = (
        payload.get('sheet_url') or
        payload.get('url') or
        payload.get('spreadsheet_url') or ''
    ).strip()

    name = (payload.get('name') or payload.get('spreadsheet_name') or 'Google Sheet Leads').strip()
    worksheet_name = (payload.get('worksheet_name') or 'Sheet1').strip()
    branch_id = payload.get('branch_id')

    # 1. Validate Google Sheet URL (Strict domain & format validation, SSRF protection)
    is_valid, val_err = validate_url(sheet_url)
    if not is_valid:
        return JsonResponse({
            'success': False,
            'error': val_err or 'Invalid Google Spreadsheet URL.'
        }, status=400)

    # 2. Extract Spreadsheet ID & GID
    spreadsheet_id = extract_spreadsheet_id(sheet_url)
    gid = extract_gid(sheet_url) or '0'

    # 3. Test public access and fetch initial data
    try:
        headers, rows = fetch_sheet(
            spreadsheet_id=spreadsheet_id,
            gid=gid,
            sheet_name=worksheet_name
        )
    except PermissionError as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=403)
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': f"Failed to access Google Sheet: {e}"
        }, status=502)

    if not headers or not any(headers):
        return JsonResponse({
            'success': False,
            'error': 'The Google Sheet contains no data or could not be read. Please ensure it contains header columns and is shared as "Anyone with the link can view".'
        }, status=400)

    # 4. Save or retrieve GoogleSheetConnection in MySQL
    conn, created = GoogleSheetConnection.objects.get_or_create(
        spreadsheet_id=spreadsheet_id,
        worksheet_name=worksheet_name,
        defaults={
            'name': name,
            'spreadsheet_url': sheet_url,
            'gid': gid,
            'is_active': True,
            'last_sync_status': 'Connected',
            'created_by': request.user if request.user.is_authenticated else None,
            'branch_id': int(branch_id) if (branch_id and str(branch_id).isdigit()) else None,
        }
    )

    if not created:
        conn.name = name
        conn.spreadsheet_url = sheet_url
        conn.gid = gid
        conn.is_active = True
        conn.last_sync_status = 'Connected'
        if branch_id and str(branch_id).isdigit():
            conn.branch_id = int(branch_id)
        conn.save()

    # 5. Perform initial synchronization into MySQL
    sync_result = sync_connection(
        connection=conn,
        triggered_by=request.user if request.user.is_authenticated else None,
        headers=headers,
        rows=rows
    )

    rows_imported = sync_result.get('created', 0) + sync_result.get('updated', 0)

    return JsonResponse({
        'success': True,
        'source_id': conn.id,
        'spreadsheet_id': conn.spreadsheet_id,
        'gid': conn.gid or '0',
        'worksheet_name': conn.worksheet_name,
        'rows_imported': rows_imported,
        'sync_result': sync_result,
        'message': f"Connected and synced {rows_imported} rows into MySQL successfully."
    }, status=201 if created else 200)


@admin_required
def api_google_sheets_sync(request, connection_id):
    """
    POST /api/google-sheets/<int:connection_id>/sync/
    Triggers live manual 'Sync Now' for a specific connected sheet.
    Fetches latest rows from Google Sheets public export endpoint and updates MySQL.
    """
    if request.method != 'POST':
        return HttpResponseNotAllowed(['POST'])

    conn = get_object_or_404(GoogleSheetConnection, pk=connection_id)
    user = request.user if request.user.is_authenticated else None

    result = sync_connection(conn, triggered_by=user)

    return JsonResponse({
        'success': result.get('success', True),
        'connection_id': conn.id,
        'name': conn.name,
        'sync_result': result
    })


@admin_required
def api_google_sheets_detail(request, connection_id):
    """
    GET /api/google-sheets/<int:connection_id>/ -> Details & latest MySQL imported records.
    DELETE /api/google-sheets/<int:connection_id>/ -> Removes / disconnects connection.
    """
    conn = get_object_or_404(GoogleSheetConnection, pk=connection_id)

    if request.method == 'GET':
        # Retrieve imported leads from MySQL
        row_mappings = GoogleSheetRowMapping.objects.filter(connection=conn).select_related('lead')
        imported_records = []
        for m in row_mappings[:100]:
            imported_records.append({
                'row_index': m.row_index,
                'row_identifier': m.row_identifier,
                'lead_id': m.lead_id,
                'name': m.lead.name,
                'phone': m.lead.phone,
                'email': m.lead.email,
                'source_status': m.source_status,
                'status': m.lead.status,
            })

        return JsonResponse({
            'success': True,
            'source': {
                'id': conn.id,
                'name': conn.name,
                'sheet_url': conn.spreadsheet_url,
                'spreadsheet_id': conn.spreadsheet_id,
                'gid': conn.gid or '0',
                'worksheet_name': conn.worksheet_name,
                'is_active': conn.is_active,
                'connection_status': conn.connection_status,
                'last_sync_status': conn.last_sync_status,
                'last_synced_at': conn.last_sync_time.isoformat() if conn.last_sync_time else None,
                'last_sync_error': conn.last_sync_error,
                'total_leads_imported': conn.row_mappings.count(),
                'field_mapping': conn.field_mapping or {},
            },
            'records_count': len(imported_records),
            'records': imported_records
        })

    elif request.method == 'DELETE':
        conn.is_active = False
        conn.connection_status = 'DISCONNECTED'
        conn.last_sync_status = 'Disconnected'
        conn.save(update_fields=['is_active', 'connection_status', 'last_sync_status', 'updated_at'])

        return JsonResponse({
            'success': True,
            'connection_id': conn.id,
            'message': f"Google Sheet '{conn.name}' disconnected successfully."
        })

    return HttpResponseNotAllowed(['GET', 'DELETE'])


@admin_required
def api_google_sheets_inspect_mapping(request):
    """
    POST /api/google-sheets/inspect-mapping/
    Analyzes spreadsheet column headers and sample cell values using the
    Intelligent Column Matching Engine.
    
    Accepts:
    {
        "connection_id": 123  (optional if sheet_url provided)
        OR
        "sheet_url": "https://...",
        "worksheet_name": "Sheet1"
    }
    """
    if request.method != 'POST':
        return HttpResponseNotAllowed(['POST'])

    payload = _parse_request_body(request)
    connection_id = payload.get('connection_id')
    sheet_url = payload.get('sheet_url') or payload.get('url') or ''
    worksheet_name = payload.get('worksheet_name') or 'Sheet1'

    conn = None
    if connection_id:
        conn = get_object_or_404(GoogleSheetConnection, pk=connection_id)
        sheet_url = conn.spreadsheet_url
        worksheet_name = conn.worksheet_name

    if not sheet_url:
        return JsonResponse({'success': False, 'error': 'Either connection_id or sheet_url must be provided.'}, status=400)

    is_valid, val_err = validate_url(sheet_url)
    if not is_valid:
        return JsonResponse({'success': False, 'error': val_err or 'Invalid Google Spreadsheet URL.'}, status=400)

    spreadsheet_id = extract_spreadsheet_id(sheet_url)
    gid = extract_gid(sheet_url) or (conn.gid if conn else '0') or '0'

    try:
        headers, rows = fetch_sheet(
            spreadsheet_id=spreadsheet_id,
            gid=gid,
            sheet_name=worksheet_name
        )
    except PermissionError as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=403)
    except Exception as e:
        return JsonResponse({'success': False, 'error': f"Failed to access Google Sheet: {e}"}, status=502)

    if not headers or not any(headers):
        return JsonResponse({'success': False, 'error': 'The Google Sheet returned no headers or data.'}, status=400)

    active_entities = get_active_crm_entities()
    existing_mapping = (conn.field_mapping or {}) if conn else {}
    # Clean runtime keys if present
    stored_profile = {k: v for k, v in existing_mapping.items() if k not in ('headers', 'rows', 'meta') and isinstance(v, str)}

    matching_spec = match_all_columns(
        headers=headers,
        sample_rows=rows[:50],
        active_entities=active_entities,
        existing_mapping=stored_profile
    )

    # Format available CRM fields for UI dropdowns
    available_fields = []
    for field_key, field_def in AUTHORITATIVE_FIELD_INVENTORY.items():
        available_fields.append({
            'field': field_key,
            'label': field_def['label'],
            'category': field_def['category'],
            'is_primary': field_def.get('is_primary', False)
        })

    return JsonResponse({
        'success': True,
        'connection_id': conn.id if conn else None,
        'connection_name': conn.name if conn else 'New Spreadsheet',
        'spreadsheet_id': spreadsheet_id,
        'worksheet_name': worksheet_name,
        'total_rows': len(rows),
        'total_columns': len(headers),
        'headers': headers,
        'column_mappings': matching_spec['column_mappings'],
        'field_to_header': matching_spec['field_to_header'],
        'unmapped_headers': matching_spec['unmapped_headers'],
        'missing_critical_fields': matching_spec['missing_critical_fields'],
        'high_confidence_count': matching_spec['high_confidence_count'],
        'medium_confidence_count': matching_spec['medium_confidence_count'],
        'low_confidence_count': matching_spec['low_confidence_count'],
        'available_crm_fields': available_fields
    })


@admin_required
def api_google_sheets_preview_sync(request):
    """
    POST /api/google-sheets/preview-sync/
    Executes a non-destructive dry-run against the live Google Sheet data using
    the proposed or confirmed column mapping. Returns projected impact metrics.
    
    Payload:
    {
        "connection_id": 123,
        "field_mapping": {
            "name": "Candidate Name",
            "phone": "Mobile",
            ...
        }
    }
    """
    if request.method != 'POST':
        return HttpResponseNotAllowed(['POST'])

    payload = _parse_request_body(request)
    connection_id = payload.get('connection_id')
    if not connection_id:
        return JsonResponse({'success': False, 'error': 'connection_id is required for pre-sync preview.'}, status=400)

    conn = get_object_or_404(GoogleSheetConnection, pk=connection_id)
    proposed_mapping = payload.get('field_mapping') or {}

    headers = payload.get('headers') or (conn.field_mapping or {}).get('headers')
    rows = payload.get('rows') or (conn.field_mapping or {}).get('rows')

    preview_res = sync_connection(
        connection=conn,
        triggered_by=request.user if request.user.is_authenticated else None,
        headers=headers,
        rows=rows,
        dry_run=True,
        custom_field_mapping=proposed_mapping
    )

    return JsonResponse({
        'success': preview_res.get('success', True),
        'connection_id': conn.id,
        'connection_name': conn.name,
        'preview': preview_res
    })


@admin_required
def api_google_sheets_save_mapping(request, connection_id):
    """
    POST /api/google-sheets/<int:connection_id>/save-mapping/
    Saves an approved column mapping configuration for a GoogleSheetConnection.
    
    Payload:
    {
        "field_mapping": {
            "name": "Student Name",
            "phone": "Phone Number",
            ...
        }
    }
    """
    if request.method != 'POST':
        return HttpResponseNotAllowed(['POST'])

    conn = get_object_or_404(GoogleSheetConnection, pk=connection_id)
    payload = _parse_request_body(request)
    new_mapping = payload.get('field_mapping')

    if not isinstance(new_mapping, dict):
        return JsonResponse({'success': False, 'error': 'field_mapping must be a valid JSON object.'}, status=400)

    current_mapping = dict(conn.field_mapping or {})
    current_mapping.update(new_mapping)
    conn.field_mapping = current_mapping
    conn.save(update_fields=['field_mapping', 'updated_at'])

    return JsonResponse({
        'success': True,
        'connection_id': conn.id,
        'name': conn.name,
        'field_mapping': conn.field_mapping,
        'message': 'Column mapping profile saved successfully.'
    })

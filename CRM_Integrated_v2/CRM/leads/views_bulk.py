"""
API Views for Advanced Bulk Edit Leads in TECHPANDA CRM.
Provides:
- api_bulk_edit_options: Options catalog (statuses, staff, tags, products, branches, categories).
- api_bulk_edit_preview: Server-validated preview of proposed changes and percentage distributions.
- api_bulk_edit_execute: Atomic batch execution with idempotency, audit trail, and activity logging.
- api_bulk_edit_status: Status inspection for bulk operation records.
"""

import json
import logging
from django.http import JsonResponse
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_GET, require_POST
from django.core.exceptions import PermissionDenied, ValidationError

from accounts.models import User, UserRole
from accounts.permissions import get_accessible_branch_ids
from branches.models import Branch
from products.models import Product
from lead_channels.models import Channel
from .models import (
    Lead,
    LeadStatus,
    LeadCategory,
    LeadTag,
    VisitorStatus,
    BulkOperationRecord,
)
from .bulk_edit_service import (
    resolve_authorized_leads,
    preview_bulk_edit,
    execute_bulk_edit,
)

logger = logging.getLogger('crm')


@login_required
@require_GET
def api_bulk_edit_options(request):
    """
    Returns accessible dropdown options for configuring bulk edits based on the user's role.
    """
    user = request.user
    if user.role == UserRole.RECEPTIONIST:
        raise PermissionDenied("Receptionists are not permitted to bulk edit leads.")

    accessible_bids = get_accessible_branch_ids(user)

    # 1. Staff Members (Telecallers & Counselors)
    tc_qs = User.objects.filter(role=UserRole.TELECALLER, is_active=True).select_related('branch')
    counselor_qs = User.objects.filter(role=UserRole.COUNSELOR, is_active=True).select_related('branch')

    if not (user.is_admin_user or user.is_superuser):
        if accessible_bids:
            tc_qs = tc_qs.filter(branch_id__in=accessible_bids)
            counselor_qs = counselor_qs.filter(branch_id__in=accessible_bids)
        elif user.branch_id:
            tc_qs = tc_qs.filter(branch_id=user.branch_id)
            counselor_qs = counselor_qs.filter(branch_id=user.branch_id)

    telecallers = [
        {
            'id': t.id,
            'name': t.get_full_name() or t.username,
            'username': t.username,
            'branch_id': t.branch_id,
            'branch_name': t.branch.name if t.branch else '',
        }
        for t in tc_qs.order_by('first_name', 'username')
    ]

    counselors = [
        {
            'id': c.id,
            'name': c.get_full_name() or c.username,
            'username': c.username,
            'branch_id': c.branch_id,
            'branch_name': c.branch.name if c.branch else '',
        }
        for c in counselor_qs.order_by('first_name', 'username')
    ]

    # 2. Branches
    branch_qs = Branch.objects.filter(status=Branch.Status.ACTIVE)
    if not (user.is_admin_user or user.is_superuser) and accessible_bids:
        branch_qs = branch_qs.filter(id__in=accessible_bids)
    branches = [{'id': b.id, 'name': b.name} for b in branch_qs.order_by('name')]

    # 3. Products & Channels
    products = [{'id': p.id, 'name': p.name} for p in Product.objects.filter(status=Product.Status.ACTIVE).order_by('name')]
    channels = [{'id': ch.id, 'name': ch.name} for ch in Channel.objects.filter(status='Active').order_by('name')]

    # 4. Tags
    tags = [{'id': tg.id, 'name': tg.name, 'color': tg.color} for tg in LeadTag.objects.all().order_by('name')]

    return JsonResponse({
        'success': True,
        'statuses': [{'value': code, 'label': label} for code, label in LeadStatus.choices],
        'categories': [{'value': code, 'label': label} for code, label in LeadCategory.choices],
        'ratings': [
            {'value': 1, 'label': '1 Star (Low Priority)'},
            {'value': 2, 'label': '2 Stars'},
            {'value': 3, 'label': '3 Stars (Medium)'},
            {'value': 4, 'label': '4 Stars (High Priority)'},
            {'value': 5, 'label': '5 Stars (Urgent / VIP)'},
        ],
        'visitor_statuses': [{'value': code, 'label': label} for code, label in VisitorStatus.choices],
        'telecallers': telecallers,
        'counselors': counselors,
        'branches': branches,
        'products': products,
        'channels': channels,
        'tags': tags,
    })


@login_required
@require_POST
def api_bulk_edit_preview(request):
    """
    Validates selected leads and returns server-computed operation summary
    with percentage allocations and warnings before execution.
    """
    try:
        data = json.loads(request.body)
    except Exception:
        data = request.POST

    lead_ids = data.get('lead_ids', [])
    filters = data.get('filters', {})
    changes = data.get('changes', {})

    try:
        preview = preview_bulk_edit(request.user, lead_ids=lead_ids, filter_params=filters, changes=changes)
        return JsonResponse({
            'success': True,
            'preview': preview,
        })
    except (PermissionDenied, ValidationError) as pe:
        return JsonResponse({'success': False, 'error': str(pe)}, status=403 if isinstance(pe, PermissionDenied) else 400)
    except Exception as exc:
        logger.exception("api_bulk_edit_preview error: %s", exc)
        return JsonResponse({'success': False, 'error': str(exc)}, status=500)


@login_required
@require_POST
def api_bulk_edit_execute(request):
    """
    Executes atomic bulk edit on the authorized lead selection.
    """
    try:
        data = json.loads(request.body)
    except Exception:
        data = request.POST

    lead_ids = data.get('lead_ids', [])
    filters = data.get('filters', {})
    changes = data.get('changes', {})
    idempotency_key = (data.get('idempotency_key') or '').strip()
    note = (data.get('note') or '').strip()

    try:
        result = execute_bulk_edit(
            user=request.user,
            lead_ids=lead_ids,
            filter_params=filters,
            changes=changes,
            idempotency_key=idempotency_key,
            reassignment_note=note
        )
        return JsonResponse(result)
    except (PermissionDenied, ValidationError) as pe:
        return JsonResponse({'success': False, 'error': str(pe)}, status=403 if isinstance(pe, PermissionDenied) else 400)
    except Exception as exc:
        logger.exception("api_bulk_edit_execute error: %s", exc)
        return JsonResponse({'success': False, 'error': str(exc)}, status=500)


@login_required
@require_GET
def api_bulk_edit_status(request, operation_id):
    """
    Returns execution status and audit summary for a bulk operation.
    """
    op = BulkOperationRecord.objects.filter(operation_id=operation_id).first()
    if not op:
        return JsonResponse({'success': False, 'error': 'Operation record not found.'}, status=404)

    # Permission check: Actor or Admin/Manager
    if op.actor != request.user and not (request.user.is_admin_user or request.user.is_sales_head_user):
        raise PermissionDenied("You do not have permission to view this operation.")

    return JsonResponse({
        'success': True,
        'operation_id': op.operation_id,
        'operation_type': op.operation_type,
        'status': op.status,
        'actor': op.actor.get_full_name() if op.actor else 'System',
        'total_authorized': op.total_authorized,
        'success_count': op.success_count,
        'skipped_count': op.skipped_count,
        'failed_count': op.failed_count,
        'requested_changes': op.requested_changes,
        'error_summary': op.error_summary,
        'reassignment_note': op.reassignment_note,
        'created_at': op.created_at.strftime('%Y-%m-%d %H:%M:%S'),
        'completed_at': op.completed_at.strftime('%Y-%m-%d %H:%M:%S') if op.completed_at else None,
    })

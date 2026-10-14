"""
Advanced Bulk Edit & Reassignment Service for TECHPANDA CRM.
Handles:
1. Role-scoped authorized lead queryset resolution (from IDs or active filters).
2. Deterministic percentage-based and single-assignee lead redistribution.
3. Concurrency-safe transactions, row locking, and status transition validation.
4. Pending follow-up task handling (reassign, preserve, cancel).
5. Priority rating (1-5 stars) and tag management without duplicate associations.
6. Permitted custom field updates with protected field guards.
7. Operation audit tracking via BulkOperationRecord and Activity logging.
"""

import uuid
import logging
from decimal import Decimal, ROUND_HALF_UP
from typing import Dict, Any, List, Optional, Tuple

from django.db import transaction
from django.db.models import Q, QuerySet
from django.utils import timezone
from django.core.exceptions import PermissionDenied, ValidationError

from accounts.models import User, UserRole
from accounts.permissions import (
    get_accessible_branch_ids,
    can_access_lead,
    can_edit_lead,
    can_reassign_lead,
    can_change_lead_status,
)
from branches.models import Branch
from products.models import Product
from lead_channels.models import Channel
from followups.models import FollowUp, FollowUpStatus
from activities.utils import log_activity

from .models import (
    Lead,
    LeadStatus,
    LeadCategory,
    LeadOwnerType,
    LeadTag,
    VisitorStatus,
    LeadAssignmentHistory,
    LeadStatusHistory,
    BulkOperationRecord,
    BulkOperationStatus,
)
from .handoff_service import reassign_lead, change_lead_status

logger = logging.getLogger('crm')

PROTECTED_FIELDS = {
    'id', 'pk', 'phone', 'email', 'created_at', 'updated_at',
    'enrollment', 'payments', 'is_offline', 'assignment_history',
    'status_history', 'calls', 'followups', 'whatsapp_opt_out',
    'whatsapp_consent_given', 'whatsapp_consent_date'
}


def resolve_authorized_leads(user: User, lead_ids: Optional[List[int]] = None, filter_params: Optional[Dict[str, Any]] = None) -> QuerySet:
    """
    Resolves the authorized Lead queryset for the actor based on lead_ids or filter_params.
    Strictly enforces object-level visibility and hierarchy permissions:
    - Admin: all matching leads.
    - Sales Head: leads within accessible branches.
    - Branch Head: leads within their assigned branch.
    - Counselor: leads within their branch or directly assigned.
    - Telecaller: leads directly assigned to them.
    - Receptionist: cannot bulk edit (empty queryset).
    """
    if not user or not user.is_authenticated:
        return Lead.objects.none()

    if user.role == UserRole.RECEPTIONIST:
        return Lead.objects.none()

    qs = Lead.objects.all().select_related(
        'branch', 'assigned_telecaller', 'assigned_counselor', 'assigned_sales_head', 'product', 'channel'
    )

    # 1. Enforce Role Visibility Boundary
    if not (user.is_admin_user or user.is_superuser):
        if user.role == UserRole.SALES_HEAD:
            accessible_bids = get_accessible_branch_ids(user)
            qs = qs.filter(branch_id__in=accessible_bids)
        elif user.role == UserRole.BRANCH_HEAD:
            if user.branch_id:
                qs = qs.filter(branch_id=user.branch_id)
            else:
                return Lead.objects.none()
        elif user.role == UserRole.COUNSELOR:
            if user.branch_id:
                qs = qs.filter(Q(branch_id=user.branch_id) | Q(assigned_counselor=user))
            else:
                qs = qs.filter(assigned_counselor=user)
        elif user.is_telecaller_user:
            qs = qs.filter(assigned_telecaller=user)
        else:
            return Lead.objects.none()

    # 2. Filter by specific lead IDs or URL filter parameters
    if lead_ids:
        clean_ids = [int(i) for i in lead_ids if str(i).isdigit()]
        if not clean_ids:
            return Lead.objects.none()
        qs = qs.filter(id__in=clean_ids)
    elif filter_params:
        search = (filter_params.get('search') or '').strip()
        if search:
            qs = qs.filter(
                Q(name__icontains=search)
                | Q(phone__icontains=search)
                | Q(email__icontains=search)
                | Q(notes__icontains=search)
            )

        branch_val = filter_params.get('branch')
        if branch_val and str(branch_val).isdigit():
            qs = qs.filter(branch_id=int(branch_val))

        status_val = filter_params.get('status')
        if status_val and status_val in LeadStatus.values:
            qs = qs.filter(status=status_val)

        assignment_status_val = filter_params.get('assignment_status')
        if assignment_status_val:
            qs = qs.filter(assignment_status=assignment_status_val)

        tc_val = filter_params.get('telecaller')
        if tc_val and str(tc_val).isdigit():
            qs = qs.filter(assigned_telecaller_id=int(tc_val))

        counselor_val = filter_params.get('counselor')
        if counselor_val and str(counselor_val).isdigit():
            qs = qs.filter(assigned_counselor_id=int(counselor_val))

        product_val = filter_params.get('product')
        if product_val and str(product_val).isdigit():
            qs = qs.filter(product_id=int(product_val))

        channel_val = filter_params.get('channel')
        if channel_val and str(channel_val).isdigit():
            qs = qs.filter(channel_id=int(channel_val))

        category_val = filter_params.get('category')
        if category_val and category_val in LeadCategory.values:
            qs = qs.filter(category=category_val)
    else:
        return Lead.objects.none()

    return qs.order_by('-created_at')


def calculate_percentage_distribution(total_count: int, allocations: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Computes integer lead distribution across assignees based on configured percentages.
    Guarantees:
    - Sum of percentages must equal exactly 100%.
    - Integer counts are computed deterministically.
    - Rounding remainders are absorbed cleanly by descending order of percentage/remainder.
    - Sum of distributed lead counts strictly equals total_count.
    """
    if total_count <= 0 or not allocations:
        return []

    # Validate sum of percentages == 100
    total_pct = sum(Decimal(str(a.get('percentage', 0))) for a in allocations)
    if total_pct != Decimal('100'):
        raise ValidationError(f"Allocation percentages must total exactly 100%. Current total: {total_pct}%")

    distributed = []
    running_count = 0
    remainders = []

    for idx, item in enumerate(allocations):
        pct = Decimal(str(item.get('percentage', 0)))
        exact_shares = (Decimal(str(total_count)) * pct) / Decimal('100')
        base_int = int(exact_shares)
        frac = exact_shares - Decimal(str(base_int))
        running_count += base_int

        entry = {
            'user_id': item['user_id'],
            'user_name': item.get('user_name', ''),
            'percentage': float(pct),
            'count': base_int,
            'frac': frac,
            'idx': idx,
        }
        distributed.append(entry)
        remainders.append((frac, idx))

    remainder_to_distribute = total_count - running_count
    # Sort by highest fractional remainder first
    remainders.sort(key=lambda x: x[0], reverse=True)

    for i in range(remainder_to_distribute):
        target_idx = remainders[i % len(remainders)][1]
        distributed[target_idx]['count'] += 1

    # Cleanup internal sorting metadata
    for d in distributed:
        d.pop('frac', None)
        d.pop('idx', None)

    return distributed


def _normalize_changes(changes: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Normalizes changes payload into canonical dictionary representation.
    Supports both nested structure and flattened shorthand parameters.
    """
    if not changes:
        return {}
    c = dict(changes)

    # Normalize Reassignment
    if 'reassignment' not in c:
        role = c.get('reassign_role') or c.get('target_role')
        strategy = c.get('reassign_mode') or c.get('strategy')
        single_id = c.get('single_assignee_id') or c.get('target_user_id')
        allocs = c.get('percentage_allocations') or c.get('allocations')
        task_handling = c.get('pending_task_handling') or c.get('pending_tasks') or 'reassign'

        if role or strategy or single_id or allocs:
            c['reassignment'] = {
                'role': (role or 'TELECALLER').upper(),
                'strategy': strategy or ('percentage' if allocs else 'single'),
                'target_user_id': single_id,
                'allocations': allocs or [],
                'pending_tasks': task_handling,
            }

    # Normalize Tags
    if 'tags' not in c:
        add_tags = c.get('add_tags') or []
        remove_tags = c.get('remove_tags') or []
        if add_tags or remove_tags:
            c['tags'] = {
                'add': add_tags,
                'remove': remove_tags,
            }

    return c


def preview_bulk_edit(
    user: User,
    lead_ids: Optional[List[int]] = None,
    filter_params: Optional[Dict[str, Any]] = None,
    changes: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Generates a server-validated preview of proposed bulk changes before execution.
    Inspects affected leads, validates status transitions, calculates allocation counts,
    and returns warnings about restricted records.
    """
    if not user.is_authenticated or user.role == UserRole.RECEPTIONIST:
        raise PermissionDenied("You do not have permission to perform bulk edits.")

    qs = resolve_authorized_leads(user, lead_ids=lead_ids, filter_params=filter_params)
    total_authorized = qs.count()
    changes = _normalize_changes(changes)

    preview: Dict[str, Any] = {
        'success': True,
        'total_authorized': total_authorized,
        'authorized_count': total_authorized,
        'requested_lead_count': len(lead_ids) if lead_ids else total_authorized,
        'warnings': [],
        'changes_summary': {},
    }

    if total_authorized == 0:
        preview['warnings'].append("No authorized leads match the current selection or filters.")
        return preview

    # 1. Status Change Preview
    new_status = changes.get('status')
    if new_status:
        if new_status not in LeadStatus.values:
            preview['warnings'].append(f"Invalid status '{new_status}'.")
        else:
            ineligible_status_count = 0
            if new_status == LeadStatus.ENROLLED:
                # Requires enrollment authority - evaluate via optimized aggregate counts
                if user.is_admin_user:
                    ineligible_status_count = 0
                elif user.is_sales_head_user:
                    acc_branches = get_accessible_branch_ids(user)
                    ineligible_status_count = qs.exclude(branch_id__in=acc_branches).count()
                elif user.is_branch_head_user:
                    if user.branch_id:
                        ineligible_status_count = qs.exclude(branch_id=user.branch_id).count()
                    else:
                        ineligible_status_count = 0
                elif user.role == UserRole.COUNSELOR:
                    ineligible_status_count = qs.exclude(assigned_counselor_id=user.id).count()
                else:
                    ineligible_status_count = total_authorized

                if ineligible_status_count > 0:
                    preview['warnings'].append(
                        f"{ineligible_status_count} of {total_authorized} lead(s) cannot be transitioned to 'Enrolled' due to lack of counselor/manager authority and will be skipped."
                    )

            preview['changes_summary']['status'] = {
                'target_status': new_status,
                'ineligible_count': ineligible_status_count,
                'note': "Transitioning to 'Enrolled' requires Counselor or Manager permission." if new_status == LeadStatus.ENROLLED else ""
            }

    # 2. Rating Change Preview
    new_rating = changes.get('rating')
    if new_rating is not None:
        try:
            rating_val = int(new_rating)
            if 1 <= rating_val <= 5:
                preview['changes_summary']['rating'] = {
                    'target_rating': rating_val,
                    'stars_label': f"{rating_val} Star{'s' if rating_val > 1 else ''}"
                }
            else:
                preview['warnings'].append("Rating must be between 1 and 5 stars.")
        except (ValueError, TypeError):
            preview['warnings'].append("Invalid numerical rating.")

    # 3. Reassignment & Distribution Preview
    reassign_cfg = changes.get('reassignment')
    if reassign_cfg:
        target_role = reassign_cfg.get('role', 'TELECALLER').upper()
        strategy = reassign_cfg.get('strategy', 'single')  # 'single' or 'percentage'
        task_handling = reassign_cfg.get('pending_tasks', 'reassign')

        if strategy == 'single':
            target_user_id = reassign_cfg.get('target_user_id')
            target_user = User.objects.filter(id=target_user_id, is_active=True).first()
            if not target_user:
                preview['warnings'].append("Target assignee not found or inactive.")
            else:
                # Optimized bulk branch check
                cross_branch_count = 0
                if target_user.branch_id and not user.is_admin_user:
                    cross_branch_count = qs.exclude(branch_id=target_user.branch_id).exclude(branch_id__isnull=True).count()
                    if cross_branch_count > 0:
                        preview['warnings'].append(
                            f"{cross_branch_count} lead(s) belong to a different branch than {target_user.get_full_name() or target_user.username} and will be skipped."
                        )

                alloc_entry = {
                    'user_id': target_user.id,
                    'user_name': target_user.get_full_name() or target_user.username,
                    'count': total_authorized,
                    'ineligible_count': cross_branch_count,
                    'percentage': 100.0,
                }
                preview['changes_summary']['reassignment'] = {
                    'strategy': 'single',
                    'target_role': target_role,
                    'assignee_name': target_user.get_full_name() or target_user.username,
                    'assignee_id': target_user.id,
                    'assigned_count': total_authorized,
                    'pending_tasks_handling': task_handling,
                    'allocations': [alloc_entry],
                }
                preview['allocation_summary'] = [alloc_entry]
        elif strategy == 'percentage':
            allocations = reassign_cfg.get('allocations', [])
            try:
                user_ids = [a.get('user_id') for a in allocations if a.get('user_id')]
                user_map = {u.id: u for u in User.objects.filter(id__in=user_ids, is_active=True)}

                enriched_alloc = []
                for a in allocations:
                    u = user_map.get(a.get('user_id'))
                    if u:
                        enriched_alloc.append({
                            'user_id': u.id,
                            'user_name': u.get_full_name() or u.username,
                            'percentage': a.get('percentage', 0),
                        })

                distributed = calculate_percentage_distribution(total_authorized, enriched_alloc)
                preview['changes_summary']['reassignment'] = {
                    'strategy': 'percentage',
                    'target_role': target_role,
                    'allocations': distributed,
                    'pending_tasks_handling': task_handling,
                }
                preview['allocation_summary'] = distributed
            except ValidationError as ve:
                preview['warnings'].append(str(ve))

    # 4. Tags Preview
    tags_cfg = changes.get('tags')
    if tags_cfg:
        add_tags = tags_cfg.get('add', [])
        remove_tags = tags_cfg.get('remove', [])
        preview['changes_summary']['tags'] = {
            'add': [str(t).strip() for t in add_tags if str(t).strip()],
            'remove': [str(t).strip() for t in remove_tags if str(t).strip()],
        }

    # 5. Custom & Standard Fields Preview
    fields_cfg = changes.get('fields', {})
    valid_fields = {}
    for k, v in fields_cfg.items():
        if k in PROTECTED_FIELDS:
            preview['warnings'].append(f"Modification of protected field '{k}' is prohibited.")
        else:
            valid_fields[k] = v
    if valid_fields:
        preview['changes_summary']['fields'] = valid_fields

    return preview


@transaction.atomic
def execute_bulk_edit(
    user: User,
    lead_ids: Optional[List[int]] = None,
    filter_params: Optional[Dict[str, Any]] = None,
    changes: Optional[Dict[str, Any]] = None,
    idempotency_key: Optional[str] = None,
    reassignment_note: str = ""
) -> Dict[str, Any]:
    """
    Executes atomic, concurrency-safe bulk updates on authorized leads.
    Preserves audit history via BulkOperationRecord, Activity logs,
    LeadAssignmentHistory, and LeadStatusHistory.
    """
    if not user.is_authenticated or user.role == UserRole.RECEPTIONIST:
        raise PermissionDenied("You do not have permission to execute bulk edits.")

    changes = _normalize_changes(changes)
    op_id = f"bulk-{uuid.uuid4().hex[:12]}"

    # Check idempotency to prevent duplicate submissions
    if idempotency_key:
        existing_op = BulkOperationRecord.objects.filter(
            idempotency_key=idempotency_key,
            actor=user
        ).first()
        if existing_op:
            if existing_op.status in [BulkOperationStatus.COMPLETED, BulkOperationStatus.COMPLETED_WITH_ERRORS]:
                return {
                    'success': True,
                    'operation_id': existing_op.operation_id,
                    'status': existing_op.status,
                    'total_authorized': existing_op.total_authorized,
                    'success_count': existing_op.success_count,
                    'skipped_count': existing_op.skipped_count,
                    'failed_count': existing_op.failed_count,
                    'error_summary': existing_op.error_summary,
                    'message': "Retrieved existing idempotent operation result."
                }

    qs = resolve_authorized_leads(user, lead_ids=lead_ids, filter_params=filter_params)
    total_authorized = qs.count()

    op_record = BulkOperationRecord.objects.create(
        operation_id=op_id,
        idempotency_key=idempotency_key or '',
        actor=user,
        operation_type='bulk_edit',
        status=BulkOperationStatus.RUNNING,
        total_requested=len(lead_ids) if lead_ids else total_authorized,
        total_authorized=total_authorized,
        requested_changes=changes,
        reassignment_note=reassignment_note,
    )

    if total_authorized == 0:
        op_record.status = BulkOperationStatus.COMPLETED
        op_record.completed_at = timezone.now()
        op_record.save(update_fields=['status', 'completed_at'])
        return {
            'success': True,
            'operation_id': op_id,
            'status': op_record.status,
            'success_count': 0,
            'skipped_count': 0,
            'failed_count': 0,
            'message': "No matching authorized leads to update."
        }

    # Prepare Reassignment distribution map if requested
    reassign_cfg = changes.get('reassignment')
    distribution_assignments = []
    task_handling = 'preserve'
    target_role = 'TELECALLER'

    if reassign_cfg:
        target_role = reassign_cfg.get('role', 'TELECALLER').upper()
        strategy = reassign_cfg.get('strategy', 'single')
        task_handling = reassign_cfg.get('pending_tasks', 'reassign')

        if strategy == 'single':
            t_user = User.objects.filter(id=reassign_cfg.get('target_user_id'), is_active=True).first()
            if not t_user:
                raise ValidationError("Target assignee is inactive or does not exist.")
            distribution_assignments = [(t_user, total_authorized)]
        elif strategy == 'percentage':
            allocs = reassign_cfg.get('allocations', [])
            enriched = []
            for a in allocs:
                u = User.objects.filter(id=a.get('user_id'), is_active=True).first()
                if u:
                    enriched.append({'user_id': u.id, 'user_obj': u, 'percentage': a.get('percentage', 0)})
            distributed_counts = calculate_percentage_distribution(total_authorized, enriched)
            for d in distributed_counts:
                u_obj = next((x['user_obj'] for x in enriched if x['user_id'] == d['user_id']), None)
                if u_obj:
                    distribution_assignments.append((u_obj, d['count']))

    # Flatten assignee queue for sequential assignment
    assignee_queue = []
    for user_obj, count in distribution_assignments:
        assignee_queue.extend([user_obj] * count)

    success_count = 0
    skipped_count = 0
    failed_count = 0
    error_summary = []

    # Bounded chunk processing with row locking
    candidate_ids = list(qs.values_list('id', flat=True))
    CHUNK_SIZE = 100

    for start in range(0, len(candidate_ids), CHUNK_SIZE):
        batch_ids = candidate_ids[start:start + CHUNK_SIZE]
        locked_leads = list(
            Lead.objects.select_for_update(skip_locked=True)
            .filter(id__in=batch_ids)
            .select_related('branch', 'assigned_telecaller', 'assigned_counselor')
        )

        for lead in locked_leads:
            try:
                if not can_edit_lead(user, lead):
                    skipped_count += 1
                    error_summary.append(f"Lead #{lead.id}: Insufficient edit permissions.")
                    continue

                lead_modified = False
                update_fields = ['updated_at']

                # 1. Apply Status Transition
                new_status = changes.get('status')
                if new_status and new_status != lead.status:
                    if can_change_lead_status(user, lead, new_status):
                        old_st = lead.status
                        lead.status = new_status
                        update_fields.append('status')
                        lead_modified = True

                        LeadStatusHistory.objects.create(
                            lead=lead,
                            old_status=old_st,
                            new_status=new_status,
                            changed_by=user,
                            remarks=f"Bulk edit #{op_id}: {reassignment_note}".strip()
                        )
                    else:
                        error_summary.append(f"Lead #{lead.id}: Permission denied for transition to '{new_status}'.")

                # 2. Apply Priority Rating
                new_rating = changes.get('rating')
                if new_rating is not None:
                    try:
                        r_val = int(new_rating)
                        if 1 <= r_val <= 5 and lead.rating != r_val:
                            lead.rating = r_val
                            update_fields.append('rating')
                            lead_modified = True
                    except (ValueError, TypeError):
                        pass

                # 3. Apply Reassignment
                if assignee_queue:
                    target_user = assignee_queue.pop(0)
                    if can_reassign_lead(user, lead, target_user):
                        old_assignee_field = 'assigned_counselor' if target_role == 'COUNSELOR' else 'assigned_telecaller'
                        old_assignee = getattr(lead, old_assignee_field, None)

                        setattr(lead, old_assignee_field, target_user)
                        lead.current_owner_type = LeadOwnerType.COUNSELOR if target_role == 'COUNSELOR' else LeadOwnerType.TELECALLER
                        lead.assignment_status = 'Assigned'
                        lead.assigned_at = timezone.now()
                        update_fields.extend([old_assignee_field, 'current_owner_type', 'assignment_status', 'assigned_at'])
                        lead_modified = True

                        LeadAssignmentHistory.objects.create(
                            lead=lead,
                            from_user=old_assignee,
                            to_user=target_user,
                            from_role=lead.current_owner_type,
                            to_role=target_role,
                            branch=lead.branch,
                            reason=reassignment_note or f"Bulk reassignment via op #{op_id}",
                            assigned_by=user,
                        )

                        # Handle Pending Follow-up Tasks
                        pending_tasks = FollowUp.objects.filter(
                            lead=lead,
                            status__in=[FollowUpStatus.PENDING, FollowUpStatus.OVERDUE]
                        )
                        if task_handling == 'reassign':
                            if target_role == 'COUNSELOR':
                                pending_tasks.update(assigned_user=target_user, updated_at=timezone.now())
                            else:
                                pending_tasks.update(telecaller=target_user, assigned_user=target_user, updated_at=timezone.now())
                        elif task_handling == 'cancel':
                            for t in pending_tasks:
                                t.status = FollowUpStatus.CANCELLED
                                t.notes = (t.notes + f"\n[Cancelled via Bulk Reassignment #{op_id}]").strip()
                                t.save(update_fields=['status', 'notes', 'updated_at'])
                    else:
                        error_summary.append(f"Lead #{lead.id}: Cannot reassign across branch boundary to {target_user.username}.")

                # 4. Apply Custom & Standard Editable Fields
                fields_cfg = changes.get('fields', {})
                for f_name, f_val in fields_cfg.items():
                    if f_name in PROTECTED_FIELDS:
                        continue

                    if f_name == 'category' and f_val in LeadCategory.values:
                        lead.category = f_val
                        update_fields.append('category')
                        lead_modified = True
                    elif f_name == 'product_id' and f_val:
                        lead.product_id = int(f_val)
                        update_fields.append('product')
                        lead_modified = True
                    elif f_name == 'branch_id' and f_val:
                        bid = int(f_val)
                        if user.is_admin_user or bid in get_accessible_branch_ids(user):
                            lead.branch_id = bid
                            update_fields.append('branch')
                            lead_modified = True
                    elif f_name == 'channel_id' and f_val:
                        lead.channel_id = int(f_val)
                        update_fields.append('channel')
                        lead_modified = True
                    elif f_name == 'visitor_status' and f_val in VisitorStatus.values:
                        lead.visitor_status = f_val
                        update_fields.append('visitor_status')
                        lead_modified = True
                    elif f_name == 'center_visit_date' and f_val:
                        lead.center_visit_date = f_val
                        update_fields.append('center_visit_date')
                        lead_modified = True
                    elif f_name == 'notes_action':
                        action_type = fields_cfg.get('notes_action', 'append')
                        action_text = (fields_cfg.get('notes_text') or '').strip()
                        if action_text:
                            if action_type == 'append':
                                lead.notes = f"{lead.notes}\n{action_text}".strip()
                            elif action_type == 'prepend':
                                lead.notes = f"{action_text}\n{lead.notes}".strip()
                            elif action_type == 'replace':
                                lead.notes = action_text
                            update_fields.append('notes')
                            lead_modified = True
                    elif f_name.startswith('custom_'):
                        # Dynamic custom attributes stored in JSON field
                        key_name = f_name.replace('custom_', '')
                        curr_custom = dict(lead.custom_fields or {})
                        curr_custom[key_name] = f_val
                        lead.custom_fields = curr_custom
                        update_fields.append('custom_fields')
                        lead_modified = True

                # Direct custom_fields dictionary update
                custom_dict = changes.get('custom_fields')
                if isinstance(custom_dict, dict) and custom_dict:
                    curr_custom = dict(lead.custom_fields or {})
                    for ck, cv in custom_dict.items():
                        if ck not in PROTECTED_FIELDS:
                            curr_custom[ck] = cv
                    lead.custom_fields = curr_custom
                    update_fields.append('custom_fields')
                    lead_modified = True

                # Save lead modifications if any
                if lead_modified:
                    lead.save(update_fields=list(set(update_fields)))

                # 5. Apply Tag Associations
                tags_cfg = changes.get('tags')
                if tags_cfg:
                    add_tags = tags_cfg.get('add', [])
                    remove_tags = tags_cfg.get('remove', [])
                    for t_item in add_tags:
                        tag_obj = None
                        if isinstance(t_item, int) or (isinstance(t_item, str) and t_item.isdigit()):
                            tag_obj = LeadTag.objects.filter(id=int(t_item)).first()
                        if not tag_obj:
                            t_clean = str(t_item).strip()
                            if t_clean:
                                tag_obj, _ = LeadTag.objects.get_or_create(name=t_clean)
                        if tag_obj:
                            lead.tags.add(tag_obj)

                    for t_item in remove_tags:
                        tag_obj = None
                        if isinstance(t_item, int) or (isinstance(t_item, str) and t_item.isdigit()):
                            tag_obj = LeadTag.objects.filter(id=int(t_item)).first()
                        if not tag_obj:
                            t_clean = str(t_item).strip()
                            if t_clean:
                                tag_obj = LeadTag.objects.filter(name=t_clean).first()
                        if tag_obj:
                            lead.tags.remove(tag_obj)

                log_activity(
                    user=user,
                    action="Bulk Lead Edit",
                    description=f"Lead #{lead.id} updated via bulk operation #{op_id}.",
                    object_type="Lead",
                    object_id=lead.id
                )
                success_count += 1

            except Exception as exc:
                logger.exception("Failed bulk edit on lead #%s: %s", getattr(lead, 'id', 'unknown'), exc)
                failed_count += 1
                error_summary.append(f"Lead #{getattr(lead, 'id', '?')}: {str(exc)}")

    # Update operation audit record
    op_record.success_count = success_count
    op_record.skipped_count = skipped_count
    op_record.failed_count = failed_count
    op_record.error_summary = error_summary[:50]  # Cap summary size
    op_record.completed_at = timezone.now()

    if failed_count > 0 or skipped_count > 0:
        op_record.status = BulkOperationStatus.COMPLETED_WITH_ERRORS if success_count > 0 else BulkOperationStatus.FAILED
    else:
        op_record.status = BulkOperationStatus.COMPLETED

    op_record.save()

    return {
        'success': op_record.status in [BulkOperationStatus.COMPLETED, BulkOperationStatus.COMPLETED_WITH_ERRORS],
        'operation_id': op_id,
        'status': op_record.status,
        'total_authorized': total_authorized,
        'success_count': success_count,
        'skipped_count': skipped_count,
        'failed_count': failed_count,
        'error_summary': error_summary[:20],
        'message': f"Successfully updated {success_count} leads." + (f" ({skipped_count} skipped, {failed_count} failed)" if (skipped_count or failed_count) else "")
    }

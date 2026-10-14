"""
Bulk Lead Assignment Service.
Handles 4 distinct queues for bulk redistribution:
1. Unassigned: leads with assignment_status='Unassigned' / 'Pending Assignment' or assigned_telecaller__isnull=True.
2. Untouched: assigned but 0 total call records (calls.count() == 0).
3. Unanswered: leads with call attempts (calls.count() > 0) where all calls were RNR / No Answer / Busy, with 0 connected calls.
4. Unattended: leads where last contact was > 48 hours ago or follow-up is overdue without contact.

Supports:
- Distribution strategies: 'single' (single telecaller) or 'round_robin' (balanced across active branch telecallers).
- Concurrency protection: select_for_update(skip_locked=True).
- Audit trail: LeadAssignmentHistory and Activity logging.
"""

import logging
from itertools import cycle
from django.db import transaction
from django.db.models import Count, Max, Q, F
from django.utils import timezone
from accounts.models import User, UserRole
from branches.models import Branch
from leads.models import Lead, LeadOwnerType, TelecallerLeadSetup
from leads.handoff_service import reassign_lead
from activities.utils import log_activity

logger = logging.getLogger('crm')


def get_queue_queryset(queue_type: str, branch=None, user=None):
    """
    Returns the filtered queryset for a specific queue, respecting branch constraints.
    Supports single branch ID, list/tuple/set of branch IDs, or comma-separated string.
    """
    qs = Lead.objects.all().select_related('branch', 'assigned_telecaller', 'assigned_counselor', 'channel')

    # Apply branch filtering if specified
    if branch:
        if isinstance(branch, (list, tuple, set)):
            clean_bids = [int(b) for b in branch if str(b).isdigit()]
            if clean_bids:
                qs = qs.filter(branch_id__in=clean_bids)
        elif isinstance(branch, str) and ',' in branch:
            clean_bids = [int(b.strip()) for b in branch.split(',') if b.strip().isdigit()]
            if clean_bids:
                qs = qs.filter(branch_id__in=clean_bids)
        elif isinstance(branch, (int, str)) and str(branch).isdigit():
            qs = qs.filter(branch_id=int(branch))
        else:
            qs = qs.filter(branch=branch)
    elif user and not getattr(user, 'is_admin_user', False):
        from accounts.permissions import get_accessible_branch_ids
        accessible_branch_ids = get_accessible_branch_ids(user)
        if accessible_branch_ids:
            qs = qs.filter(branch_id__in=accessible_branch_ids)

    queue_type = queue_type.lower().strip()

    if queue_type == 'unassigned':
        return qs.filter(
            Q(assigned_telecaller__isnull=True) |
            Q(assignment_status__in=['Unassigned', 'Pending Assignment'])
        ).order_by('-created_at')

    elif queue_type == 'untouched':
        return qs.filter(
            assigned_telecaller__isnull=False
        ).annotate(
            call_count=Count('calls')
        ).filter(
            call_count=0
        ).order_by('-created_at')

    elif queue_type == 'unanswered':
        # Has call attempts, but 0 connected/completed calls, all calls are unanswered/failed
        return qs.filter(
            assigned_telecaller__isnull=False
        ).annotate(
            total_calls=Count('calls'),
            connected_calls=Count(
                'calls',
                filter=Q(calls__call_status__in=['Connected', 'Completed']) | Q(calls__duration__gt=0)
            )
        ).filter(
            total_calls__gt=0,
            connected_calls=0
        ).order_by('-updated_at')

    elif queue_type == 'unattended':
        cutoff_48h = timezone.now() - timezone.timedelta(hours=48)
        today = timezone.localdate()
        return qs.filter(
            assigned_telecaller__isnull=False
        ).annotate(
            latest_call=Max('calls__call_started_at')
        ).filter(
            Q(latest_call__lt=cutoff_48h) |
            Q(latest_call__isnull=True, created_at__lt=cutoff_48h) |
            Q(followups__status='Pending', followups__follow_up_date__lt=today)
        ).distinct().order_by('-updated_at')

    else:
        return qs.none()


def get_queue_counts(branch=None, user=None):
    """
    Returns counts for all 4 queues simultaneously for badges and summary cards.
    """
    return {
        'unassigned': get_queue_queryset('unassigned', branch=branch, user=user).count(),
        'untouched': get_queue_queryset('untouched', branch=branch, user=user).count(),
        'unanswered': get_queue_queryset('unanswered', branch=branch, user=user).count(),
        'unattended': get_queue_queryset('unattended', branch=branch, user=user).count(),
    }


def get_bulk_assignment_preview(
    queue_type: str,
    branch_ids=None,
    telecaller_ids=None,
    lead_ids=None,
    user=None
):
    """
    Computes preview statistics for bulk assignment:
    - total eligible leads in queue / branches
    - counts of selected branches and telecallers
    - estimated distribution per telecaller
    - branch compatibility warnings (branches with leads but 0 selected telecallers)
    """
    if isinstance(branch_ids, str):
        branch_ids = [int(b.strip()) for b in branch_ids.split(',') if b.strip().isdigit()]
    elif isinstance(branch_ids, (list, tuple, set)):
        branch_ids = [int(b) for b in branch_ids if str(b).isdigit()]
    else:
        branch_ids = []

    if isinstance(telecaller_ids, str):
        telecaller_ids = [int(t.strip()) for t in telecaller_ids.split(',') if t.strip().isdigit()]
    elif isinstance(telecaller_ids, (list, tuple, set)):
        telecaller_ids = [int(t) for t in telecaller_ids if str(t).isdigit()]
    else:
        telecaller_ids = []

    base_qs = get_queue_queryset(queue_type, branch=branch_ids or None, user=user)
    if lead_ids:
        base_qs = base_qs.filter(id__in=lead_ids)

    total_eligible = min(base_qs.count(), 100)

    # Telecallers breakdown
    tc_qs = User.objects.filter(role=UserRole.TELECALLER, is_active=True).select_related('branch')
    if telecaller_ids:
        tc_qs = tc_qs.filter(id__in=telecaller_ids)
    elif branch_ids:
        tc_qs = tc_qs.filter(branch_id__in=branch_ids)

    selected_tcs = list(tc_qs)
    tc_count = len(selected_tcs)

    # Group telecallers by branch
    tcs_by_branch_id = {}
    for tc in selected_tcs:
        if tc.branch_id:
            tcs_by_branch_id.setdefault(tc.branch_id, []).append(tc)

    # Lead counts grouped by branch
    lead_counts_by_branch = {}
    if branch_ids:
        branch_lead_counts = base_qs.values('branch_id').annotate(c=Count('id'))
        for bl in branch_lead_counts:
            lead_counts_by_branch[bl['branch_id']] = bl['c']

    warnings = []
    branches_map = {b.id: b.name for b in Branch.objects.filter(id__in=branch_ids)} if branch_ids else {}
    for b_id in branch_ids:
        b_name = branches_map.get(b_id, f"Branch #{b_id}")
        leads_in_b = lead_counts_by_branch.get(b_id, 0)
        tcs_in_b = len(tcs_by_branch_id.get(b_id, []))
        if leads_in_b > 0 and tcs_in_b == 0:
            warnings.append(f"Branch '{b_name}' has {leads_in_b} lead(s) in this queue, but no telecallers selected. These leads will be skipped.")

    est_per_tc = round(total_eligible / tc_count, 1) if tc_count > 0 else 0

    return {
        'total_eligible_leads': total_eligible,
        'selected_branches_count': len(branch_ids),
        'selected_telecallers_count': tc_count,
        'estimated_leads_per_telecaller': est_per_tc,
        'warnings': warnings,
        'branch_telecaller_counts': {
            branches_map.get(b_id, f"Branch #{b_id}"): len(tcs)
            for b_id, tcs in tcs_by_branch_id.items()
        }
    }


def execute_bulk_assignment(
    queue_type: str,
    lead_ids=None,
    strategy: str = 'round_robin',
    target_role: str = 'TELECALLER',
    target_telecaller_id=None,
    target_branch_id=None,
    branch_ids=None,
    telecaller_ids=None,
    reason: str = '',
    assigned_by=None,
    limit: int = 100
):
    """
    Executes atomic bulk assignment on leads from a specific queue:
    - strategy='single': assigns all eligible leads to target_telecaller/counselor.
    - strategy='round_robin': distributes leads evenly across selected staff with strict branch compatibility.
    Uses select_for_update(skip_locked=True) for concurrency safety and database transactions.
    """
    target_role = (target_role or 'TELECALLER').upper()
    role_enum = UserRole.COUNSELOR if target_role == 'COUNSELOR' else UserRole.TELECALLER
    role_label = 'counselor' if target_role == 'COUNSELOR' else 'telecaller'

    if not reason:
        reason = f"Bulk {role_label} assignment from queue: {queue_type.capitalize()}"

    # 1. Normalize branch_ids
    clean_branch_ids = []
    if branch_ids:
        if isinstance(branch_ids, str):
            clean_branch_ids = [int(b.strip()) for b in branch_ids.split(',') if b.strip().isdigit()]
        elif isinstance(branch_ids, (list, tuple, set)):
            clean_branch_ids = [int(b) for b in branch_ids if str(b).isdigit()]
    elif target_branch_id and str(target_branch_id).isdigit():
        clean_branch_ids = [int(target_branch_id)]

    # Validate user permissions for branches
    if assigned_by and not getattr(assigned_by, 'is_admin_user', False):
        from accounts.permissions import get_accessible_branch_ids
        accessible = set(get_accessible_branch_ids(assigned_by))
        if clean_branch_ids and not set(clean_branch_ids).issubset(accessible):
            return {
                'success': False,
                'assigned_count': 0,
                'error': 'Permission denied: You do not have permission to manage assignments for one or more selected branches.'
            }

    # 2. Normalize staff IDs
    clean_tc_ids = []
    if telecaller_ids:
        if isinstance(telecaller_ids, str):
            clean_tc_ids = [int(t.strip()) for t in telecaller_ids.split(',') if t.strip().isdigit()]
        elif isinstance(telecaller_ids, (list, tuple, set)):
            clean_tc_ids = [int(t) for t in telecaller_ids if str(t).isdigit()]
    elif target_telecaller_id and str(target_telecaller_id).isdigit():
        clean_tc_ids = [int(target_telecaller_id)]

    # 3. Determine recipient staff
    tc_qs = User.objects.filter(role=role_enum, is_active=True).select_related('branch')
    if clean_tc_ids:
        tc_qs = tc_qs.filter(id__in=clean_tc_ids)
    elif clean_branch_ids:
        tc_qs = tc_qs.filter(branch_id__in=clean_branch_ids)
    elif assigned_by and getattr(assigned_by, 'branch_id', None):
        tc_qs = tc_qs.filter(branch_id=assigned_by.branch_id)

    telecaller_pool = list(tc_qs.order_by('first_name', 'username', 'id'))
    if not telecaller_pool:
        return {
            'success': False,
            'assigned_count': 0,
            'error': f'No active, eligible {role_label}s available for assignment in the selected criteria.'
        }

    # If single strategy, require exactly one target telecaller
    if strategy == 'single':
        telecaller_pool = [telecaller_pool[0]]

    # 4. Map telecallers by branch for branch-compatible Round-Robin
    tcs_by_branch = {}
    for tc in telecaller_pool:
        if tc.branch_id:
            tcs_by_branch.setdefault(tc.branch_id, []).append(tc)

    branch_cycles = {
        b_id: cycle(tcs) for b_id, tcs in tcs_by_branch.items()
    }
    global_tc_cycle = cycle(telecaller_pool)

    # 5. Fetch candidate leads
    base_qs = get_queue_queryset(queue_type, branch=clean_branch_ids or None, user=assigned_by)
    if lead_ids:
        base_qs = base_qs.filter(id__in=lead_ids)

    # Enforce 100 leads limit per execution
    max_limit = min(limit, 100) if limit and limit > 0 else 100
    candidate_ids = list(base_qs.values_list('id', flat=True)[:max_limit])

    if not candidate_ids:
        return {
            'success': False,
            'assigned_count': 0,
            'error': 'No matching leads found in this queue to assign.'
        }

    assigned_count = 0
    assigned_details = []
    telecaller_summary = {}
    skipped_leads = []

    # 6. Concurrency safe atomic transaction
    with transaction.atomic():
        locked_leads = list(
            Lead.objects.select_for_update(skip_locked=True)
            .filter(id__in=candidate_ids)
            .select_related('branch', 'assigned_telecaller')
        )

        for lead in locked_leads:
            assigned_telecaller = None

            if strategy == 'single':
                assigned_telecaller = telecaller_pool[0]
                # Enforce branch compatibility if lead belongs to a branch
                if lead.branch_id and assigned_telecaller.branch_id and lead.branch_id != assigned_telecaller.branch_id:
                    skipped_leads.append({
                        'lead_id': lead.id,
                        'lead_name': lead.name,
                        'reason': f"Lead belongs to '{lead.branch.name if lead.branch else 'Unknown'}' while selected telecaller belongs to '{assigned_telecaller.branch.name if assigned_telecaller.branch else 'Unknown'}'."
                    })
                    continue
            else:
                # Round-robin: check branch compatibility
                if lead.branch_id:
                    if lead.branch_id in branch_cycles:
                        assigned_telecaller = next(branch_cycles[lead.branch_id])
                    else:
                        # Lead has a branch, but no telecaller was selected for that branch!
                        skipped_leads.append({
                            'lead_id': lead.id,
                            'lead_name': lead.name,
                            'branch_name': lead.branch.name if lead.branch else 'Unknown',
                            'reason': f"No telecallers selected for branch '{lead.branch.name if lead.branch else 'Unknown'}'"
                        })
                        continue
                else:
                    # Lead has no branch: distribute across global selected pool
                    assigned_telecaller = next(global_tc_cycle)
                    if assigned_telecaller.branch:
                        lead.branch = assigned_telecaller.branch

            # Reassign lead safely
            old_telecaller_name = lead.assigned_telecaller.username if lead.assigned_telecaller else 'None'
            reassign_lead(
                lead,
                to_user=assigned_telecaller,
                to_role=target_role,
                reason=reason,
                assigned_by=assigned_by,
                _skip_permission_check=True
            )

            # Update assignment status
            lead.assignment_status = 'Assigned'
            lead.assigned_at = timezone.now()
            update_fields = ['assignment_status', 'assigned_at', 'updated_at']
            if not lead.branch_id and assigned_telecaller.branch_id:
                lead.branch = assigned_telecaller.branch
                update_fields.append('branch')
            lead.save(update_fields=update_fields)

            # Increment lead count in setup if exists
            TelecallerLeadSetup.objects.filter(
                telecaller=assigned_telecaller,
                branch=lead.branch
            ).update(lead_count=F('lead_count') + 1)

            # Log CRM activity
            log_activity(
                user=assigned_by,
                action="Bulk Lead Assigned",
                description=f"Lead #{lead.id} ({lead.name}) bulk assigned from '{old_telecaller_name}' to Telecaller '{assigned_telecaller.username}' via {strategy} distribution from queue '{queue_type}'. Reason: {reason}",
                object_type="Lead",
                object_id=lead.id
            )

            assigned_count += 1
            tc_key = assigned_telecaller.get_full_name() or assigned_telecaller.username
            telecaller_summary[tc_key] = telecaller_summary.get(tc_key, 0) + 1
            assigned_details.append({
                'lead_id': lead.id,
                'lead_name': lead.name,
                'branch_name': lead.branch.name if lead.branch else 'No Branch',
                'telecaller_username': assigned_telecaller.username,
                'telecaller_name': tc_key,
            })

    msg = f"Successfully assigned {assigned_count} lead(s) across {len(telecaller_summary)} telecaller(s)."
    if skipped_leads:
        msg += f" Note: {len(skipped_leads)} lead(s) were skipped due to branch eligibility constraints."

    return {
        'success': True,
        'assigned_count': assigned_count,
        'skipped_count': len(skipped_leads),
        'queue_type': queue_type,
        'strategy': strategy,
        'telecaller_summary': telecaller_summary,
        'skipped_leads': skipped_leads,
        'details': assigned_details,
        'message': msg
    }

import logging
from django.db import transaction
from django.db.models import F, Count, Q
from django.utils import timezone
from accounts.models import User, UserRole
from branches.models import Branch
from activities.utils import log_activity

logger = logging.getLogger('crm')


def assign_new_lead(lead, branch=None, source="Google Sheet", triggered_by=None, exclude_telecaller=None) -> bool:
    """
    Single Centralized Lead Assignment Engine across all sources:
    - Google Sheets (Offline, Instagram, Facebook, future spreadsheets)
    - Google Form
    - Manual Import / Creation
    """
    from .models import LeadSetupConfig, TelecallerLeadSetup, AssignmentMethod, LeadOwnerType, LeadAssignmentHistory

    target_branch = branch or getattr(lead, 'branch', None)
    if not target_branch:
        lead.assignment_status = 'Pending Assignment'
        lead.pending_assignment_reason = 'Lead does not have an assigned branch.'
        lead.assigned_telecaller = None
        if lead.pk:
            lead.save(update_fields=['assignment_status', 'pending_assignment_reason', 'assigned_telecaller', 'updated_at'])
        else:
            lead.save()
        log_activity(
            user=triggered_by,
            action="Lead Assignment Pending",
            description=f"Lead '{lead.name}' marked Pending Assignment: Missing branch.",
            object_type="Lead",
            object_id=getattr(lead, 'pk', None)
        )
        return False

    with transaction.atomic():
        # Channel-aware branch percentage lookup
        lead_channel = getattr(lead, 'channel', None)
        if not lead_channel and getattr(lead, 'source', None):
            from channels.models import Channel
            lead_channel = Channel.objects.filter(name__iexact=lead.source, status='Active').first()

        # Query active telecallers belonging to this branch with is_active=True in setup
        qs = TelecallerLeadSetup.objects.select_for_update().filter(
            branch=target_branch,
            is_active=True,
            telecaller__is_active=True,
            telecaller__role=UserRole.TELECALLER
        )
        if exclude_telecaller:
            qs = qs.exclude(telecaller=exclude_telecaller)

        # Prefer channel-specific rules if configured; fallback to general branch rules
        if lead_channel and qs.filter(channel=lead_channel).exists():
            qs = qs.filter(channel=lead_channel)
        else:
            qs = qs.filter(channel__isnull=True)

        setups = list(qs.select_related('telecaller', 'telecaller__branch'))

        # Strictly percentage-based distribution with mandatory 100% total validation
        valid_setups = [s for s in setups if s.assignment_percentage > 0]
        total_pct = sum(s.assignment_percentage for s in valid_setups)

        # Strict 100% check
        if not valid_setups:
            lead.branch = target_branch
            lead.assignment_status = 'Pending Assignment'
            lead.pending_assignment_reason = f"No active telecallers or allocation configured for branch '{target_branch.name}'."
            lead.assigned_telecaller = None
            if lead.pk:
                lead.save(update_fields=['branch', 'assignment_status', 'pending_assignment_reason', 'assigned_telecaller', 'updated_at'])
            else:
                lead.save()
            log_activity(
                user=triggered_by,
                action="Lead Assignment Pending",
                description=f"Lead '{lead.name}' marked Pending Assignment: No active telecallers or allocation configured for branch '{target_branch.name}'.",
                object_type="Lead",
                object_id=getattr(lead, 'pk', None)
            )
            return False

        # In standard new-lead ingestion, total percentage must equal 100%.
        # When exclude_telecaller is specified (e.g. during SLA escalation), we pick the best among remaining eligible telecallers.
        if not exclude_telecaller and total_pct != 100:
            lead.branch = target_branch
            lead.assignment_status = 'Pending Assignment'
            lead.pending_assignment_reason = f"Branch '{target_branch.name}' telecaller allocation total is {total_pct}% (must equal exactly 100%)."
            lead.assigned_telecaller = None
            if lead.pk:
                lead.save(update_fields=['branch', 'assignment_status', 'pending_assignment_reason', 'assigned_telecaller', 'updated_at'])
            else:
                lead.save()
            log_activity(
                user=triggered_by,
                action="Lead Assignment Pending",
                description=f"Lead '{lead.name}' marked Pending Assignment: Branch '{target_branch.name}' allocation total is {total_pct}% (must equal 100%).",
                object_type="Lead",
                object_id=getattr(lead, 'pk', None)
            )
            return False

        # Strict Weighted Distribution Algorithm (Largest Positive Allocation Gap)
        # Cumulative total assigned to the active allocation group
        total_assigned = sum(s.current_leads_assigned for s in valid_setups)
        next_total = total_assigned + 1

        def allocation_score(s):
            target_count = next_total * (s.assignment_percentage / 100.0)
            actual_count = s.current_leads_assigned
            gap = target_count - actual_count
            # Tie breakers: larger gap, higher percentage, lower current count, lower id
            return (gap, s.assignment_percentage, -s.current_leads_assigned, -s.id)

        best_setup = max(valid_setups, key=allocation_score)
        selected_telecaller = best_setup.telecaller

        if not selected_telecaller:
            lead.branch = target_branch
            lead.assignment_status = 'Pending Assignment'
            lead.pending_assignment_reason = f"Could not determine eligible telecaller for branch '{target_branch.name}'."
            lead.assigned_telecaller = None
            if lead.pk:
                lead.save(update_fields=['branch', 'assignment_status', 'pending_assignment_reason', 'assigned_telecaller', 'updated_at'])
            else:
                lead.save()
            return False

        # Identify assigned manager (Sales Head with access to this branch)
        selected_manager = User.objects.filter(
            role=UserRole.SALES_HEAD,
            branch_access__branch=target_branch,
            is_active=True
        ).annotate(cnt=Count('manager_leads')).order_by('cnt', 'id').first()
        if not selected_manager:
            selected_manager = User.objects.filter(role=UserRole.SALES_HEAD, is_active=True).first()

        # Update Lead atomically
        previous_telecaller = lead.assigned_telecaller if lead.pk else None
        lead.branch = target_branch
        lead.assigned_telecaller = selected_telecaller
        lead.assigned_sales_head = selected_manager
        lead.current_owner_type = LeadOwnerType.TELECALLER
        lead.assignment_status = 'Assigned'
        lead.pending_assignment_reason = ''
        lead.assigned_at = timezone.now()
        if lead.pk:
            lead.save(update_fields=[
                'branch',
                'assigned_telecaller',
                'assigned_sales_head',
                'current_owner_type',
                'assignment_status',
                'pending_assignment_reason',
                'assigned_at',
                'updated_at'
            ])
        else:
            lead.save()

        LeadAssignmentHistory.objects.create(
            lead=lead,
            from_user=previous_telecaller,
            to_user=selected_telecaller,
            from_role=UserRole.TELECALLER if previous_telecaller else '',
            to_role=UserRole.TELECALLER,
            branch=target_branch,
            reason=source,
            assigned_by=triggered_by if getattr(triggered_by, 'is_authenticated', False) else None,
        )

        # Atomically increment telecaller's assignment counter
        TelecallerLeadSetup.objects.filter(pk=best_setup.pk).update(
            current_leads_assigned=F('current_leads_assigned') + 1,
            updated_at=timezone.now()
        )

        tc_name = selected_telecaller.get_full_name() or selected_telecaller.username
        mgr_name = selected_manager.get_full_name() or selected_manager.username if selected_manager else "Unassigned"

        log_activity(
            user=triggered_by or selected_manager,
            action="Lead Auto-Assigned",
            description=f"Lead '{lead.name}' auto-assigned to Branch '{target_branch.name}' Telecaller '{tc_name}' (Sales Head: {mgr_name}) via {source}.",
            object_type="Lead",
            object_id=lead.pk
        )
        return True


def assign_lead_to_branch_telecaller(lead, branch=None, source="Google Form", triggered_by=None):
    """
    Backwards-compatible wrapper delegating to the unified assign_new_lead engine.
    """
    target_branch = branch or getattr(lead, 'branch', None)
    if target_branch and getattr(lead, 'branch', None) != target_branch:
        lead.branch = target_branch
        lead.save(update_fields=['branch'])
    return assign_new_lead(lead, branch=target_branch, source=source, triggered_by=triggered_by)


def assign_lead_automatically(lead, branch=None, source="Import", triggered_by=None):
    """
    Backwards-compatible wrapper delegating to the unified assign_new_lead engine.
    """
    target_branch = branch or getattr(lead, 'branch', None)
    if target_branch and getattr(lead, 'branch', None) != target_branch:
        lead.branch = target_branch
        lead.save(update_fields=['branch'])
    return assign_new_lead(lead, branch=target_branch, source=source, triggered_by=triggered_by)


def retry_pending_assignments(branch=None, user=None) -> tuple[int, int]:
    """
    Retries assignment for all leads currently marked 'Pending Assignment' or unassigned.
    Returns: (newly_assigned_count, still_pending_count)
    """
    from .models import Lead

    pending_qs = Lead.objects.filter(
        Q(assignment_status='Pending Assignment') |
        Q(assigned_telecaller__isnull=True, assignment_status__in=['Pending Assignment', 'Unassigned'])
    )
    if branch:
        pending_qs = pending_qs.filter(Q(branch=branch) | Q(branch__isnull=True))

    assigned_count = 0
    still_pending_count = 0

    for lead in pending_qs:
        target_b = lead.branch or branch
        success = assign_new_lead(lead, branch=target_b, source="Retry Assignment", triggered_by=user)
        if success:
            assigned_count += 1
        else:
            still_pending_count += 1

    return assigned_count, still_pending_count


def apply_branch_lead_distribution(branch, user=None) -> tuple[int, int, str]:
    """
    Applies strict percentage-based distribution to all available leads in the specified branch.
    Available leads include:
    - Leads in the branch (or unassigned branch leads)
    - Excluding protected leads (leads in progress, follow-up, demo scheduled, converted, lost, or having existing calls/followups)
    - Unassigned leads, pending assignment leads, or fresh/new leads
    
    Guarantees:
    - Exactly reflects the configured percentages across all available leads in the database.
    - Saves assignments directly to Lead.assigned_telecaller, Lead.assigned_sales_head, Lead.assignment_status='Assigned'.
    - Updates telecaller current_leads_assigned counters.
    - Preserves all protected leads.
    """
    from .models import Lead, LeadStatus, TelecallerLeadSetup, AssignmentMethod, LeadSetupConfig, LeadOwnerType, LeadAssignmentHistory

    if not branch:
        return 0, 0, "No branch provided."

    with transaction.atomic():
        valid_setups = list(
            TelecallerLeadSetup.objects.select_for_update()
            .filter(
                branch=branch,
                is_active=True,
                assignment_percentage__gt=0,
                telecaller__is_active=True,
                telecaller__role=UserRole.TELECALLER
            )
            .select_related('telecaller', 'telecaller__branch')
            .order_by('id')
        )

        if not valid_setups:
            unassigned_qs = Lead.objects.filter(
                Q(branch=branch) | Q(branch__isnull=True)
            ).filter(
                Q(assigned_telecaller__isnull=True) | Q(assignment_status='Pending Assignment')
            )
            count = unassigned_qs.count()
            unassigned_qs.update(
                branch=branch,
                assignment_status='Pending Assignment',
                pending_assignment_reason=f"No active telecallers or allocation configured for branch '{branch.name}'."
            )
            return 0, count, f"No active telecallers or allocation configured for branch '{branch.name}'."

        total_pct = sum(s.assignment_percentage for s in valid_setups)
        if total_pct != 100:
            unassigned_qs = Lead.objects.filter(
                Q(branch=branch) | Q(branch__isnull=True)
            ).filter(
                Q(assigned_telecaller__isnull=True) | Q(assignment_status='Pending Assignment')
            )
            count = unassigned_qs.count()
            unassigned_qs.update(
                branch=branch,
                assignment_status='Pending Assignment',
                pending_assignment_reason=f"Branch '{branch.name}' telecaller allocation total is {total_pct}% (must equal exactly 100%)."
            )
            return 0, count, f"Total percentage allocation for branch '{branch.name}' is {total_pct}% (must equal 100%)."

        # Protected statuses that MUST NOT be reassigned
        protected_statuses = [
            LeadStatus.CONTACTED,
            LeadStatus.INTERESTED,
            LeadStatus.FOLLOW_UP,
            LeadStatus.DEMO_SCHEDULED,
            LeadStatus.INSTITUTE_VISIT,
            LeadStatus.CONVERTED,
            LeadStatus.LOST,
            LeadStatus.LATER,
            LeadStatus.DISCUSSION
        ]

        # Query eligible leads for this branch
        available_leads = list(
            Lead.objects.select_for_update()
            .filter(
                Q(branch=branch) | Q(branch__isnull=True)
            )
            .exclude(status__in=protected_statuses)
            .exclude(calls__isnull=False)
            .exclude(followups__isnull=False)
            .filter(
                Q(assigned_telecaller__isnull=True) |
                Q(assignment_status__in=['Pending Assignment', 'Unassigned']) |
                Q(status=LeadStatus.NEW)
            )
            .distinct()
            .order_by('id')
        )

        if not available_leads:
            return 0, 0, f"No available leads to distribute for branch '{branch.name}'."

        # Reset current_leads_assigned counters so this batch distribution precisely allocates by percentage
        for s in valid_setups:
            s.current_leads_assigned = 0
        TelecallerLeadSetup.objects.filter(id__in=[s.id for s in valid_setups]).update(current_leads_assigned=0)

        now = timezone.now()
        assigned_count = 0

        for lead in available_leads:
            next_total = sum(s.current_leads_assigned for s in valid_setups) + 1
            best_setup = max(valid_setups, key=lambda s: (
                next_total * (s.assignment_percentage / 100.0) - s.current_leads_assigned,
                s.assignment_percentage,
                -s.current_leads_assigned,
                -s.id
            ))
            selected_tc = best_setup.telecaller
            selected_mgr = User.objects.filter(
                role=UserRole.SALES_HEAD, branch_access__branch=branch, is_active=True
            ).first()

            previous_telecaller = lead.assigned_telecaller
            lead.branch = branch
            lead.assigned_telecaller = selected_tc
            lead.assigned_sales_head = selected_mgr
            lead.current_owner_type = LeadOwnerType.TELECALLER
            lead.assignment_status = 'Assigned'
            lead.pending_assignment_reason = ''
            lead.assigned_at = now
            lead.save(update_fields=[
                'branch',
                'assigned_telecaller',
                'assigned_sales_head',
                'current_owner_type',
                'assignment_status',
                'pending_assignment_reason',
                'assigned_at',
                'updated_at'
            ])

            LeadAssignmentHistory.objects.create(
                lead=lead,
                from_user=previous_telecaller,
                to_user=selected_tc,
                from_role=UserRole.TELECALLER if previous_telecaller else '',
                to_role=UserRole.TELECALLER,
                branch=branch,
                reason='Batch Lead Distribution',
                assigned_by=user if getattr(user, 'is_authenticated', False) else None,
            )

            best_setup.current_leads_assigned += 1
            assigned_count += 1

        for s in valid_setups:
            s.save(update_fields=['current_leads_assigned', 'updated_at'])

        log_activity(
            user=user,
            action="Batch Lead Distribution",
            description=f"Admin applied lead assignment for branch '{branch.name}': {assigned_count} leads distributed across {len(valid_setups)} telecallers.",
            object_type="Branch",
            object_id=branch.pk
        )

        return assigned_count, 0, f"Successfully distributed {assigned_count} leads for branch '{branch.name}'."


def reassign_ineligible_telecaller_work(telecaller, branch=None, triggered_by=None) -> dict:
    """
    Centralized Reassignment Engine:
    When a telecaller is deactivated, on leave, or unchecked in Lead Setup,
    their active leads and pending/overdue follow-ups are safely reassigned
    to eligible telecallers in the branch using the configured assignment engine.

    Eligibility Rules:
    - Active telecaller, active in TelecallerLeadSetup, assignment_percentage > 0.
    - Belongs to the same branch.
    - If no eligible telecallers exist, leads are marked 'Pending Assignment'.
    - Preserves follow-up schedule, notes, status, contact info, call history & recordings.
    - Emits audit log entries to LeadAssignmentHistory and Activity.
    """
    from .models import Lead, LeadStatus, LeadAssignmentHistory, TelecallerLeadSetup, LeadOwnerType
    from followups.models import FollowUp, FollowUpStatus

    target_branch = branch or getattr(telecaller, 'branch', None)
    tc_name = telecaller.get_full_name() or telecaller.username

    # Exclude terminal closed states: CONVERTED, JOINED, LOST, NOT_INTERESTED, NOT_JOINED
    terminal_statuses = [
        LeadStatus.CONVERTED, LeadStatus.JOINED,
        LeadStatus.LOST, LeadStatus.NOT_INTERESTED, LeadStatus.NOT_JOINED
    ]

    leads_to_reassign = Lead.objects.filter(
        assigned_telecaller=telecaller
    ).exclude(status__in=terminal_statuses)

    if target_branch:
        leads_to_reassign = leads_to_reassign.filter(Q(branch=target_branch) | Q(branch__isnull=True))

    leads_to_reassign = list(leads_to_reassign.select_related('branch'))

    # Pending and overdue follow-ups belonging to this telecaller
    followups_to_reassign = list(FollowUp.objects.filter(
        telecaller=telecaller,
        status__in=[FollowUpStatus.PENDING, FollowUpStatus.OVERDUE]
    ).select_related('lead'))

    reassigned_leads = 0
    pending_leads = 0
    reassigned_followups = 0

    with transaction.atomic():
        # Check if eligible telecallers exist in branch
        for lead in leads_to_reassign:
            lead_branch = lead.branch or target_branch
            old_telecaller = lead.assigned_telecaller
            success = assign_new_lead(
                lead,
                branch=lead_branch,
                source=f"Reassignment (Telecaller '{tc_name}' Ineligible)",
                triggered_by=triggered_by
            )
            if success:
                reassigned_leads += 1
                # Sync any related pending follow-ups for this lead to the newly assigned telecaller
                new_telecaller = lead.assigned_telecaller
                for fu in followups_to_reassign:
                    if fu.lead_id == lead.pk:
                        fu.telecaller = new_telecaller
                        fu.assigned_user = new_telecaller
                        if lead.assigned_sales_head:
                            fu.manager = lead.assigned_sales_head
                        fu.save(update_fields=['telecaller', 'assigned_user', 'manager', 'updated_at'])
                        reassigned_followups += 1
            else:
                pending_leads += 1
                # Unassign telecaller on follow-ups for pending lead
                for fu in followups_to_reassign:
                    if fu.lead_id == lead.pk:
                        fu.telecaller = None
                        fu.assigned_user = None
                        fu.save(update_fields=['telecaller', 'assigned_user', 'updated_at'])

        # Any orphan follow-ups for this telecaller not attached to the fetched active leads
        handled_fu_ids = {fu.pk for fu in followups_to_reassign if fu.lead in leads_to_reassign}
        for fu in followups_to_reassign:
            if fu.pk not in handled_fu_ids:
                if fu.lead and fu.lead.assigned_telecaller and fu.lead.assigned_telecaller != telecaller:
                    fu.telecaller = fu.lead.assigned_telecaller
                    fu.assigned_user = fu.lead.assigned_telecaller
                else:
                    fu.telecaller = None
                    fu.assigned_user = None
                fu.save(update_fields=['telecaller', 'assigned_user', 'updated_at'])
                reassigned_followups += 1

    summary = {
        'reassigned_leads': reassigned_leads,
        'pending_leads': pending_leads,
        'reassigned_followups': reassigned_followups,
    }
    logger.info(f"Reassigned work for ineligible telecaller {tc_name}: {summary}")
    return summary


def run_lead_sla_escalation(stale_hours=24, untouched_days=7, triggered_by=None) -> dict:
    """
    Automated SLA & Lead Escalation Engine:
    Detects leads violating response SLAs and automatically escalates them:
    
    Rule 1: Fresh leads in 'New' status that have remained un-contacted for > stale_hours (default 24h)
    Rule 2: Leads not touched (no call or note logged) for > untouched_days (default 7 days)
    
    Escalation Action:
    - Atomically reassigns each breached lead to the next eligible telecaller in the branch using round-robin/weighted allocation.
    - If the current telecaller is the only one in the branch, sends an urgent notification to their Branch Head / Sales Head.
    - Records an audit log entry in LeadAssignmentHistory and Activity.
    - Dispatches a Notification to the newly assigned telecaller.
    """
    from .models import Lead, LeadStatus, LeadAssignmentHistory, TelecallerLeadSetup
    from calls.models import CallHistory
    from activities.services import create_notification
    from django.urls import reverse

    now = timezone.now()
    stale_cutoff = now - timezone.timedelta(hours=stale_hours)
    untouched_cutoff = now - timezone.timedelta(days=untouched_days)

    terminal_statuses = [
        LeadStatus.CONVERTED, LeadStatus.JOINED,
        LeadStatus.LOST, LeadStatus.NOT_INTERESTED, LeadStatus.NOT_JOINED
    ]

    escalated_fresh = 0
    escalated_untouched = 0
    notified_managers = 0

    # Rule 1: Fresh 'New' leads assigned but untouched past stale_cutoff
    fresh_breached = Lead.objects.filter(
        status=LeadStatus.NEW,
        assigned_telecaller__isnull=False,
        created_at__lte=stale_cutoff
    ).exclude(status__in=terminal_statuses)

    for lead in list(fresh_breached.select_related('branch', 'assigned_telecaller')):
        old_tc = lead.assigned_telecaller
        branch = lead.branch
        if not branch:
            continue

        # Look for another eligible telecaller in the branch
        other_tcs = TelecallerLeadSetup.objects.filter(
            branch=branch,
            is_active=True,
            assignment_percentage__gt=0,
            telecaller__is_active=True
        ).exclude(telecaller=old_tc)

        if other_tcs.exists():
            success = assign_new_lead(
                lead,
                branch=branch,
                source=f"SLA Escalation ({stale_hours}h Uncontacted)",
                triggered_by=triggered_by,
                exclude_telecaller=old_tc
            )
            if success:
                escalated_fresh += 1
                new_tc = lead.assigned_telecaller
                if new_tc and new_tc != old_tc:
                    try:
                        create_notification(
                            recipient=new_tc,
                            title="🚨 Escalated Lead Assigned",
                            message=f"Lead {lead.name} escalated to you due to {stale_hours}h response SLA breach.",
                            notification_type='warning',
                            link=reverse('telecaller_lead_detail', args=[lead.id])
                        )
                    except Exception:
                        pass
        else:
            # Only 1 telecaller in branch: notify their manager/branch head
            mgr = lead.assigned_sales_head or User.objects.filter(role=UserRole.BRANCH_HEAD, branch=branch, is_active=True).first()
            if mgr:
                create_notification(
                    recipient=mgr,
                    title="⚠️ SLA Breach Alert",
                    message=f"Lead {lead.name} has been uncontacted for >{stale_hours}h by {old_tc.username} (no alternate telecaller in {branch.name}).",
                    notification_type='danger',
                    link=reverse('manager_lead_detail', args=[lead.id]) if hasattr(mgr, 'role') and mgr.role == UserRole.SALES_HEAD else ''
                )
                notified_managers += 1

    # Rule 2: Inactive leads untouched past untouched_days
    recent_calls = CallHistory.objects.filter(
        call_started_at__gte=untouched_cutoff
    ).values_list('lead_id', flat=True)

    untouched_breached = Lead.objects.filter(
        assigned_telecaller__isnull=False,
        created_at__lte=untouched_cutoff
    ).exclude(status__in=terminal_statuses).exclude(id__in=recent_calls)

    for lead in list(untouched_breached.select_related('branch', 'assigned_telecaller')[:25]):
        old_tc = lead.assigned_telecaller
        branch = lead.branch
        if not branch:
            continue

        other_tcs = TelecallerLeadSetup.objects.filter(
            branch=branch,
            is_active=True,
            assignment_percentage__gt=0,
            telecaller__is_active=True
        ).exclude(telecaller=old_tc)

        if other_tcs.exists():
            success = assign_new_lead(
                lead,
                branch=branch,
                source=f"SLA Escalation ({untouched_days}d Untouched)",
                triggered_by=triggered_by,
                exclude_telecaller=old_tc
            )
            if success:
                escalated_untouched += 1
                new_tc = lead.assigned_telecaller
                if new_tc and new_tc != old_tc:
                    try:
                        create_notification(
                            recipient=new_tc,
                            title="🚨 Neglected Lead Reassigned",
                            message=f"Lead {lead.name} reassigned to you after remaining untouched for {untouched_days} days.",
                            notification_type='warning',
                            link=reverse('telecaller_lead_detail', args=[lead.id])
                        )
                    except Exception:
                        pass

    summary = {
        'escalated_fresh': escalated_fresh,
        'escalated_untouched': escalated_untouched,
        'notified_managers': notified_managers,
        'total_escalated': escalated_fresh + escalated_untouched
    }
    logger.info(f"SLA Escalation complete: {summary}")
    return summary

import logging
from django.db import transaction
from django.utils import timezone
from django.core.exceptions import ValidationError

from accounts.models import User, UserRole
from branches.models import Branch
from lead_channels.models import Channel
from activities.utils import log_activity
from .models import Lead, LeadOwnerType, TelecallerLeadSetup, LeadAssignmentHistory

logger = logging.getLogger(__name__)


def get_branch_channel_rules(branch_id, channel_id=None):
    """
    Returns active allocation rules for a specific branch and channel.
    """
    qs = TelecallerLeadSetup.objects.filter(
        branch_id=branch_id,
        is_active=True,
        telecaller__is_active=True
    ).select_related('telecaller', 'channel')
    if channel_id:
        channel_qs = qs.filter(channel_id=channel_id)
        if channel_qs.exists():
            return channel_qs
    return qs.filter(channel__isnull=True)


def validate_channel_allocation_percentages(telecaller_percentages):
    """
    Validates that a dict/list of telecaller percentages totals exactly 100%.
    Example input: [{'telecaller_id': 1, 'percentage': 50}, {'telecaller_id': 2, 'percentage': 50}]
    """
    total = 0
    clean = []
    for item in telecaller_percentages:
        tc_id = item.get('telecaller_id')
        try:
            pct = int(item.get('percentage', 0))
        except (ValueError, TypeError):
            pct = 0
        if pct < 0:
            raise ValidationError("Allocation percentages cannot be negative.")
        if pct > 0:
            total += pct
            clean.append({'telecaller_id': tc_id, 'percentage': pct})

    if total != 100:
        raise ValidationError(f"Total percentage allocation must equal exactly 100%. Current sum: {total}%.")
    return clean


@transaction.atomic
def save_branch_channel_allocation(branch, channel, allocations_data, user=None):
    """
    Saves channel-specific percentage rules for a branch.
    Input allocations_data: [{'telecaller_id': 1, 'percentage': 60}, {'telecaller_id': 2, 'percentage': 40}]
    """
    clean_items = validate_channel_allocation_percentages(allocations_data)
    eligible_tcs = User.objects.filter(
        id__in=[item['telecaller_id'] for item in clean_items],
        role=UserRole.TELECALLER,
        branch=branch,
        is_active=True
    )
    eligible_ids = set(eligible_tcs.values_list('id', flat=True))

    for item in clean_items:
        if item['telecaller_id'] not in eligible_ids:
            tc = User.objects.filter(id=item['telecaller_id']).first()
            tc_name = tc.username if tc else f"User #{item['telecaller_id']}"
            raise ValidationError(f"Telecaller '{tc_name}' is not an active telecaller for branch '{branch.name}'.")

    # Deactivate existing rules for this branch + channel
    if channel:
        TelecallerLeadSetup.objects.filter(branch=branch, channel=channel).update(is_active=False)
    else:
        TelecallerLeadSetup.objects.filter(branch=branch, channel__isnull=True).update(is_active=False)

    for item in clean_items:
        TelecallerLeadSetup.objects.update_or_create(
            branch=branch,
            channel=channel,
            telecaller_id=item['telecaller_id'],
            defaults={
                'assignment_percentage': item['percentage'],
                'channel_name': channel.name if channel else 'All Channels',
                'is_active': True
            }
        )

    chan_name = channel.name if channel else 'Default'
    if user:
        log_activity(
            user=user,
            action="Branch Allocation Updated",
            description=f"Updated lead allocation for branch '{branch.name}', channel '{chan_name}' (100% total).",
            object_type="Branch",
            object_id=branch.id
        )

    return True


@transaction.atomic
def allocate_lead_by_branch_and_channel(lead, assigned_by=None):
    """
    Deterministic percentage-based lead routing.
    1. Identifies channel & branch.
    2. Loads active TelecallerLeadSetup rules for (branch, channel).
    3. Selects telecaller with lowest ratio of current_leads_assigned vs quota weight.
    4. Records assignment, history, and updates lead.
    """
    if not lead.branch:
        lead.assignment_status = 'Pending Assignment'
        lead.save(update_fields=['assignment_status', 'updated_at'])
        return None

    channel = lead.channel
    if not channel and lead.source:
        channel = Channel.objects.filter(name__iexact=lead.source, status='Active').first()

    # Query rules for branch + channel
    rules = list(TelecallerLeadSetup.objects.filter(
        branch=lead.branch,
        channel=channel,
        is_active=True,
        telecaller__is_active=True
    ).select_related('telecaller'))

    # Fallback to general branch rules if no channel-specific rule exists
    if not rules:
        rules = list(TelecallerLeadSetup.objects.filter(
            branch=lead.branch,
            channel__isnull=True,
            is_active=True,
            telecaller__is_active=True
        ).select_related('telecaller'))

    if not rules:
        lead.assignment_status = 'Pending Assignment'
        lead.pending_assignment_reason = f"No active lead allocation rules for branch '{lead.branch.name}'."
        lead.save(update_fields=['assignment_status', 'pending_assignment_reason', 'updated_at'])
        return None

    # Deterministic selection based on assignment percentage weight and current assigned leads
    # Sort by ratio: current_assigned / percentage (lowest ratio receives the next lead)
    def sort_key(rule):
        weight = max(1, rule.assignment_percentage)
        ratio = rule.current_leads_assigned / weight
        return (ratio, rule.current_leads_assigned, rule.id)

    rules.sort(key=sort_key)
    selected_rule = rules[0]
    selected_telecaller = selected_rule.telecaller

    # Assign lead
    old_telecaller = lead.assigned_telecaller
    lead.assigned_telecaller = selected_telecaller
    lead.current_owner_type = LeadOwnerType.TELECALLER
    lead.assignment_status = 'Assigned'
    lead.assigned_at = timezone.now()
    lead.pending_assignment_reason = ''
    lead.save(update_fields=['assigned_telecaller', 'current_owner_type', 'assignment_status', 'assigned_at', 'pending_assignment_reason', 'updated_at'])

    # Increment counter
    selected_rule.current_leads_assigned += 1
    selected_rule.save(update_fields=['current_leads_assigned', 'updated_at'])

    # Audit history
    LeadAssignmentHistory.objects.create(
        lead=lead,
        from_user=old_telecaller,
        to_user=selected_telecaller,
        from_role='TELECALLER' if old_telecaller else '',
        to_role='TELECALLER',
        branch=lead.branch,
        reason=f"Branch-Channel Percentage Rule ({selected_rule.assignment_percentage}%)",
        assigned_by=assigned_by if (assigned_by and getattr(assigned_by, 'is_authenticated', False)) else None
    )

    log_activity(
        user=assigned_by,
        action="Lead Auto-Allocated",
        description=f"Lead '{lead.name}' auto-assigned to telecaller '{selected_telecaller.username}' in branch '{lead.branch.name}'.",
        object_type="Lead",
        object_id=lead.id
    )

    return selected_telecaller

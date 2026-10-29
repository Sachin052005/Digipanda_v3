"""
Reporting & Dashboard Analytics Services
Integrates the Marketing Performance Dashboard with real TELE CRM database models,
enforcing strict role-based and branch-based permissions, aggregation optimizations,
and robust Google Sheets synchronization support.
"""

import json
import logging
from datetime import datetime, time, timedelta
import urllib.request
import urllib.error

from django.db.models import Count, Q, Avg, Sum, Min, Max
from django.utils import timezone
from django.urls import reverse

from accounts.models import User, UserRole
from accounts.permissions import get_accessible_branch_ids
from branches.models import Branch
from branches.utils import get_admin_selected_branch
from calls.models import CallHistory, CallStatus, CallOutcome
from followups.models import FollowUp, FollowUpStatus
from lead_channels.models import Channel
from leads.models import Lead, LeadStatus, LeadCategory

logger = logging.getLogger('crm')

CANONICAL_CHANNELS = [
    'Meta WhatsApp',
    'Meta Lead Form',
    'Website (Google Ad)',
    'Website (Google SEO)',
    'Instagram',
    'Google Calls',
    'Influencer',
]

CHANNEL_COLORS = {
    'Meta WhatsApp': '#25D366',
    'Meta Lead Form': '#0284c7',
    'Website (Google Ad)': '#f59e0b',
    'Website (Google SEO)': '#8b5cf6',
    'Instagram': '#ec4899',
    'Google Calls': '#06b6d4',
    'Influencer': '#6366f1',
    'Other': '#64748b',
}

GOOGLE_SHEET_ID = '1PiCtFM-k_dCz87XR0Vso2d9NImnw0P8hsNuAq2D_-zE'

CONFIGURED_SHEET_BRANCHES = [
    {'name': 'Tnagar', 'gid': '0'},
    {'name': 'Velachery', 'gid': '875342187'},
    {'name': 'CBE', 'gid': '1844546948'},
    {'name': 'OMR', 'gid': '694041727'},
    {'name': 'Porur', 'gid': '592575622'},
    {'name': 'Tambaram', 'gid': '813463373'},
    {'name': 'Anna Nagar', 'gid': '1607111616'},
    {'name': 'Kochi', 'gid': '2113729191'},
]


def resolve_canonical_channel_q(channel_name: str) -> Q:
    """
    Returns a Q filter that matches a canonical channel across both
    the lead's related Channel model and its text source field.
    """
    c = (channel_name or '').strip().lower()
    if 'whatsapp' in c:
        return Q(channel__name__icontains='whatsapp') | Q(source__icontains='whatsapp')
    elif 'meta lead' in c or 'lead form' in c or 'facebook' in c:
        return Q(channel__name__icontains='facebook') | Q(channel__name__icontains='meta') | Q(source__icontains='facebook') | Q(source__icontains='meta')
    elif 'google ad' in c:
        return Q(channel__name__icontains='google ad') | Q(source__icontains='google ad')
    elif 'google seo' in c or 'seo' in c or 'website' in c:
        return Q(channel__name__icontains='website') | Q(channel__name__icontains='seo') | Q(source__icontains='website') | Q(source__icontains='seo')
    elif 'instagram' in c:
        return Q(channel__name__icontains='instagram') | Q(source__icontains='instagram')
    elif 'google call' in c or 'call' in c:
        return Q(channel__name__icontains='google call') | Q(source__icontains='google call') | Q(source__icontains='call')
    elif 'influencer' in c:
        return Q(channel__name__icontains='influencer') | Q(source__icontains='influencer')
    return Q(channel__name__iexact=channel_name) | Q(source__iexact=channel_name)


def map_lead_to_canonical_channel(channel_name: str, source: str) -> str:
    """Classifies a lead into one of the 7 canonical channels or 'Other'."""
    val = f"{channel_name or ''} {source or ''}".strip().lower()
    if 'whatsapp' in val:
        return 'Meta WhatsApp'
    if 'facebook' in val or 'meta' in val or 'lead form' in val:
        return 'Meta Lead Form'
    if 'google ad' in val:
        return 'Website (Google Ad)'
    if 'seo' in val or 'website' in val:
        return 'Website (Google SEO)'
    if 'instagram' in val:
        return 'Instagram'
    if 'google call' in val or 'call' in val:
        return 'Google Calls'
    if 'influencer' in val:
        return 'Influencer'
    return 'Other'


def parse_date_range(date_filter: str, start_date_str: str = '', end_date_str: str = ''):
    """
    Returns (start_dt, end_dt, prev_start_dt, prev_end_dt, display_label) in local timezone.
    """
    now = timezone.localtime(timezone.now())
    today = now.date()

    if date_filter == 'today':
        start_date = today
        end_date = today
        label = "Today"
    elif date_filter == 'yesterday':
        start_date = today - timedelta(days=1)
        end_date = start_date
        label = "Yesterday"
    elif date_filter == 'this_week' or date_filter == 'week':
        # Start of current week (Monday)
        start_date = today - timedelta(days=today.weekday())
        end_date = today
        label = "This Week"
    elif date_filter == 'last_7_days':
        start_date = today - timedelta(days=6)
        end_date = today
        label = "Last 7 Days"
    elif date_filter == 'this_month' or date_filter == 'month':
        start_date = today.replace(day=1)
        end_date = today
        label = "This Month"
    elif date_filter == 'all':
        return None, None, None, None, "All Time"
    elif date_filter == 'custom' or (start_date_str and end_date_str):
        try:
            start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date()
            end_date = datetime.strptime(end_date_str, '%Y-%m-%d').date()
            if start_date > end_date:
                start_date, end_date = end_date, start_date
            label = f"{start_date.strftime('%d %b')} – {end_date.strftime('%d %b')}"
        except (ValueError, TypeError):
            start_date = today
            end_date = today
            label = "Today"
    else:
        # Default to today
        start_date = today
        end_date = today
        label = "Today"

    # Convert to datetimes (midnight to end-of-day)
    tz = timezone.get_current_timezone()
    start_dt = timezone.make_aware(datetime.combine(start_date, time.min), tz)
    end_dt = timezone.make_aware(datetime.combine(end_date, time.max), tz)

    # Compute previous period of identical day duration for trend comparisons
    num_days = (end_date - start_date).days + 1
    prev_end_date = start_date - timedelta(days=1)
    prev_start_date = prev_end_date - timedelta(days=num_days - 1)
    prev_start_dt = timezone.make_aware(datetime.combine(prev_start_date, time.min), tz)
    prev_end_dt = timezone.make_aware(datetime.combine(prev_end_date, time.max), tz)

    return start_dt, end_dt, prev_start_dt, prev_end_dt, label


def get_accessible_branches_for_user(user):
    """Returns queryset of branches the user has permission to view."""
    if not user.is_authenticated:
        return Branch.objects.none()

    if getattr(user, 'is_admin_user', False):
        return Branch.objects.filter(status='Active').order_by('name')

    if getattr(user, 'is_sales_head_user', False):
        branch_ids = get_accessible_branch_ids(user)
        return Branch.objects.filter(id__in=branch_ids, status='Active').order_by('name')

    if getattr(user, 'is_branch_head_user', False):
        if user.branch_id:
            return Branch.objects.filter(id=user.branch_id)
        return Branch.objects.none()

    if user.branch_id:
        return Branch.objects.filter(id=user.branch_id)

    return Branch.objects.none()


def get_dashboard_report_data(user, params=None):
    """
    Main aggregator computing live CRM KPI cards, channel distribution,
    branch-wise highlighted summary table, and Chart.js payloads.
    """
    params = params or {}
    date_filter = params.get('date_filter', 'today')
    start_date_str = params.get('start_date', '')
    end_date_str = params.get('end_date', '')
    branch_filter = params.get('branch', '').strip()
    channel_filter = params.get('channel', '').strip()

    start_dt, end_dt, prev_start_dt, prev_end_dt, period_label = parse_date_range(
        date_filter, start_date_str, end_date_str
    )

    # Base QuerySets scoped by role
    accessible_branches = get_accessible_branches_for_user(user)
    accessible_branch_ids = list(accessible_branches.values_list('id', flat=True))

    leads_qs = Lead.objects.all()
    calls_qs = CallHistory.objects.all()

    if not getattr(user, 'is_admin_user', False):
        leads_qs = leads_qs.filter(Q(branch_id__in=accessible_branch_ids) | Q(assigned_sales_head=user) | Q(assigned_telecaller=user) | Q(assigned_counselor=user))
        calls_qs = calls_qs.filter(Q(lead__branch_id__in=accessible_branch_ids) | Q(caller=user) | Q(telecaller=user) | Q(manager=user))

    # Apply Branch Filter
    selected_admin_branch = get_admin_selected_branch(user) if hasattr(user, 'session') else None
    effective_branch_id = branch_filter or (str(selected_admin_branch.id) if selected_admin_branch else '')

    if effective_branch_id and effective_branch_id.isdigit():
        b_id = int(effective_branch_id)
        if getattr(user, 'is_admin_user', False) or b_id in accessible_branch_ids:
            leads_qs = leads_qs.filter(branch_id=b_id)
            calls_qs = calls_qs.filter(lead__branch_id=b_id)

    # Apply Channel Filter
    if channel_filter:
        channel_q = resolve_canonical_channel_q(channel_filter)
        leads_qs = leads_qs.filter(channel_q)
        calls_qs = calls_qs.filter(lead__in=Lead.objects.filter(channel_q))

    # Current period filter
    if start_dt and end_dt:
        current_leads_qs = leads_qs.filter(created_at__range=(start_dt, end_dt))
        current_calls_qs = calls_qs.filter(call_started_at__range=(start_dt, end_dt))
    else:
        current_leads_qs = leads_qs
        current_calls_qs = calls_qs

    # Previous period comparison for Total Leads Trend
    if prev_start_dt and prev_end_dt:
        prev_leads_count = leads_qs.filter(created_at__range=(prev_start_dt, prev_end_dt)).count()
    else:
        prev_leads_count = 0

    total_leads = current_leads_qs.count()

    if prev_leads_count > 0:
        total_change_pct = round(((total_leads - prev_leads_count) / prev_leads_count) * 100)
    elif total_leads > 0 and prev_leads_count == 0:
        total_change_pct = 100
    else:
        total_change_pct = 0

    # KPI 1: Connected / Contacted Leads
    connected_q = Q(status__in=[LeadStatus.CONTACTED, LeadStatus.INTERESTED, LeadStatus.DISCUSSION])
    connected_leads = current_leads_qs.filter(connected_q).count()
    connected_pct = round((connected_leads / total_leads * 100)) if total_leads > 0 else 0

    # KPI 2: Prospected / Converted / Follow-up Leads
    prospected_q = Q(status__in=[LeadStatus.CONVERTED, LeadStatus.FOLLOW_UP, LeadStatus.DEMO_SCHEDULED, LeadStatus.INSTITUTE_VISIT, LeadStatus.VISITED, LeadStatus.JOINED])
    prospected_leads = current_leads_qs.filter(prospected_q).count()
    prospected_pct = round((prospected_leads / total_leads * 100)) if total_leads > 0 else 0

    # KPI 3: Call not connected / Missed Leads
    not_connected_q = Q(status__in=[LeadStatus.NO_ANSWER, LeadStatus.BUSY, LeadStatus.LOST, LeadStatus.NOT_INTERESTED])
    not_connected_leads = current_leads_qs.filter(not_connected_q).count()
    not_connected_pct = round((not_connected_leads / total_leads * 100)) if total_leads > 0 else 0

    # Detailed status metrics
    new_leads_count = current_leads_qs.filter(status=LeadStatus.NEW).count()
    converted_leads_count = current_leads_qs.filter(status=LeadStatus.CONVERTED).count()
    conversion_rate = round((converted_leads_count / total_leads * 100), 1) if total_leads > 0 else 0

    # Call metrics
    total_calls_count = current_calls_qs.count()
    completed_calls_count = current_calls_qs.filter(call_status='Completed').count()
    missed_calls_count = current_calls_qs.filter(call_status__in=['No Answer', 'Missed', 'Busy', 'Failed']).count()

    # -------------------------------------------------------------
    # 2. Leads by Channel Breakdown (7 Canonical Channels)
    # -------------------------------------------------------------
    # Fetch lead rows with channel and source for categorization
    lead_channel_data = list(current_leads_qs.values('channel__name', 'source').annotate(count=Count('id')))
    channel_counts = {c: 0 for c in CANONICAL_CHANNELS}
    other_channels_count = 0

    for item in lead_channel_data:
        c_name = item.get('channel__name') or ''
        s_name = item.get('source') or ''
        cnt = item.get('count', 0)
        canonical = map_lead_to_canonical_channel(c_name, s_name)
        if canonical in channel_counts:
            channel_counts[canonical] += cnt
        else:
            other_channels_count += cnt

    channel_cards = []
    for c in CANONICAL_CHANNELS:
        cnt = channel_counts[c]
        p = round((cnt / total_leads * 100)) if total_leads > 0 else 0
        channel_cards.append({
            'channel': c,
            'count': cnt,
            'percentage': p,
            'color': CHANNEL_COLORS.get(c, '#64748b'),
        })

    # -------------------------------------------------------------
    # 3. Branch-Wise Lead Summary Table (9 Highlighted + 3 Status Columns)
    # -------------------------------------------------------------
    # Query leads grouped by branch, channel, and status
    branch_rows = []
    branch_totals = {
        'total_leads': 0,
        'channels': [0] * len(CANONICAL_CHANNELS),
        'new_leads': 0,
        'contacted_leads': 0,
        'missed_leads': 0,
        'converted_leads': 0,
    }

    # Fetch branch summaries for all accessible branches
    for br in accessible_branches:
        br_leads_qs = current_leads_qs.filter(branch=br)
        br_total = br_leads_qs.count()

        # Categorize channels for this branch
        br_channel_items = list(br_leads_qs.values('channel__name', 'source').annotate(count=Count('id')))
        br_ch_map = {c: 0 for c in CANONICAL_CHANNELS}
        for item in br_channel_items:
            canonical = map_lead_to_canonical_channel(item.get('channel__name'), item.get('source'))
            if canonical in br_ch_map:
                br_ch_map[canonical] += item.get('count', 0)

        br_new = br_leads_qs.filter(status=LeadStatus.NEW).count()
        br_contacted = br_leads_qs.filter(status__in=[LeadStatus.CONTACTED, LeadStatus.INTERESTED, LeadStatus.DISCUSSION]).count()
        br_missed = br_leads_qs.filter(status__in=[LeadStatus.NO_ANSWER, LeadStatus.BUSY, LeadStatus.LOST, LeadStatus.NOT_INTERESTED]).count()
        br_conv = br_leads_qs.filter(status=LeadStatus.CONVERTED).count()

        channel_counts_list = [br_ch_map[c] for c in CANONICAL_CHANNELS]

        branch_rows.append({
            'branch': br.name,
            'branch_id': br.id,
            'total_leads': br_total,
            'channels': channel_counts_list,
            'new_leads': br_new,
            'contacted_leads': br_contacted,
            'missed_leads': br_missed,
            'converted_leads': br_conv,
            'conversion_rate': round((br_conv / br_total * 100), 1) if br_total > 0 else 0,
        })

        # Accumulate totals
        branch_totals['total_leads'] += br_total
        for idx, val in enumerate(channel_counts_list):
            branch_totals['channels'][idx] += val
        branch_totals['new_leads'] += br_new
        branch_totals['contacted_leads'] += br_contacted
        branch_totals['missed_leads'] += br_missed
        branch_totals['converted_leads'] += br_conv

    # Unassigned branch leads (if any)
    unassigned_leads_qs = current_leads_qs.filter(branch__isnull=True)
    unassigned_count = unassigned_leads_qs.count()
    if unassigned_count > 0:
        un_ch_items = list(unassigned_leads_qs.values('channel__name', 'source').annotate(count=Count('id')))
        un_ch_map = {c: 0 for c in CANONICAL_CHANNELS}
        for item in un_ch_items:
            canonical = map_lead_to_canonical_channel(item.get('channel__name'), item.get('source'))
            if canonical in un_ch_map:
                un_ch_map[canonical] += item.get('count', 0)

        un_new = unassigned_leads_qs.filter(status=LeadStatus.NEW).count()
        un_contacted = unassigned_leads_qs.filter(status__in=[LeadStatus.CONTACTED, LeadStatus.INTERESTED, LeadStatus.DISCUSSION]).count()
        un_missed = unassigned_leads_qs.filter(status__in=[LeadStatus.NO_ANSWER, LeadStatus.BUSY, LeadStatus.LOST, LeadStatus.NOT_INTERESTED]).count()
        un_conv = unassigned_leads_qs.filter(status=LeadStatus.CONVERTED).count()
        un_ch_list = [un_ch_map[c] for c in CANONICAL_CHANNELS]

        branch_rows.append({
            'branch': 'Unassigned',
            'branch_id': '',
            'total_leads': unassigned_count,
            'channels': un_ch_list,
            'new_leads': un_new,
            'contacted_leads': un_contacted,
            'missed_leads': un_missed,
            'converted_leads': un_conv,
            'conversion_rate': round((un_conv / unassigned_count * 100), 1) if unassigned_count > 0 else 0,
        })

        branch_totals['total_leads'] += unassigned_count
        for idx, val in enumerate(un_ch_list):
            branch_totals['channels'][idx] += val
        branch_totals['new_leads'] += un_new
        branch_totals['contacted_leads'] += un_contacted
        branch_totals['missed_leads'] += un_missed
        branch_totals['converted_leads'] += un_conv

    # -------------------------------------------------------------
    # 4. Chart 1: Leads by Channel Donut Chart
    # -------------------------------------------------------------
    donut_labels = [c['channel'] for c in channel_cards]
    donut_values = [c['count'] for c in channel_cards]
    donut_colors = [c['color'] for c in channel_cards]
    donut_percentages = [c['percentage'] for c in channel_cards]

    # -------------------------------------------------------------
    # 5. Chart 2: Branch Wise Lead Distribution Stacked Bar Chart
    # -------------------------------------------------------------
    stacked_labels = [r['branch'] for r in branch_rows]
    stacked_datasets = []
    for idx, c in enumerate(CANONICAL_CHANNELS):
        stacked_datasets.append({
            'label': c,
            'data': [r['channels'][idx] for r in branch_rows],
            'backgroundColor': CHANNEL_COLORS.get(c, '#94a3b8'),
        })

    # -------------------------------------------------------------
    # 6. Chart 3: Call Outcomes & Lead Quality Bar Chart
    # -------------------------------------------------------------
    # Query CallOutcome and CallStatus from CallHistory
    call_outcomes_raw = list(
        current_calls_qs.filter(call_outcome__isnull=False)
        .exclude(call_outcome='')
        .values('call_outcome')
        .annotate(count=Count('id'))
        .order_by('-count')
    )
    outcome_labels = []
    outcome_values = []
    outcome_percentages = []
    total_calls_with_outcome = sum(x['count'] for x in call_outcomes_raw)

    for item in call_outcomes_raw:
        outcome_labels.append(item['call_outcome'])
        cnt = item['count']
        outcome_values.append(cnt)
        outcome_percentages.append(round((cnt / total_calls_with_outcome * 100)) if total_calls_with_outcome > 0 else 0)

    # Fallback to call statuses if outcome records are empty
    if not outcome_labels:
        call_statuses_raw = list(
            current_calls_qs.values('call_status')
            .annotate(count=Count('id'))
            .order_by('-count')
        )
        total_s = sum(x['count'] for x in call_statuses_raw)
        for item in call_statuses_raw:
            outcome_labels.append(item['call_status'])
            cnt = item['count']
            outcome_values.append(cnt)
            outcome_percentages.append(round((cnt / total_s * 100)) if total_s > 0 else 0)

    if not outcome_labels:
        outcome_labels = ['No Calls Logged']
        outcome_values = [0]
        outcome_percentages = [0]

    resolved_start_date = start_dt.strftime('%Y-%m-%d') if start_dt else ''
    resolved_end_date = end_dt.strftime('%Y-%m-%d') if end_dt else ''

    report_state_payload = {
        'period_label': period_label,
        'date_filter': date_filter,
        'start_date': resolved_start_date,
        'end_date': resolved_end_date,
        'branch_filter': effective_branch_id,
        'channel_filter': channel_filter,
        'kpi_total_leads': total_leads,
        'kpi_total_change_pct': total_change_pct,
        'kpi_connected_leads': connected_leads,
        'kpi_connected_pct': connected_pct,
        'kpi_prospected_leads': prospected_leads,
        'kpi_prospected_pct': prospected_pct,
        'kpi_not_connected_leads': not_connected_leads,
        'kpi_not_connected_pct': not_connected_pct,
        'channels': channel_cards,
        'donut_chart': {
            'labels': donut_labels,
            'values': donut_values,
            'colors': donut_colors,
            'percentages': donut_percentages,
            'total': total_leads,
        },
        'stacked_chart': {
            'labels': stacked_labels,
            'datasets': stacked_datasets,
        },
        'outcomes_chart': {
            'labels': outcome_labels,
            'values': outcome_values,
            'percentages': outcome_percentages,
            'total': total_calls_count,
        },
    }
    report_state_json = json.dumps(report_state_payload)

    return {
        'period_label': period_label,
        'date_filter': date_filter,
        'start_date': resolved_start_date,
        'end_date': resolved_end_date,
        'branch_filter': effective_branch_id,
        'channel_filter': channel_filter,
        'report_state_json': report_state_json,
        'leads_url': reverse('admin_leads_list') if (getattr(user, 'is_admin_user', False) or getattr(user, 'role', '') == 'ADMIN' or getattr(user, 'is_superuser', False)) else reverse('manager_leads_list'),

        # 4 Pastel KPI Cards
        'kpi_total_leads': total_leads,
        'kpi_total_change_pct': total_change_pct,
        'kpi_connected_leads': connected_leads,
        'kpi_connected_pct': connected_pct,
        'kpi_prospected_leads': prospected_leads,
        'kpi_prospected_pct': prospected_pct,
        'kpi_not_connected_leads': not_connected_leads,
        'kpi_not_connected_pct': not_connected_pct,

        # Additional summary metrics
        'new_leads_count': new_leads_count,
        'converted_leads_count': converted_leads_count,
        'conversion_rate': conversion_rate,
        'total_calls_count': total_calls_count,
        'completed_calls_count': completed_calls_count,
        'missed_calls_count': missed_calls_count,

        # 7 Channel Cards
        'channels': channel_cards,
        'canonical_channels': CANONICAL_CHANNELS,

        # Branch Wise Summary Table
        'branch_rows': branch_rows,
        'branch_totals': branch_totals,
        'accessible_branches': accessible_branches,

        # Charts JSON payloads
        'donut_chart': {
            'labels': donut_labels,
            'values': donut_values,
            'colors': donut_colors,
            'percentages': donut_percentages,
            'total': total_leads,
        },
        'stacked_chart': {
            'labels': stacked_labels,
            'datasets': stacked_datasets,
        },
        'outcomes_chart': {
            'labels': outcome_labels,
            'values': outcome_values,
            'percentages': outcome_percentages,
            'total': total_calls_count,
        },
    }


def sync_google_sheets_data(user=None):
    """
    Server-side Google Sheets synchronization helper.
    Fetches the configured public Google Sheet tabs across all branches,
    parses row metrics, and returns summary telemetry.
    """
    results = {
        'status': 'success',
        'branches_synced': 0,
        'total_rows_parsed': 0,
        'errors': [],
    }

    for b_info in CONFIGURED_SHEET_BRANCHES:
        name = b_info['name']
        gid = b_info['gid']
        url = f"https://docs.google.com/spreadsheets/d/{GOOGLE_SHEET_ID}/export?format=csv&gid={gid}"
        try:
            req = urllib.request.Request(
                url,
                headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0.0.0 Safari/537.36'}
            )
            with urllib.request.urlopen(req, timeout=8) as resp:
                content = resp.read().decode('utf-8', errors='ignore')
                lines = [line.strip() for line in content.splitlines() if line.strip()]
                results['branches_synced'] += 1
                results['total_rows_parsed'] += len(lines)
        except Exception as e:
            logger.warning(f"Failed to fetch Google Sheet tab for branch {name} (gid={gid}): {e}")
            results['errors'].append(f"{name}: {str(e)}")

    if results['errors'] and results['branches_synced'] == 0:
        results['status'] = 'error'

    return results


# ==========================================
# TELECALLER RNR & MANAGEMENT CHARTS (REQ 10 & 13)
# ==========================================

def get_telecaller_rnr_report_data(branch_ids=None, counselor_id=None, start_dt=None, end_dt=None, search_query=None):
    """
    Computes detailed telecaller-wise RNR statistics:
    - total calls
    - connected calls
    - RNR calls
    - unique RNR leads (distinct leads with >=1 RNR call)
    - repeat RNR leads (distinct leads with >=2 RNR calls)
    - average attempts per RNR lead
    - connection rate & RNR rate
    """
    rnr_call_q = Q(call_outcome__in=['RNR', 'No Answer', 'Busy']) | Q(call_status__in=['No Answer', 'Busy', 'Missed', 'Failed'])

    telecallers_qs = User.objects.filter(role=UserRole.TELECALLER).select_related('branch', 'counselor')

    if branch_ids is not None:
        telecallers_qs = telecallers_qs.filter(branch_id__in=branch_ids)

    if counselor_id:
        telecallers_qs = telecallers_qs.filter(counselor_id=counselor_id)

    if search_query:
        telecallers_qs = telecallers_qs.filter(
            Q(username__icontains=search_query) |
            Q(first_name__icontains=search_query) |
            Q(last_name__icontains=search_query) |
            Q(phone__icontains=search_query)
        )

    date_filter = Q()
    if start_dt and end_dt:
        date_filter = Q(call_started_at__range=(start_dt, end_dt))

    # Overall aggregates across all matching telecallers (no duplicate lead inflation)
    all_filtered_calls = CallHistory.objects.filter(
        Q(caller__in=telecallers_qs) | Q(telecaller__in=telecallers_qs)
    ).filter(date_filter).distinct()

    overall_total_calls = all_filtered_calls.count()
    overall_connected_calls = all_filtered_calls.filter(duration__gt=0).exclude(rnr_call_q).count()
    overall_rnr_calls_qs = all_filtered_calls.filter(rnr_call_q)
    overall_rnr_calls = overall_rnr_calls_qs.count()

    # Distinct leads with at least 1 RNR call across the filtered call set
    overall_unique_rnr_leads = overall_rnr_calls_qs.filter(lead__isnull=False).values('lead_id').distinct().count()

    # Distinct leads with at least 2 RNR calls across the filtered call set
    overall_repeat_rnr_leads = (
        overall_rnr_calls_qs.filter(lead__isnull=False)
        .values('lead_id')
        .annotate(c=Count('id'))
        .filter(c__gte=2)
        .count()
    )

    report_rows = []
    for tc in telecallers_qs:
        tc_calls = CallHistory.objects.filter(Q(caller=tc) | Q(telecaller=tc)).filter(date_filter)
        total_calls = tc_calls.count()
        rnr_calls_qs = tc_calls.filter(rnr_call_q)
        rnr_calls = rnr_calls_qs.count()
        connected_calls = tc_calls.filter(duration__gt=0).exclude(rnr_call_q).count()

        unique_rnr_lead_ids = set(rnr_calls_qs.filter(lead__isnull=False).values_list('lead_id', flat=True))
        unique_rnr_leads = len(unique_rnr_lead_ids)

        repeat_rnr_leads = 0
        if unique_rnr_leads > 0:
            lead_counts = rnr_calls_qs.filter(lead__isnull=False).values('lead_id').annotate(c=Count('id')).filter(c__gte=2)
            repeat_rnr_leads = lead_counts.count()

        avg_attempts_per_rnr = round(rnr_calls / unique_rnr_leads, 1) if unique_rnr_leads > 0 else 0.0
        connection_rate = round((connected_calls / total_calls) * 100, 1) if total_calls > 0 else 0.0
        rnr_rate = round((rnr_calls / total_calls) * 100, 1) if total_calls > 0 else 0.0

        report_rows.append({
            'telecaller': tc,
            'total_calls': total_calls,
            'connected_calls': connected_calls,
            'rnr_calls': rnr_calls,
            'unique_rnr_leads': unique_rnr_leads,
            'repeat_rnr_leads': repeat_rnr_leads,
            'avg_attempts_per_rnr': avg_attempts_per_rnr,
            'connection_rate': connection_rate,
            'rnr_rate': rnr_rate,
        })

    report_rows.sort(key=lambda r: r['total_calls'], reverse=True)

    summary = {
        'total_telecallers': len(report_rows),
        'overall_total_calls': overall_total_calls,
        'overall_connected_calls': overall_connected_calls,
        'overall_rnr_calls': overall_rnr_calls,
        'overall_unique_rnr_leads': overall_unique_rnr_leads,
        'overall_repeat_rnr_leads': overall_repeat_rnr_leads,
        'overall_avg_attempts_per_rnr': round(overall_rnr_calls / overall_unique_rnr_leads, 1) if overall_unique_rnr_leads > 0 else 0.0,
        'overall_connection_rate': round((overall_connected_calls / overall_total_calls) * 100, 1) if overall_total_calls > 0 else 0.0,
        'overall_rnr_rate': round((overall_rnr_calls / overall_total_calls) * 100, 1) if overall_total_calls > 0 else 0.0,
    }

    return {
        'rows': report_rows,
        'summary': summary,
    }


def get_telecaller_rnr_lead_details(detail_type='unique_rnr', branch_ids=None, counselor_id=None,
                                    start_dt=None, end_dt=None, search_query=None, telecaller_id=None,
                                    lead_search=None):
    """
    Returns distinct leads with RNR attempts for drilldown modal and CSV export (Module 2).
    - detail_type: 'unique_rnr' (>= 1 RNR call) or 'repeat_rnr' (>= 2 RNR calls)
    - avoids N+1 queries, aggregates attempt metrics, and formats call history
    """
    from leads.models import Lead
    rnr_call_q = Q(call_outcome__in=['RNR', 'No Answer', 'Busy']) | Q(call_status__in=['No Answer', 'Busy', 'Missed', 'Failed'])

    telecallers_qs = User.objects.filter(role=UserRole.TELECALLER)
    if branch_ids is not None:
        telecallers_qs = telecallers_qs.filter(branch_id__in=branch_ids)
    if counselor_id:
        telecallers_qs = telecallers_qs.filter(counselor_id=counselor_id)
    if telecaller_id:
        telecallers_qs = telecallers_qs.filter(id=telecaller_id)
    if search_query:
        telecallers_qs = telecallers_qs.filter(
            Q(username__icontains=search_query) |
            Q(first_name__icontains=search_query) |
            Q(last_name__icontains=search_query) |
            Q(phone__icontains=search_query)
        )

    date_filter = Q()
    if start_dt and end_dt:
        date_filter = Q(call_started_at__range=(start_dt, end_dt))

    calls_base_qs = CallHistory.objects.filter(
        Q(caller__in=telecallers_qs) | Q(telecaller__in=telecallers_qs)
    ).filter(date_filter).filter(lead__isnull=False).distinct()

    rnr_calls_qs = calls_base_qs.filter(rnr_call_q)

    min_attempts = 2 if detail_type == 'repeat_rnr' else 1
    lead_rnr_agg = (
        rnr_calls_qs.order_by().values('lead_id')
        .annotate(
            rnr_count=Count('id'),
            first_rnr_at=Min('call_started_at'),
            latest_rnr_at=Max('call_started_at')
        )
        .filter(rnr_count__gte=min_attempts)
    )

    lead_meta_map = {item['lead_id']: item for item in lead_rnr_agg}
    target_lead_ids = list(lead_meta_map.keys())

    if not target_lead_ids:
        return {
            'leads': [],
            'total_count': 0,
            'detail_type': detail_type,
            'title': 'Repeat RNR Leads (>= 2 Attempts)' if detail_type == 'repeat_rnr' else 'Unique RNR Leads',
        }

    leads_qs = Lead.objects.filter(id__in=target_lead_ids).select_related('branch', 'assigned_telecaller', 'assigned_counselor')

    if lead_search:
        lead_search = lead_search.strip()
        leads_qs = leads_qs.filter(
            Q(name__icontains=lead_search) |
            Q(phone__icontains=lead_search) |
            Q(email__icontains=lead_search)
        )

    # Total calls in filtered period per lead
    total_calls_agg = (
        calls_base_qs.filter(lead_id__in=target_lead_ids)
        .order_by()
        .values('lead_id')
        .annotate(total_count=Count('id'))
    )
    total_calls_map = {item['lead_id']: item['total_count'] for item in total_calls_agg}

    # Calls in period for these leads (ordered by call_started_at)
    recent_calls = (
        calls_base_qs.filter(lead_id__in=target_lead_ids)
        .select_related('caller', 'telecaller')
        .order_by('call_started_at')
    )
    calls_by_lead = {}
    for c in recent_calls:
        caller_label = 'System'
        if c.caller:
            caller_label = c.caller.get_full_name() or c.caller.username
        elif c.telecaller:
            caller_label = c.telecaller.get_full_name() or c.telecaller.username

        calls_by_lead.setdefault(c.lead_id, []).append({
            'id': c.id,
            'caller_name': caller_label,
            'call_started_at': c.call_started_at.strftime('%Y-%m-%d %H:%M:%S') if c.call_started_at else '',
            'duration_formatted': c.formatted_duration,
            'duration': c.duration,
            'call_status': c.call_status,
            'call_outcome': c.call_outcome,
            'notes': c.notes or '',
        })

    lead_items = []
    for lead in leads_qs:
        meta = lead_meta_map.get(lead.id, {})
        lead_calls = calls_by_lead.get(lead.id, [])
        latest_call = lead_calls[-1] if lead_calls else None

        first_rnr_str = meta.get('first_rnr_at').strftime('%Y-%m-%d %H:%M') if meta.get('first_rnr_at') else ''
        latest_rnr_str = meta.get('latest_rnr_at').strftime('%Y-%m-%d %H:%M') if meta.get('latest_rnr_at') else ''

        assigned_tc_name = 'Unassigned'
        if lead.assigned_telecaller:
            assigned_tc_name = lead.assigned_telecaller.get_full_name() or lead.assigned_telecaller.username

        assigned_c_name = 'Unassigned'
        if lead.assigned_counselor:
            assigned_c_name = lead.assigned_counselor.get_full_name() or lead.assigned_counselor.username

        lead_items.append({
            'lead_id': lead.id,
            'name': lead.name or 'Unknown',
            'phone': lead.phone or '',
            'masked_phone': lead.masked_phone,
            'email': lead.email or '',
            'branch_name': lead.branch.name if lead.branch else 'General',
            'assigned_telecaller_name': assigned_tc_name,
            'assigned_counselor_name': assigned_c_name,
            'status': lead.status,
            'rnr_count': meta.get('rnr_count', 0),
            'total_calls_count': total_calls_map.get(lead.id, meta.get('rnr_count', 0)),
            'first_rnr_at': first_rnr_str,
            'latest_rnr_at': latest_rnr_str,
            'latest_call_outcome': latest_call['call_outcome'] if latest_call else 'RNR',
            'latest_call_status': latest_call['call_status'] if latest_call else 'No Answer',
            'calls_history': lead_calls,
        })

    lead_items.sort(key=lambda x: (x['rnr_count'], x['latest_rnr_at']), reverse=True)

    return {
        'leads': lead_items,
        'total_count': len(lead_items),
        'detail_type': detail_type,
        'title': 'Repeat RNR Leads (>= 2 Attempts)' if detail_type == 'repeat_rnr' else 'Unique RNR Leads',
    }


def get_management_chart_data(branch_ids=None, start_dt=None, end_dt=None):
    """
    Returns structured JSON data for management charts (Req 13):
    1. Status distribution (pie/doughnut)
    2. Training vs Placement category distribution (doughnut)
    3. Telecaller RNR vs Connected call performance (bar)
    4. Counselor Lead Volume and Conversions (bar)
    """
    leads_qs = Lead.objects.all()
    calls_qs = CallHistory.objects.all()

    if branch_ids is not None:
        leads_qs = leads_qs.filter(branch_id__in=branch_ids)
        calls_qs = calls_qs.filter(lead__branch_id__in=branch_ids)

    if start_dt and end_dt:
        leads_qs = leads_qs.filter(created_at__range=(start_dt, end_dt))
        calls_qs = calls_qs.filter(call_started_at__range=(start_dt, end_dt))

    # 1. Status Distribution
    status_counts = leads_qs.values('status').annotate(count=Count('id')).order_by('-count')
    status_labels = [item['status'] for item in status_counts]
    status_data = [item['count'] for item in status_counts]

    # 2. Category Distribution (Training vs Placement)
    training_count = leads_qs.filter(category=LeadCategory.TRAINING).count()
    placement_count = leads_qs.filter(category=LeadCategory.PLACEMENT).count()

    # 3. Telecaller Performance Bar Chart (Top 8 telecallers)
    rnr_call_q = Q(call_outcome__in=['RNR', 'No Answer', 'Busy']) | Q(call_status__in=['No Answer', 'Busy', 'Missed', 'Failed'])
    telecallers = User.objects.filter(role=UserRole.TELECALLER)
    if branch_ids is not None:
        telecallers = telecallers.filter(branch_id__in=branch_ids)

    tc_labels = []
    tc_connected = []
    tc_rnr = []
    for tc in telecallers[:8]:
        tc_calls = calls_qs.filter(Q(caller=tc) | Q(telecaller=tc))
        tot = tc_calls.count()
        if tot > 0:
            tc_labels.append(tc.get_full_name() or tc.username)
            conn = tc_calls.filter(duration__gt=0).exclude(rnr_call_q).count()
            rnr = tc_calls.filter(rnr_call_q).count()
            tc_connected.append(conn)
            tc_rnr.append(rnr)

    # 4. Counselor Lead Volume and Conversions (Top 8 counselors)
    counselors = User.objects.filter(role=UserRole.COUNSELOR)
    if branch_ids is not None:
        counselors = counselors.filter(branch_id__in=branch_ids)

    c_labels = []
    c_leads = []
    c_joined = []
    for c in counselors[:8]:
        c_leads_qs = leads_qs.filter(assigned_counselor=c)
        tot = c_leads_qs.count()
        if tot > 0:
            c_labels.append(c.get_full_name() or c.username)
            c_leads.append(tot)
            c_joined.append(c_leads_qs.filter(status__in=[LeadStatus.JOINED, LeadStatus.ENROLLED]).count())

    return {
        'status_chart': {
            'labels': status_labels,
            'data': status_data,
        },
        'category_chart': {
            'labels': ['Training', 'Placement'],
            'data': [training_count, placement_count],
        },
        'telecaller_chart': {
            'labels': tc_labels,
            'connected': tc_connected,
            'rnr': tc_rnr,
        },
        'counselor_chart': {
            'labels': c_labels,
            'leads': c_leads,
            'joined': c_joined,
        }
    }


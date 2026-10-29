from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth.forms import SetPasswordForm
from django.core.exceptions import PermissionDenied
from django.db.models import Count, Q, Max, Sum
from django.core.paginator import Paginator
from django.utils import timezone

from accounts.models import User, UserRole
from accounts.permissions import admin_required, counselor_required, role_required, get_accessible_branch_ids
from branches.models import Branch
from leads.models import Lead, LeadStatus, LeadCategory, PaymentTransaction, PaymentTransactionStatus
from leads.handoff_service import reassign_lead, unassign_lead
from followups.models import FollowUp, FollowUpStatus
from calls.models import CallHistory, CallOutcome, CallStatus
from datetime import datetime, timedelta, time
from activities.models import Activity
from activities.utils import log_activity
from branch_heads.views import _counselor_context
from accounts.services import send_user_welcome_email
from .forms import AdminCounselorCreateForm


# ==========================================
# COUNSELOR: OWN PORTAL
# ==========================================

@counselor_required
def counselor_dashboard(request):
    counselor = request.user

    from leads.utils_date_filter import extract_normalized_date_range
    _date_info = extract_normalized_date_range(request, default_period='all')
    start_date = _date_info['start_date']
    end_date = _date_info['end_date']
    period = _date_info['period']
    today = timezone.localdate()
    start_dt = _date_info['start_dt']
    end_dt = _date_info['end_dt']

    from leads.services import get_user_assigned_leads
    my_leads = get_user_assigned_leads(counselor)
    if start_dt and end_dt:
        my_leads = my_leads.filter(created_at__range=(start_dt, end_dt))

    my_leads_count = my_leads.count()
    visits_count = my_leads.filter(status=LeadStatus.VISITED).count()
    counseling_count = my_leads.filter(status=LeadStatus.COUNSELING).count()
    joined_count = my_leads.filter(status__in=[LeadStatus.JOINED, LeadStatus.ENROLLED]).count()

    followups_qs = FollowUp.objects.filter(
        Q(lead__in=my_leads) | Q(assigned_user=counselor),
        status=FollowUpStatus.PENDING
    ).distinct()
    if start_dt and end_dt:
        followups_qs = followups_qs.filter(follow_up_date__range=(start_dt.date(), end_dt.date()))
    pending_followups_count = followups_qs.count()

    status_counts = my_leads.values('status').annotate(total=Count('id'))
    status_dict = {item['status']: item['total'] for item in status_counts}

    telecallers = User.objects.filter(role=UserRole.TELECALLER, counselor=counselor)

    # Payments originally recorded by this counselor that were rejected and require revision
    rejected_payments = PaymentTransaction.objects.filter(
        recorded_by=counselor,
        status=PaymentTransactionStatus.REJECTED
    ).select_related(
        'enrollment', 'enrollment__product', 'enrollment__branch', 'reviewed_by'
    ).order_by('-reviewed_at', '-updated_at')
    rejected_payments_count = rejected_payments.count()

    recent_activities = Activity.objects.filter(user=counselor).select_related('user')[:8]
    recent_leads = my_leads.select_related('channel', 'product', 'branch').order_by('-updated_at')[:8]

    return render(request, 'counselor_dashboard/dashboard.html', {
        'period': period,
        'start_date': start_date,
        'end_date': end_date,
        'my_leads_count': my_leads_count,
        'visits_count': visits_count,
        'counseling_count': counseling_count,
        'joined_count': joined_count,
        'pending_followups_count': pending_followups_count,
        'status_dict': status_dict,
        'telecallers_count': telecallers.count(),
        'rejected_payments': rejected_payments,
        'rejected_payments_count': rejected_payments_count,
        'recent_activities': recent_activities,
        'recent_leads': recent_leads,
    })


@counselor_required
def counselor_telecallers_list(request):
    counselor = request.user
    telecallers = User.get_telecallers_queryset().filter(counselor=counselor)
    if counselor.branch_id:
        telecallers = telecallers.filter(branch_id=counselor.branch_id)

    telecallers = telecallers.annotate(
        lead_count=Count('telecaller_leads', distinct=True),
        call_count=Count('telecaller_calls', distinct=True),
        followup_count=Count('telecaller_followups', distinct=True)
    ).order_by('-date_joined')

    return render(request, 'counselor/telecallers_list.html', {
        'telecallers': telecallers
    })


@counselor_required
def counselor_telecaller_leads(request, pk):
    """
    Leads assigned to one of the logged-in Counselor's own Telecallers.
    Filters strictly by Telecaller + Counselor + Branch.
    """
    counselor = request.user
    tc_qs = User.get_telecallers_queryset().filter(counselor=counselor)
    if counselor.branch_id:
        tc_qs = tc_qs.filter(branch_id=counselor.branch_id)

    telecaller = get_object_or_404(tc_qs, pk=pk)

    # Strictly filter leads by assigned_telecaller AND branch
    leads = Lead.objects.filter(assigned_telecaller=telecaller)
    if counselor.branch_id:
        leads = leads.filter(branch_id=counselor.branch_id)
    leads = leads.select_related('channel', 'product', 'branch').order_by('-updated_at')

    # Eligible alternative telecallers under same counselor and branch
    other_telecallers = User.get_telecallers_queryset().filter(
        counselor=counselor, is_active=True
    )
    if counselor.branch_id:
        other_telecallers = other_telecallers.filter(branch_id=counselor.branch_id)
    other_telecallers = other_telecallers.exclude(pk=telecaller.pk)

    return render(request, 'counselor/telecaller_leads.html', {
        'telecaller': telecaller,
        'leads': leads,
        'other_telecallers': other_telecallers,
    })


@counselor_required
def counselor_lead_reassign(request, lead_pk):
    """
    Reassigns a lead from one of the Counselor's own Telecallers to another eligible telecaller.
    Enforces server-side security: Lead must belong to counselor's supervision and branch.
    Target telecaller must belong to counselor and same branch.
    Creates LeadAssignmentHistory.
    """
    counselor = request.user
    lead = get_object_or_404(Lead, pk=lead_pk)

    if not lead.assigned_telecaller_id or lead.assigned_telecaller.counselor_id != counselor.id:
        raise PermissionDenied("This lead is not under one of your Telecallers.")
    if counselor.branch_id and lead.branch_id and lead.branch_id != counselor.branch_id:
        raise PermissionDenied("This lead belongs to a different branch.")

    current_telecaller_pk = lead.assigned_telecaller_id

    if request.method == 'POST':
        target_id = request.POST.get('telecaller_id', '').strip()
        eligible_qs = User.get_telecallers_queryset().filter(
            counselor=counselor, is_active=True
        )
        if counselor.branch_id:
            eligible_qs = eligible_qs.filter(branch_id=counselor.branch_id)

        target = eligible_qs.filter(pk=target_id).first() if target_id.isdigit() else None
        if not target:
            messages.error(request, "Select a valid, active Telecaller under your supervision.")
            return redirect('counselor_telecaller_leads', pk=current_telecaller_pk)

        reassign_lead(
            lead, to_user=target, to_role='TELECALLER',
            reason=f'Reassigned by Counselor {counselor.username}', assigned_by=counselor
        )
        log_activity(
            user=counselor,
            action="Lead Reassigned",
            description=f"Counselor reassigned lead '{lead.name}' from Telecaller to '{target.get_full_name() or target.username}'.",
            object_type="Lead",
            object_id=lead.pk,
            request=request
        )
        messages.success(request, f"Lead '{lead.name}' reassigned to '{target.get_full_name() or target.username}'.")
        return redirect('counselor_telecaller_leads', pk=target.pk)

    return redirect('counselor_telecaller_leads', pk=current_telecaller_pk)


@counselor_required
def counselor_lead_unassign(request, lead_pk):
    """
    Unassigns a lead from one of the Counselor's own Telecallers.
    The lead returns to 'Pending Assignment' with LeadAssignmentHistory created.
    """
    counselor = request.user
    lead = get_object_or_404(Lead, pk=lead_pk)

    if not lead.assigned_telecaller_id or lead.assigned_telecaller.counselor_id != counselor.id:
        raise PermissionDenied("This lead is not under one of your Telecallers.")
    if counselor.branch_id and lead.branch_id and lead.branch_id != counselor.branch_id:
        raise PermissionDenied("This lead belongs to a different branch.")

    current_telecaller_pk = lead.assigned_telecaller_id

    if request.method == 'POST':
        unassign_lead(lead, unassigned_by=counselor, reason=f'Unassigned by Counselor {counselor.username}')
        log_activity(
            user=counselor,
            action="Lead Unassigned",
            description=f"Counselor unassigned lead '{lead.name}' from its Telecaller.",
            object_type="Lead",
            object_id=lead.pk,
            request=request
        )
        messages.success(request, f"Lead '{lead.name}' has been unassigned and is pending reassignment.")
        return redirect('counselor_telecaller_leads', pk=current_telecaller_pk)

    return redirect('counselor_telecaller_leads', pk=current_telecaller_pk)



# ==========================================
# ADMIN: COUNSELOR OVERSIGHT (ALL BRANCHES)
# ==========================================

@admin_required
def admin_counselors_list(request):
    search_query = request.GET.get('search', '').strip()
    status_filter = request.GET.get('status', '').strip()
    branch_filter = request.GET.get('branch', '').strip()

    counselors_qs = User.objects.filter(role=UserRole.COUNSELOR).select_related('branch')

    if search_query:
        counselors_qs = counselors_qs.filter(
            Q(username__icontains=search_query) |
            Q(first_name__icontains=search_query) |
            Q(last_name__icontains=search_query) |
            Q(email__icontains=search_query) |
            Q(phone__icontains=search_query)
        )
    if status_filter == 'active':
        counselors_qs = counselors_qs.filter(is_active=True)
    elif status_filter == 'inactive':
        counselors_qs = counselors_qs.filter(is_active=False)
    if branch_filter:
        counselors_qs = counselors_qs.filter(branch_id=branch_filter)

    counselors_qs = counselors_qs.annotate(
        telecaller_count=Count('assigned_telecallers', distinct=True),
        lead_count=Count('counselor_leads', distinct=True),
    ).order_by('-date_joined')

    paginator = Paginator(counselors_qs, 12)
    page_obj = paginator.get_page(request.GET.get('page'))

    return render(request, 'admin/counselors_list.html', {
        'page_obj': page_obj,
        'branches': Branch.objects.filter(status='Active'),
        'search_query': search_query,
        'status_filter': status_filter,
        'branch_filter': branch_filter,
    })


@admin_required
def admin_counselor_create(request):
    allowed_branches = Branch.objects.filter(status='Active')
    if request.method == 'POST':
        form = AdminCounselorCreateForm(request.POST, allowed_branches=allowed_branches)
        if form.is_valid():
            counselor = form.save()
            log_activity(
                user=request.user,
                action="Counselor Created",
                description=f"Admin created Counselor account '{counselor.username}' for branch '{counselor.branch.name}'.",
                object_type="User",
                object_id=counselor.pk,
                request=request
            )
            email_sent, email_msg = send_user_welcome_email(counselor, request=request)
            if email_sent:
                messages.success(request, f"Counselor '{counselor.username}' created successfully. A welcome email has been sent to {counselor.email}.")
            else:
                messages.warning(request, f"Counselor '{counselor.username}' created successfully, but the welcome email could not be sent ({email_msg}). Please retry sending the invitation.")
            return redirect('admin_counselors_list')
    else:
        form = AdminCounselorCreateForm(allowed_branches=allowed_branches)

    return render(request, 'admin/counselor_create.html', {'form': form})


@admin_required
def admin_counselor_detail(request, pk):
    counselor = get_object_or_404(User.objects.select_related('branch'), pk=pk, role=UserRole.COUNSELOR)
    branch_head = User.objects.filter(role=UserRole.BRANCH_HEAD, branch_id=counselor.branch_id).first()
    context = _counselor_context(counselor)
    context['branch_head'] = branch_head
    return render(request, 'admin/counselor_detail.html', context)


@admin_required
def admin_counselor_change_password(request, pk):
    counselor = get_object_or_404(User, pk=pk, role=UserRole.COUNSELOR)
    from accounts.permissions import can_manage_user
    if not can_manage_user(request.user, counselor):
        raise PermissionDenied("You do not have permission to manage this counselor's password.")

    if request.method == 'POST':
        form = SetPasswordForm(counselor, request.POST)
        if form.is_valid():
            form.save()
            counselor.must_change_password = False
            counselor.save(update_fields=['must_change_password'])
            log_activity(
                user=request.user,
                action="Administrator Set Password",
                description=f"Administrator '{request.user.username}' reset password for Counselor '{counselor.username}'.",
                object_type="User",
                object_id=counselor.pk,
                request=request
            )
            messages.success(request, f"Password for Counselor '{counselor.username}' has been successfully changed.")
            from activities.services import create_notification
            create_notification(
                recipient=counselor,
                title="Password Changed",
                message="Your account password was updated by the Administrator.",
                notification_type="password_changed"
            )
            return redirect('admin_counselor_detail', pk=counselor.pk)
    else:
        form = SetPasswordForm(counselor)

    return render(request, 'admin/counselor_change_password.html', {
        'form': form,
        'counselor': counselor,
    })


# ==========================================
# COUNSELOR RNR & UNPICKED RECALL QUEUES (REQ 9 & 12)
# ==========================================

@role_required(UserRole.COUNSELOR, UserRole.BRANCH_HEAD, UserRole.ADMIN, UserRole.SALES_HEAD)
def counselor_rnr_leads(request):
    """
    RNR Follow-up & 3-Call Detail History for Counselors.
    Tracks Ring No Response (RNR), unanswered calls, and callback requests.
    """
    user = request.user
    counselor_id = request.GET.get('counselor_id')

    if user.role == UserRole.COUNSELOR:
        counselor_user = user
        leads_qs = Lead.objects.filter(
            Q(assigned_counselor=user) | Q(assigned_telecaller__counselor=user)
        )
        if user.branch_id:
            leads_qs = leads_qs.filter(branch_id=user.branch_id)
    elif counselor_id and counselor_id.isdigit():
        counselor_user = get_object_or_404(User, pk=counselor_id, role=UserRole.COUNSELOR)
        if user.role == UserRole.BRANCH_HEAD and counselor_user.branch_id != user.branch_id:
            raise PermissionDenied("Counselor does not belong to your branch.")
        leads_qs = Lead.objects.filter(
            Q(assigned_counselor=counselor_user) | Q(assigned_telecaller__counselor=counselor_user)
        )
        if counselor_user.branch_id:
            leads_qs = leads_qs.filter(branch_id=counselor_user.branch_id)
    elif user.role == UserRole.BRANCH_HEAD:
        counselor_user = None
        leads_qs = Lead.objects.filter(branch_id=user.branch_id)
    else:
        counselor_user = None
        leads_qs = Lead.objects.all()

    rnr_q = Q(calls__call_outcome__in=['RNR', 'No Answer', 'Busy']) | Q(calls__call_status__in=['No Answer', 'Busy', 'Missed', 'Failed'])

    rnr_leads = leads_qs.filter(rnr_q).annotate(
        rnr_count=Count('calls', filter=rnr_q, distinct=True),
        latest_call_at=Max('calls__call_started_at')
    ).filter(rnr_count__gt=0).distinct()

    unique_rnr_count = rnr_leads.count()
    total_rnr_attempts = sum(l.rnr_count for l in rnr_leads)
    repeat_rnr_count = rnr_leads.filter(rnr_count__gte=2).count()

    today = timezone.localdate()
    overdue_recalls_count = FollowUp.objects.filter(
        lead__in=rnr_leads,
        status=FollowUpStatus.PENDING,
        follow_up_date__lt=today
    ).count()

    search_query = request.GET.get('search', '').strip()
    if search_query:
        rnr_leads = rnr_leads.filter(
            Q(name__icontains=search_query) |
            Q(phone__icontains=search_query) |
            Q(email__icontains=search_query)
        )

    branch_filter = request.GET.get('branch', '').strip()
    if branch_filter and branch_filter.isdigit():
        rnr_leads = rnr_leads.filter(branch_id=branch_filter)

    min_attempts = request.GET.get('min_attempts', '').strip()
    if min_attempts and min_attempts.isdigit():
        rnr_leads = rnr_leads.filter(rnr_count__gte=int(min_attempts))

    rnr_leads = rnr_leads.select_related('branch', 'assigned_telecaller', 'assigned_counselor').order_by('-latest_call_at', '-id')

    paginator = Paginator(rnr_leads, 15)
    page_obj = paginator.get_page(request.GET.get('page'))

    return render(request, 'counselor/rnr_leads.html', {
        'page_obj': page_obj,
        'unique_rnr_count': unique_rnr_count,
        'total_rnr_attempts': total_rnr_attempts,
        'repeat_rnr_count': repeat_rnr_count,
        'overdue_recalls_count': overdue_recalls_count,
        'counselor_user': counselor_user,
        'branches': Branch.objects.filter(status='Active'),
        'branch_filter': branch_filter,
        'search_query': search_query,
        'min_attempts': min_attempts,
    })


@role_required(UserRole.COUNSELOR, UserRole.BRANCH_HEAD, UserRole.ADMIN, UserRole.SALES_HEAD)
def counselor_unpicked_recalls(request):
    """
    Unpicked recalls & scheduled callbacks queue for Counselors.
    """
    user = request.user
    today = timezone.localdate()

    if user.role == UserRole.COUNSELOR:
        counselor_user = user
        recalls_qs = FollowUp.objects.filter(
            Q(lead__assigned_counselor=user) |
            Q(lead__assigned_telecaller__counselor=user) |
            Q(assigned_user=user)
        )
        if user.branch_id:
            recalls_qs = recalls_qs.filter(lead__branch_id=user.branch_id)
    elif user.role == UserRole.BRANCH_HEAD:
        counselor_user = None
        recalls_qs = FollowUp.objects.filter(lead__branch_id=user.branch_id)
    else:
        counselor_user = None
        recalls_qs = FollowUp.objects.all()

    recalls_qs = recalls_qs.filter(status=FollowUpStatus.PENDING)

    due_today_count = recalls_qs.filter(follow_up_date=today).count()
    overdue_count = recalls_qs.filter(follow_up_date__lt=today).count()
    upcoming_count = recalls_qs.filter(
        follow_up_date__gt=today,
        follow_up_date__lte=today + timedelta(days=7)
    ).count()
    total_recalls_count = recalls_qs.count()

    recall_type = request.GET.get('type', '').strip()
    if recall_type == 'today':
        recalls_qs = recalls_qs.filter(follow_up_date=today)
    elif recall_type == 'overdue':
        recalls_qs = recalls_qs.filter(follow_up_date__lt=today)
    elif recall_type == 'upcoming':
        recalls_qs = recalls_qs.filter(
            follow_up_date__gt=today,
            follow_up_date__lte=today + timedelta(days=7)
        )

    search_query = request.GET.get('search', '').strip()
    if search_query:
        recalls_qs = recalls_qs.filter(
            Q(lead__name__icontains=search_query) |
            Q(lead__phone__icontains=search_query)
        )

    recalls_qs = recalls_qs.select_related(
        'lead', 'lead__branch', 'lead__assigned_counselor', 'lead__assigned_telecaller', 'assigned_user'
    ).order_by('follow_up_date', 'follow_up_time')

    paginator = Paginator(recalls_qs, 15)
    page_obj = paginator.get_page(request.GET.get('page'))

    return render(request, 'counselor/unpicked_recalls.html', {
        'page_obj': page_obj,
        'due_today_count': due_today_count,
        'overdue_count': overdue_count,
        'upcoming_count': upcoming_count,
        'total_recalls_count': total_recalls_count,
        'counselor_user': counselor_user,
        'recall_type': recall_type,
        'search_query': search_query,
    })


@role_required(UserRole.ADMIN, UserRole.SALES_HEAD, UserRole.BRANCH_HEAD)
def admin_counselor_leads_drilldown(request, pk):
    """
    Lead-count drill-down for Counselor.
    Detailed lead breakdown with RNR, unattended, and conversion metrics.
    """
    counselor = get_object_or_404(User.objects.select_related('branch'), pk=pk, role=UserRole.COUNSELOR)
    user = request.user
    if user.role == UserRole.BRANCH_HEAD and counselor.branch_id != user.branch_id:
        raise PermissionDenied("Counselor does not belong to your branch.")
    if user.role == UserRole.SALES_HEAD:
        accessible_branches = get_accessible_branch_ids(user)
        if counselor.branch_id and counselor.branch_id not in accessible_branches:
            raise PermissionDenied("Counselor does not belong to your accessible branches.")

    leads_qs = Lead.objects.filter(
        Q(assigned_counselor=counselor) | Q(assigned_telecaller__counselor=counselor)
    ).distinct()

    rnr_q = Q(calls__call_outcome__in=['RNR', 'No Answer', 'Busy']) | Q(calls__call_status__in=['No Answer', 'Busy', 'Missed', 'Failed'])

    total_leads = leads_qs.count()
    unattended_leads_count = leads_qs.filter(status=LeadStatus.NEW, calls__isnull=True).count()
    rnr_leads_count = leads_qs.filter(rnr_q).distinct().count()
    joined_count = leads_qs.filter(status__in=[LeadStatus.JOINED, LeadStatus.ENROLLED]).count()
    active_engagement_count = leads_qs.filter(status__in=[LeadStatus.COUNSELING, LeadStatus.VISITED, LeadStatus.DISCUSSION, LeadStatus.CONTACTED]).count()

    annotated_qs = leads_qs.annotate(
        rnr_count=Count('calls', filter=rnr_q, distinct=True)
    )

    status_filter = request.GET.get('status', '').strip()
    category_filter = request.GET.get('category', '').strip()
    special_filter = request.GET.get('special_filter', '').strip()
    search_query = request.GET.get('search', '').strip()

    if status_filter:
        annotated_qs = annotated_qs.filter(status=status_filter)
    if category_filter:
        annotated_qs = annotated_qs.filter(category=category_filter)
    if special_filter == 'rnr':
        annotated_qs = annotated_qs.filter(rnr_count__gt=0)
    elif special_filter == 'unattended':
        annotated_qs = annotated_qs.filter(status=LeadStatus.NEW, calls__isnull=True)
    elif special_filter == 'repeat_rnr':
        annotated_qs = annotated_qs.filter(rnr_count__gte=2)

    if search_query:
        annotated_qs = annotated_qs.filter(
            Q(name__icontains=search_query) |
            Q(phone__icontains=search_query) |
            Q(email__icontains=search_query)
        )

    annotated_qs = annotated_qs.select_related(
        'branch', 'assigned_telecaller', 'assigned_counselor', 'product', 'channel'
    ).prefetch_related('calls__caller', 'calls__telecaller').order_by('-updated_at')

    paginator = Paginator(annotated_qs, 15)
    page_obj = paginator.get_page(request.GET.get('page'))

    return render(request, 'admin/counselor_leads_drilldown.html', {
        'counselor': counselor,
        'page_obj': page_obj,
        'total_leads': total_leads,
        'unattended_leads_count': unattended_leads_count,
        'rnr_leads_count': rnr_leads_count,
        'joined_count': joined_count,
        'active_engagement_count': active_engagement_count,
        'status_choices': LeadStatus.choices,
        'status_filter': status_filter,
        'category_filter': category_filter,
        'special_filter': special_filter,
        'search_query': search_query,
    })


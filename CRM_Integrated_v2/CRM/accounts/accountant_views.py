import logging
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.views.decorators.http import require_POST
from django.db.models import Q

from accounts.models import User, UserRole
from accounts.permissions import admin_required, can_manage_user
from branches.models import Branch
from activities.utils import log_activity

logger = logging.getLogger(__name__)


@admin_required
def admin_accountants_list(request):
    """
    Administrator view listing all Accountant users across branches.
    Provides branch filter, search, invitation status, and action buttons.
    """
    query = request.GET.get('q', '').strip()
    branch_id = request.GET.get('branch', '').strip()
    status_filter = request.GET.get('status', '').strip()

    accountants = User.objects.filter(role=UserRole.ACCOUNTANT).select_related('branch').order_by('-date_joined')

    if query:
        accountants = accountants.filter(
            Q(username__icontains=query) |
            Q(first_name__icontains=query) |
            Q(last_name__icontains=query) |
            Q(email__icontains=query) |
            Q(phone__icontains=query)
        )

    if branch_id and branch_id.isdigit():
        accountants = accountants.filter(branch_id=int(branch_id))

    if status_filter == 'active':
        accountants = accountants.filter(is_active=True)
    elif status_filter == 'inactive':
        accountants = accountants.filter(is_active=False)

    branches = Branch.objects.filter(status='Active')

    total_accountants = User.objects.filter(role=UserRole.ACCOUNTANT).count()
    active_accountants = User.objects.filter(role=UserRole.ACCOUNTANT, is_active=True).count()

    context = {
        'accountants': accountants,
        'branches': branches,
        'selected_branch': branch_id,
        'selected_status': status_filter,
        'search_query': query,
        'total_accountants': total_accountants,
        'active_accountants': active_accountants,
        'portal_title': 'Accountant Staff Management',
    }
    return render(request, 'admin/accountants_list.html', context)


@admin_required
@require_POST
def admin_accountant_toggle_status(request, pk):
    """
    Activates or deactivates an Accountant user account.
    """
    target_user = get_object_or_404(User, pk=pk, role=UserRole.ACCOUNTANT)

    if not can_manage_user(request.user, target_user):
        messages.error(request, "Permission denied.")
        return redirect('admin_accountants_list')

    target_user.is_active = not target_user.is_active
    target_user.save(update_fields=['is_active'])

    status_str = "activated" if target_user.is_active else "deactivated"
    log_activity(
        user=request.user,
        action=f"Accountant {status_str.title()}",
        description=f"Administrator {request.user.username} {status_str} accountant '{target_user.username}'.",
        object_type="User",
        object_id=str(target_user.pk),
        request=request
    )
    messages.success(request, f"Accountant '{target_user.username}' {status_str} successfully.")
    return redirect('admin_accountants_list')


@admin_required
def admin_accountant_detail(request, pk):
    """
    Administrator profile & verification activity detail view for an Accountant.
    Displays verified transactions, total verified sum, rejected counts, and verification queue.
    """
    from decimal import Decimal
    from django.db.models import Sum
    from leads.models import PaymentTransaction, PaymentTransactionStatus
    from activities.models import Activity

    accountant = get_object_or_404(User.objects.select_related('branch'), pk=pk, role=UserRole.ACCOUNTANT)
    branch = accountant.branch

    verified_statuses = [PaymentTransactionStatus.APPROVED, PaymentTransactionStatus.SUCCESS]
    verified_qs = PaymentTransaction.objects.filter(reviewed_by=accountant, status__in=verified_statuses)
    verified_count = verified_qs.count()
    verified_amount = verified_qs.aggregate(total=Sum('amount'))['total'] or Decimal('0.00')

    rejected_count = PaymentTransaction.objects.filter(
        reviewed_by=accountant,
        status=PaymentTransactionStatus.REJECTED
    ).count()

    # Pending queue for accountant's branch or global if unassigned
    if branch:
        pending_queue_count = PaymentTransaction.objects.filter(
            enrollment__branch=branch,
            status=PaymentTransactionStatus.PENDING_VERIFICATION
        ).count()
    else:
        pending_queue_count = PaymentTransaction.objects.filter(
            status=PaymentTransactionStatus.PENDING_VERIFICATION
        ).count()

    recent_verifications = PaymentTransaction.objects.filter(
        Q(reviewed_by=accountant) | Q(recorded_by=accountant)
    ).select_related('enrollment', 'recorded_by').order_by('-updated_at')[:10]

    recent_activities = Activity.objects.filter(user=accountant).order_by('-timestamp')[:10]

    context = {
        'accountant': accountant,
        'branch': branch,
        'verified_count': verified_count,
        'verified_amount': verified_amount,
        'rejected_count': rejected_count,
        'pending_queue_count': pending_queue_count,
        'recent_verifications': recent_verifications,
        'recent_activities': recent_activities,
    }
    return render(request, 'admin/accountant_detail.html', context)

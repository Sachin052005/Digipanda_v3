from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth.forms import SetPasswordForm
from django.core.paginator import Paginator
from django.db.models import Q
from django.views.decorators.http import require_POST

from .models import User, UserRole
from .permissions import admin_required
from .forms import AdminReceptionistCreateForm
from .services import send_user_welcome_email
from branches.models import Branch
from activities.utils import log_activity


@admin_required
def admin_receptionists_list(request):
    """Admin oversight view listing all Receptionists across branches."""
    search_query = request.GET.get('search', '').strip()
    status_filter = request.GET.get('status', '').strip()
    branch_filter = request.GET.get('branch', '').strip()

    receptionists_qs = User.objects.filter(role=UserRole.RECEPTIONIST).select_related('branch')

    if search_query:
        receptionists_qs = receptionists_qs.filter(
            Q(username__icontains=search_query) |
            Q(first_name__icontains=search_query) |
            Q(last_name__icontains=search_query) |
            Q(email__icontains=search_query) |
            Q(phone__icontains=search_query)
        )
    if status_filter == 'active':
        receptionists_qs = receptionists_qs.filter(is_active=True)
    elif status_filter == 'inactive':
        receptionists_qs = receptionists_qs.filter(is_active=False)
    if branch_filter:
        receptionists_qs = receptionists_qs.filter(branch_id=branch_filter)

    receptionists_qs = receptionists_qs.order_by('-date_joined')

    # Counters
    all_recs = User.objects.filter(role=UserRole.RECEPTIONIST)
    total_receptionists = all_recs.count()
    active_count = all_recs.filter(is_active=True).count()
    inactive_count = all_recs.filter(is_active=False).count()

    paginator = Paginator(receptionists_qs, 15)
    page_obj = paginator.get_page(request.GET.get('page'))

    return render(request, 'admin/receptionists_list.html', {
        'page_obj': page_obj,
        'branches': Branch.objects.filter(status='Active'),
        'total_receptionists': total_receptionists,
        'active_count': active_count,
        'inactive_count': inactive_count,
        'search_query': search_query,
        'status_filter': status_filter,
        'branch_filter': branch_filter,
    })


@admin_required
def admin_receptionist_create(request):
    """Admin creates a Receptionist directly with branch assignment and password options."""
    allowed_branches = Branch.objects.filter(status='Active')
    if request.method == 'POST':
        form = AdminReceptionistCreateForm(request.POST, allowed_branches=allowed_branches)
        if form.is_valid():
            receptionist = form.save()
            log_activity(
                user=request.user,
                action="Receptionist Created",
                description=f"Admin created Receptionist account '{receptionist.username}' for branch '{receptionist.branch.name if receptionist.branch else 'Unassigned'}'.",
                object_type="User",
                object_id=receptionist.pk,
                request=request
            )
            email_sent, email_msg = send_user_welcome_email(receptionist, request=request)
            if email_sent:
                messages.success(request, f"Receptionist '{receptionist.username}' created successfully. A welcome email has been sent to {receptionist.email}.")
            else:
                messages.warning(request, f"Receptionist '{receptionist.username}' created successfully, but the welcome email could not be sent ({email_msg}). Please retry sending the invitation.")
            return redirect('admin_receptionists_list')
    else:
        form = AdminReceptionistCreateForm(allowed_branches=allowed_branches)

    return render(request, 'admin/receptionist_create.html', {'form': form})


@admin_required
def admin_receptionist_change_password(request, pk):
    """Admin resets or sets a new password for a Receptionist."""
    receptionist = get_object_or_404(User, pk=pk, role=UserRole.RECEPTIONIST)
    if request.method == 'POST':
        form = SetPasswordForm(receptionist, request.POST)
        if form.is_valid():
            form.save()
            receptionist.must_change_password = False
            receptionist.save(update_fields=['must_change_password'])
            log_activity(
                user=request.user,
                action="Password Changed",
                description=f"Admin updated password for Receptionist '{receptionist.username}'.",
                object_type="User",
                object_id=receptionist.pk,
                request=request
            )
            messages.success(request, f"Password for Receptionist '{receptionist.username}' was updated successfully.")
            return redirect('admin_receptionists_list')
    else:
        form = SetPasswordForm(receptionist)

    return render(request, 'admin/receptionist_change_password.html', {
        'form': form,
        'receptionist': receptionist
    })


@admin_required
@require_POST
def admin_receptionist_toggle_status(request, pk):
    """Admin activates or deactivates a Receptionist account."""
    receptionist = get_object_or_404(User, pk=pk, role=UserRole.RECEPTIONIST)
    receptionist.is_active = not receptionist.is_active
    receptionist.save(update_fields=['is_active'])

    status_str = "activated" if receptionist.is_active else "deactivated"
    log_activity(
        user=request.user,
        action="Receptionist Status Toggled",
        description=f"Admin {status_str} Receptionist '{receptionist.username}'.",
        object_type="User",
        object_id=receptionist.pk,
        request=request
    )
    messages.success(request, f"Receptionist '{receptionist.username}' was successfully {status_str}.")
    return redirect('admin_receptionists_list')

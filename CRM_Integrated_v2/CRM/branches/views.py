from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.db.models import Count
from django.core.paginator import Paginator
from accounts.permissions import admin_required
from django.views.decorators.http import require_POST
from .models import Branch
from .forms import BranchForm
from .utils import set_admin_selected_branch
from activities.utils import log_activity

@admin_required
def admin_branches_list(request):
    search_query = request.GET.get('search', '').strip()
    status_filter = request.GET.get('status', '').strip()

    branches_qs = Branch.objects.annotate(lead_count=Count('leads'))

    if search_query:
        branches_qs = branches_qs.filter(name__icontains=search_query)
    if status_filter:
        branches_qs = branches_qs.filter(status=status_filter)

    branches_qs = branches_qs.order_by('name')
    paginator = Paginator(branches_qs, 15)
    page_obj = paginator.get_page(request.GET.get('page'))

    form = BranchForm()
    if request.method == 'POST' and request.POST.get('action') == 'create':
        form = BranchForm(request.POST)
        if form.is_valid():
            branch = form.save()
            log_activity(
                user=request.user,
                action="Branch Created",
                description=f"Created branch office: '{branch.name}'",
                object_type="Branch",
                object_id=branch.pk,
                request=request
            )
            messages.success(request, f"Branch '{branch.name}' created successfully.")
            return redirect('admin_branches_list')

    return render(request, 'admin/branches_list.html', {
        'page_obj': page_obj,
        'form': form,
        'search_query': search_query,
        'status_filter': status_filter,
    })

@admin_required
def admin_branch_edit(request, pk):
    from channels.models import Channel
    from accounts.models import User, UserRole
    from leads.models import TelecallerLeadSetup
    from leads.allocation_service import save_branch_channel_allocation
    from django.core.exceptions import ValidationError

    branch = get_object_or_404(Branch, pk=pk)

    if request.method == 'POST':
        action = request.POST.get('action', 'edit_branch')
        if action == 'save_channel_allocation':
            channel_id = request.POST.get('channel_id')
            channel = get_object_or_404(Channel, pk=channel_id) if (channel_id and str(channel_id).isdigit()) else None

            # Collect telecaller percentages for this channel
            allocations = []
            for k, v in request.POST.items():
                if k.startswith('pct_tc_'):
                    tc_id_str = k.replace('pct_tc_', '')
                    if tc_id_str.isdigit():
                        try:
                            val = int(v) if v else 0
                        except ValueError:
                            val = 0
                        if val > 0:
                            allocations.append({'telecaller_id': int(tc_id_str), 'percentage': val})

            try:
                save_branch_channel_allocation(branch, channel, allocations, user=request.user)
                chan_lbl = channel.name if channel else 'All Channels'
                msg = f"Allocation settings for channel '{chan_lbl}' saved successfully (100% total)."
                if request.headers.get('x-requested-with') == 'XMLHttpRequest' or request.content_type == 'application/json':
                    return JsonResponse({'success': True, 'message': msg})
                messages.success(request, msg)
                return redirect('admin_branch_edit', pk=branch.pk)
            except ValidationError as ve:
                err_msg = ve.message if hasattr(ve, 'message') else str(ve)
                if request.headers.get('x-requested-with') == 'XMLHttpRequest' or request.content_type == 'application/json':
                    return JsonResponse({'success': False, 'error': err_msg}, status=400)
                messages.error(request, err_msg)
            except Exception as ex:
                if request.headers.get('x-requested-with') == 'XMLHttpRequest' or request.content_type == 'application/json':
                    return JsonResponse({'success': False, 'error': str(ex)}, status=500)
                messages.error(request, str(ex))

        else:
            form = BranchForm(request.POST, instance=branch)
            if form.is_valid():
                form.save()
                log_activity(
                    user=request.user,
                    action="Branch Updated",
                    description=f"Updated branch '{branch.name}'.",
                    object_type="Branch",
                    object_id=branch.pk,
                    request=request
                )
                messages.success(request, f"Branch '{branch.name}' updated.")
                return redirect('admin_branches_list')
    else:
        form = BranchForm(instance=branch)

    # Prepare Lead Allocation Settings per Channel for this branch
    channels = list(Channel.objects.filter(status='Active').order_by('name'))
    branch_telecallers = list(User.objects.filter(role=UserRole.TELECALLER, branch=branch, is_active=True).order_by('first_name', 'username'))

    channel_allocations_data = []
    for ch in channels:
        rules = list(TelecallerLeadSetup.objects.filter(branch=branch, channel=ch, is_active=True).select_related('telecaller'))
        rules_map = {r.telecaller_id: r.assignment_percentage for r in rules}
        total_p = sum(rules_map.values())
        tc_entries = []
        for tc in branch_telecallers:
            tc_entries.append({
                'telecaller': tc,
                'percentage': rules_map.get(tc.id, 0),
                'assigned_count': next((r.current_leads_assigned for r in rules if r.telecaller_id == tc.id), 0)
            })
        channel_allocations_data.append({
            'channel': ch,
            'tc_entries': tc_entries,
            'total_percentage': total_p,
            'is_valid_100': (total_p == 100),
            'active_rules_count': len([r for r in rules if r.assignment_percentage > 0]),
        })

    return render(request, 'admin/branch_form.html', {
        'form': form,
        'branch': branch,
        'channels': channels,
        'branch_telecallers': branch_telecallers,
        'channel_allocations_data': channel_allocations_data,
    })

@admin_required
def admin_branch_toggle_status(request, pk):
    branch = get_object_or_404(Branch, pk=pk)
    old_status = branch.status
    branch.status = 'Inactive' if old_status == 'Active' else 'Active'
    branch.save()

    log_activity(
        user=request.user,
        action="Branch Status Changed",
        description=f"Branch '{branch.name}' changed from {old_status} to {branch.status}.",
        object_type="Branch",
        object_id=branch.pk,
        request=request
    )
    messages.success(request, f"Branch '{branch.name}' status is now {branch.status}.")
    return redirect('admin_branches_list')

@admin_required
@require_POST
def set_active_branch(request):
    branch_id = request.POST.get('branch_id')
    set_admin_selected_branch(request, branch_id)
    next_url = request.POST.get('next') or request.META.get('HTTP_REFERER') or 'admin_dashboard'
    return redirect(next_url)


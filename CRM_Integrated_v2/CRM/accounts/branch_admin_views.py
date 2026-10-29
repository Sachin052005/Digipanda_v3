import logging
from django import forms
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.core.exceptions import ValidationError, PermissionDenied
from django.core.paginator import Paginator
from django.db.models import Q, Count
from django.contrib.auth.forms import SetPasswordForm

from accounts.models import User, UserRole
from accounts.permissions import admin_required, can_manage_user, can_create_user
from accounts.services import generate_unique_username, send_user_welcome_email
from branches.models import Branch
from leads.models import Enrollment, Lead
from activities.utils import log_activity

logger = logging.getLogger(__name__)


class BranchAdminCreateForm(forms.ModelForm):
    branch = forms.ModelChoiceField(
        queryset=Branch.objects.none(),
        required=True,
        widget=forms.Select(attrs={'class': 'form-select'})
    )

    class Meta:
        model = User
        fields = ['first_name', 'last_name', 'username', 'email', 'phone', 'branch', 'is_active']
        widgets = {
            'first_name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'First Name'}),
            'last_name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Last Name'}),
            'username': forms.TextInput(attrs={'class': 'form-control bg-light', 'readonly': 'readonly', 'placeholder': 'Generated automatically'}),
            'email': forms.EmailInput(attrs={'class': 'form-control', 'placeholder': 'admin@branch.com'}),
            'phone': forms.TextInput(attrs={'class': 'form-control', 'placeholder': '+91 XXXXX XXXXX'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }

    def __init__(self, *args, allowed_branches=None, **kwargs):
        super().__init__(*args, **kwargs)
        if not self.instance.pk:
            self.instance.role = UserRole.BRANCH_ADMIN
            self.fields['is_active'].initial = True
        self.fields['branch'].queryset = allowed_branches if allowed_branches is not None else Branch.objects.filter(status='Active')

    def clean_username(self):
        username = (self.cleaned_data.get('username') or '').strip()
        if not username:
            first = self.cleaned_data.get('first_name') or ''
            last = self.cleaned_data.get('last_name') or ''
            email = self.cleaned_data.get('email') or ''
            username = generate_unique_username(first_name=first, last_name=last, role=UserRole.BRANCH_ADMIN, email=email)
        elif User.objects.filter(username__iexact=username).exists():
            username = generate_unique_username(first_name=username, role=UserRole.BRANCH_ADMIN)
        return username

    def clean_email(self):
        email = (self.cleaned_data.get('email') or '').strip()
        if not email:
            raise ValidationError("Email is required.")
        if User.objects.filter(email__iexact=email).exists():
            raise ValidationError("A user with this email address already exists.")
        return email

    def save(self, commit=True):
        user = super().save(commit=False)
        user.role = UserRole.BRANCH_ADMIN
        if not user.username:
            user.username = self.clean_username()
        if commit:
            user.save()
        return user


class BranchAdminEditForm(forms.ModelForm):
    branch = forms.ModelChoiceField(
        queryset=Branch.objects.none(),
        required=True,
        widget=forms.Select(attrs={'class': 'form-select'})
    )

    class Meta:
        model = User
        fields = ['first_name', 'last_name', 'email', 'phone', 'branch', 'is_active']
        widgets = {
            'first_name': forms.TextInput(attrs={'class': 'form-control'}),
            'last_name': forms.TextInput(attrs={'class': 'form-control'}),
            'email': forms.EmailInput(attrs={'class': 'form-control'}),
            'phone': forms.TextInput(attrs={'class': 'form-control'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }

    def __init__(self, *args, allowed_branches=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['branch'].queryset = allowed_branches if allowed_branches is not None else Branch.objects.filter(status='Active')


@admin_required
def admin_branch_admins_list(request):
    """
    Administrator view listing all Branch Admin accounts across all branches.
    """
    search_query = request.GET.get('search', '').strip()
    status_filter = request.GET.get('status', '').strip()
    branch_filter = request.GET.get('branch', '').strip()

    qs = User.objects.filter(role=UserRole.BRANCH_ADMIN).select_related('branch')

    if search_query:
        qs = qs.filter(
            Q(username__icontains=search_query) |
            Q(first_name__icontains=search_query) |
            Q(last_name__icontains=search_query) |
            Q(email__icontains=search_query) |
            Q(phone__icontains=search_query)
        )

    if status_filter == 'active':
        qs = qs.filter(is_active=True)
    elif status_filter == 'inactive':
        qs = qs.filter(is_active=False)

    if branch_filter and branch_filter.isdigit():
        qs = qs.filter(branch_id=int(branch_filter))

    qs = qs.annotate(
        enrolled_count=Count('branch__enrollments', distinct=True)
    ).order_by('-date_joined')

    paginator = Paginator(qs, 15)
    page_obj = paginator.get_page(request.GET.get('page'))

    total_count = User.objects.filter(role=UserRole.BRANCH_ADMIN).count()
    active_count = User.objects.filter(role=UserRole.BRANCH_ADMIN, is_active=True).count()

    return render(request, 'admin/branch_admins_list.html', {
        'page_obj': page_obj,
        'branches': Branch.objects.filter(status='Active').order_by('name'),
        'search_query': search_query,
        'status_filter': status_filter,
        'branch_filter': branch_filter,
        'total_count': total_count,
        'active_count': active_count,
        'portal_title': 'Branch Admin Management',
    })


@admin_required
def admin_branch_admin_create(request):
    """
    Onboard a new Branch Admin dedicated to a specific branch.
    Dispatches automated welcome email with account activation link.
    """
    allowed_branches = Branch.objects.filter(status='Active')
    if request.method == 'POST':
        form = BranchAdminCreateForm(request.POST, allowed_branches=allowed_branches)
        if form.is_valid():
            branch_admin = form.save()
            log_activity(
                user=request.user,
                action="Branch Admin Created",
                description=f"Admin created Branch Admin account '{branch_admin.username}' for branch '{branch_admin.branch.name}'.",
                object_type="User",
                object_id=branch_admin.pk,
                request=request
            )
            email_sent, email_msg = send_user_welcome_email(branch_admin, request=request)
            if email_sent:
                messages.success(request, f"Branch Admin '{branch_admin.username}' created successfully. A welcome email has been sent to {branch_admin.email}.")
            else:
                messages.warning(request, f"Branch Admin '{branch_admin.username}' created successfully, but welcome email could not be sent ({email_msg}). You can set password manually.")
            return redirect('admin_branch_admins_list')
    else:
        form = BranchAdminCreateForm(allowed_branches=allowed_branches)

    return render(request, 'admin/branch_admin_create.html', {
        'form': form,
        'portal_title': 'Create Branch Admin',
    })


@admin_required
def admin_branch_admin_detail(request, pk):
    branch_admin = get_object_or_404(User.objects.select_related('branch'), pk=pk, role=UserRole.BRANCH_ADMIN)
    enrolled_count = Enrollment.objects.filter(branch=branch_admin.branch).count() if branch_admin.branch else 0
    leads_count = Lead.objects.filter(branch=branch_admin.branch).count() if branch_admin.branch else 0
    return render(request, 'admin/branch_admin_detail.html', {
        'target_user': branch_admin,
        'enrolled_count': enrolled_count,
        'leads_count': leads_count,
    })


@admin_required
def admin_branch_admin_edit(request, pk):
    branch_admin = get_object_or_404(User, pk=pk, role=UserRole.BRANCH_ADMIN)
    allowed_branches = Branch.objects.filter(status='Active')
    if request.method == 'POST':
        form = BranchAdminEditForm(request.POST, instance=branch_admin, allowed_branches=allowed_branches)
        if form.is_valid():
            form.save()
            messages.success(request, f"Branch Admin '{branch_admin.username}' updated successfully.")
            return redirect('admin_branch_admins_list')
    else:
        form = BranchAdminEditForm(instance=branch_admin, allowed_branches=allowed_branches)

    return render(request, 'admin/branch_admin_edit.html', {
        'form': form,
        'target_user': branch_admin,
    })

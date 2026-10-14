from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse
from django.contrib.auth import authenticate, login, logout
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.tokens import default_token_generator
from django.contrib.auth.forms import SetPasswordForm
from django.utils.http import urlsafe_base64_decode
from django.utils.encoding import force_str
from django.core.exceptions import PermissionDenied

from .forms import LoginForm, ManagerRegistrationForm, TelecallerRegistrationForm, AdminCreateUserForm
from .models import User, UserRole
from .permissions import admin_required, can_manage_user
from .services import send_user_welcome_email, generate_unique_username, _clean_name_string
from branches.models import Branch
from activities.utils import log_activity

def login_redirect(request):
    """Smart redirect to appropriate dashboard based on user role."""
    if not request.user.is_authenticated:
        return redirect('login')
    if request.user.is_admin_user:
        return redirect('admin_dashboard')
    elif request.user.is_sales_head_user:
        return redirect('manager_dashboard')
    elif request.user.is_branch_head_user:
        return redirect('branch_head_dashboard')
    elif request.user.is_counselor_user:
        return redirect('counselor_dashboard')
    elif request.user.is_telecaller_user:
        return redirect('telecaller_dashboard')
    elif request.user.is_receptionist_user:
        return redirect('receptionist_dashboard')
    return redirect('login')

def _process_login(request, expected_role=None, template_name='registration/login.html', portal_title='CRM Login'):
    if request.user.is_authenticated:
        return login_redirect(request)

    form = LoginForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        username_input = form.cleaned_data.get('username', '').strip()
        password = form.cleaned_data.get('password')
        remember_me = form.cleaned_data.get('remember_me')

        matched_user = User.objects.filter(email__iexact=username_input).first()
        if not matched_user:
            matched_user = User.objects.filter(username__iexact=username_input).first()

        auth_username = matched_user.username if matched_user else username_input
        user = authenticate(request, username=auth_username, password=password)
        if user is not None:
            if not user.is_active:
                messages.error(request, "This account is inactive. Please contact your administrator.")
                return render(request, template_name, {'form': form, 'portal_title': portal_title, 'portal_role': expected_role})

            if expected_role:
                if expected_role == UserRole.ADMIN and not user.is_admin_user:
                    messages.error(request, f"Access denied. '{user.username}' is not registered with Admin privileges.")
                    return render(request, template_name, {'form': form, 'portal_title': portal_title, 'portal_role': expected_role})
                elif expected_role == UserRole.SALES_HEAD and not user.is_sales_head_user:
                    messages.error(request, f"Access denied. '{user.username}' is not a Sales Head.")
                    return render(request, template_name, {'form': form, 'portal_title': portal_title, 'portal_role': expected_role})
                elif expected_role == UserRole.TELECALLER and not user.is_telecaller_user:
                    messages.error(request, f"Access denied. '{user.username}' is not a Telecaller.")
                    return render(request, template_name, {'form': form, 'portal_title': portal_title, 'portal_role': expected_role})
                elif expected_role == UserRole.RECEPTIONIST and not user.is_receptionist_user:
                    messages.error(request, f"Access denied. '{user.username}' is not a Receptionist.")
                    return render(request, template_name, {'form': form, 'portal_title': portal_title, 'portal_role': expected_role})

            login(request, user)
            if not remember_me:
                request.session.set_expiry(0)  # Browser close expiration
            else:
                request.session.set_expiry(1209600)  # 2 weeks

            log_activity(
                user=user,
                action="User Logged In",
                description=f"{user.display_role} '{user.username}' logged in successfully.",
                object_type="User",
                object_id=str(user.pk),
                request=request
            )
            messages.success(request, f"Welcome back, {user.first_name or user.username}!")
            return login_redirect(request)
        else:
            messages.error(request, "Invalid username or password. Please try again.")

    return render(request, template_name, {
        'form': form,
        'portal_title': portal_title,
        'portal_role': expected_role
    })

def general_login(request):
    return _process_login(
        request,
        expected_role=None,
        template_name='registration/login.html',
        portal_title='TECHPANDA CRM Login'
    )

def admin_login(request):
    return _process_login(
        request,
        expected_role=UserRole.ADMIN,
        template_name='registration/admin_login.html',
        portal_title='Admin Secure Portal'
    )

def manager_login(request):
    return _process_login(
        request,
        expected_role=UserRole.SALES_HEAD,
        template_name='registration/manager_login.html',
        portal_title='Sales Head Portal'
    )

def telecaller_login(request):
    return _process_login(
        request,
        expected_role=UserRole.TELECALLER,
        template_name='registration/telecaller_login.html',
        portal_title='Telecaller Workspace Login'
    )

def receptionist_login(request):
    return _process_login(
        request,
        expected_role=UserRole.RECEPTIONIST,
        template_name='registration/login.html',
        portal_title='Reception Desk Login'
    )

def manager_register(request):
    if request.user.is_authenticated:
        return login_redirect(request)

    if request.method == 'POST':
        form = ManagerRegistrationForm(request.POST)
        if form.is_valid():
            user = form.save()
            log_activity(
                user=user,
                action="Sales Head Registered",
                description=f"New Sales Head account registered: '{user.username}' ({user.email}).",
                object_type="User",
                object_id=str(user.pk),
                request=request
            )
            messages.success(request, "Sales Head registration successful! You can now log in.")
            return redirect('manager_login')
    else:
        form = ManagerRegistrationForm()

    return render(request, 'registration/manager_register.html', {
        'form': form,
        'portal_title': 'Register as Sales Head'
    })

def telecaller_register(request):
    if request.user.is_authenticated:
        return login_redirect(request)

    if request.method == 'POST':
        form = TelecallerRegistrationForm(request.POST)
        if form.is_valid():
            user = form.save()
            log_activity(
                user=user,
                action="Telecaller Registered",
                description=f"New Telecaller account registered: '{user.username}' ({user.email}).",
                object_type="User",
                object_id=str(user.pk),
                request=request
            )
            messages.success(request, "Telecaller registration successful! You can now log in.")
            return redirect('telecaller_login')
    else:
        form = TelecallerRegistrationForm()

    return render(request, 'registration/telecaller_register.html', {
        'form': form,
        'portal_title': 'Register as Telecaller'
    })

@login_required
def logout_view(request):
    user = request.user
    log_activity(
        user=user,
        action="User Logged Out",
        description=f"User '{user.username}' logged out.",
        object_type="User",
        object_id=str(user.pk),
        request=request
    )
    logout(request)
    messages.info(request, "You have been logged out successfully.")
    return redirect('login')


def account_setup_view(request, uidb64, token):
    """
    Validates the secure single-use time-limited onboarding token.
    Allows new members to set their password according to Django password validators,
    activates the account, invalidates the token, and redirects to login.
    """
    try:
        uid = force_str(urlsafe_base64_decode(uidb64))
        target_user = User.objects.filter(pk=uid).first()
    except (TypeError, ValueError, OverflowError):
        target_user = None

    if not target_user or not default_token_generator.check_token(target_user, token):
        return render(request, 'registration/account_setup_invalid.html', {
            'error': 'This password setup link is invalid, expired, or has already been used.',
        })

    if request.method == 'POST':
        form = SetPasswordForm(user=target_user, data=request.POST)
        if form.is_valid():
            form.save()
            target_user.is_active = True
            target_user.must_change_password = False
            target_user.invitation_status = 'ACTIVATED'
            target_user.save(update_fields=['is_active', 'must_change_password', 'invitation_status'])

            log_activity(
                user=target_user,
                action="Account Activated",
                description=f"Member '{target_user.username}' successfully set password and activated their account.",
                object_type="User",
                object_id=str(target_user.pk),
                request=request
            )
            messages.success(request, f"Password set successfully! Your account is now active. Please sign in with your Login ID: {target_user.username}")
            return redirect('login')
    else:
        form = SetPasswordForm(user=target_user)

    return render(request, 'registration/account_setup.html', {
        'form': form,
        'target_user': target_user,
    })


@login_required
def resend_user_invitation(request, pk):
    """
    Permission-checked idempotent action to resend the welcome email and secure password setup link.
    """
    target_user = get_object_or_404(User, pk=pk)

    if not can_manage_user(request.user, target_user):
        raise PermissionDenied("You do not have permission to resend invitations for this user.")

    email_sent, email_msg = send_user_welcome_email(target_user, request=request)
    if email_sent:
        messages.success(request, f"Welcome invitation resent successfully to {target_user.email}.")
    else:
        messages.warning(request, f"Failed to send welcome invitation to {target_user.email}: {email_msg}")

    next_url = request.META.get('HTTP_REFERER') or request.GET.get('next')
    if next_url:
        return redirect(next_url)

    if target_user.role == UserRole.SALES_HEAD:
        return redirect('admin_managers_list')
    elif target_user.role == UserRole.BRANCH_HEAD:
        return redirect('admin_branch_heads_list')
    elif target_user.role == UserRole.COUNSELOR:
        return redirect('admin_counselors_list')
    elif target_user.role == UserRole.TELECALLER:
        return redirect('admin_telecallers_list')
    elif target_user.role == UserRole.RECEPTIONIST:
        return redirect('admin_receptionists_list')
    return redirect('admin_dashboard')


@admin_required
def create_user_view(request):
    """
    Unified administrator Create User page.
    Validates permissions, generates a unique Login ID (if blank), creates user,
    and automatically dispatches the welcome email with secure password setup link.
    """
    allowed_branches = Branch.objects.filter(status='Active')
    if request.method == 'POST':
        form = AdminCreateUserForm(request.POST, allowed_branches=allowed_branches)
        if form.is_valid():
            user = form.save(commit=True, created_by=request.user)
            log_activity(
                user=request.user,
                action="User Created",
                description=f"Admin created {user.display_role} account '{user.username}' ({user.email}).",
                object_type="User",
                object_id=str(user.pk),
                request=request
            )

            # Send welcome email
            email_sent, email_msg = send_user_welcome_email(user, request=request)
            if email_sent:
                messages.success(
                    request,
                    f"User created successfully. A welcome email has been sent to the registered email address ({user.email})."
                )
            else:
                messages.warning(
                    request,
                    f"User created successfully, but the welcome email could not be sent ({email_msg}). Please retry sending the invitation."
                )

            # Redirect based on created user's role
            if user.role == UserRole.SALES_HEAD:
                return redirect('admin_managers_list')
            elif user.role == UserRole.BRANCH_HEAD:
                return redirect('admin_branch_heads_list')
            elif user.role == UserRole.COUNSELOR:
                return redirect('admin_counselors_list')
            elif user.role == UserRole.TELECALLER:
                return redirect('admin_telecallers_list')
            elif user.role == UserRole.RECEPTIONIST:
                return redirect('admin_receptionists_list')
            return redirect('admin_dashboard')
    else:
        form = AdminCreateUserForm(allowed_branches=allowed_branches)

    return render(request, 'admin/user_create.html', {
        'form': form,
        'portal_title': 'Create New CRM User',
    })


@login_required
def api_username_preview(request):
    """
    Lightweight, debounced API endpoint providing real-time preview of the auto-generated
    username/login ID based on the user's first and last name, role, and email.
    """
    first_name = request.GET.get('first_name', '').strip()
    last_name = request.GET.get('last_name', '').strip()
    role = request.GET.get('role', '').strip() or None
    email = request.GET.get('email', '').strip() or None
    exclude_id = request.GET.get('exclude_id', '').strip() or None
    if exclude_id and exclude_id.isdigit():
        exclude_id = int(exclude_id)
    else:
        exclude_id = None

    if not first_name and not last_name and not email:
        return JsonResponse({
            'success': True,
            'username': '',
            'base': '',
            'is_collision': False,
            'available': True,
        })

    candidate = generate_unique_username(
        first_name=first_name,
        last_name=last_name,
        role=role,
        email=email,
        exclude_user_id=exclude_id
    )

    first_clean = _clean_name_string(first_name)
    last_clean = _clean_name_string(last_name)
    if first_clean and last_clean:
        base = f"{first_clean}.{last_clean}"
    elif first_clean:
        base = first_clean
    elif last_clean:
        base = last_clean
    elif email and '@' in email:
        base = _clean_name_string(email.split('@')[0])
    else:
        base = f"{_clean_name_string(role) or 'user'}.member"

    import re
    base = re.sub(r'\.+', '.', base).strip('.')[:130].rstrip('.')
    is_collision = (candidate != base)

    return JsonResponse({
        'success': True,
        'username': candidate,
        'base': base,
        'is_collision': is_collision,
        'available': True,
    })



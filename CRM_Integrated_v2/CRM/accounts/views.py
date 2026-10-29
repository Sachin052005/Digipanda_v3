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
from .permissions import admin_required, can_manage_user, _ROLE_DASHBOARD_URL_NAMES
from .services import send_user_welcome_email, generate_unique_username, _clean_name_string
from branches.models import Branch
from activities.utils import log_activity

def login_redirect(request):
    """Smart redirect to appropriate dashboard based on user role."""
    if not request.user.is_authenticated:
        return redirect('login')

    user = request.user
    role = getattr(user, 'role', None)

    # 1. Superadmin / Admin / Superuser
    if user.is_superuser or role in (UserRole.ADMIN, UserRole.SUPERADMIN) or getattr(user, 'is_admin_user', False):
        return redirect('admin_dashboard')

    # 2. Canonical mapping by role
    dashboard_name = _ROLE_DASHBOARD_URL_NAMES.get(role)
    if dashboard_name:
        return redirect(dashboard_name)

    # 3. Property-based fallbacks
    if getattr(user, 'is_sales_head_user', False):
        return redirect('manager_dashboard')
    elif getattr(user, 'is_branch_head_user', False):
        return redirect('branch_head_dashboard')
    elif getattr(user, 'is_branch_admin_user', False):
        return redirect('admin_enrolled_students')
    elif getattr(user, 'is_counselor_user', False):
        return redirect('counselor_dashboard')
    elif getattr(user, 'is_telecaller_user', False):
        return redirect('telecaller_dashboard')
    elif getattr(user, 'is_receptionist_user', False):
        return redirect('receptionist_dashboard')
    elif getattr(user, 'is_accountant_user', False):
        return redirect('accountant_dashboard')
    elif getattr(user, 'is_finance_head_user', False):
        return redirect('finance_dashboard')
    elif user.is_staff:
        return redirect('admin_dashboard')

    # Defensive fallback for any other authenticated user: NEVER redirect to 'login' while authenticated!
    return redirect('root')

def _process_login(request, expected_role=None, template_name='registration/login.html', portal_title='CRM Login'):
    if request.user.is_authenticated:
        dest = login_redirect(request)
        dest_url = getattr(dest, 'url', '')
        if dest_url in ('/login/', '/login', request.path):
            return redirect('root')
        return dest

    form = LoginForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        email_input = (form.cleaned_data.get('email') or form.cleaned_data.get('username') or '').strip()
        password = form.cleaned_data.get('password')
        remember_me = form.cleaned_data.get('remember_me')

        # Authenticate via EmailAuthBackend (with case-insensitive email matching)
        user = authenticate(request, username=email_input, password=password)
        if user is None:
            user = authenticate(request, email=email_input, password=password)

        if user is not None:
            if not user.is_active:
                messages.error(request, "This account is inactive. Please contact your administrator.")
                return render(request, template_name, {'form': form, 'portal_title': portal_title, 'portal_role': expected_role})

            if expected_role:
                if expected_role == UserRole.ADMIN and not user.is_admin_user:
                    messages.error(request, f"Access denied. '{user.email}' is not registered with Admin privileges.")
                    return render(request, template_name, {'form': form, 'portal_title': portal_title, 'portal_role': expected_role})
                elif expected_role == UserRole.SALES_HEAD and not user.is_sales_head_user:
                    messages.error(request, f"Access denied. '{user.email}' is not a Sales Head.")
                    return render(request, template_name, {'form': form, 'portal_title': portal_title, 'portal_role': expected_role})
                elif expected_role == UserRole.TELECALLER and not user.is_telecaller_user:
                    messages.error(request, f"Access denied. '{user.email}' is not a Telecaller.")
                    return render(request, template_name, {'form': form, 'portal_title': portal_title, 'portal_role': expected_role})
                elif expected_role == UserRole.RECEPTIONIST and not user.is_receptionist_user:
                    messages.error(request, f"Access denied. '{user.email}' is not a Receptionist.")
                    return render(request, template_name, {'form': form, 'portal_title': portal_title, 'portal_role': expected_role})

            login(request, user)
            if not remember_me:
                request.session.set_expiry(0)  # Browser close expiration
            else:
                request.session.set_expiry(1209600)  # 2 weeks

            log_activity(
                user=user,
                action="User Logged In",
                description=f"{user.display_role} '{user.email}' logged in successfully.",
                object_type="User",
                object_id=str(user.pk),
                request=request
            )
            messages.success(request, f"Welcome back, {user.first_name or user.email}!")
            return login_redirect(request)
        else:
            messages.error(request, "Invalid email address or password. Please try again.")

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
        portal_title='DigiPanda CRM Login'
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
    return redirect('/login/?logged_out=1')


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
    elif target_user.role == UserRole.ACCOUNTANT:
        return redirect('admin_accountants_list')
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
            elif user.role == UserRole.BRANCH_ADMIN:
                return redirect('admin_branch_admins_list')
            elif user.role == UserRole.COUNSELOR:
                return redirect('admin_counselors_list')
            elif user.role == UserRole.TELECALLER:
                return redirect('admin_telecallers_list')
            elif user.role == UserRole.RECEPTIONIST:
                return redirect('admin_receptionists_list')
            elif user.role == UserRole.ACCOUNTANT:
                return redirect('admin_accountants_list')
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


@login_required
def user_profile(request):
    """Profile page for any authenticated user with self-service profile editing."""
    from django.contrib import messages
    from accounts.forms import UserProfileUpdateForm

    if request.method == 'POST':
        form = UserProfileUpdateForm(request.POST, instance=request.user)
        if form.is_valid():
            form.save()
            messages.success(request, "Your profile has been successfully updated.")
            return redirect('user_profile')
        else:
            messages.error(request, "Please correct the highlighted errors to update your profile.")
    else:
        form = UserProfileUpdateForm(instance=request.user)

    return render(request, 'accounts/profile.html', {
        'user': request.user,
        'form': form,
    })


@login_required
def universal_user_profile_redirect(request, pk):
    """
    Universal profile resolver: routes to the specific role profile view.
    Sales Head -> admin_manager_detail
    Branch Head -> admin_branch_head_detail
    Counselor -> admin_counselor_detail
    Telecaller -> admin_telecaller_detail
    Receptionist -> admin_receptionist_detail
    Accountant -> admin_accountant_detail
    Admin / Self -> user_profile
    """
    target_user = get_object_or_404(User, pk=pk)

    if target_user.role == UserRole.SALES_HEAD:
        return redirect('admin_manager_detail', pk=pk)
    elif target_user.role == UserRole.BRANCH_HEAD:
        return redirect('admin_branch_head_detail', pk=pk)
    elif target_user.role == UserRole.COUNSELOR:
        return redirect('admin_counselor_detail', pk=pk)
    elif target_user.role == UserRole.TELECALLER:
        return redirect('admin_telecaller_detail', pk=pk)
    elif target_user.role == UserRole.RECEPTIONIST:
        return redirect('admin_receptionist_detail', pk=pk)
    elif target_user.role == UserRole.ACCOUNTANT:
        return redirect('admin_accountant_detail', pk=pk)
    else:
        if request.user.pk == target_user.pk:
            return redirect('user_profile')
        return render(request, 'accounts/profile.html', {
            'user': target_user,
            'is_target_profile': True,
        })


@login_required
def user_change_password(request):
    """
    Allows any authenticated user to change their own password.
    Requires:
    - Current password (validated against existing password)
    - New password & confirmation (enforces all project password validators)
    - Updates session auth hash so the current session remains active
    - Records audit log via log_activity
    """
    from django.contrib.auth import update_session_auth_hash
    from django.contrib.auth.forms import PasswordChangeForm

    if request.method == 'POST':
        form = PasswordChangeForm(user=request.user, data=request.POST)
        if form.is_valid():
            user = form.save()
            update_session_auth_hash(request, user)
            log_activity(
                user=request.user,
                action="Password Changed",
                description=f"User '{request.user.username}' changed their password via Profile settings.",
                object_type="User",
                object_id=str(request.user.pk),
                request=request
            )
            messages.success(request, "Your password has been changed successfully.")
            return redirect('user_profile')
        else:
            messages.error(request, "Please correct the errors below.")
    else:
        form = PasswordChangeForm(user=request.user)

    return render(request, 'accounts/change_password.html', {
        'form': form,
    })


@login_required
def admin_send_password_reset_link(request, pk):
    """
    Authorized action to send a secure password reset link to a selected staff member's email.
    Enforces can_manage_user and superadmin protection.
    Records audit logging without exposing secrets.
    """
    target_user = get_object_or_404(User, pk=pk)

    if not can_manage_user(request.user, target_user):
        raise PermissionDenied("You do not have permission to send a password reset link for this user.")

    from .services import send_password_reset_email_for_user
    email_sent, email_msg = send_password_reset_email_for_user(target_user, request=request, admin_user=request.user)
    if email_sent:
        messages.success(request, f"Password reset link successfully sent to {target_user.email}.")
    else:
        messages.error(request, f"Failed to send password reset link to {target_user.email}: {email_msg}")

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
    elif target_user.role == UserRole.ACCOUNTANT:
        return redirect('admin_accountants_list')
    return redirect('admin_dashboard')


@login_required
def admin_set_user_password(request, pk):
    """
    Authorized administrator action to directly set a new password for a selected staff account.
    Enforces can_manage_user, superadmin protection, password validators, and audit logging.
    """
    target_user = get_object_or_404(User, pk=pk)

    if not can_manage_user(request.user, target_user):
        raise PermissionDenied("You do not have permission to set the password for this user.")

    if request.method == 'POST':
        form = SetPasswordForm(target_user, request.POST)
        if form.is_valid():
            form.save()
            target_user.must_change_password = False
            target_user.save(update_fields=['must_change_password'])

            log_activity(
                user=request.user,
                action="Administrator Set Password",
                description=f"Administrator '{request.user.username}' directly set a new password for '{target_user.username}' ({target_user.role}).",
                object_type="User",
                object_id=str(target_user.pk),
                request=request
            )

            try:
                from activities.services import create_notification
                create_notification(
                    recipient=target_user,
                    title="Password Changed",
                    message="Your account password was updated by an Administrator.",
                    notification_type="password_changed"
                )
            except Exception:
                pass

            messages.success(request, f"Password for {target_user.get_full_name() or target_user.username} has been successfully updated.")

            next_url = request.POST.get('next') or request.GET.get('next')
            if next_url:
                return redirect(next_url)

            if target_user.role == UserRole.SALES_HEAD:
                return redirect('admin_manager_detail', pk=target_user.pk)
            elif target_user.role == UserRole.BRANCH_HEAD:
                return redirect('admin_branch_head_detail', pk=target_user.pk)
            elif target_user.role == UserRole.COUNSELOR:
                return redirect('admin_counselor_detail', pk=target_user.pk)
            elif target_user.role == UserRole.TELECALLER:
                return redirect('admin_telecaller_detail', pk=target_user.pk)
            elif target_user.role == UserRole.RECEPTIONIST:
                return redirect('admin_receptionists_list')
            elif target_user.role == UserRole.ACCOUNTANT:
                return redirect('admin_accountants_list')
            return redirect('admin_dashboard')
        else:
            messages.error(request, "Please correct the password errors below.")
    else:
        form = SetPasswordForm(target_user)

    return render(request, 'accounts/admin_set_password.html', {
        'form': form,
        'target_user': target_user,
    })




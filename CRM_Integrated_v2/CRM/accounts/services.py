"""
Accounts Service Layer for TECHPANDA CRM.
Handles:
- Automatic unique login ID / username generation
- User creation with credential onboarding
- Cryptographically secure single-use time-limited account setup links
- Professional welcome email dispatch with HTML and plain-text alternatives
- Idempotent invitation resending and audit tracking
"""

import logging
import re
from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.tokens import default_token_generator
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils import timezone
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode

from activities.utils import log_activity
from accounts.models import UserRole
from accounts.credentials_service import setup_user_credentials

logger = logging.getLogger(__name__)
User = get_user_model()


import unicodedata


def _clean_name_string(val):
    """
    Normalizes a name string:
    - Strips accents via Unicode NFKD
    - Replaces whitespace, hyphens, underscores with single dots
    - Keeps only lowercase a-z, 0-9, and dots
    - Collapses multiple dots and strips edge dots
    """
    if not val:
        return ""
    # Strip unicode accents
    norm = unicodedata.normalize('NFKD', str(val)).encode('ascii', 'ignore').decode('ascii').lower()
    # Replace spaces, hyphens, underscores with dots
    norm = re.sub(r'[\s\-_]+', '.', norm)
    # Remove any character not lowercase alphanumeric or dot
    norm = re.sub(r'[^a-z0-9.]', '', norm)
    # Collapse multiple consecutive dots
    norm = re.sub(r'\.+', '.', norm)
    return norm.strip('.')


def generate_unique_username(first_name="", last_name="", role=None, email=None, exclude_user_id=None):
    """
    Generates a clean, professional, and unique login ID (username) for a CRM member.
    Rules:
    - Normalizes first and last name (Unicode accents stripped, spaces/hyphens to dots).
    - If both first & last provided: '{first}.{last}'.
    - If only first provided: '{first}'.
    - If only last provided: '{last}'.
    - If neither, uses email username prefix (normalized).
    - If still empty, uses '{role}.member' (fallback 'user.member').
    - Base is capped at 130 characters.
    - If collision exists, appends numbers starting at 2 (e.g. 'tamil.selvan', 'tamil.selvan2', 'tamil.selvan3').
    """
    first = _clean_name_string(first_name)
    last = _clean_name_string(last_name)

    base = ""
    if first and last:
        base = f"{first}.{last}"
    elif first:
        base = first
    elif last:
        base = last
    elif email and '@' in email:
        email_prefix = email.split('@')[0]
        base = _clean_name_string(email_prefix)
    else:
        role_str = _clean_name_string(role) or "user"
        base = f"{role_str}.member"

    # Collapse consecutive dots and strip ends
    base = re.sub(r'\.+', '.', base).strip('.')
    if not base:
        base = "user.member"

    # Ensure length doesn't exceed 130
    if len(base) > 130:
        base = base[:130].rstrip('.')

    candidate = base
    counter = 1

    qs = User.objects.all()
    if exclude_user_id:
        qs = qs.exclude(pk=exclude_user_id)

    while qs.filter(username__iexact=candidate).exists():
        counter += 1
        candidate = f"{base}{counter}"
        if len(candidate) > 150:
            candidate = f"{base[:140].rstrip('.')}{counter}"

    return candidate



def send_user_welcome_email(user, request=None):
    """
    Generates a secure, single-use, time-limited password setup link and dispatches
    a branded welcome email to the member's registered email address.

    Returns:
        tuple (bool, str): (success, message)
    """
    if not user.email:
        logger.warning("Cannot send welcome email: User %s has no email address configured.", user.username)
        return False, "User has no email address configured."

    # 1. Cryptographically secure, user-specific, single-use token bound to account
    uidb64 = urlsafe_base64_encode(force_bytes(user.pk))
    token = default_token_generator.make_token(user)

    # 2. Build absolute setup URL
    relative_url = reverse('account_setup', kwargs={'uidb64': uidb64, 'token': token})
    if request:
        setup_url = request.build_absolute_uri(relative_url)
        login_url = request.build_absolute_uri(reverse('login'))
    else:
        base_url = getattr(settings, 'CRM_BASE_URL', 'http://127.0.0.1:8000').rstrip('/')
        setup_url = f"{base_url}{relative_url}"
        login_url = f"{base_url}/login/"

    company_name = getattr(settings, 'COMPANY_NAME', 'TECHPANDA')

    context = {
        'user': user,
        'user_name': user.get_full_name() or user.first_name or user.username,
        'username': user.username,
        'user_role': user.display_role,
        'branch_name': user.branch.name if user.branch else 'All Branches / Central',
        'company_name': company_name,
        'setup_url': setup_url,
        'login_url': login_url,
    }

    subject = f"Welcome to {company_name} CRM — Your Account Details"

    try:
        html_content = render_to_string('emails/user_welcome.html', context)
        text_content = render_to_string('emails/user_welcome.txt', context)

        from_email = getattr(settings, 'DEFAULT_FROM_EMAIL', None) or f"{company_name} CRM <no-reply@techpanda.academy>"

        msg = EmailMultiAlternatives(
            subject=subject,
            body=text_content,
            from_email=from_email,
            to=[user.email],
        )
        msg.attach_alternative(html_content, "text/html")
        msg.send(fail_silently=False)

        # Update invitation tracking
        user.invitation_status = 'SENT'
        user.invitation_sent_at = timezone.now()
        user.save(update_fields=['invitation_status', 'invitation_sent_at'])

        log_activity(
            user=user,
            action="Welcome Email Sent",
            description=f"Welcome and password setup email sent to '{user.username}' ({user.email}).",
            object_type="User",
            object_id=str(user.pk),
            request=request
        )
        logger.info("Welcome email successfully sent to %s (%s).", user.username, user.email)
        return True, "Welcome email sent successfully."

    except Exception as e:
        logger.error("Failed to send welcome email to %s (%s): %s", user.username, user.email, str(e), exc_info=True)
        user.invitation_status = 'FAILED'
        user.save(update_fields=['invitation_status'])

        log_activity(
            user=user,
            action="Welcome Email Delivery Failed",
            description=f"Welcome email delivery to '{user.username}' ({user.email}) failed: {str(e)}",
            object_type="User",
            object_id=str(user.pk),
            request=request
        )
        return False, str(e)


def create_user_with_generated_credentials(
    first_name,
    last_name,
    email,
    role,
    branch=None,
    counselor=None,
    username=None,
    phone='',
    raw_password=None,
    is_active=True,
    created_by=None,
    request=None
):
    """
    Unified high-level service to create a team member across any CRM role.
    Validates data, assigns credentials, saves account, and dispatches the welcome email.

    Returns:
        tuple (user, email_sent, email_message)
    """
    if not username:
        username = generate_unique_username(first_name=first_name, last_name=last_name, role=role, email=email)

    user = User(
        username=username,
        first_name=first_name or '',
        last_name=last_name or '',
        email=email,
        phone=phone or '',
        role=role,
        branch=branch,
        counselor=counselor,
    )

    # Set credentials
    # If raw_password is provided manually, use it and activate account.
    # If raw_password is not provided, account remains inactive/unable to authenticate until setup.
    if raw_password:
        user.set_password(raw_password)
        user.must_change_password = False
        user.is_active = is_active
    else:
        user.set_unusable_password()
        user.must_change_password = True
        user.is_active = False  # Inactive until account activation via email setup link
        user.invitation_status = 'PENDING'

    user.save()

    # Log creation activity
    creator_str = f"by {created_by.username}" if created_by else "by System"
    log_activity(
        user=created_by or user,
        action="User Created",
        description=f"New {user.display_role} account '{user.username}' created {creator_str}.",
        object_type="User",
        object_id=str(user.pk),
        request=request
    )

    # Dispatch welcome email with setup token
    email_sent, email_msg = send_user_welcome_email(user, request=request)
    return user, email_sent, email_msg

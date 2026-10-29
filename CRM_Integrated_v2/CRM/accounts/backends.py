"""
Authentication backends for DigiPanda CRM.
Supports email-based authentication with case-insensitive matching.
"""

from django.contrib.auth.backends import ModelBackend
from django.contrib.auth import get_user_model

User = get_user_model()


class EmailAuthBackend(ModelBackend):
    """
    Authenticate against settings.AUTH_USER_MODEL using an email address
    (case-insensitive). Also falls back to username if an existing system call
    passes a username.
    """

    def authenticate(self, request, username=None, password=None, email=None, **kwargs):
        login_identifier = email or username or kwargs.get('email') or kwargs.get('username')
        if not login_identifier or not password:
            return None

        login_identifier = str(login_identifier).strip()

        # Primary lookup: email (case-insensitive)
        user = User.objects.filter(email__iexact=login_identifier).first()

        # Secondary fallback lookup: username (case-insensitive) for technical compatibility
        if not user:
            user = User.objects.filter(username__iexact=login_identifier).first()

        if user and user.check_password(password) and self.user_can_authenticate(user):
            return user
        return None

    def get_user(self, user_id):
        try:
            return User.objects.get(pk=user_id)
        except User.DoesNotExist:
            return None

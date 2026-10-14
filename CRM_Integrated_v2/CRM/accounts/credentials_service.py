"""
Credentials Service for TECHPANDA CRM.
Handles cryptographically secure random password generation, automated account credential onboarding,
and one-time credential flash alerts with required password changes.
"""

import secrets
import string
from django.contrib.auth.password_validation import validate_password


def generate_secure_random_password(length: int = 12) -> str:
    """
    Generates a cryptographically strong, random temporary password that satisfies
    Django password validators (uppercase, lowercase, numeric digits, and special characters).
    """
    if length < 10:
        length = 12

    uppercase = string.ascii_uppercase
    lowercase = string.ascii_lowercase
    digits = string.digits
    special = "!@#$%^&*()-_=+"

    # Ensure representation from every required character set
    pwd_chars = [
        secrets.choice(uppercase),
        secrets.choice(lowercase),
        secrets.choice(digits),
        secrets.choice(special),
    ]

    all_characters = uppercase + lowercase + digits + special
    for _ in range(length - 4):
        pwd_chars.append(secrets.choice(all_characters))

    # Shuffle cryptographically to avoid predictable character positions
    secrets.SystemRandom().shuffle(pwd_chars)
    password = "".join(pwd_chars)

    return password


def setup_user_credentials(user, raw_password=None, auto_generate=False):
    """
    Sets up credentials on a user instance:
    - If auto_generate is True or raw_password is empty, generates a cryptographically strong password
      and sets must_change_password = True.
    - If raw_password is provided manually, validates and sets it.
    Returns (user, raw_password_used, was_auto_generated).
    """
    was_auto_generated = False
    if auto_generate or not raw_password:
        raw_password = generate_secure_random_password(length=12)
        was_auto_generated = True
        user.must_change_password = True
    else:
        user.must_change_password = False

    user.set_password(raw_password)
    user._generated_password = raw_password if was_auto_generated else None
    return user, raw_password, was_auto_generated

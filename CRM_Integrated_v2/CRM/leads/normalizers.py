"""
Canonical Identity Normalization Service for CRM Leads.
Provides robust, reproducible cleaning of phone numbers and email addresses.
"""
import re
from typing import Optional


def normalize_phone_number(raw_phone: Optional[str]) -> Optional[str]:
    """
    Standardize a phone number string:
    - Strips prefixes like 'p:', 'tel:', '+91', '91', leading '0'.
    - Strips whitespace, hyphens, brackets, dots.
    - If 10 digits remain (Indian standard national mobile), returns those 10 digits.
    - If international (+...) format, formats to clean E.164.
    - Rejects garbage (repeated zeros, < 7 digits, all non-digits).
    """
    if not raw_phone:
        return None

    raw = str(raw_phone).strip()
    if not raw:
        return None

    # Handle uri prefixes: p:+91..., tel:+91...
    if ':' in raw:
        raw = raw.split(':', 1)[-1].strip()

    is_international_plus = raw.startswith('+')

    # Extract digits only
    digits = re.sub(r'\D', '', raw)
    if not digits or len(digits) < 7:
        return None

    # Reject obvious dummy sequences
    if set(digits) == {'0'} or digits == '1234567890' or digits == '0123456789':
        return None

    # Standard Indian mobile handling
    # If 12 digits starting with 91 (e.g. 919876543210)
    if len(digits) == 12 and digits.startswith('91'):
        return digits[2:]

    # If 11 digits starting with 0 (e.g. 09876543210)
    if len(digits) == 11 and digits.startswith('0'):
        return digits[1:]

    # Standard 10-digit number
    if len(digits) == 10:
        return digits

    # If international with + prefix and > 10 digits
    if is_international_plus and len(digits) > 10:
        return f"+{digits}"

    # Fallback to last 10 digits if longer
    if len(digits) > 10:
        return digits[-10:]

    return digits


def normalize_email(raw_email: Optional[str]) -> Optional[str]:
    """
    Normalize email address:
    - Lowercase, strip whitespace.
    - Validate basic structure (contains @ and dot).
    - Reject dummy/placeholder emails.
    """
    if not raw_email:
        return None

    email = str(raw_email).strip().lower()
    if not email or '@' not in email or '.' not in email:
        return None

    # Reject common dummy placeholders
    dummy_patterns = [
        'noemail', 'na@', 'none@', 'test@', 'test.com', 'example.com',
        'null@', 'nil@', 'notgiven', 'noreply@'
    ]
    if any(p in email for p in dummy_patterns):
        return None

    return email

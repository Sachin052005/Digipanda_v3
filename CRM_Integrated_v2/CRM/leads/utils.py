"""
Utility helpers for Leads views and controllers.
Provides reusable pagination, sorting, and filter validation.
"""
from typing import Tuple

ALLOWED_PAGE_SIZES: Tuple[int, ...] = (20, 50, 100, 500)
DEFAULT_PAGE_SIZE: int = 20


def get_validated_page_size(request, default: int = DEFAULT_PAGE_SIZE) -> int:
    """
    Extracts and validates the requested page size from request GET parameters.
    Supports 'page_size' or 'per_page'.
    Accepts only values in ALLOWED_PAGE_SIZES (20, 50, 100, 500).
    Safely falls back to default (20) if missing or invalid.
    """
    if not request or not hasattr(request, 'GET'):
        return default

    raw_size = request.GET.get('page_size') or request.GET.get('per_page')
    if not raw_size:
        return default

    try:
        size = int(str(raw_size).strip())
        if size in ALLOWED_PAGE_SIZES:
            return size
    except (ValueError, TypeError):
        pass

    return default

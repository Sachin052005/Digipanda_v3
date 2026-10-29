"""
TechPanda CRM - Centralized Date Parameter Normalization Utility
Reconciles date filter parameter naming variations across dashboards:
  - Canonical: start_date / end_date
  - Dashboard variants: from_date / to_date
  - Listing variants: date_from / date_to
"""

from datetime import datetime, date, timedelta, time
from django.utils import timezone


def parse_iso_date(date_str):
    """Safely parse a YYYY-MM-DD string into a date object. Returns None on invalid format."""
    if not date_str or not isinstance(date_str, str):
        return None
    cleaned = date_str.strip()
    if not cleaned:
        return None
    try:
        return datetime.strptime(cleaned, '%Y-%m-%d').date()
    except (ValueError, TypeError):
        return None


def extract_normalized_date_range(request, default_period='all'):
    """
    Inspects GET parameters and extracts normalized start_date and end_date.
    Checks parameter aliases in prioritized order:
      1. start_date / end_date (Canonical)
      2. from_date / to_date (Admin Dashboard standard)
      3. date_from / date_to (Leads List standard)

    Returns a dict with:
      - 'start_date': str 'YYYY-MM-DD' or ''
      - 'end_date': str 'YYYY-MM-DD' or ''
      - 'period': str ('today', 'yesterday', 'week', 'month', 'custom', 'all')
      - 'start_date_obj': date object or None
      - 'end_date_obj': date object or None
      - 'start_dt': timezone-aware datetime or None (start of day 00:00:00)
      - 'end_dt': timezone-aware datetime or None (end of day 23:59:59.999999)
      - 'is_valid': bool
    """
    get = request.GET if (request and hasattr(request, 'GET')) else {}

    # Extract raw parameters with alias resolution
    raw_start = (get.get('start_date') or get.get('from_date') or get.get('date_from') or '').strip()
    raw_end = (get.get('end_date') or get.get('to_date') or get.get('date_to') or '').strip()
    period = get.get('period', default_period or 'all').strip().lower()

    today = timezone.localdate()
    start_date_obj = None
    end_date_obj = None

    # Handle named periods
    if period == 'today':
        start_date_obj = today
        end_date_obj = today
    elif period == 'yesterday':
        yesterday = today - timedelta(days=1)
        start_date_obj = yesterday
        end_date_obj = yesterday
    elif period == 'week':
        start_date_obj = today - timedelta(days=today.weekday())
        end_date_obj = today
    elif period == 'month':
        start_date_obj = today.replace(day=1)
        end_date_obj = today
    elif raw_start or raw_end:
        period = 'custom'
        start_date_obj = parse_iso_date(raw_start)
        end_date_obj = parse_iso_date(raw_end)

        # Handle half-open ranges
        if start_date_obj and not end_date_obj:
            end_date_obj = today
        elif end_date_obj and not start_date_obj:
            start_date_obj = end_date_obj

        # Auto-correct reversed ranges
        if start_date_obj and end_date_obj and start_date_obj > end_date_obj:
            start_date_obj, end_date_obj = end_date_obj, start_date_obj

    # Produce output string format
    start_date_str = start_date_obj.strftime('%Y-%m-%d') if start_date_obj else ''
    end_date_str = end_date_obj.strftime('%Y-%m-%d') if end_date_obj else ''

    # Build timezone-aware datetimes
    start_dt = None
    end_dt = None
    if start_date_obj:
        start_dt = timezone.make_aware(datetime.combine(start_date_obj, time.min))
    if end_date_obj:
        end_dt = timezone.make_aware(datetime.combine(end_date_obj, time.max))

    return {
        'start_date': start_date_str,
        'end_date': end_date_str,
        'from_date': start_date_str,  # backward compatibility alias
        'to_date': end_date_str,      # backward compatibility alias
        'date_from': start_date_str,  # backward compatibility alias
        'date_to': end_date_str,      # backward compatibility alias
        'period': period,
        'start_date_obj': start_date_obj,
        'end_date_obj': end_date_obj,
        'start_dt': start_dt,
        'end_dt': end_dt,
        'is_valid': bool(start_date_obj and end_date_obj) if period == 'custom' else True,
    }


def preserve_normalized_date_params(request, target_dict=None):
    """
    Copies normalized date parameters into a query dict preserving both
    canonical and compatible naming for outbound navigation links.
    """
    if target_dict is None:
        target_dict = {}
    normalized = extract_normalized_date_range(request)
    if normalized['start_date']:
        target_dict['start_date'] = normalized['start_date']
        target_dict['date_from'] = normalized['start_date']
        target_dict['from_date'] = normalized['start_date']
    if normalized['end_date']:
        target_dict['end_date'] = normalized['end_date']
        target_dict['date_to'] = normalized['end_date']
        target_dict['to_date'] = normalized['end_date']
    if normalized['period'] and normalized['period'] != 'all':
        target_dict['period'] = normalized['period']
    return target_dict

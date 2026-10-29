import os
import sys
from datetime import date, timedelta
from unittest import TestCase

CRM_ROOT = 'D:/CRM_Integrated_v2/CRM_Integrated_v2/CRM'
if CRM_ROOT not in sys.path:
    sys.path.insert(0, CRM_ROOT)

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
import django
django.setup()

from django.test import RequestFactory
from django.utils import timezone
from leads.utils_date_filter import extract_normalized_date_range, parse_iso_date
from leads.templatetags.kpi_tags import build_kpi_url


class DateParameterContractsTests(TestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.today = timezone.localdate()

    def test_canonical_start_and_end_date(self):
        """Verify canonical start_date and end_date are parsed accurately."""
        request = self.factory.get('/dashboard/?start_date=2026-10-01&end_date=2026-10-15')
        res = extract_normalized_date_range(request)
        self.assertEqual(res['start_date'], '2026-10-01')
        self.assertEqual(res['end_date'], '2026-10-15')
        self.assertEqual(res['period'], 'custom')
        self.assertEqual(res['start_date_obj'], date(2026, 10, 1))
        self.assertEqual(res['end_date_obj'], date(2026, 10, 15))

    def test_admin_from_date_and_to_date_aliases(self):
        """Verify from_date and to_date are recognized as start_date and end_date."""
        request = self.factory.get('/dashboard/?from_date=2026-09-01&to_date=2026-09-30')
        res = extract_normalized_date_range(request)
        self.assertEqual(res['start_date'], '2026-09-01')
        self.assertEqual(res['end_date'], '2026-09-30')
        self.assertEqual(res['from_date'], '2026-09-01')
        self.assertEqual(res['to_date'], '2026-09-30')
        self.assertEqual(res['period'], 'custom')

    def test_leads_list_date_from_and_date_to_aliases(self):
        """Verify date_from and date_to are recognized accurately."""
        request = self.factory.get('/leads/?date_from=2026-08-10&date_to=2026-08-20')
        res = extract_normalized_date_range(request)
        self.assertEqual(res['start_date'], '2026-08-10')
        self.assertEqual(res['end_date'], '2026-08-20')
        self.assertEqual(res['date_from'], '2026-08-10')
        self.assertEqual(res['date_to'], '2026-08-20')

    def test_named_period_presets(self):
        """Verify today, week, month presets calculate correct dates."""
        req_today = self.factory.get('/dashboard/?period=today')
        res_today = extract_normalized_date_range(req_today)
        self.assertEqual(res_today['start_date'], self.today.strftime('%Y-%m-%d'))
        self.assertEqual(res_today['end_date'], self.today.strftime('%Y-%m-%d'))

        req_month = self.factory.get('/dashboard/?period=month')
        res_month = extract_normalized_date_range(req_month)
        self.assertEqual(res_month['start_date'], self.today.replace(day=1).strftime('%Y-%m-%d'))
        self.assertEqual(res_month['end_date'], self.today.strftime('%Y-%m-%d'))

    def test_reversed_dates_auto_correction(self):
        """Verify that if start_date > end_date, the utility automatically corrects order."""
        request = self.factory.get('/dashboard/?start_date=2026-10-25&end_date=2026-10-05')
        res = extract_normalized_date_range(request)
        self.assertEqual(res['start_date'], '2026-10-05')
        self.assertEqual(res['end_date'], '2026-10-25')

    def test_invalid_dates_handled_safely(self):
        """Verify that malformed dates do not raise server errors."""
        request = self.factory.get('/dashboard/?start_date=not-a-date&end_date=2026-99-99')
        res = extract_normalized_date_range(request)
        self.assertEqual(res['start_date'], '')
        self.assertEqual(res['end_date'], '')
        self.assertFalse(res['is_valid'])

    def test_build_kpi_url_preserves_date_range_and_filters(self):
        """Verify build_kpi_url translates dashboard date filters to date_from / date_to for leads list."""
        req = self.factory.get('/dashboard/?from_date=2026-10-01&to_date=2026-10-20&branch=3')
        context = {'request': req, 'selected_branch_id': 3}
        url = build_kpi_url(context, 'admin_leads_list', 'status', 'New')
        
        self.assertIn('status=New', url)
        self.assertIn('date_from=2026-10-01', url)
        self.assertIn('date_to=2026-10-20', url)
        self.assertIn('branch=3', url)


if __name__ == '__main__':
    import unittest
    unittest.main()

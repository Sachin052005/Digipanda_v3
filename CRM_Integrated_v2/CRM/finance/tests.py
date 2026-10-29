import os
import sys
from decimal import Decimal
from datetime import date, timedelta
from unittest import TestCase

CRM_ROOT = 'D:/CRM_Integrated_v2/CRM_Integrated_v2/CRM'
if CRM_ROOT not in sys.path:
    sys.path.insert(0, CRM_ROOT)

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
import django
django.setup()

from django.test import RequestFactory
from django.urls import reverse, resolve
from django.contrib.messages.storage.fallback import FallbackStorage
from django.contrib.auth import get_user_model

from accounts.models import UserRole
from accounts.permissions import _ROLE_DASHBOARD_URL_NAMES
from branches.models import Branch
from products.models import Product
from leads.models import Enrollment, PaymentTransaction, PaymentTransactionStatus
from finance.models import Expense, ExpenseCategory, ExpenseStatus, InternalTransfer, RenewalAlert
from finance.services import get_finance_dashboard_metrics, get_pending_payments_breakdown

User = get_user_model()


class FinancePortalUnitTests(TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.branch = Branch.objects.first()
        if not cls.branch:
            cls.branch = Branch.objects.create(name='Vadapalani', code='VAD', status=Branch.Status.ACTIVE)

        # Ensure saved users exist for context processors
        cls.finance_head, _ = User.objects.get_or_create(
            username='test_fin_head_user',
            defaults={'role': UserRole.FINANCE_HEAD, 'branch': cls.branch, 'is_active': True}
        )
        if cls.finance_head.role != UserRole.FINANCE_HEAD:
            cls.finance_head.role = UserRole.FINANCE_HEAD
            cls.finance_head.branch = cls.branch
            cls.finance_head.save()

        cls.telecaller, _ = User.objects.get_or_create(
            username='test_tc_user',
            defaults={'role': UserRole.TELECALLER, 'branch': cls.branch, 'is_active': True}
        )
        if cls.telecaller.role != UserRole.TELECALLER:
            cls.telecaller.role = UserRole.TELECALLER
            cls.telecaller.save()

    def setUp(self):
        self.factory = RequestFactory()

    def _prepare_request(self, path, user):
        req = self.factory.get(path)
        req.resolver_match = resolve(path)
        req.user = user
        setattr(req, 'session', {})
        setattr(req, '_messages', FallbackStorage(req))
        return req

    def test_01_finance_head_role_and_property(self):
        """Validates UserRole.FINANCE_HEAD and helper properties."""
        self.assertEqual(UserRole.FINANCE_HEAD, 'FINANCE_HEAD')
        self.assertTrue(self.finance_head.is_finance_head_user)
        self.assertFalse(self.finance_head.is_admin_user)
        self.assertFalse(self.telecaller.is_finance_head_user)
        self.assertEqual(_ROLE_DASHBOARD_URL_NAMES.get(UserRole.FINANCE_HEAD), 'finance_dashboard')

    def test_02_login_redirect_finance_head(self):
        """Validates that login_redirect sends a Finance Head to finance_dashboard."""
        from accounts.views import login_redirect
        req = self._prepare_request('/login/redirect/', self.finance_head)
        response = login_redirect(req)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse('finance_dashboard'))

    def test_03_url_reversals(self):
        """Ensures all 11 screenshot-derived finance portal URLs reverse cleanly."""
        url_names = [
            'finance_login',
            'finance_dashboard',
            'finance_pending_payments',
            'finance_approvals',
            'finance_oversight',
            'finance_expenses',
            'finance_internal_transfers',
            'finance_renewal_alerts',
            'finance_employees',
            'finance_payroll',
            'finance_salary_arrears',
            'finance_incentive_track',
            'finance_settings',
            'finance_audit_export',
        ]
        for name in url_names:
            url = reverse(name)
            self.assertTrue(url.startswith('/finance/'))

    def test_04_permission_barrier_telecaller_denied(self):
        """Verifies that unauthorized roles are blocked from accessing the finance dashboard."""
        from finance.views import finance_dashboard
        req = self._prepare_request('/finance/dashboard/', self.telecaller)
        resp = finance_dashboard(req)
        # Should redirect with access denied
        self.assertEqual(resp.status_code, 302)
        self.assertNotEqual(resp.url, '/finance/dashboard/')

    def test_05_permission_barrier_finance_head_permitted(self):
        """Verifies that Finance Head can access finance dashboard."""
        from finance.views import finance_dashboard
        req = self._prepare_request('/finance/dashboard/', self.finance_head)
        resp = finance_dashboard(req)
        self.assertEqual(resp.status_code, 200)

    def test_06_dashboard_financial_math(self):
        """Verifies that dashboard financial calculations use exact Decimal math."""
        metrics = get_finance_dashboard_metrics([self.branch.id])
        # Balance = total_collection - total_expenses
        self.assertEqual(metrics['balance'], metrics['total_collection'] - metrics['total_expenses'])
        # Balance after GST = balance - total_gst
        self.assertEqual(metrics['balance_after_gst'], metrics['balance'] - metrics['total_gst'])
        self.assertIsInstance(metrics['total_collection'], Decimal)
        self.assertIsInstance(metrics['balance'], Decimal)

    def test_07_template_rendering_all_views(self):
        """Renders all 11 core templates to guarantee zero template syntax errors."""
        views_to_test = [
            ('/finance/dashboard/', 'finance/dashboard.html'),
            ('/finance/pending/', 'finance/pending_payments.html'),
            ('/finance/approvals/', 'finance/approvals.html'),
            ('/finance/finance-oversight/', 'finance/finance_oversight.html'),
            ('/finance/expenses/', 'finance/expenses_ledger.html'),
            ('/finance/internal-transfers/', 'finance/internal_transfers.html'),
            ('/finance/renewal-alerts/', 'finance/renewal_alerts.html'),
            ('/finance/hr/employees/', 'finance/employees.html'),
            ('/finance/hr/payroll/', 'finance/payroll.html'),
            ('/finance/hr/salary-arrears/', 'finance/salary_arrears.html'),
            ('/finance/incentive-track/', 'finance/incentive_track.html'),
            ('/finance/settings/', 'finance/settings.html'),
        ]
        for path, tpl in views_to_test:
            req = self._prepare_request(path, self.finance_head)
            resolver_match = resolve(path)
            view_func = resolver_match.func
            resp = view_func(req)
            self.assertEqual(resp.status_code, 200, f"Failed rendering {tpl}")
            self.assertIn('<!DOCTYPE html>', resp.content.decode('utf-8'))

    def test_08_finance_login_ui_ux_flow(self):
        """Verifies Finance Head login view rendering, password toggle markup, and auth redirect."""
        from django.contrib.auth.models import AnonymousUser
        from finance.views import finance_login

        # 1. Anonymous GET login page
        req = self._prepare_request('/finance/login/', AnonymousUser())
        resp = finance_login(req)
        self.assertEqual(resp.status_code, 200)
        content = resp.content.decode('utf-8')
        self.assertIn('Finance Sign In', content)
        self.assertIn('tp-password-toggle-btn', content)
        self.assertIn('btn-finance-submit', content)
        self.assertIn('Branch Financial Head Portal', content)

        # 2. Already authenticated user accessing login is redirected to dashboard
        req_auth = self._prepare_request('/finance/login/', self.finance_head)
        resp_auth = finance_login(req_auth)
        self.assertEqual(resp_auth.status_code, 302)
        self.assertEqual(resp_auth.url, reverse('finance_dashboard'))

    def test_09_renewal_alerts_enterprise_integration(self):
        """
        Validates Enterprise Renewal Alerts:
        - Creation with contract ref, dual recipients (Finance Head & Branch Head)
        - Next reminder date calculation based on lead time
        - Real database KPI metrics aggregation
        - Batch evaluation engine dispatching in-app notifications
        - Recurrence advancement on mark_done
        """
        from finance.models import RenewalAlert, RenewalAlertType, RenewalAlertStatus
        from finance.services import get_renewal_alerts_metrics, process_renewal_alerts_batch
        from activities.models import Notification

        today = date.today()

        # Create a branch head user for dual recipient testing
        branch_head, _ = User.objects.get_or_create(
            username='test_bh_user_alert',
            defaults={'role': UserRole.BRANCH_HEAD, 'branch': self.branch, 'is_active': True}
        )

        # 1. Create a renewal alert due in 5 days with 7 days lead time
        alert = RenewalAlert.objects.create(
            branch=self.branch,
            name="Office Lease Q4",
            alert_type=RenewalAlertType.RENEWAL,
            contract_reference="LEASE-2026-VAD-01",
            repeat_every_months=3,  # Quarterly
            due_date=today + timedelta(days=5),
            alert_starts_days_before=7,
            amount=Decimal('85000.00'),
            recipient_finance_head=self.finance_head,
            recipient_branch_head=branch_head,
            created_by=self.finance_head,
            status=RenewalAlertStatus.ACTIVE
        )

        # 2. Verify reminder lead time
        self.assertEqual(alert.next_reminder_date, alert.due_date - timedelta(days=7))
        self.assertTrue(today >= alert.next_reminder_date)  # It is within lead window!

        # 3. Verify KPI metrics calculation from database
        metrics = get_renewal_alerts_metrics([self.branch.id])
        self.assertGreaterEqual(metrics['total_active_count'], 1)
        self.assertGreaterEqual(metrics['due_in_7_days_count'], 1)
        self.assertGreaterEqual(metrics['total_active_amount'], Decimal('85000.00'))

        # 4. Run batch evaluation engine
        notif_count_before = Notification.objects.filter(recipient__in=[self.finance_head, branch_head]).count()
        res = process_renewal_alerts_batch(target_date=today)
        self.assertGreaterEqual(res['notifications_sent'], 2)  # Both recipients notified!

        notif_count_after = Notification.objects.filter(recipient__in=[self.finance_head, branch_head]).count()
        self.assertGreaterEqual(notif_count_after, notif_count_before + 2)

        # Duplicate barrier verification: running again today does NOT dispatch duplicate notifications
        res_dup = process_renewal_alerts_batch(target_date=today)
        self.assertEqual(res_dup['notifications_sent'], 0)

        # 5. Verify recurrence advancement
        old_due = alert.due_date
        alert.advance_to_next_cycle()
        alert.refresh_from_db()
        self.assertEqual(alert.status, RenewalAlertStatus.ACTIVE)
        self.assertGreater(alert.due_date, old_due)
        # Advance by 3 months
        self.assertIsNone(alert.last_notified_date)

        # 6. Verify view rendering
        from finance.views import finance_renewal_alerts
        req = self._prepare_request('/finance/renewal-alerts/', self.finance_head)
        resp = finance_renewal_alerts(req)
        self.assertEqual(resp.status_code, 200)
        content = resp.content.decode('utf-8')
        self.assertIn('Renewal Alerts', content)
        self.assertIn('Total Active Alerts', content)
        self.assertIn('Due Within 7 Days', content)
        self.assertIn('Office Lease Q4', content)
        self.assertIn('LEASE-2026-VAD-01', content)


if __name__ == '__main__':
    import unittest
    unittest.main()

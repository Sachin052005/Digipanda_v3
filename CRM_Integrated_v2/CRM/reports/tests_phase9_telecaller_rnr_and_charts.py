from django.test import TestCase, Client
from django.urls import reverse
from django.utils import timezone
from datetime import timedelta

from accounts.models import User, UserRole
from branches.models import Branch
from leads.models import Lead, LeadStatus, LeadCategory
from calls.models import CallHistory, CallOutcome, CallStatus


class TelecallerRNRAndChartsTestCase(TestCase):
    def setUp(self):
        self.client = Client()
        self.branch1 = Branch.objects.create(name="Alpha Branch", status="Active")
        self.branch2 = Branch.objects.create(name="Beta Branch", status="Active")

        # Admin User
        self.admin = User.objects.create_user(
            username="admin_rep", email="admin_rep@test.com", password="password123",
            role=UserRole.ADMIN, is_staff=True, is_superuser=True
        )

        # Counselor
        self.counselor = User.objects.create_user(
            username="counselor_rep", email="c_rep@test.com", password="password123",
            role=UserRole.COUNSELOR, branch=self.branch1
        )

        # Telecaller 1 (Alpha Branch)
        self.tc1 = User.objects.create_user(
            username="tc_alpha", email="tc1@test.com", password="password123",
            role=UserRole.TELECALLER, counselor=self.counselor, branch=self.branch1
        )

        # Telecaller 2 (Beta Branch)
        self.tc2 = User.objects.create_user(
            username="tc_beta", email="tc2@test.com", password="password123",
            role=UserRole.TELECALLER, branch=self.branch2
        )

        # Leads & Calls
        # Lead A: Dialed by TC1, 2 RNR calls (Repeat RNR)
        self.lead_a = Lead.objects.create(
            name="Lead A", phone="+919999999001", branch=self.branch1,
            assigned_counselor=self.counselor, assigned_telecaller=self.tc1,
            status=LeadStatus.CONTACTED, category=LeadCategory.TRAINING
        )
        CallHistory.objects.create(
            lead=self.lead_a, caller=self.tc1, telecaller=self.tc1,
            call_status=CallStatus.NO_ANSWER, call_outcome=CallOutcome.RNR, duration=0
        )
        CallHistory.objects.create(
            lead=self.lead_a, caller=self.tc1, telecaller=self.tc1,
            call_status=CallStatus.BUSY, call_outcome=CallOutcome.RNR, duration=0
        )

        # Lead B: Dialed by TC1, 1 Connected call
        self.lead_b = Lead.objects.create(
            name="Lead B", phone="+919999999002", branch=self.branch1,
            assigned_counselor=self.counselor, assigned_telecaller=self.tc1,
            status=LeadStatus.JOINED, category=LeadCategory.PLACEMENT
        )
        CallHistory.objects.create(
            lead=self.lead_b, caller=self.tc1, telecaller=self.tc1,
            call_status=CallStatus.COMPLETED, call_outcome=CallOutcome.CONVERTED, duration=150
        )

    def test_telecaller_rnr_report_view(self):
        self.client.login(username="admin_rep", password="password123")
        url = reverse('telecaller_rnr_report')
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

        # Overall summary assertions
        summary = response.context['summary']
        self.assertEqual(summary['overall_total_calls'], 3)
        self.assertEqual(summary['overall_connected_calls'], 1)
        self.assertEqual(summary['overall_rnr_calls'], 2)
        self.assertEqual(summary['overall_unique_rnr_leads'], 1)
        self.assertEqual(summary['overall_repeat_rnr_leads'], 1)

        # Rows check for TC1
        rows = response.context['rows']
        tc1_row = next(r for r in rows if r['telecaller'].username == 'tc_alpha')
        self.assertEqual(tc1_row['total_calls'], 3)
        self.assertEqual(tc1_row['rnr_calls'], 2)
        self.assertEqual(tc1_row['connected_calls'], 1)
        self.assertEqual(tc1_row['unique_rnr_leads'], 1)
        self.assertEqual(tc1_row['repeat_rnr_leads'], 1)
        self.assertEqual(tc1_row['avg_attempts_per_rnr'], 2.0)

    def test_telecaller_rnr_report_csv_export(self):
        self.client.login(username="admin_rep", password="password123")
        url = reverse('telecaller_rnr_report')
        response = self.client.get(url, {'export': 'csv'})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'text/csv')
        self.assertIn('attachment; filename="telecaller_rnr_report_', response['Content-Disposition'])

        content = response.content.decode('utf-8')
        self.assertIn('Telecaller Name,Username,Branch,Supervising Counselor', content)
        self.assertIn('tc_alpha', content)

    def test_management_charts_api(self):
        self.client.login(username="admin_rep", password="password123")
        url = reverse('management_charts_api')
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

        json_data = response.json()
        self.assertIn('status_chart', json_data)
        self.assertIn('category_chart', json_data)
        self.assertIn('telecaller_chart', json_data)
        self.assertIn('counselor_chart', json_data)

        # Check Category chart data: 1 Training (Lead A), 1 Placement (Lead B)
        cat_chart = json_data['category_chart']
        self.assertEqual(cat_chart['labels'], ['Training', 'Placement'])
        self.assertEqual(cat_chart['data'], [1, 1])

        # Check Telecaller chart data
        tc_chart = json_data['telecaller_chart']
        self.assertIn('tc_alpha', str(tc_chart['labels']))
        self.assertEqual(tc_chart['connected'], [1])
        self.assertEqual(tc_chart['rnr'], [2])

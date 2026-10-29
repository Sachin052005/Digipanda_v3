import json
from django.test import TestCase, Client
from django.urls import reverse
from django.utils import timezone
from accounts.models import User, UserRole
from branches.models import Branch
from leads.models import Lead, LeadStatus
from calls.models import CallHistory, CallStatus, CallOutcome
from reports.services import get_telecaller_rnr_report_data, get_telecaller_rnr_lead_details


class TelecallerRNRKpiTestCase(TestCase):
    def setUp(self):
        self.client = Client()
        self.branch = Branch.objects.create(name="Madurai Branch")

        self.admin = User.objects.create_user(
            username="admin_rnr_test",
            email="admin_rnr@test.com",
            password="Password@123",
            role=UserRole.ADMIN,
            branch=self.branch
        )

        self.tc1 = User.objects.create_user(
            username="tc1_rnr",
            email="tc1@test.com",
            password="Password@123",
            role=UserRole.TELECALLER,
            branch=self.branch
        )

        self.tc2 = User.objects.create_user(
            username="tc2_rnr",
            email="tc2@test.com",
            password="Password@123",
            role=UserRole.TELECALLER,
            branch=self.branch
        )

        # 3 Leads
        self.lead1 = Lead.objects.create(
            name="RNR Lead 1",
            phone="9876543211",
            branch=self.branch,
            assigned_telecaller=self.tc1,
            status=LeadStatus.NEW
        )
        self.lead2 = Lead.objects.create(
            name="RNR Lead 2",
            phone="9876543212",
            branch=self.branch,
            assigned_telecaller=self.tc1,
            status=LeadStatus.NEW
        )
        self.lead3 = Lead.objects.create(
            name="RNR Lead 3",
            phone="9876543213",
            branch=self.branch,
            assigned_telecaller=self.tc2,
            status=LeadStatus.NEW
        )

        # Now create 6 calls as specified in test case:
        # Lead 1: 3 calls by TC1 (all RNR)
        for i in range(3):
            CallHistory.objects.create(
                lead=self.lead1,
                caller=self.tc1,
                telecaller=self.tc1,
                call_status=CallStatus.NO_ANSWER,
                call_outcome=CallOutcome.RNR,
                duration=0
            )

        # Lead 2: 2 calls (1 by TC1, 1 by TC2, both RNR)
        CallHistory.objects.create(
            lead=self.lead2,
            caller=self.tc1,
            telecaller=self.tc1,
            call_status=CallStatus.NO_ANSWER,
            call_outcome=CallOutcome.RNR,
            duration=0
        )
        CallHistory.objects.create(
            lead=self.lead2,
            caller=self.tc2,
            telecaller=self.tc2,
            call_status=CallStatus.NO_ANSWER,
            call_outcome=CallOutcome.RNR,
            duration=0
        )

        # Lead 3: 1 call by TC2 (RNR)
        CallHistory.objects.create(
            lead=self.lead3,
            caller=self.tc2,
            telecaller=self.tc2,
            call_status=CallStatus.NO_ANSWER,
            call_outcome=CallOutcome.RNR,
            duration=0
        )

    def test_rnr_kpi_calculations_without_duplicate_inflation(self):
        """
        Verify that overall summary accurately counts distinct leads:
        - 6 total calls
        - 3 unique RNR leads
        - 2 repeat RNR leads (>=2 calls)
        - Average attempts = 6 / 3 = 2.0
        """
        data = get_telecaller_rnr_report_data(branch_ids=[self.branch.id])
        summary = data['summary']

        self.assertEqual(summary['overall_total_calls'], 6)
        self.assertEqual(summary['overall_rnr_calls'], 6)
        self.assertEqual(summary['overall_unique_rnr_leads'], 3, "Unique RNR leads must be 3 distinct leads")
        self.assertEqual(summary['overall_repeat_rnr_leads'], 2, "Repeat RNR leads must be 2 distinct leads with >=2 attempts")
        self.assertEqual(summary['overall_avg_attempts_per_rnr'], 2.0)

    def test_drilldown_api_unique_and_repeat_rnr(self):
        """Verify the drilldown API returns correct distinct leads and histories."""
        self.client.force_login(self.admin)

        # Unique RNR: should return 3 leads
        url_unique = f"{reverse('telecaller_rnr_lead_drilldown')}?type=unique_rnr&branch={self.branch.id}"
        res = self.client.get(url_unique)
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data['total_count'], 3)
        lead_ids = [l['lead_id'] for l in data['leads']]
        self.assertCountEqual(lead_ids, [self.lead1.id, self.lead2.id, self.lead3.id])

        # Repeat RNR: should return 2 leads (lead1 with 3, lead2 with 2)
        url_repeat = f"{reverse('telecaller_rnr_lead_drilldown')}?type=repeat_rnr&branch={self.branch.id}"
        res_repeat = self.client.get(url_repeat)
        self.assertEqual(res_repeat.status_code, 200)
        data_repeat = res_repeat.json()
        self.assertEqual(data_repeat['total_count'], 2)
        repeat_lead_ids = [l['lead_id'] for l in data_repeat['leads']]
        self.assertCountEqual(repeat_lead_ids, [self.lead1.id, self.lead2.id])

        # Test CSV export
        url_csv = f"{reverse('telecaller_rnr_lead_drilldown')}?type=unique_rnr&branch={self.branch.id}&export=csv"
        res_csv = self.client.get(url_csv)
        self.assertEqual(res_csv.status_code, 200)
        self.assertEqual(res_csv['Content-Type'], 'text/csv')
        csv_content = res_csv.content.decode('utf-8')
        self.assertIn("RNR Lead 1", csv_content)
        self.assertIn("RNR Lead 2", csv_content)
        self.assertIn("RNR Lead 3", csv_content)

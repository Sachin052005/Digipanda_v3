from django.test import TestCase, Client
from django.urls import reverse
from django.utils import timezone
from datetime import timedelta, datetime

from accounts.models import User, UserRole
from branches.models import Branch
from leads.models import Lead, LeadStatus, LeadCategory
from calls.models import CallHistory, CallOutcome, CallStatus
from followups.models import FollowUp, FollowUpStatus


class BranchHeadDashboardTestCase(TestCase):
    def setUp(self):
        self.client = Client()
        self.branch_a = Branch.objects.create(name="North Branch", status="Active")
        self.branch_b = Branch.objects.create(name="South Branch", status="Active")

        # Branch Head for Branch A
        self.bh_user = User.objects.create_user(
            username="bh_north", email="bhnorth@test.com", password="password123",
            role=UserRole.BRANCH_HEAD, branch=self.branch_a
        )

        # Counselor under Branch A
        self.counselor_a = User.objects.create_user(
            username="counselor_north", email="cnorth@test.com", password="password123",
            role=UserRole.COUNSELOR, branch=self.branch_a
        )

        # Telecaller under Branch A
        self.telecaller_a = User.objects.create_user(
            username="telecaller_north", email="tnorth@test.com", password="password123",
            role=UserRole.TELECALLER, counselor=self.counselor_a, branch=self.branch_a
        )

        # Leads for Branch A:
        # Lead 1: Created Today, Contacted, has an RNR call
        self.lead_today = Lead.objects.create(
            name="Today Lead", phone="+919876543201", branch=self.branch_a,
            assigned_counselor=self.counselor_a, assigned_telecaller=self.telecaller_a,
            status=LeadStatus.CONTACTED, category=LeadCategory.TRAINING
        )
        CallHistory.objects.create(
            lead=self.lead_today, caller=self.telecaller_a, telecaller=self.telecaller_a,
            call_status=CallStatus.NO_ANSWER, call_outcome=CallOutcome.RNR, duration=0
        )

        # Lead 2: Created Today, Joined
        self.lead_joined = Lead.objects.create(
            name="Joined Lead", phone="+919876543202", branch=self.branch_a,
            assigned_counselor=self.counselor_a, assigned_telecaller=self.telecaller_a,
            status=LeadStatus.JOINED, category=LeadCategory.PLACEMENT
        )

        # Lead 3: Under Branch B (should not appear in Branch A dashboard)
        self.lead_branch_b = Lead.objects.create(
            name="Other Branch Lead", phone="+919876543203", branch=self.branch_b,
            status=LeadStatus.NEW
        )

    def test_branch_head_dashboard_default_view(self):
        self.client.login(username="bh_north", password="password123")
        url = reverse('branch_head_dashboard')
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

        # Only branch A leads should be counted (2 leads)
        self.assertEqual(response.context['branch_leads_count'], 2)
        self.assertEqual(response.context['attended_leads_count'], 2)
        self.assertEqual(response.context['joined_count'], 1)
        self.assertEqual(response.context['rnr_leads_count'], 1)

        # Counselor performance breakdown check
        c_perf = list(response.context['counselor_perf'])
        self.assertEqual(len(c_perf), 1)
        self.assertEqual(c_perf[0].lead_count, 2)
        self.assertEqual(c_perf[0].joined_count, 1)

        # Telecaller performance breakdown check
        t_perf = list(response.context['telecaller_perf'])
        self.assertEqual(len(t_perf), 1)
        self.assertEqual(t_perf[0].lead_count, 2)
        self.assertEqual(t_perf[0].call_count, 1)
        self.assertEqual(t_perf[0].rnr_count, 1)

    def test_branch_head_dashboard_period_filtering(self):
        self.client.login(username="bh_north", password="password123")
        url = reverse('branch_head_dashboard')

        # Filter period=today
        resp_today = self.client.get(url, {'period': 'today'})
        self.assertEqual(resp_today.status_code, 200)
        self.assertEqual(resp_today.context['branch_leads_count'], 2)

        # Filter period=month
        resp_month = self.client.get(url, {'period': 'month'})
        self.assertEqual(resp_month.status_code, 200)
        self.assertEqual(resp_month.context['branch_leads_count'], 2)

        # Custom date range in the past with 0 leads
        past_date = (timezone.localdate() - timedelta(days=60)).strftime('%Y-%m-%d')
        resp_custom = self.client.get(url, {
            'period': 'custom',
            'start_date': past_date,
            'end_date': past_date
        })
        self.assertEqual(resp_custom.status_code, 200)
        self.assertEqual(resp_custom.context['branch_leads_count'], 0)

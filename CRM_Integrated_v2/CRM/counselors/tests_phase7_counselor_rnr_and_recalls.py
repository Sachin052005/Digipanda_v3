from django.test import TestCase, Client
from django.urls import reverse
from django.utils import timezone
from datetime import timedelta

from accounts.models import User, UserRole
from branches.models import Branch
from leads.models import Lead, LeadStatus, LeadCategory
from calls.models import CallHistory, CallOutcome, CallStatus
from followups.models import FollowUp, FollowUpStatus


class CounselorRNRAndRecallsTestCase(TestCase):
    def setUp(self):
        self.client = Client()
        self.branch1 = Branch.objects.create(name="Central Branch", status="Active")
        self.branch2 = Branch.objects.create(name="South Branch", status="Active")

        # Admin user
        self.admin = User.objects.create_user(
            username="admin_test", email="admin@test.com", password="adminpassword123",
            role=UserRole.ADMIN, is_staff=True, is_superuser=True
        )

        # Counselor 1 (Branch 1)
        self.counselor1 = User.objects.create_user(
            username="counselor_one", email="c1@test.com", password="password123",
            role=UserRole.COUNSELOR, branch=self.branch1
        )

        # Counselor 2 (Branch 2)
        self.counselor2 = User.objects.create_user(
            username="counselor_two", email="c2@test.com", password="password123",
            role=UserRole.COUNSELOR, branch=self.branch2
        )

        # Branch Head for Branch 1
        self.bh1 = User.objects.create_user(
            username="bh_one", email="bh1@test.com", password="password123",
            role=UserRole.BRANCH_HEAD, branch=self.branch1
        )

        # Telecaller under Counselor 1
        self.tc1 = User.objects.create_user(
            username="tc_one", email="tc1@test.com", password="password123",
            role=UserRole.TELECALLER, counselor=self.counselor1, branch=self.branch1
        )

        # Create Leads
        # Lead A: Assigned to TC1, has 2 RNR calls (Repeat RNR)
        self.lead_a = Lead.objects.create(
            name="Alice Smith", phone="+919876543210", email="alice@test.com",
            branch=self.branch1, assigned_counselor=self.counselor1,
            assigned_telecaller=self.tc1, status=LeadStatus.CONTACTED,
            category=LeadCategory.TRAINING
        )
        CallHistory.objects.create(
            lead=self.lead_a, caller=self.tc1, telecaller=self.tc1,
            call_status=CallStatus.NO_ANSWER, call_outcome=CallOutcome.RNR,
            call_started_at=timezone.now() - timedelta(hours=3), duration=0
        )
        CallHistory.objects.create(
            lead=self.lead_a, caller=self.tc1, telecaller=self.tc1,
            call_status=CallStatus.BUSY, call_outcome=CallOutcome.RNR,
            call_started_at=timezone.now() - timedelta(hours=1), duration=0
        )

        # Lead B: Assigned directly to Counselor 1, 1 Connected call (Not RNR)
        self.lead_b = Lead.objects.create(
            name="Bob Jones", phone="+919876543211", email="bob@test.com",
            branch=self.branch1, assigned_counselor=self.counselor1,
            status=LeadStatus.VISITED, category=LeadCategory.PLACEMENT
        )
        CallHistory.objects.create(
            lead=self.lead_b, caller=self.counselor1,
            call_status=CallStatus.COMPLETED, call_outcome=CallOutcome.INTERESTED,
            call_started_at=timezone.now() - timedelta(days=1), duration=120
        )

        # FollowUps: One overdue for Lead A
        self.fu_a = FollowUp.objects.create(
            lead=self.lead_a, assigned_user=self.counselor1,
            follow_up_date=timezone.localdate() - timedelta(days=1),
            status=FollowUpStatus.PENDING, notes="Recall overdue after RNR"
        )
        # FollowUp: One due today for Lead B
        self.fu_b = FollowUp.objects.create(
            lead=self.lead_b, assigned_user=self.counselor1,
            follow_up_date=timezone.localdate(),
            status=FollowUpStatus.PENDING, notes="Callback requested today"
        )

    def test_counselor_rnr_leads_view(self):
        self.client.login(username="counselor_one", password="password123")
        url = reverse('counselor_rnr_leads')
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

        # Unique RNR lead count should be 1 (Lead A)
        self.assertEqual(response.context['unique_rnr_count'], 1)
        self.assertEqual(response.context['repeat_rnr_count'], 1)
        self.assertEqual(response.context['total_rnr_attempts'], 2)
        self.assertEqual(response.context['overdue_recalls_count'], 1)

        # Check last_three_calls property
        leads = list(response.context['page_obj'])
        self.assertEqual(len(leads), 1)
        self.assertEqual(leads[0].id, self.lead_a.id)
        self.assertEqual(len(leads[0].last_three_calls), 2)

    def test_counselor_unpicked_recalls_view(self):
        self.client.login(username="counselor_one", password="password123")
        url = reverse('counselor_unpicked_recalls')
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

        # Check counts
        self.assertEqual(response.context['total_recalls_count'], 2)
        self.assertEqual(response.context['overdue_count'], 1)
        self.assertEqual(response.context['due_today_count'], 1)

        # Filter by overdue
        resp_overdue = self.client.get(url, {'type': 'overdue'})
        self.assertEqual(resp_overdue.status_code, 200)
        recalls = list(resp_overdue.context['page_obj'])
        self.assertEqual(len(recalls), 1)
        self.assertEqual(recalls[0].id, self.fu_a.id)

    def test_admin_counselor_leads_drilldown_view(self):
        self.client.login(username="admin_test", password="adminpassword123")
        url = reverse('admin_counselor_leads_drilldown', kwargs={'pk': self.counselor1.pk})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

        self.assertEqual(response.context['total_leads'], 2)
        self.assertEqual(response.context['rnr_leads_count'], 1)

        # Filter by special_filter=rnr
        resp_rnr = self.client.get(url, {'special_filter': 'rnr'})
        leads = list(resp_rnr.context['page_obj'])
        self.assertEqual(len(leads), 1)
        self.assertEqual(leads[0].id, self.lead_a.id)

        # Filter by category=Placement
        resp_cat = self.client.get(url, {'category': 'Placement'})
        leads_cat = list(resp_cat.context['page_obj'])
        self.assertEqual(len(leads_cat), 1)
        self.assertEqual(leads_cat[0].id, self.lead_b.id)

    def test_branch_head_scoping_on_drilldown(self):
        # Branch Head 1 should access Counselor 1 (same branch)
        self.client.login(username="bh_one", password="password123")
        url1 = reverse('admin_counselor_leads_drilldown', kwargs={'pk': self.counselor1.pk})
        resp1 = self.client.get(url1)
        self.assertEqual(resp1.status_code, 200)

        # Branch Head 1 should NOT be allowed to access Counselor 2 (different branch)
        url2 = reverse('admin_counselor_leads_drilldown', kwargs={'pk': self.counselor2.pk})
        resp2 = self.client.get(url2)
        self.assertEqual(resp2.status_code, 403)

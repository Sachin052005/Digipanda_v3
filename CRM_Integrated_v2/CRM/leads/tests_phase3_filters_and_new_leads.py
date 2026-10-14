from django.test import TestCase, Client
from django.urls import reverse
from django.utils import timezone
from datetime import timedelta

from accounts.models import User, UserRole
from branches.models import Branch
from products.models import Product
from lead_channels.models import Channel
from leads.models import Lead, LeadStatus, LeadCategory
from calls.models import CallHistory, CallOutcome, CallStatus
from followups.models import FollowUp, FollowUpStatus


class AdminFiltersAndNewLeadsTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.admin = User.objects.create_user(
            username="admin_p3",
            password="Password123!",
            role=UserRole.ADMIN,
            is_staff=True,
            is_superuser=True
        )
        self.branch1 = Branch.objects.create(name="Chennai Main", status="Active")
        self.branch2 = Branch.objects.create(name="Bangalore Central", status="Active")

        self.telecaller = User.objects.create_user(
            username="telecaller_p3",
            password="Password123!",
            role=UserRole.TELECALLER,
            branch=self.branch1,
            first_name="Anitha",
            last_name="S"
        )
        self.counselor = User.objects.create_user(
            username="counselor_p3",
            password="Password123!",
            role=UserRole.COUNSELOR,
            branch=self.branch1,
            first_name="Manoj",
            last_name="K"
        )

        self.product = Product.objects.create(name="AI & ML Masters", price=30000)
        self.channel = Channel.objects.create(name="Website Inquiries", status="Active")

        # Lead 1: New, Training, assigned to telecaller & counselor
        self.lead_new = Lead.objects.create(
            name="Vikram New",
            phone="9876543210",
            email="vikram@example.com",
            status=LeadStatus.NEW,
            category=LeadCategory.TRAINING,
            branch=self.branch1,
            assigned_telecaller=self.telecaller,
            assigned_counselor=self.counselor,
            product=self.product,
            channel=self.channel,
            source="Meta Ads"
        )

        # Lead 2: Interested, Placement
        self.lead_interested = Lead.objects.create(
            name="Deepa Placement",
            phone="9876543211",
            email="deepa@example.com",
            status=LeadStatus.INTERESTED,
            category=LeadCategory.PLACEMENT,
            branch=self.branch2,
            source="Walk-in"
        )

        # Lead 3: Converted
        self.lead_converted = Lead.objects.create(
            name="Karan Converted",
            phone="9876543212",
            status=LeadStatus.CONVERTED,
            category=LeadCategory.TRAINING,
            branch=self.branch1,
            source="Google"
        )

        # Add Call and Followup to lead_new
        today = timezone.now().date()
        self.call = CallHistory.objects.create(
            lead=self.lead_new,
            caller=self.telecaller,
            call_status=CallStatus.COMPLETED,
            call_outcome=CallOutcome.INTERESTED,
            call_started_at=timezone.now(),
            duration=120
        )
        self.followup = FollowUp.objects.create(
            lead=self.lead_new,
            assigned_user=self.counselor,
            follow_up_date=today + timedelta(days=2),
            status=FollowUpStatus.PENDING,
            notes="Counseling demo session"
        )

    def test_admin_leads_list_custom_filters(self):
        self.client.force_login(self.admin)
        url = reverse('admin_leads_list')

        # Filter by Category: Placement
        resp = self.client.get(url, {'category': 'Placement'})
        self.assertEqual(resp.status_code, 200)
        leads = list(resp.context['page_obj'])
        self.assertEqual(len(leads), 1)
        self.assertEqual(leads[0].id, self.lead_interested.id)

        # Filter by Category: Training
        resp_train = self.client.get(url, {'category': 'Training'})
        self.assertEqual(resp_train.status_code, 200)
        self.assertEqual(len(resp_train.context['page_obj']), 2)

        # Filter by Counselor
        resp_couns = self.client.get(url, {'counselor': self.counselor.id})
        self.assertEqual(resp_couns.status_code, 200)
        self.assertEqual(len(resp_couns.context['page_obj']), 1)
        self.assertEqual(resp_couns.context['page_obj'][0].id, self.lead_new.id)

        # Filter by Source: Meta
        resp_src = self.client.get(url, {'source': 'Meta'})
        self.assertEqual(resp_src.status_code, 200)
        self.assertEqual(len(resp_src.context['page_obj']), 1)
        self.assertEqual(resp_src.context['page_obj'][0].id, self.lead_new.id)

        # Filter by Last Contact Date
        today_str = timezone.now().date().isoformat()
        resp_call = self.client.get(url, {'last_contact_date': today_str})
        self.assertEqual(resp_call.status_code, 200)
        self.assertEqual(len(resp_call.context['page_obj']), 1)
        self.assertEqual(resp_call.context['page_obj'][0].id, self.lead_new.id)

        # Filter by Next Follow-up Date
        fu_date_str = (timezone.now().date() + timedelta(days=2)).isoformat()
        resp_fu = self.client.get(url, {'next_followup_date': fu_date_str})
        self.assertEqual(resp_fu.status_code, 200)
        self.assertEqual(len(resp_fu.context['page_obj']), 1)
        self.assertEqual(resp_fu.context['page_obj'][0].id, self.lead_new.id)

    def test_admin_new_leads_view(self):
        self.client.force_login(self.admin)
        url = reverse('admin_new_leads')

        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        # Only lead_new has status='New'
        self.assertEqual(response.context['new_leads_count'], 1)
        page_leads = list(response.context['page_obj'])
        self.assertEqual(len(page_leads), 1)
        ld = page_leads[0]
        self.assertEqual(ld.id, self.lead_new.id)
        self.assertEqual(ld.name, "Vikram New")
        self.assertEqual(ld.status, LeadStatus.NEW)
        self.assertEqual(ld.category, LeadCategory.TRAINING)
        self.assertIsNotNone(ld.latest_call)
        self.assertIsNotNone(ld.next_followup)

    def test_admin_new_leads_permission_denied_for_telecaller(self):
        self.client.force_login(self.telecaller)
        url = reverse('admin_new_leads')
        response = self.client.get(url)
        # telecaller should be redirected or forbidden by @admin_required
        self.assertIn(response.status_code, [302, 403])

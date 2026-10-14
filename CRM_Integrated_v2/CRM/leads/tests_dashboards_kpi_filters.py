from django.test import TestCase, Client
from django.urls import reverse
from django.utils import timezone
from datetime import timedelta
from accounts.models import User, UserRole
from branches.models import Branch
from leads.models import Lead, LeadStatus
from followups.models import FollowUp, FollowUpStatus
from calls.models import CallHistory


class DashboardKpiAndFiltersTestCase(TestCase):
    def setUp(self):
        self.client = Client()
        self.branch = Branch.objects.create(name="Anna Nagar Branch", status="Active")

        # Create users for all roles
        self.admin = User.objects.create_superuser(
            username="admin_user", email="admin@crm.com", password="Password@123", role=UserRole.ADMIN
        )
        self.sales_head = User.objects.create_user(
            username="sales_head_user", email="sales@crm.com", password="Password@123",
            role=UserRole.SALES_HEAD, branch=self.branch
        )
        self.branch_head = User.objects.create_user(
            username="branch_head_user", email="bh@crm.com", password="Password@123",
            role=UserRole.BRANCH_HEAD, branch=self.branch
        )
        self.counselor = User.objects.create_user(
            username="counselor_user", email="counselor@crm.com", password="Password@123",
            role=UserRole.COUNSELOR, branch=self.branch
        )
        self.telecaller = User.objects.create_user(
            username="telecaller_user", email="tc@crm.com", password="Password@123",
            role=UserRole.TELECALLER, branch=self.branch, counselor=self.counselor
        )
        self.receptionist = User.objects.create_user(
            username="receptionist_user", email="rec@crm.com", password="Password@123",
            role=UserRole.RECEPTIONIST, branch=self.branch
        )

        # Create test leads
        self.lead1 = Lead.objects.create(
            name="John Doe", phone="9876543210", email="john@example.com",
            branch=self.branch, assigned_counselor=self.counselor,
            assigned_telecaller=self.telecaller, assigned_sales_head=self.sales_head,
            status=LeadStatus.NEW, source="Website"
        )
        self.lead2 = Lead.objects.create(
            name="Jane Walkin", phone="9876543211", email="jane@example.com",
            branch=self.branch, assigned_counselor=self.counselor,
            status=LeadStatus.VISITED, source="Walk-in"
        )

    def test_counselor_dashboard_kpis_and_filters(self):
        self.client.force_login(self.counselor)
        # 1. Base dashboard check
        response = self.client.get(reverse('counselor_dashboard'))
        self.assertEqual(response.status_code, 200)
        # Check clickable KPI links present in content
        self.assertContains(response, reverse('counselor_leads_list'))
        self.assertContains(response, f"{reverse('counselor_leads_list')}?status=Visited")
        self.assertContains(response, f"{reverse('counselor_leads_list')}?status=Counseling")
        self.assertContains(response, f"{reverse('counselor_followups_list')}?status=Pending")
        self.assertContains(response, f"{reverse('counselor_leads_list')}?status=Enrolled")
        # Check period filter bar present
        self.assertContains(response, 'Period:')
        self.assertContains(response, '?period=today')
        self.assertContains(response, '?period=week')
        self.assertContains(response, '?period=month')

        # 2. Today filter check
        resp_today = self.client.get(reverse('counselor_dashboard'), {'period': 'today'})
        self.assertEqual(resp_today.status_code, 200)
        self.assertEqual(resp_today.context['period'], 'today')

        # 3. Custom date filter check
        today_str = timezone.localdate().strftime('%Y-%m-%d')
        resp_custom = self.client.get(reverse('counselor_dashboard'), {
            'period': 'custom', 'start_date': today_str, 'end_date': today_str
        })
        self.assertEqual(resp_custom.status_code, 200)

    def test_telecaller_dashboard_kpis_and_filters(self):
        self.client.force_login(self.telecaller)
        # 1. Base dashboard check
        response = self.client.get(reverse('telecaller_dashboard'))
        self.assertEqual(response.status_code, 200)
        # Check clickable KPI cards present in content
        self.assertContains(response, f"{reverse('telecaller_leads_list')}?filter=fresh_today")
        self.assertContains(response, f"{reverse('telecaller_followups_list')}?status=today")
        self.assertContains(response, f"{reverse('telecaller_calls_list')}?status=pending")
        self.assertContains(response, f"{reverse('telecaller_leads_list')}?filter=untouched_7")
        self.assertContains(response, f"{reverse('telecaller_leads_list')}?filter=untouched_15")
        self.assertContains(response, f"{reverse('telecaller_leads_list')}?filter=not_picked")
        # Check period filter bar present
        self.assertContains(response, 'Period:')
        self.assertContains(response, '?period=today')

        # 2. Week filter check
        resp_week = self.client.get(reverse('telecaller_dashboard'), {'period': 'week'})
        self.assertEqual(resp_week.status_code, 200)
        self.assertEqual(resp_week.context['period'], 'week')

    def test_branch_head_dashboard_kpis_and_filters(self):
        self.client.force_login(self.branch_head)
        # 1. Base dashboard check
        response = self.client.get(reverse('branch_head_dashboard'))
        self.assertEqual(response.status_code, 200)
        # Check clickable KPI cards present in content
        self.assertContains(response, reverse('branch_head_leads_list'))
        self.assertContains(response, f"{reverse('branch_head_leads_list')}?status_group=attended")
        self.assertContains(response, f"{reverse('branch_head_leads_list')}?status=Visited")
        self.assertContains(response, f"{reverse('branch_head_leads_list')}?status=Enrolled")
        self.assertContains(response, f"{reverse('branch_head_leads_list')}?status_group=rnr")
        self.assertContains(response, reverse('branch_head_telecallers_list'))

        # 2. Branch head leads list status_group filter check
        resp_attended = self.client.get(reverse('branch_head_leads_list'), {'status_group': 'attended'})
        self.assertEqual(resp_attended.status_code, 200)
        resp_rnr = self.client.get(reverse('branch_head_leads_list'), {'status_group': 'rnr'})
        self.assertEqual(resp_rnr.status_code, 200)

    def test_manager_dashboard_kpis_and_filters(self):
        self.client.force_login(self.sales_head)
        # 1. Base dashboard check
        response = self.client.get(reverse('manager_dashboard'))
        self.assertEqual(response.status_code, 200)
        # Check clickable KPI cards present in content
        self.assertContains(response, reverse('manager_leads_list'))
        self.assertContains(response, reverse('manager_telecallers_list'))
        self.assertContains(response, f"{reverse('manager_calls_list')}?date=today")
        self.assertContains(response, f"{reverse('manager_calls_list')}?status=Completed")
        self.assertContains(response, f"{reverse('manager_followups_list')}?status=Pending")
        self.assertContains(response, f"{reverse('manager_followups_list')}?status=Overdue")
        # Check period filter bar present
        self.assertContains(response, 'Period:')
        self.assertContains(response, '?period=month')

        # 2. Month filter check
        resp_month = self.client.get(reverse('manager_dashboard'), {'period': 'month'})
        self.assertEqual(resp_month.status_code, 200)
        self.assertEqual(resp_month.context['period'], 'month')

    def test_admin_dashboard_kpis_and_filters(self):
        self.client.force_login(self.admin)
        # 1. Base dashboard check
        response = self.client.get(reverse('admin_dashboard'))
        self.assertEqual(response.status_code, 200)
        # Check clickable KPI cards present in content
        self.assertContains(response, reverse('admin_leads_list'))
        self.assertContains(response, f"{reverse('admin_leads_list')}?status=New")
        self.assertContains(response, f"{reverse('admin_leads_list')}?status=active")
        self.assertContains(response, reverse('admin_managers_list'))
        self.assertContains(response, reverse('admin_branch_heads_list'))
        self.assertContains(response, reverse('admin_counselors_list'))
        self.assertContains(response, reverse('admin_telecallers_list'))
        self.assertContains(response, f"{reverse('admin_followups_list')}?status=pending")
        self.assertContains(response, f"{reverse('admin_followups_list')}?status=overdue")
        self.assertContains(response, reverse('admin_calls_list'))
        self.assertContains(response, f"{reverse('admin_calls_list')}?status=Completed")
        self.assertContains(response, reverse('admin_branches_list'))
        # Check Quick Period buttons present
        self.assertContains(response, 'Quick Period:')
        self.assertContains(response, '?period=today')

        # 2. Today filter check
        resp_today = self.client.get(reverse('admin_dashboard'), {'period': 'today'})
        self.assertEqual(resp_today.status_code, 200)
        self.assertEqual(resp_today.context['period'], 'today')

    def test_receptionist_dashboard_kpis_and_filters(self):
        self.client.force_login(self.receptionist)
        # 1. Base dashboard check
        response = self.client.get(reverse('receptionist_dashboard'))
        self.assertEqual(response.status_code, 200)
        # Check clickable KPI cards present in content
        self.assertContains(response, '?period=today')
        self.assertContains(response, '?assignment_filter=unassigned')
        self.assertContains(response, '?assignment_filter=assigned')
        self.assertContains(response, '?period=month')
        # Check period filter bar present
        self.assertContains(response, 'Period:')
        self.assertContains(response, 'name="from_date"')
        self.assertContains(response, 'name="to_date"')

        # 2. Period filter check
        resp_week = self.client.get(reverse('receptionist_dashboard'), {'period': 'week'})
        self.assertEqual(resp_week.status_code, 200)
        self.assertEqual(resp_week.context['period'], 'week')

from django.test import TestCase, Client
from django.urls import reverse
from accounts.models import User, UserRole
from branches.models import Branch
from leads.models import Lead, LeadStatus
from calls.models import CallHistory
from reports.services import get_dashboard_report_data, CANONICAL_CHANNELS


class DashboardReportIntegrationTests(TestCase):
    def setUp(self):
        self.branch1, _ = Branch.objects.get_or_create(name='Anna Nagar', defaults={'status': 'Active'})
        self.branch2, _ = Branch.objects.get_or_create(name='Velachery', defaults={'status': 'Active'})

        self.admin = User.objects.create_superuser(
            username='admin_test',
            password='password123',
            email='admin@test.com',
            role=UserRole.ADMIN
        )

        self.manager = User.objects.create_user(
            username='manager_test',
            password='password123',
            email='manager@test.com',
            role=UserRole.SALES_HEAD,
            branch=self.branch1
        )

        self.telecaller = User.objects.create_user(
            username='telecaller_test',
            password='password123',
            email='telecaller@test.com',
            role=UserRole.TELECALLER,
            branch=self.branch1
        )

        # Create sample leads
        self.lead1 = Lead.objects.create(
            name='Lead One',
            phone='9999911111',
            status=LeadStatus.NEW,
            source='WhatsApp',
            branch=self.branch1
        )
        self.lead2 = Lead.objects.create(
            name='Lead Two',
            phone='9999922222',
            status=LeadStatus.CONVERTED,
            source='Google Call',
            branch=self.branch2
        )

        # Create sample call
        self.call1 = CallHistory.objects.create(
            lead=self.lead1,
            caller=self.telecaller,
            call_status='Completed',
            call_outcome='Interested',
            duration=45
        )

    def test_admin_reports_access_and_rendering(self):
        client = Client()
        client.force_login(self.admin)

        response = client.get(reverse('admin_reports'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'CRM Dashboard')
        self.assertContains(response, 'Branch Wise Lead Summary')
        self.assertContains(response, 'Leads by Channel')
        self.assertContains(response, 'channelDonutChart')
        self.assertContains(response, 'branchStackedChart')
        self.assertContains(response, 'outcomesChart')

    def test_manager_reports_access_and_scoping(self):
        client = Client()
        client.force_login(self.manager)

        response = client.get(reverse('manager_reports'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'CRM Dashboard')
        self.assertContains(response, 'Branch Wise Lead Summary')

    def test_reports_api_data_endpoint(self):
        client = Client()
        client.force_login(self.admin)

        response = client.get(reverse('reports_api_data') + '?date_filter=all')
        self.assertEqual(response.status_code, 200)

        data = response.json()
        self.assertIn('kpi_total_leads', data)
        self.assertIn('channels', data)
        self.assertIn('branch_rows', data)
        self.assertIn('donut_chart', data)
        self.assertIn('stacked_chart', data)
        self.assertIn('outcomes_chart', data)
        self.assertEqual(data['kpi_total_leads'], 2)

    def test_reports_api_branch_filter(self):
        client = Client()
        client.force_login(self.admin)

        response = client.get(reverse('reports_api_data') + f'?date_filter=all&branch={self.branch1.id}')
        self.assertEqual(response.status_code, 200)

        data = response.json()
        self.assertEqual(data['kpi_total_leads'], 1)

    def test_unauthenticated_access_denied(self):
        client = Client()
        response = client.get(reverse('admin_reports'))
        # Should redirect to login
        self.assertIn(response.status_code, [302, 403])

    def test_services_data_aggregation(self):
        data = get_dashboard_report_data(self.admin, {'date_filter': 'all'})
        self.assertEqual(data['kpi_total_leads'], 2)
        self.assertEqual(data['converted_leads_count'], 1)
        self.assertEqual(len(data['canonical_channels']), 7)
        self.assertEqual(data['total_calls_count'], 1)

from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth import get_user_model
from branches.models import Branch
from leads.models import Lead, LeadStatus, LeadStatusHistory
from accounts.models import UserRole

User = get_user_model()


class UIModernizationEndpointsTestCase(TestCase):
    def setUp(self):
        self.client = Client()

        # Create Branches
        self.branch_a = Branch.objects.create(name="Chennai Branch")
        self.branch_b = Branch.objects.create(name="Bangalore Branch")

        # Create Users
        self.admin_user = User.objects.create_superuser(
            username="admin_test",
            password="password123",
            role=UserRole.ADMIN,
            is_staff=True,
            is_superuser=True
        )

        self.branch_head_a = User.objects.create_user(
            username="branch_head_a",
            password="password123",
            role=UserRole.BRANCH_HEAD,
            branch=self.branch_a
        )

        self.telecaller_a = User.objects.create_user(
            username="telecaller_a",
            password="password123",
            role=UserRole.TELECALLER,
            branch=self.branch_a
        )

        # Create Leads
        self.lead_a = Lead.objects.create(
            name="Ravi Kumar",
            phone="9876543210",
            email="ravi@example.com",
            branch=self.branch_a,
            status=LeadStatus.NEW,
            assigned_telecaller=self.telecaller_a
        )

        self.lead_b = Lead.objects.create(
            name="Suresh Raina",
            phone="9123456780",
            email="suresh@example.com",
            branch=self.branch_b,
            status=LeadStatus.NEW
        )

    def test_quick_search_requires_login(self):
        """Anonymous access must be redirected to login."""
        response = self.client.get(reverse('global_quick_search'), {'q': 'Ravi'})
        self.assertEqual(response.status_code, 302)

    def test_quick_search_min_query_length(self):
        """Queries shorter than 2 chars return empty results without hitting DB filter."""
        self.client.force_login(self.admin_user)
        response = self.client.get(reverse('global_quick_search'), {'q': 'R'})
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data['leads'], [])

    def test_quick_search_branch_isolation(self):
        """Branch Head A can search Lead A, but NOT Lead B (Branch B)."""
        self.client.force_login(self.branch_head_a)
        response = self.client.get(reverse('global_quick_search'), {'q': 'Suresh'})
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(len(data['leads']), 0)

        response = self.client.get(reverse('global_quick_search'), {'q': 'Ravi'})
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(len(data['leads']), 1)
        self.assertEqual(data['leads'][0]['name'], 'Ravi Kumar')

    def test_kanban_status_update_success(self):
        """Status update via API updates lead status and creates LeadStatusHistory."""
        self.client.force_login(self.admin_user)
        url = reverse('api_update_lead_status')
        payload = {
            'lead_id': self.lead_a.id,
            'new_status': LeadStatus.CONTACTED,
            'remarks': 'Moved via Kanban test'
        }
        response = self.client.post(url, payload, content_type='application/json')
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data['success'])
        self.assertEqual(data['new_status'], LeadStatus.CONTACTED)

        self.lead_a.refresh_from_db()
        self.assertEqual(self.lead_a.status, LeadStatus.CONTACTED)

        history = LeadStatusHistory.objects.filter(lead=self.lead_a, new_status=LeadStatus.CONTACTED)
        self.assertTrue(history.exists())

    def test_kanban_status_update_permission_denied(self):
        """Branch Head A cannot update Lead B belonging to Branch B."""
        self.client.force_login(self.branch_head_a)
        url = reverse('api_update_lead_status')
        payload = {
            'lead_id': self.lead_b.id,
            'new_status': LeadStatus.INTERESTED,
        }
        response = self.client.post(url, payload, content_type='application/json')
        self.assertEqual(response.status_code, 403)
        data = response.json()
        self.assertFalse(data['success'])

    def test_bulk_action_status_update(self):
        """Admin can bulk update multiple leads atomically."""
        self.client.force_login(self.admin_user)
        url = reverse('api_bulk_action')
        payload = {
            'action': 'status_update',
            'lead_ids': [self.lead_a.id, self.lead_b.id],
            'new_status': LeadStatus.FOLLOW_UP
        }
        response = self.client.post(url, payload, content_type='application/json')
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data['success'])
        self.assertEqual(data['updated_count'], 2)

        self.lead_a.refresh_from_db()
        self.lead_b.refresh_from_db()
        self.assertEqual(self.lead_a.status, LeadStatus.FOLLOW_UP)
        self.assertEqual(self.lead_b.status, LeadStatus.FOLLOW_UP)

    def test_kanban_view_renders_successfully(self):
        """Kanban page renders with 200 OK without FieldError or TemplateSyntaxError."""
        self.client.force_login(self.admin_user)
        response = self.client.get(reverse('leads_kanban'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Lead Pipeline (Kanban)')

    def test_complete_call_record_invalid_lead_id_returns_400(self):
        """Calling complete_call_record with empty or invalid lead_id returns 400 instead of 500."""
        self.client.force_login(self.telecaller_a)
        url = reverse('complete_call_record')
        # Empty lead_id
        response = self.client.post(url, {'lead_id': '', 'notes': 'Test notes'}, HTTP_X_REQUESTED_WITH='XMLHttpRequest')
        self.assertEqual(response.status_code, 400)
        data = response.json()
        self.assertFalse(data['success'])

    def test_admin_leads_list_and_recordings_templates_render(self):
        """Templates with static tags render without TemplateSyntaxError."""
        self.client.force_login(self.admin_user)
        response_leads = self.client.get(reverse('admin_leads_list'))
        self.assertEqual(response_leads.status_code, 200)

        response_recs = self.client.get(reverse('call_recordings_list'))
        self.assertEqual(response_recs.status_code, 200)


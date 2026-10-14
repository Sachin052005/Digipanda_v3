import json
from django.test import TestCase, Client
from django.urls import reverse
from django.utils import timezone
from accounts.models import User, UserRole
from branches.models import Branch
from lead_channels.models import Channel
from leads.models import Lead, VisitorStatus, LeadStatus, LeadAssignmentHistory, LeadOwnerType
from activities.models import Activity, Notification


class Phase6WalkinAndReceptionTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.admin = User.objects.create_user(
            username="admin_p6",
            email="admin_p6@example.com",
            password="AdminPassword123!",
            role=UserRole.ADMIN,
            is_staff=True,
            is_superuser=True
        )
        self.branch = Branch.objects.create(name="Trichy Main", status="Active")
        self.channel = Channel.objects.create(name="Walk-in", status="Active")

        self.counselor = User.objects.create_user(
            username="counselor_p6",
            email="counselor_p6@example.com",
            password="Password123!",
            role=UserRole.COUNSELOR,
            branch=self.branch,
            is_active=True
        )

    def test_log_walkin_visitor_without_immediate_counselor(self):
        """Front desk logs visitor into lobby waiting queue with token number."""
        self.client.login(username="admin_p6", password="AdminPassword123!")
        url = reverse('admin_walkin_create')

        payload = {
            'name': 'Kavitha Visitor',
            'phone': '9876543210',
            'email': 'kavitha@example.com',
            'branch_id': self.branch.id,
            'category': 'Training',
            'notes': 'Interested in Python Full Stack',
        }
        response = self.client.post(url, data=json.dumps(payload), content_type='application/json')
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data['success'])
        self.assertTrue(data['token_number'].startswith('WI-'))

        lead = Lead.objects.get(id=data['lead_id'])
        self.assertEqual(lead.name, 'Kavitha Visitor')
        self.assertEqual(lead.source, 'Walk-in')
        self.assertEqual(lead.visitor_status, VisitorStatus.WAITING)
        self.assertIsNone(lead.assigned_counselor)
        self.assertIsNotNone(lead.center_visit_date)

        # Check CRM Activity log
        activity = Activity.objects.filter(object_id=lead.id, action="Walk-in Visitor Checked In").first()
        self.assertIsNotNone(activity)

    def test_log_walkin_visitor_with_immediate_counselor_assignment(self):
        """Front desk logs visitor and immediately routes to available counselor."""
        self.client.login(username="admin_p6", password="AdminPassword123!")
        url = reverse('admin_walkin_create')

        payload = {
            'name': 'Manoj Visitor',
            'phone': '9876543211',
            'email': 'manoj@example.com',
            'branch_id': self.branch.id,
            'category': 'Placement',
            'counselor_id': self.counselor.id,
            'notes': 'Placement orientation',
        }
        response = self.client.post(url, data=json.dumps(payload), content_type='application/json')
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data['success'])

        lead = Lead.objects.get(id=data['lead_id'])
        self.assertEqual(lead.assigned_counselor, self.counselor)
        self.assertEqual(lead.visitor_status, VisitorStatus.IN_CONSULTATION)

        # Check counselor notification
        notification = Notification.objects.filter(recipient=self.counselor).first()
        self.assertIsNotNone(notification)
        self.assertIn('Manoj Visitor', notification.message)

    def test_assign_waiting_visitor_to_counselor(self):
        """Receptionist assigns a waiting visitor to a counselor from the desk queue."""
        self.client.login(username="admin_p6", password="AdminPassword123!")
        lead = Lead.objects.create(
            name="Suresh Visitor",
            phone="9876543212",
            branch=self.branch,
            channel=self.channel,
            source='Walk-in',
            visitor_status=VisitorStatus.WAITING,
            token_number="WI-20261012-005"
        )

        url = reverse('admin_walkin_assign_counselor', kwargs={'pk': lead.pk})
        payload = {
            'counselor_id': self.counselor.id,
            'reason': 'Receptionist called counselor for consultation'
        }
        response = self.client.post(url, data=json.dumps(payload), content_type='application/json')
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data['success'])

        lead.refresh_from_db()
        self.assertEqual(lead.assigned_counselor, self.counselor)
        self.assertEqual(lead.visitor_status, VisitorStatus.IN_CONSULTATION)

        history = LeadAssignmentHistory.objects.filter(lead=lead).latest('created_at')
        self.assertEqual(history.to_user, self.counselor)
        self.assertEqual(history.to_role, 'COUNSELOR')

    def test_update_visitor_status_and_desk_view(self):
        """Update visitor status to Completed and verify desk view reflects KPI updates."""
        self.client.login(username="admin_p6", password="AdminPassword123!")
        lead = Lead.objects.create(
            name="Deepa Visitor",
            phone="9876543213",
            branch=self.branch,
            channel=self.channel,
            source='Walk-in',
            visitor_status=VisitorStatus.IN_CONSULTATION,
            token_number="WI-20261012-006"
        )

        # Update status to Completed
        url = reverse('admin_walkin_update_status', kwargs={'pk': lead.pk})
        response = self.client.post(url, data=json.dumps({'visitor_status': 'Completed'}), content_type='application/json')
        self.assertEqual(response.status_code, 200)

        lead.refresh_from_db()
        self.assertEqual(lead.visitor_status, VisitorStatus.COMPLETED)
        self.assertEqual(lead.status, LeadStatus.VISITED)

        # Verify desk view page load
        desk_url = reverse('admin_walkin_desk')
        desk_res = self.client.get(desk_url)
        self.assertEqual(desk_res.status_code, 200)
        self.assertContains(desk_res, "Deepa Visitor")
        self.assertContains(desk_res, "WI-20261012-006")

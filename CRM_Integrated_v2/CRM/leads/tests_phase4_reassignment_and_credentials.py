import json
from django.test import TestCase, Client
from django.urls import reverse
from accounts.models import User, UserRole
from branches.models import Branch
from lead_channels.models import Channel
from leads.models import Lead, LeadAssignmentHistory, LeadOwnerType
from activities.models import Activity


class Phase4ReassignmentAndCredentialsTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.admin = User.objects.create_user(
            username="admin_p4",
            email="admin_p4@example.com",
            password="AdminPassword123!",
            role=UserRole.ADMIN,
            is_staff=True,
            is_superuser=True
        )
        self.branch1 = Branch.objects.create(name="Trichy Main", status="Active")
        self.branch2 = Branch.objects.create(name="Chennai Central", status="Active")

        self.counselor1 = User.objects.create_user(
            username="counselor_t1",
            email="counselor_t1@example.com",
            password="Password123!",
            role=UserRole.COUNSELOR,
            branch=self.branch1,
            is_active=True
        )
        self.counselor2 = User.objects.create_user(
            username="counselor_c2",
            email="counselor_c2@example.com",
            password="Password123!",
            role=UserRole.COUNSELOR,
            branch=self.branch2,
            is_active=True
        )

        self.telecaller1 = User.objects.create_user(
            username="telecaller_t1",
            email="telecaller_t1@example.com",
            password="Password123!",
            role=UserRole.TELECALLER,
            counselor=self.counselor1,
            branch=self.branch1,
            is_active=True
        )

        self.channel = Channel.objects.create(name="Website", status="Active")
        self.lead1 = Lead.objects.create(
            name="Alice Candidate",
            phone="9876500001",
            email="alice@example.com",
            branch=self.branch1,
            channel=self.channel,
            assigned_telecaller=self.telecaller1,
            current_owner_type=LeadOwnerType.TELECALLER
        )
        self.lead2 = Lead.objects.create(
            name="Bob Candidate",
            phone="9876500002",
            email="bob@example.com",
            branch=self.branch1,
            channel=self.channel,
            assigned_telecaller=self.telecaller1,
            current_owner_type=LeadOwnerType.TELECALLER
        )

    def test_single_lead_reassignment_to_counselor(self):
        """Admin or authorized user can reassign a lead to a counselor with audit history."""
        self.client.login(username="admin_p4", password="AdminPassword123!")
        url = reverse('api_reassign_lead_to_counselor', kwargs={'pk': self.lead1.pk})

        payload = {
            'counselor_id': self.counselor1.id,
            'reason': 'Escalated to counselor for course consultation'
        }
        response = self.client.post(url, data=json.dumps(payload), content_type='application/json')
        self.assertEqual(response.status_code, 200)
        resp_data = response.json()
        self.assertTrue(resp_data['success'])

        self.lead1.refresh_from_db()
        self.assertEqual(self.lead1.assigned_counselor, self.counselor1)
        self.assertEqual(self.lead1.current_owner_type, LeadOwnerType.COUNSELOR)

        # Check LeadAssignmentHistory audit trail
        history = LeadAssignmentHistory.objects.filter(lead=self.lead1).latest('created_at')
        self.assertEqual(history.from_user, self.telecaller1)
        self.assertEqual(history.to_user, self.counselor1)
        self.assertEqual(history.to_role, 'COUNSELOR')
        self.assertIn('Escalated to counselor', history.reason)

        # Check Activity log
        activity = Activity.objects.filter(object_id=self.lead1.id, action="Lead Reassigned to Counselor").first()
        self.assertIsNotNone(activity)

    def test_reassign_to_different_branch_forbidden_for_non_admin(self):
        """Reassigning across branch boundaries must be prevented for branch-scoped users."""
        self.client.login(username="counselor_t1", password="Password123!")
        url = reverse('api_reassign_lead_to_counselor', kwargs={'pk': self.lead1.pk})

        payload = {
            'counselor_id': self.counselor2.id,  # counselor2 is in branch2
            'reason': 'Cross branch transfer attempt'
        }
        response = self.client.post(url, data=json.dumps(payload), content_type='application/json')
        self.assertEqual(response.status_code, 403)

    def test_bulk_lead_reassignment_to_counselor(self):
        """Bulk action reassign_counselor atomically updates multiple leads."""
        self.client.login(username="admin_p4", password="AdminPassword123!")
        url = reverse('api_bulk_action')

        payload = {
            'action': 'reassign_counselor',
            'lead_ids': [self.lead1.id, self.lead2.id],
            'counselor_id': self.counselor1.id,
            'reason': 'Batch handoff to counselor'
        }
        response = self.client.post(url, data=json.dumps(payload), content_type='application/json')
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data['success'])
        self.assertEqual(data['updated_count'], 2)

        self.lead1.refresh_from_db()
        self.lead2.refresh_from_db()
        self.assertEqual(self.lead1.assigned_counselor, self.counselor1)
        self.assertEqual(self.lead2.assigned_counselor, self.counselor1)

    def test_auto_generated_credentials_sets_must_change_password(self):
        """When password is not provided in forms, credentials must be auto-generated and must_change_password set."""
        from counselors.forms import AdminCounselorCreateForm
        from branch_heads.forms import BranchHeadCreateForm
        from telecallers.forms import AdminTelecallerCreateForm

        # Counselor auto-password
        c_form = AdminCounselorCreateForm(allowed_branches=Branch.objects.all(), data={
            'first_name': 'Auto',
            'last_name': 'Counselor',
            'username': 'auto_counselor_1',
            'email': 'autocounselor1@example.com',
            'phone': '9111111111',
            'branch': self.branch1.id,
            'password': '',
            'confirm_password': '',
            'is_active': True,
        })
        self.assertTrue(c_form.is_valid(), c_form.errors)
        c_user = c_form.save()
        self.assertTrue(c_user.must_change_password)
        self.assertIsNotNone(c_user._generated_password)
        self.assertTrue(c_user.check_password(c_user._generated_password))

        # Telecaller auto-password
        t_form = AdminTelecallerCreateForm(data={
            'first_name': 'Auto',
            'last_name': 'Telecaller',
            'username': 'auto_telecaller_1',
            'email': 'autotelecaller1@example.com',
            'phone': '9222222222',
            'counselor': self.counselor1.id,
            'branch': self.branch1.id,
            'password': '',
            'confirm_password': '',
            'is_active': True,
        })
        self.assertTrue(t_form.is_valid(), t_form.errors)
        t_user = t_form.save()
        self.assertTrue(t_user.must_change_password)
        self.assertIsNotNone(t_user._generated_password)
        self.assertTrue(t_user.check_password(t_user._generated_password))

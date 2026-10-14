import json
from django.test import TestCase, Client
from django.urls import reverse
from django.utils import timezone
from django.core.exceptions import ValidationError
from datetime import timedelta

from accounts.models import User, UserRole
from accounts.credentials_service import setup_user_credentials
from branches.models import Branch
from lead_channels.models import Channel
from leads.models import Lead, LeadStatus, LeadCategory, VisitorStatus, LeadAssignmentHistory, GoogleSheetConnection, GoogleSheetRowMapping, DuplicateLeadRecord
from activities.models import Activity, Notification
from calls.models import CallHistory
from followups.models import FollowUp


class ReceptionistWorkflowTests(TestCase):
    def setUp(self):
        self.client = Client()

        # Branches
        self.branch_anna, _ = Branch.objects.get_or_create(name="Anna Nagar Central", defaults={'status': "Active"})
        self.branch_vela, _ = Branch.objects.get_or_create(name="Velachery Hub", defaults={'status': "Active"})

        # Admin
        self.admin = User.objects.create_user(
            username="admin_reception_test",
            password="Password123!",
            role=UserRole.ADMIN,
            is_staff=True,
            is_superuser=True
        )

        # Receptionist for Anna Nagar
        self.receptionist_anna = User.objects.create_user(
            username="receptionist_anna",
            password="Password123!",
            role=UserRole.RECEPTIONIST,
            branch=self.branch_anna,
            first_name="Priya",
            last_name="Sundar"
        )

        # Receptionist for Velachery
        self.receptionist_vela = User.objects.create_user(
            username="receptionist_vela",
            password="Password123!",
            role=UserRole.RECEPTIONIST,
            branch=self.branch_vela,
            first_name="Meena",
            last_name="K"
        )

        # Counselors
        self.counselor_anna = User.objects.create_user(
            username="counselor_anna_rec",
            password="Password123!",
            role=UserRole.COUNSELOR,
            branch=self.branch_anna,
            first_name="Anitha",
            is_active=True
        )
        self.counselor_anna_inactive = User.objects.create_user(
            username="counselor_anna_inact",
            password="Password123!",
            role=UserRole.COUNSELOR,
            branch=self.branch_anna,
            first_name="InactiveCounselor",
            is_active=False
        )
        self.counselor_vela = User.objects.create_user(
            username="counselor_vela_rec",
            password="Password123!",
            role=UserRole.COUNSELOR,
            branch=self.branch_vela,
            first_name="Karthik",
            is_active=True
        )

        # Regular Telecaller
        self.telecaller = User.objects.create_user(
            username="telecaller_test",
            password="Password123!",
            role=UserRole.TELECALLER,
            branch=self.branch_anna
        )

        # Channel
        self.walkin_channel, _ = Channel.objects.get_or_create(name='Walk-in', defaults={'status': 'Active'})

    # 1. Role & Validation Tests
    def test_receptionist_role_attributes(self):
        self.assertTrue(self.receptionist_anna.is_receptionist_user)
        self.assertEqual(self.receptionist_anna.role, UserRole.RECEPTIONIST)
        self.assertEqual(self.receptionist_anna.display_role, "Receptionist")

    def test_receptionist_requires_branch_in_clean(self):
        user_no_branch = User(
            username="receptionist_nobranch",
            role=UserRole.RECEPTIONIST
        )
        with self.assertRaises(ValidationError) as ctx:
            user_no_branch.clean()
        self.assertIn('branch', ctx.exception.message_dict)

    def test_receptionist_auto_credentials_and_must_change_password(self):
        new_rec = User(
            username="rec_auto_cred",
            role=UserRole.RECEPTIONIST,
            branch=self.branch_anna
        )
        user_saved, raw_pwd, was_auto = setup_user_credentials(new_rec, auto_generate=True)
        self.assertTrue(was_auto)
        self.assertTrue(user_saved.must_change_password)
        self.assertTrue(user_saved.check_password(raw_pwd))

    # 2. Login & Redirection Tests
    def test_receptionist_login_redirects_to_receptionist_dashboard(self):
        self.client.login(username="receptionist_anna", password="Password123!")
        res = self.client.get(reverse('login_redirect'), follow=False)
        self.assertRedirects(res, reverse('receptionist_dashboard'))

    def test_admin_walkin_desk_redirects_receptionist_to_dashboard(self):
        self.client.login(username="receptionist_anna", password="Password123!")
        res = self.client.get(reverse('admin_walkin_desk'), follow=False)
        self.assertRedirects(res, reverse('receptionist_dashboard'))

    def test_receptionist_login_portal_denies_wrong_role(self):
        # Counselor attempts to login via receptionist login
        res = self.client.post(reverse('receptionist_login'), {
            'username': 'counselor_anna_rec',
            'password': 'Password123!'
        })
        self.assertContains(res, "is not a Receptionist")

    # 3. Dashboard KPI and Isolation Tests
    def test_receptionist_dashboard_view_and_branch_isolation(self):
        now = timezone.now()
        # Create walk-in lead in Anna Nagar
        lead_anna = Lead.objects.create(
            name="Student Anna",
            phone="9876543211",
            branch=self.branch_anna,
            source="Walk-in",
            channel=self.walkin_channel,
            created_at=now,
            center_visit_date=now,
            visitor_status=VisitorStatus.WAITING,
            assignment_status="Pending Assignment"
        )
        # Create walk-in lead in Velachery
        lead_vela = Lead.objects.create(
            name="Student Velachery",
            phone="9876543212",
            branch=self.branch_vela,
            source="Walk-in",
            channel=self.walkin_channel,
            created_at=now,
            center_visit_date=now,
            visitor_status=VisitorStatus.WAITING,
            assignment_status="Pending Assignment"
        )

        self.client.login(username="receptionist_anna", password="Password123!")
        res = self.client.get(reverse('receptionist_dashboard'))
        self.assertEqual(res.status_code, 200)

        # Anna Nagar receptionist should see Student Anna, NOT Student Velachery
        self.assertContains(res, "Student Anna")
        self.assertNotContains(res, "Student Velachery")

        # KPI counts
        self.assertEqual(res.context['total_today'], 1)
        self.assertEqual(res.context['awaiting_assignment'], 1)
        self.assertEqual(res.context['assigned_today'], 0)
        self.assertEqual(res.context['total_this_month'], 1)

    def test_receptionist_dashboard_denies_unauthorized_roles(self):
        self.client.login(username="telecaller_test", password="Password123!")
        res = self.client.get(reverse('receptionist_dashboard'))
        self.assertEqual(res.status_code, 403)

    # 4. Student Registration Tests (admin_walkin_create)
    def test_receptionist_registers_walkin_student_with_token(self):
        self.client.login(username="receptionist_anna", password="Password123!")
        res = self.client.post(
            reverse('admin_walkin_create'),
            data=json.dumps({
                'name': 'Kavya Raman',
                'phone': '9123456789',
                'email': 'kavya@example.com',
                'category': 'Training',
                'notes': 'Looking for Python Fullstack weekend batch',
                # Even if another branch ID is maliciously submitted, it must force user.branch
                'branch_id': self.branch_vela.id
            }),
            content_type='application/json'
        )
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertTrue(data['success'])
        self.assertTrue(data['token_number'].startswith("WI-"))

        lead = Lead.objects.get(pk=data['lead_id'])
        self.assertEqual(lead.name, 'Kavya Raman')
        self.assertEqual(lead.branch, self.branch_anna)  # Enforced to Anna Nagar!
        self.assertEqual(lead.source, 'Walk-in')
        self.assertEqual(lead.assignment_status, 'Pending Assignment')
        self.assertEqual(lead.visitor_status, VisitorStatus.WAITING)

        # Verify activity logged
        act = Activity.objects.filter(object_id=str(lead.id), action="Walk-in Visitor Checked In").first()
        self.assertIsNotNone(act)

    def test_receptionist_registers_student_with_immediate_counselor(self):
        self.client.login(username="receptionist_anna", password="Password123!")
        res = self.client.post(
            reverse('admin_walkin_create'),
            data=json.dumps({
                'name': 'Ganesh M',
                'phone': '9876500001',
                'category': 'Placement',
                'counselor_id': self.counselor_anna.id
            }),
            content_type='application/json'
        )
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertTrue(data['success'])

        lead = Lead.objects.get(pk=data['lead_id'])
        self.assertEqual(lead.assigned_counselor, self.counselor_anna)
        self.assertEqual(lead.assignment_status, 'Assigned')
        self.assertEqual(lead.visitor_status, VisitorStatus.IN_CONSULTATION)

        # Verify notification sent to counselor
        notif = Notification.objects.filter(recipient=self.counselor_anna).first()
        self.assertIsNotNone(notif)
        self.assertIn("Walk-in Visitor Waiting", notif.title)

    def test_receptionist_cannot_assign_immediate_counselor_from_other_branch(self):
        self.client.login(username="receptionist_anna", password="Password123!")
        res = self.client.post(
            reverse('admin_walkin_create'),
            data=json.dumps({
                'name': 'Invalid Branch Counselor Test',
                'phone': '9876500002',
                'counselor_id': self.counselor_vela.id  # Belongs to Velachery
            }),
            content_type='application/json'
        )
        self.assertEqual(res.status_code, 400)
        data = res.json()
        self.assertFalse(data['success'])
        self.assertIn("Selected counselor belongs to a different branch", data['error'])

    # 5. Counselor Assignment Tests (admin_walkin_assign_counselor)
    def test_receptionist_assigns_waiting_lead_to_branch_counselor(self):
        lead = Lead.objects.create(
            name="Waiting Visitor",
            phone="9876512345",
            branch=self.branch_anna,
            source="Walk-in",
            visitor_status=VisitorStatus.WAITING,
            assignment_status="Pending Assignment"
        )
        self.client.login(username="receptionist_anna", password="Password123!")
        res = self.client.post(
            reverse('admin_walkin_assign_counselor', args=[lead.id]),
            data=json.dumps({
                'counselor_id': self.counselor_anna.id,
                'reason': 'Front desk consultation assignment'
            }),
            content_type='application/json'
        )
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertTrue(data['success'])

        lead.refresh_from_db()
        self.assertEqual(lead.assigned_counselor, self.counselor_anna)
        self.assertEqual(lead.visitor_status, VisitorStatus.IN_CONSULTATION)
        self.assertEqual(lead.assignment_status, 'Assigned')

        # Check assignment history
        hist = LeadAssignmentHistory.objects.filter(lead=lead, to_user=self.counselor_anna).first()
        self.assertIsNotNone(hist)
        self.assertEqual(hist.assigned_by, self.receptionist_anna)

    def test_receptionist_cannot_assign_lead_from_different_branch(self):
        lead_vela = Lead.objects.create(
            name="Velachery Student",
            phone="9876599999",
            branch=self.branch_vela,
            source="Walk-in"
        )
        self.client.login(username="receptionist_anna", password="Password123!")
        res = self.client.post(
            reverse('admin_walkin_assign_counselor', args=[lead_vela.id]),
            data=json.dumps({
                'counselor_id': self.counselor_anna.id
            }),
            content_type='application/json'
        )
        self.assertEqual(res.status_code, 403)

    def test_receptionist_cannot_assign_to_cross_branch_counselor(self):
        lead_anna = Lead.objects.create(
            name="Anna Student",
            phone="9876588888",
            branch=self.branch_anna,
            source="Walk-in"
        )
        self.client.login(username="receptionist_anna", password="Password123!")
        res = self.client.post(
            reverse('admin_walkin_assign_counselor', args=[lead_anna.id]),
            data=json.dumps({
                'counselor_id': self.counselor_vela.id  # Velachery counselor
            }),
            content_type='application/json'
        )
        self.assertEqual(res.status_code, 400)
        self.assertIn("Cannot assign to a counselor outside your branch", res.json()['error'])

    def test_receptionist_cannot_assign_to_inactive_counselor(self):
        lead_anna = Lead.objects.create(
            name="Anna Student",
            phone="9876577777",
            branch=self.branch_anna,
            source="Walk-in"
        )
        self.client.login(username="receptionist_anna", password="Password123!")
        res = self.client.post(
            reverse('admin_walkin_assign_counselor', args=[lead_anna.id]),
            data=json.dumps({
                'counselor_id': self.counselor_anna_inactive.id
            }),
            content_type='application/json'
        )
        # get_object_or_404 with is_active=True returns 404
        self.assertEqual(res.status_code, 404)

    # 6. Status Update Permission Tests (Receptionist Must Be Denied)
    def test_receptionist_denied_from_updating_visitor_or_lead_status(self):
        lead = Lead.objects.create(
            name="Status Update Student",
            phone="9876566666",
            branch=self.branch_anna,
            source="Walk-in",
            visitor_status=VisitorStatus.WAITING,
            status=LeadStatus.NEW
        )
        self.client.login(username="receptionist_anna", password="Password123!")
        res = self.client.post(
            reverse('admin_walkin_update_status', args=[lead.id]),
            data=json.dumps({'visitor_status': 'Completed'}),
            content_type='application/json'
        )
        self.assertEqual(res.status_code, 403)
        lead.refresh_from_db()
        self.assertEqual(lead.visitor_status, VisitorStatus.WAITING)
        self.assertEqual(lead.status, LeadStatus.NEW)

    def test_receptionist_cannot_update_status_on_other_branch_lead(self):
        lead_vela = Lead.objects.create(
            name="Vela Status Test",
            phone="9876555555",
            branch=self.branch_vela,
            source="Walk-in",
            visitor_status=VisitorStatus.WAITING
        )
        self.client.login(username="receptionist_anna", password="Password123!")
        res = self.client.post(
            reverse('admin_walkin_update_status', args=[lead_vela.id]),
            data=json.dumps({'visitor_status': 'Completed'}),
            content_type='application/json'
        )
        self.assertEqual(res.status_code, 403)

    # 6B. Lead History View Tests
    def test_receptionist_can_view_authorized_lead_complete_history(self):
        lead = Lead.objects.create(
            name="History Student",
            phone="9876543200",
            email="history@example.com",
            branch=self.branch_anna,
            source="Walk-in",
            status=LeadStatus.CONTACTED,
            notes="Initial inquiry at front desk"
        )
        # Create Call
        CallHistory.objects.create(
            lead=lead,
            caller=self.telecaller,
            call_started_at=timezone.now(),
            call_outcome="Interested in Python course",
            notes="Student requested syllabus"
        )
        # Create FollowUp
        FollowUp.objects.create(
            lead=lead,
            follow_up_date=(timezone.now() + timedelta(days=1)).date(),
            status="Pending",
            notes="Follow up about admission fee"
        )
        # Create Assignment History
        LeadAssignmentHistory.objects.create(
            lead=lead,
            from_user=None,
            to_user=self.counselor_anna,
            to_role="COUNSELOR",
            assigned_by=self.receptionist_anna,
            reason="Desk check-in"
        )
        # Create Google Sheet Connection & Mapping
        sheet_conn = GoogleSheetConnection.objects.create(
            name="Walkin Intake Sheet",
            spreadsheet_url="https://docs.google.com/spreadsheets/d/abc12345/edit",
            spreadsheet_id="abc12345"
        )
        GoogleSheetRowMapping.objects.create(
            connection=sheet_conn,
            lead=lead,
            row_identifier="row-1",
            row_index=1
        )

        self.client.login(username="receptionist_anna", password="Password123!")

        # 1. Test HTML view
        res_html = self.client.get(reverse('receptionist_lead_history', args=[lead.id]))
        self.assertEqual(res_html.status_code, 200)
        self.assertContains(res_html, "History Student")
        self.assertContains(res_html, "9876543200")
        self.assertContains(res_html, "Walkin Intake Sheet")
        self.assertContains(res_html, "Student requested syllabus")

        # 2. Test JSON view for modal
        res_json = self.client.get(f"{reverse('receptionist_lead_history', args=[lead.id])}?format=json")
        self.assertEqual(res_json.status_code, 200)
        data = res_json.json()
        self.assertTrue(data['success'])
        self.assertEqual(data['student']['name'], "History Student")
        self.assertEqual(len(data['assignments']), 1)
        self.assertEqual(len(data['calls']), 1)
        self.assertEqual(len(data['followups']), 1)
        self.assertEqual(len(data['sheet_info']), 1)
        self.assertEqual(data['sheet_info'][0]['connection_name'], "Walkin Intake Sheet")

    def test_receptionist_cannot_view_lead_history_of_other_branch(self):
        lead_vela = Lead.objects.create(
            name="Vela Student",
            phone="9876543299",
            branch=self.branch_vela,
            source="Walk-in"
        )
        self.client.login(username="receptionist_anna", password="Password123!")
        res = self.client.get(reverse('receptionist_lead_history', args=[lead_vela.id]))
        self.assertEqual(res.status_code, 403)

    # 6C. Duplicate Detection & Prevention Tests
    def test_walkin_registration_detects_existing_lead_and_prevents_duplicate(self):
        existing_lead = Lead.objects.create(
            name="Existing Rahul",
            phone="9876599111",
            email="rahul@example.com",
            branch=self.branch_anna,
            source="Google Sheets",
            status=LeadStatus.NEW
        )
        self.client.login(username="receptionist_anna", password="Password123!")

        # Attempt to register with same phone
        res = self.client.post(
            reverse('admin_walkin_create'),
            data=json.dumps({
                'name': 'Rahul R',
                'phone': '9876599111',
                'email': 'rahul_diff@example.com',
                'category': 'Training'
            }),
            content_type='application/json'
        )
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertFalse(data['success'])
        self.assertTrue(data['is_duplicate'])
        self.assertEqual(len(data['matches']), 1)
        self.assertEqual(data['matches'][0]['id'], existing_lead.id)

        # Verify no second lead was created
        self.assertEqual(Lead.objects.filter(phone="9876599111").count(), 1)

    def test_receptionist_check_existing_lead_endpoint(self):
        Lead.objects.create(
            name="Pooja Sharma",
            phone="9876540099",
            email="pooja@example.com",
            branch=self.branch_anna,
            source="Website"
        )
        self.client.login(username="receptionist_anna", password="Password123!")
        res = self.client.get(reverse('receptionist_check_existing_lead') + "?phone=9876540099")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertTrue(data['success'])
        self.assertTrue(data['has_matches'])
        self.assertEqual(data['count'], 1)
        self.assertEqual(data['matches'][0]['name'], "Pooja Sharma")

    def test_counselor_assignment_preserves_lead_status(self):
        lead = Lead.objects.create(
            name="Intact Status Student",
            phone="9876543111",
            branch=self.branch_anna,
            source="Walk-in",
            status=LeadStatus.NEW,
            visitor_status=VisitorStatus.WAITING
        )
        self.client.login(username="receptionist_anna", password="Password123!")
        res = self.client.post(
            reverse('admin_walkin_assign_counselor', args=[lead.id]),
            data=json.dumps({
                'counselor_id': self.counselor_anna.id,
                'reason': 'Front desk assign'
            }),
            content_type='application/json'
        )
        self.assertEqual(res.status_code, 200)
        lead.refresh_from_db()
        self.assertEqual(lead.assigned_counselor, self.counselor_anna)
        # Strict preservation: lead.status remains NEW
        self.assertEqual(lead.status, LeadStatus.NEW)
        self.assertEqual(lead.visitor_status, VisitorStatus.IN_CONSULTATION)

    # 6D. Strict Permission Rejection Tests
    def test_receptionist_denied_from_editing_lead_fields(self):
        lead = Lead.objects.create(
            name="Edit Denied Student",
            phone="9876543222",
            branch=self.branch_anna,
            source="Walk-in"
        )
        self.client.login(username="receptionist_anna", password="Password123!")
        res = self.client.post(
            reverse('api_update_lead_field', args=[lead.id]),
            data=json.dumps({'field': 'name', 'value': 'Hacked Name'}),
            content_type='application/json'
        )
        self.assertEqual(res.status_code, 403)
        lead.refresh_from_db()
        self.assertEqual(lead.name, "Edit Denied Student")

    def test_receptionist_denied_from_deleting_lead(self):
        lead = Lead.objects.create(
            name="Delete Denied Student",
            phone="9876543333",
            branch=self.branch_anna,
            source="Walk-in"
        )
        self.client.login(username="receptionist_anna", password="Password123!")
        res = self.client.post(reverse('admin_lead_delete', args=[lead.id]))
        # Admin required decorator redirects non-admins
        self.assertIn(res.status_code, [302, 403])
        self.assertTrue(Lead.objects.filter(pk=lead.id).exists())

    def test_receptionist_denied_from_google_sheets_connection_api(self):
        self.client.login(username="receptionist_anna", password="Password123!")
        res = self.client.get(reverse('api_google_sheets_list'))
        # Admin required decorator denies non-admins
        self.assertIn(res.status_code, [302, 403])

    # 7. Admin Receptionist Management Portal Tests
    def test_admin_receptionists_list_view(self):
        self.client.login(username="admin_reception_test", password="Password123!")
        res = self.client.get(reverse('admin_receptionists_list'))
        self.assertEqual(res.status_code, 200)
        self.assertContains(res, "receptionist_anna")
        self.assertContains(res, "receptionist_vela")
        self.assertContains(res, "+ Add Receptionist")

    def test_admin_creates_receptionist_with_auto_credentials(self):
        self.client.login(username="admin_reception_test", password="Password123!")
        res = self.client.post(reverse('admin_receptionist_create'), {
            'first_name': 'Deepika',
            'last_name': 'R',
            'username': 'deepika_rec',
            'email': 'deepika@panda.com',
            'phone': '9876541111',
            'branch': self.branch_anna.id,
            'is_active': 'on',
            'password': '',
            'confirm_password': ''
        })
        self.assertRedirects(res, reverse('admin_receptionists_list'))
        created = User.objects.get(username='deepika_rec')
        self.assertEqual(created.role, UserRole.RECEPTIONIST)
        self.assertEqual(created.branch, self.branch_anna)
        self.assertTrue(created.must_change_password)
        self.assertTrue(created.is_active)

    def test_admin_resets_receptionist_password(self):
        self.client.login(username="admin_reception_test", password="Password123!")
        res = self.client.post(reverse('admin_receptionist_change_password', args=[self.receptionist_anna.id]), {
            'new_password1': 'NewSecurePass999!',
            'new_password2': 'NewSecurePass999!'
        })
        self.assertRedirects(res, reverse('admin_receptionists_list'))
        self.receptionist_anna.refresh_from_db()
        self.assertTrue(self.receptionist_anna.check_password('NewSecurePass999!'))
        self.assertFalse(self.receptionist_anna.must_change_password)

    def test_admin_toggles_receptionist_status(self):
        self.client.login(username="admin_reception_test", password="Password123!")
        self.assertTrue(self.receptionist_anna.is_active)
        res = self.client.post(reverse('admin_receptionist_toggle_status', args=[self.receptionist_anna.id]))
        self.assertRedirects(res, reverse('admin_receptionists_list'))
        self.receptionist_anna.refresh_from_db()
        self.assertFalse(self.receptionist_anna.is_active)


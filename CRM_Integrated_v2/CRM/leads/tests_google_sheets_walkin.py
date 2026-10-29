import json
from django.test import TestCase, Client
from django.urls import reverse
from django.utils import timezone

from accounts.models import User, UserRole
from branches.models import Branch
from lead_channels.models import Channel
from products.models import Product
from leads.models import (
    Lead,
    LeadStatus,
    VisitorStatus,
    LeadAssignmentHistory,
    GoogleSheetConnection,
    GoogleSheetRowMapping,
    DuplicateLeadRecord,
)
from leads.google_sheets import sync_google_sheet


class GoogleSheetsWalkInWorkflowTests(TestCase):
    def setUp(self):
        self.client = Client()

        # Branches
        self.branch_anna, _ = Branch.objects.get_or_create(
            name="Anna Nagar Central", defaults={'status': "Active"}
        )
        self.branch_vela, _ = Branch.objects.get_or_create(
            name="Velachery Hub", defaults={'status': "Active"}
        )

        # Admin
        self.admin = User.objects.create_user(
            username="admin_sheets_test",
            password="Password123!",
            role=UserRole.ADMIN,
            is_staff=True,
            is_superuser=True
        )

        # Receptionists
        self.receptionist_anna = User.objects.create_user(
            username="receptionist_anna_test",
            password="Password123!",
            role=UserRole.RECEPTIONIST,
            branch=self.branch_anna,
            first_name="Priya",
            last_name="Sundar"
        )
        self.receptionist_vela = User.objects.create_user(
            username="receptionist_vela_test",
            password="Password123!",
            role=UserRole.RECEPTIONIST,
            branch=self.branch_vela,
            first_name="Meena",
            last_name="K"
        )

        # Counselors
        self.counselor_anna = User.objects.create_user(
            username="counselor_anna_test",
            password="Password123!",
            role=UserRole.COUNSELOR,
            branch=self.branch_anna,
            first_name="Anitha",
            is_active=True
        )
        self.counselor_vela = User.objects.create_user(
            username="counselor_vela_test",
            password="Password123!",
            role=UserRole.COUNSELOR,
            branch=self.branch_vela,
            first_name="Karthik",
            is_active=True
        )

        # Telecaller
        self.telecaller = User.objects.create_user(
            username="telecaller_test_user",
            password="Password123!",
            role=UserRole.TELECALLER,
            branch=self.branch_anna
        )

        # Product
        self.course_python, _ = Product.objects.get_or_create(
            name="Full Stack Python", defaults={'status': "Active"}
        )

        # Channels
        self.channel_sheets, _ = Channel.objects.get_or_create(
            name="Google Sheets", defaults={'status': "Active"}
        )
        self.channel_walkin, _ = Channel.objects.get_or_create(
            name="Walk-in", defaults={'status': "Active"}
        )

        # Admin-configured Google Sheet Connection
        self.connection = GoogleSheetConnection.objects.create(
            name="Anna Nagar Walk-in Form",
            spreadsheet_id="test_sheet_12345",
            spreadsheet_url="https://docs.google.com/spreadsheets/d/test_sheet_12345/edit",
            worksheet_name="Form Responses 1",
            branch=self.branch_anna,
            channel=self.channel_sheets,
            is_active=True,
            field_mapping={
                'name': 'Student Name',
                'phone': 'Contact Number',
                'email': 'Email Address',
                'branch': 'Branch',
                'product': 'Interested Course',
                'notes': 'Remarks'
            }
        )

    # -------------------------------------------------------------------------
    # 1. Admin Page & Google Sheets Ingestion & Idempotency
    # -------------------------------------------------------------------------
    def test_google_sheets_sync_creates_walkin_lead(self):
        """Verify syncing Google Sheet creates a walk-in lead with source='Google Sheets'."""
        headers = ['Student Name', 'Contact Number', 'Email Address', 'Branch', 'Interested Course', 'Remarks']
        rows = [
            {
                'Student Name': 'Ramesh Kumar',
                'Contact Number': '9876543210',
                'Email Address': 'ramesh.k@example.com',
                'Branch': 'Anna Nagar Central',
                'Interested Course': 'Full Stack Python',
                'Remarks': 'Walked in to discuss course schedule'
            }
        ]

        result = sync_google_sheet(self.connection, headers=headers, rows=rows)
        self.assertEqual(result['status'], 'Success')
        self.assertEqual(result['new_leads'], 1)

        lead = Lead.objects.get(phone='9876543210')
        self.assertEqual(lead.name, 'Ramesh Kumar')
        self.assertEqual(lead.source, 'Google Sheets')
        self.assertTrue(lead.is_offline)
        self.assertEqual(lead.branch, self.branch_anna)
        self.assertEqual(lead.visitor_status, VisitorStatus.WAITING)
        self.assertEqual(lead.assignment_status, 'Pending Assignment')
        self.assertIsNone(lead.assigned_counselor)

        # Mapping created
        mapping = GoogleSheetRowMapping.objects.filter(connection=self.connection, lead=lead).first()
        self.assertIsNotNone(mapping)

    def test_google_sheets_sync_is_idempotent_no_duplicates(self):
        """Repeated synchronization must not create duplicate CRM records."""
        headers = ['Student Name', 'Contact Number', 'Email Address', 'Branch', 'Interested Course', 'Remarks']
        rows = [
            {
                'Student Name': 'Ramesh Kumar',
                'Contact Number': '9876543210',
                'Email Address': 'ramesh.k@example.com',
                'Branch': 'Anna Nagar Central',
                'Interested Course': 'Full Stack Python',
                'Remarks': 'Initial check-in'
            }
        ]

        # First sync
        result1 = sync_google_sheet(self.connection, headers=headers, rows=rows)
        self.assertEqual(result1['new_leads'], 1)
        self.assertEqual(Lead.objects.filter(phone='9876543210').count(), 1)

        # Second sync with same row
        result2 = sync_google_sheet(self.connection, headers=headers, rows=rows)
        self.assertEqual(result2['new_leads'], 0)
        self.assertEqual(Lead.objects.filter(phone='9876543210').count(), 1)

    # -------------------------------------------------------------------------
    # 2. Identify New vs Existing Leads (Normalized Mobile Primary, Email Secondary)
    # -------------------------------------------------------------------------
    def test_existing_lead_matched_by_normalized_phone_no_overwrite_with_blanks(self):
        """Matching by normalized mobile preserves existing CRM history without blank overwrite."""
        # Pre-existing lead in CRM
        existing = Lead.objects.create(
            name="Kavitha Raman",
            phone="9876543222",
            email="kavitha@example.com",
            branch=self.branch_anna,
            product=self.course_python,
            status=LeadStatus.FOLLOW_UP,
            assigned_telecaller=self.telecaller,
            assigned_counselor=self.counselor_anna,
            notes="Existing student inquired last month."
        )

        headers = ['Student Name', 'Contact Number', 'Email Address', 'Branch', 'Interested Course', 'Remarks']
        # Incoming row with formatted mobile number '+91 98765 43222' and blank Course/Product
        rows = [
            {
                'Student Name': 'Kavitha Raman',
                'Contact Number': '+91 98765 43222',
                'Email Address': 'kavitha@example.com',
                'Branch': 'Anna Nagar Central',
                'Interested Course': '',  # Blank
                'Remarks': 'Walked into branch today for counselor meeting'
            }
        ]

        result = sync_google_sheet(self.connection, headers=headers, rows=rows)
        self.assertEqual(result['new_leads'], 0)
        self.assertEqual(Lead.objects.filter(phone='9876543222').count(), 1)

        existing.refresh_from_db()
        # Preserved critical status and counselor assignment
        self.assertEqual(existing.status, LeadStatus.FOLLOW_UP)
        self.assertEqual(existing.assigned_telecaller, self.telecaller)
        self.assertEqual(existing.assigned_counselor, self.counselor_anna)
        # Blank course in sheet did NOT overwrite existing product
        self.assertEqual(existing.product, self.course_python)
        # Notes appended rather than overwritten
        self.assertIn("Walked into branch today", existing.notes)
        self.assertIn("Existing student inquired last month", existing.notes)

    def test_ambiguous_match_detection_and_flagging(self):
        """Phone matches Lead A but Email matches Lead B: must flag as ambiguous match."""
        lead_a = Lead.objects.create(
            name="Student Alpha",
            phone="9876500001",
            email="alpha@example.com",
            branch=self.branch_anna
        )
        lead_b = Lead.objects.create(
            name="Student Beta",
            phone="9876500002",
            email="beta@example.com",
            branch=self.branch_anna
        )

        headers = ['Student Name', 'Contact Number', 'Email Address', 'Branch', 'Interested Course', 'Remarks']
        # Row has phone of Alpha, but email of Beta
        rows = [
            {
                'Student Name': 'Conflicting Student',
                'Contact Number': '9876500001',
                'Email Address': 'beta@example.com',
                'Branch': 'Anna Nagar Central',
                'Interested Course': 'Full Stack Python',
                'Remarks': 'Ambiguous record test'
            }
        ]

        sync_google_sheet(self.connection, headers=headers, rows=rows)

        # Verify DuplicateLeadRecord was created with AMBIGUOUS_MATCH_FLAGGED
        flagged = DuplicateLeadRecord.objects.filter(
            action_taken='AMBIGUOUS_MATCH_FLAGGED'
        ).first()
        self.assertIsNotNone(flagged)
        self.assertEqual(flagged.original_lead, lead_a)
        self.assertIn(f"Lead #{lead_b.id}", flagged.duplicate_reason)

    # -------------------------------------------------------------------------
    # 3. Receptionist Dashboard Display
    # -------------------------------------------------------------------------
    def test_receptionist_dashboard_displays_google_sheets_and_manual_walkins(self):
        """Receptionist sees both manual walk-ins and Google Sheets leads scoped to their branch."""
        # 1. Manual walk-in in Anna Nagar
        manual_lead = Lead.objects.create(
            name="Manual Walkin Student",
            phone="9876511111",
            branch=self.branch_anna,
            source="Walk-in",
            channel=self.channel_walkin,
            is_offline=True
        )

        # 2. Google Sheets lead in Anna Nagar
        sheet_lead = Lead.objects.create(
            name="Sheet Walkin Student",
            phone="9876522222",
            branch=self.branch_anna,
            source="Google Sheets",
            channel=self.channel_sheets,
            is_offline=True
        )

        # 3. Another branch's lead (should NOT be visible to Anna Nagar receptionist)
        vela_lead = Lead.objects.create(
            name="Velachery Student",
            phone="9876533333",
            branch=self.branch_vela,
            source="Walk-in",
            is_offline=True
        )

        self.client.login(username="receptionist_anna_test", password="Password123!")
        res = self.client.get(reverse('receptionist_dashboard'))
        self.assertEqual(res.status_code, 200)

        # Should contain branch leads
        self.assertContains(res, "Manual Walkin Student")
        self.assertContains(res, "Sheet Walkin Student")
        self.assertContains(res, "Google Sheets")
        self.assertContains(res, "Direct Walk-in")

        # Must NOT contain Velachery lead
        self.assertNotContains(res, "Velachery Student")

    # -------------------------------------------------------------------------
    # 4. Counselor Assignment (Single and Bulk)
    # -------------------------------------------------------------------------
    def test_receptionist_bulk_assign_counselor_success(self):
        """Receptionist selects multiple walk-in leads and assigns them to an eligible branch counselor."""
        lead1 = Lead.objects.create(
            name="Bulk Lead 1",
            phone="9876599901",
            branch=self.branch_anna,
            source="Google Sheets",
            is_offline=True
        )
        lead2 = Lead.objects.create(
            name="Bulk Lead 2",
            phone="9876599902",
            branch=self.branch_anna,
            source="Walk-in",
            is_offline=True
        )

        self.client.login(username="receptionist_anna_test", password="Password123!")
        res = self.client.post(
            reverse('admin_walkin_bulk_assign_counselor'),
            data=json.dumps({
                'lead_ids': [lead1.id, lead2.id],
                'counselor_id': self.counselor_anna.id,
                'reason': 'Bulk front-desk consultation assign'
            }),
            content_type='application/json'
        )

        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertTrue(data['success'])
        self.assertEqual(data['assigned_count'], 2)

        # Check DB updates
        lead1.refresh_from_db()
        lead2.refresh_from_db()
        self.assertEqual(lead1.assigned_counselor, self.counselor_anna)
        self.assertEqual(lead2.assigned_counselor, self.counselor_anna)
        self.assertEqual(lead1.visitor_status, VisitorStatus.IN_CONSULTATION)
        self.assertEqual(lead2.visitor_status, VisitorStatus.IN_CONSULTATION)

        # Verify audit history logged
        self.assertTrue(LeadAssignmentHistory.objects.filter(lead=lead1, to_user=self.counselor_anna).exists())
        self.assertTrue(LeadAssignmentHistory.objects.filter(lead=lead2, to_user=self.counselor_anna).exists())

        # Verify assigned counselor sees the leads in counselor dashboard
        self.client.login(username="counselor_anna_test", password="Password123!")
        c_res = self.client.get(reverse('counselor_dashboard'))
        self.assertEqual(c_res.status_code, 200)
        self.assertContains(c_res, "Bulk Lead 1")
        self.assertContains(c_res, "Bulk Lead 2")

    def test_receptionist_bulk_assign_cross_branch_counselor_rejected(self):
        """Receptionist cannot assign leads to a counselor in another branch."""
        lead = Lead.objects.create(
            name="Anna Lead",
            phone="9876599903",
            branch=self.branch_anna,
            source="Walk-in",
            is_offline=True
        )

        self.client.login(username="receptionist_anna_test", password="Password123!")
        # Try assigning Anna lead to Velachery counselor
        res = self.client.post(
            reverse('admin_walkin_bulk_assign_counselor'),
            data=json.dumps({
                'lead_ids': [lead.id],
                'counselor_id': self.counselor_vela.id,
                'reason': 'Illegal cross-branch assign'
            }),
            content_type='application/json'
        )

        self.assertEqual(res.status_code, 400)
        lead.refresh_from_db()
        self.assertIsNone(lead.assigned_counselor)

    def test_receptionist_cannot_see_google_sheets_spreadsheet_url(self):
        """Spreadsheet URL is confidential to admin and must not be leaked to receptionist."""
        lead = Lead.objects.create(
            name="Confidential Sheet Lead",
            phone="9876599904",
            branch=self.branch_anna,
            source="Google Sheets",
            is_offline=True
        )
        GoogleSheetRowMapping.objects.create(
            connection=self.connection,
            lead=lead,
            row_index=2,
            row_identifier="row_2_hash",
            row_data_hash="dummy_hash"
        )

        self.client.login(username="receptionist_anna_test", password="Password123!")
        res = self.client.get(reverse('receptionist_lead_history', args=[lead.id]))
        self.assertEqual(res.status_code, 200)
        # Ensure spreadsheet edit link is omitted for receptionist
        self.assertNotContains(res, "test_sheet_12345/edit")

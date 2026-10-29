import unittest
from unittest.mock import patch
from django.test import TestCase, Client
from django.contrib.auth import get_user_model
from django.urls import reverse

from services.intelligent_matching_engine import (
    normalize_header,
    fuzzy_similarity_score,
    analyze_column_values,
    match_column,
    match_all_columns,
    AUTHORITATIVE_FIELD_INVENTORY,
)
from services.google_sheets_sync_service import sync_connection
from leads.models import (
    Lead,
    GoogleSheetConnection,
    GoogleSheetRowMapping,
    GoogleSheetSyncHistory,
)
from branches.models import Branch
from products.models import Product
from lead_channels.models import Channel

User = get_user_model()


class IntelligentMatchingEngineUnitTests(unittest.TestCase):
    """Exhaustive tests for the pure matching engine algorithms."""

    def test_normalize_header(self):
        self.assertEqual(normalize_header("  Phone  Number  "), "phone number")
        self.assertEqual(normalize_header("FIRST_NAME-TEST"), "first name test")
        self.assertEqual(normalize_header("பெயர்"), "பெயர்")
        self.assertEqual(normalize_header("नाम"), "नाम")

    def test_exact_and_alias_matching(self):
        res_phone = match_column("Phone Number", ["9876543210", "9123456789"])
        self.assertEqual(res_phone.crm_field, "phone")
        self.assertEqual(res_phone.tier, "HIGH")
        self.assertGreaterEqual(res_phone.confidence, 0.90)

        res_email = match_column("Email Address", ["test@example.com"])
        self.assertEqual(res_email.crm_field, "email")
        self.assertEqual(res_email.tier, "HIGH")

        res_name = match_column("Student Name", ["Arun Kumar"])
        self.assertEqual(res_name.crm_field, "name")
        self.assertEqual(res_name.tier, "HIGH")

    def test_multilingual_matching_tamil(self):
        res_name = match_column("பெயர்", ["விஜய்", "பிரியா"])
        self.assertEqual(res_name.crm_field, "name")
        self.assertIn("Tamil", str(res_name.reasons))

        res_phone = match_column("தொலைபேசி", ["9876543210"])
        self.assertEqual(res_phone.crm_field, "phone")

        res_email = match_column("மின்னஞ்சல்", ["student@tamil.edu"])
        self.assertEqual(res_email.crm_field, "email")

        res_course = match_column("படிப்பு", ["Python"])
        self.assertEqual(res_course.crm_field, "product")

        res_branch = match_column("கிளை", ["Chennai"])
        self.assertEqual(res_branch.crm_field, "branch")

    def test_multilingual_matching_hindi(self):
        res_name = match_column("नाम", ["राहुल शर्मा"])
        self.assertEqual(res_name.crm_field, "name")
        self.assertIn("Hindi", str(res_name.reasons))

        res_phone = match_column("फ़ोन", ["9876543210"])
        self.assertEqual(res_phone.crm_field, "phone")

        res_email = match_column("ईमेल", ["student@hindi.edu"])
        self.assertEqual(res_email.crm_field, "email")

        res_course = match_column("पाठ्यक्रम", ["Data Science"])
        self.assertEqual(res_course.crm_field, "product")

        res_branch = match_column("शाखा", ["Delhi"])
        self.assertEqual(res_branch.crm_field, "branch")

    def test_fuzzy_matching(self):
        res_fuzzy_phone = match_column("Phne Numbr", ["9876543210", "9876543211"])
        self.assertEqual(res_fuzzy_phone.crm_field, "phone")
        self.assertIn("Fuzzy match", str(res_fuzzy_phone.reasons))

        res_fuzzy_email = match_column("Emal Adres", ["user@gmail.com"])
        self.assertEqual(res_fuzzy_email.crm_field, "email")

    def test_cell_value_pattern_matching_untyped_header(self):
        # Column header is generic, but cell values are unmistakable phone numbers
        res_phone_pattern = match_column("Col_A", ["9876543210", "9123456780", "9988776655"])
        self.assertEqual(res_phone_pattern.crm_field, "phone")
        self.assertIn("match phone regex", str(res_phone_pattern.reasons))

        # Column header is generic, but cell values are emails
        res_email_pattern = match_column("Data_B", ["a@b.com", "user@corp.org", "info@site.io"])
        self.assertEqual(res_email_pattern.crm_field, "email")
        self.assertIn("match email pattern", str(res_email_pattern.reasons))

    def test_match_all_columns_conflict_resolution(self):
        headers = [
            "Candidate Name",
            "Contact Phone",
            "Alternate Mobile",
            "Email ID",
            "Course Interested",
            "Preferred Center",
            "Mode of Study",
            "Favorite Color",  # Completely unmapped
        ]
        sample_rows = [
            {
                "Candidate Name": "Kavitha",
                "Contact Phone": "9876543210",
                "Alternate Mobile": "9123456789",
                "Email ID": "kavitha@example.com",
                "Course Interested": "Python Fullstack",
                "Preferred Center": "Chennai",
                "Mode of Study": "Online",
                "Favorite Color": "Cyan",
            }
        ]

        spec = match_all_columns(headers, sample_rows)
        field_to_header = spec['field_to_header']

        self.assertEqual(field_to_header.get('name'), "Candidate Name")
        self.assertEqual(field_to_header.get('phone'), "Contact Phone")
        self.assertEqual(field_to_header.get('alternate_phone'), "Alternate Mobile")
        self.assertEqual(field_to_header.get('email'), "Email ID")
        self.assertEqual(field_to_header.get('product'), "Course Interested")
        self.assertEqual(field_to_header.get('branch'), "Preferred Center")
        self.assertEqual(field_to_header.get('class_mode'), "Mode of Study")
        self.assertIn("Favorite Color", spec['unmapped_headers'])


class IntelligentSheetsSyncServiceTests(TestCase):
    """End-to-end synchronization tests with database transactions."""

    def setUp(self):
        self.admin_user = User.objects.create_superuser(
            username='admin_test',
            email='admin@test.com',
            password='testpassword123'
        )
        self.branch = Branch.objects.create(name='Velachery Branch', status='Active')
        self.product = Product.objects.create(name='AI Engineering', status='Active')
        self.channel = Channel.objects.create(name='Google Sheets')

        self.connection = GoogleSheetConnection.objects.create(
            name='Test Enquiries Sheet',
            spreadsheet_url='https://docs.google.com/spreadsheets/d/1ABCXYZ1234567890/edit#gid=0',
            spreadsheet_id='1ABCXYZ1234567890',
            gid='0',
            worksheet_name='Sheet1',
            branch=self.branch,
            channel=self.channel,
            is_active=True,
            created_by=self.admin_user
        )

    def test_sync_creates_leads_and_preserves_unmapped_fields(self):
        headers = ['Full Name', 'Phone No', 'Course', 'Email', 'Emergency Phone', 'Preferred Timing']
        rows = [
            {
                'Full Name': 'Vimal Raj',
                'Phone No': '9876543210',
                'Course': 'AI Engineering',
                'Email': 'vimal@example.com',
                'Emergency Phone': '9123456780',
                'Preferred Timing': 'Evening Batch 7PM',
            }
        ]

        res = sync_connection(self.connection, triggered_by=self.admin_user, headers=headers, rows=rows)
        self.assertTrue(res['success'])
        self.assertEqual(res['created'], 1)

        lead = Lead.objects.filter(phone='9876543210').first()
        self.assertIsNotNone(lead)
        self.assertEqual(lead.name, 'Vimal Raj')
        self.assertEqual(lead.email, 'vimal@example.com')
        self.assertEqual(lead.alternate_phone, '9123456780')

        # Check that unmapped column 'Preferred Timing' was preserved in custom_fields['all_answers']
        self.assertIn('all_answers', lead.custom_fields)
        self.assertEqual(lead.custom_fields['all_answers'].get('Preferred Timing'), 'Evening Batch 7PM')
        # Check notes contains form data
        self.assertIn('Preferred Timing: Evening Batch 7PM', lead.notes)

    def test_in_place_non_destructive_updates(self):
        # 1. Initial sync
        headers = ['Full Name', 'Mobile', 'Email Address']
        rows_v1 = [
            {'Full Name': 'Suresh', 'Mobile': '9944112233', 'Email Address': 'suresh@company.com'}
        ]
        sync_connection(self.connection, triggered_by=self.admin_user, headers=headers, rows=rows_v1)
        lead = Lead.objects.get(phone='9944112233')
        self.assertEqual(lead.email, 'suresh@company.com')

        # 2. Second sync: name changed in sheet, email left blank in sheet
        rows_v2 = [
            {'Full Name': 'Suresh Kumar', 'Mobile': '9944112233', 'Email Address': ''}
        ]
        res_v2 = sync_connection(self.connection, triggered_by=self.admin_user, headers=headers, rows=rows_v2)
        self.assertEqual(res_v2['updated'], 1)

        lead.refresh_from_db()
        self.assertEqual(lead.name, 'Suresh Kumar')
        # CRITICAL NON-DESTRUCTIVE RULE: Blank in sheet must NOT erase existing CRM email!
        self.assertEqual(lead.email, 'suresh@company.com')

    def test_dry_run_preview_does_not_modify_database(self):
        headers = ['Candidate Name', 'Mobile Number', 'Email Address']
        rows = [
            {'Candidate Name': 'Deepak', 'Mobile Number': '9840112233', 'Email Address': 'deepak@test.com'}
        ]

        prev_res = sync_connection(
            self.connection,
            triggered_by=self.admin_user,
            headers=headers,
            rows=rows,
            dry_run=True
        )

        self.assertTrue(prev_res['dry_run'])
        self.assertEqual(prev_res['created'], 1)
        # Verify nothing was written to database
        self.assertFalse(Lead.objects.filter(phone='9840112233').exists())
        self.assertFalse(GoogleSheetRowMapping.objects.filter(connection=self.connection).exists())


class IntelligentMatchingAPITests(TestCase):
    """Tests for the REST API endpoints."""

    def setUp(self):
        self.client = Client()
        self.admin = User.objects.create_superuser('admin_api', 'api@test.com', 'pass1234')
        self.client.force_login(self.admin)

        self.connection = GoogleSheetConnection.objects.create(
            name='API Test Sheet',
            spreadsheet_url='https://docs.google.com/spreadsheets/d/1SAMPLE123456789/edit#gid=0',
            spreadsheet_id='1SAMPLE123456789',
            gid='0',
            worksheet_name='Sheet1',
            is_active=True,
            created_by=self.admin
        )

    @patch('leads.api_google_sheets.fetch_sheet')
    def test_inspect_mapping_api(self, mock_fetch):
        mock_fetch.return_value = (
            ['Name', 'Mobile No', 'Email', 'Preferred Course', 'City', 'Extra Note'],
            [{'Name': 'Anand', 'Mobile No': '9876543210', 'Email': 'anand@test.com', 'Preferred Course': 'Python', 'City': 'Chennai', 'Extra Note': 'Weekend'}]
        )

        resp = self.client.post(
            reverse('api_google_sheets_inspect_mapping'),
            data=json.dumps({'connection_id': self.connection.id}),
            content_type='application/json'
        )

        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertTrue(data['success'])
        self.assertIn('column_mappings', data)
        self.assertEqual(data['field_to_header']['phone'], 'Mobile No')
        self.assertEqual(data['field_to_header']['email'], 'Email')
        self.assertIn('available_crm_fields', data)

    @patch('leads.api_google_sheets.fetch_sheet')
    def test_preview_sync_api(self, mock_fetch):
        mock_fetch.return_value = (
            ['Name', 'Phone'],
            [{'Name': 'Karthik', 'Phone': '9876543210'}]
        )

        resp = self.client.post(
            reverse('api_google_sheets_preview_sync'),
            data=json.dumps({
                'connection_id': self.connection.id,
                'field_mapping': {'name': 'Name', 'phone': 'Phone'}
            }),
            content_type='application/json'
        )

        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertTrue(data['success'])
        self.assertTrue(data['preview']['dry_run'])
        self.assertEqual(data['preview']['created'], 1)

    def test_save_mapping_api(self):
        custom_mapping = {'name': 'Custom Name Col', 'phone': 'Custom Phone Col'}
        resp = self.client.post(
            reverse('api_google_sheets_save_mapping', args=[self.connection.id]),
            data=json.dumps({'field_mapping': custom_mapping}),
            content_type='application/json'
        )

        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertTrue(data['success'])

        self.connection.refresh_from_db()
        self.assertEqual(self.connection.field_mapping.get('name'), 'Custom Name Col')
        self.assertEqual(self.connection.field_mapping.get('phone'), 'Custom Phone Col')

import io
from django.test import TestCase
from django.utils import timezone
from accounts.models import User, UserRole
from branches.models import Branch
from leads.models import Lead, LeadStatus, LeadImportHistory, DuplicateLeadRecord
from leads.duplicates import normalize_phone, normalize_email, find_duplicate_lead, find_all_matching_leads
from leads.services import import_leads_file
from leads.intake import intake_lead
from calls.sync_services import find_lead_by_phone, phone10


class Phase3DuplicateRemediationTests(TestCase):
    def setUp(self):
        self.branch = Branch.objects.create(name="Phase3 Test Branch")
        self.admin_user = User.objects.create_user(
            username="p3_admin",
            email="p3_admin@example.com",
            password="testpassword",
            role=UserRole.ADMIN,
            branch=self.branch
        )
        self.telecaller = User.objects.create_user(
            username="p3_telecaller",
            email="p3_tc@example.com",
            password="testpassword",
            role=UserRole.TELECALLER,
            branch=self.branch
        )

    def test_international_phone_normalization(self):
        """Verify normalize_phone handles UK, US, UAE, Australia, 00 prefix, domestic Indian, and surrogate formats."""
        # UK
        self.assertEqual(normalize_phone("+44 7911 123456"), "+447911123456")
        # US
        self.assertEqual(normalize_phone("+1 (415) 555-2671"), "+14155552671")
        # UAE
        self.assertEqual(normalize_phone("+971 50 123 4567"), "+971501234567")
        # Australia
        self.assertEqual(normalize_phone("+61 412 345 678"), "+61412345678")
        # 00 international prefix
        self.assertEqual(normalize_phone("001 415 555 2671"), "+14155552671")
        # Domestic Indian formats -> clean 10 digits
        self.assertEqual(normalize_phone("+91 98765 43210"), "9876543210")
        self.assertEqual(normalize_phone("919876543210"), "9876543210")
        self.assertEqual(normalize_phone("09876543210"), "9876543210")
        self.assertEqual(normalize_phone("9876543210"), "9876543210")
        # Surrogate markers
        self.assertEqual(normalize_phone("NoPhone-123456"), "NoPhone-123456")
        # Empty / None
        self.assertEqual(normalize_phone(""), "")
        self.assertEqual(normalize_phone(None), "")

    def test_international_and_domestic_no_false_collision(self):
        """An international number with 10 digits suffix matching an Indian domestic number must NOT collide."""
        # Indian lead
        indian_lead = Lead.objects.create(
            name="Ravi Kumar",
            phone="9876543210",
            email="ravi@example.com",
            branch=self.branch
        )
        self.assertEqual(indian_lead.normalized_phone, "9876543210")

        # US number ending in the same 10 digits
        us_phone = "+1 9876543210"
        match = find_duplicate_lead(phone=us_phone)
        self.assertIsNone(match, "International +19876543210 must NOT match Indian 9876543210")

        # Saving US lead
        us_lead = Lead.objects.create(
            name="John Smith",
            phone=us_phone,
            email="john@example.com",
            branch=self.branch
        )
        self.assertEqual(us_lead.normalized_phone, "+19876543210")
        self.assertNotEqual(indian_lead.normalized_phone, us_lead.normalized_phone)

        # Finding each lead individually works cleanly
        self.assertEqual(find_duplicate_lead(phone="9876543210").id, indian_lead.id)
        self.assertEqual(find_duplicate_lead(phone="+1 9876543210").id, us_lead.id)

    def test_row_tolerant_bulk_import_continues_on_error(self):
        """Bulk file import must commit valid rows and isolate failed rows using savepoints."""
        initial_lead_count = Lead.objects.count()

        csv_content = (
            "Name,Phone,Email,Branch,Product,Notes\n"
            "Valid Lead 1,9841122331,valid1@example.com,Phase3 Test Branch,Python,First valid\n"
            "Invalid Missing Phone,,invalid@example.com,Phase3 Test Branch,Python,Bad row missing phone\n"
            "Valid Lead 2,9841122332,valid2@example.com,Phase3 Test Branch,Python,Second valid\n"
        )
        csv_file = io.BytesIO(csv_content.encode('utf-8'))
        csv_file.name = "test_row_tolerant.csv"

        successful, failed, errors = import_leads_file(csv_file, self.admin_user)

        self.assertEqual(successful, 2, f"Should successfully import 2 valid rows. Errors: {errors}")
        self.assertEqual(failed, 1)
        self.assertEqual(len(errors), 1)
        self.assertIn("Row 2", errors[0])

        # Valid rows must exist in DB
        self.assertTrue(Lead.objects.filter(phone="9841122331").exists())
        self.assertTrue(Lead.objects.filter(phone="9841122332").exists())
        self.assertEqual(Lead.objects.count(), initial_lead_count + 2)

        # Check LeadImportHistory status
        history = LeadImportHistory.objects.order_by('-pk').first()
        self.assertIsNotNone(history)
        self.assertEqual(history.records, 3)
        self.assertEqual(history.successful, 2)
        self.assertEqual(history.failed, 1)
        self.assertEqual(history.status, "Completed with Errors")
        self.assertIn("Row 2", history.error_log)

    def test_row_tolerant_bulk_import_recovers_from_unhandled_exception(self):
        """If an unexpected exception occurs inside row processing, the row savepoint rolls back without breaking others."""
        csv_content = (
            "Name,Phone,Email\n"
            "Pre Exception Lead,9841199001,pre@example.com\n"
            "Mid Exception Lead,9841199002,mid@example.com\n"
            "Post Exception Lead,9841199003,post@example.com\n"
        )
        csv_file = io.BytesIO(csv_content.encode('utf-8'))
        csv_file.name = "test_exception_recovery.csv"

        # Mock find_duplicate_lead to raise an exception only on the second row
        orig_find = find_duplicate_lead
        call_count = [0]

        def flaky_find(*args, **kwargs):
            call_count[0] += 1
            if call_count[0] == 2:
                raise RuntimeError("Simulated transient DB error on Row 2")
            return orig_find(*args, **kwargs)

        from unittest.mock import patch
        with patch('leads.services.find_duplicate_lead', side_effect=flaky_find):
            successful, failed, errors = import_leads_file(csv_file, self.admin_user)

        self.assertEqual(successful, 2)
        self.assertEqual(failed, 1)
        self.assertTrue(any("Simulated transient DB error on Row 2" in err for err in errors))
        self.assertTrue(Lead.objects.filter(phone="9841199001").exists())
        self.assertFalse(Lead.objects.filter(phone="9841199002").exists())
        self.assertTrue(Lead.objects.filter(phone="9841199003").exists())

    def test_external_event_idempotency(self):
        """Provider event ID replay must return IDEMPOTENT_IGNORED without duplicate record creation."""
        event_id = "fb_lead_event_uuid_12345"

        # First intake call
        res1 = intake_lead(
            phone="9876511223",
            source="Facebook",
            name="FB Customer",
            email="fbcustomer@example.com",
            branch=self.branch,
            provider_event_id=event_id,
        )
        self.assertEqual(res1.action_taken, "CREATED_NEW")
        self.assertTrue(res1.created)
        first_lead_id = res1.lead.id

        # Duplicate webhook delivery with identical provider_event_id
        res2 = intake_lead(
            phone="9876511223",
            source="Facebook",
            name="FB Customer",
            email="fbcustomer@example.com",
            branch=self.branch,
            provider_event_id=event_id,
        )
        self.assertEqual(res2.action_taken, "IDEMPOTENT_IGNORED")
        self.assertFalse(res2.created)
        self.assertEqual(res2.lead.id, first_lead_id)

        # Audit count remains 1
        audits = DuplicateLeadRecord.objects.filter(provider_event_id=event_id)
        self.assertEqual(audits.count(), 1)

    def test_international_lead_intake_and_lookup(self):
        """International lead created via intake_lead can be searched by calls find_lead_by_phone."""
        res = intake_lead(
            phone="+44 7911 123456",
            source="WhatsApp",
            name="London Lead",
            email="london@example.co.uk",
            branch=self.branch,
        )
        self.assertEqual(res.action_taken, "CREATED_NEW")
        lead = res.lead
        self.assertEqual(lead.normalized_phone, "+447911123456")

        # Fast lookup via find_lead_by_phone
        found = find_lead_by_phone("+44 7911 123456", user=self.telecaller)
        self.assertIsNotNone(found)
        self.assertEqual(found.id, lead.id)

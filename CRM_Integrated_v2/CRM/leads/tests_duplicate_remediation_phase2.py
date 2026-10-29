from datetime import timedelta
from django.test import TestCase
from django.utils import timezone
from accounts.models import User, UserRole
from branches.models import Branch
from lead_channels.models import Channel
from products.models import Product
from leads.models import Lead, LeadStatus, DuplicateLeadRecord
from leads.duplicates import find_duplicate_lead, process_spreadsheet_row_duplicate_rules
from calls.sync_services import find_lead_by_phone as calls_find_lead
from drive.services import find_lead_by_phone as drive_find_lead


class Phase2RemediationTests(TestCase):
    """
    Test suite for Phase 2 of duplicate data remediation:
    - Automatic `normalized_phone` population and indexing on `Lead.save()`.
    - Android call synchronization fast indexed lookup.
    - Drive recording lead matching fast indexed lookup.
    - Duplicate detection using normalized phone index.
    - Google Sheets row duplicate governance.
    """

    def setUp(self):
        self.branch_a = Branch.objects.create(name="Phase2 Branch A", status="Active")
        self.branch_b = Branch.objects.create(name="Phase2 Branch B", status="Active")

        self.telecaller = User.objects.create(
            username="p2_tc",
            role=UserRole.TELECALLER,
            branch=self.branch_a,
            first_name="P2",
            last_name="Caller"
        )

        self.channel = Channel.objects.create(name="Google Sheets Channel", status="Active")
        self.product = Product.objects.create(name="Full Stack Web Dev", status="Active")

    def test_normalized_phone_auto_populated_on_lead_save(self):
        """Lead.save() must extract clean 10-digit normalized phone automatically."""
        lead = Lead.objects.create(
            name="Rohan Sharma",
            phone="+91 98401 23456",
            email="rohan@example.com",
            branch=self.branch_a
        )
        lead.refresh_from_db()
        self.assertEqual(lead.normalized_phone, "9840123456")

        # Test updating phone with 0 prefix
        lead.phone = "09840123456"
        lead.save()
        lead.refresh_from_db()
        self.assertEqual(lead.normalized_phone, "9840123456")

    def test_nophone_lead_normalized_phone_empty(self):
        """Surrogate NoPhone- identifiers must have empty normalized_phone."""
        lead = Lead.objects.create(
            name="Email Only Lead",
            phone="NoPhone-abcd1234ef",
            email="emailonly@example.com",
            branch=self.branch_a
        )
        lead.refresh_from_db()
        self.assertEqual(lead.normalized_phone, "")

    def test_calls_find_lead_by_phone_indexed_lookup(self):
        """calls.sync_services.find_lead_by_phone must locate lead via normalized_phone."""
        lead = Lead.objects.create(
            name="Priya Patel",
            phone="+91 98765 99887",
            branch=self.branch_a,
            assigned_telecaller=self.telecaller
        )
        self.assertEqual(lead.normalized_phone, "9876599887")

        # Search with various formatting variations
        found_lead = calls_find_lead("9876599887", user=self.telecaller)
        self.assertIsNotNone(found_lead)
        self.assertEqual(found_lead.pk, lead.pk)

        found_formatted = calls_find_lead("+91 98765 99887", user=self.telecaller)
        self.assertIsNotNone(found_formatted)
        self.assertEqual(found_formatted.pk, lead.pk)

    def test_drive_find_lead_by_phone_indexed_lookup(self):
        """drive.services.find_lead_by_phone must find lead using indexed normalized phone."""
        lead = Lead.objects.create(
            name="Vikram Singh",
            phone="9876500112",
            branch=self.branch_a,
            assigned_telecaller=self.telecaller
        )
        found = drive_find_lead("9876500112", user=self.telecaller)
        self.assertIsNotNone(found)
        self.assertEqual(found.pk, lead.pk)

    def test_find_duplicate_lead_uses_normalized_phone(self):
        """find_duplicate_lead must match against normalized_phone index."""
        lead = Lead.objects.create(
            name="Meera Nair",
            phone="9840911223",
            branch=self.branch_a
        )
        match = find_duplicate_lead(phone="+91 98409 11223")
        self.assertIsNotNone(match)
        self.assertEqual(match.pk, lead.pk)

    def test_spreadsheet_row_duplicate_rules_same_branch(self):
        """Google Sheets row in same branch must be marked DUPLICATE."""
        orig_lead = Lead.objects.create(
            name="Kavita Rao",
            phone="9876512345",
            email="kavita@example.com",
            branch=self.branch_a
        )
        row_data = {
            'name': 'Kavita Rao',
            'phone': '9876512345',
            'email': 'kavita@example.com',
            'branch': self.branch_a.name
        }
        lead, is_dup, dup_rec = process_spreadsheet_row_duplicate_rules(
            row_data=row_data,
            headers=['name', 'phone', 'email', 'branch']
        )
        self.assertTrue(is_dup)
        self.assertEqual(lead.pk, orig_lead.pk)
        self.assertIsNotNone(dup_rec)
        self.assertEqual(dup_rec.status, 'DUPLICATE')

    def test_spreadsheet_row_duplicate_rules_different_branch_within_10_days(self):
        """Google Sheets row in different branch within 10 days must be DUPLICATE and add secondary branch."""
        orig_lead = Lead.objects.create(
            name="Arun Kumar",
            phone="9876523456",
            email="arun@example.com",
            branch=self.branch_a
        )
        row_data = {
            'name': 'Arun Kumar',
            'phone': '9876523456',
            'email': 'arun@example.com',
            'branch': self.branch_b.name
        }
        lead, is_dup, dup_rec = process_spreadsheet_row_duplicate_rules(
            row_data=row_data,
            headers=['name', 'phone', 'email', 'branch']
        )
        self.assertTrue(is_dup)
        self.assertEqual(lead.pk, orig_lead.pk)
        self.assertIsNotNone(dup_rec)
        self.assertIn(self.branch_b, orig_lead.secondary_branches.all())

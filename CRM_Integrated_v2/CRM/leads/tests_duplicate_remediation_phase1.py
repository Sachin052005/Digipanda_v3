import io
import csv
from datetime import timedelta
from django.test import TestCase
from django.utils import timezone
from accounts.models import User, UserRole
from branches.models import Branch, SalesHeadBranchAccess
from lead_channels.models import Channel
from products.models import Product
from leads.models import Lead, LeadStatus, DuplicateLeadRecord
from leads.forms import AdminLeadForm, ManagerLeadForm, TelecallerLeadForm
from leads.services import import_leads_file
from leads.duplicates import normalize_phone, normalize_email


class Phase1DuplicateRemediationTests(TestCase):
    """
    Test suite for Phase 1 of duplicate data remediation:
    - Lead edit validation on phone, alternate_phone, and email across Admin, Manager, and Telecaller forms.
    - Exclusion of current lead during edits.
    - Ambiguous match handling (reporting field-level errors without merging/deleting).
    - Normalized phone persistence in bulk imports.
    - Preservation of existing 10-day re-enquiry duplicate rules.
    """

    def setUp(self):
        self.branch_a, _ = Branch.objects.get_or_create(name="Phase1 Branch A", defaults={"status": "Active"})
        self.branch_b, _ = Branch.objects.get_or_create(name="Phase1 Branch B", defaults={"status": "Active"})

        self.admin_user, _ = User.objects.get_or_create(
            username="p1_admin",
            defaults={"role": UserRole.ADMIN, "first_name": "Admin", "last_name": "Super"}
        )
        self.admin_user.set_password("AdminPass123!")
        self.admin_user.save()

        self.manager_user, _ = User.objects.get_or_create(
            username="p1_mgr",
            defaults={"role": UserRole.SALES_HEAD, "branch": self.branch_a, "first_name": "Manager", "last_name": "One"}
        )
        self.manager_user.set_password("MgrPass123!")
        self.manager_user.save()
        SalesHeadBranchAccess.objects.get_or_create(sales_head=self.manager_user, branch=self.branch_a)

        self.telecaller_user, _ = User.objects.get_or_create(
            username="p1_tc",
            defaults={"role": UserRole.TELECALLER, "branch": self.branch_a, "first_name": "Caller", "last_name": "One"}
        )
        self.telecaller_user.set_password("TcPass123!")
        self.telecaller_user.save()

        self.channel, _ = Channel.objects.get_or_create(name="Direct", defaults={"status": "Active"})
        self.product, _ = Product.objects.get_or_create(name="Python Master", defaults={"status": "Active"})

        # Lead 1: Alice
        self.lead_alice = Lead.objects.create(
            name="Alice Smith",
            phone="9876543210",
            email="alice@example.com",
            alternate_phone="9876543219",
            branch=self.branch_a,
            assigned_sales_head=self.manager_user,
            assigned_telecaller=self.telecaller_user,
            status=LeadStatus.NEW
        )

        # Lead 2: Bob
        self.lead_bob = Lead.objects.create(
            name="Bob Jones",
            phone="9876543211",
            email="bob@example.com",
            branch=self.branch_a,
            assigned_sales_head=self.manager_user,
            assigned_telecaller=self.telecaller_user,
            status=LeadStatus.NEW
        )

        # Lead 3: Charlie
        self.lead_charlie = Lead.objects.create(
            name="Charlie Brown",
            phone="9876543212",
            email="charlie@example.com",
            branch=self.branch_a,
            assigned_sales_head=self.manager_user,
            assigned_telecaller=self.telecaller_user,
            status=LeadStatus.NEW
        )

    def test_admin_lead_edit_rejects_duplicate_primary_phone(self):
        """Editing Lead Bob's phone to Alice's phone must fail validation."""
        form_data = {
            'name': self.lead_bob.name,
            'phone': '+91 98765 43210',  # Alice's phone with formatting
            'email': self.lead_bob.email,
            'branch': self.branch_a.id,
            'status': self.lead_bob.status,
            'category': self.lead_bob.category or 'General',
        }
        form = AdminLeadForm(data=form_data, instance=self.lead_bob)
        self.assertFalse(form.is_valid(), "Form should be invalid when phone belongs to another lead.")
        self.assertIn('phone', form.errors)
        self.assertIn(f"Lead #{self.lead_alice.pk}", form.errors['phone'][0])

    def test_admin_lead_edit_allows_saving_own_unchanged_phone(self):
        """Saving Lead Alice without changing her phone number must succeed."""
        form_data = {
            'name': "Alice Smith Updated",
            'phone': self.lead_alice.phone,
            'email': self.lead_alice.email,
            'branch': self.branch_a.id,
            'status': self.lead_alice.status,
            'category': self.lead_alice.category or 'General',
        }
        form = AdminLeadForm(data=form_data, instance=self.lead_alice)
        self.assertTrue(form.is_valid(), f"Form should be valid when phone is unchanged. Errors: {form.errors}")
        saved_lead = form.save()
        self.assertEqual(saved_lead.name, "Alice Smith Updated")
        self.assertEqual(saved_lead.phone, "9876543210")

    def test_admin_lead_edit_rejects_duplicate_email(self):
        """Editing Lead Bob's email to Alice's email must fail validation."""
        form_data = {
            'name': self.lead_bob.name,
            'phone': self.lead_bob.phone,
            'email': 'ALICE@example.com ',  # Alice's email with mixed casing & whitespace
            'branch': self.branch_a.id,
            'status': self.lead_bob.status,
            'category': self.lead_bob.category or 'General',
        }
        form = AdminLeadForm(data=form_data, instance=self.lead_bob)
        self.assertFalse(form.is_valid(), "Form should be invalid when email belongs to another lead.")
        self.assertIn('email', form.errors)
        self.assertIn(f"Lead #{self.lead_alice.pk}", form.errors['email'][0])

    def test_admin_lead_edit_rejects_alternate_phone_matching_another_primary(self):
        """Setting Bob's alternate phone to Alice's primary phone must fail validation."""
        form_data = {
            'name': self.lead_bob.name,
            'phone': self.lead_bob.phone,
            'email': self.lead_bob.email,
            'alternate_phone': '9876543210',  # Alice's primary phone
            'branch': self.branch_a.id,
            'status': self.lead_bob.status,
            'category': self.lead_bob.category or 'General',
        }
        form = AdminLeadForm(data=form_data, instance=self.lead_bob)
        self.assertFalse(form.is_valid(), "Form should be invalid when alternate_phone matches another lead's phone.")
        self.assertIn('alternate_phone', form.errors)
        self.assertIn(f"Lead #{self.lead_alice.pk}", form.errors['alternate_phone'][0])

    def test_alternate_phone_cannot_be_same_as_own_primary_phone(self):
        """Setting Alice's alternate phone to her own primary phone must fail validation."""
        form_data = {
            'name': self.lead_alice.name,
            'phone': self.lead_alice.phone,
            'email': self.lead_alice.email,
            'alternate_phone': self.lead_alice.phone,
            'branch': self.branch_a.id,
            'status': self.lead_alice.status,
            'category': self.lead_alice.category or 'General',
        }
        form = AdminLeadForm(data=form_data, instance=self.lead_alice)
        self.assertFalse(form.is_valid(), "Form should be invalid when alternate phone is identical to primary phone.")
        self.assertIn('alternate_phone', form.errors)
        self.assertIn("cannot be identical", form.errors['alternate_phone'][0].lower())

    def test_ambiguous_match_surfaces_both_field_errors_without_merging(self):
        """
        If Charlie's phone is changed to Alice's phone AND email is changed to Bob's email,
        both field-level errors must be surfaced simultaneously. Neither lead must be merged or deleted.
        """
        form_data = {
            'name': self.lead_charlie.name,
            'phone': '9876543210',  # Alice's phone
            'email': 'bob@example.com',  # Bob's email
            'branch': self.branch_a.id,
            'status': self.lead_charlie.status,
            'category': self.lead_charlie.category or 'General',
        }
        form = AdminLeadForm(data=form_data, instance=self.lead_charlie)
        self.assertFalse(form.is_valid())
        self.assertIn('phone', form.errors)
        self.assertIn('email', form.errors)
        self.assertIn(f"Lead #{self.lead_alice.pk}", form.errors['phone'][0])
        self.assertIn(f"Lead #{self.lead_bob.pk}", form.errors['email'][0])

        # Verify no leads were deleted
        self.assertEqual(Lead.objects.count(), 3)
        self.assertTrue(Lead.objects.filter(pk=self.lead_alice.pk).exists())
        self.assertTrue(Lead.objects.filter(pk=self.lead_bob.pk).exists())
        self.assertTrue(Lead.objects.filter(pk=self.lead_charlie.pk).exists())

    def test_manager_lead_edit_rejects_duplicate_alternate_phone(self):
        """ManagerLeadForm must reject alternate phone matching an existing lead."""
        form_data = {
            'assigned_telecaller': self.telecaller_user.id,
            'status': self.lead_bob.status,
            'category': self.lead_bob.category or 'General',
            'alternate_phone': '+91-98765-43210',  # Alice's phone
            'notes': 'Checking alternate phone validation',
        }
        form = ManagerLeadForm(data=form_data, instance=self.lead_bob, manager=self.manager_user)
        self.assertFalse(form.is_valid(), "ManagerLeadForm should reject duplicate alternate_phone.")
        self.assertIn('alternate_phone', form.errors)
        self.assertIn(f"Lead #{self.lead_alice.pk}", form.errors['alternate_phone'][0])

    def test_telecaller_lead_edit_rejects_duplicate_email(self):
        """TelecallerLeadForm must reject email belonging to another lead."""
        form_data = {
            'status': self.lead_bob.status,
            'category': self.lead_bob.category or 'General',
            'email': 'alice@example.com',  # Alice's email
            'notes': 'Telecaller updated lead',
        }
        form = TelecallerLeadForm(data=form_data, instance=self.lead_bob)
        self.assertFalse(form.is_valid(), "TelecallerLeadForm should reject duplicate email.")
        self.assertIn('email', form.errors)
        self.assertIn(f"Lead #{self.lead_alice.pk}", form.errors['email'][0])

    def test_telecaller_lead_edit_allows_own_unchanged_email(self):
        """TelecallerLeadForm must allow saving own unchanged email."""
        form_data = {
            'status': self.lead_bob.status,
            'category': self.lead_bob.category or 'General',
            'email': self.lead_bob.email,
            'notes': 'Telecaller verified existing email',
        }
        form = TelecallerLeadForm(data=form_data, instance=self.lead_bob)
        self.assertTrue(form.is_valid(), f"TelecallerLeadForm should accept own email. Errors: {form.errors}")

    def test_bulk_import_persists_normalized_phone_digits(self):
        """Bulk CSV import must normalize and persist digits-only phone numbers in Lead.phone."""
        csv_content = (
            "Name,Phone,Email,Branch,Product,Notes\n"
            "David Miller,+91 98400 55667,david@example.com,Phase1 Branch A,Python Master,Fresh import\n"
        )
        csv_file = io.BytesIO(csv_content.encode('utf-8'))
        csv_file.name = "test_import_normalize.csv"

        successful, failed, errors = import_leads_file(csv_file, self.admin_user)
        self.assertEqual(successful, 1, f"Import should succeed with 1 lead. Errors: {errors}")
        self.assertEqual(failed, 0)

        imported_lead = Lead.objects.filter(email="david@example.com").first()
        self.assertIsNotNone(imported_lead)
        # Primary phone must be stored as clean digits without +91 or spaces
        self.assertEqual(imported_lead.phone, "9840055667")

    def test_bulk_import_preserves_10_day_duplicate_rule(self):
        """Bulk import of an existing lead within 10 days must NOT create a duplicate Lead row."""
        # Alice was created just now (< 10 days)
        initial_lead_count = Lead.objects.count()

        csv_content = (
            "Name,Phone,Email,Branch,Product,Notes\n"
            "Alice Smith,+91 98765 43210,alice@example.com,Phase1 Branch A,Python Master,Re-inquiry in CSV\n"
        )
        csv_file = io.BytesIO(csv_content.encode('utf-8'))
        csv_file.name = "test_alice_dup.csv"

        successful, failed, errors = import_leads_file(csv_file, self.admin_user)
        self.assertEqual(successful, 1)

        # No new lead row should be created
        self.assertEqual(Lead.objects.count(), initial_lead_count)

        # A DuplicateLeadRecord must be recorded
        dup_rec = DuplicateLeadRecord.objects.filter(original_lead=self.lead_alice).first()
        self.assertIsNotNone(dup_rec)
        self.assertEqual(dup_rec.record_type, 'INCOMING_DUPLICATE')
        self.assertEqual(dup_rec.action_taken, 'RETAINED_WITHIN_10_DAYS')

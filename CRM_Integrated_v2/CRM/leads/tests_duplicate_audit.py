import datetime
from django.test import TestCase, override_settings
from django.utils import timezone
from accounts.models import User, UserRole
from branches.models import Branch, SalesHeadBranchAccess
from lead_channels.models import Channel
from products.models import Product
from activities.models import Activity, Notification
from leads.models import (
    Lead, LeadStatus, DuplicateLeadRecord, TelecallerLeadSetup,
    LeadStatusHistory
)
from leads.intake import intake_lead, IntakeResult, phone10
from leads.duplicates import (
    process_incoming_lead_with_10day_rule,
    handle_incoming_lead_duplicate,
    normalize_phone,
)


class DuplicateLeadAuditSystemTests(TestCase):
    """
    Comprehensive test suite for the centralized cross-source duplicate lead
    detection and audit system.
    """

    def setUp(self):
        # 1. Create Branches
        self.branch_a, _ = Branch.objects.get_or_create(name="Audit Branch A", defaults={"status": "Active"})
        self.branch_b, _ = Branch.objects.get_or_create(name="Audit Branch B", defaults={"status": "Active"})

        # 2. Create Users (Sales Head & Telecallers)
        self.sales_head_a, _ = User.objects.get_or_create(
            username="sh_audit_a",
            defaults={
                "role": UserRole.SALES_HEAD,
                "branch": self.branch_a,
                "first_name": "Ramesh",
                "last_name": "Manager"
            }
        )
        self.sales_head_a.set_password("Password123!")
        self.sales_head_a.save()
        SalesHeadBranchAccess.objects.get_or_create(sales_head=self.sales_head_a, branch=self.branch_a)

        self.telecaller_a, _ = User.objects.get_or_create(
            username="tc_audit_a",
            defaults={
                "role": UserRole.TELECALLER,
                "branch": self.branch_a,
                "first_name": "Pooja",
                "last_name": "Caller"
            }
        )
        self.telecaller_a.set_password("Password123!")
        self.telecaller_a.save()
        TelecallerLeadSetup.objects.get_or_create(
            telecaller=self.telecaller_a,
            branch=self.branch_a,
            defaults={"assignment_percentage": 100, "lead_count": 50}
        )

        self.telecaller_b, _ = User.objects.get_or_create(
            username="tc_audit_b",
            defaults={
                "role": UserRole.TELECALLER,
                "branch": self.branch_b,
                "first_name": "Vikram",
                "last_name": "Caller"
            }
        )
        self.telecaller_b.set_password("Password123!")
        self.telecaller_b.save()
        TelecallerLeadSetup.objects.get_or_create(
            telecaller=self.telecaller_b,
            branch=self.branch_b,
            defaults={"assignment_percentage": 100, "lead_count": 50}
        )

        # 3. Products & Channels
        self.channel_meta, _ = Channel.objects.get_or_create(name="Facebook")
        self.channel_wa, _ = Channel.objects.get_or_create(name="WhatsApp")
        self.product_python, _ = Product.objects.get_or_create(name="Python Full Stack")
        self.product_data, _ = Product.objects.get_or_create(name="Data Science")


    def test_phone_normalization(self):
        """Rule 1: Phone numbers normalize consistently to 10 digits across formats."""
        self.assertEqual(phone10("+91 98765 43210"), "9876543210")
        self.assertEqual(phone10("09876543210"), "9876543210")
        self.assertEqual(phone10("919876543210"), "9876543210")
        self.assertEqual(phone10("98765-43210"), "9876543210")
        self.assertEqual(phone10("(98765) 43210"), "9876543210")
        self.assertEqual(phone10("invalid"), "")

    def test_case_1_no_matching_lead_creates_new(self):
        """Rule 8: When no matching lead exists, create normally and assign."""
        res = intake_lead(
            phone="+91 98400 11223",
            source="Facebook",
            name="Anand Kumar",
            email="anand@example.com",
            branch=self.branch_a,
            product=self.product_python,
            note="Initial inquiry"
        )
        self.assertTrue(res.created)
        self.assertEqual(res.action_taken, "CREATED_NEW")
        self.assertIsNone(res.duplicate_record)

        lead = res.lead
        self.assertEqual(lead.phone, "9840011223")
        self.assertEqual(lead.name, "Anand Kumar")
        self.assertEqual(lead.branch, self.branch_a)
        self.assertEqual(lead.status, LeadStatus.NEW)
        self.assertEqual(lead.assigned_telecaller, self.telecaller_a)
        self.assertEqual(DuplicateLeadRecord.objects.count(), 0)

        # Check tuple unpacking compatibility
        lead_unpack, created_unpack = res
        self.assertEqual(lead_unpack.id, lead.id)
        self.assertTrue(created_unpack)

    def test_case_2_duplicate_within_10_days_retains_existing(self):
        """Rule 6: If <= 10 days elapsed, retain existing lead completely untouched."""
        now = timezone.now()
        orig_time = now - datetime.timedelta(days=4)

        # Create original lead 4 days ago
        orig_lead = Lead.objects.create(
            name="Deepa Sharma",
            phone="9840022334",
            email="deepa@example.com",
            branch=self.branch_a,
            assigned_telecaller=self.telecaller_a,
            assigned_sales_head=self.sales_head_a,
            status=LeadStatus.INTERESTED,
            source="Manual Entry",
            notes="Original note from staff."
        )
        # Override created_at to 4 days ago
        Lead.objects.filter(id=orig_lead.id).update(created_at=orig_time)
        orig_lead.refresh_from_db()

        # Incoming duplicate via WhatsApp in Branch B (4 days elapsed)
        with self.captureOnCommitCallbacks(execute=True):
            res = intake_lead(
                phone="+91 98400 22334",
                source="WhatsApp",
                name="Deepa S.",
                email="deepa.new@example.com",
                branch=self.branch_b,
                note="I want Python details",
                incoming_timestamp=now
            )

        self.assertFalse(res.created)
        self.assertEqual(res.action_taken, "RETAINED_WITHIN_10_DAYS")
        self.assertIsNotNone(res.duplicate_record)

        # Verify existing lead was NOT modified
        orig_lead.refresh_from_db()
        self.assertEqual(orig_lead.branch, self.branch_a)  # Branch NOT changed
        self.assertEqual(orig_lead.status, LeadStatus.INTERESTED)  # Status NOT changed
        self.assertEqual(orig_lead.assigned_telecaller, self.telecaller_a)  # Assignment NOT changed
        self.assertEqual(orig_lead.email, "deepa@example.com")  # Email NOT overwritten
        self.assertEqual(orig_lead.source, "Manual Entry")  # Source NOT overwritten

        # Verify DuplicateLeadRecord audit record
        dup = res.duplicate_record
        dup.refresh_from_db()
        self.assertEqual(dup.original_lead, orig_lead)
        self.assertEqual(dup.normalized_phone, "9840022334")
        self.assertEqual(dup.action_taken, "RETAINED_WITHIN_10_DAYS")
        self.assertEqual(dup.branch, self.branch_b)
        self.assertEqual(dup.existing_branch, self.branch_a)
        self.assertEqual(dup.existing_source, "Manual Entry")
        self.assertAlmostEqual(dup.elapsed_days, 4.0, delta=0.1)
        self.assertEqual(dup.field_changes, {})
        self.assertEqual(dup.notification_status, "SENT")


        # Verify notification created for assigned telecaller
        notifs = Notification.objects.filter(recipient=self.telecaller_a, notification_type="duplicate_lead")
        self.assertTrue(notifs.exists())

    def test_case_3_duplicate_exactly_10_days_retained(self):
        """Rule 6 boundary: Exactly 10.0 days (240 hours) is <= 10 days -> RETAINED."""
        now = timezone.now()
        orig_time = now - datetime.timedelta(days=10)

        orig_lead = Lead.objects.create(
            name="Suresh Raina",
            phone="9840033445",
            branch=self.branch_a,
            assigned_telecaller=self.telecaller_a,
            status=LeadStatus.FOLLOW_UP,
            source="Website"
        )
        Lead.objects.filter(id=orig_lead.id).update(created_at=orig_time)
        orig_lead.refresh_from_db()

        res = intake_lead(
            phone="9840033445",
            source="Google Call",
            branch=self.branch_b,
            incoming_timestamp=now
        )
        self.assertFalse(res.created)
        self.assertEqual(res.action_taken, "RETAINED_WITHIN_10_DAYS")
        orig_lead.refresh_from_db()
        self.assertEqual(orig_lead.branch, self.branch_a)
        self.assertEqual(orig_lead.status, LeadStatus.FOLLOW_UP)

    def test_case_4_duplicate_after_10_days_updates_preserving_lead_id(self):
        """Rule 7: > 10 days elapsed -> update existing lead, preserve lead ID, change branch."""
        now = timezone.now()
        orig_time = now - datetime.timedelta(days=25)

        orig_lead = Lead.objects.create(
            name="Kavitha",
            phone="9840044556",
            email="",
            branch=self.branch_a,
            assigned_telecaller=self.telecaller_a,
            status=LeadStatus.LOST,
            source="Manual Entry",
            notes="Student was unavailable previously."
        )
        Lead.objects.filter(id=orig_lead.id).update(created_at=orig_time)
        orig_lead.refresh_from_db()
        orig_id = orig_lead.id

        # Incoming re-enquiry after 25 days for Branch B
        with self.captureOnCommitCallbacks(execute=True):
            res = intake_lead(
                phone="09840044556",
                source="Facebook",
                name="Kavitha Murugan",
                email="kavitha@example.com",
                branch=self.branch_b,
                product=self.product_data,
                note="Re-enquiring for Data Science batch",
                incoming_timestamp=now
            )

        self.assertFalse(res.created)
        self.assertEqual(res.action_taken, "UPDATED_AFTER_10_DAYS")

        # CRITICAL: Preserve existing Lead ID
        updated_lead = res.lead
        self.assertEqual(updated_lead.id, orig_id)
        self.assertEqual(Lead.objects.filter(phone="9840044556").count(), 1)

        # Check in-place updates
        updated_lead.refresh_from_db()
        self.assertEqual(updated_lead.branch, self.branch_b)  # Branch updated to incoming
        self.assertTrue(updated_lead.secondary_branches.filter(id=self.branch_a.id).exists())  # Old branch retained
        self.assertEqual(updated_lead.status, LeadStatus.NEW)  # Reactivated to NEW
        self.assertEqual(updated_lead.email, "kavitha@example.com")  # Blank email filled
        self.assertEqual(updated_lead.product, self.product_data)  # Product filled
        self.assertEqual(updated_lead.assigned_telecaller, self.telecaller_b)  # Reassigned for Branch B
        self.assertIn("Student was unavailable previously.", updated_lead.notes)  # History preserved
        self.assertIn("[Re-Enquiry - Facebook", updated_lead.notes)  # Timeline appended

        # Audit record
        dup = res.duplicate_record
        dup.refresh_from_db()
        self.assertEqual(dup.original_lead, updated_lead)
        self.assertEqual(dup.action_taken, "UPDATED_AFTER_10_DAYS")
        self.assertAlmostEqual(dup.elapsed_days, 25.0, delta=0.2)
        self.assertIn("branch", dup.field_changes)
        self.assertIn("status", dup.field_changes)
        self.assertEqual(dup.notification_status, "SENT")


        # LeadStatusHistory recorded
        hist = LeadStatusHistory.objects.filter(lead=updated_lead, new_status=LeadStatus.NEW)
        self.assertTrue(hist.exists())

    def test_case_5_idempotency_suppresses_repeated_events(self):
        """Rule 9: provider_event_id deduplication suppresses repeated lead mutation & notifications."""
        res1 = intake_lead(
            phone="9840055667",
            source="Facebook",
            name="Ganesh",
            branch=self.branch_a,
            provider_event_id="meta_evt_101"
        )
        self.assertTrue(res1.created)
        self.assertEqual(res1.action_taken, "CREATED_NEW")

        # Now simulate duplicate delivery within 10 days with same event ID
        res2 = intake_lead(
            phone="9840055667",
            source="Facebook",
            name="Ganesh Duplicate",
            branch=self.branch_b,
            provider_event_id="meta_evt_dup_202"
        )
        self.assertFalse(res2.created)
        self.assertEqual(res2.action_taken, "RETAINED_WITHIN_10_DAYS")

        # Now simulate re-sending identical event ID "meta_evt_dup_202"
        res3 = intake_lead(
            phone="9840055667",
            source="Facebook",
            name="Ganesh Retry",
            branch=self.branch_b,
            provider_event_id="meta_evt_dup_202"
        )
        self.assertFalse(res3.created)
        self.assertEqual(res3.action_taken, "IDEMPOTENT_IGNORED")
        # Ensure only 1 DuplicateLeadRecord was created for meta_evt_dup_202
        self.assertEqual(DuplicateLeadRecord.objects.filter(provider_event_id="meta_evt_dup_202").count(), 1)

    def test_case_6_alternate_phone_matching(self):
        """Rule 1: Cross-match on alternate phone as well as primary phone."""
        orig = Lead.objects.create(
            name="Rajesh",
            phone="9840011111",
            alternate_phone="9840099999",
            branch=self.branch_a,
            status=LeadStatus.NEW
        )
        res = intake_lead(
            phone="+91 98400 99999",
            source="Google Call",
            name="Rajesh Alt"
        )
        self.assertFalse(res.created)
        self.assertEqual(res.lead.id, orig.id)

    def test_case_7_invalid_phone_raises_error(self):
        """Validation: Invalid phone raises ValueError without DB changes."""
        with self.assertRaises(ValueError):
            intake_lead(phone="not_a_phone", source="Manual")

    def test_case_8_process_incoming_lead_with_10day_rule_wrapper(self):
        """Compatibility: process_incoming_lead_with_10day_rule returns (lead, is_dup, dup_rec)."""
        lead_data = {
            'name': 'Pooja Test',
            'phone': '9840066778',
            'email': 'pooja@test.com',
            'notes': 'Form test inquiry'
        }
        # First call -> New
        lead, is_dup, dup_rec = process_incoming_lead_with_10day_rule(
            lead_data=lead_data,
            branch=self.branch_a,
            source="Google Form"
        )
        self.assertFalse(is_dup)
        self.assertIsNone(dup_rec)
        self.assertEqual(lead.phone, "9840066778")

        # Second call same day -> Duplicate within 10 days
        lead2, is_dup2, dup_rec2 = process_incoming_lead_with_10day_rule(
            lead_data=lead_data,
            branch=self.branch_b,
            source="Google Form"
        )
        self.assertTrue(is_dup2)
        self.assertIsNotNone(dup_rec2)
        self.assertEqual(dup_rec2.action_taken, "RETAINED_WITHIN_10_DAYS")
        self.assertEqual(lead2.id, lead.id)

    def test_case_9_handle_incoming_lead_duplicate_wrapper(self):
        """Compatibility: handle_incoming_lead_duplicate routes through 10-day engine."""
        now = timezone.now()
        orig_lead = Lead.objects.create(
            name="Mano",
            phone="9840077889",
            branch=self.branch_a,
            status=LeadStatus.NEW
        )
        # Calling handle_incoming_lead_duplicate immediately (< 10 days)
        res_lead = handle_incoming_lead_duplicate(
            existing_lead=orig_lead,
            incoming_data={'name': 'Mano Edit', 'phone': '9840077889'},
            branch=self.branch_b,
            source_label="Manual Entry"
        )
        self.assertEqual(res_lead.id, orig_lead.id)
        # Within 10 days: branch remains unchanged
        orig_lead.refresh_from_db()
        self.assertEqual(orig_lead.branch, self.branch_a)
        # Audit record created
        self.assertTrue(DuplicateLeadRecord.objects.filter(original_lead=orig_lead, action_taken="RETAINED_WITHIN_10_DAYS").exists())

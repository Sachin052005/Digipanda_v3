# -*- coding: utf-8 -*-
from django.test import TestCase, Client
from django.urls import reverse
from django.utils import timezone
from datetime import timedelta
from accounts.models import User, UserRole
from branches.models import Branch, SalesHeadBranchAccess
from products.models import Product
from leads.models import Lead, LeadStatus, DuplicateLeadRecord
from leads.intake import intake_lead
from leads.duplicates import keep_single_lead_for_group


class DuplicateDataTableArchitectureTests(TestCase):
    """
    Automated verification for the dedicated duplicate data table architecture.
    """

    def setUp(self):
        self.client = Client()

        # Create Branches
        self.branch_a, _ = Branch.objects.get_or_create(name="Duplicate Test Branch A", defaults={"status": "Active"})
        self.branch_b, _ = Branch.objects.get_or_create(name="Duplicate Test Branch B", defaults={"status": "Active"})

        # Create Admin User
        self.admin = User.objects.create_superuser(
            username="dup_admin_test",
            email="dup_admin@techpanda.test",
            password="AdminPassword123!"
        )
        self.client.force_login(self.admin)

        # Create Product
        self.product, _ = Product.objects.get_or_create(name="Full Stack Python")

    def test_incoming_duplicate_stored_in_separate_table_with_payload(self):
        """
        Submitting an inquiry within 10 days for an existing phone number creates a record in
        DuplicateLeadRecord with record_type='INCOMING_DUPLICATE' and verbatim data_payload.
        """
        # 1. Create first lead
        res1 = intake_lead(
            phone="9876543210",
            source="Facebook",
            name="Aarav Sharma",
            email="aarav@techpanda.test",
            branch=self.branch_a,
            data_payload={"ad_name": "Summer Course Promo", "city": "Chennai"}
        )
        self.assertTrue(res1.created)
        primary_lead = res1.lead

        # 2. Duplicate submission 2 days later
        res2 = intake_lead(
            phone="9876543210",
            source="Google Form",
            name="Aarav Sharma",
            email="aarav@techpanda.test",
            branch=self.branch_a,
            data_payload={"preferred_timing": "Morning Batch", "utm_source": "google"}
        )
        self.assertFalse(res2.created)
        self.assertEqual(res2.action_taken, "RETAINED_WITHIN_10_DAYS")

        # Verify duplicate table contains the record
        dup_rec = DuplicateLeadRecord.objects.filter(original_lead=primary_lead).first()
        self.assertIsNotNone(dup_rec)
        self.assertEqual(dup_rec.record_type, "INCOMING_DUPLICATE")
        self.assertEqual(dup_rec.source, "Google Form")
        self.assertEqual(dup_rec.data_payload.get("preferred_timing"), "Morning Batch")

        # Verify primary lead remains single and clean
        self.assertEqual(Lead.objects.filter(phone__endswith="9876543210").count(), 1)

    def test_reenquiry_after_10_days_stored_with_reenquiry_type(self):
        """
        Submitting after 10 days marks DuplicateLeadRecord with record_type='REENQUIRY_DUPLICATE'.
        """
        past_time = timezone.now() - timedelta(days=20)
        lead = Lead.objects.create(
            name="Pooja Rao",
            phone="9123456780",
            email="pooja@techpanda.test",
            branch=self.branch_a,
            source="Website",
            status=LeadStatus.FOLLOW_UP
        )
        Lead.objects.filter(id=lead.id).update(created_at=past_time)

        res = intake_lead(
            phone="9123456780",
            source="WhatsApp",
            name="Pooja Rao",
            branch=self.branch_b,
            data_payload={"query": "Re-admission query for data science"}
        )

        self.assertFalse(res.created)
        self.assertEqual(res.action_taken, "UPDATED_AFTER_10_DAYS")

        dup_rec = DuplicateLeadRecord.objects.filter(original_lead=lead, record_type="REENQUIRY_DUPLICATE").first()
        self.assertIsNotNone(dup_rec)
        self.assertEqual(dup_rec.action_taken, "UPDATED_AFTER_10_DAYS")
        self.assertEqual(dup_rec.data_payload.get("query"), "Re-admission query for data science")

    def test_pre_merge_archiving_in_keep_single_lead(self):
        """
        When two duplicate leads exist in the database and keep_single_lead_for_group is called,
        the duplicate lead is archived into DuplicateLeadRecord with record_type='MERGED_ARCHIVE'
        before being deleted from the active Lead table.
        """
        lead1 = Lead.objects.create(
            name="Vikram Singh",
            phone="9988776655",
            email="vikram@techpanda.test",
            branch=self.branch_a,
            source="Walk-in",
            notes="Walked into Branch A"
        )
        lead2 = Lead.objects.create(
            name="Vikram S",
            phone="9988776655",
            email="vikram.alt@techpanda.test",
            branch=self.branch_b,
            source="Google Sheets",
            notes="Sheet import for Branch B"
        )

        self.assertEqual(Lead.objects.filter(phone="9988776655").count(), 2)

        # Merge leads
        primary = keep_single_lead_for_group(f"{lead1.id},{lead2.id}", user=self.admin)
        self.assertEqual(primary.id, lead1.id)

        # Active Lead table now only has 1 record
        self.assertEqual(Lead.objects.filter(phone="9988776655").count(), 1)

        # Duplicate table has the MERGED_ARCHIVE record with full payload snapshot
        archived_rec = DuplicateLeadRecord.objects.filter(
            original_lead=primary,
            record_type="MERGED_ARCHIVE"
        ).first()
        self.assertIsNotNone(archived_rec)
        self.assertEqual(archived_rec.action_taken, "MERGED_INTO_PRIMARY")
        self.assertEqual(archived_rec.data_payload.get("archived_lead_id"), lead2.id)
        self.assertEqual(archived_rec.data_payload.get("source"), "Google Sheets")
        self.assertIn("Branch B", archived_rec.data_payload.get("notes"))

    def test_payload_api_returns_json(self):
        """
        The /admin/duplicate-leads/<id>/payload/ endpoint returns formatted JSON data.
        """
        lead = Lead.objects.create(name="Deepak", phone="9898989898", branch=self.branch_a)
        dup_rec = DuplicateLeadRecord.objects.create(
            original_lead=lead,
            name="Deepak",
            phone="9898989898",
            record_type="INCOMING_DUPLICATE",
            source="Facebook Ads",
            branch=self.branch_a,
            data_payload={"utm_medium": "cpc", "lead_score": 85}
        )

        url = reverse("admin_duplicate_lead_payload", args=[dup_rec.id])
        resp = self.client.get(url, HTTP_X_REQUESTED_WITH="XMLHttpRequest")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertTrue(data.get("success"))
        self.assertEqual(data.get("data_payload", {}).get("lead_score"), 85)

    def test_promote_duplicate_to_independent_lead(self):
        """
        The /admin/duplicate-leads/<id>/promote/ endpoint creates a new independent lead
        from the duplicate record and marks record_type='MANUAL_PROMOTED'.
        """
        lead = Lead.objects.create(name="Parent Contact", phone="9797979797", branch=self.branch_a)
        dup_rec = DuplicateLeadRecord.objects.create(
            original_lead=lead,
            name="Sibling Student",
            phone="9797979797",
            email="sibling@techpanda.test",
            record_type="INCOMING_DUPLICATE",
            source="Web Form",
            branch=self.branch_b,
            duplicate_reason="Sibling shared phone"
        )

        url = reverse("admin_duplicate_lead_promote", args=[dup_rec.id])
        resp = self.client.post(url, HTTP_X_REQUESTED_WITH="XMLHttpRequest")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertTrue(data.get("success"))

        new_lead_id = data.get("new_lead_id")
        promoted_lead = Lead.objects.get(id=new_lead_id)
        self.assertEqual(promoted_lead.name, "Sibling Student")
        self.assertEqual(promoted_lead.email, "sibling@techpanda.test")

        dup_rec.refresh_from_db()
        self.assertEqual(dup_rec.record_type, "MANUAL_PROMOTED")
        self.assertEqual(dup_rec.action_taken, "MANUAL_PROMOTED")

    def test_csv_export_endpoint(self):
        """
        The /admin/duplicate-leads/export/ endpoint returns a valid CSV file stream.
        """
        lead = Lead.objects.create(name="Export Student", phone="9696969696", branch=self.branch_a)
        DuplicateLeadRecord.objects.create(
            original_lead=lead,
            name="Export Student",
            phone="9696969696",
            source="Meta Ads",
            branch=self.branch_a,
            data_payload={"city": "Madurai"}
        )

        url = reverse("admin_duplicate_leads_export")
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp["Content-Type"], "text/csv; charset=utf-8")
        self.assertIn("attachment; filename=", resp["Content-Disposition"])
        content = resp.content.decode("utf-8")
        self.assertIn("Export Student", content)
        self.assertIn("Meta Ads", content)

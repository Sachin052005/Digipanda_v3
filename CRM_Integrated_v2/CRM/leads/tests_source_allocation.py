import json
from django.test import TestCase, Client
from django.urls import reverse
from accounts.models import User, UserRole
from branches.models import Branch
from leads.models import (
    Lead, LeadStatus, TelecallerLeadSetup, LeadAllocationConfigAudit,
    CANONICAL_LEAD_SOURCES, normalize_lead_source
)
from leads.assignment import assign_new_lead, apply_branch_lead_distribution


class SourceAllocationTestCase(TestCase):
    def setUp(self):
        self.client = Client()
        self.branch = Branch.objects.create(name="Madurai Branch")

        self.admin = User.objects.create_user(
            username="admin_alloc",
            email="admin_alloc@test.com",
            password="Password@123",
            role=UserRole.ADMIN,
            branch=self.branch
        )

        self.tc1 = User.objects.create_user(
            username="tc1_alloc",
            email="tc1_alloc@test.com",
            password="Password@123",
            role=UserRole.TELECALLER,
            branch=self.branch
        )

        self.tc2 = User.objects.create_user(
            username="tc2_alloc",
            email="tc2_alloc@test.com",
            password="Password@123",
            role=UserRole.TELECALLER,
            branch=self.branch
        )

    def test_strict_100_percent_validation_on_save(self):
        """Saving percentages that do not sum to 100% must be rejected."""
        self.client.force_login(self.admin)
        url = reverse('admin_lead_setup')

        # Test < 100% (e.g. 80%)
        res = self.client.post(url, {
            'action': 'save_branch_allocation',
            'branch_id': self.branch.id,
            'source': 'WhatsApp',
            'active_telecallers': [self.tc1.id, self.tc2.id],
            f'percentage_{self.tc1.id}': 50,
            f'percentage_{self.tc2.id}': 30,
        }, HTTP_X_REQUESTED_WITH='XMLHttpRequest')
        self.assertEqual(res.status_code, 400)
        data = res.json()
        self.assertFalse(data['success'])
        self.assertIn("must equal exactly 100%", data['error'])

        # Test > 100% (e.g. 110%)
        res2 = self.client.post(url, {
            'action': 'save_branch_allocation',
            'branch_id': self.branch.id,
            'source': 'WhatsApp',
            'active_telecallers': [self.tc1.id, self.tc2.id],
            f'percentage_{self.tc1.id}': 60,
            f'percentage_{self.tc2.id}': 50,
        }, HTTP_X_REQUESTED_WITH='XMLHttpRequest')
        self.assertEqual(res2.status_code, 400)

        # Test valid 100% (60% + 40%)
        res3 = self.client.post(url, {
            'action': 'save_branch_allocation',
            'branch_id': self.branch.id,
            'source': 'WhatsApp',
            'active_telecallers': [self.tc1.id, self.tc2.id],
            f'percentage_{self.tc1.id}': 60,
            f'percentage_{self.tc2.id}': 40,
        }, HTTP_X_REQUESTED_WITH='XMLHttpRequest')
        self.assertEqual(res3.status_code, 200)
        self.assertTrue(res3.json()['success'])

        # Verify audit log was created
        audit = LeadAllocationConfigAudit.objects.filter(branch=self.branch, source='WhatsApp').first()
        self.assertIsNotNone(audit)
        self.assertEqual(audit.changed_by, self.admin)

    def test_independent_allocation_per_source(self):
        """Modifying one source must not alter another source's allocation."""
        self.client.force_login(self.admin)
        url = reverse('admin_lead_setup')

        # Configure WhatsApp: TC1 = 60%, TC2 = 40%
        self.client.post(url, {
            'action': 'save_branch_allocation',
            'branch_id': self.branch.id,
            'source': 'WhatsApp',
            'active_telecallers': [self.tc1.id, self.tc2.id],
            f'percentage_{self.tc1.id}': 60,
            f'percentage_{self.tc2.id}': 40,
        }, HTTP_X_REQUESTED_WITH='XMLHttpRequest')

        # Configure Facebook: TC1 = 50%, TC2 = 50%
        self.client.post(url, {
            'action': 'save_branch_allocation',
            'branch_id': self.branch.id,
            'source': 'Facebook',
            'active_telecallers': [self.tc1.id, self.tc2.id],
            f'percentage_{self.tc1.id}': 50,
            f'percentage_{self.tc2.id}': 50,
        }, HTTP_X_REQUESTED_WITH='XMLHttpRequest')

        # Verify WhatsApp setup unchanged
        wa_tc1 = TelecallerLeadSetup.objects.get(branch=self.branch, source='WhatsApp', telecaller=self.tc1)
        wa_tc2 = TelecallerLeadSetup.objects.get(branch=self.branch, source='WhatsApp', telecaller=self.tc2)
        self.assertEqual(wa_tc1.assignment_percentage, 60)
        self.assertEqual(wa_tc2.assignment_percentage, 40)

        # Verify Facebook setup
        fb_tc1 = TelecallerLeadSetup.objects.get(branch=self.branch, source='Facebook', telecaller=self.tc1)
        fb_tc2 = TelecallerLeadSetup.objects.get(branch=self.branch, source='Facebook', telecaller=self.tc2)
        self.assertEqual(fb_tc1.assignment_percentage, 50)
        self.assertEqual(fb_tc2.assignment_percentage, 50)

    def test_automatic_lead_routing_by_source(self):
        """New leads entering the system must route according to their source rule."""
        # Configure WhatsApp: TC1 = 100%
        TelecallerLeadSetup.objects.update_or_create(
            branch=self.branch,
            source='WhatsApp',
            telecaller=self.tc1,
            defaults={'assignment_percentage': 100, 'is_active': True}
        )
        TelecallerLeadSetup.objects.update_or_create(
            branch=self.branch,
            source='WhatsApp',
            telecaller=self.tc2,
            defaults={'assignment_percentage': 0, 'is_active': False}
        )

        # Configure Facebook: TC2 = 100%
        TelecallerLeadSetup.objects.update_or_create(
            branch=self.branch,
            source='Facebook',
            telecaller=self.tc1,
            defaults={'assignment_percentage': 0, 'is_active': False}
        )
        TelecallerLeadSetup.objects.update_or_create(
            branch=self.branch,
            source='Facebook',
            telecaller=self.tc2,
            defaults={'assignment_percentage': 100, 'is_active': True}
        )

        # Ingest WhatsApp lead
        wa_lead = Lead.objects.create(
            name="WhatsApp Lead",
            phone="9876500001",
            branch=self.branch,
            source="WhatsApp",
            status=LeadStatus.NEW
        )
        assigned_wa = assign_new_lead(wa_lead, branch=self.branch, source="WhatsApp")
        self.assertTrue(assigned_wa)
        wa_lead.refresh_from_db()
        self.assertEqual(wa_lead.assigned_telecaller, self.tc1)
        self.assertEqual(wa_lead.assignment_status, 'Assigned')

        # Ingest Facebook lead
        fb_lead = Lead.objects.create(
            name="Facebook Lead",
            phone="9876500002",
            branch=self.branch,
            source="Facebook",
            status=LeadStatus.NEW
        )
        assigned_fb = assign_new_lead(fb_lead, branch=self.branch, source="Facebook")
        self.assertTrue(assigned_fb)
        fb_lead.refresh_from_db()
        self.assertEqual(fb_lead.assigned_telecaller, self.tc2)
        self.assertEqual(fb_lead.assignment_status, 'Assigned')

    def test_unallocated_source_pending_assignment_fallback(self):
        """Lead from an unconfigured source with no fallback rule goes to Pending Assignment."""
        # Unconfigured source 'Website'
        web_lead = Lead.objects.create(
            name="Website Lead",
            phone="9876500003",
            branch=self.branch,
            source="Website",
            status=LeadStatus.NEW
        )
        res = assign_new_lead(web_lead, branch=self.branch, source="Website")
        self.assertFalse(res)
        web_lead.refresh_from_db()
        self.assertEqual(web_lead.assignment_status, 'Pending Assignment')
        self.assertIn("No active telecallers or allocation configured", web_lead.pending_assignment_reason)

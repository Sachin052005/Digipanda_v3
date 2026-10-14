import json
from decimal import Decimal
from django.test import TestCase, Client
from django.urls import reverse
from django.core.exceptions import ValidationError
from accounts.models import User, UserRole
from branches.models import Branch
from lead_channels.models import Channel
from products.models import Product
from followups.models import FollowUp, FollowUpStatus
from leads.models import (
    Lead, LeadTag, LeadAssignmentHistory, BulkOperationRecord, BulkOperationStatus
)
from leads.bulk_edit_service import (
    calculate_percentage_distribution,
    resolve_authorized_leads,
    preview_bulk_edit,
    execute_bulk_edit,
)


class BulkEditMathAndServiceTests(TestCase):
    def setUp(self):
        self.branch1 = Branch.objects.create(name="Trichy Main", status="Active")
        self.branch2 = Branch.objects.create(name="Madurai", status="Active")
        self.channel = Channel.objects.create(name="Website", status="Active")
        self.product = Product.objects.create(name="Full Stack Dev", price=25000, status="Active")

        self.admin = User.objects.create_user(
            username="admin_bulk", email="admin_bulk@crm.com",
            password="Password123!", role=UserRole.ADMIN, is_staff=True, is_superuser=True
        )
        self.branch_head = User.objects.create_user(
            username="bhead_bulk", email="bhead_bulk@crm.com",
            password="Password123!", role=UserRole.BRANCH_HEAD, branch=self.branch1
        )
        self.counselor = User.objects.create_user(
            username="counselor_bulk", email="counselor_bulk@crm.com",
            password="Password123!", role=UserRole.COUNSELOR, branch=self.branch1
        )
        self.telecaller1 = User.objects.create_user(
            username="telecaller_bulk1", email="telecaller_bulk1@crm.com",
            password="Password123!", role=UserRole.TELECALLER, branch=self.branch1
        )
        self.telecaller2 = User.objects.create_user(
            username="telecaller_bulk2", email="telecaller_bulk2@crm.com",
            password="Password123!", role=UserRole.TELECALLER, branch=self.branch1
        )
        self.receptionist = User.objects.create_user(
            username="receptionist_bulk", email="receptionist_bulk@crm.com",
            password="Password123!", role=UserRole.RECEPTIONIST, branch=self.branch1
        )

        # Create tags
        self.tag_hot = LeadTag.objects.create(name="Hot Lead", color="#ef4444")
        self.tag_followup = LeadTag.objects.create(name="Needs Followup", color="#3b82f6")

        # Create leads in branch 1
        self.leads_b1 = []
        for i in range(1, 11):
            lead = Lead.objects.create(
                name=f"Lead B1 {i}",
                phone=f"98765432{i:02d}",
                branch=self.branch1,
                channel=self.channel,
                product=self.product,
                status="New Lead",
                rating=1
            )
            self.leads_b1.append(lead)

        # Create lead in branch 2
        self.lead_b2 = Lead.objects.create(
            name="Lead B2 Madurai",
            phone="9876543299",
            branch=self.branch2,
            channel=self.channel,
            product=self.product,
            status="New Lead",
            rating=1
        )

    def test_percentage_distribution_math(self):
        # 50% / 50% on 200 leads -> [100, 100]
        allocs = [{'user_id': 1, 'percentage': 50}, {'user_id': 2, 'percentage': 50}]
        res = calculate_percentage_distribution(200, allocs)
        res_map = {d['user_id']: d['count'] for d in res}
        self.assertEqual(res_map[1], 100)
        self.assertEqual(res_map[2], 100)

        # 50% / 30% / 20% on 200 leads -> [100, 60, 40]
        allocs3 = [
            {'user_id': 1, 'percentage': 50},
            {'user_id': 2, 'percentage': 30},
            {'user_id': 3, 'percentage': 20}
        ]
        res3 = calculate_percentage_distribution(200, allocs3)
        res3_map = {d['user_id']: d['count'] for d in res3}
        self.assertEqual(res3_map[1], 100)
        self.assertEqual(res3_map[2], 60)
        self.assertEqual(res3_map[3], 40)

        # 33% / 33% / 34% on 100 leads -> [33, 33, 34]
        allocs_odd = [
            {'user_id': 1, 'percentage': 33},
            {'user_id': 2, 'percentage': 33},
            {'user_id': 3, 'percentage': 34}
        ]
        res_odd = calculate_percentage_distribution(100, allocs_odd)
        res_odd_map = {d['user_id']: d['count'] for d in res_odd}
        self.assertEqual(res_odd_map[1], 33)
        self.assertEqual(res_odd_map[2], 33)
        self.assertEqual(res_odd_map[3], 34)

        # 50% / 50% on 7 leads -> [4, 3] remainder absorbed cleanly
        res_rem = calculate_percentage_distribution(7, allocs)
        self.assertEqual(sum(d['count'] for d in res_rem), 7)
        res_rem_map = {d['user_id']: d['count'] for d in res_rem}
        self.assertEqual(res_rem_map[1], 4)
        self.assertEqual(res_rem_map[2], 3)

        # Sum != 100 raises ValidationError
        invalid_alloc = [{'user_id': 1, 'percentage': 50}, {'user_id': 2, 'percentage': 40}]
        with self.assertRaises(ValidationError):
            calculate_percentage_distribution(100, invalid_alloc)

    def test_resolve_authorized_leads_permissions(self):
        all_ids = [l.id for l in self.leads_b1] + [self.lead_b2.id]

        # Admin resolves all 11 leads
        admin_qs = resolve_authorized_leads(self.admin, lead_ids=all_ids)
        self.assertEqual(admin_qs.count(), 11)

        # Branch Head resolves only branch 1 leads (10 leads), branch 2 lead is excluded
        bhead_qs = resolve_authorized_leads(self.branch_head, lead_ids=all_ids)
        self.assertEqual(bhead_qs.count(), 10)
        self.assertFalse(bhead_qs.filter(id=self.lead_b2.id).exists())

        # Receptionist cannot resolve leads for bulk editing
        rec_qs = resolve_authorized_leads(self.receptionist, lead_ids=all_ids)
        self.assertEqual(rec_qs.count(), 0)

    def test_preview_bulk_edit_calculation(self):
        lead_ids = [l.id for l in self.leads_b1[:5]]
        changes = {
            'status': 'Contacted',
            'rating': 4,
            'add_tags': [self.tag_hot.id],
            'reassign_role': 'telecaller',
            'reassign_mode': 'single',
            'single_assignee_id': self.telecaller1.id,
        }
        preview = preview_bulk_edit(self.admin, lead_ids=lead_ids, changes=changes)
        self.assertTrue(preview['success'])
        self.assertEqual(preview['authorized_count'], 5)
        self.assertIn('status', preview['changes_summary'])
        self.assertEqual(preview['changes_summary']['status']['target_status'], 'Contacted')
        self.assertEqual(preview['changes_summary']['rating']['target_rating'], 4)
        self.assertEqual(len(preview['allocation_summary']), 1)
        self.assertEqual(preview['allocation_summary'][0]['count'], 5)

    def test_execute_bulk_edit_single_reassignment_and_tags(self):
        lead_ids = [l.id for l in self.leads_b1[:4]]
        # Assign tag_followup initially
        for l in self.leads_b1[:4]:
            l.tags.add(self.tag_followup)

        changes = {
            'status': 'Contacted',
            'rating': 5,
            'add_tags': [self.tag_hot.id],
            'remove_tags': [self.tag_followup.id],
            'reassign_role': 'telecaller',
            'reassign_mode': 'single',
            'single_assignee_id': self.telecaller1.id,
            'pending_task_handling': 'preserve',
            'custom_fields': {'qualification': 'Graduate', 'preferred_batch': 'Weekend'}
        }
        res = execute_bulk_edit(
            user=self.admin,
            lead_ids=lead_ids,
            changes=changes,
            idempotency_key='test-key-001',
            reassignment_note='Bulk telecaller campaign launch'
        )
        self.assertEqual(res['status'], BulkOperationStatus.COMPLETED)
        self.assertEqual(res['success_count'], 4)
        self.assertEqual(res['failed_count'], 0)

        # Check records in DB
        for lid in lead_ids:
            ld = Lead.objects.get(id=lid)
            self.assertEqual(ld.status, 'Contacted')
            self.assertEqual(ld.rating, 5)
            self.assertEqual(ld.assigned_telecaller, self.telecaller1)
            self.assertEqual(ld.custom_fields.get('qualification'), 'Graduate')
            self.assertEqual(ld.custom_fields.get('preferred_batch'), 'Weekend')
            self.assertTrue(ld.tags.filter(id=self.tag_hot.id).exists())
            self.assertFalse(ld.tags.filter(id=self.tag_followup.id).exists())

        # Check audit record
        audit = BulkOperationRecord.objects.get(idempotency_key='test-key-001')
        self.assertEqual(audit.success_count, 4)
        self.assertEqual(audit.actor, self.admin)
        self.assertEqual(audit.reassignment_note, 'Bulk telecaller campaign launch')

    def test_execute_bulk_edit_percentage_distribution(self):
        lead_ids = [l.id for l in self.leads_b1]  # 10 leads
        changes = {
            'reassign_role': 'telecaller',
            'reassign_mode': 'percentage',
            'percentage_allocations': [
                {'user_id': self.telecaller1.id, 'percentage': 60},
                {'user_id': self.telecaller2.id, 'percentage': 40}
            ],
            'pending_task_handling': 'reassign'
        }
        res = execute_bulk_edit(
            user=self.admin,
            lead_ids=lead_ids,
            changes=changes,
            idempotency_key='test-key-pct-100',
            reassignment_note='Split 60/40 test'
        )
        self.assertEqual(res['status'], BulkOperationStatus.COMPLETED)
        self.assertEqual(res['success_count'], 10)

        tc1_count = Lead.objects.filter(id__in=lead_ids, assigned_telecaller=self.telecaller1).count()
        tc2_count = Lead.objects.filter(id__in=lead_ids, assigned_telecaller=self.telecaller2).count()
        self.assertEqual(tc1_count, 6)
        self.assertEqual(tc2_count, 4)

    def test_pending_tasks_handling(self):
        lead = self.leads_b1[0]
        lead.assigned_telecaller = self.telecaller1
        lead.save()

        # Create a pending follow-up for telecaller1
        task = FollowUp.objects.create(
            lead=lead,
            assigned_user=self.telecaller1,
            telecaller=self.telecaller1,
            status=FollowUpStatus.PENDING,
            follow_up_date="2026-10-15",
            follow_up_time="10:00:00"
        )

        # 1. Test Reassign Task Policy
        changes = {
            'reassign_role': 'telecaller',
            'reassign_mode': 'single',
            'single_assignee_id': self.telecaller2.id,
            'pending_task_handling': 'reassign'
        }
        execute_bulk_edit(
            user=self.admin,
            lead_ids=[lead.id],
            changes=changes,
            idempotency_key='test-key-task-reassign'
        )
        task.refresh_from_db()
        self.assertEqual(task.assigned_user, self.telecaller2)
        self.assertEqual(task.telecaller, self.telecaller2)
        self.assertEqual(task.status, FollowUpStatus.PENDING)

        # 2. Test Cancel Task Policy
        changes_cancel = {
            'reassign_role': 'telecaller',
            'reassign_mode': 'single',
            'single_assignee_id': self.telecaller1.id,
            'pending_task_handling': 'cancel'
        }
        execute_bulk_edit(
            user=self.admin,
            lead_ids=[lead.id],
            changes=changes_cancel,
            idempotency_key='test-key-task-cancel'
        )
        task.refresh_from_db()
        self.assertEqual(task.status, FollowUpStatus.CANCELLED)

    def test_idempotency_protection(self):
        lead_ids = [self.leads_b1[0].id]
        changes = {'status': 'Contacted'}
        res1 = execute_bulk_edit(self.admin, lead_ids, changes, idempotency_key='same-key-123')
        self.assertEqual(res1['status'], BulkOperationStatus.COMPLETED)

        # Re-running with the exact same key returns cached result without reprocessing
        res2 = execute_bulk_edit(self.admin, lead_ids, changes, idempotency_key='same-key-123')
        self.assertEqual(res2['status'], BulkOperationStatus.COMPLETED)
        self.assertEqual(res2['operation_id'], res1['operation_id'])


class BulkEditApiEndpointTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.branch = Branch.objects.create(name="Trichy Main", status="Active")
        self.admin = User.objects.create_user(
            username="admin_api", email="admin_api@crm.com",
            password="AdminPassword123!", role=UserRole.ADMIN, is_staff=True, is_superuser=True
        )
        self.receptionist = User.objects.create_user(
            username="rec_api", email="rec_api@crm.com",
            password="Password123!", role=UserRole.RECEPTIONIST, branch=self.branch
        )
        self.lead = Lead.objects.create(
            name="API Test Lead", phone="9988776655", branch=self.branch, status="New Lead"
        )

    def test_bulk_options_endpoint_admin(self):
        self.client.login(username="admin_api", password="AdminPassword123!")
        res = self.client.get(reverse('api_bulk_edit_options'))
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertTrue(data['success'])
        self.assertIn('statuses', data)
        self.assertIn('telecallers', data)
        self.assertIn('counselors', data)
        self.assertIn('branches', data)
        self.assertIn('products', data)
        self.assertIn('tags', data)

    def test_bulk_options_endpoint_receptionist_forbidden(self):
        self.client.login(username="rec_api", password="Password123!")
        res = self.client.get(reverse('api_bulk_edit_options'))
        self.assertEqual(res.status_code, 403)

    def test_bulk_preview_endpoint(self):
        self.client.login(username="admin_api", password="AdminPassword123!")
        payload = {
            'lead_ids': [self.lead.id],
            'changes': {'status': 'Contacted', 'rating': 3}
        }
        res = self.client.post(
            reverse('api_bulk_edit_preview'),
            data=json.dumps(payload),
            content_type='application/json'
        )
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertTrue(data['success'])
        self.assertEqual(data['preview']['authorized_count'], 1)

    def test_bulk_preview_endpoint_20_leads_read_only(self):
        """Verifies preview generation for 20 selected leads without mutating any records."""
        self.client.login(username="admin_api", password="AdminPassword123!")
        # Create 20 leads
        twenty_leads = []
        for i in range(1, 21):
            ld = Lead.objects.create(
                name=f"Preview Test Lead {i}",
                phone=f"91112223{i:02d}",
                branch=self.branch,
                status="New Lead",
                rating=1
            )
            twenty_leads.append(ld)

        lead_ids = [l.id for l in twenty_leads]
        payload = {
            'lead_ids': lead_ids,
            'changes': {
                'status': 'Contacted',
                'rating': 5,
                'custom_fields': {'verified': 'yes'}
            }
        }
        res = self.client.post(
            reverse('api_bulk_edit_preview'),
            data=json.dumps(payload),
            content_type='application/json'
        )
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertTrue(data['success'])
        preview = data['preview']
        self.assertEqual(preview['authorized_count'], 20)
        self.assertEqual(preview['total_authorized'], 20)
        self.assertEqual(preview['changes_summary']['status']['target_status'], 'Contacted')
        self.assertEqual(preview['changes_summary']['rating']['target_rating'], 5)

        # Strictly verify read-only behavior: None of the 20 leads were changed
        for ld in twenty_leads:
            ld.refresh_from_db()
            self.assertEqual(ld.status, "New Lead")
            self.assertEqual(ld.rating, 1)
            self.assertEqual(ld.custom_fields, {})

    def test_bulk_preview_branch_head_cross_branch_scope(self):
        """Branch head preview excludes leads belonging to other branches."""
        other_branch = Branch.objects.create(name="Coimbatore", status="Active")
        bhead = User.objects.create_user(
            username="bhead_preview", email="bhead_prev@crm.com",
            password="Password123!", role=UserRole.BRANCH_HEAD, branch=self.branch
        )
        lead_my_branch = Lead.objects.create(name="My Branch Lead", phone="9000000011", branch=self.branch)
        lead_other_branch = Lead.objects.create(name="Other Branch Lead", phone="9000000022", branch=other_branch)

        self.client.login(username="bhead_preview", password="Password123!")
        payload = {
            'lead_ids': [lead_my_branch.id, lead_other_branch.id],
            'changes': {'status': 'Contacted'}
        }
        res = self.client.post(
            reverse('api_bulk_edit_preview'),
            data=json.dumps(payload),
            content_type='application/json'
        )
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertTrue(data['success'])
        # Only the lead from self.branch should be authorized
        self.assertEqual(data['preview']['authorized_count'], 1)

    def test_bulk_preview_receptionist_forbidden(self):
        """Receptionist is not permitted to request preview or bulk edit."""
        self.client.login(username="rec_api", password="Password123!")
        res = self.client.post(
            reverse('api_bulk_edit_preview'),
            data=json.dumps({'lead_ids': [self.lead.id], 'changes': {'status': 'Contacted'}}),
            content_type='application/json'
        )
        self.assertEqual(res.status_code, 403)

    def test_bulk_preview_invalid_empty_leads(self):
        """Empty lead IDs with no filter returns warning in preview rather than crashing."""
        self.client.login(username="admin_api", password="AdminPassword123!")
        res = self.client.post(
            reverse('api_bulk_edit_preview'),
            data=json.dumps({'lead_ids': [], 'changes': {'status': 'Contacted'}}),
            content_type='application/json'
        )
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertTrue(data['success'])
        self.assertEqual(data['preview']['authorized_count'], 0)
        self.assertTrue(len(data['preview']['warnings']) > 0)

    def test_bulk_execute_endpoint(self):
        self.client.login(username="admin_api", password="AdminPassword123!")
        payload = {
            'lead_ids': [self.lead.id],
            'changes': {'status': 'Contacted', 'rating': 4},
            'idempotency_key': 'endpoint-key-999',
            'reassignment_note': 'API bulk update test'
        }
        res = self.client.post(
            reverse('api_bulk_edit_execute'),
            data=json.dumps(payload),
            content_type='application/json'
        )
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertTrue(data['success'])
        self.assertEqual(data['status'], BulkOperationStatus.COMPLETED)
        self.assertEqual(data['success_count'], 1)

        self.lead.refresh_from_db()
        self.assertEqual(self.lead.status, 'Contacted')
        self.assertEqual(self.lead.rating, 4)

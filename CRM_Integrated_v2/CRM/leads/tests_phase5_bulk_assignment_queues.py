import json
from django.test import TestCase, Client
from django.urls import reverse
from django.utils import timezone
from accounts.models import User, UserRole
from branches.models import Branch
from lead_channels.models import Channel
from leads.models import Lead, LeadAssignmentHistory, LeadOwnerType
from calls.models import CallHistory, CallStatus, CallOutcome
from followups.models import FollowUp, FollowUpStatus
from leads.bulk_assignment_service import get_queue_queryset, get_queue_counts, execute_bulk_assignment


class Phase5BulkAssignmentQueuesTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.admin = User.objects.create_user(
            username="admin_p5",
            email="admin_p5@example.com",
            password="AdminPassword123!",
            role=UserRole.ADMIN,
            is_staff=True,
            is_superuser=True
        )
        self.branch = Branch.objects.create(name="Trichy Main", status="Active")
        self.channel = Channel.objects.create(name="Direct Portal", status="Active")

        self.counselor = User.objects.create_user(
            username="counselor_p5",
            email="counselor_p5@example.com",
            password="Password123!",
            role=UserRole.COUNSELOR,
            branch=self.branch,
            is_active=True
        )

        self.telecaller1 = User.objects.create_user(
            username="telecaller_p5_1",
            email="telecaller_p5_1@example.com",
            password="Password123!",
            role=UserRole.TELECALLER,
            counselor=self.counselor,
            branch=self.branch,
            is_active=True
        )
        self.telecaller2 = User.objects.create_user(
            username="telecaller_p5_2",
            email="telecaller_p5_2@example.com",
            password="Password123!",
            role=UserRole.TELECALLER,
            counselor=self.counselor,
            branch=self.branch,
            is_active=True
        )

        # 1. Unassigned lead
        self.lead_unassigned = Lead.objects.create(
            name="Unassigned Prospect",
            phone="9000000001",
            branch=self.branch,
            channel=self.channel,
            assignment_status='Pending Assignment',
            assigned_telecaller=None,
            current_owner_type=LeadOwnerType.UNASSIGNED
        )

        # 2. Untouched lead (Assigned, 0 calls)
        self.lead_untouched = Lead.objects.create(
            name="Untouched Prospect",
            phone="9000000002",
            branch=self.branch,
            channel=self.channel,
            assignment_status='Assigned',
            assigned_telecaller=self.telecaller1,
            current_owner_type=LeadOwnerType.TELECALLER
        )

        # 3. Unanswered lead (Has calls, but all RNR / No Answer / Busy, 0 connected)
        self.lead_unanswered = Lead.objects.create(
            name="Unanswered Prospect",
            phone="9000000003",
            branch=self.branch,
            channel=self.channel,
            assignment_status='Assigned',
            assigned_telecaller=self.telecaller1,
            current_owner_type=LeadOwnerType.TELECALLER
        )
        CallHistory.objects.create(
            lead=self.lead_unanswered,
            caller=self.telecaller1,
            telecaller=self.telecaller1,
            call_status=CallStatus.NO_ANSWER,
            call_outcome=CallOutcome.RNR,
            duration=0,
            call_started_at=timezone.now() - timezone.timedelta(hours=2)
        )

        # 4. Unattended lead (Assigned, but last call was >48 hours ago)
        self.lead_unattended = Lead.objects.create(
            name="Unattended Prospect",
            phone="9000000004",
            branch=self.branch,
            channel=self.channel,
            assignment_status='Assigned',
            assigned_telecaller=self.telecaller1,
            current_owner_type=LeadOwnerType.TELECALLER
        )
        CallHistory.objects.create(
            lead=self.lead_unattended,
            caller=self.telecaller1,
            telecaller=self.telecaller1,
            call_status=CallStatus.COMPLETED,
            call_outcome=CallOutcome.FOLLOW_UP_REQUIRED,
            duration=65,
            call_started_at=timezone.now() - timezone.timedelta(hours=72)
        )

    def test_queue_classification(self):
        """Each of the 4 queues correctly filters its target leads."""
        unassigned_leads = list(get_queue_queryset('unassigned'))
        self.assertIn(self.lead_unassigned, unassigned_leads)
        self.assertNotIn(self.lead_untouched, unassigned_leads)

        untouched_leads = list(get_queue_queryset('untouched'))
        self.assertIn(self.lead_untouched, untouched_leads)
        self.assertNotIn(self.lead_unassigned, untouched_leads)
        self.assertNotIn(self.lead_unanswered, untouched_leads)

        unanswered_leads = list(get_queue_queryset('unanswered'))
        self.assertIn(self.lead_unanswered, unanswered_leads)
        self.assertNotIn(self.lead_untouched, unanswered_leads)
        self.assertNotIn(self.lead_unattended, unanswered_leads)

        unattended_leads = list(get_queue_queryset('unattended'))
        self.assertIn(self.lead_unattended, unattended_leads)

        counts = get_queue_counts()
        self.assertGreaterEqual(counts['unassigned'], 1)
        self.assertGreaterEqual(counts['untouched'], 1)
        self.assertGreaterEqual(counts['unanswered'], 1)
        self.assertGreaterEqual(counts['unattended'], 1)

    def test_single_telecaller_bulk_assignment(self):
        """Executing bulk assignment with strategy=single assigns all queue leads to target telecaller."""
        result = execute_bulk_assignment(
            queue_type='unassigned',
            lead_ids=[self.lead_unassigned.id],
            strategy='single',
            target_telecaller_id=self.telecaller2.id,
            reason='Single reallocation test',
            assigned_by=self.admin
        )
        self.assertTrue(result['success'])
        self.assertEqual(result['assigned_count'], 1)

        self.lead_unassigned.refresh_from_db()
        self.assertEqual(self.lead_unassigned.assigned_telecaller, self.telecaller2)
        self.assertEqual(self.lead_unassigned.assignment_status, 'Assigned')

        # Check LeadAssignmentHistory audit record
        history = LeadAssignmentHistory.objects.filter(lead=self.lead_unassigned).latest('created_at')
        self.assertEqual(history.to_user, self.telecaller2)
        self.assertEqual(history.to_role, 'TELECALLER')

    def test_round_robin_bulk_assignment(self):
        """Executing bulk assignment with strategy=round_robin balances leads across active branch telecallers."""
        # Create 2 more unassigned leads
        l2 = Lead.objects.create(name="RR Lead 2", phone="9000000005", branch=self.branch, channel=self.channel, assignment_status='Unassigned')
        l3 = Lead.objects.create(name="RR Lead 3", phone="9000000006", branch=self.branch, channel=self.channel, assignment_status='Unassigned')

        result = execute_bulk_assignment(
            queue_type='unassigned',
            lead_ids=[l2.id, l3.id],
            strategy='round_robin',
            target_branch_id=self.branch.id,
            reason='Round robin distribution test',
            assigned_by=self.admin
        )
        self.assertTrue(result['success'])
        self.assertEqual(result['assigned_count'], 2)

        l2.refresh_from_db()
        l3.refresh_from_db()
        self.assertIsNotNone(l2.assigned_telecaller)
        self.assertIsNotNone(l3.assigned_telecaller)
        # Verified round-robin distribution assigned to both telecallers
        assigned_ids = {l2.assigned_telecaller_id, l3.assigned_telecaller_id}
        self.assertEqual(assigned_ids, {self.telecaller1.id, self.telecaller2.id})

    def test_admin_lead_queues_view_and_api(self):
        """Admin can access lead queues view and execute bulk assignment via API."""
        self.client.login(username="admin_p5", password="AdminPassword123!")

        # GET lead queues page
        response = self.client.get(reverse('admin_lead_queues') + '?queue=untouched')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Untouched Prospect")

        # POST bulk assignment API
        payload = {
            'queue_type': 'untouched',
            'lead_ids': [self.lead_untouched.id],
            'strategy': 'single',
            'target_telecaller_id': self.telecaller2.id,
            'reason': 'API bulk reassign'
        }
        api_response = self.client.post(
            reverse('api_bulk_assign_leads'),
            data=json.dumps(payload),
            content_type='application/json'
        )
        self.assertEqual(api_response.status_code, 200)
        api_data = api_response.json()
        self.assertTrue(api_data['success'])
        self.assertEqual(api_data['assigned_count'], 1)

        self.lead_untouched.refresh_from_db()
        self.assertEqual(self.lead_untouched.assigned_telecaller, self.telecaller2)

    def test_multi_branch_and_multi_telecaller_round_robin(self):
        """
        Verify multi-branch and multi-telecaller Round-Robin:
        - Selects multiple branches and multiple telecallers.
        - Leads belonging to Branch 1 are distributed evenly among Branch 1 telecallers.
        - Leads belonging to Branch 2 are distributed evenly among Branch 2 telecallers.
        - Cross-branch contamination is strictly prevented.
        """
        branch_south = Branch.objects.create(name="Madurai South", status="Active")
        tc_south1 = User.objects.create_user(username="tc_south_1", role=UserRole.TELECALLER, branch=branch_south, is_active=True)
        tc_south2 = User.objects.create_user(username="tc_south_2", role=UserRole.TELECALLER, branch=branch_south, is_active=True)

        # 4 leads in Branch 1 (self.branch)
        b1_leads = [
            Lead.objects.create(name=f"B1 Lead {i}", phone=f"91000000{i:02d}", branch=self.branch, channel=self.channel, assignment_status='Unassigned')
            for i in range(1, 5)
        ]
        # 4 leads in Branch 2 (branch_south)
        b2_leads = [
            Lead.objects.create(name=f"B2 Lead {i}", phone=f"92000000{i:02d}", branch=branch_south, channel=self.channel, assignment_status='Unassigned')
            for i in range(1, 5)
        ]

        result = execute_bulk_assignment(
            queue_type='unassigned',
            branch_ids=[self.branch.id, branch_south.id],
            telecaller_ids=[self.telecaller1.id, self.telecaller2.id, tc_south1.id, tc_south2.id],
            strategy='round_robin',
            reason='Multi-branch round-robin distribution',
            assigned_by=self.admin
        )

        self.assertTrue(result['success'])
        self.assertGreaterEqual(result['assigned_count'], 8)
        self.assertEqual(result['skipped_count'], 0)

        # Verify B1 leads were assigned exclusively to self.telecaller1 and self.telecaller2 (2 each)
        for l in b1_leads:
            l.refresh_from_db()
            self.assertIn(l.assigned_telecaller_id, [self.telecaller1.id, self.telecaller2.id])

        b1_tc1_count = Lead.objects.filter(id__in=[l.id for l in b1_leads], assigned_telecaller=self.telecaller1).count()
        b1_tc2_count = Lead.objects.filter(id__in=[l.id for l in b1_leads], assigned_telecaller=self.telecaller2).count()
        self.assertEqual(b1_tc1_count, 2)
        self.assertEqual(b1_tc2_count, 2)

        # Verify B2 leads were assigned exclusively to tc_south1 and tc_south2 (2 each)
        for l in b2_leads:
            l.refresh_from_db()
            self.assertIn(l.assigned_telecaller_id, [tc_south1.id, tc_south2.id])

        b2_tc1_count = Lead.objects.filter(id__in=[l.id for l in b2_leads], assigned_telecaller=tc_south1).count()
        b2_tc2_count = Lead.objects.filter(id__in=[l.id for l in b2_leads], assigned_telecaller=tc_south2).count()
        self.assertEqual(b2_tc1_count, 2)
        self.assertEqual(b2_tc2_count, 2)

    def test_branch_eligibility_skips_when_branch_has_no_selected_telecallers(self):
        """
        If a selected branch has leads in the queue, but no telecallers were selected for that branch,
        leads are safely skipped rather than being incorrectly assigned cross-branch.
        """
        branch_unmanned = Branch.objects.create(name="Coimbatore West", status="Active")
        lead_unmanned = Lead.objects.create(
            name="Coimbatore Lead", phone="9300000001", branch=branch_unmanned,
            channel=self.channel, assignment_status='Unassigned'
        )

        result = execute_bulk_assignment(
            queue_type='unassigned',
            branch_ids=[self.branch.id, branch_unmanned.id],
            telecaller_ids=[self.telecaller1.id],  # only from self.branch
            strategy='round_robin',
            assigned_by=self.admin
        )

        self.assertTrue(result['success'])
        self.assertGreaterEqual(result['skipped_count'], 1)
        lead_unmanned.refresh_from_db()
        self.assertIsNone(lead_unmanned.assigned_telecaller)
        self.assertEqual(lead_unmanned.assignment_status, 'Unassigned')

    def test_inactive_telecallers_excluded_from_assignment_pool(self):
        """Inactive telecallers are strictly excluded from assignment."""
        inactive_tc = User.objects.create_user(
            username="inactive_tc", role=UserRole.TELECALLER,
            branch=self.branch, is_active=False
        )
        l_test = Lead.objects.create(name="Inactive Pool Test", phone="9400000001", branch=self.branch, channel=self.channel, assignment_status='Unassigned')

        result = execute_bulk_assignment(
            queue_type='unassigned',
            lead_ids=[l_test.id],
            telecaller_ids=[inactive_tc.id],
            strategy='round_robin',
            assigned_by=self.admin
        )
        self.assertFalse(result['success'])
        self.assertIn("No active", result['error'])

    def test_unauthorized_branch_head_prevented_from_cross_branch_assignment(self):
        """A Branch Head cannot assign leads in branches outside their authorized branch scope."""
        other_branch = Branch.objects.create(name="Salem Central", status="Active")
        branch_head_user = User.objects.create_user(
            username="bh_trichy", role=UserRole.BRANCH_HEAD,
            branch=self.branch, is_active=True
        )

        result = execute_bulk_assignment(
            queue_type='unassigned',
            branch_ids=[other_branch.id],
            strategy='round_robin',
            assigned_by=branch_head_user
        )
        self.assertFalse(result['success'])
        self.assertIn("Permission denied", result['error'])

    def test_execution_limit_respects_100_leads(self):
        """Bulk assignment respects the 100 leads limit per execution."""
        batch_leads = [
            Lead(name=f"Bulk Limit {i}", phone=f"95{i:08d}", branch=self.branch, channel=self.channel, assignment_status='Unassigned')
            for i in range(110)
        ]
        Lead.objects.bulk_create(batch_leads)

        result = execute_bulk_assignment(
            queue_type='unassigned',
            branch_ids=[self.branch.id],
            telecaller_ids=[self.telecaller1.id],
            strategy='single',
            limit=150,  # exceeds 100
            assigned_by=self.admin
        )
        self.assertTrue(result['success'])
        self.assertEqual(result['assigned_count'], 100)

    def test_api_bulk_assign_preview_endpoint(self):
        """Preview API returns accurate counts, estimated leads per telecaller, and branch warnings."""
        self.client.login(username="admin_p5", password="AdminPassword123!")

        empty_branch = Branch.objects.create(name="Empty Staff Branch", status="Active")
        Lead.objects.create(name="Empty Branch Lead", phone="9600000001", branch=empty_branch, channel=self.channel, assignment_status='Unassigned')

        payload = {
            'queue_type': 'unassigned',
            'branch_ids': [self.branch.id, empty_branch.id],
            'telecaller_ids': [self.telecaller1.id, self.telecaller2.id]  # only branch 1 has telecallers
        }

        resp = self.client.post(
            reverse('api_bulk_assign_preview'),
            data=json.dumps(payload),
            content_type='application/json'
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertTrue(data['success'])
        preview = data['preview']
        self.assertEqual(preview['selected_branches_count'], 2)
        self.assertEqual(preview['selected_telecallers_count'], 2)
        self.assertGreater(preview['total_eligible_leads'], 0)
        self.assertGreater(preview['estimated_leads_per_telecaller'], 0)
        # Warning exists because empty_branch has leads but no telecallers
        self.assertTrue(len(preview['warnings']) >= 1)
        self.assertIn("Empty Staff Branch", preview['warnings'][0])

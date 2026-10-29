import datetime
from django.test import TestCase, Client
from django.urls import reverse
from django.utils import timezone
from accounts.models import User, UserRole
from branches.models import Branch
from leads.models import Lead, LeadStatus, LeadOwnerType
from followups.models import FollowUp, FollowUpStatus
from leads.services import get_user_assigned_leads
from leads.handoff_service import reassign_lead, handoff_to_counselor


class MyLeadsOwnershipTests(TestCase):
    """
    Test suite for Part 1: My Leads Ownership & Dashboard KPI Isolation.
    Verifies that My Leads represents only the authenticated user's current assigned leads.
    """

    def setUp(self):
        self.client = Client()
        self.branch1 = Branch.objects.create(name="Chennai Main")
        self.branch2 = Branch.objects.create(name="Bangalore Central")

        # Counselors
        self.counselor_a = User.objects.create_user(
            username="counselor_a",
            email="counselor_a@techpanda.academy",
            password="Password123!",
            role=UserRole.COUNSELOR,
            branch=self.branch1,
        )
        self.counselor_b = User.objects.create_user(
            username="counselor_b",
            email="counselor_b@techpanda.academy",
            password="Password123!",
            role=UserRole.COUNSELOR,
            branch=self.branch1,
        )
        self.counselor_remote = User.objects.create_user(
            username="counselor_remote",
            email="counselor_remote@techpanda.academy",
            password="Password123!",
            role=UserRole.COUNSELOR,
            branch=self.branch2,
        )

        # Telecallers
        self.telecaller_a = User.objects.create_user(
            username="telecaller_a",
            email="telecaller_a@techpanda.academy",
            password="Password123!",
            role=UserRole.TELECALLER,
            branch=self.branch1,
            counselor=self.counselor_a,  # Under counselor A's supervision
        )
        self.telecaller_b = User.objects.create_user(
            username="telecaller_b",
            email="telecaller_b@techpanda.academy",
            password="Password123!",
            role=UserRole.TELECALLER,
            branch=self.branch1,
            counselor=self.counselor_b,
        )

    # 1. Twenty-five leads assigned only to a Telecaller must not appear in Counselor's My Leads KPI
    def test_01_twenty_five_telecaller_only_leads_do_not_appear_in_counselor_my_leads(self):
        for i in range(25):
            Lead.objects.create(
                name=f"Telecaller Lead {i}",
                phone=f"90000000{i:02d}",
                branch=self.branch1,
                assigned_telecaller=self.telecaller_a,
                current_owner_type=LeadOwnerType.TELECALLER,
                status=LeadStatus.NEW,
            )

        self.assertEqual(get_user_assigned_leads(self.counselor_a).count(), 0)

        self.client.login(username="counselor_a", password="Password123!")
        resp = self.client.get(reverse('counselor_dashboard'))
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.context['my_leads_count'], 0)

        # Check list page
        resp_list = self.client.get(reverse('counselor_leads_list'))
        self.assertEqual(resp_list.status_code, 200)
        self.assertEqual(len(resp_list.context['page_obj']), 0)

    # 2. Twenty-five leads assigned directly to Counselor must count as 25
    def test_02_twenty_five_direct_counselor_leads_count_as_twenty_five(self):
        for i in range(25):
            Lead.objects.create(
                name=f"Direct Counselor Lead {i}",
                phone=f"91000000{i:02d}",
                branch=self.branch1,
                assigned_counselor=self.counselor_a,
                current_owner_type=LeadOwnerType.COUNSELOR,
                status=LeadStatus.COUNSELING,
            )

        self.assertEqual(get_user_assigned_leads(self.counselor_a).count(), 25)

        self.client.login(username="counselor_a", password="Password123!")
        resp = self.client.get(reverse('counselor_dashboard'))
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.context['my_leads_count'], 25)
        self.assertEqual(resp.context['counseling_count'], 25)

    # 3. Ten Telecaller-only leads and five leads assigned to Counselor produce count of 5
    def test_03_mixed_telecaller_and_counselor_leads_scoped_properly(self):
        for i in range(10):
            Lead.objects.create(
                name=f"TC Lead {i}",
                phone=f"92000000{i:02d}",
                branch=self.branch1,
                assigned_telecaller=self.telecaller_a,
                current_owner_type=LeadOwnerType.TELECALLER,
                status=LeadStatus.NEW,
            )
        for i in range(5):
            Lead.objects.create(
                name=f"Counselor Lead {i}",
                phone=f"93000000{i:02d}",
                branch=self.branch1,
                assigned_counselor=self.counselor_a,
                current_owner_type=LeadOwnerType.COUNSELOR,
                status=LeadStatus.VISITED,
            )

        self.assertEqual(get_user_assigned_leads(self.counselor_a).count(), 5)

        self.client.login(username="counselor_a", password="Password123!")
        resp = self.client.get(reverse('counselor_dashboard'))
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.context['my_leads_count'], 5)
        self.assertEqual(resp.context['visits_count'], 5)

    # 4. Leads assigned to another Counselor on the same team/branch must not appear
    def test_04_leads_assigned_to_other_counselor_do_not_appear(self):
        lead_other = Lead.objects.create(
            name="Other Counselor Lead",
            phone="9400000001",
            branch=self.branch1,
            assigned_counselor=self.counselor_b,
            current_owner_type=LeadOwnerType.COUNSELOR,
            status=LeadStatus.COUNSELING,
        )

        self.assertEqual(get_user_assigned_leads(self.counselor_a).count(), 0)

        self.client.login(username="counselor_a", password="Password123!")
        resp = self.client.get(reverse('counselor_leads_list'))
        self.assertNotContains(resp, "Other Counselor Lead")

    # 5. Leads assigned to another branch must not appear
    def test_05_leads_assigned_to_other_branch_do_not_appear(self):
        lead_remote = Lead.objects.create(
            name="Remote Branch Lead",
            phone="9500000001",
            branch=self.branch2,
            assigned_counselor=self.counselor_remote,
            current_owner_type=LeadOwnerType.COUNSELOR,
            status=LeadStatus.COUNSELING,
        )

        self.assertEqual(get_user_assigned_leads(self.counselor_a).count(), 0)

        self.client.login(username="counselor_a", password="Password123!")
        resp = self.client.get(reverse('counselor_leads_list'))
        self.assertNotContains(resp, "Remote Branch Lead")

    # 6. Reassigned lead must not count as currently owned by previous owner
    def test_06_reassigned_lead_does_not_count_for_previous_owner(self):
        lead = Lead.objects.create(
            name="Handoff Lead",
            phone="9600000001",
            branch=self.branch1,
            assigned_counselor=self.counselor_a,
            current_owner_type=LeadOwnerType.COUNSELOR,
            status=LeadStatus.COUNSELING,
        )
        self.assertEqual(get_user_assigned_leads(self.counselor_a).count(), 1)

        # Reassign to counselor B
        reassign_lead(lead, to_user=self.counselor_b, to_role="COUNSELOR", assigned_by=self.counselor_a)
        lead.refresh_from_db()

        self.assertEqual(get_user_assigned_leads(self.counselor_a).count(), 0)
        self.assertEqual(get_user_assigned_leads(self.counselor_b).count(), 1)

    # 7. Formally transferred lead follows authoritative current assignment
    def test_07_formally_transferred_lead_follows_authoritative_current_assignment(self):
        lead = Lead.objects.create(
            name="Telecaller To Counselor Lead",
            phone="9700000001",
            branch=self.branch1,
            assigned_telecaller=self.telecaller_a,
            current_owner_type=LeadOwnerType.TELECALLER,
            status=LeadStatus.VISIT_SCHEDULED,
        )
        self.assertEqual(get_user_assigned_leads(self.counselor_a).count(), 0)

        # Handoff to Counselor A
        handoff_to_counselor(lead, counselor=self.counselor_a, assigned_by=self.telecaller_a)
        lead.refresh_from_db()

        self.assertEqual(get_user_assigned_leads(self.counselor_a).count(), 1)
        self.assertEqual(lead.current_owner_type, LeadOwnerType.COUNSELOR)
        self.assertEqual(lead.assigned_counselor, self.counselor_a)

    # 8. Multiple joins must not inflate lead counts
    def test_08_multiple_joins_do_not_inflate_lead_counts(self):
        lead = Lead.objects.create(
            name="Joined Lead",
            phone="9800000001",
            branch=self.branch1,
            assigned_counselor=self.counselor_a,
            current_owner_type=LeadOwnerType.COUNSELOR,
            status=LeadStatus.COUNSELING,
        )
        # Add multiple followups
        for i in range(5):
            FollowUp.objects.create(
                lead=lead,
                assigned_user=self.counselor_a,
                follow_up_date=timezone.now().date(),
                status=FollowUpStatus.PENDING,
            )

        self.assertEqual(get_user_assigned_leads(self.counselor_a).count(), 1)

        self.client.login(username="counselor_a", password="Password123!")
        resp = self.client.get(reverse('counselor_dashboard'))
        self.assertEqual(resp.context['my_leads_count'], 1)

    # 9. Dashboard KPI and My Leads page agree when same filters applied
    def test_09_dashboard_kpi_and_my_leads_page_agree(self):
        for i in range(3):
            Lead.objects.create(
                name=f"Visited Lead {i}",
                phone=f"99100000{i:02d}",
                branch=self.branch1,
                assigned_counselor=self.counselor_a,
                current_owner_type=LeadOwnerType.COUNSELOR,
                status=LeadStatus.VISITED,
            )
        for i in range(2):
            Lead.objects.create(
                name=f"Counseling Lead {i}",
                phone=f"99200000{i:02d}",
                branch=self.branch1,
                assigned_counselor=self.counselor_a,
                current_owner_type=LeadOwnerType.COUNSELOR,
                status=LeadStatus.COUNSELING,
            )

        self.client.login(username="counselor_a", password="Password123!")
        resp_dash = self.client.get(reverse('counselor_dashboard'))
        self.assertEqual(resp_dash.context['my_leads_count'], 5)
        self.assertEqual(resp_dash.context['visits_count'], 3)
        self.assertEqual(resp_dash.context['counseling_count'], 2)

        resp_list_all = self.client.get(reverse('counselor_leads_list'))
        self.assertEqual(len(resp_list_all.context['page_obj']), 5)

        resp_list_visited = self.client.get(reverse('counselor_leads_list'), {'status': 'Visited'})
        self.assertEqual(len(resp_list_visited.context['page_obj']), 3)

        resp_list_counseling = self.client.get(reverse('counselor_leads_list'), {'status': 'Counseling'})
        self.assertEqual(len(resp_list_counseling.context['page_obj']), 2)

    # 10. Direct URL access enforces ownership restrictions
    def test_10_direct_url_access_enforces_ownership_restrictions(self):
        lead_other = Lead.objects.create(
            name="Confidential Other Lead",
            phone="9930000001",
            branch=self.branch1,
            assigned_counselor=self.counselor_b,
            current_owner_type=LeadOwnerType.COUNSELOR,
            status=LeadStatus.COUNSELING,
        )

        self.client.login(username="counselor_a", password="Password123!")
        # Attempt to access lead_other directly
        resp = self.client.get(reverse('counselor_lead_detail', args=[lead_other.pk]))
        self.assertEqual(resp.status_code, 404)

        # Attempt to update status on lead_other directly
        resp_post = self.client.post(
            reverse('counselor_lead_update_status', args=[lead_other.pk]),
            {'status': LeadStatus.VISITED}
        )
        self.assertEqual(resp_post.status_code, 404)

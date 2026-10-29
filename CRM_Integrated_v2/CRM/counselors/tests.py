from django.test import TestCase, Client
from django.urls import reverse
from accounts.models import User, UserRole
from branches.models import Branch


class CounselorPortalTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.branch = Branch.objects.get_or_create(name="Counselor Portal Branch")[0]

        self.counselor = User.objects.create_user(
            username="cp_counselor", password="pwd12345678", role=UserRole.COUNSELOR, branch=self.branch
        )
        self.other_counselor = User.objects.create_user(
            username="cp_other_counselor", password="pwd12345678", role=UserRole.COUNSELOR, branch=self.branch
        )

        self.my_telecaller = User.objects.create_user(
            username="cp_my_telecaller", password="pwd12345678", role=UserRole.TELECALLER,
            branch=self.branch, counselor=self.counselor
        )
        self.other_telecaller = User.objects.create_user(
            username="cp_other_telecaller", password="pwd12345678", role=UserRole.TELECALLER,
            branch=self.branch, counselor=self.other_counselor
        )

    def test_counselor_dashboard_renders_and_scopes_to_self(self):
        self.client.login(username="cp_counselor", password="pwd12345678")
        resp = self.client.get(reverse('counselor_dashboard'))
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.context['my_leads_count'], 0)

    def test_counselor_telecallers_list_only_shows_own_telecallers(self):
        self.client.login(username="cp_counselor", password="pwd12345678")
        resp = self.client.get(reverse('counselor_telecallers_list'))
        self.assertContains(resp, 'cp_my_telecaller')
        self.assertNotContains(resp, 'cp_other_telecaller')

    def test_admin_counselor_leads_drilldown_scoping_and_filters(self):
        from leads.models import Lead, LeadStatus
        from calls.models import CallHistory
        from lead_channels.models import Channel

        admin = User.objects.create_user(
            username="admin_counselor_test", password="pwd12345678", role=UserRole.ADMIN,
            is_staff=True, is_superuser=True
        )
        ch, _ = Channel.objects.get_or_create(name="Online")

        # Direct lead for counselor
        lead1 = Lead.objects.create(
            name="Direct Lead 1", phone="9998881111", branch=self.branch, channel=ch,
            assigned_counselor=self.counselor, status=LeadStatus.COUNSELING
        )
        # Lead via supervised telecaller
        lead2 = Lead.objects.create(
            name="Supervised Lead 2", phone="9998882222", branch=self.branch, channel=ch,
            assigned_telecaller=self.my_telecaller, status=LeadStatus.NEW
        )
        # Lead for other counselor (must NOT appear)
        lead3 = Lead.objects.create(
            name="Other Counselor Lead", phone="9998883333", branch=self.branch, channel=ch,
            assigned_counselor=self.other_counselor, status=LeadStatus.NEW
        )

        # Log call for lead1 with RNR
        CallHistory.objects.create(
            lead=lead1, caller=self.counselor, telecaller=self.my_telecaller,
            call_outcome='RNR', duration=15
        )

        self.client.login(username="admin_counselor_test", password="pwd12345678")
        url = reverse('admin_counselor_leads_drilldown', args=[self.counselor.pk])
        resp = self.client.get(url)

        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.context['total_leads'], 2)
        self.assertEqual(resp.context['rnr_leads_count'], 1)
        self.assertEqual(resp.context['unattended_leads_count'], 1)
        self.assertContains(resp, "Direct Lead 1")
        self.assertContains(resp, "Supervised Lead 2")
        self.assertNotContains(resp, "Other Counselor Lead")

        # Test RNR filter
        resp_rnr = self.client.get(url + "?special_filter=rnr")
        self.assertEqual(resp_rnr.status_code, 200)
        self.assertEqual(len(resp_rnr.context['page_obj']), 1)
        self.assertEqual(resp_rnr.context['page_obj'][0].id, lead1.id)

        # Test unattended filter
        resp_unattended = self.client.get(url + "?special_filter=unattended")
        self.assertEqual(resp_unattended.status_code, 200)
        self.assertEqual(len(resp_unattended.context['page_obj']), 1)
        self.assertEqual(resp_unattended.context['page_obj'][0].id, lead2.id)

    def test_branch_head_cannot_drilldown_cross_branch_counselor(self):
        other_branch = Branch.objects.create(name="Remote Branch")
        remote_counselor = User.objects.create_user(
            username="remote_counselor", password="pwd12345678", role=UserRole.COUNSELOR, branch=other_branch
        )
        branch_head = User.objects.create_user(
            username="bh_local", password="pwd12345678", role=UserRole.BRANCH_HEAD, branch=self.branch
        )

        self.client.login(username="bh_local", password="pwd12345678")
        resp = self.client.get(reverse('admin_counselor_leads_drilldown', args=[remote_counselor.pk]))
        self.assertEqual(resp.status_code, 403)


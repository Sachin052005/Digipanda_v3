import json
from django.test import TestCase, Client
from django.urls import reverse
from accounts.models import User, UserRole
from branches.models import Branch


class WhatsAppPermissionsTestCase(TestCase):
    def setUp(self):
        self.client = Client()
        self.branch = Branch.objects.create(name="Test Branch WA")

        # Admin user
        self.admin_user = User.objects.create_user(
            username="admin_wa_test",
            email="admin_wa@test.com",
            password="Password@123",
            role=UserRole.ADMIN,
            branch=self.branch
        )

        # Superadmin user
        self.superadmin_user = User.objects.create_superuser(
            username="super_wa_test",
            email="super_wa@test.com",
            password="Password@123",
            role=UserRole.SUPERADMIN,
            branch=self.branch
        )

        # Telecaller user
        self.telecaller_user = User.objects.create_user(
            username="tc_wa_test",
            email="tc_wa@test.com",
            password="Password@123",
            role=UserRole.TELECALLER,
            branch=self.branch
        )

        # Counselor user
        self.counselor_user = User.objects.create_user(
            username="coun_wa_test",
            email="coun_wa@test.com",
            password="Password@123",
            role=UserRole.COUNSELOR,
            branch=self.branch
        )

        # Receptionist user
        self.receptionist_user = User.objects.create_user(
            username="rec_wa_test",
            email="rec_wa@test.com",
            password="Password@123",
            role=UserRole.RECEPTIONIST,
            branch=self.branch
        )

        # Branch Head user
        self.branch_head_user = User.objects.create_user(
            username="bh_wa_test",
            email="bh_wa@test.com",
            password="Password@123",
            role=UserRole.BRANCH_HEAD,
            branch=self.branch
        )

    def test_admin_and_superadmin_can_access_whatsapp_pages(self):
        """Admin and Superadmin must have access to WhatsApp views."""
        self.client.force_login(self.admin_user)
        inbox_res = self.client.get(reverse('inbox'))
        self.assertIn(inbox_res.status_code, [200, 302])

        campaigns_res = self.client.get(reverse('whatsapp_campaigns_list'))
        self.assertEqual(campaigns_res.status_code, 200)

        automations_res = self.client.get(reverse('automation-list'))
        self.assertEqual(automations_res.status_code, 200)

        self.client.force_login(self.superadmin_user)
        inbox_super = self.client.get(reverse('inbox'))
        self.assertIn(inbox_super.status_code, [200, 302])

        campaigns_super = self.client.get(reverse('whatsapp_campaigns_list'))
        self.assertEqual(campaigns_super.status_code, 200)

    def test_non_admin_roles_forbidden_from_whatsapp_views(self):
        """Telecaller, Counselor, Receptionist, Branch Head must strictly get 403 Forbidden."""
        non_admin_users = [
            self.telecaller_user,
            self.counselor_user,
            self.receptionist_user,
            self.branch_head_user,
        ]

        for user in non_admin_users:
            self.client.force_login(user)

            # Inbox
            res = self.client.get(reverse('inbox'))
            self.assertEqual(res.status_code, 403, f"{user.role} was not forbidden from inbox")

            # Campaigns list
            res = self.client.get(reverse('whatsapp_campaigns_list'))
            self.assertEqual(res.status_code, 403, f"{user.role} was not forbidden from campaigns list")

            # Automations
            res = self.client.get(reverse('automation-list'))
            self.assertEqual(res.status_code, 403, f"{user.role} was not forbidden from automations list")

            # API campaign control
            res = self.client.post(reverse('api_campaign_control', args=[9999]), {'action': 'pause'})
            self.assertEqual(res.status_code, 403, f"{user.role} was not forbidden from campaign control API")

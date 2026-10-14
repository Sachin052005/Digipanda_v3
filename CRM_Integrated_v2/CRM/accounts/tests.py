from django.test import TestCase, Client
from django.urls import reverse
from accounts.models import User, UserRole
from branches.models import Branch, SalesHeadBranchAccess

class AccountsAndAuthTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.branch = Branch.objects.create(name="Central Campus", phone="9999988888")

        # Admin user
        self.admin = User.objects.create_user(
            username="testadmin",
            email="admin@test.com",
            password="adminpassword123",
            role=UserRole.ADMIN,
            is_staff=True,
            is_superuser=True
        )

        # Sales Head user (formerly "Manager")
        self.manager = User.objects.create_user(
            username="testmanager",
            email="manager@test.com",
            password="managerpassword123",
            role=UserRole.SALES_HEAD,
            branch=self.branch
        )
        SalesHeadBranchAccess.objects.create(sales_head=self.manager, branch=self.branch)

        # Telecaller user
        self.telecaller = User.objects.create_user(
            username="testtelecaller",
            email="telecaller@test.com",
            password="callerpassword123",
            role=UserRole.TELECALLER,
            branch=self.branch
        )

    def test_admin_login_and_redirect(self):
        response = self.client.post(reverse('admin_login'), {
            'username': 'testadmin',
            'password': 'adminpassword123'
        })
        self.assertRedirects(response, reverse('admin_dashboard'))

    def test_manager_registration_and_login(self):
        # Registration
        reg_response = self.client.post(reverse('manager_register'), {
            'first_name': 'John',
            'last_name': 'Manager',
            'username': 'newmanager',
            'email': 'newmanager@test.com',
            'phone': '9876543210',
            'password': 'safePassword123!',
            'confirm_password': 'safePassword123!'
        })
        self.assertRedirects(reg_response, reverse('manager_login'))
        new_mgr = User.objects.get(username='newmanager')
        self.assertEqual(new_mgr.role, UserRole.SALES_HEAD)

        # Login
        login_response = self.client.post(reverse('manager_login'), {
            'username': 'newmanager',
            'password': 'safePassword123!'
        })
        self.assertRedirects(login_response, reverse('manager_dashboard'))

    def test_telecaller_registration_and_login(self):
        # Registration
        reg_response = self.client.post(reverse('telecaller_register'), {
            'first_name': 'Alice',
            'last_name': 'Caller',
            'username': 'newcaller',
            'email': 'newcaller@test.com',
            'phone': '9876543211',
            'password': 'safePassword123!',
            'confirm_password': 'safePassword123!'
        })
        self.assertRedirects(reg_response, reverse('telecaller_login'))
        new_tc = User.objects.get(username='newcaller')
        self.assertEqual(new_tc.role, UserRole.TELECALLER)

        # Login
        login_response = self.client.post(reverse('telecaller_login'), {
            'username': 'newcaller',
            'password': 'safePassword123!'
        })
        self.assertRedirects(login_response, reverse('telecaller_dashboard'))

    def test_unauthorized_dashboard_access_blocked(self):
        # Telecaller trying to access Admin dashboard
        self.client.login(username='testtelecaller', password='callerpassword123')
        response = self.client.get(reverse('admin_dashboard'))
        # Should redirect to telecaller dashboard
        self.assertRedirects(response, reverse('telecaller_dashboard'))

        # Manager trying to access Admin dashboard
        self.client.login(username='testmanager', password='managerpassword123')
        response = self.client.get(reverse('admin_dashboard'))
        self.assertRedirects(response, reverse('manager_dashboard'))

    def test_manager_telecaller_relationship(self):
        from accounts.permissions import get_accessible_branch_ids
        self.assertIn(self.telecaller.branch_id, get_accessible_branch_ids(self.manager))
        self.assertIn(self.branch, [access.branch for access in self.manager.branch_access.all()])

    def test_login_with_email(self):
        # Admin email login
        response = self.client.post(reverse('login'), {
            'username': 'admin@test.com',
            'password': 'adminpassword123'
        })
        self.assertRedirects(response, reverse('admin_dashboard'))

        # Telecaller email login
        self.client.logout()
        response = self.client.post(reverse('login'), {
            'username': 'telecaller@test.com',
            'password': 'callerpassword123'
        })
        self.assertRedirects(response, reverse('telecaller_dashboard'))

    def test_branch_head_and_counselor_login_redirect_to_their_dashboards(self):
        branch_head = User.objects.create_user(
            username="testbranchhead", email="branchhead@test.com", password="branchheadpass123",
            role=UserRole.BRANCH_HEAD, branch=self.branch
        )
        counselor = User.objects.create_user(
            username="testcounselor", email="counselor@test.com", password="counselorpass123",
            role=UserRole.COUNSELOR, branch=self.branch
        )

        response = self.client.post(reverse('login'), {
            'username': 'testbranchhead', 'password': 'branchheadpass123'
        })
        self.assertRedirects(response, reverse('branch_head_dashboard'))

        self.client.logout()
        response = self.client.post(reverse('login'), {
            'username': 'testcounselor', 'password': 'counselorpass123'
        })
        self.assertRedirects(response, reverse('counselor_dashboard'))

    def test_password_reset_views(self):
        response = self.client.get(reverse('password_reset'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Reset Password")

    def test_strong_password_rules(self):
        from accounts.validators import ComplexityValidator
        from django.core.exceptions import ValidationError

        validator = ComplexityValidator(min_length=8)

        # Valid strong password
        validator.validate("ValidStrongPass123!")

        # Too short
        with self.assertRaises(ValidationError) as ctx:
            validator.validate("Short1!")
        self.assertTrue(any("at least 8 characters" in msg for msg in ctx.exception.messages))

        # Missing uppercase
        with self.assertRaises(ValidationError) as ctx:
            validator.validate("nouppercase123!")
        self.assertTrue(any("uppercase letter" in msg for msg in ctx.exception.messages))

        # Missing lowercase
        with self.assertRaises(ValidationError) as ctx:
            validator.validate("NOLOWERCASE123!")
        self.assertTrue(any("lowercase letter" in msg for msg in ctx.exception.messages))

        # Missing digit
        with self.assertRaises(ValidationError) as ctx:
            validator.validate("NoDigitsHere!!")
        self.assertTrue(any("numeric digit" in msg for msg in ctx.exception.messages))

        # Missing special character
        with self.assertRaises(ValidationError) as ctx:
            validator.validate("NoSpecialChar123")
        self.assertTrue(any("special character" in msg for msg in ctx.exception.messages))

        # Contains username
        with self.assertRaises(ValidationError) as ctx:
            user = User(username="rajesh", email="rajesh@test.com")
            validator.validate("SecretRajesh123!", user=user)
        self.assertTrue(any("contain your username" in msg for msg in ctx.exception.messages))


class LeadPermissionFunctionsTests(TestCase):
    """Covers the centralized lead/user authorization helpers added for the hierarchy rework."""

    def setUp(self):
        self.branch_a = Branch.objects.create(name="Perm Branch A")
        self.branch_b = Branch.objects.create(name="Perm Branch B")

        self.admin = User.objects.create_user(
            username="perm_admin", password="pwd", role=UserRole.ADMIN, is_staff=True, is_superuser=True
        )
        self.sales_head_a = User.objects.create_user(username="perm_sh_a", password="pwd", role=UserRole.SALES_HEAD)
        SalesHeadBranchAccess.objects.create(sales_head=self.sales_head_a, branch=self.branch_a)
        self.branch_head_a = User.objects.create_user(
            username="perm_bh_a", password="pwd", role=UserRole.BRANCH_HEAD, branch=self.branch_a
        )
        self.branch_head_b = User.objects.create_user(
            username="perm_bh_b", password="pwd", role=UserRole.BRANCH_HEAD, branch=self.branch_b
        )
        self.counselor_a = User.objects.create_user(
            username="perm_counselor_a", password="pwd", role=UserRole.COUNSELOR, branch=self.branch_a
        )
        self.telecaller_a = User.objects.create_user(
            username="perm_tc_a", password="pwd", role=UserRole.TELECALLER, branch=self.branch_a
        )
        self.telecaller_b = User.objects.create_user(
            username="perm_tc_b", password="pwd", role=UserRole.TELECALLER, branch=self.branch_b
        )

    def test_can_reassign_lead_rejects_cross_branch_target(self):
        from accounts.permissions import can_reassign_lead
        from leads.models import Lead

        lead = Lead.objects.create(name="Perm Lead", phone="9000000010", branch=self.branch_a)

        # Sales Head A may reassign within branch A...
        self.assertTrue(can_reassign_lead(self.sales_head_a, lead, self.telecaller_a))
        # ...but not to a telecaller belonging to branch B.
        self.assertFalse(can_reassign_lead(self.sales_head_a, lead, self.telecaller_b))
        # Admin may override across branches.
        self.assertTrue(can_reassign_lead(self.admin, lead, self.telecaller_b))

    def test_can_create_user_role_scoping(self):
        from accounts.permissions import can_create_user

        # Admin can create anyone anywhere.
        self.assertTrue(can_create_user(self.admin, UserRole.SALES_HEAD, self.branch_a))

        # Sales Head can create a Branch Head only in an accessible branch.
        self.assertTrue(can_create_user(self.sales_head_a, UserRole.BRANCH_HEAD, self.branch_a))
        self.assertFalse(can_create_user(self.sales_head_a, UserRole.BRANCH_HEAD, self.branch_b))
        self.assertFalse(can_create_user(self.sales_head_a, UserRole.COUNSELOR, self.branch_a))

        # Branch Head can create Counselors/Telecallers only in their own branch.
        self.assertTrue(can_create_user(self.branch_head_a, UserRole.COUNSELOR, self.branch_a))
        self.assertTrue(can_create_user(self.branch_head_a, UserRole.TELECALLER, self.branch_a))
        self.assertFalse(can_create_user(self.branch_head_a, UserRole.COUNSELOR, self.branch_b))
        self.assertFalse(can_create_user(self.branch_head_a, UserRole.BRANCH_HEAD, self.branch_a))

        # Counselor can create only Telecallers in their own branch.
        self.assertTrue(can_create_user(self.counselor_a, UserRole.TELECALLER, self.branch_a))
        self.assertFalse(can_create_user(self.counselor_a, UserRole.TELECALLER, self.branch_b))
        self.assertFalse(can_create_user(self.counselor_a, UserRole.COUNSELOR, self.branch_a))

        # Telecaller cannot create anyone.
        self.assertFalse(can_create_user(self.telecaller_a, UserRole.TELECALLER, self.branch_a))

    def test_can_manage_user_scoping(self):
        from accounts.permissions import can_manage_user

        self.assertTrue(can_manage_user(self.sales_head_a, self.branch_head_a))
        self.assertFalse(can_manage_user(self.sales_head_a, self.branch_head_b))
        self.assertTrue(can_manage_user(self.branch_head_a, self.telecaller_a))
        self.assertFalse(can_manage_user(self.branch_head_a, self.telecaller_b))
        self.assertFalse(can_manage_user(self.telecaller_a, self.telecaller_b))


class DisabledAccountAccessTests(TestCase):
    """Spec section 43: disabled accounts must never authenticate, and an account
    deactivated mid-session must be blocked on its very next request."""

    def setUp(self):
        self.client = Client()
        self.branch = Branch.objects.create(name="Disabled Acct Branch")
        self.telecaller = User.objects.create_user(
            username="disabled_tc", email="disabled_tc@test.com", password="pwd12345678",
            role=UserRole.TELECALLER, branch=self.branch, is_active=True,
        )

    def test_inactive_user_cannot_log_in(self):
        self.telecaller.is_active = False
        self.telecaller.save()

        resp = self.client.post(reverse('login'), {
            'username': 'disabled_tc', 'password': 'pwd12345678',
        })
        # Must not be redirected into the app - Django's ModelBackend already refuses
        # to authenticate an inactive user, so login fails outright.
        self.assertNotEqual(resp.status_code, 302)
        dashboard_resp = self.client.get(reverse('telecaller_dashboard'))
        self.assertNotEqual(dashboard_resp.status_code, 200)

    def test_account_deactivated_mid_session_is_blocked_on_next_request(self):
        self.client.login(username='disabled_tc', password='pwd12345678')
        # Confirm the session is genuinely active first.
        ok_resp = self.client.get(reverse('telecaller_dashboard'))
        self.assertEqual(ok_resp.status_code, 200)

        self.telecaller.is_active = False
        self.telecaller.save()

        resp = self.client.get(reverse('telecaller_dashboard'))
        # Django's auth backend re-validates is_active on every request, so the
        # session is treated as logged out before our own role_required check even
        # runs - the redirect carries Django's standard ?next= param.
        self.assertEqual(resp.status_code, 302)
        self.assertTrue(resp.url.startswith(reverse('login')))


class GlobalUserProvisioningAndPagesTests(TestCase):
    """
    Test suite for:
    - Automatic unique username generation & collision resolution
    - Username preview API endpoint
    - Welcome email trigger & user provisioning without manual password fields
    - The 4 enhanced CRM pages: Counselor RNR Leads, Counselor Recalls, WhatsApp, Receptionist Dashboard
    """

    def setUp(self):
        self.client = Client()
        self.branch = Branch.objects.create(name="Chennai Main", phone="9876543210")

        self.admin = User.objects.create_user(
            username="admin_super",
            email="admin_super@test.com",
            password="pwdAdmin123!",
            role=UserRole.ADMIN,
            is_staff=True,
            is_superuser=True
        )

        self.counselor = User.objects.create_user(
            username="counselor_john",
            email="counselor_john@test.com",
            password="pwdCounselor123!",
            role=UserRole.COUNSELOR,
            branch=self.branch
        )

        self.receptionist = User.objects.create_user(
            username="receptionist_mary",
            email="receptionist_mary@test.com",
            password="pwdReceptionist123!",
            role=UserRole.RECEPTIONIST,
            branch=self.branch
        )

    def test_username_generation_and_collisions(self):
        from accounts.services import generate_unique_username

        # Standard first and last name
        u1 = generate_unique_username("Tamil", "Selvan")
        self.assertEqual(u1, "tamil.selvan")

        # Create user with this username
        User.objects.create_user(username="tamil.selvan", email="tamil@test.com")

        # Second collision -> tamil.selvan2
        u2 = generate_unique_username("Tamil", "Selvan")
        self.assertEqual(u2, "tamil.selvan2")

        # Create user with tamil.selvan2
        User.objects.create_user(username="tamil.selvan2", email="tamil2@test.com")

        # Third collision -> tamil.selvan3
        u3 = generate_unique_username("Tamil", "Selvan")
        self.assertEqual(u3, "tamil.selvan3")

        # Accent stripping & special characters
        u_accent = generate_unique_username("René", "Descartes")
        self.assertEqual(u_accent, "rene.descartes")

        u_dash = generate_unique_username("Jean-Luc", "Picard")
        self.assertEqual(u_dash, "jean.luc.picard")

    def test_username_preview_api(self):
        self.client.force_login(self.admin)

        resp = self.client.get(reverse('api_username_preview'), {
            'first_name': 'Kavitha',
            'last_name': 'Rajan'
        })
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertTrue(data['success'])
        self.assertEqual(data['username'], 'kavitha.rajan')
        self.assertFalse(data['is_collision'])

        # Pre-create kavitha.rajan
        User.objects.create_user(username="kavitha.rajan", email="kavitha@test.com")

        resp2 = self.client.get(reverse('api_username_preview'), {
            'first_name': 'Kavitha',
            'last_name': 'Rajan'
        })
        self.assertEqual(resp2.status_code, 200)
        data2 = resp2.json()
        self.assertEqual(data2['username'], 'kavitha.rajan2')
        self.assertTrue(data2['is_collision'])

    def test_user_provisioning_without_password(self):
        from accounts.services import create_user_with_generated_credentials
        from django.core import mail

        user, raw_pwd, token = create_user_with_generated_credentials(
            first_name="Anita",
            last_name="Roy",
            email="anita.roy@example.com",
            phone="9876500001",
            role=UserRole.COUNSELOR,
            branch=self.branch,
            created_by=self.admin
        )

        self.assertEqual(user.username, "anita.roy")
        self.assertEqual(user.role, UserRole.COUNSELOR)
        self.assertEqual(user.branch, self.branch)
        self.assertFalse(user.has_usable_password())
        self.assertFalse(user.is_active)  # Pending onboarding
        self.assertIsNotNone(token)

        # Check welcome email was generated
        self.assertGreaterEqual(len(mail.outbox), 1)
        sent_email = mail.outbox[-1]
        self.assertIn("anita.roy@example.com", sent_email.to)
        self.assertIn("anita.roy", sent_email.body)

    def test_counselor_rnr_leads_page(self):
        self.client.force_login(self.counselor)
        resp = self.client.get(reverse('counselor_rnr_leads'))
        self.assertEqual(resp.status_code, 200)

        # Filter query
        resp_filtered = self.client.get(reverse('counselor_rnr_leads') + '?search=test&min_attempts=2')
        self.assertEqual(resp_filtered.status_code, 200)

    def test_counselor_recalls_page(self):
        self.client.force_login(self.counselor)
        resp = self.client.get(reverse('counselor_unpicked_recalls'))
        self.assertEqual(resp.status_code, 200)

        # Filter types
        for ftype in ['today', 'overdue', 'upcoming']:
            resp_type = self.client.get(f"{reverse('counselor_unpicked_recalls')}?type={ftype}")
            self.assertEqual(resp_type.status_code, 200)

    def test_whatsapp_inbox_page(self):
        self.client.force_login(self.admin)
        resp = self.client.get(reverse('whatsapp_inbox'))
        self.assertEqual(resp.status_code, 200)

    def test_receptionist_dashboard_page(self):
        self.client.force_login(self.receptionist)
        resp = self.client.get(reverse('receptionist_dashboard'))
        self.assertEqual(resp.status_code, 200)



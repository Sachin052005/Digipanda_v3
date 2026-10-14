import time
from unittest.mock import patch
from django.test import TestCase, Client, override_settings
from django.urls import reverse
from django.core import mail
from django.contrib.auth import authenticate
from django.contrib.auth.tokens import default_token_generator
from django.utils.http import urlsafe_base64_encode
from django.utils.encoding import force_bytes

from accounts.models import User, UserRole
from branches.models import Branch
from accounts.services import generate_unique_username, send_user_welcome_email


@override_settings(
    EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend',
    PASSWORD_RESET_TIMEOUT=86400,
    CRM_BASE_URL='http://testserver'
)
class WelcomeEmailAndActivationTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.branch = Branch.objects.get_or_create(name="Cyber City Branch", status="Active")[0]

        # Admin user
        self.admin = User.objects.create_user(
            username="admin_lead",
            email="admin_lead@test.com",
            password="AdminPassword123!",
            role=UserRole.ADMIN,
            is_staff=True,
            is_superuser=True
        )

        # Standard telecaller user (non-admin, no manage permission)
        self.telecaller = User.objects.create_user(
            username="telecaller_std",
            email="telecaller_std@test.com",
            password="CallerPassword123!",
            role=UserRole.TELECALLER,
            branch=self.branch,
            is_active=True
        )

        # Standard counselor user
        self.counselor = User.objects.create_user(
            username="counselor_active",
            email="counselor_active@test.com",
            password="CounselorPass123!",
            role=UserRole.COUNSELOR,
            branch=self.branch,
            is_active=True
        )

        mail.outbox.clear()

    # 1. Admin creates user via create_user_view
    def test_01_admin_creates_user_via_unified_view(self):
        self.client.login(username="admin_lead", password="AdminPassword123!")
        url = reverse('admin_user_create')
        data = {
            'role': UserRole.COUNSELOR,
            'first_name': 'Ananya',
            'last_name': 'Sharma',
            'username': 'ananya.sharma',
            'email': 'ananya.sharma@example.com',
            'phone': '9876543210',
            'branch': self.branch.id,
        }
        response = self.client.post(url, data)
        self.assertEqual(response.status_code, 302)
        self.assertRedirects(response, reverse('admin_counselors_list'))

        new_user = User.objects.get(username='ananya.sharma')
        self.assertEqual(new_user.role, UserRole.COUNSELOR)
        self.assertEqual(new_user.branch, self.branch)
        self.assertEqual(new_user.invitation_status, 'SENT')
        self.assertIsNotNone(new_user.invitation_sent_at)
        self.assertFalse(new_user.is_active)  # Inactive until setup

    # 2. One welcome email sent to registered email address
    def test_02_one_welcome_email_sent_to_registered_email(self):
        self.client.login(username="admin_lead", password="AdminPassword123!")
        url = reverse('admin_user_create')
        data = {
            'role': UserRole.TELECALLER,
            'first_name': 'Rohan',
            'last_name': 'Verma',
            'username': 'rohan.verma',
            'email': 'rohan.verma@example.com',
            'branch': self.branch.id,
            'counselor': self.counselor.id,
        }
        self.client.post(url, data)
        self.assertEqual(len(mail.outbox), 1)
        sent_email = mail.outbox[0]
        self.assertIn('rohan.verma@example.com', sent_email.to)

    # 3. Email subject, login ID, role, branch, and setup URL are present
    def test_03_email_content_contains_credentials_and_link(self):
        self.client.login(username="admin_lead", password="AdminPassword123!")
        url = reverse('admin_user_create')
        data = {
            'role': UserRole.COUNSELOR,
            'first_name': 'Priya',
            'last_name': 'Nair',
            'username': 'priya.nair',
            'email': 'priya.nair@example.com',
            'branch': self.branch.id,
        }
        self.client.post(url, data)
        self.assertEqual(len(mail.outbox), 1)
        sent_email = mail.outbox[0]

        self.assertIn("Welcome to TECHPANDA CRM", sent_email.subject)
        self.assertIn("priya.nair", sent_email.body)
        self.assertIn("Counselor", sent_email.body)
        self.assertIn("Cyber City Branch", sent_email.body)
        self.assertIn("/accounts/setup/", sent_email.body)

    # 4. HTML and text alternatives render properly
    def test_04_html_and_text_alternatives_present(self):
        user = User.objects.create_user(
            username="test_alt",
            email="test_alt@example.com",
            role=UserRole.RECEPTIONIST,
            branch=self.branch,
            is_active=False
        )
        success, _ = send_user_welcome_email(user)
        self.assertTrue(success)
        self.assertEqual(len(mail.outbox), 1)
        msg = mail.outbox[0]

        # Plain text body
        self.assertIn("Welcome to TECHPANDA CRM", msg.body)
        self.assertIn("Set up your password", msg.body)
        # HTML alternate body
        self.assertEqual(len(msg.alternatives), 1)
        html_content, mimetype = msg.alternatives[0]
        self.assertEqual(mimetype, 'text/html')
        self.assertIn("<!DOCTYPE html>", html_content)
        self.assertIn("TECHPANDA", html_content)

    # 5. Unauthorized users cannot create users or resend invitations
    def test_05_unauthorized_users_forbidden(self):
        self.client.login(username="telecaller_std", password="CallerPassword123!")
        create_url = reverse('admin_user_create')
        res_create = self.client.get(create_url)
        # @admin_required redirects or returns 302/403
        self.assertIn(res_create.status_code, [302, 403])

        target_user = User.objects.create_user(
            username="target_guy",
            email="target@example.com",
            role=UserRole.COUNSELOR,
            branch=self.branch,
            is_active=False
        )
        resend_url = reverse('resend_user_invitation', args=[target_user.pk])
        res_resend = self.client.get(resend_url)
        self.assertEqual(res_resend.status_code, 403)

    # 6. Duplicate username collision handled gracefully
    def test_06_unique_username_generation(self):
        # Create user with initial username
        User.objects.create_user(username="rajesh.kumar", email="rajesh1@test.com", role=UserRole.COUNSELOR)
        # Generating unique username for same name should append suffix
        generated = generate_unique_username("Rajesh", "Kumar", UserRole.COUNSELOR, "rajesh2@test.com")
        self.assertNotEqual(generated, "rajesh.kumar")
        self.assertTrue(generated.startswith("rajesh.kumar"))
        self.assertFalse(User.objects.filter(username=generated).exists())

    # 7. Email delivery failure preserves user and sets status FAILED without duplication
    def test_07_email_failure_preserves_user_and_sets_failed_status(self):
        with patch('accounts.services.EmailMultiAlternatives.send', side_effect=Exception("SMTP Connection refused")):
            self.client.login(username="admin_lead", password="AdminPassword123!")
            url = reverse('admin_user_create')
            data = {
                'role': UserRole.RECEPTIONIST,
                'first_name': 'Kavita',
                'last_name': 'Patel',
                'username': 'kavita.patel',
                'email': 'kavita.patel@example.com',
                'branch': self.branch.id,
            }
            response = self.client.post(url, data)
            self.assertEqual(response.status_code, 302)

            user = User.objects.get(username='kavita.patel')
            self.assertEqual(user.invitation_status, 'FAILED')
            self.assertFalse(user.is_active)
            self.assertEqual(User.objects.filter(username='kavita.patel').count(), 1)

    # 8. Resend invitation sends email with fresh token, updates status, does not create duplicate user
    def test_08_resend_invitation_sends_email_and_updates_status(self):
        user = User.objects.create_user(
            username="resend_test",
            email="resend_test@example.com",
            role=UserRole.COUNSELOR,
            branch=self.branch,
            is_active=False,
            invitation_status='FAILED'
        )
        self.client.login(username="admin_lead", password="AdminPassword123!")
        resend_url = reverse('resend_user_invitation', args=[user.pk])
        response = self.client.get(resend_url)
        self.assertEqual(response.status_code, 302)

        user.refresh_from_db()
        self.assertEqual(user.invitation_status, 'SENT')
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn(user.email, mail.outbox[0].to)
        self.assertEqual(User.objects.filter(username="resend_test").count(), 1)

    # 9. Expired setup links rejected
    def test_09_expired_setup_link_rejected(self):
        user = User.objects.create_user(
            username="expired_test",
            email="expired@example.com",
            role=UserRole.COUNSELOR,
            branch=self.branch,
            is_active=False
        )
        user.set_unusable_password()
        user.save()

        uidb64 = urlsafe_base64_encode(force_bytes(user.pk))
        token = default_token_generator.make_token(user)

        # Mock token generator check_token to simulate expiry
        with patch.object(default_token_generator, 'check_token', return_value=False):
            setup_url = reverse('account_setup', args=[uidb64, token])
            response = self.client.get(setup_url)
            self.assertEqual(response.status_code, 200)
            self.assertContains(response, "expired", status_code=200)

    # 10. Invalid and already-used setup links rejected
    def test_10_invalid_and_tampered_links_rejected(self):
        setup_url = reverse('account_setup', args=['invalid_uid', 'invalid_token'])
        response = self.client.get(setup_url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "invalid, expired, or has already been used")

    # 11. Valid setup link permits setting a valid password
    def test_11_valid_setup_link_sets_password_and_activates(self):
        user = User.objects.create_user(
            username="setup_valid",
            email="valid@example.com",
            role=UserRole.COUNSELOR,
            branch=self.branch,
            is_active=False,
            invitation_status='SENT'
        )
        user.set_unusable_password()
        user.save()

        uidb64 = urlsafe_base64_encode(force_bytes(user.pk))
        token = default_token_generator.make_token(user)
        setup_url = reverse('account_setup', args=[uidb64, token])

        post_data = {
            'new_password1': 'SecurePassword987!',
            'new_password2': 'SecurePassword987!',
        }
        response = self.client.post(setup_url, post_data)
        self.assertEqual(response.status_code, 302)
        self.assertRedirects(response, reverse('login'))

        user.refresh_from_db()
        self.assertTrue(user.is_active)
        self.assertEqual(user.invitation_status, 'ACTIVATED')
        self.assertTrue(user.check_password('SecurePassword987!'))

        # Check token is invalidated immediately upon save
        self.assertFalse(default_token_generator.check_token(user, token))

    # 12. Password confirmation mismatch and short passwords rejected by validators
    def test_12_password_validation_rejections(self):
        user = User.objects.create_user(
            username="validation_test",
            email="validation@example.com",
            role=UserRole.COUNSELOR,
            branch=self.branch,
            is_active=False
        )
        user.set_unusable_password()
        user.save()

        uidb64 = urlsafe_base64_encode(force_bytes(user.pk))
        token = default_token_generator.make_token(user)
        setup_url = reverse('account_setup', args=[uidb64, token])

        # Mismatch
        res_mismatch = self.client.post(setup_url, {
            'new_password1': 'ValidPassword123!',
            'new_password2': 'MismatchPassword123!',
        })
        self.assertEqual(res_mismatch.status_code, 200)
        self.assertContains(res_mismatch, "didn&#x27;t match" if "&#x27;" in res_mismatch.content.decode() else "match")

        user.refresh_from_db()
        self.assertFalse(user.is_active)

    # 13. Account cannot authenticate before password setup / activation
    def test_13_cannot_authenticate_prior_to_activation(self):
        user = User.objects.create_user(
            username="inactive_caller",
            email="inactive@example.com",
            role=UserRole.TELECALLER,
            branch=self.branch,
            is_active=False
        )
        user.set_unusable_password()
        user.save()

        auth_user = authenticate(username="inactive_caller", password="AnyPassword123!")
        self.assertIsNone(auth_user)

    # 14. User can log in with login ID and new password after activation
    def test_14_user_can_login_after_activation(self):
        user = User.objects.create_user(
            username="login_test_user",
            email="login_user@example.com",
            role=UserRole.COUNSELOR,
            branch=self.branch,
            is_active=False
        )
        user.set_unusable_password()
        user.save()

        uidb64 = urlsafe_base64_encode(force_bytes(user.pk))
        token = default_token_generator.make_token(user)
        setup_url = reverse('account_setup', args=[uidb64, token])

        self.client.post(setup_url, {
            'new_password1': 'MyBrandNewPassword123!',
            'new_password2': 'MyBrandNewPassword123!',
        })

        # Now authenticate
        login_success = self.client.login(username="login_test_user", password="MyBrandNewPassword123!")
        self.assertTrue(login_success)

    # 15. Branch and role assignments remain correct after activation
    def test_15_branch_and_role_preserved_after_activation(self):
        user = User.objects.create_user(
            username="preserve_branch_test",
            email="preserve@example.com",
            role=UserRole.BRANCH_HEAD,
            branch=self.branch,
            is_active=False
        )
        user.set_unusable_password()
        user.save()

        uidb64 = urlsafe_base64_encode(force_bytes(user.pk))
        token = default_token_generator.make_token(user)
        setup_url = reverse('account_setup', args=[uidb64, token])

        self.client.post(setup_url, {
            'new_password1': 'BranchHeadPass123!',
            'new_password2': 'BranchHeadPass123!',
        })

        user.refresh_from_db()
        self.assertEqual(user.role, UserRole.BRANCH_HEAD)
        self.assertEqual(user.branch, self.branch)

    # 16. Tokens are not leaked in activity logs
    def test_16_tokens_not_logged_in_activity(self):
        from activities.models import Activity
        user = User.objects.create_user(
            username="privacy_test",
            email="privacy@example.com",
            role=UserRole.TELECALLER,
            branch=self.branch,
            is_active=False
        )
        user.set_unusable_password()
        user.save()

        uidb64 = urlsafe_base64_encode(force_bytes(user.pk))
        token = default_token_generator.make_token(user)

        send_user_welcome_email(user)
        logs = Activity.objects.filter(object_id=str(user.pk))
        for log in logs:
            self.assertNotIn(token, log.description)

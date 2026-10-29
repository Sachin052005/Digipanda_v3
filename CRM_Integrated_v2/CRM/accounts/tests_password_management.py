from unittest.mock import patch
from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth import authenticate
from django.contrib.auth.tokens import default_token_generator
from django.utils.http import urlsafe_base64_encode
from django.utils.encoding import force_bytes
from django.core import mail
from accounts.models import User, UserRole
from branches.models import Branch
from activities.models import Activity
from accounts.services import send_password_reset_email_for_user


class PasswordManagementTests(TestCase):
    """
    Test suite for Part 3: Password Management for all user roles.
    Covers:
    - Forgot Password on login pages & email dispatch
    - User Profile: Self Change Password with validators & session preservation
    - Admin Staff Management: Send Reset Link
    - Admin/Superadmin: Set New Password for selected user & Superadmin protection
    - Audit logging and security validations
    """

    def setUp(self):
        self.client = Client()
        self.branch = Branch.objects.create(name="Chennai Branch")

        # Superadmin
        self.superadmin = User.objects.create_superuser(
            username="superadmin_test",
            email="superadmin@techpanda.academy",
            password="SuperPassword123!",
            role=UserRole.ADMIN,
        )

        # Standard Admin
        self.admin = User.objects.create_user(
            username="admin_standard",
            email="admin_std@techpanda.academy",
            password="AdminPassword123!",
            role=UserRole.ADMIN,
            is_staff=True,
            is_superuser=False,
        )

        # Sales Head
        self.sales_head = User.objects.create_user(
            username="sales_head_test",
            email="sales_head@techpanda.academy",
            password="SalesPassword123!",
            role=UserRole.SALES_HEAD,
            branch=self.branch,
        )

        # Branch Head
        self.branch_head = User.objects.create_user(
            username="branch_head_test",
            email="branch_head@techpanda.academy",
            password="BranchPassword123!",
            role=UserRole.BRANCH_HEAD,
            branch=self.branch,
        )

        # Counselor
        self.counselor = User.objects.create_user(
            username="counselor_test",
            email="counselor@techpanda.academy",
            password="CounselorPassword123!",
            role=UserRole.COUNSELOR,
            branch=self.branch,
        )

        # Telecaller
        self.telecaller = User.objects.create_user(
            username="telecaller_test",
            email="telecaller@techpanda.academy",
            password="CallerPassword123!",
            role=UserRole.TELECALLER,
            branch=self.branch,
            counselor=self.counselor,
        )

        # Receptionist
        self.receptionist = User.objects.create_user(
            username="receptionist_test",
            email="receptionist@techpanda.academy",
            password="ReceptionPassword123!",
            role=UserRole.RECEPTIONIST,
            branch=self.branch,
        )

    # 1. Forgot password link is accessible across all login pages
    def test_01_forgot_password_link_present_on_login_pages(self):
        login_urls = [
            reverse('login'),
            reverse('admin_login'),
            reverse('manager_login'),
            reverse('telecaller_login'),
        ]
        for url in login_urls:
            resp = self.client.get(url)
            self.assertEqual(resp.status_code, 200)
            self.assertContains(resp, reverse('password_reset'))

    # 2. Unknown email receives generic response without revealing account existence
    def test_02_unknown_email_receives_generic_response_no_enumeration(self):
        resp = self.client.post(reverse('password_reset'), {
            'email': 'nonexistent_user_999@randomdomain.com'
        })
        self.assertEqual(resp.status_code, 302)
        self.assertRedirects(resp, reverse('password_reset_done'))

        resp_done = self.client.get(reverse('password_reset_done'))
        self.assertEqual(resp_done.status_code, 200)
        self.assertContains(resp_done, "If an account exists with the email you entered")

    # 3. Valid reset link works and lets user set a new valid password
    def test_03_valid_reset_link_allows_setting_new_password(self):
        uid = urlsafe_base64_encode(force_bytes(self.telecaller.pk))
        token = default_token_generator.make_token(self.telecaller)

        url = reverse('password_reset_confirm', kwargs={'uidb64': uid, 'token': token})
        resp = self.client.get(url, follow=True)
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "Set New Password")

        # Submit new valid password to the redirected session URL
        target_path = resp.request['PATH_INFO']
        resp_post = self.client.post(target_path, {
            'new_password1': 'BrandNewPassword999!',
            'new_password2': 'BrandNewPassword999!',
        })
        self.assertEqual(resp_post.status_code, 302)
        self.assertRedirects(resp_post, reverse('password_reset_complete'))

        # Verify old password fails and new password authenticates
        self.assertIsNone(authenticate(username="telecaller_test", password="CallerPassword123!"))
        self.assertIsNotNone(authenticate(username="telecaller_test", password="BrandNewPassword999!"))

    # 4. Invalid or reused reset token fails
    def test_04_invalid_or_reused_reset_token_fails(self):
        uid = urlsafe_base64_encode(force_bytes(self.telecaller.pk))
        token = default_token_generator.make_token(self.telecaller)

        url = reverse('password_reset_confirm', kwargs={'uidb64': uid, 'token': token})
        resp = self.client.get(url, follow=True)
        self.assertEqual(resp.status_code, 200)

        # Use token once
        target_path = resp.request['PATH_INFO']
        resp_post = self.client.post(target_path, {
            'new_password1': 'FirstResetPass123!',
            'new_password2': 'FirstResetPass123!',
        })
        self.assertEqual(resp_post.status_code, 302)

        # Attempt to reuse the same token with a fresh client / cleared session
        fresh_client = self.client_class()
        resp_reuse = fresh_client.get(url, follow=True)
        self.assertEqual(resp_reuse.status_code, 200)
        self.assertContains(resp_reuse, "Reset Link Invalid or Expired")

    # 5. Profile Change Password validates current password
    def test_05_profile_change_password_validates_current_password(self):
        self.client.login(username="counselor_test", password="CounselorPassword123!")

        url = reverse('change_password')
        resp_bad_old = self.client.post(url, {
            'old_password': 'IncorrectOldPassword!',
            'new_password1': 'NewCounselorPass123!',
            'new_password2': 'NewCounselorPass123!',
        })
        self.assertEqual(resp_bad_old.status_code, 200)
        self.assertContains(resp_bad_old, "Your old password was entered incorrectly.")

        # Password remains unchanged
        self.assertIsNotNone(authenticate(username="counselor_test", password="CounselorPassword123!"))

    # 6. Profile Change Password enforces password validators and confirmation
    def test_06_profile_change_password_enforces_complexity_and_matching(self):
        self.client.login(username="counselor_test", password="CounselorPassword123!")
        url = reverse('change_password')

        # Mismatch
        resp_mismatch = self.client.post(url, {
            'old_password': 'CounselorPassword123!',
            'new_password1': 'ValidPassword123!',
            'new_password2': 'DifferentPassword123!',
        })
        self.assertEqual(resp_mismatch.status_code, 200)
        self.assertContains(resp_mismatch, "didn’t match")

        # Too short / simple
        resp_simple = self.client.post(url, {
            'old_password': 'CounselorPassword123!',
            'new_password1': 'simple',
            'new_password2': 'simple',
        })
        self.assertEqual(resp_simple.status_code, 200)
        self.assertContains(resp_simple, "This password is too short.")

    # 7. Successful Profile Change Password preserves current session and updates password
    def test_07_successful_profile_change_password_updates_hash_and_audits(self):
        self.client.login(username="counselor_test", password="CounselorPassword123!")
        url = reverse('change_password')

        resp = self.client.post(url, {
            'old_password': 'CounselorPassword123!',
            'new_password1': 'BrandNewSecurePass888!',
            'new_password2': 'BrandNewSecurePass888!',
        })
        self.assertEqual(resp.status_code, 302)
        self.assertRedirects(resp, reverse('user_profile'))

        # Still logged in on this session
        resp_profile = self.client.get(reverse('user_profile'))
        self.assertEqual(resp_profile.status_code, 200)
        self.assertContains(resp_profile, "counselor_test")

        # New password authenticates
        self.assertIsNotNone(authenticate(username="counselor_test", password="BrandNewSecurePass888!"))

        # Audit log verified
        activity = Activity.objects.filter(action="Password Changed", user=self.counselor).first()
        self.assertIsNotNone(activity)
        self.assertIn("counselor_test", activity.description)

    # 8. Unauthenticated user cannot access Change Password
    def test_08_unauthenticated_cannot_access_profile_or_change_password(self):
        resp_profile = self.client.get(reverse('user_profile'))
        self.assertEqual(resp_profile.status_code, 302)
        self.assertIn(reverse('login'), resp_profile.url)

        resp_change = self.client.get(reverse('change_password'))
        self.assertEqual(resp_change.status_code, 302)
        self.assertIn(reverse('login'), resp_change.url)

    # 9. Admin can send password reset link to staff member
    def test_09_admin_can_send_password_reset_link_to_staff(self):
        self.client.login(username="admin_standard", password="AdminPassword123!")

        url = reverse('admin_send_password_reset_link', args=[self.telecaller.pk])
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 302)

        # Email was dispatched
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, [self.telecaller.email])
        self.assertIn("password-reset-confirm", mail.outbox[0].body)

        # Audit log created
        log_entry = Activity.objects.filter(action="Password Reset Link Sent", object_id=str(self.telecaller.pk)).first()
        self.assertIsNotNone(log_entry)
        self.assertIn("admin_standard", log_entry.description)
        # Ensure reset token NOT in description
        self.assertNotIn(default_token_generator.make_token(self.telecaller), log_entry.description)

    # 10. Admin cannot set password or reset link for Superadmin
    def test_10_admin_cannot_manage_or_reset_superadmin_account(self):
        self.client.login(username="admin_standard", password="AdminPassword123!")

        # Try to send reset link for superadmin
        resp_reset = self.client.get(reverse('admin_send_password_reset_link', args=[self.superadmin.pk]))
        self.assertEqual(resp_reset.status_code, 403)

        # Try to set password for superadmin
        resp_set = self.client.get(reverse('admin_set_user_password', args=[self.superadmin.pk]))
        self.assertEqual(resp_set.status_code, 403)

    # 11. Superadmin can set password for any user
    def test_11_superadmin_can_set_password_for_user(self):
        self.client.login(username="superadmin_test", password="SuperPassword123!")

        url = reverse('admin_set_user_password', args=[self.receptionist.pk])
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)

        # Submit new password
        resp_post = self.client.post(url, {
            'new_password1': 'AdminAssignedPass987!',
            'new_password2': 'AdminAssignedPass987!',
        })
        self.assertEqual(resp_post.status_code, 302)

        # Verify new password works
        self.assertIsNotNone(authenticate(username="receptionist_test", password="AdminAssignedPass987!"))

        # Verify audit record
        activity = Activity.objects.filter(action="Administrator Set Password", object_id=str(self.receptionist.pk)).first()
        self.assertIsNotNone(activity)
        self.assertIn("superadmin_test", activity.description)
        # Verify plaintext password NEVER in log
        self.assertNotIn("AdminAssignedPass987!", activity.description)

    # 12. Email failure is safely handled and never reports false success
    def test_12_email_delivery_failure_handled_safely(self):
        with patch('django.core.mail.EmailMultiAlternatives.send', side_effect=Exception("SMTP Connection Refused")):
            sent, err = send_password_reset_email_for_user(self.counselor, admin_user=self.admin)
            self.assertFalse(sent)
            self.assertIn("SMTP Connection Refused", err)

            failure_log = Activity.objects.filter(action="Password Reset Delivery Failed", object_id=str(self.counselor.pk)).first()
            self.assertIsNotNone(failure_log)

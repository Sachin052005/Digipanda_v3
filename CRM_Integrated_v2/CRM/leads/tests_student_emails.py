"""
Comprehensive automated test suite for Gmail SMTP configuration and automated student emails.
Covers:
1. SMTP settings loading and environment configuration.
2. Shared email service rendering and multipart delivery.
3. Enrollment confirmation email on commit & idempotency.
4. Payment receipt email on verified payment & ledger balance calculations.
5. Pending / failed payments do NOT dispatch receipts.
6. Partial payments and full payments reflect correct outstanding balances.
7. GST breakdown calculation in email context.
8. Installment reminders for upcoming, due, and overdue installments.
9. Fully paid installments stop receiving reminders.
10. Duplicate task execution avoids sending duplicate messages.
11. SMTP failure isolation (preserves enrollment and payment records).
12. Resending and safe retries without duplicating database transactions.
13. Branch permissions and recipient email integrity.
"""

from decimal import Decimal
from unittest.mock import patch
from datetime import timedelta

from django.test import TestCase, Client, override_settings
from django.urls import reverse
from django.core import mail
from django.utils import timezone
from django.conf import settings

from accounts.models import User, UserRole
from branches.models import Branch
from products.models import Product
from leads.models import (
    Lead,
    LeadStatus,
    Enrollment,
    Installment,
    PaymentTransaction,
    PaymentEmailLog,
    GSTTreatment,
    PaymentPlan,
    InstallmentMethod,
    InstallmentStatus,
    PaymentMethod,
    PaymentTransactionStatus,
)
from leads.services_enrollment import (
    create_or_update_enrollment,
    record_payment,
    send_installment_reminders,
)
from services.email_service import (
    is_valid_email,
    send_template_email,
    send_enrollment_confirmation_email,
    send_payment_receipt_email,
    send_installment_reminder_email,
    process_installment_reminders_batch,
)


@override_settings(
    EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend',
    DEFAULT_FROM_EMAIL='idpsachin@gmail.com',
    EMAIL_HOST_USER='idpsachin@gmail.com',
    COMPANY_NAME='TECHPANDA'
)
class StudentEmailAutomationTests(TestCase):
    def setUp(self):
        self.client = Client()

        # Branch
        self.branch = Branch.objects.get_or_create(name="Anna Nagar Campus", status="Active")[0]

        # Admin & Counselor
        self.admin = User.objects.create_user(
            username="admin_mail_test",
            email="admin_mail@test.com",
            password="AdminPassword123!",
            role=UserRole.ADMIN,
            is_staff=True,
            is_superuser=True
        )
        self.counselor = User.objects.create_user(
            username="counselor_mail_test",
            email="counselor_mail@test.com",
            password="CounselorPass123!",
            role=UserRole.COUNSELOR,
            branch=self.branch,
            is_active=True
        )

        # Product / Course
        self.course = Product.objects.get_or_create(
            name="Full Stack Python Development",
            defaults={"price": Decimal('25000.00'), "status": Product.Status.ACTIVE}
        )[0]

        # Lead
        self.lead = Lead.objects.create(
            name="Arun Kumar",
            phone="9876543210",
            email="arun.kumar@example.com",
            branch=self.branch,
            assigned_counselor=self.counselor,
            product=self.course,
            status=LeadStatus.INTERESTED
        )

        mail.outbox.clear()

    # 1. SMTP Settings loading
    def test_01_smtp_settings_configuration(self):
        self.assertEqual(settings.EMAIL_HOST, "smtp.gmail.com")
        self.assertEqual(settings.EMAIL_PORT, 587)
        self.assertTrue(settings.EMAIL_USE_TLS)
        self.assertFalse(settings.EMAIL_USE_SSL)
        self.assertEqual(settings.DEFAULT_FROM_EMAIL, "idpsachin@gmail.com")

    # 2. Email validation & Shared template dispatch
    def test_02_email_validation_and_template_dispatch(self):
        self.assertTrue(is_valid_email("student@example.com"))
        self.assertFalse(is_valid_email("invalid-email"))
        self.assertFalse(is_valid_email(""))
        self.assertFalse(is_valid_email(None))

        # Test dispatch
        success, _ = send_template_email(
            subject="Test Subject",
            recipient="student@example.com",
            html_template="emails/enrollment_confirmation.html",
            text_template="emails/enrollment_confirmation.txt",
            context={
                'company_name': 'TECHPANDA',
                'student_name': 'Test Student',
                'student_id': 'STU-100',
                'enrollment_number': 'ENR-2026-100',
                'course_name': 'Python',
                'course_duration': '3 Months',
                'enrollment_date': '2026-10-13',
                'branch_name': 'Anna Nagar',
                'total_payable': Decimal('25000.00'),
                'gst_treatment': 'Inclusive of GST',
                'payment_plan': 'Full Payment',
            }
        )
        self.assertTrue(success)
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].subject, "Test Subject")
        self.assertIn("student@example.com", mail.outbox[0].to)

    # 3. Enrollment confirmation email on successful enrollment
    def test_03_enrollment_confirmation_email_sent_on_success(self):
        data = {
            'student_name': "Arun Kumar",
            'student_phone': "9876543210",
            'student_email': "arun.kumar@example.com",
            'product': self.course,
            'branch': self.branch,
            'assigned_counselor': self.counselor,
            'base_course_fee': Decimal('25000.00'),
            'gst_treatment': GSTTreatment.INCLUSIVE,
            'tax_rate': Decimal('18.00'),
            'payment_plan': PaymentPlan.FULL_PAYMENT,
        }
        with self.captureOnCommitCallbacks(execute=True):
            enrollment = create_or_update_enrollment(self.lead, self.counselor, data)

        self.assertEqual(len(mail.outbox), 1)
        sent_email = mail.outbox[0]
        self.assertEqual(sent_email.subject, f"Enrollment Confirmed — {self.course.name}")
        self.assertIn("arun.kumar@example.com", sent_email.to)
        self.assertIn("Arun Kumar", sent_email.body)
        self.assertIn(enrollment.enrollment_number, sent_email.body)
        self.assertIn("Anna Nagar Campus", sent_email.body)

        # Check DB state
        enrollment.refresh_from_db()
        self.assertTrue(enrollment.confirmation_email_sent)
        self.assertIsNotNone(enrollment.confirmation_email_sent_at)
        self.assertTrue(
            PaymentEmailLog.objects.filter(
                enrollment=enrollment,
                email_type='ENROLLMENT_CONFIRMATION',
                status='SENT'
            ).exists()
        )

    # 4. Enrollment email idempotency (no duplicate sends)
    def test_04_enrollment_confirmation_idempotent(self):
        data = {
            'student_name': "Arun Kumar",
            'student_phone': "9876543210",
            'student_email': "arun.kumar@example.com",
            'product': self.course,
            'branch': self.branch,
            'assigned_counselor': self.counselor,
            'base_course_fee': Decimal('25000.00'),
            'gst_treatment': GSTTreatment.INCLUSIVE,
            'tax_rate': Decimal('18.00'),
            'payment_plan': PaymentPlan.FULL_PAYMENT,
        }
        with self.captureOnCommitCallbacks(execute=True):
            enrollment = create_or_update_enrollment(self.lead, self.counselor, data)

        self.assertEqual(len(mail.outbox), 1)

        # Re-run or update enrollment
        with self.captureOnCommitCallbacks(execute=True):
            enrollment = create_or_update_enrollment(self.lead, self.counselor, data)

        # Should still be 1, no duplicate sent
        self.assertEqual(len(mail.outbox), 1)

    # 5. Verified payment sends one receipt email with complete financial accounting
    def test_05_verified_payment_sends_receipt_with_gst_and_balances(self):
        data = {
            'student_name': "Arun Kumar",
            'student_phone': "9876543210",
            'student_email': "arun.kumar@example.com",
            'product': self.course,
            'branch': self.branch,
            'assigned_counselor': self.counselor,
            'base_course_fee': Decimal('25000.00'),
            'gst_treatment': GSTTreatment.EXCLUSIVE,  # 25,000 + 18% GST (4,500) = 29,500
            'tax_rate': Decimal('18.00'),
            'payment_plan': PaymentPlan.SPLIT_PAYMENT,
            'installment_count': 2,
        }
        with self.captureOnCommitCallbacks(execute=True):
            enrollment = create_or_update_enrollment(self.lead, self.counselor, data)

        mail.outbox.clear()  # Clear enrollment email

        # Record partial payment 1: ₹15,000
        payment_data = {
            'amount': Decimal('15000.00'),
            'payment_method': PaymentMethod.UPI,
            'transaction_reference': 'UPI-REF-998877',
            'notes': 'Installment 1 paid',
        }
        with self.captureOnCommitCallbacks(execute=True):
            txn = record_payment(enrollment, self.counselor, payment_data)

        self.assertEqual(len(mail.outbox), 1)
        receipt_email = mail.outbox[0]

        # Verify subject & contents
        expected_subject = f"Payment Receipt — {enrollment.enrollment_number} — UPI-REF-998877"
        self.assertEqual(receipt_email.subject, expected_subject)
        self.assertIn("Arun Kumar", receipt_email.body)
        self.assertIn("15000.00", receipt_email.body)
        self.assertIn("29500.00", receipt_email.body)  # Total course fee
        self.assertIn("14500.00", receipt_email.body)  # Remaining balance (29,500 - 15,000)
        self.assertIn("4500.00", receipt_email.body)   # GST Component
        self.assertIn("25000.00", receipt_email.body)  # Taxable Amount

        # Verify DB status
        txn.refresh_from_db()
        self.assertTrue(txn.email_sent)
        self.assertIsNotNone(txn.email_sent_at)
        self.assertTrue(
            PaymentEmailLog.objects.filter(
                payment=txn,
                email_type='PAYMENT_CONFIRMATION',
                status='SENT'
            ).exists()
        )

    # 6. Full payment stops further installment reminders and reflects 0 balance
    def test_06_full_payment_updates_ledger_and_clears_balance(self):
        data = {
            'student_name': "Arun Kumar",
            'student_phone': "9876543210",
            'student_email': "arun.kumar@example.com",
            'product': self.course,
            'branch': self.branch,
            'assigned_counselor': self.counselor,
            'base_course_fee': Decimal('20000.00'),
            'gst_treatment': GSTTreatment.INCLUSIVE,
            'tax_rate': Decimal('18.00'),
            'payment_plan': PaymentPlan.FULL_PAYMENT,
        }
        with self.captureOnCommitCallbacks(execute=True):
            enrollment = create_or_update_enrollment(self.lead, self.counselor, data)

        mail.outbox.clear()

        # Full payment of ₹20,000
        payment_data = {
            'amount': Decimal('20000.00'),
            'payment_method': PaymentMethod.BANK_TRANSFER,
            'transaction_reference': 'NEFT-883311',
        }
        with self.captureOnCommitCallbacks(execute=True):
            txn = record_payment(enrollment, self.counselor, payment_data)

        enrollment.refresh_from_db()
        self.assertEqual(enrollment.outstanding_balance, Decimal('0.00'))
        self.assertEqual(enrollment.total_paid, Decimal('20000.00'))
        self.assertEqual(enrollment.payment_status, 'Fully Paid')

        # Check receipt email
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn("0.00", mail.outbox[0].body)

    # 7. Failed or pending payments do not send successful receipts
    def test_07_failed_or_pending_payments_do_not_dispatch_receipts(self):
        data = {
            'student_name': "Arun Kumar",
            'student_phone': "9876543210",
            'student_email': "arun.kumar@example.com",
            'product': self.course,
            'branch': self.branch,
            'base_course_fee': Decimal('20000.00'),
            'gst_treatment': GSTTreatment.INCLUSIVE,
        }
        with self.captureOnCommitCallbacks(execute=True):
            enrollment = create_or_update_enrollment(self.lead, self.counselor, data)

        mail.outbox.clear()

        # Create a pending or failed payment directly
        payment_pending = PaymentTransaction.objects.create(
            enrollment=enrollment,
            amount=Decimal('5000.00'),
            payment_method=PaymentMethod.ONLINE,
            receipt_number='REC-PENDING-01',
            status=PaymentTransactionStatus.PENDING
        )
        success, msg = send_payment_receipt_email(payment_pending)
        self.assertFalse(success)
        self.assertIn("non-successful", msg)
        self.assertEqual(len(mail.outbox), 0)

    # 8. Idempotency: duplicate payment email execution does not duplicate emails
    def test_08_duplicate_payment_receipt_idempotent(self):
        data = {
            'student_name': "Arun Kumar",
            'student_phone': "9876543210",
            'student_email': "arun.kumar@example.com",
            'product': self.course,
            'branch': self.branch,
            'base_course_fee': Decimal('20000.00'),
            'gst_treatment': GSTTreatment.INCLUSIVE,
        }
        with self.captureOnCommitCallbacks(execute=True):
            enrollment = create_or_update_enrollment(self.lead, self.counselor, data)

        mail.outbox.clear()

        with self.captureOnCommitCallbacks(execute=True):
            txn = record_payment(enrollment, self.counselor, {'amount': Decimal('5000.00'), 'payment_method': PaymentMethod.CASH})

        self.assertEqual(len(mail.outbox), 1)

        # Call send_payment_receipt_email again manually
        success, msg = send_payment_receipt_email(txn)
        self.assertTrue(success)
        self.assertIn("already sent", msg)
        self.assertEqual(len(mail.outbox), 1)

    # 9. Installment due reminders sent to eligible students with remaining balance
    def test_09_installment_reminders_sent_to_eligible_students(self):
        today = timezone.localdate()
        data = {
            'student_name': "Arun Kumar",
            'student_phone': "9876543210",
            'student_email': "arun.kumar@example.com",
            'product': self.course,
            'branch': self.branch,
            'base_course_fee': Decimal('20000.00'),
            'gst_treatment': GSTTreatment.INCLUSIVE,
            'payment_plan': PaymentPlan.SPLIT_PAYMENT,
            'installment_count': 2,
            'first_installment_date': today,
        }
        with self.captureOnCommitCallbacks(execute=True):
            enrollment = create_or_update_enrollment(self.lead, self.counselor, data)

        mail.outbox.clear()

        # Installment 1 is due today, has remaining_balance = 10,000
        summary = process_installment_reminders_batch(target_date=today)
        self.assertEqual(summary['due_today'], 1)
        self.assertEqual(len(mail.outbox), 1)

        reminder_email = mail.outbox[0]
        self.assertEqual(reminder_email.subject, f"Fee Payment Reminder — {self.course.name}")
        self.assertIn("Arun Kumar", reminder_email.body)
        self.assertIn("10000.00", reminder_email.body)

    # 10. Fully paid installments stop receiving reminders
    def test_10_fully_paid_installments_stop_receiving_reminders(self):
        today = timezone.localdate()
        data = {
            'student_name': "Arun Kumar",
            'student_phone': "9876543210",
            'student_email': "arun.kumar@example.com",
            'product': self.course,
            'branch': self.branch,
            'base_course_fee': Decimal('20000.00'),
            'gst_treatment': GSTTreatment.INCLUSIVE,
            'payment_plan': PaymentPlan.SPLIT_PAYMENT,
            'installment_count': 2,
            'first_installment_date': today,
        }
        with self.captureOnCommitCallbacks(execute=True):
            enrollment = create_or_update_enrollment(self.lead, self.counselor, data)

        # Pay installment 1 in full
        with self.captureOnCommitCallbacks(execute=True):
            record_payment(enrollment, self.counselor, {'amount': Decimal('10000.00'), 'payment_method': PaymentMethod.UPI})

        mail.outbox.clear()

        # Run reminders for today
        summary = process_installment_reminders_batch(target_date=today)
        # Installment 1 has remaining_balance = 0, so due_today count should be 0
        self.assertEqual(summary['due_today'], 0)
        self.assertEqual(len(mail.outbox), 0)

    # 11. Overdue installment reminders trigger on schedule (3 days overdue & weekly)
    def test_11_overdue_installment_reminders_schedule(self):
        today = timezone.localdate()
        data = {
            'student_name': "Arun Kumar",
            'student_phone': "9876543210",
            'student_email': "arun.kumar@example.com",
            'product': self.course,
            'branch': self.branch,
            'base_course_fee': Decimal('20000.00'),
            'gst_treatment': GSTTreatment.INCLUSIVE,
            'payment_plan': PaymentPlan.SPLIT_PAYMENT,
            'installment_count': 2,
            'first_installment_date': today - timedelta(days=3),  # 3 days overdue
        }
        with self.captureOnCommitCallbacks(execute=True):
            enrollment = create_or_update_enrollment(self.lead, self.counselor, data)

        mail.outbox.clear()

        summary = process_installment_reminders_batch(target_date=today)
        self.assertEqual(summary['overdue_3_days'], 1)
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn("OVERDUE", mail.outbox[0].body)

    # 12. SMTP failure preserves enrollment and payment data in DB without rollback
    def test_12_smtp_failure_preserves_records_and_sets_failed_status(self):
        with patch('services.email_service.EmailMultiAlternatives.send', side_effect=Exception("SMTP Connection timed out")):
            data = {
                'student_name': "Karan Mehta",
                'student_phone': "9876543219",
                'student_email': "karan.mehta@example.com",
                'product': self.course,
                'branch': self.branch,
                'assigned_counselor': self.counselor,
                'base_course_fee': Decimal('20000.00'),
                'gst_treatment': GSTTreatment.INCLUSIVE,
            }
            lead_karan = Lead.objects.create(
                name="Karan Mehta",
                phone="9876543219",
                email="karan.mehta@example.com",
                branch=self.branch,
                assigned_counselor=self.counselor,
                product=self.course
            )

            with self.captureOnCommitCallbacks(execute=True):
                enrollment = create_or_update_enrollment(lead_karan, self.counselor, data)

            # Enrollment must be intact in database
            enrollment.refresh_from_db()
            self.assertEqual(enrollment.student_name, "Karan Mehta")
            self.assertFalse(enrollment.confirmation_email_sent)
            self.assertIn("timed out", enrollment.confirmation_email_error)

            # Now test payment failure isolation
            with self.captureOnCommitCallbacks(execute=True):
                payment = record_payment(enrollment, self.counselor, {'amount': Decimal('5000.00'), 'payment_method': PaymentMethod.UPI})

            # Payment must be intact in database
            payment.refresh_from_db()
            self.assertEqual(payment.amount, Decimal('5000.00'))
            self.assertFalse(payment.email_sent)
            self.assertIn("timed out", payment.email_error)
            self.assertEqual(enrollment.total_paid, Decimal('5000.00'))  # Financial ledger intact!

    # 13. Resending failed emails safely retries without creating duplicate transactions
    def test_13_resend_failed_emails_without_duplication(self):
        lead_karan = Lead.objects.create(
            name="Karan Mehta",
            phone="9876543219",
            email="karan.mehta@example.com",
            branch=self.branch,
            assigned_counselor=self.counselor,
            product=self.course
        )
        data = {
            'student_name': "Karan Mehta",
            'student_phone': "9876543219",
            'student_email': "karan.mehta@example.com",
            'product': self.course,
            'branch': self.branch,
            'assigned_counselor': self.counselor,
            'base_course_fee': Decimal('20000.00'),
            'gst_treatment': GSTTreatment.INCLUSIVE,
        }
        with self.captureOnCommitCallbacks(execute=True):
            enrollment = create_or_update_enrollment(lead_karan, self.counselor, data)

        with self.captureOnCommitCallbacks(execute=True):
            payment = record_payment(enrollment, self.counselor, {'amount': Decimal('5000.00'), 'payment_method': PaymentMethod.UPI})

        initial_payment_count = PaymentTransaction.objects.count()
        mail.outbox.clear()

        # Retry sending payment receipt
        success, msg = send_payment_receipt_email(payment, force_retry=True)
        self.assertTrue(success)
        self.assertEqual(len(mail.outbox), 1)

        # Payment count MUST remain the same (no duplicate ledger entries)
        self.assertEqual(PaymentTransaction.objects.count(), initial_payment_count)

    # 14. Branch permission check for enrollment & payments
    def test_14_branch_permissions_enforced(self):
        other_branch = Branch.objects.create(name="Coimbatore Campus", status="Active")
        other_counselor = User.objects.create_user(
            username="other_counselor",
            email="other@test.com",
            password="OtherPass123!",
            role=UserRole.COUNSELOR,
            branch=other_branch
        )

        # Other counselor cannot enroll lead assigned to self.counselor
        data = {
            'student_name': "Arun Kumar",
            'student_phone': "9876543210",
            'base_course_fee': Decimal('20000.00'),
            'gst_treatment': GSTTreatment.INCLUSIVE,
        }
        with self.assertRaises(Exception):
            create_or_update_enrollment(self.lead, other_counselor, data)

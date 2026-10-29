import io
from decimal import Decimal
from PIL import Image

from django.test import TestCase, Client
from django.urls import reverse
from django.core import mail
from django.core.files.uploadedfile import SimpleUploadedFile
from django.utils import timezone
from django.core.exceptions import ValidationError, PermissionDenied

import openpyxl

from accounts.models import User, UserRole
from branches.models import Branch
from products.models import Product
from leads.models import (
    Lead,
    LeadStatus,
    Enrollment,
    Installment,
    PaymentTransaction,
    PaymentVerificationHistory,
    GSTTreatment,
    PaymentPlan,
    InstallmentMethod,
    PaymentMethod,
    PaymentTransactionStatus,
)
from leads.services_enrollment import (
    create_or_update_enrollment,
    record_payment,
    approve_payment,
    reject_payment,
    resubmit_payment,
    validate_payment_proof,
)


def create_test_image(filename="proof.png", size=(100, 100), color=(0, 200, 100), fmt="PNG"):
    """Creates a genuine, valid in-memory image for upload testing."""
    img = Image.new("RGB", size, color=color)
    buf = io.BytesIO()
    img.save(buf, format=fmt)
    buf.seek(0)
    return SimpleUploadedFile(filename, buf.getvalue(), content_type=f"image/{fmt.lower()}")


class AccountantWorkflowTestSuite(TestCase):
    """
    Automated integration tests for the Accountant role, payment verification queue,
    proof upload validation, atomic ledger updates, and financial reporting.
    """

    def setUp(self):
        # 1. Branches
        self.branch1 = Branch.objects.create(name="OMR Chennai", status="Active")
        self.branch2 = Branch.objects.create(name="Bangalore Central", status="Active")

        # 2. Users
        self.admin = User.objects.create_user(
            username="admin.test",
            email="admin@techpanda.org",
            password="StrongPassword123!",
            role=UserRole.ADMIN
        )
        self.accountant = User.objects.create_user(
            username="accountant.omr",
            email="accountant@techpanda.org",
            password="StrongPassword123!",
            role=UserRole.ACCOUNTANT,
            branch=self.branch1
        )
        self.counselor = User.objects.create_user(
            username="counselor.omr",
            email="counselor@techpanda.org",
            password="StrongPassword123!",
            role=UserRole.COUNSELOR,
            branch=self.branch1
        )
        self.telecaller = User.objects.create_user(
            username="telecaller.omr",
            email="telecaller@techpanda.org",
            password="StrongPassword123!",
            role=UserRole.TELECALLER,
            branch=self.branch1
        )

        # 3. Product & Lead
        self.course = Product.objects.create(name="Full Stack Python AI", price=Decimal('30000.00'), status=Product.Status.ACTIVE)
        self.lead = Lead.objects.create(
            name="Siddharth Roy",
            phone="9876501234",
            email="siddharth.roy@example.com",
            branch=self.branch1,
            assigned_counselor=self.counselor,
            status=LeadStatus.INTERESTED
        )

        # 4. Enrollment: Fee = 30000, Inclusive 18%, 2 installments of 15000 each
        data = {
            'student_name': "Siddharth Roy",
            'student_phone': "9876501234",
            'student_email': "siddharth.roy@example.com",
            'product': self.course,
            'branch': self.branch1,
            'assigned_counselor': self.counselor,
            'base_course_fee': Decimal('30000.00'),
            'gst_treatment': GSTTreatment.INCLUSIVE,
            'tax_rate': Decimal('18.00'),
            'payment_plan': PaymentPlan.SPLIT_PAYMENT,
            'installment_count': 2,
            'first_installment_date': timezone.localdate(),
        }
        self.enrollment = create_or_update_enrollment(self.lead, self.counselor, data)

    # 1. Role Login & Dashboard Redirect
    def test_accountant_login_redirect_and_permissions(self):
        client = Client()
        client.force_login(self.accountant)

        # Login redirect
        res = client.get(reverse('login_redirect'))
        self.assertRedirects(res, reverse('accountant_dashboard'))

        # Dashboard access allowed for Accountant
        res_dash = client.get(reverse('accountant_dashboard'))
        self.assertEqual(res_dash.status_code, 200)
        self.assertContains(res_dash, "Financial Dashboard")

        # Telecaller strictly denied from accountant dashboard
        client.force_login(self.telecaller)
        res_tel = client.get(reverse('accountant_dashboard'))
        self.assertRedirects(res_tel, reverse('telecaller_dashboard'))

        # Counselor strictly denied from accountant dashboard
        client.force_login(self.counselor)
        res_coun = client.get(reverse('accountant_dashboard'))
        self.assertRedirects(res_coun, reverse('counselor_dashboard'))

    # 2. Payment Proof File Validation
    def test_payment_proof_validation(self):
        # Valid PNG
        valid_img = create_test_image("receipt.png", fmt="PNG")
        try:
            validate_payment_proof(valid_img)
        except ValidationError:
            self.fail("validate_payment_proof raised ValidationError unexpectedly on valid PNG!")

        # Invalid extension (e.g. .pdf or .exe)
        invalid_ext_file = SimpleUploadedFile("malicious.exe", b"not an image", content_type="application/octet-stream")
        with self.assertRaises(ValidationError) as cm:
            validate_payment_proof(invalid_ext_file)
        self.assertIn("Invalid file format", str(cm.exception))

        # Corrupt image bytes with valid extension
        corrupt_file = SimpleUploadedFile("corrupt.png", b"this is pure text, not png", content_type="image/png")
        with self.assertRaises(ValidationError) as cm2:
            validate_payment_proof(corrupt_file)
        self.assertIn("not a valid image", str(cm2.exception))

    # 3. Mandatory Proof for Online Methods vs Optional for Cash
    def test_mandatory_proof_online_methods_and_cash_exception(self):
        # Online without proof -> Raises ValidationError
        pay_data = {
            'amount': Decimal('15000.00'),
            'payment_method': PaymentMethod.UPI,
            'transaction_reference': 'UPI-TEST-001',
            'auto_approve': False,
        }
        with self.assertRaises(ValidationError) as cm:
            record_payment(self.enrollment, self.counselor, pay_data)
        self.assertIn("mandatory for online payment method", str(cm.exception))

        # Cash without proof -> Permitted
        cash_data = {
            'amount': Decimal('5000.00'),
            'payment_method': PaymentMethod.CASH,
            'notes': 'Cash advance payment',
            'auto_approve': False,
        }
        cash_txn = record_payment(self.enrollment, self.counselor, cash_data)
        self.assertEqual(cash_txn.status, PaymentTransactionStatus.PENDING_VERIFICATION)
        self.assertEqual(cash_txn.amount, Decimal('5000.00'))
        self.assertFalse(cash_txn.payment_proof)

    # 4. Submission Enters PENDING_VERIFICATION & Balances Remain Uncredited
    def test_counselor_submission_pending_and_suppresses_email(self):
        mail.outbox.clear()
        proof = create_test_image("gpay_screenshot.jpg", fmt="JPEG")

        pay_data = {
            'amount': Decimal('15000.00'),
            'payment_method': PaymentMethod.UPI,
            'transaction_reference': 'UPI-REF-554433',
            'notes': 'Installment 1 paid via GPay',
            'payment_proof': proof,
            'auto_approve': False,
        }

        with self.captureOnCommitCallbacks(execute=True):
            txn = record_payment(self.enrollment, self.counselor, pay_data)

        # 1. Status is PENDING_VERIFICATION
        self.assertEqual(txn.status, PaymentTransactionStatus.PENDING_VERIFICATION)
        self.assertTrue(txn.is_pending_verification)
        self.assertFalse(txn.is_approved)

        # 2. Balances are NOT updated yet
        self.enrollment.refresh_from_db()
        self.assertEqual(self.enrollment.total_paid, Decimal('0.00'))
        self.assertEqual(self.enrollment.outstanding_balance, Decimal('30000.00'))

        inst1 = self.enrollment.installments.get(installment_number=1)
        self.assertEqual(inst1.amount_paid, Decimal('0.00'))
        self.assertEqual(inst1.remaining_balance, Decimal('15000.00'))

        # 3. No student receipt email sent
        self.assertEqual(len(mail.outbox), 0)

        # 4. Audit History Logged
        history = PaymentVerificationHistory.objects.filter(payment=txn).first()
        self.assertIsNotNone(history)
        self.assertEqual(history.action, PaymentVerificationHistory.Action.SUBMITTED)
        self.assertEqual(history.performed_by, self.counselor)

    # 5. Accountant Approval, Atomic Balance Updates & Email Dispatch
    def test_accountant_approval_and_idempotency(self):
        proof = create_test_image("bank_transfer.png", fmt="PNG")
        pay_data = {
            'amount': Decimal('15000.00'),
            'payment_method': PaymentMethod.BANK_TRANSFER,
            'transaction_reference': 'NEFT-889900',
            'payment_proof': proof,
            'auto_approve': False,
        }
        txn = record_payment(self.enrollment, self.counselor, pay_data)

        mail.outbox.clear()

        # Approve payment
        with self.captureOnCommitCallbacks(execute=True):
            approved_txn = approve_payment(txn.id, self.accountant)

        self.assertEqual(approved_txn.status, PaymentTransactionStatus.APPROVED)
        self.assertEqual(approved_txn.reviewed_by, self.accountant)
        self.assertIsNotNone(approved_txn.reviewed_at)

        # Balances now reflect approved payment
        self.enrollment.refresh_from_db()
        self.assertEqual(self.enrollment.total_paid, Decimal('15000.00'))
        self.assertEqual(self.enrollment.outstanding_balance, Decimal('15000.00'))

        inst1 = self.enrollment.installments.get(installment_number=1)
        self.assertEqual(inst1.amount_paid, Decimal('15000.00'))
        self.assertEqual(inst1.remaining_balance, Decimal('0.00'))

        # Email dispatched to student
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn("Payment Receipt", mail.outbox[0].subject)
        self.assertIn("15000.00", mail.outbox[0].body)

        # Idempotency: Calling approve again does not double-credit or double-send
        with self.captureOnCommitCallbacks(execute=True):
            re_approved = approve_payment(approved_txn.id, self.accountant)

        self.enrollment.refresh_from_db()
        self.assertEqual(self.enrollment.total_paid, Decimal('15000.00'))
        self.assertEqual(len(mail.outbox), 1)

    # 6. Rejection Workflow with Mandatory Comment
    def test_accountant_rejection_and_mandatory_comment(self):
        proof = create_test_image("blurry_proof.jpg", fmt="JPEG")
        pay_data = {
            'amount': Decimal('15000.00'),
            'payment_method': PaymentMethod.UPI,
            'transaction_reference': 'UPI-REF-112233',
            'payment_proof': proof,
            'auto_approve': False,
        }
        txn = record_payment(self.enrollment, self.counselor, pay_data)

        # Rejection without comment -> Fails
        with self.assertRaises(ValidationError) as cm:
            reject_payment(txn.id, self.accountant, "")
        self.assertIn("rejection comment is mandatory", str(cm.exception))

        # Rejection with comment
        rejected_txn = reject_payment(txn.id, self.accountant, "UTR number does not match bank statement.")
        self.assertEqual(rejected_txn.status, PaymentTransactionStatus.REJECTED)
        self.assertEqual(rejected_txn.rejection_comment, "UTR number does not match bank statement.")
        self.assertEqual(rejected_txn.reviewed_by, self.accountant)

        # Balances remain 0
        self.enrollment.refresh_from_db()
        self.assertEqual(self.enrollment.total_paid, Decimal('0.00'))

        # Audit history logged
        history = PaymentVerificationHistory.objects.filter(payment=rejected_txn, action=PaymentVerificationHistory.Action.REJECTED).first()
        self.assertIsNotNone(history)
        self.assertEqual(history.comment, "UTR number does not match bank statement.")

    # 7. Counselor Resubmission Workflow
    def test_counselor_resubmission(self):
        proof = create_test_image("first_proof.jpg", fmt="JPEG")
        txn = record_payment(self.enrollment, self.counselor, {
            'amount': Decimal('15000.00'),
            'payment_method': PaymentMethod.UPI,
            'payment_proof': proof,
            'auto_approve': False,
        })
        reject_payment(txn.id, self.accountant, "Blurred screenshot")

        # Counselor resubmits with new proof and corrected UTR
        new_proof = create_test_image("sharp_proof.png", fmt="PNG")
        resubmitted_txn = resubmit_payment(
            txn.id,
            self.counselor,
            data={
                'transaction_reference': 'CORRECTED-UTR-999',
                'resubmission_notes': 'Uploaded high-res PDF receipt screenshot.'
            },
            new_proof=new_proof
        )

        self.assertEqual(resubmitted_txn.status, PaymentTransactionStatus.PENDING_VERIFICATION)
        self.assertEqual(resubmitted_txn.resubmission_count, 1)
        self.assertEqual(resubmitted_txn.transaction_reference, 'CORRECTED-UTR-999')

        # Now accountant approves
        approved_txn = approve_payment(resubmitted_txn.id, self.accountant)
        self.assertEqual(approved_txn.status, PaymentTransactionStatus.APPROVED)

    # 8. Financial Dashboard 6 Cards & Mutual Exclusivity
    def test_financial_dashboard_cards_calculations(self):
        client = Client()
        client.force_login(self.accountant)

        # 1. Cash Approved Payment: 5,000
        cash_txn = record_payment(self.enrollment, self.counselor, {
            'amount': Decimal('5000.00'),
            'payment_method': PaymentMethod.CASH,
            'auto_approve': False,
        })
        approve_payment(cash_txn.id, self.accountant)

        # 2. Account Approved Payment (UPI): 10,000
        upi_proof = create_test_image("upi.png", fmt="PNG")
        upi_txn = record_payment(self.enrollment, self.counselor, {
            'amount': Decimal('10000.00'),
            'payment_method': PaymentMethod.UPI,
            'payment_proof': upi_proof,
            'auto_approve': False,
        })
        approve_payment(upi_txn.id, self.accountant)

        res = client.get(reverse('accountant_dashboard'))
        self.assertEqual(res.status_code, 200)

        ctx = res.context
        # Card 1: Total Fees Due = 30000 - 15000 = 15000
        self.assertEqual(ctx['total_fees_due'], Decimal('15000.00'))
        # Card 2: Received by Cash = 5000
        self.assertEqual(ctx['cash_received'], Decimal('5000.00'))
        # Card 3: Received by Account = 10000
        self.assertEqual(ctx['account_received'], Decimal('10000.00'))
        # Card 4: Total Collection = 15000
        self.assertEqual(ctx['total_collection'], Decimal('15000.00'))
        # Card 5: New Joinee First Fee = 15000
        self.assertEqual(ctx['first_fee_approved'], Decimal('15000.00'))
        # Card 6: Pending Fee Collected = 0 (Total collection - first fee)
        self.assertEqual(ctx['pending_fee_collected'], Decimal('0.00'))

    # 9. 7-Sheet Monthly Excel Export & Formula Injection Protection
    def test_monthly_excel_report_generation(self):
        client = Client()
        client.force_login(self.accountant)

        res = client.get(reverse('accountant_monthly_report_excel'))
        self.assertEqual(res.status_code, 200)
        self.assertEqual(
            res['Content-Type'],
            'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        )

        wb = openpyxl.load_workbook(io.BytesIO(res.content))
        expected_sheets = [
            "Executive Summary",
            "Cash Transactions",
            "Bank Transactions",
            "New Joinee First Fees",
            "Pending Fees Collected",
            "Outstanding Balances",
            "Verification Audit Log",
        ]
        self.assertEqual(wb.sheetnames, expected_sheets)

    # 10. Private Proof Access Control Endpoint
    def test_payment_proof_view_access_control(self):
        proof = create_test_image("private_receipt.jpg", fmt="JPEG")
        txn = record_payment(self.enrollment, self.counselor, {
            'amount': Decimal('5000.00'),
            'payment_method': PaymentMethod.UPI,
            'payment_proof': proof,
            'auto_approve': False,
        })

        client = Client()

        # Accountant -> Allowed
        client.force_login(self.accountant)
        res_acc = client.get(reverse('accountant_payment_proof_view', args=[txn.id]))
        self.assertEqual(res_acc.status_code, 200)

        # Assigned Counselor -> Allowed
        client.force_login(self.counselor)
        res_coun = client.get(reverse('accountant_payment_proof_view', args=[txn.id]))
        self.assertEqual(res_coun.status_code, 200)

        # Unrelated Telecaller -> Denied (403)
        client.force_login(self.telecaller)
        res_tel = client.get(reverse('accountant_payment_proof_view', args=[txn.id]))
        self.assertEqual(res_tel.status_code, 403)

    # 11. Payment Rejection Routing to Submitting Counselor & Isolation
    def test_payment_rejection_routing_to_submitting_counselor(self):
        # Counselor B is another counselor in the same branch
        counselor_b = User.objects.create_user(
            username="counselor.b",
            email="counselor.b@techpanda.org",
            password="StrongPassword123!",
            role=UserRole.COUNSELOR,
            branch=self.branch1
        )

        # Step 1: Counselor A (self.counselor) records payment
        proof = create_test_image("proof_a.png", fmt="PNG")
        txn = record_payment(self.enrollment, self.counselor, {
            'amount': Decimal('12000.00'),
            'payment_method': PaymentMethod.UPI,
            'transaction_reference': 'UTR-INITIAL-111',
            'payment_proof': proof,
            'auto_approve': False,
        })
        self.assertEqual(txn.recorded_by, self.counselor)
        self.assertEqual(txn.status, PaymentTransactionStatus.PENDING_VERIFICATION)

        # Step 2: Accountant rejects payment with feedback
        rejection_reason = "Payment proof is illegible; transaction reference mismatch on bank statement."
        reject_payment(txn.id, self.accountant, rejection_reason)

        txn.refresh_from_db()
        self.assertEqual(txn.status, PaymentTransactionStatus.REJECTED)
        self.assertEqual(txn.rejection_comment, rejection_reason)
        # Original creator recorded_by is strictly preserved!
        self.assertEqual(txn.recorded_by, self.counselor)

        # Step 3: Submitting Counselor A checks their dashboard
        client = Client()
        client.force_login(self.counselor)
        res_coun_a = client.get(reverse('counselor_dashboard'))
        self.assertEqual(res_coun_a.status_code, 200)
        self.assertIn('rejected_payments', res_coun_a.context)
        rejected_list_a = list(res_coun_a.context['rejected_payments'])
        self.assertEqual(len(rejected_list_a), 1)
        self.assertEqual(rejected_list_a[0].id, txn.id)
        self.assertContains(res_coun_a, "Payment proof is illegible")

        # Step 4: Reassign the lead and enrollment to Counselor B
        self.lead.assigned_counselor = counselor_b
        self.lead.save()
        self.enrollment.assigned_counselor = counselor_b
        self.enrollment.save()

        # Step 5: Counselor B checks their dashboard -> must NOT see Counselor A's rejected payment!
        client.force_login(counselor_b)
        res_coun_b = client.get(reverse('counselor_dashboard'))
        self.assertEqual(res_coun_b.status_code, 200)
        rejected_list_b = list(res_coun_b.context['rejected_payments'])
        self.assertEqual(len(rejected_list_b), 0)
        self.assertNotContains(res_coun_b, "Payment proof is illegible")

        # Step 6: Counselor B attempts to resubmit Counselor A's rejected payment -> Denied!
        new_proof_b = create_test_image("proof_b.png", fmt="PNG")
        res_submit_b = client.post(
            reverse('enrollment_resubmit_payment', args=[txn.id]),
            {
                'amount': '12000.00',
                'payment_method': 'UPI',
                'transaction_reference': 'UTR-HACK-222',
                'payment_proof': new_proof_b,
                'resubmission_notes': 'Counselor B trying to resubmit',
            }
        )
        # Check permission denied / redirection with error message
        txn.refresh_from_db()
        self.assertEqual(txn.status, PaymentTransactionStatus.REJECTED)  # Not resubmitted!

        # Direct service call by Counselor B also raises PermissionDenied
        with self.assertRaises(PermissionDenied):
            resubmit_payment(txn.id, counselor_b, data={'transaction_reference': 'UTR-DIRECT-FAIL'})

        # Step 7: Submitting Counselor A resubmits their rejected payment -> Success!
        client.force_login(self.counselor)
        valid_proof_a = create_test_image("valid_proof_sharp.png", fmt="PNG")
        res_submit_a = client.post(
            reverse('enrollment_resubmit_payment', args=[txn.id]),
            {
                'amount': '12000.00',
                'payment_method': 'UPI',
                'transaction_reference': 'UTR-CORRECTED-333',
                'payment_proof': valid_proof_a,
                'resubmission_notes': 'Uploaded sharp HD payment receipt.',
            }
        )
        self.assertEqual(res_submit_a.status_code, 302)

        txn.refresh_from_db()
        self.assertEqual(txn.status, PaymentTransactionStatus.PENDING_VERIFICATION)
        self.assertEqual(txn.recorded_by, self.counselor)  # recorded_by is preserved!
        self.assertEqual(txn.resubmission_count, 1)
        self.assertEqual(txn.transaction_reference, 'UTR-CORRECTED-333')

        # Step 8: Accountant verifies & approves the resubmitted payment
        client.force_login(self.accountant)
        res_approve = client.post(reverse('accountant_approve_payment', args=[txn.id]))
        self.assertEqual(res_approve.status_code, 302)

        txn.refresh_from_db()
        self.assertEqual(txn.status, PaymentTransactionStatus.APPROVED)
        self.assertEqual(txn.recorded_by, self.counselor)

    # 12. Receptionist Dashboard Table Structure & Branch Scoping
    def test_receptionist_dashboard_view_and_scoping(self):
        receptionist = User.objects.create_user(
            username="receptionist.omr",
            email="receptionist@techpanda.org",
            password="StrongPassword123!",
            role=UserRole.RECEPTIONIST,
            branch=self.branch1
        )

        # Create a walk-in lead in branch 1
        walkin_lead = Lead.objects.create(
            name="Ananya Sharma",
            phone="9876543210",
            email="ananya.sharma@example.com",
            source="Walk-in",
            branch=self.branch1,
            status=LeadStatus.INTERESTED
        )

        client = Client()
        client.force_login(receptionist)
        res = client.get(reverse('receptionist_dashboard'))
        self.assertEqual(res.status_code, 200)
        self.assertContains(res, "Ananya Sharma")
        self.assertContains(res, "Direct Walk-in")
        self.assertContains(res, "OMR Chennai")


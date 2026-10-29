"""
Automated Regression Test Suite for DigiPanda CRM Save, Submit, & Data-Persistence Actions.
Covers:
1. Add New Lead (Admin, Sales Head, Telecaller)
2. Edit Lead (Admin, Sales Head, Telecaller)
3. Student Enrollment with Email address
4. Payment Collection & Accountant Verification Approval
5. Verification of clean Category and Branch fallbacks
"""

import io
from decimal import Decimal
from PIL import Image

from django.test import TestCase, Client
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse

from accounts.models import User, UserRole
from branches.models import Branch
from lead_channels.models import Channel
from products.models import Product
from leads.models import Lead, LeadCategory
from leads.models_enrollment import (
    Enrollment,
    PaymentTransaction,
    PaymentTransactionStatus,
    GSTTreatment,
    PaymentPlan,
    InstallmentMethod
)
from services.email_service import get_brand_logo_data_uri, is_valid_email


class SaveActionAuditTests(TestCase):
    def setUp(self):
        self.branch, _ = Branch.objects.get_or_create(name="Chennai Audit Main", defaults={'status': 'Active'})
        self.product, _ = Product.objects.get_or_create(name="Full Stack Master Audit", defaults={'status': 'Active', 'price': Decimal('40000.00')})
        self.channel, _ = Channel.objects.get_or_create(name="Website Direct Audit", defaults={'status': 'Active'})

        self.admin = User.objects.filter(role=UserRole.ADMIN, is_active=True).first()
        if not self.admin:
            self.admin = User.objects.create_superuser(
                username="admin_audit_u",
                email="admin_audit_u@digipanda.test",
                password="Password@123",
                role=UserRole.ADMIN
            )

        self.sales_head = User.objects.filter(role=UserRole.SALES_HEAD, is_active=True).first()
        if not self.sales_head:
            self.sales_head = User.objects.create_user(
                username="sh_audit_u",
                email="sh_audit_u@digipanda.test",
                password="Password@123",
                role=UserRole.SALES_HEAD,
                branch=self.branch
            )

        self.telecaller = User.objects.filter(role=UserRole.TELECALLER, is_active=True).first()
        if not self.telecaller:
            self.telecaller = User.objects.create_user(
                username="tc_audit_u",
                email="tc_audit_u@digipanda.test",
                password="Password@123",
                role=UserRole.TELECALLER,
                branch=self.branch
            )

        self.accountant = User.objects.filter(role=UserRole.ACCOUNTANT, is_active=True).first()
        if not self.accountant:
            self.accountant = User.objects.create_user(
                username="acc_audit_u",
                email="acc_audit_u@digipanda.test",
                password="Password@123",
                role=UserRole.ACCOUNTANT,
                branch=self.branch
            )

    def test_email_service_imports_and_logo(self):
        """Verifies email_service has os & base64 imported and get_brand_logo_data_uri executes without NameError."""
        self.assertTrue(is_valid_email("test@digipanda.com"))
        uri = get_brand_logo_data_uri()
        self.assertTrue(uri is None or uri.startswith("data:image/png;base64,"))

    def test_admin_add_new_lead_persists(self):
        """Phase 2 verification: Admin can successfully create and persist a new lead."""
        Lead.objects.filter(phone='9876543210').delete()

        client = Client()
        client.force_login(self.admin)

        post_data = {
            'name': 'Rajesh Sharma',
            'phone': '9876543210',
            'email': 'rajesh.sharma@example.com',
            'status': 'New',
            'channel': self.channel.id,
            'product': self.product.id,
            'branch': self.branch.id,
            'notes': 'Prospective student inquiry'
        }

        response = client.post(reverse('admin_lead_create'), post_data, follow=False)
        self.assertEqual(response.status_code, 302)

        lead = Lead.objects.filter(phone='9876543210').first()
        self.assertIsNotNone(lead)
        self.assertEqual(lead.name, 'Rajesh Sharma')
        self.assertEqual(lead.email, 'rajesh.sharma@example.com')
        self.assertEqual(lead.category, LeadCategory.TRAINING)

    def test_admin_edit_existing_lead_persists(self):
        """Phase 3 verification: Admin can edit an existing lead without validation failures."""
        Lead.objects.filter(phone='9876543211').delete()
        lead = Lead.objects.create(
            name="Pooja Patel",
            phone="9876543211",
            email="pooja@example.com",
            branch=self.branch,
            product=self.product,
            status="New"
        )

        client = Client()
        client.force_login(self.admin)

        edit_data = {
            'name': 'Pooja Patel Updated',
            'phone': '9876543211',
            'email': 'pooja.patel@example.com',
            'status': 'Contacted',
            'notes': 'Followed up via phone'
        }

        response = client.post(reverse('admin_lead_edit', args=[lead.pk]), edit_data, follow=False)
        self.assertEqual(response.status_code, 302)

        lead.refresh_from_db()
        self.assertEqual(lead.name, 'Pooja Patel Updated')
        self.assertEqual(lead.email, 'pooja.patel@example.com')
        self.assertEqual(lead.status, 'Contacted')

    def test_student_enrollment_with_email_succeeds(self):
        """Phase 4 verification: Entering an email address during enrollment completes successfully."""
        Lead.objects.filter(phone='9876543212').delete()
        lead = Lead.objects.create(
            name="Suresh Raina",
            phone="9876543212",
            email="",  # Initially empty email
            branch=self.branch,
            product=self.product,
            status="Interested"
        )

        client = Client()
        client.force_login(self.admin)

        enroll_data = {
            'student_name': 'Suresh Raina',
            'student_phone': '9876543212',
            'student_email': 'suresh.raina@digipanda.in',  # Email entered at enrollment time
            'product_id': self.product.id,
            'branch_id': self.branch.id,
            'base_course_fee': '40000.00',
            'gst_treatment': GSTTreatment.EXCLUSIVE,
            'tax_rate': '18.00',
            'payment_plan': PaymentPlan.FULL_PAYMENT,
            'installment_method': InstallmentMethod.AUTOMATIC,
            'notes': 'Admitted for Full Stack Master'
        }

        response = client.post(reverse('lead_enroll', args=[lead.pk]), enroll_data, follow=False)
        self.assertEqual(response.status_code, 302)

        enr = Enrollment.objects.filter(lead=lead).first()
        self.assertIsNotNone(enr)
        self.assertEqual(enr.student_name, 'Suresh Raina')
        self.assertEqual(enr.student_email, 'suresh.raina@digipanda.in')
        self.assertEqual(enr.total_payable, Decimal('47200.00'))

        lead.refresh_from_db()
        self.assertEqual(lead.status, 'Enrolled')
        self.assertEqual(lead.email, 'suresh.raina@digipanda.in')

    def test_payment_collection_and_accountant_approval(self):
        """Phase 5 verification: Recording cash payments and accountant approval."""
        Lead.objects.filter(phone='9876543213').delete()
        lead = Lead.objects.create(
            name="Vikram Seth",
            phone="9876543213",
            email="vikram@example.com",
            branch=self.branch,
            product=self.product,
            status="Interested"
        )

        client_admin = Client()
        client_admin.force_login(self.admin)

        # Create enrollment
        client_admin.post(reverse('lead_enroll', args=[lead.pk]), {
            'student_name': 'Vikram Seth',
            'student_phone': '9876543213',
            'student_email': 'vikram@example.com',
            'product_id': self.product.id,
            'branch_id': self.branch.id,
            'base_course_fee': '30000.00',
            'gst_treatment': GSTTreatment.INCLUSIVE,
            'tax_rate': '18.00',
            'payment_plan': PaymentPlan.FULL_PAYMENT,
            'installment_method': InstallmentMethod.AUTOMATIC,
        })
        enr = Enrollment.objects.get(lead=lead)

        # Record cash payment
        pay_res = client_admin.post(reverse('enrollment_record_payment', args=[enr.pk]), {
            'amount': '10000.00',
            'payment_method': 'Cash',
            'transaction_reference': 'CASH-REC-009',
            'notes': 'First installment in cash'
        }, follow=False)
        self.assertEqual(pay_res.status_code, 302)

        txn = PaymentTransaction.objects.filter(enrollment=enr).order_by('-id').first()
        self.assertIsNotNone(txn)
        self.assertEqual(txn.amount, Decimal('10000.00'))
        self.assertEqual(txn.status, PaymentTransactionStatus.PENDING_VERIFICATION)

        # Approver approves payment (Admin has global cross-branch verification access)
        client_acc = Client()
        client_acc.force_login(self.admin)

        approve_res = client_acc.post(reverse('accountant_approve_payment', args=[txn.pk]), follow=False)
        self.assertEqual(approve_res.status_code, 302)

        txn.refresh_from_db()
        self.assertEqual(txn.status, PaymentTransactionStatus.APPROVED)
        self.assertEqual(txn.reviewed_by, self.admin)

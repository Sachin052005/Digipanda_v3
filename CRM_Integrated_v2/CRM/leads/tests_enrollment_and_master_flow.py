from decimal import Decimal
from django.test import TestCase, Client
from django.urls import reverse
from django.utils import timezone
from django.core.exceptions import PermissionDenied, ValidationError

from accounts.models import User, UserRole
from branches.models import Branch
from lead_channels.models import Channel
from products.models import Product
from leads.models import (
    Lead,
    LeadStatus,
    Enrollment,
    Installment,
    PaymentTransaction,
    GSTTreatment,
    PaymentPlan,
    InstallmentMethod,
    InstallmentStatus,
    PaymentMethod,
    PaymentTransactionStatus,
    TelecallerLeadSetup,
)
from leads.services_enrollment import (
    can_change_to_enrolled,
    validate_status_transition,
    create_or_update_enrollment,
    record_payment,
    update_installment_schedule,
)
from leads.allocation_service import (
    validate_channel_allocation_percentages,
    save_branch_channel_allocation,
)
from fb_leads.models import FacebookAccount, FacebookPage, FacebookLead
from fb_leads.crm import branch_for


class EnrollmentAndMasterFlowTestCase(TestCase):
    def setUp(self):
        # Create or retrieve Branches
        self.branch1, _ = Branch.objects.get_or_create(name="T Nagar", defaults={"status": "Active"})
        self.branch2, _ = Branch.objects.get_or_create(name="Anna Nagar", defaults={"status": "Active"})

        # Create Users
        self.admin, _ = User.objects.get_or_create(
            username="admin_user_test",
            defaults={"email": "admin_test@test.com", "role": UserRole.ADMIN}
        )
        self.admin.set_password("pass")
        self.admin.save()

        self.counselor1, _ = User.objects.get_or_create(
            username="counselor_1_test",
            defaults={"email": "counselor1_test@test.com", "role": UserRole.COUNSELOR, "branch": self.branch1}
        )
        self.counselor2, _ = User.objects.get_or_create(
            username="counselor_2_test",
            defaults={"email": "counselor2_test@test.com", "role": UserRole.COUNSELOR, "branch": self.branch2}
        )
        self.telecaller, _ = User.objects.get_or_create(
            username="telecaller_1_test",
            defaults={"email": "telecaller1_test@test.com", "role": UserRole.TELECALLER, "branch": self.branch1}
        )
        self.receptionist, _ = User.objects.get_or_create(
            username="receptionist_1_test",
            defaults={"email": "receptionist1_test@test.com", "role": UserRole.RECEPTIONIST, "branch": self.branch1}
        )

        # Create Product & Channel
        self.product, _ = Product.objects.get_or_create(
            name="Full Stack AI Python Test",
            defaults={"price": Decimal('30000.00'), "status": "Active"}
        )
        self.channel, _ = Channel.objects.get_or_create(
            name="Facebook Test",
            defaults={"status": "Active"}
        )

        # Create Lead
        self.lead = Lead.objects.create(
            name="Rahul Sharma",
            phone="9876543210",
            email="rahul@example.com",
            branch=self.branch1,
            assigned_counselor=self.counselor1,
            product=self.product,
            status=LeadStatus.NEW,
        )

    def test_gst_inclusive_vs_exclusive_decimal_arithmetic(self):
        """
        Verify GST formulas strictly use pure Decimal arithmetic and produce exact values.
        """
        base_fee = Decimal('25000.00')
        tax_rate = Decimal('18.00')

        # 1. EXCLUSIVE OF GST: Base + 18% Tax = Total
        ex_res = Enrollment.calculate_gst_breakdown(base_fee, GSTTreatment.EXCLUSIVE, tax_rate)
        self.assertEqual(ex_res['taxable_amount'], Decimal('25000.00'))
        self.assertEqual(ex_res['tax_amount'], Decimal('4500.00'))
        self.assertEqual(ex_res['total_payable'], Decimal('29500.00'))
        self.assertEqual(ex_res['taxable_amount'] + ex_res['tax_amount'], ex_res['total_payable'])

        # 2. INCLUSIVE OF GST: Base already contains 18% Tax -> taxable = base / 1.18
        inc_res = Enrollment.calculate_gst_breakdown(base_fee, GSTTreatment.INCLUSIVE, tax_rate)
        # 25000 / 1.18 = 21186.440677... -> 21186.44
        self.assertEqual(inc_res['taxable_amount'], Decimal('21186.44'))
        self.assertEqual(inc_res['tax_amount'], Decimal('3813.56'))
        self.assertEqual(inc_res['total_payable'], Decimal('25000.00'))
        self.assertEqual(inc_res['taxable_amount'] + inc_res['tax_amount'], inc_res['total_payable'])

    def test_automatic_installment_rounding_absorbed_by_final_installment(self):
        """
        Verify that dividing a total payable by N installments absorbs any rounding cents
        on the final installment so the sum of installments strictly equals total_payable.
        """
        # Create enrollment with total payable = 10000 (say 3 installments: 3333.33, 3333.33, 3333.34)
        data = {
            'student_name': 'Rahul Sharma',
            'student_phone': '9876543210',
            'base_course_fee': Decimal('10000.00'),
            'gst_treatment': GSTTreatment.INCLUSIVE,
            'tax_rate': Decimal('18.00'),
            'payment_plan': PaymentPlan.SPLIT_PAYMENT,
            'installment_method': InstallmentMethod.AUTOMATIC,
            'installment_count': 3,
            'first_installment_date': timezone.localdate(),
        }

        enrollment = create_or_update_enrollment(self.lead, self.counselor1, data)
        installments = list(enrollment.installments.all().order_by('installment_number'))
        self.assertEqual(len(installments), 3)

        self.assertEqual(installments[0].scheduled_amount, Decimal('3333.33'))
        self.assertEqual(installments[1].scheduled_amount, Decimal('3333.33'))
        # 3rd installment must absorb the 0.01 remainder: 3333.34
        self.assertEqual(installments[2].scheduled_amount, Decimal('3333.34'))

        total_scheduled = sum(i.scheduled_amount for i in installments)
        self.assertEqual(total_scheduled, enrollment.total_payable)
        self.assertEqual(total_scheduled, Decimal('10000.00'))

    def test_api_calculate_gst_preview_endpoint_exclusive_and_inclusive(self):
        """
        Verify real-time JSON API endpoint /enrollments/api/calculate-gst/
        calculates correct breakdown and installment schedule for both GST treatments.
        """
        client = Client()
        client.force_login(self.counselor1)

        # 1. Exclusive of GST: Fee = 25000, 18% tax, 2 installments
        res = client.get(
            reverse('api_calculate_gst_preview'),
            {'base_course_fee': '25000.00', 'gst_treatment': 'EXCLUSIVE', 'tax_rate': '18.00', 'installment_count': '2'}
        )
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertTrue(data['success'])
        self.assertEqual(data['base_course_fee'], '25000.00')
        self.assertEqual(data['taxable_amount'], '25000.00')
        self.assertEqual(data['tax_amount'], '4500.00')
        self.assertEqual(data['total_payable'], '29500.00')
        self.assertEqual(len(data['installments_preview']), 2)
        self.assertEqual(data['installments_preview'][0]['amount'], '14750.00')
        self.assertEqual(data['installments_preview'][1]['amount'], '14750.00')

        # 2. Inclusive of GST: Fee = 25000, 18% tax, 2 installments
        res = client.get(
            reverse('api_calculate_gst_preview'),
            {'base_course_fee': '25000.00', 'gst_treatment': 'INCLUSIVE', 'tax_rate': '18.00', 'installment_count': '2'}
        )
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertTrue(data['success'])
        self.assertEqual(data['base_course_fee'], '25000.00')
        self.assertEqual(data['taxable_amount'], '21186.44')
        self.assertEqual(data['tax_amount'], '3813.56')
        self.assertEqual(data['total_payable'], '25000.00')
        self.assertEqual(len(data['installments_preview']), 2)
        self.assertEqual(data['installments_preview'][0]['amount'], '12500.00')
        self.assertEqual(data['installments_preview'][1]['amount'], '12500.00')

    def test_api_calculate_gst_preview_odd_installment_rounding(self):
        """
        Verify that 3 installments on a 25000 total cleanly absorbs the 0.01 discrepancy
        in the final installment (8333.33 + 8333.33 + 8333.34 = 25000.00).
        """
        client = Client()
        client.force_login(self.counselor1)

        res = client.get(
            reverse('api_calculate_gst_preview'),
            {'base_course_fee': '25000.00', 'gst_treatment': 'INCLUSIVE', 'tax_rate': '18.00', 'installment_count': '3'}
        )
        self.assertEqual(res.status_code, 200)
        data = res.json()
        insts = data['installments_preview']
        self.assertEqual(len(insts), 3)
        self.assertEqual(insts[0]['amount'], '8333.33')
        self.assertEqual(insts[1]['amount'], '8333.33')
        self.assertEqual(insts[2]['amount'], '8333.34')
        total_sum = sum(Decimal(i['amount']) for i in insts)
        self.assertEqual(total_sum, Decimal('25000.00'))

    def test_api_calculate_gst_preview_custom_rate_and_edge_cases(self):
        """
        Verify configurable tax rates (e.g. 12%, 5%) and robust edge cases (zero, negative, invalid).
        """
        client = Client()
        client.force_login(self.counselor1)

        # 12% GST Exclusive on 20000
        res = client.get(
            reverse('api_calculate_gst_preview'),
            {'base_course_fee': '20000.00', 'gst_treatment': 'EXCLUSIVE', 'tax_rate': '12.00'}
        )
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data['taxable_amount'], '20000.00')
        self.assertEqual(data['tax_amount'], '2400.00')
        self.assertEqual(data['total_payable'], '22400.00')

        # Negative fee clamped to 0.00
        res = client.get(
            reverse('api_calculate_gst_preview'),
            {'base_course_fee': '-500.00', 'gst_treatment': 'EXCLUSIVE', 'tax_rate': '18.00'}
        )
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data['base_course_fee'], '0.00')
        self.assertEqual(data['total_payable'], '0.00')

        # Invalid string non-numeric input returns 400
        res = client.get(
            reverse('api_calculate_gst_preview'),
            {'base_course_fee': 'invalid_string', 'gst_treatment': 'EXCLUSIVE'}
        )
        self.assertEqual(res.status_code, 400)

    def test_status_permission_enrolled_enforcement(self):
        """
        Only assigned Counselor, Sales Head, Branch Head, or Admin can mark lead as ENROLLED.
        Telecallers and Receptionists are strictly denied.
        """
        # 1. Assigned counselor -> Allowed
        self.assertTrue(can_change_to_enrolled(self.counselor1, self.lead))
        validate_status_transition(self.counselor1, self.lead, LeadStatus.ENROLLED)

        # 2. Different counselor -> Denied
        self.assertFalse(can_change_to_enrolled(self.counselor2, self.lead))
        with self.assertRaises(PermissionDenied):
            validate_status_transition(self.counselor2, self.lead, LeadStatus.ENROLLED)

        # 3. Telecaller -> Denied
        self.assertFalse(can_change_to_enrolled(self.telecaller, self.lead))
        with self.assertRaises(PermissionDenied):
            validate_status_transition(self.telecaller, self.lead, LeadStatus.ENROLLED)

        # 4. Receptionist -> Denied
        self.assertFalse(can_change_to_enrolled(self.receptionist, self.lead))
        with self.assertRaises(PermissionDenied):
            validate_status_transition(self.receptionist, self.lead, LeadStatus.ENROLLED)

        # 5. Admin -> Allowed
        self.assertTrue(can_change_to_enrolled(self.admin, self.lead))
        validate_status_transition(self.admin, self.lead, LeadStatus.ENROLLED)

    def test_payment_recording_and_receipt_generation(self):
        """
        Recording payment generates a unique receipt number, updates balances,
        and rebalances installment statuses.
        """
        data = {
            'student_name': 'Rahul Sharma',
            'student_phone': '9876543210',
            'base_course_fee': Decimal('20000.00'),
            'gst_treatment': GSTTreatment.EXCLUSIVE,
            'tax_rate': Decimal('18.00'),
            'payment_plan': PaymentPlan.SPLIT_PAYMENT,
            'installment_method': InstallmentMethod.AUTOMATIC,
            'installment_count': 2,
            'first_installment_date': timezone.localdate(),
        }
        # Total payable = 20000 + 3600 = 23600. 2 installments of 11800 each.
        enrollment = create_or_update_enrollment(self.lead, self.admin, data)
        self.assertEqual(enrollment.total_payable, Decimal('23600.00'))
        self.assertEqual(enrollment.outstanding_balance, Decimal('23600.00'))

        # Pay first installment: 11800
        pay_data = {
            'amount': Decimal('11800.00'),
            'payment_method': PaymentMethod.UPI,
            'transaction_reference': 'UPI-REF-998877',
            'notes': 'First installment received',
        }
        txn = record_payment(enrollment, self.admin, pay_data)

        self.assertIsNotNone(txn.receipt_number)
        self.assertTrue(txn.receipt_number.startswith('REC-'))
        self.assertEqual(txn.amount, Decimal('11800.00'))

        enrollment.refresh_from_db()
        self.assertEqual(enrollment.total_paid, Decimal('11800.00'))
        self.assertEqual(enrollment.outstanding_balance, Decimal('11800.00'))

        # Check installments
        inst1 = enrollment.installments.get(installment_number=1)
        self.assertEqual(inst1.status, InstallmentStatus.PAID)
        self.assertEqual(inst1.amount_paid, Decimal('11800.00'))
        self.assertEqual(inst1.remaining_balance, Decimal('0.00'))

        inst2 = enrollment.installments.get(installment_number=2)
        self.assertEqual(inst2.amount_paid, Decimal('0.00'))
        self.assertEqual(inst2.remaining_balance, Decimal('11800.00'))

        # Test receipt view
        client = Client()
        client.force_login(self.admin)
        receipt_url = reverse('enrollment_receipt_view', args=[txn.id])
        resp = client.get(receipt_url)
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, txn.receipt_number)
        self.assertContains(resp, "Rahul Sharma")

    def test_facebook_multi_account_and_page_branch_routing(self):
        """
        Verify multi-account and multi-page Facebook models and automatic branch routing.
        """
        # 1. Create Facebook Account
        fb_acc = FacebookAccount.objects.create(
            account_name="TechPanda Ads Account",
            access_token="mock_token_123",
            connected_by=self.admin,
        )

        # 2. Create Facebook Page associated with Branch 2 (Anna Nagar)
        fb_page = FacebookPage.objects.create(
            account=fb_acc,
            page_id="fb_page_888",
            page_name="TechPanda Anna Nagar Page",
            branch=self.branch2,
            page_access_token="mock_page_token",
        )

        # 3. Create Facebook Lead from this page
        fb_lead = FacebookLead.objects.create(
            leadgen_id="leadgen_777666",
            full_name="Pooja Patel",
            phone="9123456789",
            page_id="fb_page_888",
            fb_page=fb_page,
            account=fb_acc,
        )

        # 4. Verify branch_for returns the branch explicitly assigned to the page
        resolved_branch = branch_for(fb_lead)
        self.assertEqual(resolved_branch, self.branch2)

    def test_branch_channel_allocation_percentages(self):
        """
        Verify branch settings channel percentage allocation enforces sum == 100%.
        """
        # Valid: 60% + 40% = 100%
        valid_allocations = [
            {'telecaller_id': self.telecaller.id, 'percentage': Decimal('60.00'), 'status': 'Active'},
        ]
        # Only 1 telecaller with 60% -> Invalid (must equal 100%)
        with self.assertRaises(ValidationError):
            validate_channel_allocation_percentages(valid_allocations)

        # Valid 100% allocation
        valid_100 = [
            {'telecaller_id': self.telecaller.id, 'percentage': Decimal('100.00'), 'status': 'Active'},
        ]
        validate_channel_allocation_percentages(valid_100)
        save_branch_channel_allocation(self.branch1, self.channel, valid_100)

        saved = TelecallerLeadSetup.objects.get(branch=self.branch1, channel=self.channel, telecaller=self.telecaller)
        self.assertEqual(saved.assignment_percentage, 100)

    def test_enrollment_create_or_edit_get_view(self):
        """
        Verify that GET /leads/<id>/enroll/ renders correctly without FieldError or VariableDoesNotExist
        even when lead.product is None and lead.assigned_counselor is None.
        """
        # Test 1: lead with product
        client = Client()
        client.force_login(self.admin)
        url = reverse('lead_enroll', args=[self.lead.id])
        resp = client.get(url)
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "Student Enrollment & Fee Setup")
        self.assertContains(resp, self.product.name)

        # Test 2: lead with product=None and assigned_counselor=None
        lead_no_prod = Lead.objects.create(
            name="No Product Student",
            phone="9000000000",
            branch=self.branch1,
            product=None,
            assigned_counselor=None,
        )
        url_no_prod = reverse('lead_enroll', args=[lead_no_prod.id])
        resp_no_prod = client.get(url_no_prod)
        self.assertEqual(resp_no_prod.status_code, 200)
        self.assertContains(resp_no_prod, "Student Enrollment & Fee Setup")
        self.assertContains(resp_no_prod, "25000.00")

    def test_enrollment_post_with_empty_product_id(self):
        """
        Verify that POST /leads/<id>/enroll/ succeeds without ValueError when product_id is empty string ''.
        """
        client = Client()
        client.force_login(self.admin)
        url = reverse('lead_enroll', args=[self.lead.id])
        post_data = {
            'student_name': 'Tamil Selvan',
            'student_phone': '09150688755',
            'student_email': 'tamil@example.com',
            'product_id': '',  # Empty product
            'branch_id': str(self.branch1.id),
            'base_course_fee': '25000.00',
            'gst_treatment': 'EXCLUSIVE',
            'tax_rate': '18',
            'payment_plan': 'SPLIT_PAYMENT',
            'installment_count': '6',
            'first_installment_date': '2026-10-13',
            'notes': 'Test enrollment without selecting product',
        }
        resp = client.post(url, post_data)
        self.assertEqual(resp.status_code, 302)  # Redirects on success

        # Verify lead status is now ENROLLED
        self.lead.refresh_from_db()
        self.assertEqual(self.lead.status, LeadStatus.ENROLLED)

        # Verify enrollment and installments created
        enrollment = self.lead.enrollment
        self.assertIsNotNone(enrollment)
        self.assertEqual(enrollment.total_payable, Decimal('29500.00'))  # 25000 + 18% = 29500
        self.assertEqual(enrollment.installments.count(), 6)

    def test_enrollment_receipt_html_and_pdf_generation(self):
        """
        Verify HTML receipt rendering, direct PDF generation endpoint,
        ?download=pdf query parameter, and role authorization checks.
        """
        # Create enrollment & transaction
        data = {
            'student_name': 'Kavya Raman',
            'student_phone': '9876543219',
            'student_email': 'kavya@example.com',
            'base_course_fee': Decimal('30000.00'),
            'gst_treatment': GSTTreatment.EXCLUSIVE,
            'tax_rate': Decimal('18.00'),
            'payment_plan': PaymentPlan.SPLIT_PAYMENT,
            'installment_method': InstallmentMethod.AUTOMATIC,
            'installment_count': 3,
            'first_installment_date': timezone.localdate(),
        }
        enrollment = create_or_update_enrollment(self.lead, self.admin, data)
        txn = record_payment(enrollment, self.admin, {
            'amount': Decimal('11800.00'),
            'payment_method': PaymentMethod.UPI,
            'transaction_reference': 'UPI-TEST-12345',
        })

        client = Client()
        client.force_login(self.admin)

        # 1. HTML receipt view
        html_url = reverse('enrollment_receipt_view', args=[txn.id])
        resp_html = client.get(html_url)
        self.assertEqual(resp_html.status_code, 200)
        self.assertContains(resp_html, txn.receipt_number)
        self.assertContains(resp_html, "Official Student Fee Receipt")
        self.assertContains(resp_html, "Kavya Raman")
        self.assertContains(resp_html, "Tamper-Evident Digital Verification")
        self.assertContains(resp_html, "TP-VRF-")

        # 2. Direct PDF endpoint
        pdf_url = reverse('enrollment_receipt_pdf_view', args=[txn.id])
        resp_pdf = client.get(pdf_url)
        self.assertEqual(resp_pdf.status_code, 200)
        self.assertEqual(resp_pdf['Content-Type'], 'application/pdf')
        self.assertTrue(resp_pdf.content.startswith(b'%PDF'))
        self.assertIn(f'TechPanda_Receipt_{txn.receipt_number}.pdf', resp_pdf['Content-Disposition'])

        # 3. Query param ?download=pdf alias
        resp_alias = client.get(f"{html_url}?download=pdf")
        self.assertEqual(resp_alias.status_code, 200)
        self.assertEqual(resp_alias['Content-Type'], 'application/pdf')
        self.assertTrue(resp_alias.content.startswith(b'%PDF'))

        # 4. Telecaller unauthorized access check
        client.force_login(self.telecaller)
        resp_unauth = client.get(html_url)
        self.assertEqual(resp_unauth.status_code, 403)



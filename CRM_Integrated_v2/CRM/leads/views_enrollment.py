import io

import hashlib

import json

import base64

import qrcode

import qrcode.image.svg

from decimal import Decimal, ROUND_HALF_UP

from django.conf import settings

from django.shortcuts import render, get_object_or_404, redirect

from django.contrib.auth.decorators import login_required

from django.views.decorators.http import require_POST, require_GET

from django.http import JsonResponse, HttpResponse

from django.contrib import messages

from django.core.exceptions import PermissionDenied, ValidationError

from django.core.paginator import Paginator

from django.db.models import Sum, Q, Count

from django.urls import reverse

from django.template.loader import get_template

from django.utils import timezone

from xhtml2pdf import pisa

import os

from .constants import TECHPANDA_INVOICE_CONFIG

from .utils_currency import amount_to_inr_words



from accounts.models import User, UserRole

from branches.models import Branch

from products.models import Product

from activities.utils import log_activity

from .models import (

    Lead,

    LeadStatus,

    Enrollment,

    Installment,

    PaymentTransaction,

    InstallmentScheduleHistory,

    GSTTreatment,

    PaymentPlan,

    InstallmentMethod,

    EnrollmentStatus,

    EnrollmentPaymentStatus,

    InstallmentStatus,

    PaymentMethod,

    PaymentTransactionStatus,

)

from .services_enrollment import (

    can_change_to_enrolled,

    create_or_update_enrollment,

    record_payment,

    resubmit_payment,

    update_installment_schedule,

    send_installment_reminders,

)





@login_required

def admin_enrolled_students(request):

    """

    Central Admin & Management view for all Enrolled Students.

    Tracks academic onboarding, GST-compliant financial accounting,

    and installment schedules.

    """

    user = request.user

    if not (user.is_admin_user or user.is_sales_head_user or user.is_branch_head_user or user.is_branch_admin_user):

        raise PermissionDenied("Only Admin, Sales Head, or Branch Head can view Enrolled Students list.")



    enrollments_qs = Enrollment.objects.select_related(

        'lead', 'product', 'branch', 'assigned_counselor'

    ).prefetch_related('installments', 'payments').order_by('-enrollment_date', '-id')



    # Branch restriction for Branch Head

    if (user.is_branch_head_user or user.is_branch_admin_user) and user.branch:

        enrollments_qs = enrollments_qs.filter(branch=user.branch)



    # Filtering

    q = request.GET.get('q', '').strip()

    if q:

        enrollments_qs = enrollments_qs.filter(

            Q(student_name__icontains=q)

            | Q(student_phone__icontains=q)

            | Q(student_email__icontains=q)

            | Q(enrollment_number__icontains=q)

        )



    branch_id = request.GET.get('branch')

    if branch_id and (user.is_admin_user or user.is_sales_head_user):

        enrollments_qs = enrollments_qs.filter(branch_id=branch_id)



    counselor_id = request.GET.get('counselor')

    if counselor_id:

        enrollments_qs = enrollments_qs.filter(assigned_counselor_id=counselor_id)



    product_id = request.GET.get('product')

    if product_id:

        enrollments_qs = enrollments_qs.filter(product_id=product_id)



    payment_status = request.GET.get('payment_status')

    if payment_status:

        enrollments_qs = enrollments_qs.filter(payment_status=payment_status)



    # Aggregate Financial KPIs

    total_enrolled = enrollments_qs.count()

    total_receivable = enrollments_qs.aggregate(s=Sum('total_payable'))['s'] or Decimal('0.00')

    total_collected = enrollments_qs.aggregate(s=Sum('total_paid'))['s'] or Decimal('0.00')

    total_outstanding = enrollments_qs.aggregate(s=Sum('outstanding_balance'))['s'] or Decimal('0.00')

    

    overdue_count = Installment.objects.filter(

        enrollment__in=enrollments_qs,

        status=InstallmentStatus.OVERDUE

    ).count()



    paginator = Paginator(enrollments_qs, 25)

    page_obj = paginator.get_page(request.GET.get('page'))



    branches = Branch.objects.filter(status=Branch.Status.ACTIVE).order_by('name')

    counselors = User.objects.filter(role=UserRole.COUNSELOR, is_active=True).order_by('first_name', 'username')

    if (user.is_branch_head_user or user.is_branch_admin_user) and user.branch:

        counselors = counselors.filter(branch=user.branch)

    products = Product.objects.filter(status=Product.Status.ACTIVE).order_by('name')



    return render(request, 'leads/enrolled_students.html', {

        'page_obj': page_obj,

        'total_enrolled': total_enrolled,

        'total_receivable': total_receivable,

        'total_collected': total_collected,

        'total_outstanding': total_outstanding,

        'overdue_count': overdue_count,

        'branches': branches,

        'counselors': counselors,

        'products': products,

        'payment_statuses': EnrollmentPaymentStatus.choices,

        'selected_branch': branch_id,

        'selected_counselor': counselor_id,

        'selected_product': product_id,

        'selected_payment_status': payment_status,

        'search_query': q,

        'is_counselor_view': False,

    })





@login_required

def counselor_enrolled_students(request):

    """

    Counselor portal view for their own enrolled students.

    """

    user = request.user

    if user.role != UserRole.COUNSELOR and not (user.is_admin_user or user.is_sales_head_user):

        raise PermissionDenied("Only Counselors can access this view.")



    enrollments_qs = Enrollment.objects.filter(

        assigned_counselor=user

    ).select_related(

        'lead', 'product', 'branch'

    ).prefetch_related('installments', 'payments').order_by('-enrollment_date', '-id')



    q = request.GET.get('q', '').strip()

    if q:

        enrollments_qs = enrollments_qs.filter(

            Q(student_name__icontains=q)

            | Q(student_phone__icontains=q)

            | Q(student_email__icontains=q)

            | Q(enrollment_number__icontains=q)

        )



    payment_status = request.GET.get('payment_status')

    if payment_status:

        enrollments_qs = enrollments_qs.filter(payment_status=payment_status)



    total_enrolled = enrollments_qs.count()

    total_receivable = enrollments_qs.aggregate(s=Sum('total_payable'))['s'] or Decimal('0.00')

    total_collected = enrollments_qs.aggregate(s=Sum('total_paid'))['s'] or Decimal('0.00')

    total_outstanding = enrollments_qs.aggregate(s=Sum('outstanding_balance'))['s'] or Decimal('0.00')



    paginator = Paginator(enrollments_qs, 25)

    page_obj = paginator.get_page(request.GET.get('page'))



    return render(request, 'leads/enrolled_students.html', {

        'page_obj': page_obj,

        'total_enrolled': total_enrolled,

        'total_receivable': total_receivable,

        'total_collected': total_collected,

        'total_outstanding': total_outstanding,

        'payment_statuses': EnrollmentPaymentStatus.choices,

        'selected_payment_status': payment_status,

        'search_query': q,

        'is_counselor_view': True,

    })





@login_required

@require_GET

def api_calculate_gst_preview(request):

    """

    Real-time JSON endpoint to calculate GST breakdown on the client.

    Ensures pure Decimal arithmetic is used for financial honesty.

    Optionally computes live installment schedule preview.

    """

    raw_fee = request.GET.get('base_course_fee', '0')

    gst_treatment = request.GET.get('gst_treatment', GSTTreatment.EXCLUSIVE)

    raw_rate = request.GET.get('tax_rate')



    if gst_treatment not in [GSTTreatment.EXCLUSIVE, GSTTreatment.INCLUSIVE]:

        gst_treatment = GSTTreatment.EXCLUSIVE



    try:

        base_fee = Decimal(str(raw_fee)).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)

        if base_fee < Decimal('0.00'):

            base_fee = Decimal('0.00')

    except Exception:

        return JsonResponse({'success': False, 'error': 'Invalid numerical fee input.'}, status=400)



    try:

        if raw_rate is not None and str(raw_rate).strip() != '':

            tax_rate = Decimal(str(raw_rate)).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)

            if tax_rate < Decimal('0.00'):

                tax_rate = Decimal('0.00')

        else:

            tax_rate = Enrollment.get_default_gst_rate()

    except Exception:

        tax_rate = Enrollment.get_default_gst_rate()



    breakdown = Enrollment.calculate_gst_breakdown(base_fee, gst_treatment, tax_rate)



    # Optional installment schedule preview

    installment_count_raw = request.GET.get('installment_count')

    first_due_date_raw = request.GET.get('first_installment_date')

    installments_preview = []

    if installment_count_raw and str(installment_count_raw).isdigit():

        inst_count = max(1, int(installment_count_raw))

        schedule = Enrollment.calculate_installment_breakdown(

            breakdown['total_payable'],

            inst_count,

            start_date=first_due_date_raw

        )

        for item in schedule:

            installments_preview.append({

                'number': item['installment_number'],

                'amount': str(item['amount']),

                'due_date': item['due_date'],

                'formatted_due_date': item['formatted_due_date'],

            })



    return JsonResponse({

        'success': True,

        'base_course_fee': str(breakdown['base_course_fee']),

        'gst_treatment': breakdown['gst_treatment'],

        'tax_rate': str(breakdown['tax_rate']),

        'taxable_amount': str(breakdown['taxable_amount']),

        'tax_amount': str(breakdown['tax_amount']),

        'total_payable': str(breakdown['total_payable']),

        'installments_preview': installments_preview,

    })





@login_required

@require_GET

def api_enrollment_details(request, enrollment_id):

    """

    Returns complete enrollment record with installment plan and payment history for UI modals.

    """

    enrollment = get_object_or_404(

        Enrollment.objects.select_related('lead', 'product', 'branch', 'assigned_counselor'),

        id=enrollment_id

    )



    # Permission check

    if not (request.user.is_admin_user or request.user.is_sales_head_user or request.user.role == UserRole.ACCOUNTANT):

        if (request.user.is_branch_head_user or request.user.is_branch_admin_user) and enrollment.branch != request.user.branch:

            raise PermissionDenied("Access denied.")

        if request.user.role == UserRole.COUNSELOR and enrollment.assigned_counselor != request.user:

            raise PermissionDenied("Access denied.")



    installments_data = []

    for inst in enrollment.installments.all().order_by('installment_number'):

        installments_data.append({

            'id': inst.id,

            'number': inst.installment_number,

            'scheduled_amount': str(inst.scheduled_amount),

            'amount_paid': str(inst.amount_paid),

            'remaining_balance': str(inst.remaining_balance),

            'due_date': inst.due_date.strftime('%Y-%m-%d'),

            'status': inst.status,

            'paid_date': inst.paid_date.strftime('%Y-%m-%d') if inst.paid_date else None,

        })



    payments_data = []

    for pay in enrollment.payments.all().order_by('-payment_date', '-id'):

        can_resubmit = bool(

            pay.is_rejected and (getattr(request.user, 'is_admin_user', False) or getattr(request.user, 'is_superuser', False) or pay.recorded_by_id == request.user.id)

        )

        payments_data.append({

            'id': pay.id,

            'receipt_number': pay.receipt_number,

            'amount': str(pay.amount),

            'payment_date': pay.payment_date.strftime('%Y-%m-%d %H:%M'),

            'payment_method': pay.payment_method,

            'transaction_reference': pay.transaction_reference,

            'status': pay.status,

            'is_approved': pay.is_approved,

            'is_pending_verification': pay.is_pending_verification,

            'is_rejected': pay.is_rejected,

            'can_resubmit': can_resubmit,

            'rejection_comment': pay.rejection_comment,

            'resubmission_count': pay.resubmission_count,

            'payment_proof_url': reverse('accountant_payment_proof_view', args=[pay.id]) if pay.payment_proof else None,

            'received_by': pay.recorded_by.get_full_name() or pay.recorded_by.username if pay.recorded_by else 'System',

            'recorded_by_id': pay.recorded_by_id,

            'reviewed_by': pay.reviewed_by.get_full_name() or pay.reviewed_by.username if pay.reviewed_by else None,

            'reviewed_at': pay.reviewed_at.strftime('%Y-%m-%d %H:%M') if pay.reviewed_at else None,

        })



    return JsonResponse({

        'success': True,

        'enrollment': {

            'id': enrollment.id,

            'enrollment_number': enrollment.enrollment_number,

            'student_name': enrollment.student_name,

            'student_phone': enrollment.student_phone,

            'student_email': enrollment.student_email,

            'product_name': enrollment.product.name if enrollment.product else '—',

            'branch_name': enrollment.branch.name if enrollment.branch else '—',

            'counselor_name': enrollment.assigned_counselor.get_full_name() or enrollment.assigned_counselor.username if enrollment.assigned_counselor else 'Unassigned',

            'enrollment_date': enrollment.enrollment_date.strftime('%Y-%m-%d'),

            'base_course_fee': str(enrollment.base_course_fee),

            'gst_treatment': enrollment.gst_treatment,

            'tax_rate': str(enrollment.tax_rate),

            'taxable_amount': str(enrollment.taxable_amount),

            'tax_amount': str(enrollment.tax_amount),

            'total_payable': str(enrollment.total_payable),

            'total_paid': str(enrollment.total_paid),

            'outstanding_balance': str(enrollment.outstanding_balance),

            'payment_plan': enrollment.payment_plan,

            'payment_status': enrollment.payment_status,

            'enrollment_status': enrollment.enrollment_status,

        },

        'installments': installments_data,

        'payments': payments_data,

    })





@login_required

def enrollment_create_or_edit(request, lead_id):

    """

    Processes Student Enrollment for a given CRM Lead.

    Enforces that only the assigned counselor or authorized management can complete enrollment.

    """

    lead = get_object_or_404(Lead, id=lead_id)



    if not can_change_to_enrolled(request.user, lead):

        messages.error(request, "Permission Denied: Only the assigned Counselor or Management can enroll this student.")

        return redirect('admin_lead_detail' if request.user.is_admin_user else 'counselor_lead_detail', pk=lead.id)



    enrollment = getattr(lead, 'enrollment', None)



    if request.method == 'POST':

        raw_product_id = (request.POST.get('product_id') or '').strip()

        raw_branch_id = (request.POST.get('branch_id') or '').strip()



        product = None

        if raw_product_id.isdigit():

            product = Product.objects.filter(id=int(raw_product_id)).first()

        if not product:

            product = lead.product



        branch = None

        if raw_branch_id.isdigit():

            branch = Branch.objects.filter(id=int(raw_branch_id)).first()

        if not branch:

            branch = lead.branch



        first_date_raw = (request.POST.get('first_installment_date') or '').strip()

        try:

            first_installment_date = timezone.datetime.strptime(first_date_raw, '%Y-%m-%d').date() if first_date_raw else timezone.localdate()

        except (ValueError, TypeError):

            first_installment_date = timezone.localdate()



        data = {

            'student_name': request.POST.get('student_name', lead.name),

            'student_phone': request.POST.get('student_phone', lead.phone),

            'student_email': request.POST.get('student_email', lead.email),

            'product': product,

            'branch': branch,

            'base_course_fee': request.POST.get('base_course_fee'),

            'gst_treatment': request.POST.get('gst_treatment'),

            'tax_rate': request.POST.get('tax_rate', '18'),

            'payment_plan': request.POST.get('payment_plan', PaymentPlan.FULL_PAYMENT),

            'installment_method': request.POST.get('installment_method', InstallmentMethod.AUTOMATIC),

            'installment_count': request.POST.get('installment_count', '2'),

            'first_installment_date': first_installment_date,

            'notes': request.POST.get('notes', ''),

        }



        # Check for manual installments

        if data['payment_plan'] == PaymentPlan.SPLIT_PAYMENT and data['installment_method'] == InstallmentMethod.MANUAL:

            manual_installments = []

            inst_amts = request.POST.getlist('manual_amount[]')

            inst_dates = request.POST.getlist('manual_date[]')

            for i in range(len(inst_amts)):

                if inst_amts[i] and inst_dates[i]:

                    manual_installments.append({

                        'number': i + 1,

                        'amount': inst_amts[i],

                        'due_date': inst_dates[i],

                    })

            data['manual_installments'] = manual_installments



        try:

            saved_enrollment = create_or_update_enrollment(lead, request.user, data)

            messages.success(request, f"Enrollment #{saved_enrollment.enrollment_number} successfully registered for {saved_enrollment.student_name}.")

            return redirect('counselor_enrolled_students' if request.user.role == UserRole.COUNSELOR else 'admin_enrolled_students')

        except (ValidationError, PermissionDenied, Exception) as exc:

            messages.error(request, f"Enrollment failed: {exc}")



    # GET: render enrollment form

    products = Product.objects.filter(status=Product.Status.ACTIVE).order_by('name')

    branches = Branch.objects.filter(status=Branch.Status.ACTIVE).order_by('name')



    return render(request, 'leads/enrollment_form.html', {

        'lead': lead,

        'enrollment': enrollment,

        'products': products,

        'branches': branches,

        'gst_treatments': GSTTreatment.choices,

        'payment_plans': PaymentPlan.choices,

        'installment_methods': InstallmentMethod.choices,

        'default_gst_rate': Enrollment.get_default_gst_rate(),

    })





@login_required

@require_POST

def enrollment_record_payment(request, enrollment_id):

    """

    Records a payment transaction against an Enrollment.

    Payments recorded in the web interface enter PENDING_VERIFICATION and require proof for online methods.

    """

    enrollment = get_object_or_404(Enrollment, id=enrollment_id)



    redirect_view = 'counselor_enrolled_students' if request.user.role == UserRole.COUNSELOR else 'admin_enrolled_students'



    if not can_change_to_enrolled(request.user, enrollment.lead):

        messages.error(request, "Permission Denied: You do not have authority to collect payments for this student.")

        return redirect(redirect_view)



    try:

        raw_amt = request.POST.get('amount')

        amount = Decimal(str(raw_amt)).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)

    except Exception:

        messages.error(request, "Invalid payment amount.")

        return redirect(redirect_view)



    if amount <= Decimal('0.00'):

        messages.error(request, "Payment amount must be greater than zero.")

        return redirect(redirect_view)



    payment_proof = request.FILES.get('payment_proof')

    installment_id = request.POST.get('installment_id')



    data = {

        'amount': amount,

        'payment_method': request.POST.get('payment_method', PaymentMethod.UPI),

        'transaction_reference': request.POST.get('transaction_reference', '').strip(),

        'notes': request.POST.get('notes', '').strip(),

        'installment_id': installment_id,

        'payment_proof': payment_proof,

        'auto_approve': False,

    }



    try:

        txn = record_payment(enrollment, request.user, data)

        messages.info(

            request,

            f"Payment of ₹{txn.amount} via {txn.payment_method} submitted for Accountant verification (Receipt #{txn.receipt_number}). It will be credited to student account once verified."

        )

    except ValidationError as ve:

        err_msg = ", ".join(ve.messages) if hasattr(ve, 'messages') else str(ve)

        messages.error(request, f"Payment submission failed: {err_msg}")

    except Exception as exc:

        messages.error(request, f"Payment collection failed: {exc}")



    return redirect(redirect_view)





@login_required

@require_POST

def enrollment_resubmit_payment(request, payment_id):

    """

    Counselor action to correct and resubmit a rejected payment transaction with optional new proof.

    """

    payment = get_object_or_404(PaymentTransaction, id=payment_id)



    # Strict isolation: Only the counselor who originally added this payment (recorded_by) or an administrator can resubmit

    if not (getattr(request.user, 'is_admin_user', False) or getattr(request.user, 'is_superuser', False) or payment.recorded_by_id == request.user.id):

        messages.error(

            request,

            "Permission Denied: Only the counselor who originally submitted this payment (or an administrator) can correct and resubmit it."

        )

        return redirect('counselor_dashboard' if request.user.role == UserRole.COUNSELOR else 'counselor_enrolled_students')



    new_proof = request.FILES.get('payment_proof')

    raw_amount = request.POST.get('amount')

    new_method = request.POST.get('payment_method')

    new_ref = request.POST.get('transaction_reference')

    resub_notes = request.POST.get('resubmission_notes', '').strip()



    data = {

        'resubmission_notes': resub_notes or 'Corrected details submitted for review.',

    }

    if raw_amount:

        try:

            data['amount'] = Decimal(str(raw_amount)).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)

        except Exception:

            messages.error(request, "Invalid payment amount.")

            return redirect('counselor_enrolled_students')



    if new_method:

        data['payment_method'] = new_method

    if new_ref is not None:

        data['transaction_reference'] = new_ref



    try:

        updated_txn = resubmit_payment(payment, request.user, data=data, new_proof=new_proof)

        messages.success(

            request,

            f"Payment #{updated_txn.receipt_number} has been successfully resubmitted for Accountant verification."

        )

    except ValidationError as ve:

        err_msg = ", ".join(ve.messages) if hasattr(ve, 'messages') else str(ve)

        messages.error(request, f"Resubmission failed: {err_msg}")

    except Exception as exc:

        messages.error(request, f"Resubmission failed: {exc}")



    next_url = request.POST.get('next') or request.META.get('HTTP_REFERER') or 'counselor_enrolled_students'

    return redirect(next_url)





@login_required

@require_POST

def enrollment_update_installment(request, installment_id):

    """

    Modifies scheduled installment due date or amount with audit tracking.

    """

    installment = get_object_or_404(Installment, id=installment_id)



    if not (request.user.is_admin_user or request.user.is_sales_head_user or (request.user.role == UserRole.COUNSELOR and installment.enrollment.assigned_counselor == request.user)):

        raise PermissionDenied("You do not have permission to modify installment schedules.")



    new_date = request.POST.get('due_date')

    new_amt = request.POST.get('scheduled_amount')

    reason = request.POST.get('reason', '').strip()



    if not reason:

        messages.error(request, "Reason for installment modification is required for audit trail.")

        return redirect('admin_enrolled_students')



    try:

        parsed_date = timezone.datetime.strptime(new_date, '%Y-%m-%d').date() if new_date else None

        parsed_amt = Decimal(str(new_amt)).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP) if new_amt else None

        update_installment_schedule(installment, request.user, parsed_date, parsed_amt, reason)

        messages.success(request, f"Installment #{installment.installment_number} updated.")

    except Exception as exc:

        messages.error(request, f"Failed to update installment: {exc}")



    return redirect('admin_enrolled_students')





def check_receipt_access(user, enrollment):

    """

    Enforces object-level authorization for student fee receipts.

    - Superadmin / Admin / Sales Head: Full access across all branches.

    - Branch Head: Scoped strictly to enrollments within their branch.

    - Counselor: Scoped strictly to enrollments assigned to them.

    - Others: Denied.

    """

    if user.is_admin_user or user.is_sales_head_user:

        return

    if user.is_branch_head_user and user.branch and enrollment.branch == user.branch:

        return

    if user.role == UserRole.COUNSELOR and enrollment.assigned_counselor == user:

        return

    raise PermissionDenied("Access Denied: You do not have permission to view or download this student fee receipt.")





def get_receipt_context(request, txn):

    """

    Computes comprehensive financial, GST, ledger, installment, and tamper-verification

    context for official TECHPANDA fee receipts.

    """

    enrollment = txn.enrollment



    base_course_fee = enrollment.base_course_fee or Decimal('0.00')

    taxable_amount = enrollment.taxable_amount or Decimal('0.00')

    tax_amount = enrollment.tax_amount or Decimal('0.00')

    tax_rate = enrollment.tax_rate or Decimal('18.00')

    total_payable = enrollment.total_payable or Decimal('0.00')



    # Standard Indian GST half-rate split for CGST (Central) and SGST (State)

    half_rate = (tax_rate / Decimal('2')).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)

    cgst_rate = half_rate

    sgst_rate = half_rate

    cgst_amount = (tax_amount / Decimal('2')).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)

    sgst_amount = (tax_amount - cgst_amount).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)



    # Historical payments prior to this specific transaction

    prior_txns = enrollment.payments.filter(

        status__in=[PaymentTransactionStatus.APPROVED, PaymentTransactionStatus.SUCCESS]

    ).exclude(id=txn.id).filter(

        Q(payment_date__lt=txn.payment_date) |

        Q(payment_date=txn.payment_date, id__lt=txn.id)

    )

    prior_paid = sum((p.amount for p in prior_txns), Decimal('0.00')).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)

    this_payment = (txn.amount or Decimal('0.00')).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)

    cumulative_paid = (prior_paid + this_payment).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)



    # Balance remaining after this specific payment

    remaining_balance_after_txn = max(Decimal('0.00'), (total_payable - cumulative_paid).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP))

    current_outstanding = (enrollment.outstanding_balance or Decimal('0.00')).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)



    # Next pending or due installment

    next_installment = enrollment.installments.filter(

        status__in=[InstallmentStatus.UPCOMING, InstallmentStatus.DUE, InstallmentStatus.OVERDUE, InstallmentStatus.PARTIALLY_PAID]

    ).order_by('installment_number').first()



    # Tamper-evident electronic verification hash & URL

    secret = getattr(settings, 'SECRET_KEY', 'techpanda_crm_secret_key')

    raw_hash_input = f"{txn.receipt_number}:{txn.amount}:{enrollment.enrollment_number}:{secret}"

    token_sig = hashlib.sha256(raw_hash_input.encode('utf-8')).hexdigest()[:8].upper()

    verification_code = f"TP-VRF-{txn.receipt_number}-{token_sig}"



    verification_url = request.build_absolute_uri(

        reverse('enrollment_receipt_view', args=[txn.id])

    )



    # Generate QR codes (Base64 PNG and SVG) for browser and PDF rendering

    qr_svg = ''

    qr_b64 = ''

    qr_png_bytes = b''

    try:

        qr_png = qrcode.make(verification_url, box_size=4, border=1)

        png_buf = io.BytesIO()

        qr_png.save(png_buf, format='PNG')

        qr_png_bytes = png_buf.getvalue()

        qr_b64 = base64.b64encode(qr_png_bytes).decode('utf-8')



        factory = qrcode.image.svg.SvgPathImage

        svg_qr = qrcode.make(verification_url, image_factory=factory, box_size=8, border=1)

        svg_buf = io.BytesIO()

        svg_qr.save(svg_buf)

        qr_svg = svg_buf.getvalue().decode('utf-8')

    except Exception:

        pass



    branch_name = enrollment.branch.name if enrollment.branch else "Main Campus / Corporate HQ"

    branch_address = getattr(enrollment.branch, 'address', '') if enrollment.branch else ''

    if not branch_address:

        branch_address = "DigiPanda Towers, Knowledge Park, OMR, Chennai, Tamil Nadu - 600096"



    student_id = f"STU-{enrollment.lead_id or enrollment.id}"



    # Signature, Font & Logo local paths for xhtml2pdf rendering
    is_authorized = txn.status in [PaymentTransactionStatus.APPROVED, PaymentTransactionStatus.SUCCESS]
    signature_path = os.path.join(settings.BASE_DIR, 'static', 'images', 'shashi_sign.png').replace('\\', '/')
    if not os.path.exists(signature_path):
        signature_path = os.path.join(settings.BASE_DIR, 'static', 'images', 'Shashi_Sign.png').replace('\\', '/')

    signature_data_uri = None
    if is_authorized and os.path.exists(signature_path):
        try:
            with open(signature_path, 'rb') as sig_f:
                sig_bytes = sig_f.read()
                signature_data_uri = f"data:image/png;base64,{base64.b64encode(sig_bytes).decode('utf-8')}"
        except Exception:
            signature_data_uri = None

    font_path = os.path.join(settings.BASE_DIR, 'static', 'fonts', 'Arial.ttf').replace('\\', '/')

    logo_path = os.path.join(settings.BASE_DIR, 'static', 'images', 'digipanda_logo.png').replace('\\', '/')
    logo_data_uri = None
    if os.path.exists(logo_path):
        try:
            with open(logo_path, 'rb') as logo_f:
                logo_bytes = logo_f.read()
                logo_data_uri = f"data:image/png;base64,{base64.b64encode(logo_bytes).decode('utf-8')}"
        except Exception:
            logo_data_uri = None



    # Check Inter-state GST (IGST) vs Intra-state GST (CGST + SGST)

    is_interstate = False

    customer_state = getattr(enrollment, 'student_state', '') or ''

    branch_state = getattr(enrollment.branch, 'state', '') or 'Tamil Nadu'

    if customer_state and branch_state and customer_state.strip().lower() != branch_state.strip().lower():

        is_interstate = True


        is_interstate = True



    igst_rate = tax_rate if is_interstate else Decimal('0.00')

    igst_amount = tax_amount if is_interstate else Decimal('0.00')

    if is_interstate:

        cgst_rate = Decimal('0.00')

        sgst_rate = Decimal('0.00')

        cgst_amount = Decimal('0.00')

        sgst_amount = Decimal('0.00')



    # Invoice and Student formatting matching reference Tax Invoice PDF

    invoice_number = txn.receipt_number or f"TP{txn.id:05d}"

    if txn.payment_date:

        invoice_date = txn.payment_date.strftime('%d/%m/%Y')

    elif txn.created_at:

        invoice_date = txn.created_at.strftime('%d/%m/%Y')

    else:

        invoice_date = timezone.now().strftime('%d/%m/%Y')



    customer_name = (enrollment.student_name or '').strip().upper()

    customer_mobile = (enrollment.student_phone or (enrollment.lead.phone if enrollment.lead else '') or '').strip()

    customer_email = (enrollment.student_email or (enrollment.lead.email if enrollment.lead else '') or '').strip()

    customer_address = getattr(enrollment, 'student_address', '') or ''

    place_of_supply = branch_state or TECHPANDA_INVOICE_CONFIG.get('default_place_of_supply', 'Tamil Nadu')



    course_name = (enrollment.product.name if enrollment.product else "DATA ANALYTICS COURSE").strip().upper()



    total_amount_in_words = amount_to_inr_words(total_payable)

    received_amount_in_words = amount_to_inr_words(cumulative_paid)

    balance_amount_in_words = amount_to_inr_words(remaining_balance_after_txn)



    return {

        'txn': txn,

        'enrollment': enrollment,

        'student_id': student_id,

        'qr_svg': qr_svg,

        'qr_b64': qr_b64,

        'qr_png_bytes': qr_png_bytes,

        'base_course_fee': base_course_fee,

        'taxable_amount': taxable_amount,

        'tax_amount': tax_amount,

        'tax_rate': tax_rate,

        'cgst_rate': cgst_rate,

        'sgst_rate': sgst_rate,

        'cgst_amount': cgst_amount,

        'sgst_amount': sgst_amount,

        'igst_rate': igst_rate,

        'igst_amount': igst_amount,

        'is_interstate': is_interstate,

        'total_payable': total_payable,

        'prior_paid': prior_paid,

        'this_payment': this_payment,

        'cumulative_paid': cumulative_paid,

        'remaining_balance_after_txn': remaining_balance_after_txn,

        'current_outstanding': current_outstanding,

        'next_installment': next_installment,

        'verification_code': verification_code,

        'verification_url': verification_url,

        'branch_name': branch_name,

        'branch_address': branch_address,

        'institution_name': TECHPANDA_INVOICE_CONFIG['company_name'],

        'institution_tagline': "Professional Software & Technology Training",

        'institution_email': TECHPANDA_INVOICE_CONFIG['email'],

        'institution_phone': TECHPANDA_INVOICE_CONFIG['mobile'],

        'institution_website': TECHPANDA_INVOICE_CONFIG['website'],

        'invoice_config': TECHPANDA_INVOICE_CONFIG,

        'invoice_number': invoice_number,
        'receipt_number': invoice_number,
        'payment_date': invoice_date,

        'invoice_date': invoice_date,

        'customer_name': customer_name,

        'customer_mobile': customer_mobile,

        'customer_email': customer_email,

        'customer_address': customer_address,

        'place_of_supply': place_of_supply,

        'course_name': course_name,

        'taxable_rate': taxable_amount,

        'total_line_amount': total_payable,

        'total_invoice_amount': total_payable,

        'received_amount': cumulative_paid,

        'balance_amount': remaining_balance_after_txn,

        'total_amount_in_words': total_amount_in_words,

        'received_amount_in_words': received_amount_in_words,

        'balance_amount_in_words': balance_amount_in_words,

        'bank_details': TECHPANDA_INVOICE_CONFIG['bank_details'],

        'terms_and_conditions': TECHPANDA_INVOICE_CONFIG['terms_and_conditions'],

        'signatory_label': TECHPANDA_INVOICE_CONFIG['signatory_label'],
        'is_authorized': is_authorized,
        'font_path': font_path,
        'logo_path': logo_path,
        'logo_data_uri': logo_data_uri,
        'signature_path': signature_path if (is_authorized and os.path.exists(signature_path)) else None,
        'signature_url': '/static/images/shashi_sign.png' if is_authorized else None,
        'signature_data_uri': signature_data_uri,
    }





def generate_receipt_pdf(context_dict):
    """
    Renders receipt_pdf.html into a compliant A4 PDF document using xhtml2pdf.
    Applies PmlImageReader patch to ensure distinct image caching across multiple document images.
    """
    try:
        from xhtml2pdf import xhtml2pdf_reportlab
        def _pml_reader_str(self):
            if hasattr(self, '_image') and self._image:
                try:
                    return f"PmlImageObject_{hashlib.md5(self._image.tobytes()).hexdigest()}"
                except Exception:
                    pass
            return f"PmlImageObject_{id(self)}"
        xhtml2pdf_reportlab.PmlImageReader.__str__ = _pml_reader_str
    except Exception:
        pass

    template = get_template('leads/receipt_pdf.html')
    html = template.render(context_dict)
    result = io.BytesIO()
    pdf = pisa.pisaDocument(io.BytesIO(html.encode("UTF-8")), result)
    if not pdf.err:
        return result.getvalue()
    return None





@login_required

def enrollment_receipt_pdf_view(request, transaction_id):

    """

    Direct official PDF download endpoint for an authentic student fee receipt.

    """

    txn = get_object_or_404(

        PaymentTransaction.objects.select_related('enrollment', 'enrollment__product', 'enrollment__branch', 'recorded_by'),

        id=transaction_id

    )

    check_receipt_access(request.user, txn.enrollment)



    context = get_receipt_context(request, txn)

    pdf_bytes = generate_receipt_pdf(context)

    if not pdf_bytes:

        messages.error(request, "Error generating official PDF receipt. Please use the print view.")

        return redirect('enrollment_receipt_view', transaction_id=txn.id)



    response = HttpResponse(pdf_bytes, content_type='application/pdf')

    filename = f"DigiPanda_Receipt_{txn.receipt_number}.pdf"

    response['Content-Disposition'] = f'attachment; filename="{filename}"'

    return response





@login_required

def enrollment_receipt_view(request, transaction_id):

    """

    Printable and downloadable payment receipt for a student transaction.

    Supports ?download=pdf or ?format=pdf query param to trigger direct download.

    """

    txn = get_object_or_404(

        PaymentTransaction.objects.select_related('enrollment', 'enrollment__product', 'enrollment__branch', 'recorded_by'),

        id=transaction_id

    )

    check_receipt_access(request.user, txn.enrollment)



    if request.GET.get('download') == 'pdf' or request.GET.get('format') == 'pdf':

        return enrollment_receipt_pdf_view(request, transaction_id)



    context = get_receipt_context(request, txn)

    return render(request, 'leads/receipt.html', context)





@login_required

@require_POST

def trigger_installment_reminders(request):

    """

    Admin trigger to scan and send installment reminders for upcoming, due, and overdue payments.

    """

    if not (request.user.is_admin_user or request.user.is_sales_head_user):

        raise PermissionDenied("Access Denied.")



    try:

        sent_count = send_installment_reminders()

        messages.success(request, f"Dispatched {sent_count} installment reminder email(s).")

    except Exception as exc:

        messages.error(request, f"Failed to send reminders: {exc}")



    return redirect('admin_enrolled_students')


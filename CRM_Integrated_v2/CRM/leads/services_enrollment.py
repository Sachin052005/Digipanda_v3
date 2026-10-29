import os
import logging
from decimal import Decimal, ROUND_HALF_UP
from datetime import timedelta
from PIL import Image
from django.db import transaction
from django.utils import timezone
from django.core.mail import send_mail
from django.conf import settings
from django.core.exceptions import ValidationError, PermissionDenied

from accounts.models import UserRole
from activities.utils import log_activity
from .models import (
    Lead,
    LeadStatus,
    Enrollment,
    Installment,
    PaymentTransaction,
    PaymentVerificationHistory,
    InstallmentScheduleHistory,
    PaymentEmailLog,
    GSTTreatment,
    PaymentPlan,
    InstallmentMethod,
    EnrollmentStatus,
    EnrollmentPaymentStatus,
    InstallmentStatus,
    PaymentMethod,
    PaymentTransactionStatus,
)

logger = logging.getLogger(__name__)

ONLINE_PAYMENT_METHODS = [
    PaymentMethod.UPI,
    PaymentMethod.BANK_TRANSFER,
    PaymentMethod.ONLINE,
    PaymentMethod.CARD,
]

ALLOWED_PROOF_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.webp'}
MAX_PROOF_SIZE = 5 * 1024 * 1024  # 5MB


def validate_payment_proof(file_obj):
    """
    Validates uploaded payment proof:
    - Maximum size: 5MB
    - Allowed extensions: .jpg, .jpeg, .png, .webp
    - Validates image integrity using PIL
    """
    if not file_obj:
        return

    # 1. Size check
    if hasattr(file_obj, 'size') and file_obj.size > MAX_PROOF_SIZE:
        raise ValidationError(f"Payment proof file size exceeds maximum limit of 5MB ({file_obj.size / (1024*1024):.1f}MB uploaded).")

    # 2. Extension check
    name = getattr(file_obj, 'name', '')
    ext = os.path.splitext(name)[1].lower()
    if ext not in ALLOWED_PROOF_EXTENSIONS:
        raise ValidationError(f"Invalid file format '{ext}'. Allowed formats are JPG, JPEG, PNG, WEBP.")

    # 3. Image integrity check using PIL
    try:
        current_pos = file_obj.tell() if hasattr(file_obj, 'tell') else None
    except Exception:
        current_pos = None

    try:
        img = Image.open(file_obj)
        img.verify()
    except Exception as e:
        raise ValidationError(f"The uploaded file is not a valid image: {e}")
    finally:
        if hasattr(file_obj, 'seek'):
            try:
                file_obj.seek(current_pos if current_pos is not None else 0)
            except Exception:
                pass



def can_change_to_enrolled(user, lead):
    """
    Strict permission check for changing a lead's status to 'Enrolled':
    - Allowed: Admin, Sales Head, Branch Head (for their branch), or the assigned Counselor.
    - Denied: Telecaller, Receptionist, or Counselors not assigned to this lead.
    """
    if not user or not user.is_authenticated:
        return False
    if user.is_admin_user or user.is_sales_head_user:
        return True
    if user.is_branch_head_user or user.is_branch_admin_user:
        return lead.branch_id == user.branch_id or user.branch is None
    if user.role == UserRole.COUNSELOR:
        return lead.assigned_counselor_id == user.id
    # Telecaller, Receptionist, and all other roles are strictly denied
    return False


def validate_status_transition(user, lead, new_status):
    """
    Central validation for all lead status transitions across forms, APIs, and bulk actions.
    """
    if new_status == LeadStatus.ENROLLED:
        if not can_change_to_enrolled(user, lead):
            raise PermissionDenied(
                "Permission Denied: Only the assigned Counselor, Branch Head, Sales Head, or Admin can mark a lead as 'Enrolled'."
            )
    if user.role == UserRole.RECEPTIONIST:
        raise PermissionDenied("Permission Denied: Receptionists are not permitted to change lead status.")


@transaction.atomic
def create_or_update_enrollment(lead, user, data):
    """
    Creates or updates an Enrollment record linked to a Lead.
    Enforces mandatory fields, GST calculation (Inclusive/Exclusive),
    and Installment generation (Manual/Automatic).
    """
    if not can_change_to_enrolled(user, lead):
        raise PermissionDenied("You do not have permission to manage enrollments for this lead.")

    # 1. Mandatory Fields
    student_name = (data.get('student_name') or lead.name or '').strip()
    student_phone = (data.get('student_phone') or lead.phone or '').strip()
    student_email = (data.get('student_email') or lead.email or '').strip()
    product = data.get('product') or lead.product
    branch = data.get('branch') or lead.branch
    counselor = data.get('assigned_counselor') or lead.assigned_counselor

    if not student_name:
        raise ValidationError({'student_name': "Student name is required."})
    if not student_phone:
        raise ValidationError({'student_phone': "Student phone number is required."})

    # 2. Financial & GST Calculation
    raw_fee = data.get('base_course_fee', 0)
    try:
        base_course_fee = Decimal(str(raw_fee)).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
    except Exception:
        raise ValidationError({'base_course_fee': "Invalid course fee."})

    if base_course_fee <= Decimal('0.00'):
        raise ValidationError({'base_course_fee': "Agreed course fee must be greater than zero."})

    gst_treatment = data.get('gst_treatment')
    if gst_treatment not in [GSTTreatment.INCLUSIVE, GSTTreatment.EXCLUSIVE]:
        raise ValidationError({'gst_treatment': "Course Fee GST Treatment is mandatory. Please select Inclusive or Exclusive of GST."})

    raw_tax_rate = data.get('tax_rate')
    if raw_tax_rate is None or str(raw_tax_rate).strip() == '':
        tax_rate = Enrollment.get_default_gst_rate()
    else:
        try:
            tax_rate = Decimal(str(raw_tax_rate)).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
        except Exception:
            tax_rate = Enrollment.get_default_gst_rate()

    gst_breakdown = Enrollment.calculate_gst_breakdown(base_course_fee, gst_treatment, tax_rate)
    taxable_amount = gst_breakdown['taxable_amount']
    tax_amount = gst_breakdown['tax_amount']
    total_payable = gst_breakdown['total_payable']

    # 3. Payment Plan & Scheduling Method
    payment_plan = data.get('payment_plan', PaymentPlan.FULL_PAYMENT)
    installment_method = data.get('installment_method', '')
    if payment_plan == PaymentPlan.SPLIT_PAYMENT and not installment_method:
        installment_method = InstallmentMethod.AUTOMATIC

    enrollment_date = data.get('enrollment_date') or timezone.localdate()
    course_start_date = data.get('course_start_date') or None

    # 4. Generate/Retrieve Enrollment Instance
    enrollment, created = Enrollment.objects.get_or_create(
        lead=lead,
        defaults={
            'enrollment_number': f"ENR-{timezone.now().year}-{lead.id}",
            'student_name': student_name,
            'student_phone': student_phone,
            'student_email': student_email,
            'product': product,
            'branch': branch,
            'assigned_counselor': counselor,
            'enrollment_date': enrollment_date,
            'course_start_date': course_start_date,
            'base_course_fee': base_course_fee,
            'gst_treatment': gst_treatment,
            'tax_rate': tax_rate,
            'taxable_amount': taxable_amount,
            'tax_amount': tax_amount,
            'total_payable': total_payable,
            'payment_plan': payment_plan,
            'installment_method': installment_method,
            'outstanding_balance': total_payable,
            'created_by': user,
            'notes': data.get('notes', ''),
        }
    )

    if not created:
        enrollment.student_name = student_name
        enrollment.student_phone = student_phone
        enrollment.student_email = student_email
        enrollment.product = product
        enrollment.branch = branch
        if counselor:
            enrollment.assigned_counselor = counselor
        enrollment.enrollment_date = enrollment_date
        enrollment.course_start_date = course_start_date
        enrollment.base_course_fee = base_course_fee
        enrollment.gst_treatment = gst_treatment
        enrollment.tax_rate = tax_rate
        enrollment.taxable_amount = taxable_amount
        enrollment.tax_amount = tax_amount
        enrollment.total_payable = total_payable
        enrollment.payment_plan = payment_plan
        enrollment.installment_method = installment_method
        enrollment.notes = data.get('notes', enrollment.notes)
        enrollment.save()

    # 5. Process Installments
    if payment_plan == PaymentPlan.SPLIT_PAYMENT:
        if installment_method == InstallmentMethod.MANUAL:
            manual_installments = data.get('manual_installments', [])
            _setup_manual_installments(enrollment, manual_installments, user)
        else:
            inst_count = int(data.get('installment_count', 2))
            first_due = data.get('first_installment_date') or enrollment_date
            _setup_automatic_installments(enrollment, inst_count, first_due, user)
    else:
        # Full payment: single installment for the full total payable
        if not enrollment.installments.filter(amount_paid__gt=0).exists():
            enrollment.installments.all().delete()
            Installment.objects.create(
                enrollment=enrollment,
                installment_number=1,
                scheduled_amount=total_payable,
                due_date=enrollment_date,
                remaining_balance=total_payable,
                status=InstallmentStatus.UPCOMING,
                last_updated_by=user
            )

    # 6. Recalculate financials
    enrollment.update_financials()

    # 7. Update Lead status to ENROLLED if not already
    if lead.status != LeadStatus.ENROLLED:
        lead.status = LeadStatus.ENROLLED
        lead.save(update_fields=['status', 'updated_at'])

    # Sync student email back to lead record if lead email is empty
    if student_email and not lead.email:
        lead.email = student_email
        lead.save(update_fields=['email', 'updated_at'])

    log_activity(
        user=user,
        action="Enrollment Created/Updated",
        description=f"Enrollment #{enrollment.enrollment_number} processed for '{student_name}'. Total: ₹{total_payable} ({gst_treatment}).",
        object_type="Enrollment",
        object_id=enrollment.id
    )

    # 8. Send confirmation email on commit if not already sent
    if not enrollment.confirmation_email_sent:
        from services.email_service import send_enrollment_confirmation_email
        def safe_send_enrollment_email():
            try:
                send_enrollment_confirmation_email(enrollment)
            except Exception as e:
                logger.error("Failed to send enrollment confirmation email for #%s: %s", getattr(enrollment, 'enrollment_number', 'N/A'), e)
        transaction.on_commit(safe_send_enrollment_email)

    return enrollment


def _setup_automatic_installments(enrollment, count, first_due_date, user):
    """
    Safely divides remaining payable balance across N installments using Decimal arithmetic.
    Rounding difference cents/paise are absorbed by the final installment so the exact sum matches total_payable.
    Preserves already-paid installments.
    """
    if count < 1:
        count = 1

    paid_installments = list(enrollment.installments.filter(amount_paid__gt=0).order_by('installment_number'))
    already_paid_or_allocated = sum(i.scheduled_amount for i in paid_installments)
    remaining_to_schedule = max(Decimal('0.00'), enrollment.total_payable - already_paid_or_allocated)

    future_count = max(1, count - len(paid_installments))
    base_inst_amount = (remaining_to_schedule / Decimal(str(future_count))).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
    total_base = base_inst_amount * Decimal(str(future_count))
    remainder_diff = remaining_to_schedule - total_base

    # Delete existing unpaid future installments
    enrollment.installments.filter(amount_paid=0).delete()

    current_num = len(paid_installments) + 1
    current_due = first_due_date

    for i in range(future_count):
        inst_num = current_num + i
        amt = base_inst_amount
        if i == future_count - 1:
            amt = amt + remainder_diff  # Absorb rounding cents on last installment

        Installment.objects.create(
            enrollment=enrollment,
            installment_number=inst_num,
            scheduled_amount=amt,
            due_date=current_due,
            remaining_balance=amt,
            status=InstallmentStatus.UPCOMING if current_due > timezone.localdate() else InstallmentStatus.DUE,
            last_updated_by=user
        )
        current_due = current_due + timedelta(days=30)  # Next monthly due date

    enrollment.installment_count = count
    enrollment.save(update_fields=['installment_count'])


def _setup_manual_installments(enrollment, installments_data, user):
    """
    Validates and stores manually configured installment amounts and due dates.
    Validates that total scheduled amounts match total_payable.
    """
    if not installments_data:
        raise ValidationError("At least one installment must be defined for Manual Installments.")

    total_scheduled = Decimal('0.00')
    parsed = []
    for idx, item in enumerate(installments_data, start=1):
        amt = Decimal(str(item.get('amount', 0))).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
        due = item.get('due_date')
        if amt <= Decimal('0.00'):
            raise ValidationError(f"Installment #{idx} amount must be greater than zero.")
        if not due:
            raise ValidationError(f"Installment #{idx} due date is required.")
        total_scheduled += amt
        parsed.append({'num': idx, 'amount': amt, 'due_date': due, 'notes': item.get('notes', '')})

    if total_scheduled != enrollment.total_payable:
        raise ValidationError(
            f"The sum of scheduled installments (₹{total_scheduled}) must match the total payable fee (₹{enrollment.total_payable})."
        )

    # Delete unpaid installments and recreate
    enrollment.installments.filter(amount_paid=0).delete()
    for item in parsed:
        Installment.objects.create(
            enrollment=enrollment,
            installment_number=item['num'],
            scheduled_amount=item['amount'],
            due_date=item['due_date'],
            remaining_balance=item['amount'],
            status=InstallmentStatus.UPCOMING if str(item['due_date']) > str(timezone.localdate()) else InstallmentStatus.DUE,
            notes=item['notes'],
            last_updated_by=user
        )

    enrollment.installment_count = len(parsed)
    enrollment.save(update_fields=['installment_count'])


@transaction.atomic
def record_payment(
    enrollment,
    amount_or_user,
    payment_method_or_data=None,
    recorded_by=None,
    transaction_reference='',
    notes='',
    installment_id=None,
    payment_proof=None,
    auto_approve=None,
):
    """
    Records a payment transaction against an enrollment.
    If auto_approve=False (standard Counselor workflow):
      - Enforces proof screenshot for online payment methods (UPI, Bank Transfer, Card, Online).
      - Sets status to PENDING_VERIFICATION.
      - Logs PaymentVerificationHistory as SUBMITTED.
      - Balances remain unchanged until Accountant approval.
      - Suppresses student confirmation email.
    If auto_approve=True (direct admin approval / legacy test compatibility):
      - Sets status to APPROVED.
      - Updates installment and enrollment balances immediately.
      - Logs PaymentVerificationHistory as APPROVED.
      - Dispatches student confirmation email.
    """
    if isinstance(payment_method_or_data, dict):
        recorded_by = amount_or_user
        data = payment_method_or_data
        amount = data.get('amount')
        payment_method = data.get('payment_method', PaymentMethod.UPI)
        transaction_reference = data.get('transaction_reference', '')
        notes = data.get('notes', '')
        installment_id = data.get('installment_id')
        payment_proof = data.get('payment_proof') or payment_proof
        if 'auto_approve' in data:
            auto_approve = data['auto_approve']
    else:
        amount = amount_or_user
        payment_method = payment_method_or_data or PaymentMethod.UPI

    # Default auto_approve to True only for legacy programmatic calls;
    # web endpoints pass auto_approve=False.
    if auto_approve is None:
        auto_approve = True

    try:
        dec_amount = Decimal(str(amount)).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
    except Exception:
        raise ValidationError("Invalid payment amount.")

    if dec_amount <= Decimal('0.00'):
        raise ValidationError("Payment amount must be greater than zero.")

    if dec_amount > enrollment.outstanding_balance:
        if enrollment.outstanding_balance <= Decimal('0.00'):
            raise ValidationError("This enrollment is already fully paid.")

    # Validate proof requirement for online methods when verification is active
    if not auto_approve and payment_method in ONLINE_PAYMENT_METHODS:
        if not payment_proof:
            raise ValidationError(
                f"Payment screenshot / proof is mandatory for online payment method '{payment_method}'. Please upload the transaction receipt."
            )

    if payment_proof:
        validate_payment_proof(payment_proof)

    # Generate unique receipt number
    now = timezone.now()
    timestamp_str = now.strftime('%Y%m%d%H%M%S')
    micro_str = now.strftime('%f')[:4]
    receipt_number = f"REC-{enrollment.id}-{timestamp_str}-{micro_str}"

    installment = None
    if installment_id:
        try:
            installment = enrollment.installments.get(id=installment_id)
        except Installment.DoesNotExist:
            installment = None

    # If no specific installment given, apply to earliest unpaid installment
    if not installment:
        installment = enrollment.installments.filter(remaining_balance__gt=0).order_by('due_date', 'installment_number').first()

    initial_status = PaymentTransactionStatus.APPROVED if auto_approve else PaymentTransactionStatus.PENDING_VERIFICATION

    # Create PaymentTransaction
    payment = PaymentTransaction.objects.create(
        enrollment=enrollment,
        installment=installment,
        amount=dec_amount,
        payment_date=timezone.now(),
        payment_method=payment_method,
        transaction_reference=transaction_reference.strip(),
        receipt_number=receipt_number,
        status=initial_status,
        notes=notes.strip(),
        recorded_by=recorded_by,
        payment_proof=payment_proof
    )

    if auto_approve:
        payment.reviewed_by = recorded_by
        payment.reviewed_at = timezone.now()
        payment.save(update_fields=['reviewed_by', 'reviewed_at'])

        if installment:
            installment.update_balance()
        enrollment.update_financials()

        PaymentVerificationHistory.objects.create(
            payment=payment,
            action=PaymentVerificationHistory.Action.APPROVED,
            performed_by=recorded_by,
            comment="Directly approved upon creation."
        )

        log_activity(
            user=recorded_by,
            action="Payment Recorded",
            description=f"Received ₹{dec_amount} via {payment_method} for Enrollment #{enrollment.enrollment_number} (Receipt #{receipt_number}).",
            object_type="PaymentTransaction",
            object_id=payment.id
        )

        # Send confirmation email on commit
        transaction.on_commit(lambda: send_payment_confirmation_email(payment))
    else:
        PaymentVerificationHistory.objects.create(
            payment=payment,
            action=PaymentVerificationHistory.Action.SUBMITTED,
            performed_by=recorded_by,
            comment=f"Submitted for verification with proof: {'Yes' if payment_proof else 'No (Cash)'}"
        )

        log_activity(
            user=recorded_by,
            action="Payment Submitted for Verification",
            description=f"Payment of ₹{dec_amount} via {payment_method} for Enrollment #{enrollment.enrollment_number} submitted for accountant verification.",
            object_type="PaymentTransaction",
            object_id=payment.id
        )

    return payment


@transaction.atomic
def approve_payment(payment_or_id, accountant_user):
    """
    Approves a pending payment transaction.
    - Idempotent and thread-safe via select_for_update().
    - Updates installment and enrollment balances.
    - Logs PaymentVerificationHistory.
    - Dispatches student confirmation email on commit.
    """
    if isinstance(payment_or_id, PaymentTransaction):
        payment_id = payment_or_id.id
    else:
        payment_id = payment_or_id

    payment = PaymentTransaction.objects.select_for_update().select_related('enrollment', 'installment').get(id=payment_id)

    # Idempotency check: if already approved, return without duplicating side effects
    if payment.status in (PaymentTransactionStatus.APPROVED, PaymentTransactionStatus.SUCCESS):
        return payment

    if payment.status != PaymentTransactionStatus.PENDING_VERIFICATION:
        raise ValidationError(f"Cannot approve payment with status '{payment.status}'. Only pending payments can be approved.")

    payment.status = PaymentTransactionStatus.APPROVED
    payment.reviewed_by = accountant_user
    payment.reviewed_at = timezone.now()
    payment.rejection_comment = ''  # Clear any previous rejection comment
    payment.save(update_fields=['status', 'reviewed_by', 'reviewed_at', 'rejection_comment'])

    # Update installment and enrollment balances
    if payment.installment:
        payment.installment.update_balance()
    payment.enrollment.update_financials()

    PaymentVerificationHistory.objects.create(
        payment=payment,
        action=PaymentVerificationHistory.Action.APPROVED,
        performed_by=accountant_user,
        comment="Approved by accountant."
    )

    log_activity(
        user=accountant_user,
        action="Payment Approved",
        description=f"Approved payment of ₹{payment.amount} (Receipt #{payment.receipt_number}) for {payment.enrollment.student_name}.",
        object_type="PaymentTransaction",
        object_id=payment.id
    )

    # Send receipt confirmation email to student on commit
    transaction.on_commit(lambda: send_payment_confirmation_email(payment))

    return payment


@transaction.atomic
def reject_payment(payment_or_id, accountant_user, comment):
    """
    Rejects a pending payment transaction with a mandatory comment.
    - Idempotent and thread-safe via select_for_update().
    - Balances remain unchanged.
    - Logs PaymentVerificationHistory.
    """
    if not comment or not str(comment).strip():
        raise ValidationError("A rejection comment is mandatory. Please state why the payment is being rejected.")

    if isinstance(payment_or_id, PaymentTransaction):
        payment_id = payment_or_id.id
    else:
        payment_id = payment_or_id

    payment = PaymentTransaction.objects.select_for_update().select_related('enrollment', 'installment').get(id=payment_id)

    if payment.status == PaymentTransactionStatus.REJECTED:
        return payment

    if payment.status != PaymentTransactionStatus.PENDING_VERIFICATION:
        raise ValidationError(f"Cannot reject payment with status '{payment.status}'. Only pending payments can be rejected.")

    clean_comment = str(comment).strip()
    payment.status = PaymentTransactionStatus.REJECTED
    payment.reviewed_by = accountant_user
    payment.reviewed_at = timezone.now()
    payment.rejection_comment = clean_comment
    payment.save(update_fields=['status', 'reviewed_by', 'reviewed_at', 'rejection_comment'])

    PaymentVerificationHistory.objects.create(
        payment=payment,
        action=PaymentVerificationHistory.Action.REJECTED,
        performed_by=accountant_user,
        comment=clean_comment
    )

    log_activity(
        user=accountant_user,
        action="Payment Rejected",
        description=f"Rejected payment of ₹{payment.amount} (Receipt #{payment.receipt_number}) for {payment.enrollment.student_name}. Reason: {clean_comment}",
        object_type="PaymentTransaction",
        object_id=payment.id
    )

    return payment


@transaction.atomic
def resubmit_payment(payment_or_id, counselor_user, data=None, new_proof=None):
    """
    Allows a counselor to resubmit a rejected payment with corrected details or proof.
    - Resets status to PENDING_VERIFICATION.
    - Increments resubmission_count.
    - Logs PaymentVerificationHistory.
    """
    if isinstance(payment_or_id, PaymentTransaction):
        payment_id = payment_or_id.id
    else:
        payment_id = payment_or_id

    payment = PaymentTransaction.objects.select_for_update().select_related('enrollment', 'installment').get(id=payment_id)

    if payment.status != PaymentTransactionStatus.REJECTED:
        raise ValidationError(f"Only rejected payments can be resubmitted. Current status: '{payment.status}'.")

    # Strict isolation: Only the original submitting counselor (recorded_by) or an administrator can resubmit
    if counselor_user and not (getattr(counselor_user, 'is_admin_user', False) or getattr(counselor_user, 'is_superuser', False) or payment.recorded_by_id == counselor_user.id):
        raise PermissionDenied("Permission Denied: Only the counselor who originally submitted this payment (or an administrator) can resubmit it.")

    data = data or {}
    update_fields = ['status', 'resubmission_count', 'updated_at']

    if 'amount' in data and data['amount']:
        try:
            new_amount = Decimal(str(data['amount'])).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
            if new_amount <= Decimal('0.00'):
                raise ValidationError("Amount must be greater than zero.")
            payment.amount = new_amount
            update_fields.append('amount')
        except Exception:
            raise ValidationError("Invalid payment amount.")

    if 'payment_method' in data and data['payment_method']:
        payment.payment_method = data['payment_method']
        update_fields.append('payment_method')

    if 'transaction_reference' in data:
        payment.transaction_reference = str(data['transaction_reference']).strip()
        update_fields.append('transaction_reference')

    if 'notes' in data:
        payment.notes = str(data['notes']).strip()
        update_fields.append('notes')

    if new_proof:
        validate_payment_proof(new_proof)
        payment.payment_proof = new_proof
        update_fields.append('payment_proof')
    elif payment.payment_method in ONLINE_PAYMENT_METHODS and not payment.payment_proof:
        raise ValidationError(
            f"Payment screenshot / proof is mandatory for online payment method '{payment.payment_method}'."
        )

    resubmission_notes = data.get('resubmission_notes', 'Resubmitted with corrected details.')

    payment.status = PaymentTransactionStatus.PENDING_VERIFICATION
    payment.resubmission_count += 1
    payment.save(update_fields=list(set(update_fields)))

    PaymentVerificationHistory.objects.create(
        payment=payment,
        action=PaymentVerificationHistory.Action.RESUBMITTED,
        performed_by=counselor_user,
        comment=resubmission_notes
    )

    log_activity(
        user=counselor_user,
        action="Payment Resubmitted",
        description=f"Resubmitted payment #{payment.receipt_number} of ₹{payment.amount} for verification. Note: {resubmission_notes}",
        object_type="PaymentTransaction",
        object_id=payment.id
    )

    return payment



@transaction.atomic
def update_installment_schedule(enrollment, installment, new_amount, new_due_date, user, reason=""):
    """
    Audited modification of a future installment amount or due date.
    Preserves paid installments and recalculates remaining schedule.
    """
    if installment.amount_paid > Decimal('0.00'):
        raise ValidationError("Cannot modify an installment that has already received payments.")

    new_amount = Decimal(str(new_amount)).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
    if new_amount <= Decimal('0.00'):
        raise ValidationError("Installment amount must be greater than zero.")

    prev_data = {
        'scheduled_amount': str(installment.scheduled_amount),
        'due_date': str(installment.due_date),
        'status': installment.status,
    }

    installment.scheduled_amount = new_amount
    installment.due_date = new_due_date
    installment.remaining_balance = new_amount
    installment.last_updated_by = user
    installment.save()

    new_data = {
        'scheduled_amount': str(new_amount),
        'due_date': str(new_due_date),
        'status': installment.status,
    }

    InstallmentScheduleHistory.objects.create(
        enrollment=enrollment,
        installment=installment,
        action="Updated Installment",
        previous_value=prev_data,
        new_value=new_data,
        reason=reason,
        changed_by=user
    )

    enrollment.update_financials()
    return installment


def send_payment_confirmation_email(payment, force_retry=False):
    """
    Sends automated payment receipt email to student's registered email address.
    Uses shared email service with HTML and text templates, durable logging and idempotency.
    """
    from services.email_service import send_payment_receipt_email
    success, _ = send_payment_receipt_email(payment, force_retry=force_retry)
    return success


def send_installment_reminders(target_date=None):
    """
    Scheduled & idempotent reminder engine for upcoming, due, and overdue installments.
    Sends emails to students and logs attempts using the configurable multi-stage schedule.
    """
    from services.email_service import process_installment_reminders_batch
    summary = process_installment_reminders_batch(target_date=target_date)
    return sum(v for k, v in summary.items() if k != 'errors')


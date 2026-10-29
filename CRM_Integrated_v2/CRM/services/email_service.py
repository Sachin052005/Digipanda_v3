"""
Shared Email Service for DigiPanda CRM.
Handles:
- Professional HTML + Plain-text alternative email rendering and delivery via Django SMTP.
- Recipient email validation and sanitization.
- Error handling, delivery logging, and retry queues via PaymentEmailLog.
- Enrollment confirmation emails.
- Payment receipt emails (integrated with + Payment workflow).
- Installment due and overdue reminder emails.
- Management diagnostic commands.
"""

import logging
import re
import os
import base64
from decimal import Decimal
from datetime import timedelta

from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.utils import timezone
from django.db import transaction

from leads.models_enrollment import (
    Enrollment,
    Installment,
    PaymentTransaction,
    PaymentEmailLog,
    PaymentTransactionStatus,
    InstallmentStatus,
)

logger = logging.getLogger('crm.emails')

EMAIL_REGEX = re.compile(r'^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$')


def is_valid_email(email):
    """Checks whether the given email address has a valid syntax."""
    if not email or not isinstance(email, str):
        return False
    return bool(EMAIL_REGEX.match(email.strip()))


def get_brand_logo_data_uri():
    """Returns Base64 Data URI for the authentic DigiPanda logo."""
    logo_path = os.path.join(settings.BASE_DIR, 'static', 'images', 'digipanda_logo.png')
    if os.path.exists(logo_path):
        try:
            with open(logo_path, 'rb') as f:
                return f"data:image/png;base64,{base64.b64encode(f.read()).decode('utf-8')}"
        except Exception:
            pass
    return None


def send_template_email(subject, recipient, html_template, text_template, context, from_email=None, attachments=None, inline_images=None):
    """
    Core reusable email dispatcher using Django's configured EmailMultiAlternatives backend.
    Validates recipient, renders both HTML and TXT templates, and returns (success, error_or_msg_id).
    Supports file attachments and CID inline images.
    """
    recipient = (recipient or '').strip()
    if not is_valid_email(recipient):
        return False, f"Invalid recipient email address: '{recipient}'"

    from_addr = from_email or getattr(settings, 'DEFAULT_FROM_EMAIL', None) or getattr(settings, 'EMAIL_HOST_USER', '')

    if context is not None and 'logo_data_uri' not in context:
        context['logo_data_uri'] = get_brand_logo_data_uri()

    try:
        html_body = render_to_string(html_template, context)
        text_body = render_to_string(text_template, context)

        message = EmailMultiAlternatives(
            subject=subject,
            body=text_body,
            from_email=from_addr,
            to=[recipient],
        )
        message.attach_alternative(html_body, "text/html")
        if attachments:
            for att in attachments:
                message.attach(*att)
        if inline_images:
            from email.mime.image import MIMEImage
            for cid, img_data, mime_type in inline_images:
                mime_img = MIMEImage(img_data)
                mime_img.add_header('Content-ID', f'<{cid}>')
                mime_img.add_header('Content-Disposition', 'inline', filename=f'{cid}.png')
                message.attach(mime_img)
        message.send(fail_silently=False)
        return True, "Email dispatched successfully"
    except Exception as exc:
        logger.warning("SMTP delivery failed for '%s' to '%s': %s", subject, recipient, exc)
        return False, str(exc)


def send_enrollment_confirmation_email(enrollment, force_retry=False):
    """
    Sends Enrollment Confirmation email to the student upon successful enrollment creation.
    Guarantees idempotency (avoids duplicates unless force_retry=True).
    Logs the delivery attempt to PaymentEmailLog and updates Enrollment.
    """
    if not enrollment:
        return False, "Enrollment object missing"

    # Idempotency check
    if enrollment.confirmation_email_sent and not force_retry:
        logger.info("Enrollment confirmation already sent for #%s. Skipping duplicate.", enrollment.enrollment_number)
        return True, "Enrollment confirmation already sent"

    recipient_email = (enrollment.student_email or '').strip()
    if not is_valid_email(recipient_email):
        err_msg = f"No valid student email for enrollment #{enrollment.enrollment_number}"
        enrollment.confirmation_email_error = err_msg
        enrollment.save(update_fields=['confirmation_email_error'])
        return False, err_msg

    course_name = enrollment.product.name if enrollment.product else "Course Program"
    course_desc = enrollment.product.description if enrollment.product else ""
    duration = "Scheduled Batch Program"
    if course_desc and "duration" in course_desc.lower():
        duration = course_desc

    subject = f"Enrollment Confirmed — {course_name}"
    student_id = f"STU-{enrollment.lead_id}" if enrollment.lead_id else f"STU-{enrollment.id}"

    counselor_name = ""
    counselor_phone = ""
    counselor_email = ""
    if enrollment.assigned_counselor:
        counselor_name = enrollment.assigned_counselor.get_full_name() or enrollment.assigned_counselor.username
        counselor_phone = getattr(enrollment.assigned_counselor, 'phone', '')
        counselor_email = enrollment.assigned_counselor.email

    branch_name = enrollment.branch.name if enrollment.branch else "Main Campus"
    campus_address = getattr(enrollment.branch, 'address', '') or branch_name
    enroll_year = enrollment.enrollment_date.year if enrollment.enrollment_date else 2026
    session = f"{enroll_year} – {enroll_year + 1}"

    context = {
        'company_name': getattr(settings, 'COMPANY_NAME', 'DIGIPANDA'),
        'student_name': enrollment.student_name,
        'student_id': student_id,
        'enrollment_number': enrollment.enrollment_number,
        'course_name': course_name,
        'course_duration': duration,
        'enrollment_date': enrollment.enrollment_date,
        'branch_name': branch_name,
        'campus_address': campus_address,
        'session': session,
        'portal_url': 'https://learn.digipanda.in',
        'total_payable': enrollment.total_payable,
        'gst_treatment': enrollment.get_gst_treatment_display(),
        'payment_plan': enrollment.get_payment_plan_display(),
        'counselor_name': counselor_name,
        'counselor_phone': counselor_phone,
        'counselor_email': counselor_email,
    }

    log_entry = PaymentEmailLog.objects.create(
        email_type='ENROLLMENT_CONFIRMATION',
        enrollment=enrollment,
        recipient_email=recipient_email,
        recipient_name=enrollment.student_name,
        subject=subject,
        body=f"Enrollment confirmed for {enrollment.student_name} (#{enrollment.enrollment_number})",
        status='PENDING'
    )

    success, msg = send_template_email(
        subject=subject,
        recipient=recipient_email,
        html_template='emails/enrollment_confirmation.html',
        text_template='emails/enrollment_confirmation.txt',
        context=context
    )

    if success:
        enrollment.confirmation_email_sent = True
        enrollment.confirmation_email_sent_at = timezone.now()
        enrollment.confirmation_email_error = ''
        enrollment.save(update_fields=['confirmation_email_sent', 'confirmation_email_sent_at', 'confirmation_email_error'])

        log_entry.status = 'SENT'
        log_entry.sent_at = timezone.now()
        log_entry.save(update_fields=['status', 'sent_at'])
        return True, "Enrollment confirmation email sent successfully"
    else:
        enrollment.confirmation_email_error = msg
        enrollment.save(update_fields=['confirmation_email_error'])

        log_entry.status = 'FAILED'
        log_entry.error_message = msg
        log_entry.save(update_fields=['status', 'error_message'])
        return False, msg


def send_payment_receipt_email(payment, force_retry=False):
    """
    Sends Payment Receipt email to the student once payment has been verified and committed.
    Guarantees idempotency (avoids duplicate receipts unless force_retry=True).
    Logs the delivery attempt to PaymentEmailLog and updates PaymentTransaction.
    """
    if not payment:
        return False, "Payment transaction missing"

    if payment.status not in (PaymentTransactionStatus.APPROVED, PaymentTransactionStatus.SUCCESS):
        return False, f"Cannot send receipt for non-successful / non-approved payment status: '{payment.status}'"

    # Idempotency check
    if payment.email_sent and not force_retry:
        logger.info("Payment receipt already sent for receipt %s. Skipping duplicate.", payment.receipt_number)
        return True, "Payment receipt already sent"

    enrollment = payment.enrollment
    recipient_email = (enrollment.student_email or '').strip()
    if not is_valid_email(recipient_email):
        err_msg = f"No valid student email for receipt #{payment.receipt_number}"
        payment.email_error = err_msg
        payment.save(update_fields=['email_error'])
        return False, err_msg

    # Subject format: Payment Receipt — {{ enrollment_number }} — {{ transaction_reference }}
    ref_display = payment.transaction_reference.strip() if payment.transaction_reference else payment.receipt_number
    subject = f"Payment Receipt — {enrollment.enrollment_number} — {ref_display}"

    student_id = f"STU-{enrollment.lead_id}" if enrollment.lead_id else f"STU-{enrollment.id}"
    course_name = enrollment.product.name if enrollment.product else "Course Program"
    branch_name = enrollment.branch.name if enrollment.branch else "Main Campus"

    # Calculate previously paid before this payment
    # All approved payments for this enrollment before or with smaller ID
    prior_payments = enrollment.payments.filter(
        status__in=[PaymentTransactionStatus.APPROVED, PaymentTransactionStatus.SUCCESS],
        created_at__lt=payment.created_at
    ).exclude(id=payment.id)
    previously_paid = sum((p.amount for p in prior_payments), Decimal('0.00'))

    context = {
        'company_name': getattr(settings, 'COMPANY_NAME', 'DIGIPANDA'),
        'student_name': enrollment.student_name,
        'student_id': student_id,
        'enrollment_number': enrollment.enrollment_number,
        'course_name': course_name,
        'branch_name': branch_name,
        'receipt_number': payment.receipt_number,
        'transaction_reference': payment.transaction_reference,
        'payment_date': payment.payment_date,
        'payment_method': payment.get_payment_method_display(),
        'amount_received': payment.amount,
        'total_course_fee': enrollment.total_payable,
        'previously_paid': previously_paid,
        'total_paid_to_date': enrollment.total_paid,
        'outstanding_balance': enrollment.outstanding_balance,
        'gst_treatment': enrollment.get_gst_treatment_display(),
        'tax_rate': enrollment.tax_rate,
        'taxable_amount': enrollment.taxable_amount,
        'tax_amount': enrollment.tax_amount,
        'next_installment_due_date': enrollment.next_installment_date,
    }

    log_entry = PaymentEmailLog.objects.create(
        email_type='PAYMENT_CONFIRMATION',
        enrollment=enrollment,
        payment=payment,
        installment=payment.installment,
        recipient_email=recipient_email,
        recipient_name=enrollment.student_name,
        subject=subject,
        body=f"Payment receipt #{payment.receipt_number} for ₹{payment.amount}",
        status='PENDING'
    )

    # Attach official PDF receipt and inline QR code
    attachments = []
    inline_images = []
    try:
        from leads.views_enrollment import generate_receipt_pdf, get_receipt_context
        from django.test import RequestFactory
        factory = RequestFactory()
        req = factory.get('/')
        pdf_ctx = get_receipt_context(req, payment)
        context.update(pdf_ctx)

        qr_png_bytes = pdf_ctx.get('qr_png_bytes')
        if qr_png_bytes:
            inline_images.append(('receipt_qr_code', qr_png_bytes, 'image/png'))

        pdf_bytes = generate_receipt_pdf(pdf_ctx)
        if pdf_bytes:
            filename = f"DigiPanda_Receipt_{payment.receipt_number}.pdf"
            attachments.append((filename, pdf_bytes, "application/pdf"))
    except Exception as e:
        logger.warning("Could not generate PDF attachment for receipt %s: %s", payment.receipt_number, e)

    success, msg = send_template_email(
        subject=subject,
        recipient=recipient_email,
        html_template='emails/payment_receipt.html',
        text_template='emails/payment_receipt.txt',
        context=context,
        attachments=attachments,
        inline_images=inline_images
    )

    if success:
        payment.email_sent = True
        payment.email_sent_at = timezone.now()
        payment.email_error = ''
        payment.save(update_fields=['email_sent', 'email_sent_at', 'email_error'])

        log_entry.status = 'SENT'
        log_entry.sent_at = timezone.now()
        log_entry.save(update_fields=['status', 'sent_at'])
        return True, "Payment receipt sent successfully"
    else:
        payment.email_error = msg
        payment.save(update_fields=['email_error'])

        log_entry.status = 'FAILED'
        log_entry.error_message = msg
        log_entry.save(update_fields=['status', 'error_message'])
        return False, msg


def send_installment_reminder_email(installment, reminder_type='DUE_REMINDER', force_retry=False):
    """
    Sends an installment reminder email to the student.
    reminder_type can be:
      - UPCOMING_REMINDER: Upcoming installment (e.g. 7 days or 1 day before due)
      - DUE_REMINDER: Due date (today)
      - OVERDUE_REMINDER: Overdue installment
    Guarantees:
      - Only sent if remaining_balance > 0 and enrollment is not fully paid.
      - Rechecks balance immediately before dispatch.
    """
    if not installment:
        return False, "Installment missing"

    enrollment = installment.enrollment
    if enrollment.status in ['Cancelled', 'Dropout']:
        return False, f"Enrollment #{enrollment.enrollment_number} is {enrollment.status}; skipping reminder"

    # Recheck current balance
    if installment.remaining_balance <= Decimal('0.00') or enrollment.outstanding_balance <= Decimal('0.00'):
        return False, f"Installment #{installment.installment_number} or enrollment is already fully paid"

    recipient_email = (enrollment.student_email or '').strip()
    if not is_valid_email(recipient_email):
        return False, f"No valid student email for installment #{installment.id}"

    today = timezone.localdate()
    is_overdue = installment.due_date < today

    # Idempotency check for this installment & reminder type today
    if not force_retry:
        recent_sent = PaymentEmailLog.objects.filter(
            installment=installment,
            email_type=reminder_type,
            status='SENT',
            sent_at__date=today
        ).exists()
        if recent_sent:
            return True, f"{reminder_type} already sent today for installment #{installment.installment_number}"

    course_name = enrollment.product.name if enrollment.product else "Course Program"
    student_id = f"STU-{enrollment.lead_id}" if enrollment.lead_id else f"STU-{enrollment.id}"
    branch_name = enrollment.branch.name if enrollment.branch else "Main Campus"

    today = timezone.localdate()
    is_overdue = installment.due_date < today
    is_due_today = installment.due_date == today
    days_diff = (installment.due_date - today).days

    if is_overdue:
        days_remaining = f"{abs(days_diff)} days overdue"
        days_overdue = abs(days_diff)
        headline = "Your Installment is Overdue"
        pill_text = "Overdue Fee Notice"
    elif is_due_today:
        days_remaining = "Due Today"
        days_overdue = 0
        headline = "Your Installment is Due Today"
        pill_text = "Payment Due Today"
    else:
        days_remaining = f"{days_diff} days"
        days_overdue = 0
        headline = "Your Next Installment is Due Soon"
        pill_text = "Fee Payment Reminder"

    subject = f"Fee Payment Reminder — {course_name}"

    context = {
        'company_name': getattr(settings, 'COMPANY_NAME', 'DIGIPANDA'),
        'student_name': enrollment.student_name,
        'student_id': student_id,
        'enrollment_number': enrollment.enrollment_number,
        'course_name': course_name,
        'branch_name': branch_name,
        'installment_number': installment.installment_number,
        'due_date': installment.due_date,
        'installment_amount': installment.scheduled_amount,
        'amount_already_paid': installment.amount_paid,
        'remaining_installment_balance': installment.remaining_balance,
        'total_outstanding_balance': enrollment.outstanding_balance,
        'amount_due': installment.remaining_balance,
        'outstanding_balance': enrollment.outstanding_balance,
        'days_remaining': days_remaining,
        'days_overdue': days_overdue,
        'headline': headline,
        'pill_text': pill_text,
        'is_due_today': is_due_today,
        'payment_status': installment.get_status_display(),
        'is_overdue': is_overdue,
        'accounts_phone': getattr(enrollment.branch, 'phone', '') if enrollment.branch else '+91 98765 43210',
        'accounts_email': getattr(settings, 'DEFAULT_FROM_EMAIL', 'support@digipanda.in'),
        'payment_url': 'https://pay.digipanda.in',
    }

    log_entry = PaymentEmailLog.objects.create(
        email_type=reminder_type,
        enrollment=enrollment,
        installment=installment,
        recipient_email=recipient_email,
        recipient_name=enrollment.student_name,
        subject=subject,
        body=f"Installment #{installment.installment_number} fee reminder for {enrollment.student_name} (Due: {installment.due_date})",
        status='PENDING'
    )

    success, msg = send_template_email(
        subject=subject,
        recipient=recipient_email,
        html_template='emails/installment_reminder.html',
        text_template='emails/installment_reminder.txt',
        context=context
    )

    if success:
        if reminder_type == 'UPCOMING_REMINDER':
            installment.upcoming_reminder_sent = True
            installment.upcoming_reminder_sent_at = timezone.now()
        elif reminder_type == 'DUE_REMINDER':
            installment.due_reminder_sent = True
            installment.due_reminder_sent_at = timezone.now()
        elif reminder_type == 'OVERDUE_REMINDER':
            installment.overdue_reminder_sent = True
            installment.overdue_reminder_sent_at = timezone.now()
        installment.save(update_fields=[
            'upcoming_reminder_sent', 'upcoming_reminder_sent_at',
            'due_reminder_sent', 'due_reminder_sent_at',
            'overdue_reminder_sent', 'overdue_reminder_sent_at',
            'updated_at'
        ])

        log_entry.status = 'SENT'
        log_entry.sent_at = timezone.now()
        log_entry.save(update_fields=['status', 'sent_at'])
        return True, f"{reminder_type} sent successfully"
    else:
        log_entry.status = 'FAILED'
        log_entry.error_message = msg
        log_entry.save(update_fields=['status', 'error_message'])
        return False, msg


def process_installment_reminders_batch(target_date=None):
    """
    Evaluates all active installments and sends reminders according to the configurable schedule:
    - 7 days before due date
    - 1 day before due date
    - On the due date (today)
    - 3 days after due date (overdue)
    - Weekly afterward (every 7 days while overdue)

    Processed in safe batches. Returns a summary dict of counts.
    """
    today = target_date or timezone.localdate()
    seven_days_ahead = today + timedelta(days=7)
    one_day_ahead = today + timedelta(days=1)
    three_days_ago = today - timedelta(days=3)

    summary = {
        'upcoming_7_days': 0,
        'upcoming_1_day': 0,
        'due_today': 0,
        'overdue_3_days': 0,
        'overdue_weekly': 0,
        'errors': 0,
    }

    # Base query: installments with outstanding balances in active enrollments
    active_installments = Installment.objects.filter(
        remaining_balance__gt=Decimal('0.00'),
        enrollment__outstanding_balance__gt=Decimal('0.00')
    ).exclude(
        enrollment__status__in=['Cancelled', 'Dropout']
    ).select_related('enrollment', 'enrollment__product', 'enrollment__branch')

    # 1. Seven Days Before Due Date
    qs_7d = active_installments.filter(due_date=seven_days_ahead)
    for inst in qs_7d:
        # Check if already sent 7d reminder
        if not PaymentEmailLog.objects.filter(installment=inst, email_type='UPCOMING_REMINDER', sent_at__date=today).exists():
            success, _ = send_installment_reminder_email(inst, reminder_type='UPCOMING_REMINDER')
            if success:
                summary['upcoming_7_days'] += 1
            else:
                summary['errors'] += 1

    # 2. One Day Before Due Date
    qs_1d = active_installments.filter(due_date=one_day_ahead)
    for inst in qs_1d:
        if not PaymentEmailLog.objects.filter(installment=inst, email_type='UPCOMING_REMINDER', sent_at__date=today).exists():
            success, _ = send_installment_reminder_email(inst, reminder_type='UPCOMING_REMINDER')
            if success:
                summary['upcoming_1_day'] += 1
            else:
                summary['errors'] += 1

    # 3. On Due Date (Today)
    qs_today = active_installments.filter(due_date=today)
    for inst in qs_today:
        if not PaymentEmailLog.objects.filter(installment=inst, email_type='DUE_REMINDER', sent_at__date=today).exists():
            success, _ = send_installment_reminder_email(inst, reminder_type='DUE_REMINDER')
            if success:
                summary['due_today'] += 1
            else:
                summary['errors'] += 1

    # 4. Three Days Overdue
    qs_3d_overdue = active_installments.filter(due_date=three_days_ago)
    for inst in qs_3d_overdue:
        if not PaymentEmailLog.objects.filter(installment=inst, email_type='OVERDUE_REMINDER', sent_at__date=today).exists():
            success, _ = send_installment_reminder_email(inst, reminder_type='OVERDUE_REMINDER')
            if success:
                summary['overdue_3_days'] += 1
            else:
                summary['errors'] += 1

    # 5. Overdue Weekly (due_date < three_days_ago, check if >= 7 days since last overdue email)
    qs_weekly = active_installments.filter(due_date__lt=three_days_ago)
    for inst in qs_weekly:
        last_log = PaymentEmailLog.objects.filter(
            installment=inst,
            email_type='OVERDUE_REMINDER',
            status='SENT'
        ).order_by('-sent_at').first()

        should_send = False
        if not last_log:
            should_send = True
        elif last_log.sent_at and (today - last_log.sent_at.date()).days >= 7:
            should_send = True

        if should_send:
            success, _ = send_installment_reminder_email(inst, reminder_type='OVERDUE_REMINDER')
            if success:
                summary['overdue_weekly'] += 1
            else:
                summary['errors'] += 1

    return summary

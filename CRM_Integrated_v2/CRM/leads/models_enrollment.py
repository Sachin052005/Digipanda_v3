from decimal import Decimal, ROUND_HALF_UP
from django.db import models
from django.conf import settings
from django.utils import timezone


class GSTTreatment(models.TextChoices):
    INCLUSIVE = 'INCLUSIVE', 'Inclusive of GST'
    EXCLUSIVE = 'EXCLUSIVE', 'Exclusive of GST'


class PaymentPlan(models.TextChoices):
    FULL_PAYMENT = 'FULL_PAYMENT', 'Full Payment'
    SPLIT_PAYMENT = 'SPLIT_PAYMENT', 'Split Payment / Installments'


class InstallmentMethod(models.TextChoices):
    MANUAL = 'MANUAL', 'Manual Installments'
    AUTOMATIC = 'AUTOMATIC', 'Automatic Installments'


class EnrollmentStatus(models.TextChoices):
    ACTIVE = 'Active', 'Active'
    COMPLETED = 'Completed', 'Completed'
    CANCELLED = 'Cancelled', 'Cancelled'
    DROPOUT = 'Dropout', 'Dropout'


class EnrollmentPaymentStatus(models.TextChoices):
    PENDING = 'Pending', 'Pending'
    PARTIALLY_PAID = 'Partially Paid', 'Partially Paid'
    FULLY_PAID = 'Fully Paid', 'Fully Paid'
    OVERDUE = 'Overdue', 'Overdue'


class InstallmentStatus(models.TextChoices):
    UPCOMING = 'Upcoming', 'Upcoming'
    DUE = 'Due', 'Due'
    PARTIALLY_PAID = 'Partially Paid', 'Partially Paid'
    PAID = 'Paid', 'Paid'
    OVERDUE = 'Overdue', 'Overdue'


class PaymentMethod(models.TextChoices):
    CASH = 'Cash', 'Cash'
    UPI = 'UPI', 'UPI'
    BANK_TRANSFER = 'Bank Transfer', 'Bank Transfer / NEFT'
    ONLINE = 'Online', 'Online Gateway'
    CARD = 'Card', 'Credit / Debit Card'
    CHEQUE = 'Cheque', 'Cheque / DD'


class PaymentTransactionStatus(models.TextChoices):
    SUCCESS = 'Success', 'Success'
    PENDING = 'Pending', 'Pending'
    FAILED = 'Failed', 'Failed'
    REFUNDED = 'Refunded', 'Refunded'


class Enrollment(models.Model):
    """
    Student Enrollment record directly linked to a CRM Lead.
    Preserves original Lead ID, source, channel, and assignment history.
    """
    lead = models.OneToOneField(
        'leads.Lead',
        on_delete=models.CASCADE,
        related_name='enrollment',
        help_text="Original CRM Lead this enrollment was generated from"
    )
    enrollment_number = models.CharField(max_length=60, unique=True, db_index=True)

    # Student personal information (mirrored/synced from Lead)
    student_name = models.CharField(max_length=150)
    student_phone = models.CharField(max_length=20, db_index=True)
    student_email = models.EmailField(blank=True, default='')

    # Program & Assignment
    product = models.ForeignKey(
        'products.Product',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='enrollments',
        help_text="Enrolled Course / Program"
    )
    branch = models.ForeignKey(
        'branches.Branch',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='enrollments'
    )
    assigned_counselor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='counselor_enrollments',
        limit_choices_to={'role': 'COUNSELOR'}
    )

    # Dates
    enrollment_date = models.DateField(default=timezone.now)
    course_start_date = models.DateField(null=True, blank=True)

    # Financial & GST details
    base_course_fee = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'), help_text="Entered fee")
    gst_treatment = models.CharField(
        max_length=20,
        choices=GSTTreatment.choices,
        default=GSTTreatment.INCLUSIVE,
        help_text="Course Fee GST Treatment (Mandatory)"
    )
    tax_rate = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal('18.00'), help_text="Applicable GST rate percentage")
    taxable_amount = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    tax_amount = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'), help_text="Calculated GST component")
    total_payable = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'), help_text="Final payable course fee")

    # Payment Plan & Installments
    payment_plan = models.CharField(
        max_length=20,
        choices=PaymentPlan.choices,
        default=PaymentPlan.FULL_PAYMENT
    )
    installment_method = models.CharField(
        max_length=20,
        choices=InstallmentMethod.choices,
        blank=True,
        default='',
        help_text="Manual or Automatic scheduling for Split Payment"
    )
    installment_count = models.PositiveIntegerField(default=1)

    # Balances & Status
    total_paid = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    outstanding_balance = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    next_installment_date = models.DateField(null=True, blank=True)

    status = models.CharField(
        max_length=20,
        choices=EnrollmentStatus.choices,
        default=EnrollmentStatus.ACTIVE
    )
    payment_status = models.CharField(
        max_length=20,
        choices=EnrollmentPaymentStatus.choices,
        default=EnrollmentPaymentStatus.PENDING
    )

    notes = models.TextField(blank=True, default='')

    # Email notification tracking
    confirmation_email_sent = models.BooleanField(default=False)
    confirmation_email_sent_at = models.DateTimeField(null=True, blank=True)
    confirmation_email_error = models.TextField(blank=True, default='')

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='created_enrollments'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.enrollment_number} - {self.student_name} ({self.status})"

    @classmethod
    def get_default_gst_rate(cls):
        """
        Retrieves the globally configured default GST tax rate from Django settings.
        Defaults to 18.00% if not configured.
        """
        rate_val = getattr(settings, 'DEFAULT_GST_RATE', '18.00')
        try:
            return Decimal(str(rate_val)).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
        except Exception:
            return Decimal('18.00')

    @classmethod
    def calculate_gst_breakdown(cls, base_fee, treatment, tax_rate=None):
        """
        Pure Decimal calculation for GST breakdown according to treatment rules:
        - INCLUSIVE: entered fee includes GST -> taxable = fee / (1 + r/100), tax = fee - taxable, total = entered fee
        - EXCLUSIVE: entered fee excludes GST -> taxable = fee, tax = fee * (r/100), total = taxable + tax
        Returns a complete dictionary with base_course_fee, gst_treatment, tax_rate, taxable_amount, tax_amount, total_payable.
        """
        if tax_rate is None or str(tax_rate).strip() == '':
            tax_rate = cls.get_default_gst_rate()
        else:
            tax_rate = Decimal(str(tax_rate)).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)

        base_fee = Decimal(str(base_fee or '0.00')).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
        rate_fraction = tax_rate / Decimal('100')

        if treatment == GSTTreatment.INCLUSIVE:
            taxable = (base_fee / (Decimal('1') + rate_fraction)).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
            tax = (base_fee - taxable).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
            total = base_fee.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
        else:
            taxable = base_fee.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
            tax = (taxable * rate_fraction).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
            total = (taxable + tax).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)

        return {
            'base_course_fee': base_fee,
            'gst_treatment': treatment,
            'tax_rate': tax_rate,
            'taxable_amount': taxable,
            'tax_amount': tax,
            'total_payable': total,
        }

    @classmethod
    def calculate_installment_breakdown(cls, total_payable, installment_count, start_date=None):
        """
        Splits total_payable across installment_count equal installments using pure Decimal arithmetic.
        Any fractional rounding paise/cents discrepancy is absorbed by the final installment.
        Also computes projected due dates (spaced 30 days apart, starting from start_date).
        """
        from datetime import timedelta
        total = Decimal(str(total_payable or '0.00')).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
        try:
            count = max(1, int(installment_count))
        except (ValueError, TypeError):
            count = 1

        if not start_date:
            current_due = timezone.localdate()
        elif isinstance(start_date, str):
            try:
                current_due = timezone.datetime.strptime(start_date, '%Y-%m-%d').date()
            except Exception:
                current_due = timezone.localdate()
        else:
            current_due = start_date

        base_amt = (total / Decimal(str(count))).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
        total_base = base_amt * Decimal(str(count))
        remainder_diff = total - total_base

        schedule = []
        for i in range(1, count + 1):
            amt = base_amt
            if i == count:
                amt += remainder_diff  # Absorb rounding discrepancy on final installment

            schedule.append({
                'installment_number': i,
                'amount': amt.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP),
                'due_date': current_due.strftime('%Y-%m-%d'),
                'formatted_due_date': current_due.strftime('%d %b %Y'),
            })
            current_due = current_due + timedelta(days=30)

        return schedule

    def update_financials(self):
        """
        Recalculates total paid, outstanding balance, next installment date,
        and overall payment status from actual records.
        """
        paid = self.payments.filter(status=PaymentTransactionStatus.SUCCESS).aggregate(
            total=models.Sum('amount')
        )['total'] or Decimal('0.00')

        self.total_paid = paid.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
        remaining = self.total_payable - self.total_paid
        self.outstanding_balance = max(Decimal('0.00'), remaining.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP))

        if self.outstanding_balance <= Decimal('0.00') and self.total_payable > Decimal('0.00'):
            self.payment_status = EnrollmentPaymentStatus.FULLY_PAID
        elif self.total_paid > Decimal('0.00'):
            self.payment_status = EnrollmentPaymentStatus.PARTIALLY_PAID
        else:
            self.payment_status = EnrollmentPaymentStatus.PENDING

        # Check installments
        today = timezone.localdate()
        next_inst = self.installments.filter(status__in=[InstallmentStatus.UPCOMING, InstallmentStatus.DUE, InstallmentStatus.PARTIALLY_PAID]).order_by('due_date').first()
        self.next_installment_date = next_inst.due_date if next_inst else None

        # Check for overdue
        if self.installments.filter(due_date__lt=today, status__in=[InstallmentStatus.DUE, InstallmentStatus.PARTIALLY_PAID, InstallmentStatus.OVERDUE]).exists():
            if self.payment_status != EnrollmentPaymentStatus.FULLY_PAID:
                self.payment_status = EnrollmentPaymentStatus.OVERDUE

        self.save(update_fields=['total_paid', 'outstanding_balance', 'payment_status', 'next_installment_date', 'updated_at'])


class Installment(models.Model):
    """
    Installment in a split-payment schedule.
    """
    enrollment = models.ForeignKey(
        Enrollment,
        on_delete=models.CASCADE,
        related_name='installments'
    )
    installment_number = models.PositiveIntegerField()
    scheduled_amount = models.DecimalField(max_digits=12, decimal_places=2)
    due_date = models.DateField(db_index=True)
    amount_paid = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    remaining_balance = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))

    status = models.CharField(
        max_length=20,
        choices=InstallmentStatus.choices,
        default=InstallmentStatus.UPCOMING,
        db_index=True
    )
    notes = models.CharField(max_length=255, blank=True, default='')

    # Reminder Tracking (Idempotency)
    upcoming_reminder_sent = models.BooleanField(default=False)
    upcoming_reminder_sent_at = models.DateTimeField(null=True, blank=True)
    due_reminder_sent = models.BooleanField(default=False)
    due_reminder_sent_at = models.DateTimeField(null=True, blank=True)
    overdue_reminder_sent = models.BooleanField(default=False)
    overdue_reminder_sent_at = models.DateTimeField(null=True, blank=True)

    last_updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='updated_installments'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['installment_number']
        unique_together = ('enrollment', 'installment_number')

    def __str__(self):
        return f"{self.enrollment.enrollment_number} - Inst #{self.installment_number}: ₹{self.scheduled_amount} due {self.due_date}"

    def update_balance(self):
        paid = self.payments.filter(status=PaymentTransactionStatus.SUCCESS).aggregate(
            total=models.Sum('amount')
        )['total'] or Decimal('0.00')

        self.amount_paid = paid.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
        rem = self.scheduled_amount - self.amount_paid
        self.remaining_balance = max(Decimal('0.00'), rem.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP))

        today = timezone.localdate()
        if self.remaining_balance <= Decimal('0.00'):
            self.status = InstallmentStatus.PAID
        elif self.amount_paid > Decimal('0.00'):
            if self.due_date < today:
                self.status = InstallmentStatus.OVERDUE
            else:
                self.status = InstallmentStatus.PARTIALLY_PAID
        elif self.due_date < today:
            self.status = InstallmentStatus.OVERDUE
        elif self.due_date == today:
            self.status = InstallmentStatus.DUE
        else:
            self.status = InstallmentStatus.UPCOMING

        self.save(update_fields=['amount_paid', 'remaining_balance', 'status', 'updated_at'])


class PaymentTransaction(models.Model):
    """
    Append-only record of money received against an enrollment.
    """
    enrollment = models.ForeignKey(
        Enrollment,
        on_delete=models.CASCADE,
        related_name='payments'
    )
    installment = models.ForeignKey(
        Installment,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='payments'
    )
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    payment_date = models.DateTimeField(default=timezone.now)
    payment_method = models.CharField(
        max_length=30,
        choices=PaymentMethod.choices,
        default=PaymentMethod.UPI
    )
    transaction_reference = models.CharField(max_length=100, blank=True, default='', db_index=True)
    receipt_number = models.CharField(max_length=100, unique=True, db_index=True)
    status = models.CharField(
        max_length=20,
        choices=PaymentTransactionStatus.choices,
        default=PaymentTransactionStatus.SUCCESS
    )
    notes = models.TextField(blank=True, default='')

    recorded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='recorded_payments'
    )

    # Email notification tracking
    email_sent = models.BooleanField(default=False)
    email_sent_at = models.DateTimeField(null=True, blank=True)
    email_error = models.TextField(blank=True, default='')

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-payment_date', '-created_at']

    def __str__(self):
        return f"Receipt {self.receipt_number} - ₹{self.amount} ({self.payment_method}) for {self.enrollment.student_name}"


class InstallmentScheduleHistory(models.Model):
    """
    Audit log of manual/automatic changes to installment schedules.
    """
    enrollment = models.ForeignKey(
        Enrollment,
        on_delete=models.CASCADE,
        related_name='schedule_history'
    )
    installment = models.ForeignKey(
        Installment,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='audit_history'
    )
    action = models.CharField(max_length=50)  # Created, Updated Amount, Updated Due Date, Re-scheduled
    previous_value = models.JSONField(default=dict, blank=True)
    new_value = models.JSONField(default=dict, blank=True)
    reason = models.TextField(blank=True, default='')
    changed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='+'
    )
    timestamp = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-timestamp']

    def __str__(self):
        return f"{self.action} on {self.enrollment.enrollment_number} at {self.timestamp}"


class PaymentEmailLog(models.Model):
    """
    Durable log and retry queue for student payment and installment emails.
    """
    EMAIL_TYPES = [
        ('ENROLLMENT_CONFIRMATION', 'Enrollment Confirmation'),
        ('PAYMENT_CONFIRMATION', 'Payment Confirmation'),
        ('UPCOMING_REMINDER', 'Upcoming Installment Reminder'),
        ('DUE_REMINDER', 'Due Date Installment Reminder'),
        ('OVERDUE_REMINDER', 'Overdue Installment Reminder'),
    ]
    STATUS_CHOICES = [
        ('SENT', 'Sent'),
        ('FAILED', 'Failed'),
        ('PENDING', 'Pending Retry'),
    ]

    email_type = models.CharField(max_length=40, choices=EMAIL_TYPES)
    enrollment = models.ForeignKey(Enrollment, on_delete=models.CASCADE, related_name='email_logs')
    payment = models.ForeignKey(PaymentTransaction, on_delete=models.SET_NULL, null=True, blank=True, related_name='email_logs')
    installment = models.ForeignKey(Installment, on_delete=models.SET_NULL, null=True, blank=True, related_name='email_logs')

    recipient_email = models.EmailField()
    recipient_name = models.CharField(max_length=150)
    subject = models.CharField(max_length=255)
    body = models.TextField()

    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PENDING')
    error_message = models.TextField(blank=True, default='')
    attempts = models.PositiveIntegerField(default=1)

    sent_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.email_type} to {self.recipient_email} [{self.status}]"

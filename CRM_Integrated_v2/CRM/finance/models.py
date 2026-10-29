import os
from decimal import Decimal
from django.db import models
from django.conf import settings
from django.utils import timezone


class ExpenseCategory(models.TextChoices):
    MARKETING = 'Marketing', 'Marketing'
    SALES = 'Sales', 'Sales'
    TRAINING = 'Training', 'Training'
    OPERATION = 'Operation', 'Operation'
    FIXED_ASSETS = 'Fixed Assets', 'Fixed Assets'


class ExpenseStatus(models.TextChoices):
    PENDING = 'PENDING', 'Pending Approval'
    APPROVED = 'APPROVED', 'Approved'
    REJECTED = 'REJECTED', 'Rejected'


class Expense(models.Model):
    branch = models.ForeignKey(
        'branches.Branch',
        on_delete=models.CASCADE,
        related_name='expenses'
    )
    category = models.CharField(
        max_length=50,
        choices=ExpenseCategory.choices,
        default=ExpenseCategory.OPERATION
    )
    sub_category = models.CharField(
        max_length=100,
        help_text="e.g. Ad, Office Rent, Utilities, Hardware, Software"
    )
    paid_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='recorded_expenses'
    )
    paid_by_name = models.CharField(max_length=150, blank=True, default='')
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    description = models.TextField(blank=True)
    paid_to = models.CharField(
        max_length=150,
        help_text="Vendor or recipient name"
    )
    expense_date = models.DateField(default=timezone.localdate)
    proof = models.FileField(
        upload_to='finance/expenses/%Y/%m/',
        blank=True,
        null=True,
        help_text="Receipt, invoice or bill proof document"
    )
    status = models.CharField(
        max_length=20,
        choices=ExpenseStatus.choices,
        default=ExpenseStatus.PENDING
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='created_expenses'
    )
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='reviewed_expenses'
    )
    reviewed_at = models.DateTimeField(null=True, blank=True)
    rejection_reason = models.TextField(blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-expense_date', '-id']
        indexes = [
            models.Index(fields=['branch', 'expense_date']),
            models.Index(fields=['status', 'category']),
        ]

    def __str__(self):
        return f"{self.category} - {self.sub_category} (₹{self.amount})"


class BudgetForecast(models.Model):
    branch = models.ForeignKey(
        'branches.Branch',
        on_delete=models.CASCADE,
        related_name='budget_forecasts'
    )
    category = models.CharField(
        max_length=50,
        choices=ExpenseCategory.choices
    )
    month = models.PositiveSmallIntegerField(default=10)
    year = models.PositiveIntegerField(default=2026)
    forecasted_amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal('0.00')
    )
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('branch', 'category', 'month', 'year')
        ordering = ['category']

    def __str__(self):
        return f"{self.branch} - {self.category} ({self.month}/{self.year}): ₹{self.forecasted_amount}"


class BranchOpeningBalance(models.Model):
    branch = models.ForeignKey(
        'branches.Branch',
        on_delete=models.CASCADE,
        related_name='opening_balances'
    )
    owner_name = models.CharField(
        max_length=100,
        help_text="e.g. TP-VEL-BranchHead, TP-Velachery"
    )
    opening_balance = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal('0.00')
    )
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('branch', 'owner_name')
        ordering = ['owner_name']

    def __str__(self):
        return f"{self.owner_name} ({self.branch}): ₹{self.opening_balance}"


class InternalTransferStatus(models.TextChoices):
    PENDING_APPROVAL = 'PENDING_APPROVAL', 'Pending Paying Branch Approval'
    APPROVED_PENDING_RECEIPT = 'APPROVED_PENDING_RECEIPT', 'Approved, Pending Receipt'
    COMPLETED = 'COMPLETED', 'Completed'
    REJECTED = 'REJECTED', 'Rejected'


class InternalTransfer(models.Model):
    transfer_code = models.CharField(max_length=50, unique=True)
    from_branch = models.ForeignKey(
        'branches.Branch',
        on_delete=models.CASCADE,
        related_name='transfers_sent'
    )
    to_branch = models.ForeignKey(
        'branches.Branch',
        on_delete=models.CASCADE,
        related_name='transfers_received'
    )
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    reason = models.CharField(max_length=150, help_text="Reason for transfer")
    notes = models.TextField(blank=True, default='')
    delivery_challan_number = models.CharField(max_length=100, blank=True, default='')
    delivery_challan_doc = models.FileField(
        upload_to='finance/challans/%Y/%m/',
        blank=True,
        null=True
    )
    status = models.CharField(
        max_length=30,
        choices=InternalTransferStatus.choices,
        default=InternalTransferStatus.PENDING_APPROVAL
    )
    initiated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='initiated_transfers'
    )
    paying_approver = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='paying_approved_transfers'
    )
    paying_approved_at = models.DateTimeField(null=True, blank=True)
    receiving_acknowledger = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='acknowledged_transfers'
    )
    received_at = models.DateTimeField(null=True, blank=True)
    rejection_reason = models.TextField(blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.transfer_code}: {self.from_branch} -> {self.to_branch} (₹{self.amount})"


class RenewalAlertType(models.TextChoices):
    RENEWAL = 'Renewal', 'Renewal'
    DISBURSEMENT = 'Disbursement', 'Disbursement'


class RenewalAlertStatus(models.TextChoices):
    ACTIVE = 'Active', 'Active'
    DUE_TODAY = 'Due Today', 'Due Today'
    OVERDUE = 'Overdue', 'Overdue'
    DONE = 'Done', 'Done'


class RenewalAlert(models.Model):
    branch = models.ForeignKey(
        'branches.Branch',
        on_delete=models.CASCADE,
        related_name='renewal_alerts'
    )
    name = models.CharField(max_length=150, help_text="e.g. Office Rent, Electricity Bill, CRM Subscriptions")
    alert_type = models.CharField(
        max_length=20,
        choices=RenewalAlertType.choices,
        default=RenewalAlertType.RENEWAL
    )
    repeat_every_months = models.PositiveSmallIntegerField(default=1)
    due_date = models.DateField()
    alert_starts_days_before = models.PositiveSmallIntegerField(default=7)
    amount = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    notes = models.TextField(blank=True, default='')
    status = models.CharField(
        max_length=20,
        choices=RenewalAlertStatus.choices,
        default=RenewalAlertStatus.ACTIVE
    )
    contract_reference = models.CharField(max_length=100, blank=True, default='', help_text="Contract / Account number or policy ref")
    recipient_finance_head = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='finance_head_renewal_alerts'
    )
    recipient_branch_head = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='branch_head_renewal_alerts'
    )
    last_notified_date = models.DateField(null=True, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='created_renewal_alerts'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['due_date']

    def __str__(self):
        return f"{self.name} - {self.due_date} ({self.status})"

    @property
    def next_reminder_date(self):
        from datetime import timedelta
        if not self.due_date:
            return None
        return self.due_date - timedelta(days=self.alert_starts_days_before)

    def check_dynamic_status(self):
        today = timezone.localdate()
        if self.status == RenewalAlertStatus.DONE:
            return RenewalAlertStatus.DONE
        if self.due_date < today:
            return RenewalAlertStatus.OVERDUE
        if self.due_date == today:
            return RenewalAlertStatus.DUE_TODAY
        return RenewalAlertStatus.ACTIVE

    def advance_to_next_cycle(self):
        """
        Advances recurring alert to next cycle when marked done, or marks DONE if one-time.
        """
        if self.repeat_every_months and self.repeat_every_months > 0:
            import calendar
            from datetime import date
            cur_year = self.due_date.year
            cur_month = self.due_date.month
            cur_day = self.due_date.day
            
            new_month = cur_month + self.repeat_every_months
            year_add = (new_month - 1) // 12
            new_month = ((new_month - 1) % 12) + 1
            new_year = cur_year + year_add
            max_day = calendar.monthrange(new_year, new_month)[1]
            new_day = min(cur_day, max_day)
            
            self.due_date = date(new_year, new_month, new_day)
            self.status = RenewalAlertStatus.ACTIVE
            self.last_notified_date = None
        else:
            self.status = RenewalAlertStatus.DONE
        self.save()


class EmployeeEmploymentType(models.TextChoices):
    FULL_TIME = 'Full Time', 'Full Time'
    PROBATION = 'Probation', 'Probation'
    PART_TIME = 'Part Time', 'Part Time'
    CONTRACT = 'Contract', 'Contract'


class EmployeeStatus(models.TextChoices):
    PROBATION = 'Probation', 'Probation'
    ACTIVE = 'Active', 'Active'
    ON_HOLD = 'On Hold', 'On Hold'
    RESIGNED = 'Resigned', 'Resigned'


class EmployeeProfile(models.Model):
    employee_code = models.CharField(max_length=20, unique=True, help_text="e.g. EMP-0025")
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='employee_profile'
    )
    full_name = models.CharField(max_length=150)
    email = models.EmailField()
    phone = models.CharField(max_length=20, blank=True, default='')
    role_title = models.CharField(max_length=100, help_text="e.g. Branch Financial Head, Counsellor, Branch Head")
    department = models.CharField(max_length=100, default='General')
    branch = models.ForeignKey(
        'branches.Branch',
        on_delete=models.CASCADE,
        related_name='employees'
    )
    employment_type = models.CharField(
        max_length=20,
        choices=EmployeeEmploymentType.choices,
        default=EmployeeEmploymentType.FULL_TIME
    )
    status = models.CharField(
        max_length=20,
        choices=EmployeeStatus.choices,
        default=EmployeeStatus.PROBATION
    )
    basic_salary = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'))
    hra = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'))
    allowances = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'))
    pf_deduction = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'))
    esi_deduction = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'))
    professional_tax = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'))
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['employee_code']

    def __str__(self):
        return f"{self.employee_code} - {self.full_name} ({self.role_title})"

    @property
    def gross_salary(self):
        return self.basic_salary + self.hra + self.allowances

    @property
    def total_deductions(self):
        return self.pf_deduction + self.esi_deduction + self.professional_tax

    @property
    def net_salary(self):
        return max(Decimal('0.00'), self.gross_salary - self.total_deductions)


class PayrollRunStatus(models.TextChoices):
    DRAFT = 'Draft', 'Draft'
    PENDING_APPROVAL = 'Pending Approval', 'Pending Approval'
    APPROVED = 'Approved', 'Approved'
    PAID = 'Paid', 'Paid'


class PayrollRun(models.Model):
    run_number = models.CharField(max_length=50, unique=True, help_text="e.g. PR-2026-10-VEL")
    branch = models.ForeignKey(
        'branches.Branch',
        on_delete=models.CASCADE,
        related_name='payroll_runs'
    )
    month = models.PositiveSmallIntegerField(default=10)
    year = models.PositiveIntegerField(default=2026)
    period_start = models.DateField(null=True, blank=True)
    period_end = models.DateField(null=True, blank=True)
    total_gross = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    total_deductions = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    total_net = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    status = models.CharField(
        max_length=20,
        choices=PayrollRunStatus.choices,
        default=PayrollRunStatus.DRAFT
    )
    generated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='generated_payrolls'
    )
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='approved_payrolls'
    )
    paid_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-year', '-month', '-id']

    def __str__(self):
        return f"{self.run_number} - {self.branch} ({self.month}/{self.year}): ₹{self.total_net}"


class PayrollItem(models.Model):
    payroll_run = models.ForeignKey(
        PayrollRun,
        on_delete=models.CASCADE,
        related_name='items'
    )
    employee = models.ForeignKey(
        EmployeeProfile,
        on_delete=models.CASCADE,
        related_name='payroll_items'
    )
    gross_pay = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'))
    deductions = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'))
    net_pay = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'))
    is_deferred = models.BooleanField(
        default=False,
        help_text="If checked False, pay is deferred as a Salary Arrear"
    )
    remarks = models.CharField(max_length=255, blank=True, default='')

    def __str__(self):
        return f"{self.employee.full_name} in {self.payroll_run.run_number}: ₹{self.net_pay}"


class SalaryArrearSource(models.TextChoices):
    JOIN_MONTH_STUB = 'Join Month Stub', 'Join Month Stub'
    MANUAL_CORRECTION = 'Manual Correction', 'Manual Correction'
    DEFERRED_PAYROLL = 'Deferred Payroll', 'Deferred Payroll'


class SalaryArrearStatus(models.TextChoices):
    PENDING = 'Pending', 'Pending'
    FOLDED_IN_PAYROLL = 'Folded in Payroll', 'Folded in Payroll'


class SalaryArrear(models.Model):
    employee = models.ForeignKey(
        EmployeeProfile,
        on_delete=models.CASCADE,
        related_name='arrears'
    )
    period_label = models.CharField(max_length=50, help_text="e.g. September 2026")
    source = models.CharField(
        max_length=30,
        choices=SalaryArrearSource.choices,
        default=SalaryArrearSource.JOIN_MONTH_STUB
    )
    days_count = models.PositiveIntegerField(default=0)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    status = models.CharField(
        max_length=20,
        choices=SalaryArrearStatus.choices,
        default=SalaryArrearStatus.PENDING
    )
    folded_in_payroll = models.ForeignKey(
        PayrollRun,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='folded_arrears'
    )
    reason = models.TextField(blank=True, default='')
    requested_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='requested_arrears'
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.employee.full_name} - {self.period_label}: ₹{self.amount} ({self.status})"


class IncentiveStatus(models.TextChoices):
    IN_PROGRESS = 'In progress', 'In progress'
    AWAITING_RELEASE = 'Awaiting Release', 'Awaiting Release'
    RELEASED = 'Released', 'Released'
    NOT_REQUESTED = 'Not requested', 'Not requested'


class IncentiveRecord(models.Model):
    counselor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='incentive_records'
    )
    branch = models.ForeignKey(
        'branches.Branch',
        on_delete=models.CASCADE,
        related_name='incentives'
    )
    period_month = models.PositiveSmallIntegerField(default=10)
    period_year = models.PositiveIntegerField(default=2026)
    monthly_incentive = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'))
    weekly_incentive = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'))
    total_payout = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'))
    status = models.CharField(
        max_length=20,
        choices=IncentiveStatus.choices,
        default=IncentiveStatus.NOT_REQUESTED
    )
    details = models.CharField(max_length=255, blank=True, default='Month still running — releasable once it closes')
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='approved_incentives'
    )
    released_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('counselor', 'branch', 'period_month', 'period_year')
        ordering = ['-period_year', '-period_month', 'counselor__username']

    def __str__(self):
        return f"{self.counselor.username} ({self.period_month}/{self.period_year}): ₹{self.total_payout} ({self.status})"

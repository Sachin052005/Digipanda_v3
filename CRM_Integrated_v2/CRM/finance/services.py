import io
from decimal import Decimal, ROUND_HALF_UP
from datetime import datetime, time, date, timedelta
from django.db import transaction
from django.db.models import Sum, Count, Q
from django.utils import timezone
from django.core.exceptions import ValidationError

from accounts.models import User, UserRole
from branches.models import Branch
from leads.models import (
    Enrollment,
    Installment,
    PaymentTransaction,
    PaymentTransactionStatus,
    PaymentMethod,
    EnrollmentStatus,
)
from .models import (
    Expense,
    ExpenseCategory,
    ExpenseStatus,
    BudgetForecast,
    BranchOpeningBalance,
    InternalTransfer,
    InternalTransferStatus,
    RenewalAlert,
    RenewalAlertStatus,
    EmployeeProfile,
    PayrollRun,
    PayrollItem,
    PayrollRunStatus,
    SalaryArrear,
    SalaryArrearStatus,
    SalaryArrearSource,
    IncentiveRecord,
    IncentiveStatus,
)


def sanitize_for_excel(value):
    """Prevents formula injection in Excel/CSV exports."""
    if value is None:
        return ""
    val_str = str(value)
    if val_str and val_str[0] in ('=', '+', '-', '@', '\t', '\r'):
        return f"'{val_str}"
    return val_str


def get_finance_scope(user, requested_branch_id=None):
    """
    Enforces strict branch scoping:
    - Superadmin / Admin can view all branches or filter by requested_branch_id.
    - Finance Head is strictly constrained to user.branch_id.
    """
    from accounts.permissions import get_accessible_branch_ids
    accessible = get_accessible_branch_ids(user)

    if user.role == UserRole.FINANCE_HEAD:
        if user.branch_id:
            return [user.branch_id], user.branch_id
        return accessible, None

    if requested_branch_id and str(requested_branch_id).isdigit():
        b_id = int(requested_branch_id)
        if b_id in accessible:
            return [b_id], b_id

    return accessible, None


def get_finance_dashboard_metrics(branch_ids, start_dt=None, end_dt=None):
    """
    Computes all 8 authoritative financial metrics and breakdowns.
    Uses pure Decimal arithmetic and real database transactions.
    """
    today = timezone.localdate()
    if not start_dt:
        start_dt = timezone.make_aware(datetime.combine(today.replace(day=1), time.min))
    if not end_dt:
        end_dt = timezone.make_aware(datetime.combine(today, time.max))

    start_date = start_dt.date()
    end_date = end_dt.date()

    # 1. Collections (Approved Payments in range)
    pmt_qs = PaymentTransaction.objects.filter(
        enrollment__branch_id__in=branch_ids,
        status__in=[PaymentTransactionStatus.APPROVED, PaymentTransactionStatus.SUCCESS],
        payment_date__gte=start_dt,
        payment_date__lte=end_dt
    ).select_related('enrollment', 'enrollment__product')

    total_collection = pmt_qs.aggregate(s=Sum('amount'))['s'] or Decimal('0.00')

    # Total GST (Computed from enrollment GST tax rate on collections)
    # If inclusive/exclusive 18% GST:
    total_gst = Decimal('0.00')
    total_training = Decimal('0.00')
    total_placement = Decimal('0.00')

    for p in pmt_qs:
        enr = p.enrollment
        amt = p.amount or Decimal('0.00')
        if enr.tax_rate and enr.tax_rate > 0:
            if enr.gst_treatment == 'EXCLUSIVE':
                tax_share = (amt * (enr.tax_rate / Decimal('100.00'))).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
            else:
                # INCLUSIVE
                tax_share = (amt - (amt / (Decimal('1.00') + (enr.tax_rate / Decimal('100.00'))))).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
            total_gst += tax_share

        p_name = enr.product.name.lower() if enr.product else ''
        if 'placement' in p_name:
            total_placement += amt
        else:
            total_training += amt

    # 2. Approved Expenses in range
    exp_qs = Expense.objects.filter(
        branch_id__in=branch_ids,
        status=ExpenseStatus.APPROVED,
        expense_date__gte=start_date,
        expense_date__lte=end_date
    )
    total_expenses = exp_qs.aggregate(s=Sum('amount'))['s'] or Decimal('0.00')

    # 3. Balances
    balance = total_collection - total_expenses
    balance_after_gst = balance - total_gst
    other_income = Decimal('0.00')

    # 4. Collection Owner Summary (Opening + Income - Expense = Remaining)
    owners_data = []
    branches = Branch.objects.filter(id__in=branch_ids).order_by('name')
    for b in branches:
        # Branch opening balance
        op_obj = BranchOpeningBalance.objects.filter(branch=b, owner_name=f"TP-{b.name}").first()
        op_val = op_obj.opening_balance if op_obj else Decimal('0.00')

        b_income = PaymentTransaction.objects.filter(
            enrollment__branch=b,
            status__in=[PaymentTransactionStatus.APPROVED, PaymentTransactionStatus.SUCCESS],
            payment_date__gte=start_dt,
            payment_date__lte=end_dt
        ).aggregate(s=Sum('amount'))['s'] or Decimal('0.00')

        b_expense = Expense.objects.filter(
            branch=b,
            status=ExpenseStatus.APPROVED,
            expense_date__gte=start_date,
            expense_date__lte=end_date
        ).aggregate(s=Sum('amount'))['s'] or Decimal('0.00')

        rem = op_val + b_income - b_expense
        owners_data.append({
            'owner': f"TP-{b.name}",
            'opening': op_val,
            'income': b_income,
            'expense': b_expense,
            'balance': rem,
        })

    # 5. Collection by Payment Type Breakdown
    methods_data = []
    for method_choice in PaymentMethod.choices:
        m_val, m_label = method_choice
        m_amt = pmt_qs.filter(payment_method=m_val).aggregate(s=Sum('amount'))['s'] or Decimal('0.00')
        if m_amt > 0 or len(pmt_qs) == 0:
            methods_data.append({
                'method': m_label,
                'amount': m_amt
            })

    return {
        'total_collection': total_collection,
        'total_expenses': total_expenses,
        'balance': balance,
        'total_gst': total_gst,
        'balance_after_gst': balance_after_gst,
        'total_training': total_training,
        'total_placement': total_placement,
        'other_income': other_income,
        'owners_data': owners_data,
        'methods_data': methods_data,
        'pmt_count': pmt_qs.count(),
        'exp_count': exp_qs.count(),
    }


def get_pending_payments_breakdown(branch_ids, student_type=None, course_id=None, tier_filter=None, query=None):
    """
    Computes pending dues anchored on batch start dates and installment schedules.
    Categorizes into:
      Group 1: Initial Dues — paid below base fee (Upcoming <=2d, Due in 1w, Due in 2w, SLA breached, Suspension)
      Group 2: Balance Due — course not fully paid (Upcoming 30d+, 35d+, SLA breached, Suspension)
    """
    today = timezone.localdate()

    enrollments = Enrollment.objects.filter(
        branch_id__in=branch_ids,
        outstanding_balance__gt=Decimal('0.00')
    ).select_related('lead', 'product', 'branch', 'assigned_counselor')

    if student_type:
        enrollments = enrollments.filter(payment_plan=student_type)
    if course_id and str(course_id).isdigit():
        enrollments = enrollments.filter(product_id=int(course_id))
    if query:
        enrollments = enrollments.filter(
            Q(student_name__icontains=query) |
            Q(student_phone__icontains=query) |
            Q(enrollment_number__icontains=query)
        )

    # Classify each student
    initial_dues_list = []
    balance_dues_list = []

    # KPI counts & sums
    initial_dues_count = 0
    balance_dues_count = 0
    total_pending_amount = Decimal('0.00')

    # Sub-tier counters
    g1_upcoming_2d = 0
    g1_due_1w = 0
    g1_due_2w = 0
    g1_sla_breached = 0
    g1_suspension = 0

    g2_upcoming_30d = 0
    g2_35d_plus = 0
    g2_sla_breached = 0
    g2_suspension = 0

    for enr in enrollments:
        total_pending_amount += enr.outstanding_balance
        start_d = enr.course_start_date or enr.enrollment_date
        days_from_start = (today - start_d).days if start_d else 0
        base_fee = enr.base_course_fee or Decimal('0.00')

        is_below_base = (enr.total_paid < base_fee)

        if is_below_base:
            initial_dues_count += 1
            if days_from_start < -2:
                tier = 'Upcoming (batch in ≤2 days)'
                g1_upcoming_2d += 1
            elif -2 <= days_from_start <= 7:
                tier = 'Due in 1 week'
                g1_due_1w += 1
            elif 8 <= days_from_start <= 14:
                tier = 'Due in 2 weeks'
                g1_due_2w += 1
            elif 15 <= days_from_start <= 30:
                tier = 'SLA Breached'
                g1_sla_breached += 1
            else:
                tier = 'Student Suspension (LMS + WhatsApp)'
                g1_suspension += 1

            initial_dues_list.append({
                'enrollment': enr,
                'tier': tier,
                'days_from_start': days_from_start,
                'group': 'initial'
            })
        else:
            balance_dues_count += 1
            if days_from_start <= 30:
                tier = 'Upcoming (30 days +)'
                g2_upcoming_30d += 1
            elif 31 <= days_from_start <= 35:
                tier = '35 days +'
                g2_35d_plus += 1
            elif 36 <= days_from_start <= 45:
                tier = 'SLA Breached'
                g2_sla_breached += 1
            else:
                tier = 'Student Suspension (SMS + WhatsApp)'
                g2_suspension += 1

            balance_dues_list.append({
                'enrollment': enr,
                'tier': tier,
                'days_from_start': days_from_start,
                'group': 'balance'
            })

    total_count = initial_dues_count + balance_dues_count

    return {
        'total_pending_amount': total_pending_amount,
        'total_count': total_count,
        'initial_dues_count': initial_dues_count,
        'balance_dues_count': balance_dues_count,
        'g1_upcoming_2d': g1_upcoming_2d,
        'g1_due_1w': g1_due_1w,
        'g1_due_2w': g1_due_2w,
        'g1_sla_breached': g1_sla_breached,
        'g1_suspension': g1_suspension,
        'g2_upcoming_30d': g2_upcoming_30d,
        'g2_35d_plus': g2_35d_plus,
        'g2_sla_breached': g2_sla_breached,
        'g2_suspension': g2_suspension,
        'initial_dues_list': initial_dues_list,
        'balance_dues_list': balance_dues_list,
        'all_items': initial_dues_list + balance_dues_list
    }


def get_approvals_counts(branch_ids):
    """Returns active approval badge counts across all 5 categories."""
    p_count = PaymentTransaction.objects.filter(
        enrollment__branch_id__in=branch_ids,
        status=PaymentTransactionStatus.PENDING_VERIFICATION
    ).count()

    e_count = Expense.objects.filter(
        branch_id__in=branch_ids,
        status=ExpenseStatus.PENDING
    ).count()

    inc_count = IncentiveRecord.objects.filter(
        branch_id__in=branch_ids,
        status=IncentiveStatus.AWAITING_RELEASE
    ).count()

    pay_count = PayrollRun.objects.filter(
        branch_id__in=branch_ids,
        status=PayrollRunStatus.PENDING_APPROVAL
    ).count()

    return {
        'income_count': p_count,
        'expense_count': e_count,
        'other_income_count': 0,
        'incentive_count': inc_count,
        'payroll_count': pay_count,
        'total_active': p_count + e_count + inc_count + pay_count
    }


@transaction.atomic
def approve_expense(expense_id, user):
    """Safely approves a pending expense transaction."""
    exp = Expense.objects.select_for_update().get(id=expense_id)
    if exp.status == ExpenseStatus.APPROVED:
        return exp
    if exp.status != ExpenseStatus.PENDING:
        raise ValidationError(f"Cannot approve expense with status '{exp.status}'.")

    exp.status = ExpenseStatus.APPROVED
    exp.reviewed_by = user
    exp.reviewed_at = timezone.now()
    exp.rejection_reason = ''
    exp.save(update_fields=['status', 'reviewed_by', 'reviewed_at', 'rejection_reason'])
    return exp


@transaction.atomic
def reject_expense(expense_id, user, reason):
    """Safely rejects a pending expense transaction."""
    exp = Expense.objects.select_for_update().get(id=expense_id)
    if exp.status == ExpenseStatus.REJECTED:
        return exp
    exp.status = ExpenseStatus.REJECTED
    exp.reviewed_by = user
    exp.reviewed_at = timezone.now()
    exp.rejection_reason = str(reason or '').strip()
    exp.save(update_fields=['status', 'reviewed_by', 'reviewed_at', 'rejection_reason'])
    return exp


@transaction.atomic
def generate_payroll_run(branch, month, year, selected_emp_ids, user):
    """
    Generates a monthly payroll run for a branch.
    Snapshots employees' salary structures and statutory deductions.
    Unchecked employees have their net pay deferred as a SalaryArrear.
    """
    run_num = f"PR-{year}-{month:02d}-{branch.code if hasattr(branch, 'code') and branch.code else branch.name[:3].upper()}"

    # Delete draft if already exists
    PayrollRun.objects.filter(branch=branch, month=month, year=year, status=PayrollRunStatus.DRAFT).delete()

    run = PayrollRun.objects.create(
        run_number=run_num,
        branch=branch,
        month=month,
        year=year,
        status=PayrollRunStatus.PENDING_APPROVAL,
        generated_by=user
    )

    employees = EmployeeProfile.objects.filter(branch=branch).exclude(status=EmployeeProfile.Status.RESIGNED if hasattr(EmployeeProfile, 'Status') else 'Resigned')
    total_gross = Decimal('0.00')
    total_ded = Decimal('0.00')
    total_net = Decimal('0.00')

    for emp in employees:
        is_selected = (str(emp.id) in [str(x) for x in selected_emp_ids])
        gross = emp.gross_salary
        ded = emp.total_deductions
        net = emp.net_salary

        if is_selected:
            total_gross += gross
            total_ded += ded
            total_net += net

            # Fold in any pending arrears for this employee
            pending_arrears = SalaryArrear.objects.filter(employee=emp, status=SalaryArrearStatus.PENDING)
            for arr in pending_arrears:
                total_net += arr.amount
                arr.status = SalaryArrearStatus.FOLDED_IN_PAYROLL
                arr.folded_in_payroll = run
                arr.save(update_fields=['status', 'folded_in_payroll'])

            PayrollItem.objects.create(
                payroll_run=run,
                employee=emp,
                gross_pay=gross,
                deductions=ded,
                net_pay=net,
                is_deferred=False,
                remarks="Included in payroll"
            )
        else:
            # Deferred as arrear
            SalaryArrear.objects.create(
                employee=emp,
                period_label=f"{month:02d}/{year}",
                source=SalaryArrearSource.DEFERRED_PAYROLL,
                amount=net,
                status=SalaryArrearStatus.PENDING,
                reason="Unchecked during payroll generation",
                requested_by=user
            )
            PayrollItem.objects.create(
                payroll_run=run,
                employee=emp,
                gross_pay=gross,
                deductions=ded,
                net_pay=Decimal('0.00'),
                is_deferred=True,
                remarks="Deferred as salary arrear"
            )

    run.total_gross = total_gross
    run.total_deductions = total_ded
    run.total_net = total_net
    run.save(update_fields=['total_gross', 'total_deductions', 'total_net'])
    return run


@transaction.atomic
def approve_payroll_run(payroll_id, user):
    """
    Approves a payroll run.
    Automatically posts the total net salary into the Expense ledger under 'Operation' category!
    """
    run = PayrollRun.objects.select_for_update().get(id=payroll_id)
    if run.status == PayrollRunStatus.APPROVED:
        return run

    run.status = PayrollRunStatus.APPROVED
    run.approved_by = user
    run.paid_at = timezone.now()
    run.save(update_fields=['status', 'approved_by', 'paid_at'])

    # Post total salary to Expense ledger
    Expense.objects.create(
        branch=run.branch,
        category=ExpenseCategory.OPERATION,
        sub_category="Staff Payroll",
        paid_by=user,
        paid_by_name=user.get_full_name() or user.username,
        amount=run.total_net,
        description=f"Payroll run #{run.run_number} payout for {run.items.filter(is_deferred=False).count()} employees.",
        paid_to="Branch Staff",
        expense_date=timezone.localdate(),
        status=ExpenseStatus.APPROVED,
        created_by=user,
        reviewed_by=user,
        reviewed_at=timezone.now()
    )
    return run


def get_renewal_alerts_metrics(branch_ids):
    """
    Computes 4 authoritative, real database KPI metrics for Renewal Alerts scoped to branch:
    - total_active_count
    - total_active_amount
    - upcoming_count (due in > 7 days)
    - due_in_7_days_count (due in 0 to 7 days)
    - overdue_count (due date in past)
    """
    today = timezone.localdate()
    qs = RenewalAlert.objects.filter(branch_id__in=branch_ids)

    active_qs = qs.exclude(status=RenewalAlertStatus.DONE)
    total_active_count = active_qs.count()
    total_active_amount = active_qs.aggregate(s=Sum('amount'))['s'] or Decimal('0.00')

    due_7d_limit = today + timedelta(days=7)

    overdue_count = active_qs.filter(due_date__lt=today).count()
    due_in_7_days_count = active_qs.filter(due_date__gte=today, due_date__lte=due_7d_limit).count()
    upcoming_count = active_qs.filter(due_date__gt=due_7d_limit).count()
    completed_count = qs.filter(status=RenewalAlertStatus.DONE).count()

    return {
        'total_active_count': total_active_count,
        'total_active_amount': total_active_amount,
        'upcoming_count': upcoming_count,
        'due_in_7_days_count': due_in_7_days_count,
        'overdue_count': overdue_count,
        'completed_count': completed_count,
    }


def process_renewal_alerts_batch(target_date=None):
    """
    Batch evaluation engine for Renewal Alerts.
    Triggers automated in-app notifications to Branch Financial Head and Branch Head
    when target_date enters the alert_starts_days_before lead window, up until due_date.
    Prevents duplicate notifications on the same date.
    Can be called from views or management command (cron / task scheduler).
    """
    if target_date is None:
        target_date = timezone.localdate()

    from activities.services import create_notification
    from activities.utils import log_activity

    active_alerts = RenewalAlert.objects.exclude(status=RenewalAlertStatus.DONE).select_related(
        'branch', 'recipient_finance_head', 'recipient_branch_head'
    )

    notifications_sent = 0
    alerts_evaluated = 0

    for alert in active_alerts:
        alerts_evaluated += 1
        rem_date = alert.next_reminder_date

        if not rem_date or target_date < rem_date:
            continue  # Not yet in reminder lead window

        # Calculate dynamic status
        dynamic_status = alert.check_dynamic_status()
        if alert.status != dynamic_status:
            alert.status = dynamic_status
            alert.save(update_fields=['status'])

        # Duplicate check: don't send multiple alerts on the exact same date
        if alert.last_notified_date == target_date:
            continue

        # Recipients matrix
        recipients = set()
        if alert.recipient_finance_head and alert.recipient_finance_head.is_active:
            recipients.add(alert.recipient_finance_head)
        if alert.recipient_branch_head and alert.recipient_branch_head.is_active:
            recipients.add(alert.recipient_branch_head)

        # Fallback to branch staff if specific recipients weren't manually selected
        if not recipients:
            from accounts.models import User, UserRole
            branch_users = User.objects.filter(
                branch=alert.branch,
                role__in=[UserRole.FINANCE_HEAD, UserRole.BRANCH_HEAD],
                is_active=True
            )
            for u in branch_users:
                recipients.add(u)

        if not recipients:
            continue

        # Construct title & message based on urgency
        days_left = (alert.due_date - target_date).days
        if days_left < 0:
            urgency_prefix = f"OVERDUE ({abs(days_left)} days past due)"
            notif_type = 'warning'
        elif days_left == 0:
            urgency_prefix = "DUE TODAY"
            notif_type = 'warning'
        else:
            urgency_prefix = f"Due in {days_left} day{'s' if days_left != 1 else ''}"
            notif_type = 'info'

        amt_str = f" of ₹{alert.amount:,.2f}" if alert.amount else ""
        title = f"Finance Alert: {alert.name} is {urgency_prefix}"
        message = (
            f"Scheduled {alert.alert_type} '{alert.name}'{amt_str} for {alert.branch.name} "
            f"is due on {alert.due_date.strftime('%d %b %Y')}. "
            f"Please review and process to maintain branch compliance."
        )
        link = "/finance/renewal-alerts/"

        for r in recipients:
            create_notification(
                recipient=r,
                title=title,
                message=message,
                notification_type=notif_type,
                link=link
            )
            notifications_sent += 1

        alert.last_notified_date = target_date
        alert.save(update_fields=['last_notified_date'])

    return {
        'alerts_evaluated': alerts_evaluated,
        'notifications_sent': notifications_sent,
        'target_date': str(target_date),
    }

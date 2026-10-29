import csv
import io
from decimal import Decimal, ROUND_HALF_UP
from datetime import datetime, time, date, timedelta

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST
from django.http import HttpResponse, JsonResponse, Http404
from django.core.paginator import Paginator
from django.core.exceptions import ValidationError, PermissionDenied
from django.db import transaction
from django.db.models import Q, Sum, Count
from django.utils import timezone

from accounts.models import User, UserRole
from accounts.forms import LoginForm
from accounts.permissions import (
    role_required,
    finance_head_required,
    get_accessible_branch_ids,
)
from branches.models import Branch
from leads.models import (
    Enrollment,
    Installment,
    PaymentTransaction,
    PaymentTransactionStatus,
    PaymentMethod,
    EnrollmentStatus,
)
from leads.services_enrollment import approve_payment, reject_payment
from leads.utils_date_filter import extract_normalized_date_range

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
    RenewalAlertType,
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
from .forms import (
    ExpenseForm,
    InternalTransferForm,
    RenewalAlertForm,
    SalaryArrearForm,
)
from .services import (
    get_finance_scope,
    get_finance_dashboard_metrics,
    get_pending_payments_breakdown,
    get_approvals_counts,
    approve_expense,
    reject_expense,
    generate_payroll_run,
    approve_payroll_run,
    sanitize_for_excel,
)


def finance_login(request):
    """
    Dedicated Finance Head Login portal entry.
    Shares the exact same secure authentication backend, CSRF protection,
    and credential hashing while displaying the branded 'Finance Portal' workspace.
    """
    next_url = request.POST.get('next') or request.GET.get('next') or ''

    if request.user.is_authenticated:
        if next_url and next_url.startswith('/') and not next_url.startswith('//'):
            return redirect(next_url)
        from accounts.views import login_redirect
        return login_redirect(request)

    form = LoginForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        email_input = (form.cleaned_data.get('email') or form.cleaned_data.get('username') or '').strip()
        password = form.cleaned_data.get('password')
        remember_me = form.cleaned_data.get('remember_me')

        user = authenticate(request, username=email_input, password=password)
        if user is None:
            user = authenticate(request, email=email_input, password=password)

        if user is not None:
            if not user.is_active:
                messages.error(request, "Your account has been deactivated. Please contact your administrator.")
                return render(request, 'finance/login.html', {
                    'form': form,
                    'next': next_url,
                    'portal_title': 'Branch Financial Head Portal',
                })

            login(request, user)
            if not remember_me:
                request.session.set_expiry(0)
            else:
                request.session.set_expiry(60 * 60 * 24 * 30)

            try:
                from activities.services import log_activity
                log_activity(
                    user=user,
                    action="Finance Portal Sign In",
                    description=f"{user.display_role} '{user.email}' signed in to Finance Portal.",
                    object_type="User",
                    object_id=str(user.pk),
                    request=request
                )
            except Exception:
                pass

            messages.success(request, f"Welcome back, {user.first_name or user.email}!")

            if next_url and next_url.startswith('/') and not next_url.startswith('//'):
                return redirect(next_url)

            from accounts.views import login_redirect
            return login_redirect(request)
        else:
            messages.error(request, "Invalid email address or password. Please verify your credentials.")

    return render(request, 'finance/login.html', {
        'form': form,
        'next': next_url,
        'logged_out': request.GET.get('logged_out') == '1',
        'portal_title': 'Branch Financial Head Portal',
    })


@login_required
@finance_head_required
def finance_dashboard(request):
    """
    Authoritative Financial Dashboard with 8 KPI metrics, date filtering,
    collection owner summary, and payment method breakdowns.
    """
    branch_ids, selected_branch_id = get_finance_scope(request.user, request.GET.get('branch'))

    # Date Range Handling
    _date_info = extract_normalized_date_range(request, default_period='month')
    start_dt = _date_info['start_dt']
    end_dt = _date_info['end_dt']
    period_label = _date_info.get('filter_type', 'This Month').title()

    metrics = get_finance_dashboard_metrics(branch_ids, start_dt, end_dt)
    approvals_counts = get_approvals_counts(branch_ids)

    branches = Branch.objects.filter(id__in=get_accessible_branch_ids(request.user)).order_by('name')

    context = {
        'portal_title': 'Finance Dashboard',
        'metrics': metrics,
        'approvals_counts': approvals_counts,
        'pending_approvals_count': approvals_counts.get('total_pending', 0),
        'period_label': period_label,
        'filter_type': _date_info.get('filter_type', 'month'),
        'start_date': _date_info.get('start_date', ''),
        'end_date': _date_info.get('end_date', ''),
        'branches': branches,
        'selected_branch_id': selected_branch_id,
    }
    return render(request, 'finance/dashboard.html', context)


@login_required
@finance_head_required
def finance_pending_payments(request):
    """
    Pending Payments & Dues tracking:
    Group 1: Initial Dues below base fee (anchored on batch start date)
    Group 2: Balance Due course not fully paid (30d+, 35d+, SLA breached)
    """
    branch_ids, selected_branch_id = get_finance_scope(request.user, request.GET.get('branch'))
    student_type = request.GET.get('student_type', '')
    course_id = request.GET.get('course', '')
    tier_filter = request.GET.get('tier', '')
    query = request.GET.get('q', '').strip()

    data = get_pending_payments_breakdown(
        branch_ids=branch_ids,
        student_type=student_type,
        course_id=course_id,
        tier_filter=tier_filter,
        query=query
    )

    from products.models import Product
    courses = Product.objects.all().order_by('name')
    branches = Branch.objects.filter(id__in=get_accessible_branch_ids(request.user)).order_by('name')

    context = {
        'portal_title': 'Pending Payments',
        'data': data,
        'courses': courses,
        'branches': branches,
        'selected_branch_id': selected_branch_id,
        'student_type': student_type,
        'course_id': course_id,
        'tier_filter': tier_filter,
        'query': query,
    }
    return render(request, 'finance/pending_payments.html', context)


@login_required
@finance_head_required
def finance_approvals(request):
    """
    Approvals Queue across 5 categories:
    Income, Expenses, Other Income, Incentive Approvals, Payroll.
    """
    branch_ids, selected_branch_id = get_finance_scope(request.user, request.GET.get('branch'))
    active_tab = request.GET.get('tab', 'income')
    status_mode = request.GET.get('status', 'active')  # 'active' or 'completed'

    counts = get_approvals_counts(branch_ids)

    # 1. Income (Pending Payments)
    if status_mode == 'active':
        income_items = PaymentTransaction.objects.filter(
            enrollment__branch_id__in=branch_ids,
            status=PaymentTransactionStatus.PENDING_VERIFICATION
        ).select_related('enrollment', 'enrollment__product', 'enrollment__assigned_counselor', 'installment', 'recorded_by')
    else:
        income_items = PaymentTransaction.objects.filter(
            enrollment__branch_id__in=branch_ids,
            status__in=[PaymentTransactionStatus.APPROVED, PaymentTransactionStatus.REJECTED]
        ).select_related('enrollment', 'enrollment__product', 'enrollment__assigned_counselor', 'installment', 'recorded_by', 'reviewed_by')[:50]

    # 2. Expenses
    if status_mode == 'active':
        expense_items = Expense.objects.filter(
            branch_id__in=branch_ids,
            status=ExpenseStatus.PENDING
        ).select_related('branch', 'paid_by', 'created_by')
    else:
        expense_items = Expense.objects.filter(
            branch_id__in=branch_ids,
            status__in=[ExpenseStatus.APPROVED, ExpenseStatus.REJECTED]
        ).select_related('branch', 'paid_by', 'created_by', 'reviewed_by')[:50]

    # 3. Incentives
    if status_mode == 'active':
        incentive_items = IncentiveRecord.objects.filter(
            branch_id__in=branch_ids,
            status=IncentiveStatus.AWAITING_RELEASE
        ).select_related('counselor', 'branch')
    else:
        incentive_items = IncentiveRecord.objects.filter(
            branch_id__in=branch_ids,
            status=IncentiveStatus.RELEASED
        ).select_related('counselor', 'branch')[:50]

    # 4. Payroll
    if status_mode == 'active':
        payroll_items = PayrollRun.objects.filter(
            branch_id__in=branch_ids,
            status=PayrollRunStatus.PENDING_APPROVAL
        ).select_related('branch', 'generated_by')
    else:
        payroll_items = PayrollRun.objects.filter(
            branch_id__in=branch_ids,
            status__in=[PayrollRunStatus.APPROVED, PayrollRunStatus.PAID]
        ).select_related('branch', 'generated_by', 'approved_by')[:50]

    branches = Branch.objects.filter(id__in=get_accessible_branch_ids(request.user)).order_by('name')

    context = {
        'portal_title': 'Approvals',
        'active_tab': active_tab,
        'status_mode': status_mode,
        'counts': counts,
        'income_items': income_items,
        'expense_items': expense_items,
        'incentive_items': incentive_items,
        'payroll_items': payroll_items,
        'branches': branches,
        'selected_branch_id': selected_branch_id,
    }
    return render(request, 'finance/approvals.html', context)


@login_required
@finance_head_required
@require_POST
def finance_approve_payment_action(request, payment_id):
    """Action endpoint for approving a student payment."""
    try:
        approve_payment(payment_id, request.user)
        messages.success(request, f"Payment #{payment_id} approved successfully.")
    except Exception as e:
        messages.error(request, f"Error approving payment: {e}")
    return redirect(request.META.get('HTTP_REFERER') or 'finance_approvals')


@login_required
@finance_head_required
@require_POST
def finance_reject_payment_action(request, payment_id):
    """Action endpoint for rejecting a student payment."""
    reason = request.POST.get('rejection_reason', 'Rejected by Finance Head.')
    try:
        reject_payment(payment_id, request.user, reason)
        messages.warning(request, f"Payment #{payment_id} rejected.")
    except Exception as e:
        messages.error(request, f"Error rejecting payment: {e}")
    return redirect(request.META.get('HTTP_REFERER') or 'finance_approvals')


@login_required
@finance_head_required
@require_POST
def finance_approve_expense_action(request, expense_id):
    """Action endpoint for approving an expense."""
    try:
        approve_expense(expense_id, request.user)
        messages.success(request, f"Expense #{expense_id} approved successfully.")
    except Exception as e:
        messages.error(request, f"Error approving expense: {e}")
    return redirect(request.META.get('HTTP_REFERER') or 'finance_approvals')


@login_required
@finance_head_required
@require_POST
def finance_reject_expense_action(request, expense_id):
    """Action endpoint for rejecting an expense."""
    reason = request.POST.get('rejection_reason', 'Rejected by Finance Head.')
    try:
        reject_expense(expense_id, request.user, reason)
        messages.warning(request, f"Expense #{expense_id} rejected.")
    except Exception as e:
        messages.error(request, f"Error rejecting expense: {e}")
    return redirect(request.META.get('HTTP_REFERER') or 'finance_approvals')


@login_required
@finance_head_required
@require_POST
def finance_approve_payroll_action(request, payroll_id):
    """Action endpoint for approving a payroll run and auto-posting to expenses."""
    try:
        approve_payroll_run(payroll_id, request.user)
        messages.success(request, f"Payroll run #{payroll_id} approved and posted to expenses.")
    except Exception as e:
        messages.error(request, f"Error approving payroll run: {e}")
    return redirect(request.META.get('HTTP_REFERER') or 'finance_approvals')


@login_required
@finance_head_required
def finance_oversight(request):
    """
    Finance Verification / Oversight screen.
    Everything approved in branch — collections, other income, and expenses.
    Review, revert, edit, or delete with audit protection.
    """
    branch_ids, selected_branch_id = get_finance_scope(request.user, request.GET.get('branch'))
    type_filter = request.GET.get('type', 'all')
    period_filter = request.GET.get('period', 'all_time')

    # Aggregates
    pmts = PaymentTransaction.objects.filter(
        enrollment__branch_id__in=branch_ids,
        status__in=[PaymentTransactionStatus.APPROVED, PaymentTransactionStatus.SUCCESS]
    ).select_related('enrollment', 'enrollment__product', 'installment', 'recorded_by')

    exps = Expense.objects.filter(
        branch_id__in=branch_ids,
        status=ExpenseStatus.APPROVED
    ).select_related('branch', 'paid_by')

    tot_collections = pmts.aggregate(s=Sum('amount'))['s'] or Decimal('0.00')
    tot_expenses = exps.aggregate(s=Sum('amount'))['s'] or Decimal('0.00')
    other_income = Decimal('0.00')
    net_income = tot_collections + other_income - tot_expenses

    # Combine items for unified list
    combined_items = []
    if type_filter in ('all', 'collections'):
        for p in pmts[:50]:
            combined_items.append({
                'type': 'Collection',
                'id': p.id,
                'date': p.payment_date.date() if p.payment_date else None,
                'title': f"{p.enrollment.student_name} ({p.enrollment.product.name if p.enrollment.product else 'Course'})",
                'receipt': p.receipt_number,
                'amount': p.amount,
                'method': p.payment_method,
                'proof_url': p.payment_proof.url if p.payment_proof else '',
                'recorder': p.recorded_by.get_full_name() if p.recorded_by else 'Staff',
                'is_payment': True,
            })

    if type_filter in ('all', 'expenses'):
        for e in exps[:50]:
            combined_items.append({
                'type': 'Expense',
                'id': e.id,
                'date': e.expense_date,
                'title': f"{e.category} - {e.sub_category} ({e.paid_to})",
                'receipt': f"EXP-{e.id}",
                'amount': e.amount,
                'method': 'Direct',
                'proof_url': e.proof.url if e.proof else '',
                'recorder': e.paid_by.get_full_name() if e.paid_by else (e.paid_by_name or 'Staff'),
                'is_payment': False,
            })

    combined_items.sort(key=lambda x: x['date'] or date.min, reverse=True)

    branches = Branch.objects.filter(id__in=get_accessible_branch_ids(request.user)).order_by('name')

    context = {
        'portal_title': 'Finance Verification',
        'tot_collections': tot_collections,
        'tot_expenses': tot_expenses,
        'other_income': other_income,
        'net_income': net_income,
        'pmts_count': pmts.count(),
        'exps_count': exps.count(),
        'combined_items': combined_items,
        'type_filter': type_filter,
        'period_filter': period_filter,
        'branches': branches,
        'selected_branch_id': selected_branch_id,
    }
    return render(request, 'finance/finance_oversight.html', context)


@login_required
@finance_head_required
def finance_expenses(request):
    """
    Expenses & Ledger Suite:
    - Add Expense form with proof upload
    - Expenses table with search & category filters
    - Opening Balances configuration per owner
    - Budget Forecast vs Actual with Variance
    - Ledger (Opening + Income - Expense = Remaining)
    - GST Records (18% GST tracked separately, GST Collected, Taxable Base, Invoices)
    """
    branch_ids, selected_branch_id = get_finance_scope(request.user, request.GET.get('branch'))
    branch = Branch.objects.filter(id__in=branch_ids).first()

    # Form submission for Add Expense
    expense_form = ExpenseForm(request.POST or None, request.FILES or None)
    if request.method == 'POST' and 'add_expense' in request.POST:
        if expense_form.is_valid():
            new_exp = expense_form.save(commit=False)
            new_exp.branch = branch or Branch.objects.first()
            new_exp.created_by = request.user
            new_exp.status = ExpenseStatus.APPROVED  # Branch Financial Head self-creates approved or pending
            new_exp.save()
            messages.success(request, f"Expense for ₹{new_exp.amount} added successfully.")
            return redirect('finance_expenses')

    # Save Opening Balance POST
    if request.method == 'POST' and 'save_opening_balance' in request.POST:
        owner_name = request.POST.get('owner_name')
        val_str = request.POST.get('opening_balance', '0')
        try:
            val = Decimal(val_str)
            obj, _ = BranchOpeningBalance.objects.get_or_create(branch=branch, owner_name=owner_name)
            obj.opening_balance = val
            obj.save()
            messages.success(request, f"Opening balance updated for {owner_name}.")
        except Exception as e:
            messages.error(request, f"Error saving balance: {e}")
        return redirect('finance_expenses')

    # Filters
    cat_filter = request.GET.get('category', '')
    expenses_qs = Expense.objects.filter(branch_id__in=branch_ids).select_related('paid_by', 'created_by')
    if cat_filter:
        expenses_qs = expenses_qs.filter(category=cat_filter)

    total_expenses_amt = expenses_qs.aggregate(s=Sum('amount'))['s'] or Decimal('0.00')

    # Opening Balances table
    opening_balances = []
    if branch:
        default_owners = [f"TP-{branch.name[:3].upper()}-BranchHead", f"TP-{branch.name}"]
        for o in default_owners:
            rec, _ = BranchOpeningBalance.objects.get_or_create(branch=branch, owner_name=o)
            opening_balances.append(rec)

    # Budget Forecast vs Actual
    budget_rows = []
    now = timezone.localdate()
    curr_month = now.month
    curr_year = now.year

    tot_forecast = Decimal('0.00')
    tot_actual = Decimal('0.00')

    for cat_val, cat_label in ExpenseCategory.choices:
        bf = BudgetForecast.objects.filter(branch=branch, category=cat_val, month=curr_month, year=curr_year).first()
        f_amt = bf.forecasted_amount if bf else Decimal('0.00')
        a_amt = Expense.objects.filter(
            branch=branch,
            category=cat_val,
            status=ExpenseStatus.APPROVED,
            expense_date__month=curr_month,
            expense_date__year=curr_year
        ).aggregate(s=Sum('amount'))['s'] or Decimal('0.00')

        variance = f_amt - a_amt
        status_label = 'Not Started' if a_amt == 0 else ('Over Budget' if variance < 0 else 'On Track')

        tot_forecast += f_amt
        tot_actual += a_amt

        budget_rows.append({
            'category': cat_label,
            'forecasted': f_amt,
            'actual': a_amt,
            'variance': variance,
            'status': status_label,
        })

    # Ledger
    ledger_rows = []
    for ob in opening_balances:
        income = PaymentTransaction.objects.filter(
            enrollment__branch=branch,
            status__in=[PaymentTransactionStatus.APPROVED, PaymentTransactionStatus.SUCCESS]
        ).aggregate(s=Sum('amount'))['s'] or Decimal('0.00')
        exp_sum = Expense.objects.filter(
            branch=branch,
            status=ExpenseStatus.APPROVED
        ).aggregate(s=Sum('amount'))['s'] or Decimal('0.00')
        rem = ob.opening_balance + income - exp_sum
        ledger_rows.append({
            'owner': ob.owner_name,
            'opening': ob.opening_balance,
            'income': income,
            'expense': exp_sum,
            'remaining': rem,
        })

    # GST Records
    gst_pmts = PaymentTransaction.objects.filter(
        enrollment__branch_id__in=branch_ids,
        status__in=[PaymentTransactionStatus.APPROVED, PaymentTransactionStatus.SUCCESS],
        enrollment__tax_rate__gt=0
    ).select_related('enrollment', 'enrollment__product')

    gst_collected = Decimal('0.00')
    gst_taxable_base = Decimal('0.00')
    gst_gross = Decimal('0.00')

    gst_rows = []
    for p in gst_pmts:
        enr = p.enrollment
        amt = p.amount
        gst_gross += amt

        if enr.gst_treatment == 'EXCLUSIVE':
            tax = (amt * (enr.tax_rate / Decimal('100.00'))).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
            base = amt
        else:
            tax = (amt - (amt / (Decimal('1.00') + (enr.tax_rate / Decimal('100.00'))))).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
            base = amt - tax

        gst_collected += tax
        gst_taxable_base += base

        gst_rows.append({
            'date': p.payment_date.date() if p.payment_date else None,
            'receipt': p.receipt_number,
            'student': enr.student_name,
            'course': enr.product.name if enr.product else 'Course',
            'base': base,
            'gst': tax,
            'total': amt,
            'mode': p.payment_method,
        })

    branches = Branch.objects.filter(id__in=get_accessible_branch_ids(request.user)).order_by('name')

    context = {
        'portal_title': 'Expenses & Ledger',
        'expense_form': expense_form,
        'expenses': expenses_qs[:50],
        'total_expenses_amt': total_expenses_amt,
        'cat_filter': cat_filter,
        'opening_balances': opening_balances,
        'budget_rows': budget_rows,
        'tot_forecast': tot_forecast,
        'tot_actual': tot_actual,
        'tot_variance': tot_forecast - tot_actual,
        'ledger_rows': ledger_rows,
        'gst_collected': gst_collected,
        'gst_taxable_base': gst_taxable_base,
        'gst_gross': gst_gross,
        'gst_invoices_count': len(gst_rows),
        'gst_rows': gst_rows[:50],
        'branches': branches,
        'selected_branch_id': selected_branch_id,
    }
    return render(request, 'finance/expenses_ledger.html', context)


@login_required
@finance_head_required
def finance_internal_transfers(request):
    """
    Internal Transfers between branches with Delivery Challan.
    """
    branch_ids, selected_branch_id = get_finance_scope(request.user, request.GET.get('branch'))
    branch = Branch.objects.filter(id__in=branch_ids).first()
    tab = request.GET.get('tab', 'all')

    form = InternalTransferForm(request.POST or None, request.FILES or None)
    if request.method == 'POST' and 'request_transfer' in request.POST:
        if form.is_valid():
            trf = form.save(commit=False)
            trf.from_branch = branch or Branch.objects.first()
            trf.initiated_by = request.user
            trf.transfer_code = f"TRF-{timezone.now().strftime('%Y%m%d%H%M%S')}"
            trf.status = InternalTransferStatus.PENDING_APPROVAL
            trf.save()
            messages.success(request, f"Transfer request {trf.transfer_code} submitted.")
            return redirect('finance_internal_transfers')

    qs = InternalTransfer.objects.filter(
        Q(from_branch_id__in=branch_ids) | Q(to_branch_id__in=branch_ids)
    ).select_related('from_branch', 'to_branch', 'initiated_by')

    if tab == 'to_approve':
        qs = qs.filter(from_branch_id__in=branch_ids, status=InternalTransferStatus.PENDING_APPROVAL)
    elif tab == 'my_requests':
        qs = qs.filter(initiated_by=request.user)

    branches = Branch.objects.filter(id__in=get_accessible_branch_ids(request.user)).order_by('name')

    context = {
        'portal_title': 'Internal Transfers',
        'transfers': qs,
        'tab': tab,
        'form': form,
        'branches': branches,
        'selected_branch_id': selected_branch_id,
    }
    return render(request, 'finance/internal_transfers.html', context)


@login_required
@finance_head_required
def finance_renewal_alerts(request):
    """
    Enterprise Renewal Alerts & Recurring Finance Reminders:
    Rent, Electricity, Subscriptions, Salary & Incentive disbursements.
    Real-time KPI metrics, dual-recipient routing (Financial Head & Branch Head),
    search, status tabs, and automated notification evaluation.
    """
    from finance.services import get_renewal_alerts_metrics, process_renewal_alerts_batch
    from activities.utils import log_activity
    from datetime import date, timedelta

    branch_ids, selected_branch_id = get_finance_scope(request.user, request.GET.get('branch'))
    branch = Branch.objects.filter(id__in=branch_ids).first()
    today = timezone.localdate()

    # Trigger background evaluation on page load to keep alerts fresh
    try:
        process_renewal_alerts_batch(target_date=today)
    except Exception:
        pass

    tab = request.GET.get('tab', 'all')
    search_q = request.GET.get('q', '').strip()
    category_filter = request.GET.get('category', '').strip()

    form = RenewalAlertForm(request.POST or None, branch=branch)

    # ACTION 1: Add New Scheduled Alert
    if request.method == 'POST' and 'add_alert' in request.POST:
        if form.is_valid():
            alt = form.save(commit=False)
            if not alt.branch:
                alt.branch = branch or Branch.objects.first()
            alt.created_by = request.user

            # Auto-assign recipients from branch roster if left unselected
            if not alt.recipient_finance_head:
                alt.recipient_finance_head = User.objects.filter(
                    branch=alt.branch, role=UserRole.FINANCE_HEAD, is_active=True
                ).first()
            if not alt.recipient_branch_head:
                alt.recipient_branch_head = User.objects.filter(
                    branch=alt.branch, role=UserRole.BRANCH_HEAD, is_active=True
                ).first()

            alt.save()

            log_activity(
                user=request.user,
                action="Renewal Alert Created",
                description=f"Scheduled finance alert '{alt.name}' (due {alt.due_date}) for {alt.branch.name}.",
                object_type="RenewalAlert",
                object_id=str(alt.id),
                request=request
            )

            messages.success(request, f"Scheduled alert '{alt.name}' created successfully.")
            return redirect('finance_renewal_alerts')

    # ACTION 2: Mark Done & Advance Recurrence Cycle
    if request.method == 'POST' and 'mark_done' in request.POST:
        alt_id = request.POST.get('alert_id')
        alt = get_object_or_404(RenewalAlert, id=alt_id, branch_id__in=branch_ids)
        prev_due = alt.due_date
        was_recurring = bool(alt.repeat_every_months and alt.repeat_every_months > 0)
        alt.advance_to_next_cycle()

        log_activity(
            user=request.user,
            action="Renewal Alert Completed",
            description=f"Alert '{alt.name}' marked completed for {prev_due}. Advanced: {was_recurring}.",
            object_type="RenewalAlert",
            object_id=str(alt.id),
            request=request
        )

        if was_recurring:
            messages.success(request, f"Alert '{alt.name}' completed for this cycle. Advanced to next due date: {alt.due_date.strftime('%d %b %Y')}.")
        else:
            messages.success(request, f"One-time alert '{alt.name}' marked as completed.")
        return redirect('finance_renewal_alerts')

    # ACTION 3: Delete Alert
    if request.method == 'POST' and 'delete_alert' in request.POST:
        alt_id = request.POST.get('alert_id')
        alt = get_object_or_404(RenewalAlert, id=alt_id, branch_id__in=branch_ids)
        alt_name = alt.name
        alt.delete()

        log_activity(
            user=request.user,
            action="Renewal Alert Deleted",
            description=f"Deleted renewal alert '{alt_name}'.",
            object_type="RenewalAlert",
            object_id=str(alt_id),
            request=request
        )

        messages.success(request, f"Alert '{alt_name}' was removed.")
        return redirect('finance_renewal_alerts')

    # Real Database KPI Metrics
    metrics = get_renewal_alerts_metrics(branch_ids)

    # Queryset & Filtering
    qs = RenewalAlert.objects.filter(branch_id__in=branch_ids).select_related(
        'branch', 'recipient_finance_head', 'recipient_branch_head'
    )

    if search_q:
        qs = qs.filter(
            Q(name__icontains=search_q) |
            Q(notes__icontains=search_q) |
            Q(contract_reference__icontains=search_q)
        )

    if category_filter:
        qs = qs.filter(alert_type=category_filter)

    due_7d_limit = today + timedelta(days=7)

    if tab == 'due_7d':
        qs = qs.exclude(status=RenewalAlertStatus.DONE).filter(due_date__gte=today, due_date__lte=due_7d_limit)
    elif tab == 'overdue':
        qs = qs.exclude(status=RenewalAlertStatus.DONE).filter(due_date__lt=today)
    elif tab == 'renewals':
        qs = qs.filter(alert_type=RenewalAlertType.RENEWAL)
    elif tab == 'disbursements':
        qs = qs.filter(alert_type=RenewalAlertType.DISBURSEMENT)
    elif tab == 'completed':
        qs = qs.filter(status=RenewalAlertStatus.DONE)
    elif tab == 'active':
        qs = qs.exclude(status=RenewalAlertStatus.DONE)

    alerts_list = []
    for a in qs:
        a.dynamic_status = a.check_dynamic_status()
        alerts_list.append(a)

    branches = Branch.objects.filter(id__in=get_accessible_branch_ids(request.user)).order_by('name')

    context = {
        'portal_title': 'Renewal Alerts',
        'alerts': alerts_list,
        'metrics': metrics,
        'tab': tab,
        'search_q': search_q,
        'category_filter': category_filter,
        'form': form,
        'branches': branches,
        'selected_branch_id': selected_branch_id,
        'current_branch': branch,
    }
    return render(request, 'finance/renewal_alerts.html', context)


@login_required
@finance_head_required
def finance_employees(request):
    """
    HR Employee Directory.
    Branch-scoped directory with salary structures.
    """
    branch_ids, selected_branch_id = get_finance_scope(request.user, request.GET.get('branch'))
    query = request.GET.get('q', '').strip()
    status_filter = request.GET.get('status', '')
    dept_filter = request.GET.get('department', '')

    qs = EmployeeProfile.objects.filter(branch_id__in=branch_ids).select_related('branch', 'user')
    if query:
        qs = qs.filter(
            Q(full_name__icontains=query) |
            Q(email__icontains=query) |
            Q(employee_code__icontains=query)
        )
    if status_filter:
        qs = qs.filter(status=status_filter)
    if dept_filter:
        qs = qs.filter(department=dept_filter)

    branches = Branch.objects.filter(id__in=get_accessible_branch_ids(request.user)).order_by('name')

    context = {
        'portal_title': 'Employees',
        'employees': qs,
        'total_count': qs.count(),
        'query': query,
        'status_filter': status_filter,
        'dept_filter': dept_filter,
        'branches': branches,
        'selected_branch_id': selected_branch_id,
    }
    return render(request, 'finance/employees.html', context)


@login_required
@finance_head_required
def finance_payroll(request):
    """
    Monthly Payroll Runs:
    Generates payroll runs, snapshots salaries, applies statutory deductions,
    and supports deferring unselected employees as salary arrears.
    """
    branch_ids, selected_branch_id = get_finance_scope(request.user, request.GET.get('branch'))
    branch = Branch.objects.filter(id__in=branch_ids).first()

    now = timezone.localdate()
    month = int(request.GET.get('month', now.month))
    year = int(request.GET.get('year', now.year))

    # Employees for checklist
    employees = EmployeeProfile.objects.filter(branch=branch)

    if request.method == 'POST' and 'generate_payroll' in request.POST:
        selected_emp_ids = request.POST.getlist('selected_employees')
        try:
            run = generate_payroll_run(branch, month, year, selected_emp_ids, request.user)
            messages.success(request, f"Payroll run #{run.run_number} generated successfully.")
            return redirect('finance_payroll')
        except Exception as e:
            messages.error(request, f"Error generating payroll: {e}")

    runs = PayrollRun.objects.filter(branch_id__in=branch_ids).select_related('branch', 'generated_by', 'approved_by')

    branches = Branch.objects.filter(id__in=get_accessible_branch_ids(request.user)).order_by('name')

    context = {
        'portal_title': 'Payroll',
        'employees': employees,
        'runs': runs,
        'curr_month': month,
        'curr_year': year,
        'branches': branches,
        'selected_branch_id': selected_branch_id,
    }
    return render(request, 'finance/payroll.html', context)


@login_required
@finance_head_required
def finance_salary_arrears(request):
    """
    Salary Arrears:
    Deferred payments folded into later payslips.
    """
    branch_ids, selected_branch_id = get_finance_scope(request.user, request.GET.get('branch'))
    branch = Branch.objects.filter(id__in=branch_ids).first()

    form = SalaryArrearForm(request.POST or None)
    if branch:
        form.fields['employee'].queryset = EmployeeProfile.objects.filter(branch=branch)

    if request.method == 'POST' and 'request_arrear' in request.POST:
        if form.is_valid():
            arr = form.save(commit=False)
            arr.requested_by = request.user
            arr.status = SalaryArrearStatus.PENDING
            arr.save()
            messages.success(request, f"Salary arrear for {arr.employee.full_name} recorded.")
            return redirect('finance_salary_arrears')

    arrears = SalaryArrear.objects.filter(employee__branch_id__in=branch_ids).select_related('employee', 'requested_by', 'folded_in_payroll')

    branches = Branch.objects.filter(id__in=get_accessible_branch_ids(request.user)).order_by('name')

    context = {
        'portal_title': 'Salary Arrears',
        'arrears': arrears,
        'form': form,
        'branches': branches,
        'selected_branch_id': selected_branch_id,
    }
    return render(request, 'finance/salary_arrears.html', context)


@login_required
@finance_head_required
def finance_incentive_track(request):
    """
    Counsellor Incentive Payout tracking:
    Given released, Awaiting release, Not yet requested.
    """
    branch_ids, selected_branch_id = get_finance_scope(request.user, request.GET.get('branch'))
    branch = Branch.objects.filter(id__in=branch_ids).first()
    year_filter = request.GET.get('year', '')
    month_filter = request.GET.get('month', '')
    view_mode = request.GET.get('view', 'tabular')

    qs = IncentiveRecord.objects.filter(branch_id__in=branch_ids).select_related('counselor', 'branch')
    if year_filter and year_filter.isdigit():
        qs = qs.filter(period_year=int(year_filter))
    if month_filter and month_filter.isdigit():
        qs = qs.filter(period_month=int(month_filter))

    released_amt = qs.filter(status=IncentiveStatus.RELEASED).aggregate(s=Sum('total_payout'))['s'] or Decimal('0.00')
    awaiting_amt = qs.filter(status=IncentiveStatus.AWAITING_RELEASE).aggregate(s=Sum('total_payout'))['s'] or Decimal('0.00')
    not_req_amt = qs.filter(status=IncentiveStatus.NOT_REQUESTED).aggregate(s=Sum('total_payout'))['s'] or Decimal('0.00')

    branches = Branch.objects.filter(id__in=get_accessible_branch_ids(request.user)).order_by('name')

    context = {
        'portal_title': 'Incentive Track',
        'incentives': qs,
        'released_amt': released_amt,
        'awaiting_amt': awaiting_amt,
        'not_req_amt': not_req_amt,
        'view_mode': view_mode,
        'year_filter': year_filter,
        'month_filter': month_filter,
        'branches': branches,
        'selected_branch_id': selected_branch_id,
    }
    return render(request, 'finance/incentive_track.html', context)


@login_required
@finance_head_required
def finance_settings(request):
    """
    Finance Head Settings & In-app learning:
    Password change, User manual, 7 demo walkthrough video cards.
    """
    from django.contrib.auth.forms import PasswordChangeForm
    pw_form = PasswordChangeForm(request.user, request.POST or None)

    if request.method == 'POST' and 'change_password' in request.POST:
        if pw_form.is_valid():
            pw_form.save()
            messages.success(request, "Password updated successfully.")
            return redirect('finance_settings')

    context = {
        'portal_title': 'Finance Settings',
        'pw_form': pw_form,
    }
    return render(request, 'finance/settings.html', context)


@login_required
@finance_head_required
def finance_audit_export(request):
    """
    Streams Google Sheet-formatted CSV/Excel audit reports for Course Revenue or Collections.
    """
    branch_ids, _ = get_finance_scope(request.user, request.GET.get('branch'))
    report_type = request.GET.get('report', 'course_revenue')

    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = f'attachment; filename="audit_report_{report_type}_{timezone.localdate()}.csv"'

    writer = csv.writer(response)
    writer.writerow(['RECEIPT NO', 'DATE', 'STUDENT NAME', 'COURSE', 'BRANCH', 'AMOUNT (INR)', 'PAYMENT METHOD', 'STATUS'])

    pmts = PaymentTransaction.objects.filter(
        enrollment__branch_id__in=branch_ids
    ).select_related('enrollment', 'enrollment__product', 'enrollment__branch').order_by('-payment_date')

    for p in pmts:
        writer.writerow([
            sanitize_for_excel(p.receipt_number),
            sanitize_for_excel(p.payment_date.strftime('%Y-%m-%d') if p.payment_date else ''),
            sanitize_for_excel(p.enrollment.student_name),
            sanitize_for_excel(p.enrollment.product.name if p.enrollment.product else 'Course'),
            sanitize_for_excel(p.enrollment.branch.name if p.enrollment.branch else ''),
            p.amount,
            sanitize_for_excel(p.payment_method),
            sanitize_for_excel(p.status),
        ])

    return response

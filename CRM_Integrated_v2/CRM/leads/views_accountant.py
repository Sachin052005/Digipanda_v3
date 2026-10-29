import io
import mimetypes
import logging
from decimal import Decimal
from datetime import datetime, time, date

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST
from django.http import HttpResponse, JsonResponse, FileResponse, Http404
from django.core.paginator import Paginator
from django.core.exceptions import ValidationError, PermissionDenied
from django.db.models import Q, Sum, Count, Min
from django.utils import timezone

from accounts.models import User, UserRole
from accounts.permissions import accountant_required, get_accessible_branch_ids
from branches.models import Branch
from leads.models import (
    Enrollment,
    Installment,
    PaymentTransaction,
    PaymentVerificationHistory,
    PaymentMethod,
    PaymentTransactionStatus,
    EnrollmentStatus,
)
from leads.services_enrollment import approve_payment, reject_payment, resubmit_payment

logger = logging.getLogger(__name__)


def sanitize_for_excel(value):
    """
    Prevents formula injection in Excel cells by prefixing strings that begin
    with dangerous formula symbols (=, +, -, @) with a single apostrophe.
    """
    if value is None:
        return ""
    val_str = str(value)
    if val_str and val_str[0] in ('=', '+', '-', '@', '\t', '\r'):
        return f"'{val_str}"
    return val_str


def get_accountant_scope(user, requested_branch_id=None):
    """
    Resolves branch scope based on Accountant/Admin permissions and optional branch parameter.
    """
    accessible_branches = get_accessible_branch_ids(user)
    if requested_branch_id and str(requested_branch_id).isdigit():
        b_id = int(requested_branch_id)
        if b_id in accessible_branches:
            return [b_id], b_id
    if user.role == UserRole.ACCOUNTANT and user.branch_id:
        return [user.branch_id], user.branch_id
    return accessible_branches, None


@login_required
@accountant_required
def accountant_dashboard(request):
    """
    Financial Dashboard providing 6 distinct, mutually exclusive financial metrics,
    verification queue summary, and period-based filtering.
    """
    # 1. Date Range Filtering (Default to current month)
    from leads.utils_date_filter import extract_normalized_date_range
    today = timezone.localdate()
    _date_info = extract_normalized_date_range(request, default_period='month')
    start_date = _date_info['start_date_obj'] or today.replace(day=1)
    end_date = _date_info['end_date_obj'] or today
    start_date_str = _date_info['start_date'] or start_date.strftime('%Y-%m-%d')
    end_date_str = _date_info['end_date'] or end_date.strftime('%Y-%m-%d')
    start_dt = _date_info['start_dt'] or timezone.make_aware(datetime.combine(start_date, datetime.min.time()))
    end_dt = _date_info['end_dt'] or timezone.make_aware(datetime.combine(end_date, datetime.max.time()))

    # 2. Branch Scope
    requested_branch_id = request.GET.get('branch')
    branch_ids, selected_branch_id = get_accountant_scope(request.user, requested_branch_id)
    branches = Branch.objects.filter(id__in=get_accessible_branch_ids(request.user), status='Active')

    # Base QuerySets
    enrollment_qs = Enrollment.objects.filter(branch_id__in=branch_ids)
    payment_base_qs = PaymentTransaction.objects.filter(
        enrollment__branch_id__in=branch_ids,
        payment_date__range=(start_dt, end_dt)
    )

    # Approved status filter (Approved or Legacy Success)
    approved_statuses = [PaymentTransactionStatus.APPROVED, PaymentTransactionStatus.SUCCESS]
    approved_payments_qs = payment_base_qs.filter(status__in=approved_statuses)

    # CARD 1: Total Fees Due across active enrollments in branch scope
    active_enrollments = enrollment_qs.filter(status=EnrollmentStatus.ACTIVE)
    total_fees_due = active_enrollments.aggregate(total=Sum('outstanding_balance'))['total'] or Decimal('0.00')
    students_with_dues_count = active_enrollments.filter(outstanding_balance__gt=0).count()

    # CARD 2: Received by Cash (Approved)
    cash_payments = approved_payments_qs.filter(payment_method=PaymentMethod.CASH)
    cash_received = cash_payments.aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
    cash_count = cash_payments.count()

    # CARD 3: Received by Account (Approved: UPI, Bank Transfer, Card, Online, Cheque)
    account_methods = [
        PaymentMethod.UPI,
        PaymentMethod.BANK_TRANSFER,
        PaymentMethod.ONLINE,
        PaymentMethod.CARD,
        PaymentMethod.CHEQUE,
    ]
    account_payments = approved_payments_qs.filter(payment_method__in=account_methods)
    account_received = account_payments.aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
    account_count = account_payments.count()

    # CARD 4: Total Collection (Cash + Account)
    total_collection = cash_received + account_received
    total_txns_count = cash_count + account_count

    # CARD 5: New Joinee — First Fee (Admitted in period)
    new_joinee_enrollments = enrollment_qs.filter(
        enrollment_date__range=(start_date, end_date)
    )
    new_joinee_count = new_joinee_enrollments.count()

    # Identify first payments for these new joinees
    first_payments = PaymentTransaction.objects.filter(
        enrollment__in=new_joinee_enrollments
    )
    
    first_fee_approved = first_payments.filter(status__in=approved_statuses).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
    first_fee_approved_count = first_payments.filter(status__in=approved_statuses).values('enrollment_id').distinct().count()

    first_fee_pending = first_payments.filter(status=PaymentTransactionStatus.PENDING_VERIFICATION).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
    first_fee_pending_count = first_payments.filter(status=PaymentTransactionStatus.PENDING_VERIFICATION).values('enrollment_id').distinct().count()

    first_fee_rejected = first_payments.filter(status=PaymentTransactionStatus.REJECTED).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
    first_fee_rejected_count = first_payments.filter(status=PaymentTransactionStatus.REJECTED).values('enrollment_id').distinct().count()

    enrolled_with_payments_ids = set(first_payments.values_list('enrollment_id', flat=True))
    first_fee_not_recorded_count = new_joinee_count - len(enrolled_with_payments_ids)
    if first_fee_not_recorded_count < 0:
        first_fee_not_recorded_count = 0

    # CARD 6: Pending Fee Collected (Subsequent installments / recovering existing dues)
    # Mutually exclusive: Total Approved Collection MINUS New Joinee First Fees collected in this period
    pending_fee_collected = total_collection - first_fee_approved
    if pending_fee_collected < Decimal('0.00'):
        pending_fee_collected = Decimal('0.00')

    # Pending Verification Queue (Oldest first)
    pending_queue_base = PaymentTransaction.objects.filter(
        enrollment__branch_id__in=branch_ids,
        status=PaymentTransactionStatus.PENDING_VERIFICATION
    )
    pending_queue = pending_queue_base.select_related(
        'enrollment', 'enrollment__branch', 'enrollment__assigned_counselor', 'installment', 'recorded_by'
    ).order_by('payment_date')[:10]

    pending_queue_total_count = pending_queue_base.count()
    pending_queue_total_amount = pending_queue_base.aggregate(total=Sum('amount'))['total'] or Decimal('0.00')

    # Rejected Payments in branch scope
    rejected_payments_base = payment_base_qs.filter(status=PaymentTransactionStatus.REJECTED)
    payments_rejected_count = rejected_payments_base.count()
    payments_rejected_amount = rejected_payments_base.aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
    all_time_rejected_count = PaymentTransaction.objects.filter(
        enrollment__branch_id__in=branch_ids,
        status=PaymentTransactionStatus.REJECTED
    ).count()

    # Daily breakdown for chart/table
    daily_stats = (
        approved_payments_qs
        .values('payment_date__date')
        .annotate(total=Sum('amount'), count=Count('id'))
        .order_by('-payment_date__date')[:15]
    )

    context = {
        'total_fees_due': total_fees_due,
        'students_with_dues_count': students_with_dues_count,
        'cash_received': cash_received,
        'cash_count': cash_count,
        'account_received': account_received,
        'account_count': account_count,
        'total_collection': total_collection,
        'total_txns_count': total_txns_count,
        'payments_awaiting_approval_count': pending_queue_total_count,
        'payments_awaiting_approval_amount': pending_queue_total_amount,
        'payments_rejected_count': payments_rejected_count,
        'payments_rejected_amount': payments_rejected_amount,
        'all_time_rejected_count': all_time_rejected_count,
        'new_joinee_count': new_joinee_count,
        'first_fee_approved': first_fee_approved,
        'first_fee_approved_count': first_fee_approved_count,
        'first_fee_pending': first_fee_pending,
        'first_fee_pending_count': first_fee_pending_count,
        'first_fee_rejected': first_fee_rejected,
        'first_fee_rejected_count': first_fee_rejected_count,
        'first_fee_not_recorded_count': first_fee_not_recorded_count,
        'pending_fee_collected': pending_fee_collected,
        'pending_queue': pending_queue,
        'pending_queue_total_count': pending_queue_total_count,
        'pending_queue_total_amount': pending_queue_total_amount,
        'daily_stats': daily_stats,
        'branches': branches,
        'selected_branch_id': selected_branch_id,
        'start_date': start_date.strftime('%Y-%m-%d'),
        'end_date': end_date.strftime('%Y-%m-%d'),
        'portal_title': 'Financial Dashboard',
    }
    return render(request, 'accountant/dashboard.html', context)


@login_required
@accountant_required
def accountant_payment_verification(request):
    """
    Verification Queue and Ledger Table.
    Allows filtering by status (PENDING_VERIFICATION default, APPROVED, REJECTED, ALL),
    branch, counselor, date range, payment method, and search terms.
    """
    status_filter = request.GET.get('status', PaymentTransactionStatus.PENDING_VERIFICATION)
    method_filter = request.GET.get('method', '')
    counselor_filter = request.GET.get('counselor', '')
    query = request.GET.get('q', '').strip()
    start_date_str = request.GET.get('start_date', '')
    end_date_str = request.GET.get('end_date', '')

    branch_ids, selected_branch_id = get_accountant_scope(request.user, request.GET.get('branch'))

    payments = PaymentTransaction.objects.filter(
        enrollment__branch_id__in=branch_ids
    ).select_related(
        'enrollment',
        'enrollment__branch',
        'enrollment__product',
        'enrollment__assigned_counselor',
        'installment',
        'recorded_by',
        'reviewed_by'
    )

    if status_filter and status_filter != 'ALL':
        if status_filter == PaymentTransactionStatus.APPROVED:
            payments = payments.filter(status__in=[PaymentTransactionStatus.APPROVED, PaymentTransactionStatus.SUCCESS])
        else:
            payments = payments.filter(status=status_filter)

    if method_filter:
        payments = payments.filter(payment_method=method_filter)

    if counselor_filter and counselor_filter.isdigit():
        payments = payments.filter(recorded_by_id=int(counselor_filter))

    if start_date_str:
        try:
            sd = datetime.strptime(start_date_str, '%Y-%m-%d').date()
            dt_from = timezone.make_aware(datetime.combine(sd, time.min))
            payments = payments.filter(payment_date__gte=dt_from)
        except ValueError:
            pass

    if end_date_str:
        try:
            ed = datetime.strptime(end_date_str, '%Y-%m-%d').date()
            dt_to = timezone.make_aware(datetime.combine(ed, time.max))
            payments = payments.filter(payment_date__lte=dt_to)
        except ValueError:
            pass

    if query:
        payments = payments.filter(
            Q(receipt_number__icontains=query) |
            Q(transaction_reference__icontains=query) |
            Q(enrollment__student_name__icontains=query) |
            Q(enrollment__student_phone__icontains=query) |
            Q(enrollment__student_email__icontains=query) |
            Q(enrollment__enrollment_number__icontains=query)
        )

    # Order pending oldest first; others newest first
    if status_filter == PaymentTransactionStatus.PENDING_VERIFICATION:
        payments = payments.order_by('payment_date')
    else:
        payments = payments.order_by('-payment_date')

    # Summary counts for tab badges
    pending_count = PaymentTransaction.objects.filter(
        enrollment__branch_id__in=branch_ids,
        status=PaymentTransactionStatus.PENDING_VERIFICATION
    ).count()

    approved_count = PaymentTransaction.objects.filter(
        enrollment__branch_id__in=branch_ids,
        status__in=[PaymentTransactionStatus.APPROVED, PaymentTransactionStatus.SUCCESS]
    ).count()

    rejected_count = PaymentTransaction.objects.filter(
        enrollment__branch_id__in=branch_ids,
        status=PaymentTransactionStatus.REJECTED
    ).count()

    paginator = Paginator(payments, 25)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    branches = Branch.objects.filter(id__in=get_accessible_branch_ids(request.user), status='Active')
    counselors = User.objects.filter(
        role=UserRole.COUNSELOR,
        branch_id__in=branch_ids,
        is_active=True
    ).order_by('first_name')

    context = {
        'page_obj': page_obj,
        'payments': page_obj,
        'status_filter': status_filter,
        'method_filter': method_filter,
        'counselor_filter': counselor_filter,
        'search_query': query,
        'start_date': start_date_str,
        'end_date': end_date_str,
        'selected_branch_id': selected_branch_id,
        'branches': branches,
        'counselors': counselors,
        'payment_methods': PaymentMethod.choices,
        'pending_count': pending_count,
        'approved_count': approved_count,
        'rejected_count': rejected_count,
        'portal_title': 'Payment Verification Queue',
    }
    return render(request, 'accountant/verification_list.html', context)


@login_required
@accountant_required
@require_POST
def accountant_approve_payment(request, payment_id):
    """
    POST action to approve a pending payment transaction.
    Thread-safe, idempotent, updates ledger balances, and dispatches confirmation email.
    """
    payment = get_object_or_404(PaymentTransaction, id=payment_id)

    # Branch authorization
    accessible_branches = get_accessible_branch_ids(request.user)
    if payment.enrollment.branch_id not in accessible_branches:
        if request.headers.get('x-requested-with') == 'XMLHttpRequest':
            return JsonResponse({'success': False, 'message': 'Permission denied: Unauthorized branch.'}, status=403)
        raise PermissionDenied("You do not have access to this branch.")

    try:
        updated_payment = approve_payment(payment, request.user)
        msg = f"Payment #{updated_payment.receipt_number} of ₹{updated_payment.amount} has been successfully APPROVED. Ledger balances updated and receipt email dispatched."
        if request.headers.get('x-requested-with') == 'XMLHttpRequest':
            return JsonResponse({'success': True, 'message': msg})
        messages.success(request, msg)
    except ValidationError as ve:
        err_msg = ", ".join(ve.messages) if hasattr(ve, 'messages') else str(ve)
        if request.headers.get('x-requested-with') == 'XMLHttpRequest':
            return JsonResponse({'success': False, 'message': err_msg}, status=400)
        messages.error(request, f"Approval failed: {err_msg}")
    except Exception as exc:
        logger.exception("Error approving payment %s", payment_id)
        if request.headers.get('x-requested-with') == 'XMLHttpRequest':
            return JsonResponse({'success': False, 'message': f"Unexpected error: {exc}"}, status=500)
        messages.error(request, f"Error: {exc}")

    next_url = request.POST.get('next') or request.META.get('HTTP_REFERER') or 'accountant_payment_verification'
    return redirect(next_url)


@login_required
@accountant_required
@require_POST
def accountant_reject_payment(request, payment_id):
    """
    POST action to reject a pending payment with mandatory rejection comment.
    """
    payment = get_object_or_404(PaymentTransaction, id=payment_id)

    accessible_branches = get_accessible_branch_ids(request.user)
    if payment.enrollment.branch_id not in accessible_branches:
        if request.headers.get('x-requested-with') == 'XMLHttpRequest':
            return JsonResponse({'success': False, 'message': 'Permission denied: Unauthorized branch.'}, status=403)
        raise PermissionDenied("You do not have access to this branch.")

    comment = request.POST.get('rejection_comment', '').strip()
    if not comment:
        msg = "A rejection comment is mandatory. Please state the reason for rejecting this payment."
        if request.headers.get('x-requested-with') == 'XMLHttpRequest':
            return JsonResponse({'success': False, 'message': msg}, status=400)
        messages.error(request, msg)
        next_url = request.POST.get('next') or request.META.get('HTTP_REFERER') or 'accountant_payment_verification'
        return redirect(next_url)

    try:
        updated_payment = reject_payment(payment, request.user, comment)
        msg = f"Payment #{updated_payment.receipt_number} has been REJECTED. Counselor notified for correction."
        if request.headers.get('x-requested-with') == 'XMLHttpRequest':
            return JsonResponse({'success': True, 'message': msg})
        messages.warning(request, msg)
    except ValidationError as ve:
        err_msg = ", ".join(ve.messages) if hasattr(ve, 'messages') else str(ve)
        if request.headers.get('x-requested-with') == 'XMLHttpRequest':
            return JsonResponse({'success': False, 'message': err_msg}, status=400)
        messages.error(request, f"Rejection failed: {err_msg}")
    except Exception as exc:
        logger.exception("Error rejecting payment %s", payment_id)
        if request.headers.get('x-requested-with') == 'XMLHttpRequest':
            return JsonResponse({'success': False, 'message': f"Unexpected error: {exc}"}, status=500)
        messages.error(request, f"Error: {exc}")

    next_url = request.POST.get('next') or request.META.get('HTTP_REFERER') or 'accountant_payment_verification'
    return redirect(next_url)


@login_required
def accountant_payment_proof_view(request, payment_id):
    """
    Secure, access-controlled streaming endpoint for private payment proof screenshots/receipts.
    Only authorized accountants, assigned counselors, branch heads, or admins may view.
    """
    payment = get_object_or_404(PaymentTransaction, id=payment_id)

    if not payment.payment_proof:
        raise Http404("No payment proof attached to this record.")

    # Authorization check
    user = request.user
    user_branch_ids = get_accessible_branch_ids(user)
    has_access = False

    if user.is_admin_user or user.role == UserRole.ACCOUNTANT:
        has_access = payment.enrollment.branch_id in user_branch_ids
    elif user.role == UserRole.COUNSELOR:
        has_access = payment.enrollment.assigned_counselor_id == user.id or payment.recorded_by_id == user.id
    elif user.role in (UserRole.BRANCH_HEAD, UserRole.SALES_HEAD):
        has_access = payment.enrollment.branch_id in user_branch_ids

    if not has_access:
        raise PermissionDenied("You do not have permission to view this payment proof.")

    file_field = payment.payment_proof
    try:
        content_type, _ = mimetypes.guess_type(file_field.name)
        if not content_type:
            content_type = 'image/jpeg'
        return FileResponse(file_field.open('rb'), content_type=content_type, as_attachment=False)
    except FileNotFoundError:
        raise Http404("Payment proof file was not found on the server.")


@login_required
@accountant_required
def accountant_monthly_report_excel(request):
    """
    Generates a 7-sheet comprehensive monthly financial reconciliation Excel workbook:
    1. Executive Summary
    2. Cash Transactions
    3. Bank Transactions
    4. New Joinee First Fees
    5. Pending Fees Collected
    6. Outstanding Balances
    7. Verification Audit Log
    Includes currency formatting, auto-adjusted columns, and formula injection sanitization.
    """
    import openpyxl
    from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
    from openpyxl.utils import get_column_letter

    today = timezone.localdate()
    start_date_str = request.GET.get('start_date')
    end_date_str = request.GET.get('end_date')

    if start_date_str:
        try:
            start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date()
        except ValueError:
            start_date = today.replace(day=1)
    else:
        start_date = today.replace(day=1)

    if end_date_str:
        try:
            end_date = datetime.strptime(end_date_str, '%Y-%m-%d').date()
        except ValueError:
            end_date = today
    else:
        end_date = today

    start_dt = timezone.make_aware(datetime.combine(start_date, datetime.min.time()))
    end_dt = timezone.make_aware(datetime.combine(end_date, datetime.max.time()))

    branch_ids, selected_branch_id = get_accountant_scope(request.user, request.GET.get('branch'))

    # Styles
    navy_fill = PatternFill(start_color="1E293B", end_color="1E293B", fill_type="solid")
    indigo_fill = PatternFill(start_color="4338CA", end_color="4338CA", fill_type="solid")
    light_gray_fill = PatternFill(start_color="F1F5F9", end_color="F1F5F9", fill_type="solid")
    accent_fill = PatternFill(start_color="E0E7FF", end_color="E0E7FF", fill_type="solid")

    header_font = Font(name="Calibri", size=11, bold=True, color="FFFFFF")
    title_font = Font(name="Calibri", size=15, bold=True, color="1E293B")
    sub_title_font = Font(name="Calibri", size=10, italic=True, color="64748B")
    bold_font = Font(name="Calibri", size=11, bold=True)
    regular_font = Font(name="Calibri", size=11)

    thin_border_side = Side(border_style="thin", color="CBD5E1")
    cell_border = Border(left=thin_border_side, right=thin_border_side, top=thin_border_side, bottom=thin_border_side)
    thick_bottom = Border(bottom=Side(border_style="medium", color="1E293B"), top=thin_border_side)

    currency_fmt = "₹#,##0.00"
    date_fmt = "YYYY-MM-DD"
    datetime_fmt = "YYYY-MM-DD HH:MM"

    wb = openpyxl.Workbook()
    # Remove default sheet
    wb.remove(wb.active)

    approved_statuses = [PaymentTransactionStatus.APPROVED, PaymentTransactionStatus.SUCCESS]

    # ----------------------------------------------------
    # SHEET 1: EXECUTIVE SUMMARY
    # ----------------------------------------------------
    ws1 = wb.create_sheet(title="Executive Summary")
    ws1.views.sheetView[0].showGridLines = True

    ws1.append(["TECHPANDA CRM — FINANCIAL RECONCILIATION REPORT"])
    ws1.cell(1, 1).font = title_font
    ws1.append([f"Period: {start_date.strftime('%d-%b-%Y')} to {end_date.strftime('%d-%b-%Y')} | Generated: {timezone.now().strftime('%d-%b-%Y %H:%M')}"])
    ws1.cell(2, 1).font = sub_title_font
    ws1.append([])

    # Metrics calculation
    active_enr = Enrollment.objects.filter(branch_id__in=branch_ids, status=EnrollmentStatus.ACTIVE)
    total_dues = active_enr.aggregate(total=Sum('outstanding_balance'))['total'] or Decimal('0.00')

    period_payments = PaymentTransaction.objects.filter(
        enrollment__branch_id__in=branch_ids,
        payment_date__range=(start_dt, end_dt),
        status__in=approved_statuses
    )

    cash_txns = period_payments.filter(payment_method=PaymentMethod.CASH)
    cash_sum = cash_txns.aggregate(total=Sum('amount'))['total'] or Decimal('0.00')

    bank_methods = [PaymentMethod.UPI, PaymentMethod.BANK_TRANSFER, PaymentMethod.ONLINE, PaymentMethod.CARD, PaymentMethod.CHEQUE]
    bank_txns = period_payments.filter(payment_method__in=bank_methods)
    bank_sum = bank_txns.aggregate(total=Sum('amount'))['total'] or Decimal('0.00')

    total_coll = cash_sum + bank_sum

    # New joinees in period
    new_joinees = Enrollment.objects.filter(branch_id__in=branch_ids, enrollment_date__range=(start_date, end_date))
    first_fee_approved = PaymentTransaction.objects.filter(
        enrollment__in=new_joinees,
        status__in=approved_statuses
    ).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')

    pending_fee_collected = total_coll - first_fee_approved
    if pending_fee_collected < Decimal('0.00'):
        pending_fee_collected = Decimal('0.00')

    summary_rows = [
        ("Metric Description", "Count / Scope", "Amount (INR)"),
        ("1. Total Outstanding Fees Due (Active Enrollments)", active_enr.count(), total_dues),
        ("2. Total Received by Cash", cash_txns.count(), cash_sum),
        ("3. Total Received by Account (Bank/UPI/Card)", bank_txns.count(), bank_sum),
        ("4. Total Realized Revenue Collection", period_payments.count(), total_coll),
        ("5. New Joinee — First Fee Collection", new_joinees.count(), first_fee_approved),
        ("6. Subsequent Installment & Pending Fees Collected", "-", pending_fee_collected),
    ]

    for r_idx, row in enumerate(summary_rows, start=4):
        ws1.append([sanitize_for_excel(row[0]), sanitize_for_excel(row[1]), row[2] if isinstance(row[2], (int, Decimal, float)) else sanitize_for_excel(row[2])])
        if r_idx == 4:
            for c in range(1, 4):
                cell = ws1.cell(r_idx, c)
                cell.fill = navy_fill
                cell.font = header_font
                cell.alignment = Alignment(horizontal="center" if c > 1 else "left")
        else:
            for c in range(1, 4):
                cell = ws1.cell(r_idx, c)
                cell.font = regular_font
                cell.border = cell_border
                if c == 3:
                    cell.number_format = currency_fmt
                    cell.alignment = Alignment(horizontal="right")
                elif c == 2:
                    cell.alignment = Alignment(horizontal="center")

    # ----------------------------------------------------
    # Helper for Data Sheets
    # ----------------------------------------------------
    def build_transaction_sheet(title, queryset):
        ws = wb.create_sheet(title=title)
        ws.views.sheetView[0].showGridLines = True
        headers = [
            "Receipt No.", "Payment Date", "Student Name", "Phone",
            "Course / Product", "Branch", "Payment Method", "Amount",
            "Transaction Ref", "Status", "Recorded By", "Reviewed By", "Reviewed At"
        ]
        ws.append(headers)
        for c in range(1, len(headers) + 1):
            cell = ws.cell(1, c)
            cell.fill = indigo_fill
            cell.font = header_font
            cell.alignment = Alignment(horizontal="center", vertical="center")

        total_sum = Decimal('0.00')
        row_idx = 2
        for txn in queryset.select_related('enrollment', 'enrollment__branch', 'enrollment__product', 'recorded_by', 'reviewed_by'):
            ws.append([
                sanitize_for_excel(txn.receipt_number),
                txn.payment_date.strftime('%Y-%m-%d %H:%M') if txn.payment_date else '',
                sanitize_for_excel(txn.enrollment.student_name),
                sanitize_for_excel(txn.enrollment.student_phone),
                sanitize_for_excel(txn.enrollment.product.name if txn.enrollment.product else 'N/A'),
                sanitize_for_excel(txn.enrollment.branch.name if txn.enrollment.branch else 'N/A'),
                sanitize_for_excel(txn.payment_method),
                txn.amount,
                sanitize_for_excel(txn.transaction_reference or '-'),
                sanitize_for_excel(txn.status),
                sanitize_for_excel(txn.recorded_by.get_full_name() or txn.recorded_by.username if txn.recorded_by else 'System'),
                sanitize_for_excel(txn.reviewed_by.get_full_name() or txn.reviewed_by.username if txn.reviewed_by else '-'),
                txn.reviewed_at.strftime('%Y-%m-%d %H:%M') if txn.reviewed_at else '-',
            ])
            for c in range(1, len(headers) + 1):
                cell = ws.cell(row_idx, c)
                cell.font = regular_font
                cell.border = cell_border
                if c == 8:
                    cell.number_format = currency_fmt
                    cell.alignment = Alignment(horizontal="right")
            total_sum += txn.amount
            row_idx += 1

        # Summary row
        ws.append(["TOTAL", "", "", "", "", "", "", total_sum, "", "", "", "", ""])
        sum_row = ws.cell(row_idx, 1)
        sum_row.font = bold_font
        sum_cell = ws.cell(row_idx, 8)
        sum_cell.font = bold_font
        sum_cell.number_format = currency_fmt
        sum_cell.border = thick_bottom
        return ws

    # ----------------------------------------------------
    # SHEET 2: CASH TRANSACTIONS
    # ----------------------------------------------------
    build_transaction_sheet("Cash Transactions", cash_txns.order_by('-payment_date'))

    # ----------------------------------------------------
    # SHEET 3: BANK TRANSACTIONS
    # ----------------------------------------------------
    build_transaction_sheet("Bank Transactions", bank_txns.order_by('-payment_date'))

    # ----------------------------------------------------
    # SHEET 4: NEW JOINEE FIRST FEES
    # ----------------------------------------------------
    ws4 = wb.create_sheet(title="New Joinee First Fees")
    ws4.views.sheetView[0].showGridLines = True
    headers4 = [
        "Enrollment No.", "Enrollment Date", "Student Name", "Phone",
        "Course", "Branch", "Course Fee", "First Fee Amount",
        "Payment Method", "Verification Status", "Receipt No."
    ]
    ws4.append(headers4)
    for c in range(1, len(headers4) + 1):
        cell = ws4.cell(1, c)
        cell.fill = navy_fill
        cell.font = header_font
        cell.alignment = Alignment(horizontal="center")

    row_idx = 2
    nj_first_sum = Decimal('0.00')
    for enr in new_joinees.select_related('branch', 'product').order_by('-enrollment_date'):
        first_txn = enr.payments.order_by('payment_date').first()
        amt = first_txn.amount if first_txn else Decimal('0.00')
        method = first_txn.payment_method if first_txn else '-'
        st = first_txn.status if first_txn else 'Not Yet Recorded'
        rec = first_txn.receipt_number if first_txn else '-'
        ws4.append([
            sanitize_for_excel(enr.enrollment_number),
            enr.enrollment_date.strftime('%Y-%m-%d') if enr.enrollment_date else '',
            sanitize_for_excel(enr.student_name),
            sanitize_for_excel(enr.student_phone),
            sanitize_for_excel(enr.product.name if enr.product else 'N/A'),
            sanitize_for_excel(enr.branch.name if enr.branch else 'N/A'),
            enr.total_payable,
            amt,
            sanitize_for_excel(method),
            sanitize_for_excel(st),
            sanitize_for_excel(rec),
        ])
        for c in range(1, len(headers4) + 1):
            cell = ws4.cell(row_idx, c)
            cell.font = regular_font
            cell.border = cell_border
            if c in (7, 8):
                cell.number_format = currency_fmt
                cell.alignment = Alignment(horizontal="right")
        if first_txn and first_txn.status in approved_statuses:
            nj_first_sum += amt
        row_idx += 1

    ws4.append(["TOTAL APPROVED FIRST FEES", "", "", "", "", "", "", nj_first_sum, "", "", ""])
    ws4.cell(row_idx, 8).number_format = currency_fmt
    ws4.cell(row_idx, 8).font = bold_font

    # ----------------------------------------------------
    # SHEET 5: PENDING FEES COLLECTED (Installment 2+ / Prior Dues)
    # ----------------------------------------------------
    new_joinee_ids = set(new_joinees.values_list('id', flat=True))
    pending_fee_txns = period_payments.exclude(
        Q(enrollment_id__in=new_joinee_ids) & Q(installment__installment_number=1)
    ).order_by('-payment_date')
    build_transaction_sheet("Pending Fees Collected", pending_fee_txns)

    # ----------------------------------------------------
    # SHEET 6: OUTSTANDING BALANCES
    # ----------------------------------------------------
    ws6 = wb.create_sheet(title="Outstanding Balances")
    ws6.views.sheetView[0].showGridLines = True
    headers6 = [
        "Enrollment No.", "Student Name", "Phone", "Email",
        "Course", "Branch", "Assigned Counselor", "Total Payable",
        "Total Paid", "Outstanding Balance", "Next Due Date", "Payment Plan"
    ]
    ws6.append(headers6)
    for c in range(1, len(headers6) + 1):
        cell = ws6.cell(1, c)
        cell.fill = navy_fill
        cell.font = header_font
        cell.alignment = Alignment(horizontal="center")

    row_idx = 2
    out_sum = Decimal('0.00')
    dues_qs = active_enr.filter(outstanding_balance__gt=0).select_related('branch', 'product', 'assigned_counselor').order_by('-outstanding_balance')
    for enr in dues_qs:
        next_inst = enr.installments.filter(remaining_balance__gt=0).order_by('due_date').first()
        next_due = next_inst.due_date.strftime('%Y-%m-%d') if next_inst and next_inst.due_date else '-'
        ws6.append([
            sanitize_for_excel(enr.enrollment_number),
            sanitize_for_excel(enr.student_name),
            sanitize_for_excel(enr.student_phone),
            sanitize_for_excel(enr.student_email),
            sanitize_for_excel(enr.product.name if enr.product else 'N/A'),
            sanitize_for_excel(enr.branch.name if enr.branch else 'N/A'),
            sanitize_for_excel(enr.assigned_counselor.get_full_name() or enr.assigned_counselor.username if enr.assigned_counselor else 'Unassigned'),
            enr.total_payable,
            enr.total_paid,
            enr.outstanding_balance,
            sanitize_for_excel(next_due),
            sanitize_for_excel(enr.payment_plan),
        ])
        for c in range(1, len(headers6) + 1):
            cell = ws6.cell(row_idx, c)
            cell.font = regular_font
            cell.border = cell_border
            if c in (8, 9, 10):
                cell.number_format = currency_fmt
                cell.alignment = Alignment(horizontal="right")
        out_sum += enr.outstanding_balance
        row_idx += 1

    ws6.append(["TOTAL OUTSTANDING DUES", "", "", "", "", "", "", "", "", out_sum, "", ""])
    ws6.cell(row_idx, 10).number_format = currency_fmt
    ws6.cell(row_idx, 10).font = bold_font

    # ----------------------------------------------------
    # SHEET 7: VERIFICATION AUDIT LOG
    # ----------------------------------------------------
    ws7 = wb.create_sheet(title="Verification Audit Log")
    ws7.views.sheetView[0].showGridLines = True
    headers7 = [
        "Audit ID", "Timestamp", "Receipt No.", "Student Name",
        "Action Taken", "Performed By", "Actor Role", "Auditor Comment"
    ]
    ws7.append(headers7)
    for c in range(1, len(headers7) + 1):
        cell = ws7.cell(1, c)
        cell.fill = indigo_fill
        cell.font = header_font
        cell.alignment = Alignment(horizontal="center")

    audit_logs = PaymentVerificationHistory.objects.filter(
        payment__enrollment__branch_id__in=branch_ids,
        timestamp__range=(start_dt, end_dt)
    ).select_related('payment', 'payment__enrollment', 'performed_by').order_by('-timestamp')

    row_idx = 2
    for log in audit_logs:
        actor_name = log.performed_by.get_full_name() or log.performed_by.username if log.performed_by else 'System'
        actor_role = log.performed_by.role if log.performed_by else '-'
        ws7.append([
            log.id,
            log.timestamp.strftime('%Y-%m-%d %H:%M:%S'),
            sanitize_for_excel(log.payment.receipt_number),
            sanitize_for_excel(log.payment.enrollment.student_name),
            sanitize_for_excel(log.action),
            sanitize_for_excel(actor_name),
            sanitize_for_excel(actor_role),
            sanitize_for_excel(log.comment),
        ])
        for c in range(1, len(headers7) + 1):
            cell = ws7.cell(row_idx, c)
            cell.font = regular_font
            cell.border = cell_border
        row_idx += 1

    # Auto-adjust column widths across all sheets
    for ws in wb.worksheets:
        for col in ws.columns:
            max_len = 0
            col_letter = get_column_letter(col[0].column)
            for cell in col:
                val = str(cell.value or '')
                if len(val) > max_len:
                    max_len = len(val)
            ws.column_dimensions[col_letter].width = max(max_len + 3, 12)

    # Save to buffer and return response
    output = io.BytesIO()
    wb.save(output)
    output.seek(0)

    filename = f"TechPanda_Financial_Report_{start_date.strftime('%Y%m%d')}_{end_date.strftime('%Y%m%d')}.xlsx"
    response = HttpResponse(
        output.getvalue(),
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    return response

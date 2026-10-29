"""
Centralized Breadcrumb Resolver for TechPanda CRM.
Maps named Django URLs and context objects to hierarchical navigation items:
    [BreadcrumbItem(label="Dashboard", url="/admin/dashboard/"),
     BreadcrumbItem(label="All Leads", url="/admin/leads/"),
     BreadcrumbItem(label="Pooja Sundaram", url=None)]
"""
from dataclasses import dataclass
from typing import List, Optional
from django.urls import reverse, NoReverseMatch
from accounts.models import UserRole
from accounts.permissions import _ROLE_DASHBOARD_URL_NAMES


@dataclass
class BreadcrumbItem:
    label: str
    url: Optional[str] = None


def _safe_reverse(url_name: str, *args, **kwargs) -> Optional[str]:
    """Safely reverses a Django URL name without raising NoReverseMatch."""
    if not url_name:
        return None
    try:
        return reverse(url_name, args=args, kwargs=kwargs)
    except NoReverseMatch:
        return None


def _get_dashboard_url_name(user) -> str:
    """Returns the canonical dashboard URL name for the current user's role."""
    if not user or not user.is_authenticated:
        return 'login_redirect'
    if getattr(user, 'is_superuser', False) or getattr(user, 'is_admin_user', False):
        return 'admin_dashboard'
    return _ROLE_DASHBOARD_URL_NAMES.get(getattr(user, 'role', None), 'admin_dashboard')


def _clean_title(val: str, max_len: int = 32) -> str:
    """Cleans and truncates a dynamic string label."""
    s = str(val or '').strip()
    if len(s) > max_len:
        return s[:max_len - 1].rstrip() + '…'
    return s


def resolve_breadcrumbs(context) -> List[BreadcrumbItem]:
    """
    Given a template context (which includes request, user, and view context),
    resolves the active breadcrumb trail from root Dashboard to the current leaf page.
    """
    request = context.get('request')
    if not request or not hasattr(request, 'resolver_match') or not request.resolver_match:
        return []

    user = context.get('user') or getattr(request, 'user', None)
    if not user or not user.is_authenticated:
        return []

    url_name = request.resolver_match.url_name
    if not url_name:
        return []

    # Dashboard pages should not display redundant breadcrumbs
    dashboard_url_names = {
        'admin_dashboard', 'manager_dashboard', 'branch_head_dashboard',
        'counselor_dashboard', 'telecaller_dashboard', 'accountant_dashboard',
        'receptionist_dashboard', 'finance_dashboard', 'root', 'login_redirect'
    }
    if url_name in dashboard_url_names:
        return []

    # 1. Base Dashboard Item
    dash_url_name = _get_dashboard_url_name(user)
    dash_url = _safe_reverse(dash_url_name) or _safe_reverse('login_redirect')
    items: List[BreadcrumbItem] = [BreadcrumbItem(label='Dashboard', url=dash_url)]

    # 2. Extract dynamic context objects if available
    lead = context.get('lead')
    lead_name = _clean_title(getattr(lead, 'name', None) or 'Lead Profile') if lead else 'Lead Profile'
    lead_id = getattr(lead, 'pk', None)

    manager = context.get('manager') or context.get('sales_head')
    manager_name = _clean_title(manager.get_full_name() or manager.username) if manager else 'Sales Head'

    branch_head = context.get('branch_head')
    branch_head_name = _clean_title(branch_head.get_full_name() or branch_head.username) if branch_head else 'Branch Head'

    branch_admin = context.get('branch_admin')
    branch_admin_name = _clean_title(branch_admin.get_full_name() or branch_admin.username) if branch_admin else 'Branch Admin'

    counselor = context.get('counselor')
    counselor_name = _clean_title(counselor.get_full_name() or counselor.username) if counselor else 'Counselor'

    telecaller = context.get('telecaller')
    telecaller_name = _clean_title(telecaller.get_full_name() or telecaller.username) if telecaller else 'Telecaller'

    receptionist = context.get('receptionist')
    receptionist_name = _clean_title(receptionist.get_full_name() or receptionist.username) if receptionist else 'Receptionist'

    accountant = context.get('accountant')
    accountant_name = _clean_title(accountant.get_full_name() or accountant.username) if accountant else 'Accountant'

    branch = context.get('branch')
    branch_name = _clean_title(getattr(branch, 'name', None) or 'Branch') if branch else 'Branch'

    product = context.get('product') or context.get('course')
    product_name = _clean_title(getattr(product, 'name', None) or 'Course') if product else 'Course'

    channel = context.get('channel')
    channel_name = _clean_title(getattr(channel, 'name', None) or 'Channel') if channel else 'Channel'

    call = context.get('call')
    call_label = f"Call #{call.pk}" if call else "Call Details"

    # =========================================================================
    # URL Hierarchy Registry
    # =========================================================================

    # --- FINANCE HEAD PORTAL SUITE ---
    if url_name == 'finance_pending_payments':
        items.append(BreadcrumbItem(label='Pending Payments', url=None))
        return items
    if url_name == 'finance_approvals':
        items.append(BreadcrumbItem(label='Approvals', url=None))
        return items
    if url_name == 'finance_oversight':
        items.append(BreadcrumbItem(label='Finance Verification', url=None))
        return items
    if url_name == 'finance_expenses':
        items.append(BreadcrumbItem(label='Expenses & Ledger', url=None))
        return items
    if url_name == 'finance_internal_transfers':
        items.append(BreadcrumbItem(label='Internal Transfers', url=None))
        return items
    if url_name == 'finance_renewal_alerts':
        items.append(BreadcrumbItem(label='Renewal Alerts', url=None))
        return items
    if url_name == 'finance_employees':
        items.append(BreadcrumbItem(label='Employees', url=None))
        return items
    if url_name == 'finance_payroll':
        items.append(BreadcrumbItem(label='Payroll', url=None))
        return items
    if url_name == 'finance_salary_arrears':
        items.append(BreadcrumbItem(label='Salary Arrears', url=None))
        return items
    if url_name == 'finance_incentive_track':
        items.append(BreadcrumbItem(label='Incentive Track', url=None))
        return items
    if url_name == 'finance_settings':
        items.append(BreadcrumbItem(label='Finance Settings', url=None))
        return items

    # --- PIPELINE & KANBAN ---
    if url_name == 'leads_kanban':
        items.append(BreadcrumbItem(label='Pipeline (Kanban)', url=None))
        return items

    # --- REPORTS & ANALYTICS ---
    if url_name in ('admin_reports', 'manager_reports'):
        items.append(BreadcrumbItem(label='Reports & Analytics', url=None))
        return items
    if url_name == 'admin_telecaller_rnr_report':
        items.append(BreadcrumbItem(label='Reports & Analytics', url=_safe_reverse('admin_reports')))
        items.append(BreadcrumbItem(label='Telecaller Performance', url=None))
        return items
    if url_name == 'admin_counselor_rnr_report':
        items.append(BreadcrumbItem(label='Reports & Analytics', url=_safe_reverse('admin_reports')))
        items.append(BreadcrumbItem(label='Counselor Performance', url=None))
        return items

    # --- ADMIN LEADS & OPERATIONS ---
    if url_name == 'admin_leads_list':
        items.append(BreadcrumbItem(label='All Leads', url=None))
        return items
    if url_name == 'admin_lead_create':
        items.append(BreadcrumbItem(label='All Leads', url=_safe_reverse('admin_leads_list')))
        items.append(BreadcrumbItem(label='Add Lead', url=None))
        return items
    if url_name == 'admin_lead_detail':
        items.append(BreadcrumbItem(label='All Leads', url=_safe_reverse('admin_leads_list')))
        items.append(BreadcrumbItem(label=lead_name, url=None))
        return items
    if url_name == 'admin_lead_edit':
        items.append(BreadcrumbItem(label='All Leads', url=_safe_reverse('admin_leads_list')))
        if lead_id:
            items.append(BreadcrumbItem(label=lead_name, url=_safe_reverse('admin_lead_detail', lead_id)))
        else:
            items.append(BreadcrumbItem(label=lead_name, url=None))
        items.append(BreadcrumbItem(label='Edit Lead', url=None))
        return items
    if url_name == 'admin_leads_import':
        items.append(BreadcrumbItem(label='All Leads', url=_safe_reverse('admin_leads_list')))
        items.append(BreadcrumbItem(label='Import Leads', url=None))
        return items
    if url_name == 'admin_lead_queues':
        items.append(BreadcrumbItem(label='All Leads', url=_safe_reverse('admin_leads_list')))
        items.append(BreadcrumbItem(label='Allocation Queues', url=None))
        return items
    if url_name == 'admin_walkin_desk':
        items.append(BreadcrumbItem(label='All Leads', url=_safe_reverse('admin_leads_list')))
        items.append(BreadcrumbItem(label='Campus Walk-in Desk', url=None))
        return items
    if url_name in ('admin_duplicate_leads', 'admin_duplicate_leads_keep_single'):
        items.append(BreadcrumbItem(label='All Leads', url=_safe_reverse('admin_leads_list')))
        items.append(BreadcrumbItem(label='Duplicate Intelligence', url=None))
        return items
    if url_name == 'admin_enrolled_students':
        items.append(BreadcrumbItem(label='Student Enrollments', url=None))
        return items

    # Filtered Lead Lists
    filtered_lead_views = {
        'admin_interested_leads': 'Interested Leads',
        'admin_demo_scheduled_leads': 'Demo Scheduled',
        'admin_converted_leads': 'Converted Leads',
        'admin_lost_leads': 'Lost Leads',
        'admin_later_leads': 'Contact Later',
        'admin_discussion_leads': 'In Discussion',
        'admin_new_leads': 'New Inquiries',
    }
    if url_name in filtered_lead_views:
        items.append(BreadcrumbItem(label='All Leads', url=_safe_reverse('admin_leads_list')))
        items.append(BreadcrumbItem(label=filtered_lead_views[url_name], url=None))
        return items

    # --- TEAM & STAFF (ADMIN) ---
    # Sales Heads / Managers
    if url_name == 'admin_managers_list':
        items.append(BreadcrumbItem(label='Sales Heads', url=None))
        return items
    if url_name == 'admin_manager_create':
        items.append(BreadcrumbItem(label='Sales Heads', url=_safe_reverse('admin_managers_list')))
        items.append(BreadcrumbItem(label='Add Sales Head', url=None))
        return items
    if url_name == 'admin_manager_detail':
        items.append(BreadcrumbItem(label='Sales Heads', url=_safe_reverse('admin_managers_list')))
        items.append(BreadcrumbItem(label=manager_name, url=None))
        return items
    if url_name == 'admin_manager_edit':
        items.append(BreadcrumbItem(label='Sales Heads', url=_safe_reverse('admin_managers_list')))
        manager_id = getattr(manager, 'pk', None)
        if manager_id:
            items.append(BreadcrumbItem(label=manager_name, url=_safe_reverse('admin_manager_detail', manager_id)))
        items.append(BreadcrumbItem(label='Edit Sales Head', url=None))
        return items

    # Branch Heads
    if url_name == 'admin_branch_heads_list':
        items.append(BreadcrumbItem(label='Branch Heads', url=None))
        return items
    if url_name == 'admin_branch_head_create':
        items.append(BreadcrumbItem(label='Branch Heads', url=_safe_reverse('admin_branch_heads_list')))
        items.append(BreadcrumbItem(label='Add Branch Head', url=None))
        return items
    if url_name == 'admin_branch_head_detail':
        items.append(BreadcrumbItem(label='Branch Heads', url=_safe_reverse('admin_branch_heads_list')))
        items.append(BreadcrumbItem(label=branch_head_name, url=None))
        return items
    if url_name == 'admin_branch_head_edit':
        items.append(BreadcrumbItem(label='Branch Heads', url=_safe_reverse('admin_branch_heads_list')))
        bh_id = getattr(branch_head, 'pk', None)
        if bh_id:
            items.append(BreadcrumbItem(label=branch_head_name, url=_safe_reverse('admin_branch_head_detail', bh_id)))
        items.append(BreadcrumbItem(label='Edit Branch Head', url=None))
        return items

    # Branch Admins
    if url_name == 'admin_branch_admins_list':
        items.append(BreadcrumbItem(label='Branch Admins', url=None))
        return items
    if url_name == 'admin_branch_admin_create':
        items.append(BreadcrumbItem(label='Branch Admins', url=_safe_reverse('admin_branch_admins_list')))
        items.append(BreadcrumbItem(label='Add Branch Admin', url=None))
        return items
    if url_name == 'admin_branch_admin_detail':
        items.append(BreadcrumbItem(label='Branch Admins', url=_safe_reverse('admin_branch_admins_list')))
        items.append(BreadcrumbItem(label=branch_admin_name, url=None))
        return items
    if url_name == 'admin_branch_admin_edit':
        items.append(BreadcrumbItem(label='Branch Admins', url=_safe_reverse('admin_branch_admins_list')))
        ba_id = getattr(branch_admin, 'pk', None)
        if ba_id:
            items.append(BreadcrumbItem(label=branch_admin_name, url=_safe_reverse('admin_branch_admin_detail', ba_id)))
        items.append(BreadcrumbItem(label='Edit Branch Admin', url=None))
        return items

    # Counselors
    if url_name == 'admin_counselors_list':
        items.append(BreadcrumbItem(label='Counselors', url=None))
        return items
    if url_name == 'admin_counselor_create':
        items.append(BreadcrumbItem(label='Counselors', url=_safe_reverse('admin_counselors_list')))
        items.append(BreadcrumbItem(label='Add Counselor', url=None))
        return items
    if url_name == 'admin_counselor_detail':
        items.append(BreadcrumbItem(label='Counselors', url=_safe_reverse('admin_counselors_list')))
        items.append(BreadcrumbItem(label=counselor_name, url=None))
        return items

    # Telecallers
    if url_name == 'admin_telecallers_list':
        items.append(BreadcrumbItem(label='Telecallers', url=None))
        return items
    if url_name == 'admin_telecaller_create':
        items.append(BreadcrumbItem(label='Telecallers', url=_safe_reverse('admin_telecallers_list')))
        items.append(BreadcrumbItem(label='Add Telecaller', url=None))
        return items
    if url_name == 'admin_telecaller_detail':
        items.append(BreadcrumbItem(label='Telecallers', url=_safe_reverse('admin_telecallers_list')))
        items.append(BreadcrumbItem(label=telecaller_name, url=None))
        return items
    if url_name == 'admin_telecaller_edit':
        items.append(BreadcrumbItem(label='Telecallers', url=_safe_reverse('admin_telecallers_list')))
        tc_id = getattr(telecaller, 'pk', None)
        if tc_id:
            items.append(BreadcrumbItem(label=telecaller_name, url=_safe_reverse('admin_telecaller_detail', tc_id)))
        items.append(BreadcrumbItem(label='Edit Telecaller', url=None))
        return items
    if url_name == 'admin_telecaller_assign':
        items.append(BreadcrumbItem(label='Telecallers', url=_safe_reverse('admin_telecallers_list')))
        items.append(BreadcrumbItem(label='Assign Leads', url=None))
        return items

    # Receptionists
    if url_name == 'admin_receptionists_list':
        items.append(BreadcrumbItem(label='Receptionists', url=None))
        return items
    if url_name == 'admin_receptionist_create':
        items.append(BreadcrumbItem(label='Receptionists', url=_safe_reverse('admin_receptionists_list')))
        items.append(BreadcrumbItem(label='Add Receptionist', url=None))
        return items
    if url_name == 'admin_receptionist_detail':
        items.append(BreadcrumbItem(label='Receptionists', url=_safe_reverse('admin_receptionists_list')))
        items.append(BreadcrumbItem(label=receptionist_name, url=None))
        return items

    # Accountants
    if url_name == 'admin_accountants_list':
        items.append(BreadcrumbItem(label='Accountants', url=None))
        return items
    if url_name == 'admin_accountant_detail':
        items.append(BreadcrumbItem(label='Accountants', url=_safe_reverse('admin_accountants_list')))
        items.append(BreadcrumbItem(label=accountant_name, url=None))
        return items

    # --- SYSTEM & CONFIGURATION (ADMIN) ---
    if url_name == 'admin_branches_list':
        items.append(BreadcrumbItem(label='Branches', url=None))
        return items
    if url_name == 'admin_branch_create':
        items.append(BreadcrumbItem(label='Branches', url=_safe_reverse('admin_branches_list')))
        items.append(BreadcrumbItem(label='Add Branch', url=None))
        return items
    if url_name == 'admin_branch_edit':
        items.append(BreadcrumbItem(label='Branches', url=_safe_reverse('admin_branches_list')))
        items.append(BreadcrumbItem(label=f"Edit {branch_name}", url=None))
        return items

    if url_name == 'admin_products_list':
        items.append(BreadcrumbItem(label='Courses & Programs', url=None))
        return items
    if url_name == 'admin_product_create':
        items.append(BreadcrumbItem(label='Courses & Programs', url=_safe_reverse('admin_products_list')))
        items.append(BreadcrumbItem(label='Add Course', url=None))
        return items
    if url_name == 'admin_product_edit':
        items.append(BreadcrumbItem(label='Courses & Programs', url=_safe_reverse('admin_products_list')))
        items.append(BreadcrumbItem(label=f"Edit {product_name}", url=None))
        return items

    if url_name == 'admin_channels_list':
        items.append(BreadcrumbItem(label='Acquisition Channels', url=None))
        return items
    if url_name == 'admin_channel_create':
        items.append(BreadcrumbItem(label='Acquisition Channels', url=_safe_reverse('admin_channels_list')))
        items.append(BreadcrumbItem(label='Add Channel', url=None))
        return items
    if url_name == 'admin_channel_edit':
        items.append(BreadcrumbItem(label='Acquisition Channels', url=_safe_reverse('admin_channels_list')))
        items.append(BreadcrumbItem(label=f"Edit {channel_name}", url=None))
        return items

    if url_name == 'admin_lead_setup':
        items.append(BreadcrumbItem(label='Lead Allocation Setup', url=None))
        return items

    if url_name == 'admin_configuration':
        items.append(BreadcrumbItem(label='System Configuration', url=None))
        return items
    if url_name == 'admin_meta_manage':
        items.append(BreadcrumbItem(label='System Configuration', url=_safe_reverse('admin_configuration')))
        items.append(BreadcrumbItem(label='Meta Connection', url=None))
        return items

    if url_name == 'admin_activities_list':
        items.append(BreadcrumbItem(label='Activities & Logs', url=None))
        return items
    if url_name == 'admin_audit_logs':
        items.append(BreadcrumbItem(label='Audit Trail', url=None))
        return items
    if url_name == 'admin_calls_list':
        items.append(BreadcrumbItem(label='Call Logs', url=None))
        return items
    if url_name == 'admin_call_detail':
        items.append(BreadcrumbItem(label='Call Logs', url=_safe_reverse('admin_calls_list')))
        items.append(BreadcrumbItem(label=call_label, url=None))
        return items
    if url_name == 'admin_followups_list':
        items.append(BreadcrumbItem(label='Follow-ups', url=None))
        return items

    # --- COUNSELOR VIEWS ---
    if url_name == 'counselor_leads_list':
        items.append(BreadcrumbItem(label='My Leads', url=None))
        return items
    if url_name == 'counselor_lead_detail':
        items.append(BreadcrumbItem(label='My Leads', url=_safe_reverse('counselor_leads_list')))
        items.append(BreadcrumbItem(label=lead_name, url=None))
        return items
    if url_name == 'counselor_telecallers_list':
        items.append(BreadcrumbItem(label='My Telecallers', url=None))
        return items
    if url_name == 'counselor_telecaller_leads':
        items.append(BreadcrumbItem(label='My Telecallers', url=_safe_reverse('counselor_telecallers_list')))
        items.append(BreadcrumbItem(label=f"{telecaller_name}'s Leads", url=None))
        return items
    if url_name == 'counselor_followups_list':
        items.append(BreadcrumbItem(label='Follow-ups', url=None))
        return items
    if url_name == 'counselor_rnr_leads':
        items.append(BreadcrumbItem(label='RNR Follow-up', url=None))
        return items
    if url_name == 'counselor_unpicked_recalls':
        items.append(BreadcrumbItem(label='Unpicked Recalls', url=None))
        return items
    if url_name == 'counselor_enrolled_students':
        items.append(BreadcrumbItem(label='Enrolled Students', url=None))
        return items

    # --- TELECALLER VIEWS ---
    if url_name == 'telecaller_leads_list':
        items.append(BreadcrumbItem(label='My Leads', url=None))
        return items
    if url_name == 'telecaller_lead_create':
        items.append(BreadcrumbItem(label='My Leads', url=_safe_reverse('telecaller_leads_list')))
        items.append(BreadcrumbItem(label='Add Lead', url=None))
        return items
    if url_name == 'telecaller_lead_detail':
        items.append(BreadcrumbItem(label='My Leads', url=_safe_reverse('telecaller_leads_list')))
        items.append(BreadcrumbItem(label=lead_name, url=None))
        return items
    if url_name == 'telecaller_lead_edit':
        items.append(BreadcrumbItem(label='My Leads', url=_safe_reverse('telecaller_leads_list')))
        if lead_id:
            items.append(BreadcrumbItem(label=lead_name, url=_safe_reverse('telecaller_lead_detail', lead_id)))
        items.append(BreadcrumbItem(label='Edit Lead', url=None))
        return items
    if url_name == 'telecaller_followups_list':
        items.append(BreadcrumbItem(label='Follow-ups', url=None))
        return items
    if url_name == 'telecaller_calls_list':
        items.append(BreadcrumbItem(label='Call History', url=None))
        return items
    if url_name == 'telecaller_activities_list':
        items.append(BreadcrumbItem(label='Activity Feed', url=None))
        return items

    # --- MANAGER / SALES HEAD VIEWS ---
    if url_name == 'manager_leads_list':
        items.append(BreadcrumbItem(label='Leads', url=None))
        return items
    if url_name == 'manager_lead_create':
        items.append(BreadcrumbItem(label='Leads', url=_safe_reverse('manager_leads_list')))
        items.append(BreadcrumbItem(label='Add Lead', url=None))
        return items
    if url_name == 'manager_lead_detail':
        items.append(BreadcrumbItem(label='Leads', url=_safe_reverse('manager_leads_list')))
        items.append(BreadcrumbItem(label=lead_name, url=None))
        return items
    if url_name == 'manager_lead_edit':
        items.append(BreadcrumbItem(label='Leads', url=_safe_reverse('manager_leads_list')))
        if lead_id:
            items.append(BreadcrumbItem(label=lead_name, url=_safe_reverse('manager_lead_detail', lead_id)))
        items.append(BreadcrumbItem(label='Edit Lead', url=None))
        return items
    if url_name == 'manager_telecallers_list':
        items.append(BreadcrumbItem(label='Telecallers', url=None))
        return items
    if url_name == 'manager_telecaller_detail':
        items.append(BreadcrumbItem(label='Telecallers', url=_safe_reverse('manager_telecallers_list')))
        items.append(BreadcrumbItem(label=telecaller_name, url=None))
        return items
    if url_name == 'manager_followups_list':
        items.append(BreadcrumbItem(label='Follow-ups', url=None))
        return items
    if url_name == 'manager_activities_list':
        items.append(BreadcrumbItem(label='Activities', url=None))
        return items

    # --- BRANCH HEAD VIEWS ---
    if url_name == 'branch_head_leads_list':
        items.append(BreadcrumbItem(label='Branch Leads', url=None))
        return items
    if url_name == 'branch_head_lead_detail':
        items.append(BreadcrumbItem(label='Branch Leads', url=_safe_reverse('branch_head_leads_list')))
        items.append(BreadcrumbItem(label=lead_name, url=None))
        return items
    if url_name == 'branch_head_counselors_list':
        items.append(BreadcrumbItem(label='Counselors', url=None))
        return items
    if url_name == 'branch_head_counselor_create':
        items.append(BreadcrumbItem(label='Counselors', url=_safe_reverse('branch_head_counselors_list')))
        items.append(BreadcrumbItem(label='Add Counselor', url=None))
        return items
    if url_name == 'branch_head_counselor_detail':
        items.append(BreadcrumbItem(label='Counselors', url=_safe_reverse('branch_head_counselors_list')))
        items.append(BreadcrumbItem(label=counselor_name, url=None))
        return items
    if url_name == 'branch_head_telecallers_list':
        items.append(BreadcrumbItem(label='Telecallers', url=None))
        return items
    if url_name == 'branch_head_telecaller_detail':
        items.append(BreadcrumbItem(label='Telecallers', url=_safe_reverse('branch_head_telecallers_list')))
        items.append(BreadcrumbItem(label=telecaller_name, url=None))
        return items
    if url_name == 'branch_head_followups_list':
        items.append(BreadcrumbItem(label='Follow-ups', url=None))
        return items

    # --- ACCOUNTANT VIEWS ---
    if url_name == 'accountant_payment_verification':
        items.append(BreadcrumbItem(label='Payment Verification', url=None))
        return items
    if url_name == 'student_fee_ledger_view':
        items.append(BreadcrumbItem(label='Student Enrollments', url=_safe_reverse('admin_enrolled_students')))
        items.append(BreadcrumbItem(label='Student Fee Ledger', url=None))
        return items

    # --- RECEPTIONIST VIEWS ---
    if url_name in ('receptionist_dashboard', 'receptionist_walkin'):
        items.append(BreadcrumbItem(label='Reception Desk', url=None))
        return items

    # --- COMMON / UNIVERSAL VIEWS ---
    if url_name == 'user_profile':
        items.append(BreadcrumbItem(label='Settings', url=None))
        items.append(BreadcrumbItem(label='Profile & Security', url=None))
        return items
    if url_name == 'missed_calls_list':
        items.append(BreadcrumbItem(label='Missed Calls', url=None))
        return items
    if url_name in ('drive_call_recordings_list', 'call_recordings_list'):
        items.append(BreadcrumbItem(label='Call Recordings', url=None))
        return items
    if url_name in ('inbox', 'whatsapp_inbox', 'chat_inbox'):
        items.append(BreadcrumbItem(label='WhatsApp Inbox', url=None))
        return items
    if url_name in ('automation-list', 'automation-list-chat', 'chat_automations_list'):
        items.append(BreadcrumbItem(label='WhatsApp Inbox', url=_safe_reverse('inbox')))
        items.append(BreadcrumbItem(label='WhatsApp Automations', url=None))
        return items
    if url_name in ('flow-builder', 'flow-builder-detail', 'flow-builder-detail-builder',
                    'flow-builder-automations-pk', 'flow-builder-automations-builder',
                    'flow-builder-chat', 'flow-builder-detail-chat', 'flow-builder-chat-detail-builder',
                    'flow-builder-chat-automations-pk', 'flow-builder-chat-automations-builder'):
        items.append(BreadcrumbItem(label='WhatsApp Inbox', url=_safe_reverse('inbox')))
        items.append(BreadcrumbItem(label='WhatsApp Automations', url=_safe_reverse('automation-list')))
        items.append(BreadcrumbItem(label='Flow Builder', url=None))
        return items
    if url_name in ('whatsapp_campaigns_list', 'whatsapp_campaigns_list_alt'):
        items.append(BreadcrumbItem(label='WhatsApp Inbox', url=_safe_reverse('inbox')))
        items.append(BreadcrumbItem(label='Bulk Campaigns', url=None))
        return items
    if url_name in ('whatsapp_campaign_create', 'whatsapp_campaign_create_alt'):
        items.append(BreadcrumbItem(label='WhatsApp Inbox', url=_safe_reverse('inbox')))
        items.append(BreadcrumbItem(label='Bulk Campaigns', url=_safe_reverse('whatsapp_campaigns_list')))
        items.append(BreadcrumbItem(label='Create Campaign', url=None))
        return items
    if url_name == 'whatsapp_campaign_detail':
        items.append(BreadcrumbItem(label='WhatsApp Inbox', url=_safe_reverse('inbox')))
        items.append(BreadcrumbItem(label='Bulk Campaigns', url=_safe_reverse('whatsapp_campaigns_list')))
        items.append(BreadcrumbItem(label='Campaign Detail', url=None))
        return items
    if url_name == 'fb_accounts':
        items.append(BreadcrumbItem(label='Facebook Lead Ads', url=None))
        return items

    # --- FALLBACK FOR ANY OTHER AUTHENTICATED VIEW ---
    # Convert 'admin_something_list' or 'feature_name' into clean human title
    cleaned_name = url_name.replace('admin_', '').replace('_list', '').replace('_', ' ').title()
    items.append(BreadcrumbItem(label=cleaned_name, url=None))
    return items

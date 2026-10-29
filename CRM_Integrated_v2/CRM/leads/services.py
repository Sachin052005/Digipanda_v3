import csv
import io
import openpyxl
from django.db import transaction
from django.db.models import Count
from .models import Lead, LeadStatus, LeadImportHistory
from accounts.models import User, UserRole
from lead_channels.models import Channel
from products.models import Product
from branches.models import Branch
from activities.utils import log_activity
from .assignment import assign_lead_automatically
from .duplicates import find_duplicate_lead, handle_incoming_lead_duplicate, normalize_phone, normalize_email

def import_leads_file(uploaded_file, user):
    """
    Reusable file upload service for CSV/XLSX lead import.
    Applies role-scoped assignment, automatic manager & telecaller assignment,
    duplicate detection with update, and activity logging.
    """
    filename = uploaded_file.name
    rows = []

    if filename.endswith('.csv'):
        file_data = uploaded_file.read().decode('utf-8', errors='replace')
        io_string = io.StringIO(file_data)
        reader = csv.DictReader(io_string)
        for row in reader:
            rows.append(row)
    elif filename.endswith('.xlsx'):
        wb = openpyxl.load_workbook(uploaded_file, data_only=True)
        sheet = wb.active
        header = [str(cell.value or '').strip().lower() for cell in sheet[1]]
        for row_cells in sheet.iter_rows(min_row=2, values_only=True):
            if any(row_cells):
                row_dict = {}
                for h, val in zip(header, row_cells):
                    row_dict[h] = str(val or '').strip()
                rows.append(row_dict)
    else:
        raise ValueError("Unsupported file format. Please upload a .csv or .xlsx file.")

    total_records = len(rows)
    successful = 0
    failed = 0
    errors = []

    # Scoping attributes based on user role
    assigned_sales_head = None
    assigned_telecaller = None
    default_branch = None

    if user.is_telecaller_user:
        assigned_telecaller = user
        default_branch = user.branch
        if default_branch:
            access = default_branch.sales_head_access.select_related('sales_head').first()
            assigned_sales_head = access.sales_head if access else None
    elif user.is_sales_head_user:
        assigned_sales_head = user
        default_branch = user.branch

    with transaction.atomic():
        for idx, r in enumerate(rows, start=1):
            sp = transaction.savepoint()
            try:
                clean_row = {str(k).strip().lower(): str(v).strip() for k, v in r.items() if k}
                name = clean_row.get('name') or clean_row.get('lead name') or clean_row.get('full name')
                phone = clean_row.get('phone') or clean_row.get('mobile') or clean_row.get('phone number')
                email = clean_row.get('email', '')
                alt_phone = clean_row.get('alternate_phone') or clean_row.get('alt_phone', '')
                notes = clean_row.get('notes') or clean_row.get('remarks', '')

                if not name or not phone:
                    failed += 1
                    errors.append(f"Row {idx}: Name and Phone are required.")
                    transaction.savepoint_rollback(sp)
                    continue

                clean_phone = normalize_phone(phone)
                clean_alt_phone = normalize_phone(alt_phone) if alt_phone else ''
                clean_email = normalize_email(email) if email else ''

                if not clean_phone and not clean_email:
                    failed += 1
                    errors.append(f"Row {idx}: A valid phone number or email is required.")
                    transaction.savepoint_rollback(sp)
                    continue

                channel_name = clean_row.get('channel') or 'Offline'
                channel_obj = Channel.objects.filter(name__iexact=channel_name).first() if channel_name else None

                product_name = clean_row.get('product') or clean_row.get('course')
                product_obj = Product.objects.filter(name__iexact=product_name).first() if product_name else None

                branch_name = clean_row.get('branch')
                if branch_name:
                    branch_obj = Branch.objects.filter(name__iexact=branch_name).first() or default_branch
                else:
                    branch_obj = default_branch

                # Check duplicate in DB (by normalized phone, email, or details)
                search_phone = clean_phone if (clean_phone and not clean_phone.startswith('NoPhone-')) else phone
                existing_lead = find_duplicate_lead(phone=search_phone, email=clean_email or email, name=name)

                if existing_lead:
                    # Update existing lead and register branch without creating duplicate
                    handle_incoming_lead_duplicate(
                        existing_lead=existing_lead,
                        incoming_data={
                            'name': name,
                            'phone': search_phone,
                            'email': clean_email or email,
                            'alternate_phone': clean_alt_phone or alt_phone,
                            'product': product_obj,
                            'channel': channel_obj,
                            'notes': notes
                        },
                        branch=branch_obj,
                        user=user,
                        source_label=f"File Import '{filename}'"
                    )
                    transaction.savepoint_commit(sp)
                    successful += 1
                    continue

                # New Lead creation with normalized contact details
                new_lead = Lead(
                    name=name,
                    phone=search_phone,
                    email=clean_email or email,
                    alternate_phone=clean_alt_phone or alt_phone,
                    channel=channel_obj,
                    product=product_obj,
                    branch=branch_obj,
                    status=LeadStatus.NEW,
                    notes=notes
                )

                if user.is_telecaller_user:
                    new_lead.assigned_telecaller = assigned_telecaller
                    new_lead.assigned_sales_head = assigned_sales_head
                    new_lead.branch = branch_obj or default_branch
                elif user.is_sales_head_user:
                    new_lead.assigned_sales_head = assigned_sales_head
                    # Auto-assign an active telecaller within this sales head's accessible branches
                    from accounts.permissions import get_accessible_branch_ids
                    tc_qs = User.objects.filter(role=UserRole.TELECALLER, branch_id__in=get_accessible_branch_ids(user), is_active=True)
                    if branch_obj:
                        branch_tcs = tc_qs.filter(branch=branch_obj)
                        if branch_tcs.exists():
                            tc_qs = branch_tcs
                    new_lead.assigned_telecaller = tc_qs.annotate(cnt=Count('telecaller_leads')).order_by('cnt', 'id').first() if tc_qs.exists() else None
                    new_lead.branch = branch_obj or default_branch
                else:
                    # Admin or batch import: auto-assign manager and telecaller
                    assign_lead_automatically(
                        new_lead,
                        branch=branch_obj,
                        source=f"File Import '{filename}'",
                        triggered_by=user
                    )

                new_lead.save()
                transaction.savepoint_commit(sp)
                successful += 1
            except Exception as e:
                transaction.savepoint_rollback(sp)
                failed += 1
                errors.append(f"Row {idx}: {str(e)}")

    if failed == 0:
        import_status = "Completed"
    elif successful > 0:
        import_status = "Completed with Errors"
    else:
        import_status = "Failed"

    # Record history
    history = LeadImportHistory.objects.create(
        file_name=filename,
        uploaded_by=user,
        records=total_records,
        successful=successful,
        failed=failed,
        status=import_status,
        error_log="\n".join(errors[:100])
    )

    log_activity(
        user=user,
        action="Leads Imported",
        description=f"Batch lead import by {user.display_role} '{user.username}' from '{filename}': {successful} created, {failed} failed.",
        object_type="LeadImportHistory",
        object_id=history.pk
    )

    return successful, failed, errors


def get_user_assigned_leads(user):
    """
    Authoritative ownership queryset for a user's 'My Leads'.
    My Leads = leads currently assigned directly to the authenticated user,
    according to the application's authoritative current-assignment relationship.
    Being part of a team, branch, department, or reporting hierarchy must not
    automatically make another person's leads part of My Leads.
    """
    from .models import Lead, LeadOwnerType

    if not getattr(user, 'is_authenticated', False):
        return Lead.objects.none()

    if getattr(user, 'role', None) == UserRole.COUNSELOR:
        return Lead.objects.filter(
            assigned_counselor=user
        ).exclude(
            current_owner_type=LeadOwnerType.TELECALLER
        ).exclude(
            current_owner_type=LeadOwnerType.SALES_HEAD
        ).exclude(
            current_owner_type=LeadOwnerType.BRANCH_HEAD
        ).distinct()

    if getattr(user, 'role', None) == UserRole.TELECALLER:
        return Lead.objects.filter(
            assigned_telecaller=user
        ).exclude(
            current_owner_type=LeadOwnerType.COUNSELOR
        ).exclude(
            current_owner_type=LeadOwnerType.SALES_HEAD
        ).exclude(
            current_owner_type=LeadOwnerType.BRANCH_HEAD
        ).distinct()

    if getattr(user, 'role', None) == UserRole.BRANCH_HEAD:
        return Lead.objects.filter(
            assigned_branch_head=user
        ).distinct()

    if getattr(user, 'role', None) == UserRole.SALES_HEAD:
        return Lead.objects.filter(
            assigned_sales_head=user
        ).distinct()

    return Lead.objects.none()

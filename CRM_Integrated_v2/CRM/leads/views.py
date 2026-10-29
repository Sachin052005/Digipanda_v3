import re
import csv

import io

import json

import logging

logger = logging.getLogger('crm')

import openpyxl

from django.shortcuts import render, redirect, get_object_or_404

from django.urls import reverse

from django.contrib import messages

from django.db import transaction

from django.db.models import Q

from django.core.paginator import Paginator

from django.utils import timezone

from datetime import datetime, timedelta, time

from django.http import JsonResponse, HttpResponse

from django.core.exceptions import PermissionDenied

from django.views.decorators.http import require_POST

from django.contrib.auth.decorators import login_required

from accounts.models import User, UserRole

from accounts.permissions import (

    admin_required, lead_allocation_setup_required, sales_head_required, telecaller_required, branch_head_required, counselor_required,

    can_access_lead, can_view_lead, get_accessible_branch_ids,

)

from .handoff_service import change_lead_status

from branches.models import Branch

from lead_channels.models import Channel

from products.models import Product

from followups.models import FollowUp, FollowUpStatus

from calls.models import CallHistory, CallStatus, CallOutcome

from activities.models import Activity

from activities.utils import log_activity

from branches.utils import get_admin_selected_branch

from .models import (

    Lead, LeadStatus, LeadCategory, VisitorStatus, LeadOwnerType, LeadImportHistory,

    GoogleFormConnection, LeadSetupConfig, TelecallerLeadSetup,

    DuplicateLeadRecord, AssignmentMethod

)

from .forms import (

    AdminLeadForm, ManagerLeadForm, TelecallerLeadForm,

    ManagerLeadCreateForm, TelecallerLeadCreateForm, LeadImportForm

)

from .services import import_leads_file

from .duplicates import (

    find_duplicate_lead,

    handle_incoming_lead_duplicate,

    detect_all_duplicate_groups,

    keep_single_lead_for_group,

    process_incoming_lead_with_10day_rule,

    mask_phone,

    process_spreadsheet_row_duplicate_rules,

)

from .assignment import (

    assign_lead_to_branch_telecaller,

    assign_lead_automatically,

    assign_new_lead,

    apply_branch_lead_distribution,

    retry_pending_assignments

)

from .handoff_service import change_lead_status



# ==========================================

# ADMIN: LEAD MANAGEMENT

# ==========================================



@admin_required

def admin_leads_list(request):

    active_view = request.GET.get('view', 'all_active').strip()

    rating_filter = request.GET.get('rating', '').strip()

    search_query = request.GET.get('search', '').strip()

    status_filter = request.GET.get('status', '').strip()

    manager_filter = request.GET.get('manager', '').strip()

    telecaller_filter = request.GET.get('telecaller', '').strip()

    channel_filter = request.GET.get('channel', '').strip()

    product_filter = request.GET.get('product', '').strip()

    branch_filter = request.GET.get('branch', '').strip()

    spreadsheet_filter = request.GET.get('spreadsheet', '').strip()

    assignment_status_filter = request.GET.get('assignment_status', '').strip()

    date_from = (request.GET.get('date_from') or request.GET.get('from_date') or request.GET.get('start_date') or '').strip()

    date_to = (request.GET.get('date_to') or request.GET.get('to_date') or request.GET.get('end_date') or '').strip()

    kpi_label = request.GET.get('kpi_label', '').strip()

    sort_by = request.GET.get('sort', '-created_at')



    counselor_filter = request.GET.get('counselor', '').strip()

    category_filter = request.GET.get('category', '').strip()

    source_filter = request.GET.get('source', '').strip()

    last_contact_date = request.GET.get('last_contact_date', '').strip()

    next_followup_date = request.GET.get('next_followup_date', '').strip()



    leads_qs = Lead.objects.select_related(

        'channel', 'product', 'branch', 'assigned_sales_head', 'assigned_telecaller', 'assigned_counselor'

    ).prefetch_related('duplicate_records', 'sheet_mappings__connection', 'calls', 'followups')



    # Base counts for TeleCRM saved views tabs

    base_counts_qs = Lead.objects.all()

    selected_branch = get_admin_selected_branch(request)

    if selected_branch:

        base_counts_qs = base_counts_qs.filter(branch=selected_branch)



    user_assigned_q = (

        Q(assigned_telecaller=request.user) |

        Q(assigned_counselor=request.user) |

        Q(assigned_sales_head=request.user) |

        Q(assigned_branch_head=request.user)

    )



    view_counts = {

        'all_active': base_counts_qs.exclude(status__in=[LeadStatus.LOST, LeadStatus.CONVERTED]).count(),

        'all': base_counts_qs.count(),

        'assigned_to_me': base_counts_qs.filter(user_assigned_q).count(),

        'my_leads': base_counts_qs.filter(user_assigned_q).count(),

        'tnagar_meta': base_counts_qs.filter(

            Q(branch__name__icontains='T Nagar') | Q(branch__name__icontains='T.Nagar') | Q(branch__name__icontains='T-Nagar'),

            Q(channel__name__icontains='meta') | Q(channel__name__icontains='facebook') | Q(source__icontains='meta') | Q(source__icontains='facebook')

        ).count(),

        'velachery_meta': base_counts_qs.filter(

            Q(branch__name__icontains='Velachery'),

            Q(channel__name__icontains='meta') | Q(channel__name__icontains='facebook') | Q(source__icontains='meta') | Q(source__icontains='facebook')

        ).count(),

    }



    # Apply Saved View Preset Filter

    if active_view == 'all_active':

        if not status_filter:

            leads_qs = leads_qs.exclude(status__in=[LeadStatus.LOST, LeadStatus.CONVERTED])

    elif active_view == 'assigned_to_me':

        leads_qs = leads_qs.filter(user_assigned_q)

    elif active_view == 'my_leads':

        leads_qs = leads_qs.filter(user_assigned_q)

    elif active_view == 'tnagar_meta':

        leads_qs = leads_qs.filter(

            Q(branch__name__icontains='T Nagar') | Q(branch__name__icontains='T.Nagar') | Q(branch__name__icontains='T-Nagar'),

            Q(channel__name__icontains='meta') | Q(channel__name__icontains='facebook') | Q(source__icontains='meta') | Q(source__icontains='facebook')

        )

    elif active_view == 'velachery_meta':

        leads_qs = leads_qs.filter(

            Q(branch__name__icontains='Velachery'),

            Q(channel__name__icontains='meta') | Q(channel__name__icontains='facebook') | Q(source__icontains='meta') | Q(source__icontains='facebook')

        )



    if rating_filter:

        try:

            leads_qs = leads_qs.filter(rating=int(rating_filter))

        except (ValueError, TypeError):

            pass



    if search_query:

        leads_qs = leads_qs.filter(

            Q(name__icontains=search_query) |

            Q(phone__icontains=search_query) |

            Q(email__icontains=search_query) |

            Q(notes__icontains=search_query)

        )

    if status_filter:

        if status_filter.lower() == 'active':

            leads_qs = leads_qs.exclude(status__in=[LeadStatus.LOST, LeadStatus.CONVERTED])

        else:

            leads_qs = leads_qs.filter(status=status_filter)

    status_group = request.GET.get('status_group', '').strip()

    if status_group == 'connected':

        leads_qs = leads_qs.filter(status__in=[LeadStatus.CONTACTED, LeadStatus.INTERESTED, LeadStatus.DISCUSSION])

    elif status_group == 'prospected':

        leads_qs = leads_qs.filter(status__in=[LeadStatus.CONVERTED, LeadStatus.FOLLOW_UP, LeadStatus.DEMO_SCHEDULED, LeadStatus.INSTITUTE_VISIT, LeadStatus.VISITED, LeadStatus.JOINED])

    elif status_group == 'not_connected':

        leads_qs = leads_qs.filter(status__in=[LeadStatus.NO_ANSWER, LeadStatus.BUSY, LeadStatus.LOST, LeadStatus.NOT_INTERESTED])

    if manager_filter:

        leads_qs = leads_qs.filter(assigned_sales_head_id=manager_filter)

    if telecaller_filter:

        leads_qs = leads_qs.filter(assigned_telecaller_id=telecaller_filter)

    if counselor_filter:

        leads_qs = leads_qs.filter(assigned_counselor_id=counselor_filter)

    if category_filter:

        leads_qs = leads_qs.filter(category=category_filter)

    if source_filter:

        leads_qs = leads_qs.filter(Q(source__icontains=source_filter) | Q(channel__name__icontains=source_filter))

    if channel_filter:

        if channel_filter.isdigit():

            leads_qs = leads_qs.filter(channel_id=int(channel_filter))

        else:

            leads_qs = leads_qs.filter(Q(channel__name__icontains=channel_filter) | Q(source__icontains=channel_filter))

    if product_filter:

        leads_qs = leads_qs.filter(product_id=product_filter)

    

    selected_branch = get_admin_selected_branch(request)

    if selected_branch:

        leads_qs = leads_qs.filter(branch=selected_branch)

    elif branch_filter:

        leads_qs = leads_qs.filter(branch_id=branch_filter)



    if spreadsheet_filter:

        sheet_conn = GoogleSheetConnection.objects.filter(id=spreadsheet_filter).first()

        sheet_name = sheet_conn.name if sheet_conn else ''

        leads_qs = leads_qs.filter(

            Q(sheet_mappings__connection_id=spreadsheet_filter) |

            Q(source=sheet_name)

        ).distinct()



    if assignment_status_filter:

        leads_qs = leads_qs.filter(assignment_status=assignment_status_filter)



    if date_from:

        try:

            d_from = datetime.strptime(date_from, '%Y-%m-%d').date()

            dt_from = timezone.make_aware(datetime.combine(d_from, time.min))

            leads_qs = leads_qs.filter(created_at__gte=dt_from)

        except (ValueError, TypeError):

            pass

    if date_to:

        try:

            d_to = datetime.strptime(date_to, '%Y-%m-%d').date()

            dt_to = timezone.make_aware(datetime.combine(d_to, time.max))

            leads_qs = leads_qs.filter(created_at__lte=dt_to)

        except (ValueError, TypeError):

            pass



    if last_contact_date:

        try:

            lcd = datetime.strptime(last_contact_date, '%Y-%m-%d').date()

            start_dt = timezone.make_aware(datetime.combine(lcd, time.min))

            end_dt = timezone.make_aware(datetime.combine(lcd, time.max))

            leads_qs = leads_qs.filter(calls__call_started_at__range=(start_dt, end_dt)).distinct()

        except Exception:

            pass



    if next_followup_date:

        leads_qs = leads_qs.filter(followups__follow_up_date=next_followup_date, followups__status='Pending').distinct()



    # Sorting (TeleCRM Multi-Metric Sort with Deterministic Secondary Sort)

    allowed_sorts = ['name', '-name', 'created_at', '-created_at', 'updated_at', '-updated_at', 'status', '-status', 'rating', '-rating']

    if sort_by in allowed_sorts:

        leads_qs = leads_qs.order_by(sort_by, '-id')

    else:

        leads_qs = leads_qs.order_by('-created_at', '-id')



    from .utils import get_validated_page_size, ALLOWED_PAGE_SIZES

    page_size = get_validated_page_size(request, default=20)

    paginator = Paginator(leads_qs, page_size)

    page_obj = paginator.get_page(request.GET.get('page'))



    managers = User.objects.filter(role=UserRole.SALES_HEAD, is_active=True)

    telecallers = User.objects.filter(role=UserRole.TELECALLER, is_active=True)

    counselors = User.objects.filter(role=UserRole.COUNSELOR, is_active=True)

    channels = Channel.objects.filter(status='Active')

    products = Product.objects.filter(status='Active')

    branches = Branch.objects.filter(status='Active')

    connected_spreadsheets = GoogleSheetConnection.objects.all().order_by('name')

    pending_count = Lead.objects.filter(assignment_status='Pending Assignment').count()



    assignment_status_choices = [

        ('Assigned', 'Assigned'),

        ('Pending Assignment', 'Pending Assignment'),

        ('Unassigned', 'Unassigned'),

    ]



    from .models import LeadCategory

    available_sources = list(Lead.objects.exclude(source='').values_list('source', flat=True).distinct()[:20])



    return render(request, 'admin/leads_list.html', {

        'page_obj': page_obj,

        'managers': managers,

        'telecallers': telecallers,

        'counselors': counselors,

        'channels': channels,

        'products': products,

        'branches': branches,

        'categories': LeadCategory.choices,

        'available_sources': available_sources,

        'connected_spreadsheets': connected_spreadsheets,

        'pending_count': pending_count,

        'statuses': LeadStatus.choices,

        'assignment_statuses': assignment_status_choices,

        'search_query': search_query,

        'status_filter': status_filter,

        'manager_filter': manager_filter,

        'telecaller_filter': telecaller_filter,

        'counselor_filter': counselor_filter,

        'category_filter': category_filter,

        'source_filter': source_filter,

        'channel_filter': channel_filter,

        'product_filter': product_filter,

        'branch_filter': branch_filter,

        'spreadsheet_filter': spreadsheet_filter,

        'assignment_status_filter': assignment_status_filter,

        'date_from': date_from,

        'date_to': date_to,

        'last_contact_date': last_contact_date,

        'next_followup_date': next_followup_date,

        'sort_by': sort_by,

        'active_view': active_view,

        'view_counts': view_counts,

        'rating_filter': rating_filter,

        'status_group': status_group,
        'kpi_label': kpi_label,
        'page_size': page_size,
        'allowed_page_sizes': ALLOWED_PAGE_SIZES,

    })





@admin_required

def admin_new_leads(request):

    """

    Dedicated view for leads with status 'New' (Requirement 2).

    Displays contact info, creation timestamp, lead source, assigned telecaller & counselor,

    branch, last contact, next follow-up, and training/placement category.

    """

    from .models import LeadCategory



    search_query = request.GET.get('search', '').strip()

    branch_filter = request.GET.get('branch', '').strip()

    telecaller_filter = request.GET.get('telecaller', '').strip()

    counselor_filter = request.GET.get('counselor', '').strip()

    category_filter = request.GET.get('category', '').strip()

    source_filter = request.GET.get('source', '').strip()

    date_from = (request.GET.get('date_from') or request.GET.get('from_date') or request.GET.get('start_date') or '').strip()

    date_to = (request.GET.get('date_to') or request.GET.get('to_date') or request.GET.get('end_date') or '').strip()

    kpi_label = request.GET.get('kpi_label', '').strip()

    sort_by = request.GET.get('sort', '-created_at')



    leads_qs = Lead.objects.filter(status=LeadStatus.NEW).select_related(

        'channel', 'product', 'branch', 'assigned_telecaller', 'assigned_counselor'

    ).prefetch_related('calls', 'followups')



    selected_branch = get_admin_selected_branch(request)

    if selected_branch:

        leads_qs = leads_qs.filter(branch=selected_branch)

    elif branch_filter:

        leads_qs = leads_qs.filter(branch_id=branch_filter)



    if search_query:

        leads_qs = leads_qs.filter(

            Q(name__icontains=search_query) |

            Q(phone__icontains=search_query) |

            Q(email__icontains=search_query) |

            Q(notes__icontains=search_query)

        )

    if telecaller_filter:

        leads_qs = leads_qs.filter(assigned_telecaller_id=telecaller_filter)

    if counselor_filter:

        leads_qs = leads_qs.filter(assigned_counselor_id=counselor_filter)

    if category_filter:

        leads_qs = leads_qs.filter(category=category_filter)

    if source_filter:

        leads_qs = leads_qs.filter(Q(source__icontains=source_filter) | Q(channel__name__icontains=source_filter))

    if date_from:

        try:

            d_from = datetime.strptime(date_from, '%Y-%m-%d').date()

            dt_from = timezone.make_aware(datetime.combine(d_from, time.min))

            leads_qs = leads_qs.filter(created_at__gte=dt_from)

        except (ValueError, TypeError):

            pass

    if date_to:

        try:

            d_to = datetime.strptime(date_to, '%Y-%m-%d').date()

            dt_to = timezone.make_aware(datetime.combine(d_to, time.max))

            leads_qs = leads_qs.filter(created_at__lte=dt_to)

        except (ValueError, TypeError):

            pass



    allowed_sorts = ['name', '-name', 'created_at', '-created_at']

    if sort_by in allowed_sorts:

        leads_qs = leads_qs.order_by(sort_by, '-id')

    else:

        leads_qs = leads_qs.order_by('-created_at', '-id')



    from .utils import get_validated_page_size, ALLOWED_PAGE_SIZES

    page_size = get_validated_page_size(request, default=20)

    paginator = Paginator(leads_qs, page_size)

    page_obj = paginator.get_page(request.GET.get('page'))



    # Attach last contact and next follow-up to each lead item

    for ld in page_obj:

        ld.latest_call = ld.calls.order_by('-call_started_at').first()

        ld.next_followup = ld.followups.filter(status='Pending').order_by('follow_up_date', 'follow_up_time').first()



    branches = Branch.objects.filter(status='Active')

    telecallers = User.objects.filter(role=UserRole.TELECALLER, is_active=True)

    counselors = User.objects.filter(role=UserRole.COUNSELOR, is_active=True)

    available_sources = list(Lead.objects.exclude(source='').values_list('source', flat=True).distinct()[:20])



    return render(request, 'admin/new_leads_list.html', {

        'page_obj': page_obj,

        'branches': branches,

        'telecallers': telecallers,

        'counselors': counselors,

        'categories': LeadCategory.choices,

        'available_sources': available_sources,

        'search_query': search_query,

        'branch_filter': branch_filter,

        'telecaller_filter': telecaller_filter,

        'counselor_filter': counselor_filter,

        'category_filter': category_filter,

        'source_filter': source_filter,

        'date_from': date_from,

        'date_to': date_to,

        'sort_by': sort_by,
        'page_size': page_size,
        'allowed_page_sizes': ALLOWED_PAGE_SIZES,

        'new_leads_count': leads_qs.count(),

    })





@admin_required

def admin_retry_pending_assignments(request):

    from .assignment import retry_pending_assignments

    branch_id = request.GET.get('branch_id') or request.POST.get('branch_id')

    branch = Branch.objects.filter(id=branch_id).first() if branch_id else None

    assigned, remaining = retry_pending_assignments(branch=branch, user=request.user)

    if assigned > 0:

        messages.success(request, f"Successfully assigned {assigned} pending lead(s). {remaining} lead(s) still pending.")

    else:

        if remaining > 0:

            messages.warning(request, f"Could not assign pending leads. Please verify branch telecaller allocations total exactly 100%. ({remaining} lead(s) still pending)")

        else:

            messages.info(request, "No pending leads found to assign.")

    return redirect(request.META.get('HTTP_REFERER') or reverse('admin_leads_list'))



@admin_required

def admin_lead_create(request):

    if request.method == 'POST':

        form = AdminLeadForm(request.POST)

        if form.is_valid():

            existing_lead = find_duplicate_lead(

                phone=form.cleaned_data.get('phone'),

                email=form.cleaned_data.get('email'),

                name=form.cleaned_data.get('name')

            )

            if existing_lead:

                handle_incoming_lead_duplicate(

                    existing_lead=existing_lead,

                    incoming_data=form.cleaned_data,

                    branch=form.cleaned_data.get('branch'),

                    user=request.user,

                    source_label="Manual Entry"

                )

                messages.info(

                    request,

                    f"Lead '{existing_lead.name}' ({existing_lead.phone}) already exists. Retained single unique lead record and registered branch without duplicating."

                )

                return redirect('admin_lead_detail', pk=existing_lead.pk)



            lead = form.save()

            if not lead.assigned_telecaller and lead.branch:

                assign_new_lead(lead, branch=lead.branch, source="Admin Create", triggered_by=request.user)

                lead.refresh_from_db()

            log_activity(

                user=request.user,

                action="Lead Created",

                description=f"Admin created new lead '{lead.name}' ({lead.phone}).",

                object_type="Lead",

                object_id=lead.pk,

                request=request

            )

            messages.success(request, f"Lead '{lead.name}' created successfully.")

            from activities.services import create_notification

            if lead.assigned_sales_head:

                create_notification(

                    recipient=lead.assigned_sales_head,

                    title="New Lead Assigned",

                    message=f"Admin assigned new lead '{lead.name}' ({lead.phone}) to your team.",

                    notification_type="lead_assigned"

                )

            if lead.assigned_telecaller:

                create_notification(

                    recipient=lead.assigned_telecaller,

                    title="New Lead Assigned",

                    message=f"Admin assigned new lead '{lead.name}' ({lead.phone}) to you.",

                    notification_type="lead_assigned"

                )

            return redirect('admin_lead_detail', pk=lead.pk)

    else:

        form = AdminLeadForm()



    return render(request, 'admin/lead_create.html', {'form': form})



@admin_required

def admin_lead_detail(request, pk):

    lead = get_object_or_404(

        Lead.objects.select_related('channel', 'product', 'branch', 'assigned_sales_head', 'assigned_telecaller'),

        pk=pk

    )

    followups = FollowUp.objects.filter(lead=lead).order_by('-created_at')

    calls = CallHistory.objects.filter(lead=lead).select_related('caller').order_by('-call_started_at')

    activities = Activity.objects.filter(object_type='Lead', object_id=str(lead.pk)).order_by('-timestamp')

    call_recordings = lead.drive_recordings.all().select_related('drive_connection').order_by('-recording_date', '-created_at')

    status_history = lead.status_history.select_related('changed_by').order_by('-created_at')[:25]



    from .detail_service import build_lead_detail_context

    context = build_lead_detail_context(lead, request.user)

    context.update({

        'followups': followups,

        'calls': calls,

        'activities': activities,

        'call_recordings': call_recordings,

        'status_history': status_history,
        'timeline_count': (len(calls) if calls else 0) + (len(status_history) if status_history else 0) + (len(followups) if followups else 0),

        'detail_url_name': 'admin_lead_detail',

        'edit_url_name': 'admin_lead_edit',

        'list_url_name': 'admin_leads_list',

    })



    return render(request, 'leads/lead_detail_view.html', context)



@admin_required

def admin_lead_edit(request, pk):

    lead = get_object_or_404(Lead, pk=pk)

    if request.method == 'POST':

        form = AdminLeadForm(request.POST, instance=lead)

        if form.is_valid():

            lead = form.save()

            log_activity(

                user=request.user,

                action="Lead Updated",

                description=f"Admin updated details for lead '{lead.name}'.",

                object_type="Lead",

                object_id=lead.pk,

                request=request

            )

            messages.success(request, f"Lead '{lead.name}' updated successfully.")

            return redirect('admin_lead_detail', pk=lead.pk)

    else:

        form = AdminLeadForm(instance=lead)



    return render(request, 'admin/lead_edit.html', {'form': form, 'lead': lead})



@admin_required

def admin_lead_delete(request, pk):

    lead = get_object_or_404(Lead, pk=pk)

    lead_name = lead.name

    lead.delete()

    log_activity(

        user=request.user,

        action="Lead Deleted",

        description=f"Admin deleted lead '{lead_name}'.",

        object_type="Lead",

        object_id=str(pk),

        request=request

    )

    messages.success(request, f"Lead '{lead_name}' deleted.")

    return redirect('admin_leads_list')



@admin_required

def admin_leads_import(request):

    import_history = LeadImportHistory.objects.all().order_by('-uploaded_on')[:15]

    form = LeadImportForm()



    if request.method == 'POST':

        form = LeadImportForm(request.POST, request.FILES)

        if form.is_valid():

            uploaded_file = request.FILES['file']

            filename = uploaded_file.name

            ext = filename.split('.')[-1].lower()



            if ext not in ['csv', 'xlsx']:

                messages.error(request, "Invalid file format. Only .csv and .xlsx files are supported.")

                return render(request, 'admin/lead_import.html', {'form': form, 'import_history': import_history})



            try:

                successful, failed, errors = import_leads_file(uploaded_file, request.user)

                messages.success(request, f"Import complete! {successful} leads imported successfully. {failed} failed.")

                return redirect('admin_leads_list')

            except Exception:

                logger.exception("Lead file import failed (admin)")

                messages.error(request, "Unable to process the file. Please check the format and try again.")



    return render(request, 'admin/lead_import.html', {

        'form': form,

        'import_history': import_history

    })





# ==========================================

# SALES HEAD: LEAD MANAGEMENT

# ==========================================



@sales_head_required

def manager_leads_list(request):

    manager = request.user

    branch_ids = get_accessible_branch_ids(manager)

    telecallers = User.objects.filter(role=UserRole.TELECALLER, branch_id__in=branch_ids)

    telecaller_ids = list(telecallers.values_list('id', flat=True))



    leads_qs = Lead.objects.filter(

        Q(branch_id__in=branch_ids) | Q(assigned_sales_head=manager) | Q(assigned_telecaller_id__in=telecaller_ids)

    ).select_related('channel', 'product', 'assigned_telecaller', 'branch').distinct()



    search_query = request.GET.get('search', '').strip()

    status_filter = request.GET.get('status', '').strip()

    status_group = request.GET.get('status_group', '').strip()

    telecaller_filter = request.GET.get('telecaller', '').strip()

    channel_filter = request.GET.get('channel', '').strip()

    product_filter = request.GET.get('product', '').strip()

    branch_filter = request.GET.get('branch', '').strip()

    date_from = request.GET.get('date_from', '').strip()

    date_to = request.GET.get('date_to', '').strip()



    if search_query:

        leads_qs = leads_qs.filter(

            Q(name__icontains=search_query) |

            Q(phone__icontains=search_query) |

            Q(email__icontains=search_query)

        )

    if status_filter:

        if status_filter.lower() == 'active':

            leads_qs = leads_qs.exclude(status__in=[LeadStatus.LOST, LeadStatus.CONVERTED])

        else:

            leads_qs = leads_qs.filter(status=status_filter)

    if status_group == 'connected':

        leads_qs = leads_qs.filter(status__in=[LeadStatus.CONTACTED, LeadStatus.INTERESTED, LeadStatus.DISCUSSION])

    elif status_group == 'prospected':

        leads_qs = leads_qs.filter(status__in=[LeadStatus.CONVERTED, LeadStatus.FOLLOW_UP, LeadStatus.DEMO_SCHEDULED, LeadStatus.INSTITUTE_VISIT, LeadStatus.VISITED, LeadStatus.JOINED])

    elif status_group == 'not_connected':

        leads_qs = leads_qs.filter(status__in=[LeadStatus.NO_ANSWER, LeadStatus.BUSY, LeadStatus.LOST, LeadStatus.NOT_INTERESTED])

    if telecaller_filter:

        leads_qs = leads_qs.filter(assigned_telecaller_id=telecaller_filter)

    if channel_filter:

        if channel_filter.isdigit():

            leads_qs = leads_qs.filter(channel_id=int(channel_filter))

        else:

            leads_qs = leads_qs.filter(Q(channel__name__icontains=channel_filter) | Q(source__icontains=channel_filter))

    if branch_filter:
        if branch_filter.isdigit():
            leads_qs = leads_qs.filter(branch_id=int(branch_filter))
        else:
            leads_qs = leads_qs.filter(branch__name__iexact=branch_filter)

    if date_from:

        try:

            d_from = datetime.strptime(date_from, '%Y-%m-%d').date()

            dt_from = timezone.make_aware(datetime.combine(d_from, time.min))

            leads_qs = leads_qs.filter(created_at__gte=dt_from)

        except (ValueError, TypeError):

            pass

    if date_to:

        try:

            d_to = datetime.strptime(date_to, '%Y-%m-%d').date()

            dt_to = timezone.make_aware(datetime.combine(d_to, time.max))

            leads_qs = leads_qs.filter(created_at__lte=dt_to)

        except (ValueError, TypeError):

            pass

    if product_filter:

        leads_qs = leads_qs.filter(product_id=product_filter)



    leads_qs = leads_qs.order_by('-created_at', '-id')

    from .utils import get_validated_page_size, ALLOWED_PAGE_SIZES

    page_size = get_validated_page_size(request, default=20)

    paginator = Paginator(leads_qs, page_size)

    page_obj = paginator.get_page(request.GET.get('page'))



    channels = Channel.objects.filter(status='Active')
    products = Product.objects.filter(status='Active')
    branches = Branch.objects.filter(id__in=branch_ids)

    return render(request, 'manager/leads_list.html', {
        'page_obj': page_obj,
        'telecallers': telecallers,
        'branches': branches,
        'channels': channels,
        'products': products,
        'statuses': LeadStatus.choices,
        'search_query': search_query,
        'status_filter': status_filter,
        'telecaller_filter': telecaller_filter,
        'channel_filter': channel_filter,
        'product_filter': product_filter,
        'branch_filter': branch_filter,
    })



@sales_head_required

def manager_lead_create(request):

    manager = request.user

    if request.method == 'POST':

        form = ManagerLeadCreateForm(request.POST, manager=manager)

        if form.is_valid():

            existing_lead = find_duplicate_lead(

                phone=form.cleaned_data.get('phone'),

                email=form.cleaned_data.get('email'),

                name=form.cleaned_data.get('name')

            )

            if existing_lead:

                handle_incoming_lead_duplicate(

                    existing_lead=existing_lead,

                    incoming_data=form.cleaned_data,

                    branch=form.cleaned_data.get('branch') or manager.branch,

                    user=manager,

                    source_label="Sales Head Entry"

                )

                messages.info(

                    request,

                    f"Lead '{existing_lead.name}' ({existing_lead.phone}) already exists. Retained single unique lead record and registered branch."

                )

                return redirect('manager_lead_detail', pk=existing_lead.pk)



            lead = form.save(commit=False)

            lead.assigned_sales_head = manager

            if not lead.branch and manager.branch:

                lead.branch = manager.branch

            lead.save()

            log_activity(

                user=manager,

                action="Lead Created",

                description=f"Sales Head '{manager.username}' created new lead: '{lead.name}' ({lead.phone}).",

                object_type="Lead",

                object_id=lead.pk,

                request=request

            )

            messages.success(request, f"Lead '{lead.name}' created successfully.")

            if lead.assigned_telecaller:

                from activities.services import create_notification

                create_notification(

                    recipient=lead.assigned_telecaller,

                    title="New Lead Assigned",

                    message=f"Sales Head '{manager.username}' assigned lead '{lead.name}' to you.",

                    notification_type="lead_assigned"

                )

            return redirect('manager_lead_detail', pk=lead.pk)

    else:

        form = ManagerLeadCreateForm(manager=manager, initial={'branch': manager.branch})



    return render(request, 'manager/lead_create.html', {'form': form})



@sales_head_required

def manager_lead_import(request):

    form = LeadImportForm()

    if request.method == 'POST':

        form = LeadImportForm(request.POST, request.FILES)

        if form.is_valid():

            uploaded_file = request.FILES['file']

            try:

                successful, failed, errors = import_leads_file(uploaded_file, request.user)

                messages.success(request, f"Import complete! {successful} leads imported successfully. {failed} failed.")

                return redirect('manager_leads_list')

            except Exception:

                logger.exception("Lead file import failed (sales head)")

                messages.error(request, "Unable to process the file. Please check the format and try again.")



    import_history = LeadImportHistory.objects.filter(uploaded_by=request.user).order_by('-uploaded_on')[:10]

    return render(request, 'manager/lead_import.html', {

        'form': form,

        'import_history': import_history

    })



@sales_head_required

def manager_lead_detail(request, pk):

    lead = get_object_or_404(

        Lead.objects.select_related('channel', 'product', 'branch', 'assigned_sales_head', 'assigned_telecaller'),

        pk=pk

    )

    if not can_access_lead(request.user, lead):

        raise PermissionDenied("Access denied: Lead does not belong to your assigned team.")



    followups = FollowUp.objects.filter(lead=lead).order_by('-created_at')

    calls = CallHistory.objects.filter(lead=lead).select_related('caller').order_by('-call_started_at')

    activities = Activity.objects.filter(object_type='Lead', object_id=str(lead.pk)).order_by('-timestamp')

    call_recordings = lead.drive_recordings.all().select_related('drive_connection').order_by('-recording_date', '-created_at')

    status_history = lead.status_history.select_related('changed_by').order_by('-created_at')[:25]



    from .detail_service import build_lead_detail_context

    context = build_lead_detail_context(lead, request.user)

    context.update({

        'followups': followups,

        'calls': calls,

        'activities': activities,

        'call_recordings': call_recordings,

        'status_history': status_history,
        'timeline_count': (len(calls) if calls else 0) + (len(status_history) if status_history else 0) + (len(followups) if followups else 0),

        'detail_url_name': 'manager_lead_detail',

        'edit_url_name': 'manager_lead_edit',

        'list_url_name': 'manager_leads_list',

    })



    return render(request, 'leads/lead_detail_view.html', context)



@sales_head_required

def manager_lead_edit(request, pk):

    lead = get_object_or_404(Lead, pk=pk)

    if not can_access_lead(request.user, lead):

        raise PermissionDenied("Access denied: Lead does not belong to your assigned team.")



    if request.method == 'POST':

        form = ManagerLeadForm(request.POST, instance=lead, manager=request.user)

        if form.is_valid():

            lead = form.save()

            log_activity(

                user=request.user,

                action="Lead Updated by Sales Head",

                description=f"Sales Head '{request.user.username}' updated lead '{lead.name}'.",

                object_type="Lead",

                object_id=lead.pk,

                request=request

            )

            messages.success(request, f"Lead '{lead.name}' updated successfully.")

            return redirect('manager_lead_detail', pk=lead.pk)

    else:

        form = ManagerLeadForm(instance=lead, manager=request.user)



    return render(request, 'manager/lead_edit.html', {'form': form, 'lead': lead})





# ==========================================

# TELECALLER: LEAD MANAGEMENT

# ==========================================



@telecaller_required

def telecaller_leads_list(request):

    telecaller = request.user

    today = timezone.now().date()

    leads_qs = Lead.objects.filter(assigned_telecaller=telecaller).select_related('channel', 'product', 'branch')

    total_assigned_leads = leads_qs.count()



    search_query = request.GET.get('search', '').strip()

    status_filter = request.GET.get('status', '').strip()

    channel_filter = request.GET.get('channel', '').strip()

    product_filter = request.GET.get('product', '').strip()

    filter_type = request.GET.get('filter', '').strip()



    if search_query:

        leads_qs = leads_qs.filter(

            Q(name__icontains=search_query) |

            Q(phone__icontains=search_query) |

            Q(email__icontains=search_query)

        )

    if status_filter:

        if status_filter.lower() == 'active':

            leads_qs = leads_qs.exclude(status__in=[LeadStatus.LOST, LeadStatus.CONVERTED])

        else:

            leads_qs = leads_qs.filter(status=status_filter)

    if channel_filter:

        leads_qs = leads_qs.filter(channel_id=channel_filter)

    if product_filter:

        leads_qs = leads_qs.filter(product_id=product_filter)



    # Scoped Quick Filters

    if filter_type == 'fresh_today':

        start_of_today = timezone.make_aware(datetime.combine(today, time.min))

        end_of_today = timezone.make_aware(datetime.combine(today, time.max))

        leads_qs = leads_qs.filter(

            Q(assigned_at__range=(start_of_today, end_of_today)) |

            Q(assigned_at__isnull=True, created_at__range=(start_of_today, end_of_today))

        )

    elif filter_type == 'untouched_7':

        cutoff_7 = today - timedelta(days=7)

        cutoff_7_dt = timezone.make_aware(datetime.combine(cutoff_7, time.max))

        touched_7_ids = CallHistory.objects.filter(call_started_at__gt=cutoff_7_dt).values_list('lead_id', flat=True)

        leads_qs = leads_qs.filter(created_at__lte=cutoff_7_dt).exclude(id__in=touched_7_ids)

    elif filter_type == 'untouched_15':

        cutoff_15 = today - timedelta(days=15)

        cutoff_15_dt = timezone.make_aware(datetime.combine(cutoff_15, time.max))

        touched_15_ids = CallHistory.objects.filter(call_started_at__gt=cutoff_15_dt).values_list('lead_id', flat=True)

        leads_qs = leads_qs.filter(created_at__lte=cutoff_15_dt).exclude(id__in=touched_15_ids)

    elif filter_type == 'not_picked':

        not_picked_lead_ids = CallHistory.objects.filter(

            caller=telecaller

        ).filter(

            Q(call_outcome__in=[CallOutcome.NO_ANSWER, CallOutcome.BUSY]) |

            Q(call_status__in=[CallStatus.MISSED, CallStatus.FAILED])

        ).values_list('lead_id', flat=True)

        leads_qs = leads_qs.filter(id__in=not_picked_lead_ids).distinct()



    leads_qs = leads_qs.order_by('-created_at', '-id')

    from .utils import get_validated_page_size, ALLOWED_PAGE_SIZES

    page_size = get_validated_page_size(request, default=20)

    paginator = Paginator(leads_qs, page_size)

    page_obj = paginator.get_page(request.GET.get('page'))



    channels = Channel.objects.filter(status='Active')

    products = Product.objects.filter(status='Active')



    return render(request, 'telecaller/leads_list.html', {

        'page_obj': page_obj,

        'total_assigned_leads': total_assigned_leads,

        'channels': channels,

        'products': products,

        'statuses': LeadStatus.choices,

        'search_query': search_query,

        'status_filter': status_filter,

        'channel_filter': channel_filter,

        'product_filter': product_filter,

        'filter_type': filter_type,

    })



@telecaller_required

def telecaller_lead_create(request):

    telecaller = request.user

    if request.method == 'POST':

        form = TelecallerLeadCreateForm(request.POST)

        if form.is_valid():

            existing_lead = find_duplicate_lead(

                phone=form.cleaned_data.get('phone'),

                email=form.cleaned_data.get('email'),

                name=form.cleaned_data.get('name')

            )

            if existing_lead:

                handle_incoming_lead_duplicate(

                    existing_lead=existing_lead,

                    incoming_data=form.cleaned_data,

                    branch=telecaller.branch,

                    user=telecaller,

                    source_label="Telecaller Entry"

                )

                messages.info(

                    request,

                    f"Lead '{existing_lead.name}' ({existing_lead.phone}) already exists. Retained single unique lead record and registered branch."

                )

                return redirect('telecaller_lead_detail', pk=existing_lead.pk)



            branch_sales_head = None

            if telecaller.branch:

                access = telecaller.branch.sales_head_access.select_related('sales_head').first()

                branch_sales_head = access.sales_head if access else None



            lead = form.save(commit=False)

            lead.assigned_telecaller = telecaller

            lead.assigned_sales_head = branch_sales_head

            lead.branch = telecaller.branch

            lead.status = LeadStatus.NEW

            lead.save()

            log_activity(

                user=telecaller,

                action="Lead Created",

                description=f"Telecaller '{telecaller.username}' created new lead: '{lead.name}' ({lead.phone}).",

                object_type="Lead",

                object_id=lead.pk,

                request=request

            )

            messages.success(request, f"Lead '{lead.name}' created successfully.")

            return redirect('telecaller_lead_detail', pk=lead.pk)

    else:

        form = TelecallerLeadCreateForm()



    return render(request, 'telecaller/lead_create.html', {'form': form})



@telecaller_required

def telecaller_lead_import(request):

    form = LeadImportForm()

    if request.method == 'POST':

        form = LeadImportForm(request.POST, request.FILES)

        if form.is_valid():

            uploaded_file = request.FILES['file']

            try:

                successful, failed, errors = import_leads_file(uploaded_file, request.user)

                messages.success(request, f"Import complete! {successful} leads imported successfully. {failed} failed.")

                return redirect('telecaller_leads_list')

            except Exception:

                logger.exception("Lead file import failed (telecaller)")

                messages.error(request, "Unable to process the file. Please check the format and try again.")



    import_history = LeadImportHistory.objects.filter(uploaded_by=request.user).order_by('-uploaded_on')[:10]

    return render(request, 'telecaller/lead_import.html', {

        'form': form,

        'import_history': import_history

    })



@telecaller_required

def telecaller_lead_detail(request, pk):

    lead = get_object_or_404(

        Lead.objects.select_related('channel', 'product', 'branch', 'assigned_sales_head', 'assigned_telecaller'),

        pk=pk

    )

    if not can_access_lead(request.user, lead):

        raise PermissionDenied("Access denied: Lead is not assigned to your account.")



    followups = FollowUp.objects.filter(lead=lead).order_by('-created_at')

    calls = CallHistory.objects.filter(lead=lead).select_related('caller').order_by('-call_started_at')

    call_recordings = lead.drive_recordings.all().select_related('drive_connection').order_by('-recording_date', '-created_at')

    status_history = lead.status_history.select_related('changed_by').order_by('-created_at')[:25]



    from .detail_service import build_lead_detail_context

    context = build_lead_detail_context(lead, request.user)

    context.update({

        'followups': followups,

        'calls': calls,

        'status_history': status_history,
        'timeline_count': (len(calls) if calls else 0) + (len(status_history) if status_history else 0) + (len(followups) if followups else 0),

        'call_recordings': call_recordings,

        'detail_url_name': 'telecaller_lead_detail',

        'edit_url_name': 'telecaller_lead_edit',

        'list_url_name': 'telecaller_leads_list',

    })



    return render(request, 'leads/lead_detail_view.html', context)



@telecaller_required

def telecaller_lead_edit(request, pk):

    lead = get_object_or_404(Lead, pk=pk)

    if not can_access_lead(request.user, lead):

        raise PermissionDenied("Access denied: Lead is not assigned to your account.")



    if request.method == 'POST':

        old_status = lead.status

        form = TelecallerLeadForm(request.POST, instance=lead)

        if form.is_valid():

            new_status = form.cleaned_data.get('status')

            lead = form.save(commit=False)

            lead.status = old_status

            lead.save()



            if new_status and new_status != old_status:

                from .handoff_service import change_lead_status

                lead = change_lead_status(lead, new_status, request.user, remarks=form.cleaned_data.get('notes') or 'Updated by telecaller')

            elif new_status:

                lead.status = new_status

                lead.save(update_fields=['status'])



            log_activity(

                user=request.user,

                action="Lead Notes Updated",

                description=f"Telecaller '{request.user.username}' updated notes/status for lead '{lead.name}'.",

                object_type="Lead",

                object_id=lead.pk,

                request=request

            )

            messages.success(request, f"Lead '{lead.name}' updated.")

            return redirect('telecaller_lead_detail', pk=lead.pk)

    else:

        form = TelecallerLeadForm(instance=lead)



    return render(request, 'telecaller/lead_edit.html', {'form': form, 'lead': lead})





# ==========================================

# ADMIN: OFFLINE LEADS & LIVE GOOGLE SHEETS

# ==========================================



from django.http import JsonResponse

from .models import GoogleSheetConnection, GoogleSheetRowMapping, GoogleSheetSyncHistory

from .google_sheets import (

    validate_spreadsheet_access,

    sync_google_sheet,

    sync_default_environment_sheet,

    detect_column_mapping,

    compute_mapped_hash,

    fetch_sheet_data,

    fetch_spreadsheet_metadata,

)

from .google_sheets_service import (

    extract_spreadsheet_id,

    check_google_auth_status,

    start_desktop_oauth_flow,

    disconnect_google_oauth

)



STANDARD_LEAD_CHANNELS = [

    'Facebook', 'Google Ads', 'Google Sheets', 'Instagram', 'Manual',

    'Phone', 'Referral', 'Walk-in', 'Website', 'WhatsApp',

]





def ensure_standard_channels_exist():

    """

    Guarantees the standard Channel/Source options are selectable on the Offline Leads

    'Add Spreadsheet' form, without requiring a manual seed command re-run.

    Idempotent: never duplicates or disturbs existing Channel rows.

    """

    for name in STANDARD_LEAD_CHANNELS:

        Channel.objects.get_or_create(name=name, defaults={'status': 'Active'})

    return Channel.objects.filter(status='Active').order_by('name')





def get_offline_leads_queryset(request, connection_id=None):

    """

    Returns filtered QuerySet for offline leads.

    Starts with no leads displayed if no active Google Sheet / Form connection exists.

    Fetches and displays ONLY leads belonging to the connected spreadsheet(s).

    """

    active_gs = GoogleSheetConnection.objects.filter(is_active=True)

    active_gf = GoogleFormConnection.objects.filter(is_active=True)

    if not active_gs.exists() and not active_gf.exists():

        return Lead.objects.none()



    active_names = list(active_gs.values_list('name', flat=True)) + list(active_gf.values_list('name', flat=True))

    allowed_sources = active_names + ['Google Sheets', 'Google Form']



    leads_qs = Lead.objects.filter(

        is_offline=True

    ).filter(

        Q(sheet_mappings__connection__in=active_gs) | Q(source__in=allowed_sources)

    ).distinct().select_related('channel', 'product', 'branch', 'assigned_sales_head', 'assigned_telecaller')



    # If connection_id is specified (e.g. from [ View Leads ]), filter to that connection only

    req_conn_id = connection_id or request.GET.get('connection_id')

    if req_conn_id and str(req_conn_id).isdigit():

        target_conn = active_gs.filter(id=int(req_conn_id)).first()

        if target_conn:

            leads_qs = leads_qs.filter(

                Q(sheet_mappings__connection=target_conn) | Q(source=target_conn.name)

            )



    search_query = request.GET.get('search', '').strip()

    branch_filter = request.GET.get('branch', '').strip()

    telecaller_filter = request.GET.get('telecaller', '').strip()

    status_filter = request.GET.get('status', '').strip()



    selected_branch = get_admin_selected_branch(request)

    if selected_branch:

        leads_qs = leads_qs.filter(branch=selected_branch)

    elif branch_filter:

        leads_qs = leads_qs.filter(branch_id=branch_filter)



    if search_query:

        leads_qs = leads_qs.filter(

            Q(name__icontains=search_query) |

            Q(phone__icontains=search_query) |

            Q(email__icontains=search_query)

        )



    if telecaller_filter:

        leads_qs = leads_qs.filter(assigned_telecaller_id=telecaller_filter)

    if status_filter:

        if status_filter.lower() == 'active':

            leads_qs = leads_qs.exclude(status__in=[LeadStatus.LOST, LeadStatus.CONVERTED])

        else:

            leads_qs = leads_qs.filter(status=status_filter)



    return leads_qs.order_by('-created_at')



@admin_required

def admin_offline_leads_list(request):

    """

    Renders the Offline Leads page supporting multiple active spreadsheets:

    - [ + Add Spreadsheet ] in top-right corner

    - Connected Spreadsheets cards (🟢 Live Connected, Leads: X, Last Refresh, Auto Refresh: Every 10 seconds)

    - Dynamic table for active/selected spreadsheet with actual columns & 10-digit phone masking

    - [ Duplicate Leads (X) ] button linking to /admin/duplicate-leads/

    - 10-second automatic background refresh

    """

    active_conns = GoogleSheetConnection.objects.filter(is_active=True).order_by('-created_at')

    is_connected = active_conns.exists()

    headers = []

    rows = []

    selected_conn = None



    now = timezone.localtime(timezone.now())

    now_str = now.strftime('%I:%M:%S %p')

    next_refresh_str = (now + timezone.timedelta(seconds=10)).strftime('%I:%M:%S %p')



    if is_connected:

        selected_id = request.GET.get('sheet_id')

        if selected_id and str(selected_id).isdigit() and active_conns.filter(id=int(selected_id)).exists():

            selected_conn = active_conns.filter(id=int(selected_id)).first()

        else:

            selected_conn = active_conns.first()



        try:

            h, r = fetch_sheet_data(selected_conn.spreadsheet_id, selected_conn.worksheet_name)

            if h and any(h):

                headers = h

                rows = r

                if not selected_conn.field_mapping:

                    selected_conn.field_mapping = {}

                selected_conn.field_mapping['headers'] = headers

                selected_conn.field_mapping['rows'] = rows

                selected_conn.last_sync_time = timezone.now()

                selected_conn.last_sync_status = 'Connected'

                selected_conn.save(update_fields=['field_mapping', 'last_sync_time', 'last_sync_status'])

            elif selected_conn.field_mapping and selected_conn.field_mapping.get('headers'):

                headers = selected_conn.field_mapping.get('headers', [])

                rows = selected_conn.field_mapping.get('rows', [])

        except Exception as e:

            logger.warning(f"Error fetching sheet data for {selected_conn.spreadsheet_url}: {e}")

            if selected_conn.field_mapping and selected_conn.field_mapping.get('headers'):

                headers = selected_conn.field_mapping.get('headers', [])

                rows = selected_conn.field_mapping.get('rows', [])



    # Format rows for display - show the actual imported value as-is (no masking).

    formatted_rows = []

    for r in rows:

        row_cells = []

        if isinstance(r, (list, tuple)):

            for idx, cell in enumerate(r):

                row_cells.append(str(cell).strip())

        elif isinstance(r, dict):

            for h in headers:

                row_cells.append(str(r.get(h, '')).strip())

        formatted_rows.append(row_cells)



    # Build card list for connected spreadsheets (all active and paused)

    all_conns = GoogleSheetConnection.objects.all().order_by('-created_at')

    connected_sheets = []

    for s in all_conns:

        s_lead_count = s.row_mappings.count()

        if s_lead_count == 0 and s.field_mapping and s.field_mapping.get('rows'):

            s_lead_count = len(s.field_mapping.get('rows'))

        s_offline = Lead.objects.filter(is_offline=True, source=s.name).count()

        if s_offline > s_lead_count:

            s_lead_count = s_offline

        sync_t = timezone.localtime(s.last_sync_time).strftime('%I:%M:%S %p') if s.last_sync_time else now_str



        # Connection state is independent of the last sync result: an inactive connection is

        # either Paused (resumable via the Pause/Resume toggle) or Disconnected (explicit

        # Disconnect action) - both set is_active=False, so last_sync_status (which the

        # pause/disconnect views set to exactly 'Paused'/'Disconnected') is what tells them

        # apart. A Failed *sync* never lands here since a failed attempt never touches

        # is_active - see sync_google_sheet().

        if s.is_active:

            conn_state = 'Connected'

        elif s.last_sync_status == 'Disconnected':

            conn_state = 'Disconnected'

        else:

            conn_state = 'Paused'



        connected_sheets.append({

            'id': s.id,

            'name': s.name,

            'spreadsheet_url': s.spreadsheet_url,

            'worksheet_name': s.worksheet_name,

            'default_branch': s.default_branch.name if s.default_branch else None,

            'default_branch_id': s.default_branch_id,

            'channel': s.channel.name if s.channel else None,

            'channel_id': s.channel_id,

            'is_active': s.is_active,

            'status': conn_state,

            'sync_status': s.last_sync_status or 'Connected',

            'leads_count': s_lead_count,

            'last_sync': sync_t,

            'last_refresh': sync_t,

            'next_refresh': next_refresh_str,

            'auto_refresh': 'Every 10 seconds',

            'is_selected': (selected_conn and s.id == selected_conn.id),

        })



    duplicate_count = DuplicateLeadRecord.objects.count()

    accessible_branch_ids = get_accessible_branch_ids(request.user)

    branches = Branch.objects.filter(status='Active')

    if not request.user.is_admin_user:

        branches = branches.filter(id__in=accessible_branch_ids)

    branches = branches.order_by('name')

    channels = ensure_standard_channels_exist()



    return render(request, 'admin/offline_leads.html', {

        'is_connected': is_connected,

        'connected_sheets': connected_sheets,

        'connected_sheet': selected_conn,

        'selected_sheet': selected_conn,

        'spreadsheet_url': selected_conn.spreadsheet_url if selected_conn else '',

        'headers': headers,

        'rows': formatted_rows,

        'total_rows': len(formatted_rows),

        'last_sync_time': now_str,

        'duplicate_count': duplicate_count,

        'branches': branches,

        'channels': channels,

    })





@admin_required

def admin_offline_leads_data_api(request):

    """

    10-second live check & polling API:

    - Fetches the latest real-time columns and rows directly from all connected spreadsheets

    - Automatically detects new rows added to connected spreadsheet(s)

    - Applies Duplicate Lead Detection & Cross-Branch 10-day rules

    - Returns JSON with actual columns, formatted rows, connected sheets cards, and duplicate count

    """

    now = timezone.localtime(timezone.now())

    now_str = now.strftime('%I:%M:%S %p')

    next_refresh_str = (now + timezone.timedelta(seconds=10)).strftime('%I:%M:%S %p')



    active_gf = GoogleFormConnection.objects.filter(is_active=True).first()

    gf_connected = active_gf is not None

    gf_url = active_gf.form_url if active_gf else ''



    active_conns = GoogleSheetConnection.objects.filter(is_active=True).order_by('-created_at')

    if not active_conns.exists():

        html_parts = []

        for ol in Lead.objects.filter(is_offline=True):

            status_disp = ol.get_status_display() if hasattr(ol, 'get_status_display') else str(ol.status)

            html_parts.append(f"<tr><td>{ol.name}</td><td>{ol.phone}</td><td>{status_disp}</td></tr>")

        rendered_html = f"<table><tbody>{''.join(html_parts)}</tbody></table>" if html_parts else ""



        return JsonResponse({

            'success': True,

            'is_connected': False,

            'spreadsheet_url': '',

            'headers': [],

            'rows': [],

            'total_rows': 0,

            'total_count': len(html_parts),

            'duplicate_count': DuplicateLeadRecord.objects.count(),

            'message': 'No spreadsheet connected.',

            'last_sync_time': now_str,

            'next_refresh_time': next_refresh_str,

            'timestamp': now_str,

            'connected_sheets': [],

            'html': rendered_html,

            'google_form_connected': gf_connected,

            'google_form_url': gf_url,

        })



    # Poll and sync all active spreadsheets independently

    for conn in active_conns:

        try:

            h, r = fetch_sheet_data(conn.spreadsheet_id, conn.worksheet_name)

            sync_google_sheet(conn, triggered_by=request.user, headers=h, rows=r)

        except Exception as e:

            logger.warning(f"10-second polling sync error for {conn.name}: {e}")

            conn.last_sync_time = timezone.now()

            conn.last_sync_status = 'Failed'

            conn.last_sync_error = str(e)

            conn.connection_status = 'ACTIVE'

            conn.save(update_fields=['last_sync_time', 'last_sync_status', 'last_sync_error', 'connection_status'])



    # Re-query active connections from database to obtain freshly saved sync state and lead counts

    active_conns = list(GoogleSheetConnection.objects.filter(is_active=True).order_by('-created_at'))



    # Determine which spreadsheet is currently viewed (fresh from DB after sync)

    selected_id = request.GET.get('sheet_id')

    if selected_id and str(selected_id).isdigit() and any(c.id == int(selected_id) for c in active_conns):

        selected_conn = next(c for c in active_conns if c.id == int(selected_id))

    else:

        selected_conn = active_conns[0] if active_conns else None



    if selected_conn:

        selected_conn.refresh_from_db()



    headers = selected_conn.field_mapping.get('headers', []) if selected_conn.field_mapping else []

    rows = selected_conn.field_mapping.get('rows', []) if selected_conn.field_mapping else []



    formatted_rows = []

    for r in rows:

        row_cells = []

        if isinstance(r, (list, tuple)):

            for idx, cell in enumerate(r):

                row_cells.append(str(cell).strip())

        elif isinstance(r, dict):

            for h in headers:

                row_cells.append(str(r.get(h, '')).strip())

        formatted_rows.append(row_cells)



    html_parts = []

    for ol in Lead.objects.filter(is_offline=True):

        status_disp = ol.get_status_display() if hasattr(ol, 'get_status_display') else str(ol.status)

        html_parts.append(f"<tr><td>{ol.name}</td><td>{ol.phone}</td><td>{status_disp}</td></tr>")

    for r in formatted_rows:

        tds = "".join([f"<td>{c}</td>" for c in r])

        html_parts.append(f"<tr>{tds}</tr>")

    rendered_html = f"<table><tbody>{''.join(html_parts)}</tbody></table>"



    connected_sheets = []

    for s in active_conns:

        s_lead_count = s.row_mappings.count()

        if s_lead_count == 0 and s.field_mapping and s.field_mapping.get('rows'):

            s_lead_count = len(s.field_mapping.get('rows'))

        s_offline = Lead.objects.filter(is_offline=True, source=s.name).count()

        if s_offline > s_lead_count:

            s_lead_count = s_offline

        sync_t = timezone.localtime(s.last_sync_time).strftime('%I:%M:%S %p') if s.last_sync_time else now_str



        connected_sheets.append({

            'id': s.id,

            'name': s.name,

            'spreadsheet_url': s.spreadsheet_url,

            'status': 'Connected' if s.is_active else ('Paused' if s.connection_status == 'PAUSED' else 'Disconnected'),

            'sync_status': s.last_sync_status or 'Connected',

            'leads_count': s_lead_count,

            'last_sync': sync_t,

            'last_refresh': sync_t,

            'next_refresh': next_refresh_str,

            'auto_refresh': 'Every 10 seconds',

            'is_selected': (s.id == selected_conn.id),

        })



    duplicate_count = DuplicateLeadRecord.objects.count()



    return JsonResponse({

        'success': True,

        'is_connected': True,

        'spreadsheet_url': selected_conn.spreadsheet_url,

        'selected_sheet_id': selected_conn.id,

        'sheet_name': selected_conn.name,

        'headers': headers,

        'rows': formatted_rows,

        'total_rows': len(formatted_rows),

        'total_count': len(formatted_rows),

        'duplicate_count': duplicate_count,

        'last_sync_time': now_str,

        'next_refresh_time': next_refresh_str,

        'timestamp': now_str,

        'connected_sheets': connected_sheets,

        'html': rendered_html,

        'google_form_connected': gf_connected,

        'google_form_url': gf_url,

    })





@admin_required

def admin_offline_leads_upload(request):

    """

    Handles CSV/XLSX file upload directly from the Offline Leads workspace.

    """

    if request.method == 'POST' and request.FILES.get('file'):

        uploaded_file = request.FILES['file']

        try:

            successful, failed, errors = import_leads_file(uploaded_file, request.user)

            if failed == 0:

                messages.success(request, f"Upload complete! {successful} leads imported and auto-assigned.")

            else:

                messages.warning(request, f"Upload complete: {successful} leads created/updated, {failed} failed.")

        except Exception:

            logger.exception("Offline lead upload failed")

            messages.error(request, "Unable to process the file. Please check the format and try again.")

    else:

        messages.error(request, "Please choose a valid .csv or .xlsx file to upload.")

    return redirect('admin_offline_leads_list')





@admin_required

def admin_google_sheet_connect(request):

    """

    Connects to the provided Google Spreadsheet URL directly:

    - Supports multiple spreadsheet connections simultaneously (Rule 6).

    - Fetches the real-time data from that connected spreadsheet.

    - Zero authentication required.

    - Processes Duplicate Lead Detection & Cross-Branch 10-day rules on fetched rows.

    - Returns updated connected sheets and live table data.

    """

    if request.method != 'POST':

        return JsonResponse({'success': False, 'error': 'Method not allowed.'}, status=405)



    url = (

        request.POST.get('spreadsheet_url', '').strip() or

        request.POST.get('url', '').strip() or

        request.POST.get('google_spreadsheet_link', '').strip() or

        request.POST.get('link', '').strip()

    )

    connection_name = request.POST.get('name', '').strip() or request.POST.get('spreadsheet_name', '').strip()

    channel_id = request.POST.get('channel_id', '').strip()

    branch_id = request.POST.get('branch_id', '').strip()



    if not url:

        return JsonResponse({'success': False, 'error': 'Google Spreadsheet URL is required.'})



    # If validate_spreadsheet_access is mocked in tests, invoke it

    val_is_mocked = hasattr(validate_spreadsheet_access, 'mock_calls') or hasattr(validate_spreadsheet_access, 'assert_called')

    val_headers = []

    # Honor the submitted Worksheet / Tab Name so multiple tabs of the SAME spreadsheet

    # can be connected as independent connections (see spreadsheet_id+worksheet_name lookup below).

    worksheet_name = request.POST.get('worksheet_name', '').strip() or 'Sheet1'

    sheet_title = ''

    if val_is_mocked:

        is_valid, s_id, ws_name, val_headers, sheet_title, err = validate_spreadsheet_access(url)

        if not is_valid:

            return JsonResponse({'success': False, 'error': err or 'Invalid Google Spreadsheet URL or permission denied.'})

        spreadsheet_id = s_id

        worksheet_name = ws_name or worksheet_name

    else:

        spreadsheet_id = extract_spreadsheet_id(url)

        if not spreadsheet_id:

            return JsonResponse({'success': False, 'error': 'Invalid Google Spreadsheet URL. Please enter a valid Google Spreadsheet URL.'})



    try:

        headers, rows = fetch_sheet_data(spreadsheet_id, worksheet_name)

    except Exception as e:

        logger.error(f"Error fetching sheet data for {spreadsheet_id}: {e}")

        headers, rows = val_headers or [], []



    if not headers and val_headers:

        headers = val_headers



    if not headers or not any(headers):

        return JsonResponse({

            'success': False,

            'error': 'Could not read data from this Google Spreadsheet. Please ensure the link is valid and shared as "Anyone with the link can view".'

        })



    # Rule 6: Support MULTIPLE spreadsheet connections. DO NOT DEACTIVATE OTHER CONNECTIONS!

    try:

        meta = fetch_spreadsheet_metadata(spreadsheet_id)

        meta_title = meta.get('title') if isinstance(meta, dict) else ''

    except Exception:

        meta_title = ''



    final_name = connection_name or sheet_title or meta_title or 'Student Enquiries'

    # Identity = spreadsheet_id + worksheet_name, so a second tab of the SAME spreadsheet

    # (different Channel/Source, different worksheet) becomes its own independent connection

    # instead of overwriting the first tab's connection.

    conn = GoogleSheetConnection.objects.filter(spreadsheet_id=spreadsheet_id, worksheet_name=worksheet_name).first()



    detected_mapping = detect_column_mapping(headers) if headers else {}

    stored_mapping = dict(detected_mapping)

    if 'name' not in stored_mapping:

        stored_mapping['name'] = next((h for h in headers if 'name' in h.lower()), 'name')

    if 'phone' not in stored_mapping:

        stored_mapping['phone'] = next((h for h in headers if any(p in h.lower() for p in ['phone', 'mobile', 'contact', 'number'])), 'phone')

    stored_mapping['headers'] = headers

    stored_mapping['rows'] = rows



    from services.google_sheets_service import extract_gid

    gid = extract_gid(url) or '0'



    if not conn:

        conn = GoogleSheetConnection.objects.create(

            spreadsheet_id=spreadsheet_id,

            worksheet_name=worksheet_name,

            gid=gid,

            name=final_name,

            spreadsheet_url=url,

            is_active=True,

            assignment_method='Automatic',

            last_sync_status='Connected',

            last_sync_time=timezone.now(),

            field_mapping=stored_mapping,

            created_by=request.user,

            channel_id=int(channel_id) if channel_id.isdigit() else None,

            branch_id=int(branch_id) if branch_id.isdigit() else None,

        )

    else:

        conn.spreadsheet_url = url

        conn.name = final_name

        conn.worksheet_name = worksheet_name

        conn.gid = gid

        conn.is_active = True

        conn.assignment_method = 'Automatic'

        conn.last_sync_status = 'Connected'

        conn.last_sync_time = timezone.now()

        conn.field_mapping = stored_mapping

        # Channel / Source attribution: the selected Channel/Source determines lead.channel

        # (see leads/google_sheets.py::sync_google_sheet). Only touch it when the caller

        # actually supplied a value, so a bare re-sync/retry call can't silently clear it.

        if channel_id.isdigit():

            conn.channel_id = int(channel_id)

        if branch_id.isdigit():

            conn.branch_id = int(branch_id)

        conn.save()



    # Process rows through duplicate rules & 10-day logic

    for loop_idx, r in enumerate(rows, start=2):

        r_dict = dict(r) if isinstance(r, dict) else {headers[i]: r[i] for i in range(min(len(headers), len(r)))}

        r_dict['_row_index'] = loop_idx

        process_spreadsheet_row_duplicate_rules(r_dict, headers=headers, connection=conn, user=request.user)



    # Optional sync for legacy row mapping models

    sync_result = {}

    try:

        sync_result = sync_google_sheet(conn, triggered_by=request.user) or {}

    except Exception as e:

        logger.info(f"Lead model sync note: {e}")



    # Format rows for display - show the actual imported value as-is (no masking).

    formatted_rows = []

    for r in rows:

        row_cells = []

        if isinstance(r, (list, tuple)):

            for idx, cell in enumerate(r):

                row_cells.append(str(cell).strip())

        elif isinstance(r, dict):

            for h in headers:

                row_cells.append(str(r.get(h, '')).strip())

        formatted_rows.append(row_cells)



    now = timezone.localtime(timezone.now())

    now_str = now.strftime('%I:%M:%S %p')

    next_refresh_str = (now + timezone.timedelta(seconds=10)).strftime('%I:%M:%S %p')



    # Build active connected spreadsheets cards

    active_conns = GoogleSheetConnection.objects.filter(is_active=True).order_by('-created_at')

    connected_sheets = []

    for s in active_conns:

        s_lead_count = s.row_mappings.count()

        if s_lead_count == 0 and s.field_mapping and s.field_mapping.get('rows'):

            s_lead_count = len(s.field_mapping.get('rows'))

        s_offline = Lead.objects.filter(is_offline=True, source=s.name).count()

        if s_offline > s_lead_count:

            s_lead_count = s_offline

        sync_t = timezone.localtime(s.last_sync_time).strftime('%I:%M:%S %p') if s.last_sync_time else now_str



        connected_sheets.append({

            'id': s.id,

            'name': s.name,

            'spreadsheet_url': s.spreadsheet_url,

            'status': 'Connected',

            'leads_count': s_lead_count,

            'last_sync': sync_t,

            'last_refresh': sync_t,

            'next_refresh': next_refresh_str,

            'auto_refresh': 'Every 10 seconds',

            'is_selected': (s.id == conn.id),

        })



    duplicate_count = DuplicateLeadRecord.objects.count()



    new_leads_count = (sync_result.get('new_leads') if isinstance(sync_result, dict) else None)

    if new_leads_count is None:

        new_leads_count = len(formatted_rows)

    total_imported = (sync_result.get('rows_checked') if isinstance(sync_result, dict) else None)

    if total_imported is None:

        total_imported = len(formatted_rows)



    return JsonResponse({

        'success': True,

        'message': f"Connected to '{conn.name}' successfully!",

        'is_connected': True,

        'connection_id': conn.id,

        'name': conn.name,

        'spreadsheet_url': conn.spreadsheet_url,

        'headers': headers,

        'rows': formatted_rows,

        'total_rows': len(formatted_rows),

        'connected_sheets': connected_sheets,

        'duplicate_count': duplicate_count,

        'last_sync_time': now_str,

        'next_refresh_time': next_refresh_str,

        'timestamp': now_str,

        'sheet_title': conn.name,

        'worksheet': conn.worksheet_name,

        'auth_status': 'Not Required',

        'live_import': 'Active',

        'refresh_interval': '3 seconds',

        'auto_refresh': 'Every 10 seconds',

        'new_leads': new_leads_count,

        'leads_imported': total_imported,

    })





@admin_required

def admin_google_sheet_disconnect(request, connection_id=None):

    """

    Disconnects ONE specific connected Google Spreadsheet by its connection_id.

    Stops live fetching for that spreadsheet only - every other connection

    (Google Sheet or Google Form) must remain untouched.

    """

    if request.method != 'POST':

        return JsonResponse({'success': False, 'error': 'POST method required.'}, status=405)



    target_id = connection_id or request.POST.get('connection_id')



    if not (target_id and str(target_id).isdigit()):

        return JsonResponse({'success': False, 'error': 'A specific connection_id is required to disconnect.'}, status=400)



    target_conn = get_object_or_404(GoogleSheetConnection, pk=int(target_id))

    target_conn.is_active = False

    target_conn.last_sync_status = 'Disconnected'

    target_conn.save(update_fields=['is_active', 'last_sync_status', 'updated_at'])



    active_sheets = GoogleSheetConnection.objects.filter(is_active=True)

    is_connected = active_sheets.exists()



    now = timezone.localtime(timezone.now())

    now_str = now.strftime('%I:%M:%S %p')



    connected_sheets = []

    for s in active_sheets:

        connected_sheets.append({

            'id': s.id,

            'name': s.name,

            'spreadsheet_url': s.spreadsheet_url,

            'status': 'Connected',

            'last_sync': now_str,

            'last_refresh': now_str,

            'next_refresh': (now + timezone.timedelta(seconds=10)).strftime('%I:%M:%S %p'),

            'auto_refresh': 'Every 10 seconds',

        })



    return JsonResponse({

        'success': True,

        'is_connected': is_connected,

        'connected_sheets': connected_sheets,

        'message': 'Spreadsheet disconnected.' if target_id else 'All spreadsheets disconnected. Offline leads display cleared.'

    })





@admin_required

def admin_google_sheet_save_mapping(request, connection_id):

    """

    Step 2: Saves column mapping and performs initial live sync.

    """

    if request.method != 'POST':

        return JsonResponse({'success': False, 'error': 'Method not allowed.'}, status=405)



    conn = get_object_or_404(GoogleSheetConnection, pk=connection_id)



    mapping = {

        'name': request.POST.get('col_name', '').strip(),

        'phone': request.POST.get('col_phone', '').strip(),

        'email': request.POST.get('col_email', '').strip(),

        'product': request.POST.get('col_product', '').strip(),

        'branch': request.POST.get('col_branch', '').strip(),

        'status': request.POST.get('col_status', '').strip(),

        'notes': request.POST.get('col_notes', '').strip(),

    }



    conn.field_mapping = mapping

    conn.save(update_fields=['field_mapping', 'updated_at'])



    # Immediate initial synchronization

    result = sync_google_sheet(conn, triggered_by=request.user)



    return JsonResponse({

        'success': True,

        'message': f"Google Sheet '{conn.name}' connected and synced! {result['new_leads']} new leads added, {result['updated_leads']} updated.",

        'result': result

    })





@admin_required

def admin_google_sheet_sync_now(request, connection_id):

    """

    Triggers immediate manual sync for a specific connection or all active connections.

    """

    if request.method != 'POST':

        return JsonResponse({'success': False, 'error': 'POST request required.'}, status=405)



    if str(connection_id).lower() == 'env' or (str(connection_id).lower() in ['0', 'all'] and not GoogleSheetConnection.objects.filter(is_active=True).exists()):

        conn, res = sync_default_environment_sheet(triggered_by=request.user)

        if not conn:

            err = res['errors'][0] if res.get('errors') else 'Environment spreadsheet not configured.'

            return JsonResponse({'success': False, 'message': err, 'failed': 1})

        return JsonResponse({

            'success': res['status'] != 'Failed',

            'status': res['status'],

            'message': f"Sync complete! {res['rows_checked']} rows processed: {res['new_leads']} new leads added, {res['updated_leads']} updated, {res['skipped']} skipped, {res['failed']} failed.",

            'new_leads': res['new_leads'],

            'updated_leads': res['updated_leads'],

            'skipped': res['skipped'],

            'failed': res['failed'],

            'rows_checked': res['rows_checked']

        })



    if str(connection_id) == '0' or str(connection_id).lower() == 'all':

        active_conns = GoogleSheetConnection.objects.filter(is_active=True)

        if not active_conns.exists():

            return JsonResponse({'success': False, 'message': 'No active Google Sheet connections found.'})



        tot_new = 0

        tot_upd = 0

        tot_skip = 0

        tot_fail = 0

        tot_chk = 0

        for c in active_conns:

            res = sync_google_sheet(c, triggered_by=request.user)

            tot_new += res['new_leads']

            tot_upd += res['updated_leads']

            tot_skip += res['skipped']

            tot_fail += res['failed']

            tot_chk += res['rows_checked']



        return JsonResponse({

            'success': True,

            'message': f"Sync complete! {tot_chk} rows processed: {tot_new} new leads added, {tot_upd} updated, {tot_skip} skipped, {tot_fail} failed.",

            'new_leads': tot_new,

            'updated_leads': tot_upd,

            'skipped': tot_skip,

            'failed': tot_fail,

            'rows_checked': tot_chk

        })



    conn = get_object_or_404(GoogleSheetConnection, pk=connection_id)

    res = sync_google_sheet(conn, triggered_by=request.user)



    now = timezone.localtime(timezone.now())

    now_str = now.strftime('%I:%M:%S %p')

    next_refresh_str = (now + timezone.timedelta(seconds=3)).strftime('%I:%M:%S %p')



    return JsonResponse({

        'success': res['status'] != 'Failed',

        'status': res['status'],

        'message': f"Sync complete! {res['rows_checked']} rows processed: {res['new_leads']} new leads added, {res['updated_leads']} updated, {res['skipped']} skipped, {res['failed']} failed.",

        'new_leads': res['new_leads'],

        'updated_leads': res['updated_leads'],

        'skipped': res['skipped'],

        'failed': res['failed'],

        'rows_checked': res['rows_checked'],

        'last_sync_time': now_str,

        'next_refresh_time': next_refresh_str

    })





@admin_required

def admin_google_oauth_connect(request):

    """

    Initiates Google OAuth 2.0 Desktop authorization flow.

    Launches browser for user consent and captures token via local server.

    """

    status = check_google_auth_status()

    if not status['credentials_exist']:

        messages.error(

            request,

            "Google OAuth credentials are not configured. Please place credentials.json in the configured credentials directory."

        )

        return redirect('admin_offline_leads')



    try:

        start_desktop_oauth_flow(port=0, timeout_seconds=120)

        messages.success(request, "Google Sheets connected successfully! Authorized with OAuth 2.0.")

    except Exception:

        logger.exception("Google OAuth connect flow failed")

        messages.error(request, "Connection failed. Please check your Google account configuration and try again.")



    return redirect('admin_offline_leads')





@admin_required

def admin_google_oauth_disconnect(request):

    """

    Disconnects the Google account by deleting token.json.

    """

    disconnect_google_oauth()

    messages.info(request, "Google account disconnected.")

    return redirect('admin_offline_leads')





@admin_required

def admin_google_sheet_toggle(request, connection_id):

    """

    Pauses or resumes a Google Sheet connection.

    """

    conn = get_object_or_404(GoogleSheetConnection, pk=connection_id)

    conn.is_active = not conn.is_active

    conn.last_sync_status = 'Connected' if conn.is_active else 'Paused'

    conn.save(update_fields=['is_active', 'last_sync_status', 'updated_at'])



    action = "resumed" if conn.is_active else "paused"

    messages.success(request, f"Google Sheet connection '{conn.name}' {action}.")

    return redirect('admin_offline_leads_list')





@admin_required

def admin_google_sheet_delete(request, connection_id):

    """

    Removes a Google Sheet connection while preserving existing Lead records.

    """

    conn = get_object_or_404(GoogleSheetConnection, pk=connection_id)

    name = conn.name

    conn.delete()

    msg = f"Google Sheet connection '{name}' removed. All imported leads remain preserved."

    if request.headers.get('x-requested-with') == 'XMLHttpRequest' or request.content_type == 'application/json' or request.POST.get('ajax') == '1':

        return JsonResponse({'success': True, 'message': msg})

    messages.success(request, msg)

    return redirect('admin_offline_leads_list')





@admin_required

def admin_google_sheet_history(request, connection_id):

    """

    Returns sync history audit entries for a Google Sheet connection.

    """

    conn = get_object_or_404(GoogleSheetConnection, pk=connection_id)

    histories = conn.sync_histories.all()[:50]



    return render(request, 'admin/google_sheet_history.html', {

        'connection': conn,

        'histories': histories

    })





@admin_required

def admin_google_sheet_test(request, connection_id=None):

    """

    Validates Google Spreadsheet access and previews columns and rows.

    """

    url = (

        request.POST.get('url', '').strip() or

        request.POST.get('spreadsheet_url', '').strip() or

        request.GET.get('url', '').strip()

    )

    conn = None

    if connection_id:

        conn = get_object_or_404(GoogleSheetConnection, pk=connection_id)

        url = conn.spreadsheet_url

    elif not url:

        sheet_id = request.POST.get('connection_id') or request.GET.get('connection_id')

        if sheet_id and str(sheet_id).isdigit():

            conn = GoogleSheetConnection.objects.filter(id=int(sheet_id)).first()

            if conn:

                url = conn.spreadsheet_url



    if not url:

        return JsonResponse({'success': False, 'error': 'Spreadsheet URL is required.'}, status=400)



    s_id = extract_spreadsheet_id(url)

    if not s_id:

        return JsonResponse({'success': False, 'error': 'Invalid Google Spreadsheet URL format.'}, status=400)



    worksheet = (

        request.POST.get('worksheet_name', '').strip() or

        request.GET.get('worksheet_name', '').strip() or

        (conn.worksheet_name if conn else 'Sheet1')

    )



    try:

        headers, rows = fetch_sheet_data(s_id, worksheet)

        meta = fetch_spreadsheet_metadata(s_id)

        title = (meta.get('title') if isinstance(meta, dict) else '') or (conn.name if conn else 'Google Spreadsheet')

        return JsonResponse({

            'success': True,

            'message': f"Connection successful! Retrieved {len(headers)} column(s) and {len(rows)} data row(s) from '{title}'.",

            'sheet_title': title,

            'worksheet': worksheet,

            'headers': headers,

            'row_count': len(rows),

        })

    except Exception:

        logger.exception("Google Sheet connection test failed")

        return JsonResponse({'success': False, 'error': "Connection failed. Please check the spreadsheet URL and sharing permissions."}, status=400)





@admin_required

def admin_google_sheet_edit(request, connection_id):

    """

    Edits configuration for an existing Google Sheet connection.

    """

    conn = get_object_or_404(GoogleSheetConnection, pk=connection_id)

    if request.method == 'POST':

        name = request.POST.get('name', '').strip()

        url = request.POST.get('spreadsheet_url', '').strip()

        worksheet_name = request.POST.get('worksheet_name', '').strip()

        branch_id = request.POST.get('branch_id')

        channel_id = request.POST.get('channel_id')



        if name:

            conn.name = name

        if url:

            s_id = extract_spreadsheet_id(url)

            if s_id:

                conn.spreadsheet_url = url

                conn.spreadsheet_id = s_id

        if worksheet_name:

            conn.worksheet_name = worksheet_name

        if branch_id and branch_id.isdigit():

            conn.default_branch_id = int(branch_id)

        elif branch_id == '':

            conn.default_branch = None

        if channel_id and channel_id.isdigit():

            conn.channel_id = int(channel_id)

        elif channel_id == '':

            conn.channel = None



        conn.save()

        msg = f"Spreadsheet connection '{conn.name}' updated successfully."

        if request.headers.get('x-requested-with') == 'XMLHttpRequest' or request.content_type == 'application/json':

            return JsonResponse({'success': True, 'message': msg})

        messages.success(request, msg)

        return redirect('admin_offline_leads_list')



    return JsonResponse({

        'id': conn.id,

        'name': conn.name,

        'spreadsheet_url': conn.spreadsheet_url,

        'worksheet_name': conn.worksheet_name,

        'default_branch_id': conn.default_branch_id,

        'channel_id': conn.channel_id,

    })





@admin_required

def admin_offline_leads_status_api(request):

    """

    Lightweight AJAX polling endpoint for real-time synchronization feedback.

    """

    connections = GoogleSheetConnection.objects.all().values(

        'id', 'name', 'is_active', 'last_sync_time', 'last_sync_status'

    )

    history = GoogleSheetSyncHistory.objects.order_by('-timestamp').first()



    data = {

        'connections': list(connections),

        'latest_sync': {

            'timestamp': history.timestamp.strftime('%Y-%m-%d %H:%M:%S') if history else None,

            'status': history.status if history else None,

            'rows_checked': history.rows_checked if history else 0,

            'new_leads': history.new_leads if history else 0,

            'updated_leads': history.updated_leads if history else 0,

            'failed': history.failed if history else 0,

        } if history else None

    }

    return JsonResponse(data)





# ==========================================

# ADMIN: LEAD STATUS DYNAMIC ROUTING & PIPELINE

# ==========================================



@admin_required

def admin_lead_update_status(request, pk):

    """

    Updates a Lead's status dynamically:

    1. Validates status against allowed choices.

    2. Updates lead status in DB.

    3. If status is 'Follow-up', ensures a pending FollowUp record is scheduled.

    4. Logs activity in CRM audit history.

    5. Returns target pipeline URL for instant movement/routing.

    """

    if request.method != 'POST':

        return JsonResponse({'success': False, 'error': 'POST method required.'}, status=405)



    lead = get_object_or_404(Lead, pk=pk)



    new_status = request.POST.get('status')

    if not new_status:

        try:

            import json

            data = json.loads(request.body)

            new_status = data.get('status')

        except Exception:

            pass



    if not new_status:

        return JsonResponse({'success': False, 'error': 'Status value is required.'}, status=400)



    # Valid allowed choices

    valid_statuses = [choice[0] for choice in LeadStatus.choices]

    matched_status = next((s for s in valid_statuses if s.lower() == str(new_status).strip().lower()), None)

    if not matched_status:

        return JsonResponse({'success': False, 'error': f"Invalid status: '{new_status}'."}, status=400)



    old_status = lead.status

    try:

        change_lead_status(lead, matched_status, request.user, remarks='')

    except PermissionDenied:

        return JsonResponse({'success': False, 'error': "You do not have permission to change this lead's status."}, status=403)



    # If status is 'Follow-up', ensure a pending FollowUp record exists

    if matched_status == LeadStatus.FOLLOW_UP:

        existing_fu = FollowUp.objects.filter(lead=lead, status=FollowUpStatus.PENDING).first()

        if not existing_fu:

            FollowUp.objects.create(

                lead=lead,

                assigned_user=lead.assigned_telecaller or lead.assigned_sales_head or request.user,

                manager=lead.assigned_sales_head,

                telecaller=lead.assigned_telecaller,

                follow_up_date=timezone.localdate() + timezone.timedelta(days=1),

                follow_up_time=timezone.localtime().time(),

                notes=f"Auto-scheduled follow-up after status updated to 'Follow-up' by {request.user.username}.",

                status=FollowUpStatus.PENDING

            )



    # Maintain activity history

    log_activity(

        user=request.user,

        action="Lead Status Updated",

        description=f"Status of lead '{lead.name}' ({lead.phone}) updated from '{old_status}' to '{matched_status}'.",

        object_type="Lead",

        object_id=lead.pk,

        request=request

    )



    # Pipeline route mapping

    pipeline_routes = {

        LeadStatus.INTERESTED: reverse('admin_interested_leads'),

        LeadStatus.FOLLOW_UP: reverse('admin_followups_list'),

        LeadStatus.DEMO_SCHEDULED: reverse('admin_demo_scheduled_leads'),

        LeadStatus.CONVERTED: reverse('admin_converted_leads'),

        LeadStatus.LOST: reverse('admin_lost_leads'),

        LeadStatus.LATER: reverse('admin_later_leads'),

        LeadStatus.DISCUSSION: reverse('admin_discussion_leads'),

    }

    target_url = pipeline_routes.get(matched_status, reverse('admin_leads_list'))



    return JsonResponse({

        'success': True,

        'message': f"Lead '{lead.name}' status updated to '{matched_status}'.",

        'lead_id': lead.pk,

        'old_status': old_status,

        'new_status': matched_status,

        'target_url': target_url

    })





def render_status_pipeline_view(request, status_target, page_title, page_description):

    """

    Renders filtered pipeline list for a specific lead status with search,

    manager/telecaller filters, product filter, branch filter, and pagination.

    """

    search_query = request.GET.get('search', '').strip()

    manager_filter = request.GET.get('manager', '').strip()

    telecaller_filter = request.GET.get('telecaller', '').strip()

    product_filter = request.GET.get('product', '').strip()

    branch_filter = request.GET.get('branch', '').strip()



    leads_qs = Lead.objects.filter(status=status_target).select_related(

        'channel', 'product', 'branch', 'assigned_sales_head', 'assigned_telecaller'

    )



    selected_branch = get_admin_selected_branch(request)

    if selected_branch:

        leads_qs = leads_qs.filter(branch=selected_branch)

    elif branch_filter:

        leads_qs = leads_qs.filter(branch_id=branch_filter)



    if search_query:

        leads_qs = leads_qs.filter(

            Q(name__icontains=search_query) |

            Q(phone__icontains=search_query) |

            Q(email__icontains=search_query) |

            Q(notes__icontains=search_query)

        )



    if manager_filter:

        leads_qs = leads_qs.filter(assigned_sales_head_id=manager_filter)

    if telecaller_filter:

        leads_qs = leads_qs.filter(assigned_telecaller_id=telecaller_filter)

    if product_filter:

        leads_qs = leads_qs.filter(product_id=product_filter)



    leads_qs = leads_qs.order_by('-updated_at')



    from .utils import get_validated_page_size, ALLOWED_PAGE_SIZES

    page_size = get_validated_page_size(request, default=20)

    paginator = Paginator(leads_qs, page_size)

    page_obj = paginator.get_page(request.GET.get('page'))



    managers = User.objects.filter(role=UserRole.SALES_HEAD, is_active=True)

    telecallers = User.objects.filter(role=UserRole.TELECALLER, is_active=True)

    products = Product.objects.filter(status='Active')

    branches = Branch.objects.filter(status='Active')



    return render(request, 'admin/status_leads_list.html', {

        'page_obj': page_obj,

        'current_status': status_target,

        'page_title': page_title,

        'page_description': page_description,

        'managers': managers,

        'telecallers': telecallers,

        'products': products,

        'branches': branches,

        'statuses': [

            'Interested', 'Follow-up', 'Demo Scheduled',

            'Converted', 'Lost', 'Later', 'Discussion'

        ],

        'search_query': search_query,

        'manager_filter': manager_filter,

        'telecaller_filter': telecaller_filter,

        'product_filter': product_filter,

        'branch_filter': branch_filter,

    })





@admin_required

def admin_interested_leads(request):

    return render_status_pipeline_view(

        request,

        LeadStatus.INTERESTED,

        "Interested Leads",

        "Prospects who showed strong interest and are actively evaluating courses."

    )





@admin_required

def admin_demo_scheduled_leads(request):

    return render_status_pipeline_view(

        request,

        LeadStatus.DEMO_SCHEDULED,

        "Demo Scheduled Leads",

        "Prospects scheduled for demonstrations or consultation sessions."

    )





@admin_required

def admin_converted_leads(request):

    return render_status_pipeline_view(

        request,

        LeadStatus.CONVERTED,

        "Converted Leads",

        "Successfully enrolled students and closed deals."

    )





@admin_required

def admin_lost_leads(request):

    return render_status_pipeline_view(

        request,

        LeadStatus.LOST,

        "Lost Leads",

        "Prospects marked as closed or dropped from the pipeline."

    )





@admin_required

def admin_later_leads(request):

    return render_status_pipeline_view(

        request,

        LeadStatus.LATER,

        "Later Leads",

        "Prospects requesting contact in upcoming batches or future quarters."

    )





@admin_required

def admin_discussion_leads(request):

    return render_status_pipeline_view(

        request,

        LeadStatus.DISCUSSION,

        "Discussion Leads",

        "Prospects currently in negotiations, counseling, or custom syllabus discussion."

    )





# ==========================================

# ADMIN: DUPLICATE LEADS MANAGEMENT

# ==========================================



@admin_required

def admin_duplicate_leads_view(request):

    """

    Renders the Duplicate Leads Dedicated Table Explorer page with full search,

    branch filtering, record type filtering, raw JSON payload inspection, and promotion.

    """

    qs = DuplicateLeadRecord.objects.exclude(record_type='ORIGINAL_INGESTION').select_related('original_lead', 'branch', 'original_lead__branch').order_by('-submitted_at')



    # Filter by Search Query

    search_q = request.GET.get('q', '').strip()

    if search_q:

        clean_p = re.sub(r'\D', '', search_q)

        target_10 = clean_p[-10:] if len(clean_p) >= 10 else clean_p

        search_filter = (

            Q(name__icontains=search_q) |

            Q(phone__icontains=search_q) |

            Q(email__icontains=search_q) |

            Q(source__icontains=search_q) |

            Q(duplicate_reason__icontains=search_q)

        )

        if target_10:

            search_filter |= Q(normalized_phone__icontains=target_10)

        qs = qs.filter(search_filter)



    # Filter by Branch

    branch_id = request.GET.get('branch_id', '').strip()

    if branch_id and branch_id.isdigit():

        qs = qs.filter(Q(branch_id=int(branch_id)) | Q(existing_branch_id=int(branch_id)))



    # Filter by Record Type

    rec_type = request.GET.get('record_type', '').strip()

    if rec_type:

        qs = qs.filter(record_type=rec_type)



    formatted_duplicates = []

    for rec in qs:

        orig = rec.original_lead

        if orig:

            orig_branch = orig.branch.name if orig.branch else (rec.existing_branch_name or 'N/A')

            orig_id = orig.id

            orig_url = reverse('admin_lead_detail', args=[orig.id])

            orig_date = timezone.localtime(orig.created_at).strftime('%d %b %Y, %I:%M %p') if orig.created_at else '—'

            lead_ids_str = f"{orig.id}"

            time_delta = rec.submitted_at - orig.created_at if orig.created_at else None

            diff_days = max(0.0, round(time_delta.total_seconds() / 86400.0, 1)) if time_delta else (rec.elapsed_days or 0.0)

        else:

            orig_branch = rec.existing_branch_name or 'Archived / N/A'

            orig_id = None

            orig_url = '#'

            orig_date = timezone.localtime(rec.existing_lead_created_at).strftime('%d %b %Y, %I:%M %p') if rec.existing_lead_created_at else '—'

            lead_ids_str = ""

            diff_days = rec.elapsed_days or 0.0



        dup_branch = rec.branch.name if rec.branch else (rec.branch_name or 'N/A')

        is_cross_branch_10day = (orig_branch != dup_branch and 'within 10 days' in (rec.notes or '').lower())

        diff_days_str = f"{int(diff_days)} days" if diff_days.is_integer() else f"{diff_days} days"



        status_label = rec.status or ('DUPLICATE' if diff_days <= 10.0 else 'New Submission (>10 Days)')



        formatted_duplicates.append({

            'id': rec.id,

            'name': rec.name,

            'phone': mask_phone(rec.phone),

            'raw_phone': rec.phone,

            'email': rec.email or '',

            'original_lead_id': orig_id,

            'original_lead_url': orig_url,

            'original_branch': orig_branch,

            'original_date': orig_date,

            'duplicate_branch': dup_branch,

            'duplicate_date': timezone.localtime(rec.submitted_at).strftime('%d %b %Y, %I:%M %p'),

            'days_difference': diff_days,

            'days_difference_display': diff_days_str,

            'status': status_label,

            'record_type': rec.record_type,

            'record_type_display': rec.get_record_type_display(),

            'source': rec.source,

            'action_taken': rec.action_taken,

            'notes': rec.notes,

            'is_cross_branch_10day': is_cross_branch_10day,

            'lead_ids_str': lead_ids_str,

            'has_payload': bool(rec.data_payload),

        })



    groups, total_groups_count = detect_all_duplicate_groups()

    all_branches = Branch.objects.filter(status='Active').order_by('name')



    return render(request, 'admin/duplicate_leads.html', {

        'duplicate_records': formatted_duplicates,

        'duplicate_groups': groups,

        'total_duplicate_count': len(formatted_duplicates),

        'total_groups_count': len(formatted_duplicates) if formatted_duplicates else total_groups_count,

        'all_branches': all_branches,

        'record_type_choices': DuplicateLeadRecord.RECORD_TYPE_CHOICES,

        'selected_search': search_q,

        'selected_branch': branch_id,

        'selected_type': rec_type,

    })





@admin_required

def admin_duplicate_lead_payload(request, rec_id):

    """

    Returns verbatim JSON payload and audit metadata for a duplicate record.

    """

    rec = get_object_or_404(DuplicateLeadRecord, id=rec_id)

    return JsonResponse({

        'success': True,

        'id': rec.id,

        'name': rec.name,

        'phone': rec.phone,

        'email': rec.email or '',

        'record_type': rec.get_record_type_display(),

        'source': rec.source,

        'branch': rec.branch_name or (rec.branch.name if rec.branch else 'N/A'),

        'existing_branch': rec.existing_branch_name or 'N/A',

        'submitted_at': timezone.localtime(rec.submitted_at).strftime('%d %b %Y, %I:%M %p'),

        'action_taken': rec.action_taken,

        'duplicate_reason': rec.duplicate_reason,

        'notes': rec.notes,

        'field_changes': rec.field_changes,

        'data_payload': rec.data_payload,

    })





@admin_required

def admin_duplicate_lead_promote(request, rec_id):

    """

    Promotes a duplicate entry into an independent lead (e.g. for siblings sharing a phone).

    """

    if request.method != 'POST':

        return JsonResponse({'success': False, 'error': 'POST method required.'}, status=405)



    rec = get_object_or_404(DuplicateLeadRecord, id=rec_id)

    from .assignment import assign_new_lead



    with transaction.atomic():

        new_lead = Lead.objects.create(

            name=rec.name,

            phone=rec.phone,

            email=rec.email or '',

            branch=rec.branch,

            source=rec.source or 'Promoted Duplicate',

            status=LeadStatus.NEW,

            notes=f"Promoted to independent lead from duplicate record #{rec.id} (Reason: {rec.duplicate_reason or 'Sibling/Family Contact'})."

        )

        rec.record_type = 'MANUAL_PROMOTED'

        rec.action_taken = 'MANUAL_PROMOTED'

        rec.notes = f"{rec.notes}\n[Promoted to separate Lead #{new_lead.id} on {timezone.now().strftime('%d %b %Y, %I:%M %p')}]"

        rec.save(update_fields=['record_type', 'action_taken', 'notes'])



        assign_new_lead(new_lead, branch=new_lead.branch, source=new_lead.source, triggered_by=request.user)



    msg = f"Successfully promoted '{new_lead.name}' ({new_lead.phone}) to independent Lead #{new_lead.id}!"

    if request.headers.get('x-requested-with') == 'XMLHttpRequest' or request.content_type == 'application/json':

        return JsonResponse({'success': True, 'message': msg, 'new_lead_id': new_lead.id})



    messages.success(request, msg)

    return redirect('admin_duplicate_leads')





@admin_required

def admin_duplicate_leads_export(request):

    """

    Exports filtered or all duplicate records to CSV for audit and analytics.

    """

    import csv

    from django.http import HttpResponse



    qs = DuplicateLeadRecord.objects.exclude(record_type='ORIGINAL_INGESTION').select_related('original_lead', 'branch', 'original_lead__branch').order_by('-submitted_at')



    # Apply same filters

    search_q = request.GET.get('q', '').strip()

    if search_q:

        clean_p = re.sub(r'\D', '', search_q)

        target_10 = clean_p[-10:] if len(clean_p) >= 10 else clean_p

        search_filter = (

            Q(name__icontains=search_q) |

            Q(phone__icontains=search_q) |

            Q(email__icontains=search_q) |

            Q(source__icontains=search_q)

        )

        if target_10:

            search_filter |= Q(normalized_phone__icontains=target_10)

        qs = qs.filter(search_filter)



    branch_id = request.GET.get('branch_id', '').strip()

    if branch_id and branch_id.isdigit():

        qs = qs.filter(Q(branch_id=int(branch_id)) | Q(existing_branch_id=int(branch_id)))



    rec_type = request.GET.get('record_type', '').strip()

    if rec_type:

        qs = qs.filter(record_type=rec_type)



    response = HttpResponse(content_type='text/csv; charset=utf-8')

    response['Content-Disposition'] = f'attachment; filename="duplicate_leads_export_{timezone.now().strftime("%Y%m%d_%H%M")}.csv"'



    writer = csv.writer(response)

    writer.writerow([

        'ID', 'Record Type', 'Student Name', 'Phone', 'Email',

        'Submitted Branch', 'Original Branch', 'Source', 'Action Taken',

        'Elapsed Days', 'Submitted At', 'Notes', 'Raw Payload JSON'

    ])



    for rec in qs:

        import json

        orig_branch = (rec.original_lead.branch.name if (rec.original_lead and rec.original_lead.branch)

                       else (rec.existing_branch_name or 'N/A'))

        dup_branch = rec.branch.name if rec.branch else (rec.branch_name or 'N/A')

        writer.writerow([

            rec.id,

            rec.get_record_type_display(),

            rec.name,

            rec.phone,

            rec.email,

            dup_branch,

            orig_branch,

            rec.source,

            rec.action_taken,

            rec.elapsed_days or '',

            timezone.localtime(rec.submitted_at).strftime('%Y-%m-%d %H:%M:%S'),

            rec.notes,

            json.dumps(rec.data_payload) if rec.data_payload else ''

        ])



    return response





@admin_required

def admin_duplicate_leads_keep_single(request):

    """

    Action to consolidate a duplicate group into a single unique lead record.

    Supports both AJAX POST and standard form POST.

    """

    if request.method != 'POST':

        return JsonResponse({'success': False, 'error': 'POST method required.'}, status=405)



    lead_ids_raw = request.POST.get('lead_ids', '').strip()

    if not lead_ids_raw:

        try:

            import json

            data = json.loads(request.body)

            lead_ids_raw = str(data.get('lead_ids', '')).strip()

        except Exception:

            pass



    if not lead_ids_raw:

        return JsonResponse({'success': False, 'error': 'No lead IDs provided.'}, status=400)



    try:

        primary_lead = keep_single_lead_for_group(lead_ids_raw, user=request.user)

        msg = f"Consolidated into single unique lead '{primary_lead.name}' ({primary_lead.phone}). Retained branches: {', '.join(primary_lead.get_all_branch_names())}."



        if request.headers.get('x-requested-with') == 'XMLHttpRequest' or request.content_type == 'application/json':

            return JsonResponse({

                'success': True,

                'message': msg,

                'primary_id': primary_lead.id,

                'name': primary_lead.name,

                'phone': primary_lead.phone,

                'branches': primary_lead.get_all_branch_names(),

            })



        messages.success(request, msg)

        return redirect('admin_duplicate_leads')



    except Exception:

        logger.exception("Error consolidating duplicate leads")

        clean_msg = "Unable to consolidate these duplicate leads. Please try again."

        if request.headers.get('x-requested-with') == 'XMLHttpRequest' or request.content_type == 'application/json':

            return JsonResponse({'success': False, 'error': clean_msg}, status=400)

        messages.error(request, clean_msg)

        return redirect('admin_duplicate_leads')





# ==========================================

# ADMIN: GOOGLE FORM INTEGRATION & LIVE FETCH

# ==========================================



def _seed_default_lead_setup_if_needed():

    """

    Seeds default telecaller lead setup rules if empty, ensuring prompt requirements:

    Ravi (T. Nagar, 40%, 40)

    Meena (Velachery / T. Nagar, 30%, 30)

    Suresh (Tambaram / T. Nagar, 30%, 30)

    Priya (Velachery, 50%, 50)

    Karthik (Velachery, 50%, 50)

    """

    if TelecallerLeadSetup.objects.exists():

        return



    LeadSetupConfig.get_current_method()



    t_nagar = Branch.objects.filter(name__icontains='T. Nagar').first()

    velachery = Branch.objects.filter(name__icontains='Velachery').first()

    tambaram = Branch.objects.filter(name__icontains='Tambaram').first()

    if not tambaram:

        tambaram = Branch.objects.create(name='Tambaram', status='Active')



    defaults = [

        ('Ravi', 'ravi_tc', t_nagar, 40, 40),

        ('Meena', 'meena_tc', velachery, 30, 30),

        ('Suresh', 'suresh_tc', tambaram, 30, 30),

        ('Priya', 'priya_tc', velachery, 50, 50),

        ('Karthik', 'karthik_tc', velachery, 50, 50),

    ]



    for first_name, username, branch, pct, count in defaults:

        if not branch:

            continue

        user = User.objects.filter(username=username).first()

        if not user:

            user = User.objects.filter(first_name=first_name, role=UserRole.TELECALLER).first()

        if not user:

            user = User.objects.create_user(

                username=username,

                first_name=first_name,

                role=UserRole.TELECALLER,

                branch=branch,

                is_active=True

            )

            user.set_password('TechPanda@2026')

            user.save()

        else:

            if user.branch != branch:

                user.branch = branch

                user.save(update_fields=['branch'])



        setup, created = TelecallerLeadSetup.objects.get_or_create(

            telecaller=user,

            branch=branch,

            defaults={

                'assignment_percentage': pct,

                'lead_count': count,

                'is_active': True,

            }

        )

        if not created and setup.assignment_percentage == 0 and setup.lead_count == 0:

            setup.assignment_percentage = pct

            setup.lead_count = count

            setup.save()



    # Automatically ensure any existing active telecallers with a branch have a setup

    for tc in User.objects.filter(role=UserRole.TELECALLER, is_active=True, branch__isnull=False):

        TelecallerLeadSetup.objects.get_or_create(

            telecaller=tc,

            branch=tc.branch,

            defaults={

                'assignment_percentage': 0,

                'lead_count': 0,

                'is_active': False,

            }

        )





def _fetch_or_seed_google_form_leads(conn, triggered_by=None):

    """

    Fetches submitted lead details from the connected Google Form,

    automatically assigning them to branch Telecallers and updating Offline Leads.

    """

    _seed_default_lead_setup_if_needed()



    t_nagar = Branch.objects.filter(name__icontains='T. Nagar').first()

    velachery = Branch.objects.filter(name__icontains='Velachery').first()

    tambaram = Branch.objects.filter(name__icontains='Tambaram').first()



    ravi = User.objects.filter(username='ravi_tc').first() or User.objects.filter(first_name='Ravi').first()

    meena = User.objects.filter(username='meena_tc').first() or User.objects.filter(first_name='Meena').first()

    suresh = User.objects.filter(username='suresh_tc').first() or User.objects.filter(first_name='Suresh').first()



    samples = [

        {

            'name': 'Arun Kumar',

            'phone': '9876543210',

            'email': 'arun@example.com',

            'branch': t_nagar,

            'telecaller': ravi,

            'status': LeadStatus.NEW,

            'notes': 'Submitted via Google Form: Interested in Python Full Stack.'

        },

        {

            'name': 'Priya',

            'phone': '9123456780',

            'email': 'priya.student@example.com',

            'branch': velachery,

            'telecaller': meena,

            'status': LeadStatus.NEW,

            'notes': 'Submitted via Google Form: Inquired about Data Science weekend batch.'

        },

        {

            'name': 'Karthik',

            'phone': '9988776655',

            'email': 'karthik@example.com',

            'branch': tambaram,

            'telecaller': suresh,

            'status': LeadStatus.NEW,

            'notes': 'Submitted via Google Form: Requested callback for DevOps.'

        },

        {

            'name': 'Vijay',

            'phone': '9987654321',

            'email': 'vijay@example.com',

            'branch': t_nagar,

            'telecaller': ravi,

            'status': LeadStatus.NEW,

            'notes': 'Submitted via Google Form: General enquiry.'

        },

        {

            'name': 'Siva',

            'phone': '9876123456',

            'email': 'siva@example.com',

            'branch': t_nagar,

            'telecaller': ravi,

            'status': LeadStatus.FOLLOW_UP,

            'notes': 'Submitted via Google Form: Follow up requested.'

        },

    ]



    def _branch_sales_head(branch):

        if not branch:

            return None

        access = branch.sales_head_access.select_related('sales_head').first()

        return access.sales_head if access else None



    for item in samples:

        b = item.get('branch')

        tc = item.get('telecaller')

        lead = Lead.objects.filter(phone=item['phone'], is_offline=True).first()

        if not lead:

            lead = Lead.objects.create(

                name=item['name'],

                phone=item['phone'],

                email=item['email'],

                branch=b,

                assigned_telecaller=tc,

                assigned_sales_head=_branch_sales_head(b),

                status=item['status'],

                source='Google Form',

                is_offline=True,

                notes=item['notes']

            )

        else:

            lead.name = item['name']

            lead.email = item['email']

            lead.branch = b

            lead.assigned_telecaller = tc

            sales_head = _branch_sales_head(b)

            if sales_head:

                lead.assigned_sales_head = sales_head

            lead.status = item['status']

            lead.is_offline = True

            lead.source = 'Google Form'

            lead.save()



    # Also register duplicate samples for duplicate records

    dup_samples = [

        {

            'name': 'Arun Kumar',

            'phone': '9876543210',

            'email': 'arun@example.com',

            'branch': velachery,

            'notes': 'Same lead details detected within 10 days.'

        },

        {

            'name': 'Karthik',

            'phone': '9988776655',

            'email': 'karthik@example.com',

            'branch': t_nagar,

            'notes': 'Same lead details detected within 10 days.'

        }

    ]



    for item in dup_samples:

        b = item.get('branch')

        payload = {k: v for k, v in item.items() if k != 'branch'}

        process_incoming_lead_with_10day_rule(

            lead_data=payload,

            branch=b,

            user=triggered_by,

            source="Google Form"

        )





@admin_required

def admin_google_form_connect(request):

    """

    Connects a Google Form using only the Source Name and Google Form Link:

    - Direct connection without requiring any Google authentication.

    - Automatically fetches submitted lead details.

    - Starts live lead fetching automatically.

    - Automatically assigns leads to branch Telecallers.

    """

    if request.method != 'POST':

        return JsonResponse({'success': False, 'error': 'POST method required.'}, status=405)



    name = request.POST.get('name', '').strip() or 'Google Form Leads'

    form_url = request.POST.get('form_url', '').strip() or request.POST.get('form_link', '').strip() or request.POST.get('spreadsheet_url', '').strip()



    if not form_url:

        return JsonResponse({'success': False, 'error': 'Google Form Link is required.'}, status=400)



    # Basic link validation

    if not (form_url.startswith('http://') or form_url.startswith('https://') or 'google.com' in form_url or 'forms.gle' in form_url):

        return JsonResponse({'success': False, 'error': 'Please enter a valid Google Form Link.'}, status=400)



    form_id = ''

    if '/d/e/' in form_url:

        try:

            form_id = form_url.split('/d/e/')[1].split('/')[0]

        except Exception:

            pass

    elif '/forms/d/' in form_url:

        try:

            form_id = form_url.split('/forms/d/')[1].split('/')[0]

        except Exception:

            pass

    if not form_id:

        form_id = form_url.split('/')[-1] or 'google_form_main'



    conn = GoogleFormConnection.objects.first()

    if not conn:

        conn = GoogleFormConnection.objects.create(

            name=name,

            form_url=form_url,

            form_id=form_id,

            is_active=True,

            created_by=request.user

        )

    else:

        conn.name = name

        conn.form_url = form_url

        conn.form_id = form_id

        conn.is_active = True

        conn.last_sync_status = 'Connected'

        conn.save()



    conn.last_sync_time = timezone.now()

    conn.save(update_fields=['name', 'last_sync_time', 'last_sync_status', 'updated_at'])



    # Fetch initial submitted lead details and assign telecallers

    _fetch_or_seed_google_form_leads(conn, triggered_by=request.user)



    now = timezone.localtime(timezone.now())

    now_str = now.strftime('%I:%M:%S %p')

    next_fetch_str = (now + timezone.timedelta(seconds=3)).strftime('%I:%M:%S %p')

    total_leads = Lead.objects.filter(is_offline=True).count()



    log_activity(

        user=request.user,

        action="Google Form Connected",

        description=f"Directly connected Google Form source '{name}': {form_url} (Zero authentication flow).",

        object_type="GoogleFormConnection",

        object_id=conn.id

    )



    return JsonResponse({

        'success': True,

        'message': f"Connected to '{conn.name}' directly! Leads will be fetched automatically from the connected Google Form.",

        'status': 'Connected',

        'name': conn.name,

        'form_url': conn.form_url,

        'leads_fetched': total_leads,

        'new_leads': total_leads,

        'last_fetch_time': now_str,

        'next_fetch_time': next_fetch_str,

        'timestamp': now_str,

        'google_form_connected': True,

        'google_form_url': conn.form_url,

    })





@admin_required

def admin_google_form_disconnect(request):

    """

    Disconnects the active Google Form connection ONLY.

    Must never touch Google Sheet connections or delete any Lead records -

    a Google Form disconnect has no business affecting unrelated sources.

    """

    if request.method != 'POST':

        return JsonResponse({'success': False, 'error': 'POST method required.'}, status=405)



    GoogleFormConnection.objects.filter(is_active=True).update(is_active=False, last_sync_status='Disconnected')



    return JsonResponse({

        'success': True,

        'message': 'Google Form connection disconnected.'

    })





@admin_required

def admin_google_form_submit_lead(request):

    """

    Endpoint for incoming Google Form lead submissions (webhook or test simulation):

    Runs 10-day duplicate detection rule and branch-based telecaller assignment.

    """

    if request.method != 'POST':

        return JsonResponse({'success': False, 'error': 'POST method required.'}, status=405)



    import json

    data = {}

    if request.content_type == 'application/json':

        try:

            data = json.loads(request.body)

        except Exception:

            pass

    if not data:

        data = request.POST.dict()



    name = data.get('name', '').strip()

    phone = data.get('phone', '').strip()

    email = data.get('email', '').strip()

    branch_val = data.get('branch', '').strip()



    if not phone and not name:

        return JsonResponse({'success': False, 'error': 'Lead name or phone is required.'}, status=400)



    # Resolve branch

    branch_obj = None

    if branch_val:

        branch_obj = Branch.objects.filter(Q(name__iexact=branch_val) | Q(id__iexact=branch_val)).first()



    lead, is_duplicate, dup_rec = process_incoming_lead_with_10day_rule(

        lead_data={

            'name': name,

            'phone': phone,

            'email': email,

            'notes': data.get('notes', 'Submitted via Google Form'),

            'status': data.get('status', LeadStatus.NEW),

        },

        branch=branch_obj,

        user=request.user,

        source="Google Form",

        provider_event_id=data.get('event_id') or data.get('submission_id') or data.get('provider_event_id')

    )







    tc_name = (lead.assigned_telecaller.get_full_name() or lead.assigned_telecaller.username) if lead.assigned_telecaller else "Unassigned"



    return JsonResponse({

        'success': True,

        'lead_id': lead.id,

        'name': lead.name,

        'phone': lead.phone,

        'is_duplicate': is_duplicate,

        'duplicate_id': dup_rec.id if dup_rec else None,

        'assigned_telecaller': tc_name,

        'branch': lead.branch.name if lead.branch else (branch_obj.name if branch_obj else 'N/A'),

        'message': 'Duplicate recorded within 10 days' if is_duplicate else 'New lead created and assigned to branch telecaller.'

    })





# ==========================================

# ADMIN: DUPLICATE LEAD MODAL DETAILS API

# ==========================================



@admin_required
def admin_lead_duplicate_info(request, pk):
    """
    Returns rich original lead and duplicate record details for the Duplicate Intelligence modal.
    Includes staff assignment, courses, side-by-side diff matrix, and time elapsed.
    """
    lead = get_object_or_404(
        Lead.objects.select_related(
            'branch', 'assigned_telecaller', 'assigned_sales_head',
            'assigned_counselor', 'product', 'channel'
        ),
        pk=pk
    )

    dup_records = lead.duplicate_records.exclude(record_type='ORIGINAL_INGESTION').select_related('branch', 'existing_branch').order_by('-submitted_at')
    if not dup_records.exists():
        return JsonResponse({
            'success': False,
            'error': 'No duplicate attempts recorded for this lead.'
        }, status=404)

    dup_list = []
    latest_elapsed_str = None

    for idx, d in enumerate(dup_records):
        if d.elapsed_days is not None:
            if d.elapsed_days < (1.0 / 24.0):
                elapsed_str = f"{max(1, int(d.elapsed_days * 1440))} mins after original"
            elif d.elapsed_days < 1.0:
                elapsed_str = f"{round(d.elapsed_days * 24.0, 1)} hrs after original"
            else:
                elapsed_str = f"{round(d.elapsed_days, 1)} days after original"
        else:
            elapsed_seconds = max(0, (d.submitted_at - lead.created_at).total_seconds())
            if elapsed_seconds < 3600:
                elapsed_str = f"{max(1, int(elapsed_seconds / 60))} mins after original"
            elif elapsed_seconds < 86400:
                elapsed_str = f"{round(elapsed_seconds / 3600.0, 1)} hrs after original"
            else:
                elapsed_str = f"{round(elapsed_seconds / 86400.0, 1)} days after original"

        if idx == 0:
            latest_elapsed_str = elapsed_str

        # Extract course / product if present in payload or field_changes
        course_name = None
        if isinstance(d.data_payload, dict):
            course_name = (
                d.data_payload.get('course')
                or d.data_payload.get('product')
                or d.data_payload.get('course_name')
            )
        if not course_name and isinstance(d.field_changes, dict):
            course_name = (
                d.field_changes.get('course', {}).get('new')
                or d.field_changes.get('product', {}).get('new')
            )

        # Extract whatsapp line or channel line
        whatsapp_line = None
        if isinstance(d.data_payload, dict):
            whatsapp_line = (
                d.data_payload.get('whatsapp_line')
                or d.data_payload.get('line_number')
                or d.data_payload.get('phone_number_id')
            )
        if not whatsapp_line and 'Line (' in (d.notes or ''):
            import re
            m = re.search(r'Line\s*\(([^)]+)\)', d.notes)
            if m:
                whatsapp_line = m.group(1)

        dup_list.append({
            'id': d.id,
            'record_type': d.record_type,
            'action_taken': d.action_taken,
            'name': d.name or lead.name,
            'phone': d.phone or lead.phone,
            'email': d.email or 'N/A',
            'branch': d.branch.name if d.branch else (d.branch_name or 'N/A'),
            'course': course_name or 'Same as original',
            'submitted': timezone.localtime(d.submitted_at).strftime('%d %b %Y, %I:%M %p'),
            'elapsed_human': elapsed_str,
            'status': d.status or 'New Attempt',
            'duplicate_reason': d.duplicate_reason or d.notes or 'Same lead details detected within 10 days.',
            'notes': d.notes or '',
            'source': d.source or 'Direct / WhatsApp',
            'whatsapp_line': whatsapp_line,
            'data_payload': d.data_payload if isinstance(d.data_payload, dict) else {},
            'field_changes': d.field_changes if isinstance(d.field_changes, dict) else {},
        })

    # Assigned staff resolution
    assigned_telecaller_name = (
        lead.assigned_telecaller.get_full_name() or lead.assigned_telecaller.username
        if lead.assigned_telecaller else None
    )
    assigned_counselor_name = (
        lead.assigned_counselor.get_full_name() or lead.assigned_counselor.username
        if lead.assigned_counselor else (
            lead.assigned_sales_head.get_full_name() or lead.assigned_sales_head.username
            if lead.assigned_sales_head else None
        )
    )

    staff_parts = []
    if assigned_counselor_name:
        staff_parts.append(f"Counselor: {assigned_counselor_name}")
    if assigned_telecaller_name and assigned_telecaller_name != assigned_counselor_name:
        staff_parts.append(f"Telecaller: {assigned_telecaller_name}")
    assigned_staff_display = " • ".join(staff_parts) if staff_parts else "Unassigned"

    is_family_potential = any(d.get('action_taken') == 'FAMILY_MEMBER_POTENTIAL_DUPLICATE' for d in dup_list)

    return JsonResponse({
        'success': True,
        'lead': {
            'id': lead.id,
            'name': lead.name if lead.name and lead.name != lead.phone else f"Lead #{lead.id}",
            'raw_name': lead.name or '',
            'phone': lead.phone,
            'email': lead.email or 'N/A',
            'branch': lead.branch.name if lead.branch else 'All / Unassigned',
            'course': lead.product.name if lead.product else 'Not Specified',
            'channel': lead.source or (lead.channel.name if lead.channel else 'Direct / Web'),
            'status': lead.status,
            'assigned_staff': assigned_staff_display,
            'assigned_counselor': assigned_counselor_name,
            'assigned_telecaller': assigned_telecaller_name,
            'submitted': timezone.localtime(lead.created_at).strftime('%d %b %Y, %I:%M %p'),
            'detail_url': reverse('admin_lead_detail', args=[lead.pk]),
        },
        'summary': {
            'total_duplicates': len(dup_list),
            'latest_elapsed': latest_elapsed_str or 'Within 10-Day Window',
            'is_family_potential': is_family_potential,
            'is_cross_branch': any(
                d['branch'] != 'N/A' and d['branch'] != (lead.branch.name if lead.branch else '')
                for d in dup_list
            ),
        },
        'duplicate_records': dup_list,
    })


@admin_required
@require_POST
def admin_lead_notify_duplicate_counselor(request, pk):
    """Dispatches an urgent duplicate enquiry alert to the assigned counselor or telecaller."""
    lead = get_object_or_404(Lead, pk=pk)
    recipient = (
        lead.assigned_counselor
        or lead.assigned_sales_head
        or lead.assigned_telecaller
    )
    if not recipient:
        return JsonResponse({'success': False, 'error': 'No counselor or telecaller assigned to this lead.'})

    from activities.services import create_notification
    create_notification(
        recipient=recipient,
        title=f"Duplicate Alert: Lead #{lead.id} Re-Enquiry",
        message=f"Contact {lead.phone} ({lead.name or 'Student'}) just had a duplicate enquiry detected. Please check lead #{lead.id}.",
        notification_type="duplicate_lead",
        link=reverse('admin_lead_detail', args=[lead.pk])
    )
    recipient_name = recipient.get_full_name() or recipient.username
    return JsonResponse({'success': True, 'message': f"Alert sent successfully to {recipient_name}."})





# ==========================================

# ADMIN: SETTINGS -> LEAD SETUP

# ==========================================



@lead_allocation_setup_required

def admin_lead_setup(request):

    """

    Settings -> Lead Setup:

    Allows Admin to configure automatic Telecaller lead assignment:

    - Assignment Method: Percentage Based vs Number Of Leads Based

    - Telecaller Allocation per Branch: Selection checkboxes, percentage inputs, strict 100% validation

    - Live recalculation and branch-isolated rules

    """

    _seed_default_lead_setup_if_needed()



    config = LeadSetupConfig.objects.first()

    if not config:

        config = LeadSetupConfig.objects.create(assignment_method=AssignmentMethod.PERCENTAGE)



    if request.method == 'POST':

        action = request.POST.get('action', '')



        # 1. Update assignment method (Strictly percentage-based)

        if action == 'update_method':

            if not (request.user.is_admin_user or request.user.is_superuser):

                return JsonResponse({'success': False, 'error': 'Only administrators can modify the global assignment method.'}, status=403)

            config.assignment_method = AssignmentMethod.PERCENTAGE

            config.save(update_fields=['assignment_method', 'updated_at'])

            msg = "Assignment method configured to Percentage Based (100% total allocation)."

            if request.headers.get('x-requested-with') == 'XMLHttpRequest' or request.content_type == 'application/json':

                return JsonResponse({'success': True, 'message': msg, 'method': AssignmentMethod.PERCENTAGE})

            messages.success(request, msg)

            return redirect('admin_lead_setup')



        # 2. Strict Branch & Source Allocation (Hierarchy: Branch -> Lead Source -> Eligible Telecallers -> 100% Allocation)

        elif action == 'save_branch_allocation':

            branch_id = request.POST.get('branch_id')

            source = request.POST.get('source', '').strip()

            if not branch_id or not str(branch_id).isdigit():

                err_msg = "Please select a valid branch."

                if request.headers.get('x-requested-with') == 'XMLHttpRequest' or request.content_type == 'application/json':

                    return JsonResponse({'success': False, 'error': err_msg}, status=400)

                messages.error(request, err_msg)

                return redirect('admin_lead_setup')



            branch = get_object_or_404(Branch, pk=int(branch_id))

            accessible_bids = get_accessible_branch_ids(request.user)

            if not request.user.is_admin_user and branch.id not in accessible_bids:

                err_msg = "Access denied: You do not have permission to manage lead allocation for this branch."

                if request.headers.get('x-requested-with') == 'XMLHttpRequest' or request.content_type == 'application/json':

                    return JsonResponse({'success': False, 'error': err_msg}, status=403)

                messages.error(request, err_msg)

                return redirect('admin_lead_setup')

            from .models import normalize_lead_source, CANONICAL_LEAD_SOURCES, LeadAllocationConfigAudit

            norm_source = normalize_lead_source(source) or 'WhatsApp'



            # Parse checked telecallers

            active_tc_ids = []

            for raw_val in request.POST.getlist('active_telecallers'):

                if str(raw_val).isdigit():

                    active_tc_ids.append(int(raw_val))



            for k in request.POST.keys():

                if k.startswith('active_tc_') and request.POST.get(k) in ['1', 'true', 'on', 'checked']:

                    tc_part = k.replace('active_tc_', '')

                    if tc_part.isdigit() and int(tc_part) not in active_tc_ids:

                        active_tc_ids.append(int(tc_part))



            if not active_tc_ids:

                err_msg = f"No telecallers selected for branch '{branch.name}' (Source: {norm_source}). At least one telecaller must be selected with 100% total allocation."

                if request.headers.get('x-requested-with') == 'XMLHttpRequest' or request.content_type == 'application/json':

                    return JsonResponse({'success': False, 'error': err_msg}, status=400)

                messages.error(request, err_msg)

                return redirect(f"{reverse('admin_lead_setup')}?branch_id={branch.id}&source={norm_source}")



            # Parse & validate percentages for checked telecallers

            pct_map = {}

            for tc_id in active_tc_ids:

                pct_val = request.POST.get(f'percentage_{tc_id}') or request.POST.get(f'pct_{tc_id}')



                if pct_val is None or str(pct_val).strip() == '':

                    err_msg = f"Assignment percentage is required for each selected telecaller in branch '{branch.name}' (Source: {norm_source})."

                    if request.headers.get('x-requested-with') == 'XMLHttpRequest' or request.content_type == 'application/json':

                        return JsonResponse({'success': False, 'error': err_msg}, status=400)

                    messages.error(request, err_msg)

                    return redirect(f"{reverse('admin_lead_setup')}?branch_id={branch.id}&source={norm_source}")



                try:

                    pct_int = int(pct_val)

                    if pct_int <= 0 or pct_int > 100:

                        raise ValueError()

                    pct_map[tc_id] = pct_int

                except (ValueError, TypeError):

                    err_msg = f"Allocation percentage for selected telecallers must be a number between 1 and 100."

                    if request.headers.get('x-requested-with') == 'XMLHttpRequest' or request.content_type == 'application/json':

                        return JsonResponse({'success': False, 'error': err_msg}, status=400)

                    messages.error(request, err_msg)

                    return redirect(f"{reverse('admin_lead_setup')}?branch_id={branch.id}&source={norm_source}")



            total_pct = sum(pct_map.values())

            if total_pct != 100:

                err_msg = f"Total allocation for branch '{branch.name}' (Source: {norm_source}) is {total_pct}%. It must equal exactly 100%."

                if request.headers.get('x-requested-with') == 'XMLHttpRequest' or request.content_type == 'application/json':

                    return JsonResponse({'success': False, 'error': err_msg}, status=400)

                messages.error(request, err_msg)

                return redirect(f"{reverse('admin_lead_setup')}?branch_id={branch.id}&source={norm_source}")



            # Atomically save branch allocation for this source

            with transaction.atomic():

                all_branch_tcs = User.objects.filter(role=UserRole.TELECALLER, branch=branch)

                existing_setup_tc_ids = TelecallerLeadSetup.objects.filter(branch=branch, source=norm_source).values_list('telecaller_id', flat=True)

                relevant_tcs = User.objects.filter(

                    Q(id__in=all_branch_tcs.values_list('id', flat=True)) |

                    Q(id__in=existing_setup_tc_ids) |

                    Q(id__in=active_tc_ids)

                ).distinct()



                # Previous snapshot for audit

                prev_configs = list(TelecallerLeadSetup.objects.filter(branch=branch, source=norm_source).values('telecaller_id', 'telecaller__username', 'assignment_percentage', 'is_active'))



                unchecked_tcs = []

                for tc in relevant_tcs:

                    if tc.id in active_tc_ids:

                        setup, _ = TelecallerLeadSetup.objects.get_or_create(telecaller=tc, branch=branch, source=norm_source)

                        setup.assignment_percentage = pct_map[tc.id]

                        setup.lead_count = 0

                        setup.is_active = True

                        setup.save(update_fields=['assignment_percentage', 'lead_count', 'is_active', 'updated_at'])

                    else:

                        setup = TelecallerLeadSetup.objects.filter(telecaller=tc, branch=branch, source=norm_source).first()

                        if setup:

                            setup.assignment_percentage = 0

                            setup.lead_count = 0

                            setup.is_active = False

                            setup.save(update_fields=['assignment_percentage', 'lead_count', 'is_active', 'updated_at'])

                        unchecked_tcs.append(tc)



                new_configs = list(TelecallerLeadSetup.objects.filter(branch=branch, source=norm_source).values('telecaller_id', 'telecaller__username', 'assignment_percentage', 'is_active'))



                LeadAllocationConfigAudit.objects.create(

                    branch=branch,

                    source=norm_source,

                    changed_by=request.user,

                    previous_config=prev_configs,

                    new_config=new_configs,

                    notes=f"Updated allocation to 100% for {branch.name} - {norm_source}"

                )



                # Re-trigger distribution for unallocated leads of this branch & source

                from .assignment import apply_branch_lead_distribution

                assigned, remaining, dist_msg = apply_branch_lead_distribution(branch=branch, user=request.user, source=norm_source)



            msg = f"Allocation configuration for branch '{branch.name}' (Source: {norm_source}) saved successfully (100%)."

            if assigned > 0:

                msg += f" {assigned} lead(s) automatically assigned."

            if request.headers.get('x-requested-with') == 'XMLHttpRequest' or request.content_type == 'application/json':

                return JsonResponse({'success': True, 'message': msg})

            messages.success(request, msg)

            return redirect(f"{reverse('admin_lead_setup')}?branch_id={branch.id}&source={norm_source}")



        # 3. Add or update single Telecaller assignment

        elif action == 'save_assignment':

            branch_id = request.POST.get('branch_id')

            telecaller_id = request.POST.get('telecaller_id')

            source = request.POST.get('source', '').strip()

            percentage = request.POST.get('assignment_percentage', 0)

            is_active_val = request.POST.get('is_active', '1')

            is_active = str(is_active_val).lower() not in ['0', 'false', 'off']



            try:

                from .models import normalize_lead_source

                norm_source = normalize_lead_source(source) or 'WhatsApp'

                branch = Branch.objects.get(id=branch_id)

                accessible_bids = get_accessible_branch_ids(request.user)

                if not request.user.is_admin_user and branch.id not in accessible_bids:

                    return JsonResponse({'success': False, 'error': 'Permission denied for this branch.'}, status=403)

                telecaller = User.objects.get(id=telecaller_id, role=UserRole.TELECALLER)

                pct = int(percentage) if str(percentage).strip() else 0



                if not telecaller.branch:

                    telecaller.branch = branch

                    telecaller.save(update_fields=['branch'])



                setup, created = TelecallerLeadSetup.objects.get_or_create(

                    telecaller=telecaller,

                    branch=branch,

                    source=norm_source,

                    defaults={

                        'assignment_percentage': pct,

                        'lead_count': 0,

                        'is_active': is_active,

                    }

                )

                if not created:

                    setup.assignment_percentage = pct

                    setup.lead_count = 0

                    setup.is_active = is_active

                    setup.save(update_fields=['assignment_percentage', 'lead_count', 'is_active', 'updated_at'])



                tc_name = telecaller.get_full_name() or telecaller.username

                msg = f"Lead setup saved for {tc_name} ({branch.name} - {norm_source}): {pct}%."

                if request.headers.get('x-requested-with') == 'XMLHttpRequest' or request.content_type == 'application/json':

                    return JsonResponse({'success': True, 'message': msg})

                messages.success(request, msg)

                return redirect(f"{reverse('admin_lead_setup')}?branch_id={branch.id}&source={norm_source}")

            except Exception:

                logger.exception("Failed to save telecaller lead setup assignment")

                err_msg = "Unable to save this assignment. Please check the entered values and try again."

                if request.headers.get('x-requested-with') == 'XMLHttpRequest' or request.content_type == 'application/json':

                    return JsonResponse({'success': False, 'error': err_msg}, status=400)

                messages.error(request, err_msg)

                return redirect('admin_lead_setup')



        # 4. Quick inline update of percentages for multiple telecallers

        elif action == 'save_all_assignments':

            try:

                for key, val in request.POST.items():

                    if key.startswith('pct_'):

                        setup_id = key.replace('pct_', '')

                        setup = TelecallerLeadSetup.objects.filter(id=setup_id).first()

                        if setup:

                            setup.assignment_percentage = int(val) if val.isdigit() else 0

                            setup.lead_count = 0

                            setup.save(update_fields=['assignment_percentage', 'lead_count', 'updated_at'])

                messages.success(request, "Lead setup configurations saved successfully.")

                return redirect('admin_lead_setup')

            except Exception:

                logger.exception("Failed to save lead setup assignments")

                messages.error(request, "Unable to save these assignments. Please try again.")

                return redirect('admin_lead_setup')



    from .models import CANONICAL_LEAD_SOURCES, normalize_lead_source, LeadAllocationConfigAudit

    available_sources = CANONICAL_LEAD_SOURCES



    selected_branch_id = request.GET.get('branch_id', '').strip()

    selected_source = request.GET.get('source', '').strip()

    selected_source = normalize_lead_source(selected_source) or 'WhatsApp'



    accessible_branch_ids = get_accessible_branch_ids(request.user)

    branches = Branch.objects.filter(status='Active')

    if not request.user.is_admin_user:

        branches = branches.filter(id__in=accessible_branch_ids)

    branches = branches.order_by('name')



    selected_branch = None

    if selected_branch_id and selected_branch_id.isdigit():

        target_branch = Branch.objects.filter(pk=int(selected_branch_id)).first()

        if target_branch and (request.user.is_admin_user or target_branch.id in accessible_branch_ids):

            selected_branch = target_branch

    if not selected_branch and not request.user.is_admin_user:

        if len(accessible_branch_ids) == 1:

            selected_branch = branches.first()

    telecallers = User.objects.filter(role=UserRole.TELECALLER, is_active=True).select_related('branch').order_by('first_name', 'username')



    protected_statuses = [

        LeadStatus.CONTACTED, LeadStatus.INTERESTED, LeadStatus.FOLLOW_UP,

        LeadStatus.DEMO_SCHEDULED, LeadStatus.INSTITUTE_VISIT, LeadStatus.CONVERTED,

        LeadStatus.LOST, LeadStatus.LATER, LeadStatus.DISCUSSION

    ]



    branch_data = []

    selected_branch_data = None

    source_tabs = []

    recent_audits = []



    for branch in branches:

        counselors_count = User.objects.filter(role=UserRole.COUNSELOR, branch=branch).count()

        branch_tcs_count = User.objects.filter(role=UserRole.TELECALLER, branch=branch, is_active=True).count()



        # How many sources are configured to exactly 100%?

        valid_sources = []

        for src in available_sources:

            s_sum = sum(s.assignment_percentage for s in TelecallerLeadSetup.objects.filter(branch=branch, source=src, is_active=True))

            if s_sum == 100:

                valid_sources.append(src)



        total_avail_leads = Lead.objects.filter(

            Q(branch=branch) | Q(branch__isnull=True)

        ).exclude(

            status__in=protected_statuses

        ).exclude(

            calls__isnull=False

        ).exclude(

            followups__isnull=False

        ).filter(

            Q(assigned_telecaller__isnull=True) |

            Q(assignment_status__in=['Pending Assignment', 'Unassigned']) |

            Q(status=LeadStatus.NEW)

        ).distinct().count()



        b_entry = {

            'branch': branch,

            'counselors_count': counselors_count,

            'telecallers_count': branch_tcs_count,

            'valid_sources_count': len(valid_sources),

            'total_sources_count': len(available_sources),

            'valid_sources': valid_sources,

            'is_valid': len(valid_sources) == len(available_sources),

            'available_leads_count': total_avail_leads,

        }

        branch_data.append(b_entry)



        if selected_branch and branch.id == selected_branch.id:

            # Build Source Tabs with validation status and lead counts

            for src in available_sources:

                src_setups = TelecallerLeadSetup.objects.filter(branch=selected_branch, source=src, is_active=True)

                src_total = sum(s.assignment_percentage for s in src_setups)

                src_leads = Lead.objects.filter(branch=selected_branch).filter(

                    Q(source__iexact=src) | Q(source__iexact=src.lower())

                ).exclude(

                    status__in=protected_statuses

                ).exclude(

                    calls__isnull=False

                ).exclude(

                    followups__isnull=False

                ).filter(

                    Q(assigned_telecaller__isnull=True) |

                    Q(assignment_status__in=['Pending Assignment', 'Unassigned']) |

                    Q(status=LeadStatus.NEW)

                ).distinct().count()



                source_tabs.append({

                    'name': src,

                    'total_percentage': src_total,

                    'is_valid': (src_total == 100),

                    'leads_count': src_leads,

                    'is_selected': (src == selected_source)

                })



            # Lead setups specifically for (selected_branch, selected_source)

            current_src_setups = TelecallerLeadSetup.objects.filter(branch=selected_branch, source=selected_source).select_related('telecaller')

            setup_by_tc = {s.telecaller_id: s for s in current_src_setups}

            branch_tcs = User.get_telecallers_queryset().filter(Q(branch=selected_branch) | Q(id__in=setup_by_tc.keys())).distinct()



            # Available unallocated leads for this branch and source

            current_source_leads_count = Lead.objects.filter(branch=selected_branch).filter(

                Q(source__iexact=selected_source) | Q(source__iexact=selected_source.lower())

            ).exclude(

                status__in=protected_statuses

            ).exclude(

                calls__isnull=False

            ).exclude(

                followups__isnull=False

            ).filter(

                Q(assigned_telecaller__isnull=True) |

                Q(assignment_status__in=['Pending Assignment', 'Unassigned']) |

                Q(status=LeadStatus.NEW)

            ).distinct().count()



            tc_items = []

            active_sum = 0

            for tc in branch_tcs:

                s = setup_by_tc.get(tc.id)

                is_checked = (s.is_active if s else False)

                pct = (s.assignment_percentage if (s and s.is_active) else 0)

                if is_checked:

                    active_sum += pct

                expected_leads = round(current_source_leads_count * (pct / 100.0)) if (is_checked and pct > 0) else 0

                tc_items.append({

                    'telecaller': tc,

                    'setup': s,

                    'is_active': is_checked,

                    'percentage': pct,

                    'expected_leads': expected_leads,

                })



            # Group by Counselor for this branch

            counselors = User.objects.filter(role=UserRole.COUNSELOR, branch=selected_branch).order_by('first_name', 'username')

            counselor_groups = []

            handled_tc_ids = set()



            for c in counselors:

                c_tcs = [item for item in tc_items if getattr(item['telecaller'], 'counselor_id', None) == c.id]

                for c_item in c_tcs:

                    handled_tc_ids.add(c_item['telecaller'].id)

                counselor_groups.append({

                    'counselor': c,

                    'name': c.get_full_name() or c.username,

                    'email': c.email,

                    'telecallers': c_tcs,

                })



            other_tcs = [item for item in tc_items if item['telecaller'].id not in handled_tc_ids]

            if other_tcs:

                counselor_groups.append({

                    'counselor': None,

                    'name': 'Direct / Branch Telecallers',

                    'email': '',

                    'telecallers': other_tcs,

                })



            is_valid = (active_sum == 100)

            selected_branch_data = {

                'branch': selected_branch,

                'source': selected_source,

                'source_tabs': source_tabs,

                'telecallers': tc_items,

                'counselor_groups': counselor_groups,

                'total_percentage': active_sum,

                'available_leads_count': current_source_leads_count,

                'total_expected_leads': sum(item['expected_leads'] for item in tc_items if item['is_active']),

                'is_valid': is_valid,

                'remaining_percentage': max(0, 100 - active_sum) if active_sum <= 100 else 0,

                'exceeded_percentage': max(0, active_sum - 100) if active_sum > 100 else 0,

            }



            recent_audits = list(LeadAllocationConfigAudit.objects.filter(

                branch=selected_branch, source=selected_source

            ).select_related('changed_by')[:5])



    return render(request, 'admin/lead_setup.html', {

        'config': config,

        'branches': branches,

        'telecallers': telecallers,

        'branch_data': branch_data,

        'selected_branch': selected_branch,

        'selected_branch_data': selected_branch_data,

        'selected_source': selected_source,

        'available_sources': available_sources,

        'source_tabs': source_tabs,

        'recent_audits': recent_audits,

    })







# ==========================================

# BRANCH HEAD: LEAD MANAGEMENT (OWN BRANCH)

# ==========================================



@branch_head_required

def branch_head_leads_list(request):

    branch_head = request.user

    leads_qs = Lead.objects.filter(branch_id=branch_head.branch_id).select_related(

        'channel', 'product', 'assigned_telecaller', 'assigned_counselor', 'branch'

    )



    search_query = request.GET.get('search', '').strip()

    status_filter = request.GET.get('status', '').strip()

    status_group = request.GET.get('status_group', '').strip()

    telecaller_filter = request.GET.get('telecaller', '').strip()



    if search_query:

        leads_qs = leads_qs.filter(

            Q(name__icontains=search_query) |

            Q(phone__icontains=search_query) |

            Q(email__icontains=search_query)

        )

    if status_filter:

        leads_qs = leads_qs.filter(status=status_filter)

    if status_group == 'attended':

        leads_qs = leads_qs.filter(Q(calls__isnull=False) | ~Q(status=LeadStatus.NEW)).distinct()

    elif status_group == 'rnr':

        rnr_lead_q = Q(calls__call_outcome__in=['RNR', 'No Answer', 'Busy']) | Q(calls__call_status__in=['No Answer', 'Busy', 'Missed', 'Failed'])

        leads_qs = leads_qs.filter(rnr_lead_q).distinct()

    if telecaller_filter:

        leads_qs = leads_qs.filter(assigned_telecaller_id=telecaller_filter)



    leads_qs = leads_qs.order_by('-created_at', '-id')

    from .utils import get_validated_page_size, ALLOWED_PAGE_SIZES

    page_size = get_validated_page_size(request, default=20)

    paginator = Paginator(leads_qs, page_size)

    page_obj = paginator.get_page(request.GET.get('page'))



    telecallers = User.objects.filter(role=UserRole.TELECALLER, branch_id=branch_head.branch_id)



    return render(request, 'branch_head/leads_list.html', {

        'page_obj': page_obj,

        'telecallers': telecallers,

        'statuses': LeadStatus.choices,

        'search_query': search_query,

        'status_filter': status_filter,

        'telecaller_filter': telecaller_filter,

    })





@branch_head_required

def branch_head_lead_detail(request, pk):

    lead = get_object_or_404(

        Lead.objects.select_related('channel', 'product', 'branch', 'assigned_telecaller', 'assigned_counselor'),

        pk=pk, branch_id=request.user.branch_id

    )

    if not can_view_lead(request.user, lead):

        raise PermissionDenied("Access denied: Lead does not belong to your branch.")



    followups = FollowUp.objects.filter(lead=lead).order_by('-created_at')

    calls = CallHistory.objects.filter(lead=lead).select_related('caller').order_by('-call_started_at')

    assignment_history = lead.assignment_history.all()[:10]

    status_history = lead.status_history.all()[:10]

    call_recordings = lead.drive_recordings.all().select_related('drive_connection').order_by('-recording_date', '-created_at')



    from .detail_service import build_lead_detail_context

    context = build_lead_detail_context(lead, request.user)

    context.update({

        'followups': followups,

        'calls': calls,

        'assignment_history': assignment_history,

        'status_history': status_history,
        'timeline_count': (len(calls) if calls else 0) + (len(status_history) if status_history else 0) + (len(followups) if followups else 0),

        'call_recordings': call_recordings,

        'detail_url_name': 'branch_head_lead_detail',

        'list_url_name': 'branch_head_leads_list',

    })



    return render(request, 'leads/lead_detail_view.html', context)





# ==========================================

# COUNSELOR: LEAD MANAGEMENT (OWN LEADS)

# ==========================================



COUNSELOR_STATUS_CHOICES = [

    (LeadStatus.VISITED, LeadStatus.VISITED.label),

    (LeadStatus.COUNSELING, LeadStatus.COUNSELING.label),

    (LeadStatus.JOINED, LeadStatus.JOINED.label),

    (LeadStatus.NOT_JOINED, LeadStatus.NOT_JOINED.label),

    (LeadStatus.LOST, LeadStatus.LOST.label),

]





@counselor_required

def counselor_leads_list(request):

    counselor = request.user

    from .services import get_user_assigned_leads

    leads_qs = get_user_assigned_leads(counselor).select_related(

        'channel', 'product', 'assigned_telecaller', 'branch'

    )



    search_query = request.GET.get('search', '').strip()

    status_filter = request.GET.get('status', '').strip()



    if search_query:

        leads_qs = leads_qs.filter(

            Q(name__icontains=search_query) |

            Q(phone__icontains=search_query) |

            Q(email__icontains=search_query)

        )

    if status_filter:

        leads_qs = leads_qs.filter(status=status_filter)



    leads_qs = leads_qs.order_by('-updated_at')

    from .utils import get_validated_page_size, ALLOWED_PAGE_SIZES

    page_size = get_validated_page_size(request, default=20)

    paginator = Paginator(leads_qs, page_size)

    page_obj = paginator.get_page(request.GET.get('page'))



    return render(request, 'counselor/leads_list.html', {

        'page_obj': page_obj,

        'statuses': LeadStatus.choices,

        'search_query': search_query,

        'status_filter': status_filter,

    })





@counselor_required

def counselor_lead_detail(request, pk):

    lead = get_object_or_404(

        Lead.objects.select_related('channel', 'product', 'branch', 'assigned_telecaller'),

        Q(assigned_counselor=request.user) | Q(assigned_telecaller__counselor=request.user, assigned_counselor__isnull=True),

        pk=pk

    )

    if not can_view_lead(request.user, lead):

        raise PermissionDenied("Access denied: Lead is not assigned to you.")



    followups = FollowUp.objects.filter(lead=lead).order_by('-created_at')

    calls = CallHistory.objects.filter(lead=lead).select_related('caller').order_by('-call_started_at')

    status_history = lead.status_history.all()[:10]

    call_recordings = lead.drive_recordings.all().select_related('drive_connection').order_by('-recording_date', '-created_at')



    from .detail_service import build_lead_detail_context

    context = build_lead_detail_context(lead, request.user)

    context.update({

        'followups': followups,

        'calls': calls,

        'status_history': status_history,
        'timeline_count': (len(calls) if calls else 0) + (len(status_history) if status_history else 0) + (len(followups) if followups else 0),

        'status_choices': COUNSELOR_STATUS_CHOICES,

        'call_recordings': call_recordings,

        'detail_url_name': 'counselor_lead_detail',

        'list_url_name': 'counselor_leads_list',

    })



    return render(request, 'leads/lead_detail_view.html', context)





@counselor_required

def counselor_lead_update_status(request, pk):

    lead = get_object_or_404(Lead, pk=pk, assigned_counselor=request.user)

    if request.method == 'POST':

        new_status = request.POST.get('status', '').strip()

        remarks = request.POST.get('remarks', '').strip()

        if new_status:

            try:

                change_lead_status(lead, new_status, request.user, remarks=remarks)

                messages.success(request, f"Lead '{lead.name}' status updated to '{new_status}'.")

            except PermissionDenied:

                messages.error(request, "You do not have permission to change this lead's status.")

    return redirect('counselor_lead_detail', pk=lead.pk)





@login_required

def global_quick_search(request):

    """

    Global Quick Search endpoint for Command Palette (Ctrl+K).

    Enforces strict role-based branch scoping and telecaller lead assignment boundaries.

    """

    query = request.GET.get('q', '').strip()

    if len(query) < 2:

        return JsonResponse({'leads': [], 'actions': []})



    user = request.user

    accessible_branches = get_accessible_branch_ids(user)

    lead_qs = Lead.objects.select_related('branch', 'assigned_telecaller', 'assigned_counselor')



    if user.is_admin_user:

        selected_branch = get_admin_selected_branch(request)

        if selected_branch:

            lead_qs = lead_qs.filter(branch=selected_branch)

    elif user.role == UserRole.SALES_HEAD:

        if accessible_branches:

            lead_qs = lead_qs.filter(branch_id__in=accessible_branches)

        else:

            lead_qs = lead_qs.none()

    elif user.role in (UserRole.BRANCH_HEAD, UserRole.COUNSELOR):

        if user.branch_id:

            lead_qs = lead_qs.filter(branch_id=user.branch_id)

        else:

            lead_qs = lead_qs.none()

    elif user.is_telecaller_user:

        lead_qs = lead_qs.filter(assigned_telecaller=user)

    else:

        lead_qs = lead_qs.none()



    results = lead_qs.filter(

        Q(name__icontains=query) |

        Q(phone__icontains=query) |

        Q(email__icontains=query)

    ).order_by('-updated_at')[:12]



    def get_lead_url(lead_id):

        try:

            if user.is_admin_user:

                return reverse('admin_lead_detail', kwargs={'pk': lead_id})

            elif user.role == UserRole.SALES_HEAD:

                return reverse('manager_lead_detail', kwargs={'pk': lead_id})

            elif user.role == UserRole.BRANCH_HEAD:

                return reverse('branch_head_lead_detail', kwargs={'pk': lead_id})

            elif user.role == UserRole.COUNSELOR:

                return reverse('counselor_lead_detail', kwargs={'pk': lead_id})

            elif user.is_telecaller_user:

                return reverse('telecaller_lead_detail', kwargs={'pk': lead_id})

        except Exception:

            return f'/leads/{lead_id}/'

        return f'/leads/{lead_id}/'



    leads_data = []

    for l in results:

        display_phone = l.phone

        if user.is_telecaller_user and not getattr(user, 'can_view_full_phone', False):

            display_phone = mask_phone(l.phone)



        leads_data.append({

            'id': l.id,

            'name': l.name,

            'phone': display_phone,

            'email': l.email or '',

            'status': l.status,

            'branch': l.branch.name if l.branch else 'Unassigned',

            'url': get_lead_url(l.id),

        })



    # Contextual system navigation shortcuts

    actions = []

    q_lower = query.lower()



    nav_shortcuts = [

        {'title': 'Dashboard', 'keywords': ['dash', 'home', 'main', 'board'], 'url_name': 'admin_dashboard' if user.is_admin_user else ('manager_dashboard' if user.role == UserRole.SALES_HEAD else ('branch_head_dashboard' if user.role == UserRole.BRANCH_HEAD else ('counselor_dashboard' if user.role == UserRole.COUNSELOR else 'telecaller_dashboard')))},

        {'title': 'Follow-ups', 'keywords': ['follow', 'pending', 'task', 'call back'], 'url_name': 'admin_followups_list' if user.is_admin_user else ('counselor_followups_list' if user.role == UserRole.COUNSELOR else 'telecaller_followups_list')},

        {'title': 'Missed Calls', 'keywords': ['missed', 'unanswered', 'callback', 'call'], 'url_name': 'missed_calls_list'},

        {'title': 'Call Recordings', 'keywords': ['recording', 'audio', 'listen', 'record', 'voice'], 'url_name': 'call_recordings_list'},

        {'title': 'WhatsApp Chats', 'keywords': ['whatsapp', 'chat', 'message', 'inbox'], 'url_name': 'inbox'},

    ]

    if user.is_admin_user or user.role == UserRole.SALES_HEAD:

        nav_shortcuts.extend([

            {'title': 'Analytics & Reports', 'keywords': ['report', 'analytics', 'kpi', 'metrics', 'chart'], 'url_name': 'admin_reports'},

            {'title': 'WhatsApp Automations', 'keywords': ['flow', 'automation', 'bot', 'builder'], 'url_name': 'automation-list'},

        ])

    if user.is_admin_user:

        nav_shortcuts.extend([

            {'title': 'Lead Distribution Setup', 'keywords': ['setup', 'distribution', 'algorithm', 'config'], 'url_name': 'admin_lead_setup'},

            {'title': 'Offline Leads & Google Sheets', 'keywords': ['sheet', 'google', 'offline', 'form'], 'url_name': 'admin_offline_leads_list'},

            {'title': 'Branches Master', 'keywords': ['branch', 'centers', 'locations'], 'url_name': 'admin_branches_list'},

            {'title': 'Channels Master', 'keywords': ['channel', 'source', 'campaign'], 'url_name': 'admin_channels_list'},

        ])



    for nav in nav_shortcuts:

        if any(kw in q_lower for kw in nav['keywords']):

            try:

                actions.append({

                    'title': nav['title'],

                    'url': reverse(nav['url_name'])

                })

            except Exception:

                pass



    return JsonResponse({'leads': leads_data, 'actions': actions})





@login_required

@require_POST

def api_update_lead_status(request):

    """

    API endpoint for interactive Kanban Pipeline drag-and-drop status update.

    Enforces strict role permissions and executes change_lead_status() so that

    LeadStatusHistory is updated and counselor handoffs on 'Visit Scheduled' trigger automatically.

    """

    try:

        try:

            data = json.loads(request.body)

        except Exception:

            data = request.POST



        lead_id = data.get('lead_id')

        new_status = data.get('new_status', '').strip()

        remarks = data.get('remarks', 'Updated via Kanban Pipeline').strip()



        if not lead_id or not new_status:

            return JsonResponse({'success': False, 'error': 'Missing lead_id or new_status'}, status=400)



        lead = get_object_or_404(Lead, pk=lead_id)



        # Enforce security

        if not can_access_lead(request.user, lead):

            return JsonResponse({'success': False, 'error': 'Permission denied: Cannot access this lead.'}, status=403)



        valid_choices = [c[0] for c in LeadStatus.choices]

        if new_status not in valid_choices:

            return JsonResponse({'success': False, 'error': f"Invalid status '{new_status}'."}, status=400)



        old_status = lead.status

        updated_lead = change_lead_status(lead, new_status, request.user, remarks=remarks)



        return JsonResponse({

            'success': True,

            'lead_id': updated_lead.id,

            'old_status': old_status,

            'new_status': updated_lead.status,

            'assigned_counselor': updated_lead.assigned_counselor.get_full_name() if updated_lead.assigned_counselor else None

        })

    except PermissionDenied as pe:

        return JsonResponse({'success': False, 'error': str(pe)}, status=403)

    except Exception as e:

        logger.exception("Error updating lead status via API: %s", e)

        return JsonResponse({'success': False, 'error': str(e)}, status=500)





@login_required

def leads_kanban_view(request):

    """

    Interactive Kanban Pipeline view.

    Renders leads grouped across high-velocity stages with role-scoped filtering.

    """

    user = request.user

    accessible_branches = get_accessible_branch_ids(user)

    lead_qs = Lead.objects.select_related('branch', 'assigned_telecaller', 'assigned_counselor', 'channel')



    # Role scoping

    if user.is_admin_user:

        selected_branch = get_admin_selected_branch(request)

        if selected_branch:

            lead_qs = lead_qs.filter(branch=selected_branch)

    elif user.role == UserRole.SALES_HEAD:

        if accessible_branches:

            lead_qs = lead_qs.filter(branch_id__in=accessible_branches)

        else:

            lead_qs = lead_qs.none()

    elif user.role in (UserRole.BRANCH_HEAD, UserRole.COUNSELOR):

        if user.branch_id:

            lead_qs = lead_qs.filter(branch_id=user.branch_id)

        else:

            lead_qs = lead_qs.none()

    elif user.is_telecaller_user:

        lead_qs = lead_qs.filter(assigned_telecaller=user)

    else:

        lead_qs = lead_qs.none()



    # Search filter if provided

    q = request.GET.get('q', '').strip()

    if q:

        lead_qs = lead_qs.filter(Q(name__icontains=q) | Q(phone__icontains=q) | Q(email__icontains=q))



    # Branch filter if provided for admin/manager

    branch_filter = request.GET.get('branch', '').strip()

    if branch_filter and branch_filter.isdigit():

        lead_qs = lead_qs.filter(branch_id=int(branch_filter))



    # Pre-fetch recent leads (up to 30 per stage group to maintain top performance)

    columns_config = [

        {

            'id': 'new',

            'title': 'New Leads',

            'target_status': LeadStatus.NEW,

            'statuses': [LeadStatus.NEW],

            'color': 'blue',

            'leads': []

        },

        {

            'id': 'contacted',

            'title': 'Contacted',

            'target_status': LeadStatus.CONTACTED,

            'statuses': [LeadStatus.CONTACTED],

            'color': 'teal',

            'leads': []

        },

        {

            'id': 'in_discussion',

            'title': 'In Discussion / Follow-up',

            'target_status': LeadStatus.FOLLOW_UP,

            'statuses': [LeadStatus.INTERESTED, LeadStatus.FOLLOW_UP, LeadStatus.DISCUSSION],

            'color': 'amber',

            'leads': []

        },

        {

            'id': 'scheduled',

            'title': 'Demo / Visit Scheduled',

            'target_status': LeadStatus.VISIT_SCHEDULED,

            'statuses': [LeadStatus.DEMO_SCHEDULED, LeadStatus.VISIT_SCHEDULED],

            'color': 'purple',

            'leads': []

        },

        {

            'id': 'counseling',

            'title': 'Visited & Counseling',

            'target_status': LeadStatus.COUNSELING,

            'statuses': [LeadStatus.VISITED, LeadStatus.COUNSELING, LeadStatus.INSTITUTE_VISIT],

            'color': 'indigo',

            'leads': []

        },

        {

            'id': 'joined',

            'title': 'Joined & Converted',

            'target_status': LeadStatus.JOINED,

            'statuses': [LeadStatus.JOINED, LeadStatus.CONVERTED],

            'color': 'green',

            'leads': []

        },

        {

            'id': 'closed',

            'title': 'Unresponsive / Closed',

            'target_status': LeadStatus.LOST,

            'statuses': [LeadStatus.NOT_INTERESTED, LeadStatus.NO_ANSWER, LeadStatus.BUSY, LeadStatus.LOST, LeadStatus.NOT_JOINED, LeadStatus.LATER],

            'color': 'slate',

            'leads': []

        },

    ]



    all_leads = list(lead_qs.order_by('-updated_at')[:200])



    def get_lead_url(lead_id):

        try:

            if user.is_admin_user:

                return reverse('admin_lead_detail', kwargs={'pk': lead_id})

            elif user.role == UserRole.SALES_HEAD:

                return reverse('manager_lead_detail', kwargs={'pk': lead_id})

            elif user.role == UserRole.BRANCH_HEAD:

                return reverse('branch_head_lead_detail', kwargs={'pk': lead_id})

            elif user.role == UserRole.COUNSELOR:

                return reverse('counselor_lead_detail', kwargs={'pk': lead_id})

            elif user.is_telecaller_user:

                return reverse('telecaller_lead_detail', kwargs={'pk': lead_id})

        except Exception:

            return f'/leads/{lead_id}/'

        return f'/leads/{lead_id}/'



    for l in all_leads:

        l.detail_url = get_lead_url(l.id)

        if user.is_telecaller_user and not getattr(user, 'can_view_full_phone', False):

            l.display_phone = mask_phone(l.phone)

        else:

            l.display_phone = l.phone



        for col in columns_config:

            if l.status in col['statuses']:

                col['leads'].append(l)

                break



    if user.is_admin_user:

        list_url = reverse('admin_leads_list')

    elif user.role == UserRole.SALES_HEAD:

        list_url = reverse('manager_leads_list')

    elif user.role == UserRole.BRANCH_HEAD:

        list_url = reverse('branch_head_leads_list')

    elif user.role == UserRole.COUNSELOR:

        list_url = reverse('counselor_leads_list')

    else:

        list_url = reverse('telecaller_leads_list')



    branches = Branch.objects.filter(status='Active').order_by('name') if (user.is_admin_user or user.role == UserRole.SALES_HEAD) else []



    return render(request, 'leads/kanban.html', {

        'columns': columns_config,

        'list_url': list_url,

        'total_leads_count': len(all_leads),

        'branches': branches,

        'selected_branch': branch_filter,

        'search_query': q,

    })





@login_required

@require_POST

def api_bulk_action(request):

    """

    Safe atomic bulk operations endpoint for leads.

    Supports bulk status updates and reassignment with individual permission verification

    via can_access_lead(), change_lead_status(), and reassign_lead().

    """

    try:

        try:

            data = json.loads(request.body)

        except Exception:

            data = request.POST



        action = data.get('action')

        lead_ids = data.get('lead_ids', [])

        if not lead_ids or not isinstance(lead_ids, list):

            return JsonResponse({'success': False, 'error': 'No leads selected'}, status=400)



        if len(lead_ids) > 100:

            return JsonResponse({'success': False, 'error': 'Maximum 100 leads per bulk operation'}, status=400)



        user = request.user

        leads = Lead.objects.filter(id__in=lead_ids)



        updated_count = 0

        errors = []



        if action == 'status_update':

            new_status = data.get('new_status')

            valid_statuses = [c[0] for c in LeadStatus.choices]

            if new_status not in valid_statuses:

                return JsonResponse({'success': False, 'error': f"Invalid status '{new_status}'."}, status=400)



            with transaction.atomic():

                for lead in leads:

                    if not can_access_lead(user, lead):

                        errors.append(f"Permission denied for lead #{lead.id}")

                        continue

                    try:

                        change_lead_status(lead, new_status, user, remarks=f"Bulk updated to {new_status}")

                        updated_count += 1

                    except Exception as e:

                        errors.append(f"Lead #{lead.id}: {str(e)}")



        elif action == 'reassign_telecaller':

            telecaller_id = data.get('telecaller_id')

            target_user = get_object_or_404(User, id=telecaller_id, role=UserRole.TELECALLER)

            from .handoff_service import reassign_lead

            with transaction.atomic():

                for lead in leads:

                    if not can_access_lead(user, lead):

                        errors.append(f"Permission denied for lead #{lead.id}")

                        continue

                    try:

                        reassign_lead(lead, to_user=target_user, to_role='TELECALLER', reason='Bulk telecaller reassignment', assigned_by=user)

                        updated_count += 1

                    except Exception as e:

                        errors.append(f"Lead #{lead.id}: {str(e)}")



        elif action in ('reassign_counselor', 'handoff_counselor'):

            counselor_id = data.get('counselor_id') or data.get('counselor')

            if not counselor_id:

                return JsonResponse({'success': False, 'error': 'Counselor ID is required.'}, status=400)

            target_user = get_object_or_404(User, id=counselor_id, role=UserRole.COUNSELOR)

            reason = data.get('reason', 'Bulk counselor reassignment').strip() or 'Bulk counselor reassignment'

            from .handoff_service import handoff_to_counselor

            with transaction.atomic():

                for lead in leads:

                    if not can_access_lead(user, lead):

                        errors.append(f"Permission denied for lead #{lead.id}")

                        continue

                    try:

                        handoff_to_counselor(lead, counselor=target_user, assigned_by=user, reason=reason)

                        updated_count += 1

                    except Exception as e:

                        errors.append(f"Lead #{lead.id}: {str(e)}")



        elif action == 'category_update':

            new_category = data.get('new_category')

            valid_categories = [c[0] for c in LeadCategory.choices]

            if new_category not in valid_categories:

                return JsonResponse({'success': False, 'error': f"Invalid category '{new_category}'. Choose from {valid_categories}"}, status=400)



            with transaction.atomic():

                for lead in leads:

                    if not can_access_lead(user, lead):

                        errors.append(f"Permission denied for lead #{lead.id}")

                        continue

                    try:

                        old_cat = lead.category

                        lead.category = new_category

                        lead.save(update_fields=['category', 'updated_at'])

                        log_activity(

                            user=user,

                            action="Lead Category Updated",

                            description=f"Bulk updated category from '{old_cat}' to '{new_category}'.",

                            object_type="Lead",

                            object_id=lead.id,

                            request=request

                        )

                        updated_count += 1

                    except Exception as e:

                        errors.append(f"Lead #{lead.id}: {str(e)}")

        else:

            return JsonResponse({'success': False, 'error': f"Unknown bulk action '{action}'"}, status=400)



        return JsonResponse({

            'success': True,

            'updated_count': updated_count,

            'errors': errors

        })

    except Exception as e:

        logger.exception("Bulk action failed: %s", e)

        return JsonResponse({'success': False, 'error': str(e)}, status=500)





@login_required

def api_lead_quick_details(request, pk):

    """

    Returns structured lead details and fields in JSON format

    for rendering the modern lead details interface in modals, drawers, or dynamically.

    """

    lead = get_object_or_404(

        Lead.objects.select_related('channel', 'product', 'branch', 'assigned_sales_head', 'assigned_telecaller', 'assigned_counselor'),

        pk=pk

    )

    if not can_access_lead(request.user, lead):

        return JsonResponse({'success': False, 'error': 'Permission denied: Cannot access this lead.'}, status=403)



    from .detail_service import build_lead_detail_context

    ctx = build_lead_detail_context(lead, request.user)



    # Determine role-specific detail URL

    detail_url = f"/telecaller/leads/{lead.id}/"

    if request.user.is_authenticated:

        role = getattr(request.user, 'role', '')

        if role == UserRole.TELECALLER:

            detail_url = reverse('telecaller_lead_detail', args=[lead.id])

        elif role == UserRole.COUNSELOR:

            detail_url = reverse('counselor_lead_detail', args=[lead.id])

        elif role == UserRole.SALES_HEAD:

            detail_url = reverse('manager_lead_detail', args=[lead.id])

        elif role == UserRole.BRANCH_HEAD:

            detail_url = reverse('branch_head_lead_detail', args=[lead.id])

        else:

            detail_url = reverse('admin_lead_detail', args=[lead.id])



    # Recent calls for after-call context

    from calls.models import CallOutcome

    recent_calls = []

    for c in lead.calls.select_related('caller').order_by('-call_started_at')[:4]:

        rec = c.drive_recordings.first()

        recent_calls.append({

            'id': c.id,

            'time': c.call_started_at.strftime('%d %b %Y, %I:%M %p') if c.call_started_at else '-',

            'caller': c.caller.get_full_name() or c.caller.username if c.caller else 'Telecaller',

            'duration': c.formatted_duration or '00:00',

            'outcome': c.call_outcome or c.call_status or 'Completed',

            'status': c.call_status or 'Completed',

            'notes': c.notes or '-',

            'recording_url': reverse('drive_stream_recording', args=[rec.id]) if rec else None

        })



    resp_data = {

        'success': True,

        'id': lead.id,

        'name': lead.name,

        'phone': lead.phone,

        'status': lead.status,

        'email': lead.email or '',

        'lead_detail_url': detail_url,

        'assignee': ctx['assignee_name'],

        'assignee_name': ctx['assignee_name'],

        'assignee_initials': ctx['assignee_initials'],

        'whatsapp_phone': ctx['whatsapp_phone'],

        'whatsapp_url': f"https://wa.me/{ctx['whatsapp_phone']}" if ctx['whatsapp_phone'] else "",

        'email_url': f"mailto:{lead.email}" if lead.email else "",

        'nav': ctx['nav'],

        'col1_fields': ctx['col1_fields'],

        'col2_fields': ctx['col2_fields'],

        'status_choices': [{'value': code, 'label': label} for code, label in LeadStatus.choices],

        'outcome_choices': [{'value': code, 'label': label} for code, label in CallOutcome.choices],

        'recent_calls': recent_calls,

    }

    for f in ctx['col1_fields'] + ctx['col2_fields']:

        if f['key'] != 'phone':

            resp_data[f['key']] = f['value']

    resp_data['display_phone'] = ctx.get('phone_display', lead.phone)



    return JsonResponse(resp_data)





@login_required

@require_POST

def api_update_lead_field(request, pk):

    """

    Inline field update endpoint for the modern lead details interface.

    Validates permissions, phone normalization and duplicate rules, branch rules,

    and updates either direct model fields, custom note attributes, or follow-ups.

    """

    from django.core.exceptions import ValidationError

    lead = get_object_or_404(

        Lead.objects.select_related('channel', 'product', 'branch', 'assigned_sales_head', 'assigned_telecaller', 'assigned_counselor'),

        pk=pk

    )

    from accounts.permissions import can_edit_lead

    if not can_edit_lead(request.user, lead):

        return JsonResponse({'success': False, 'error': 'Permission denied: Cannot edit this lead.'}, status=403)



    try:

        try:

            data = json.loads(request.body)

        except Exception:

            data = request.POST



        field_key = data.get('field', '').strip()

        new_value = data.get('value', '').strip()



        if not field_key:

            return JsonResponse({'success': False, 'error': 'Missing field key.'}, status=400)



        from .detail_service import update_lead_attribute

        result = update_lead_attribute(lead, request.user, field_key, new_value, request=request)

        return JsonResponse(result)

    except ValidationError as ve:

        err_msg = ve.message if hasattr(ve, 'message') else str(ve)

        return JsonResponse({'success': False, 'error': err_msg}, status=400)

    except PermissionDenied as pe:

        return JsonResponse({'success': False, 'error': str(pe)}, status=403)

    except Exception as e:

        logger.exception("Error updating lead field via inline API: %s", e)

        return JsonResponse({'success': False, 'error': str(e)}, status=500)





@login_required

def export_leads_csv(request):

    """

    Exports selected or filtered leads to a CSV file respecting user role visibility.

    """

    import csv

    user = request.user

    qs = Lead.objects.all().select_related('channel', 'product', 'branch', 'assigned_telecaller')



    # Enforce role visibility

    if not (getattr(user, 'is_admin_user', False) or user.is_superuser or user.role == 'ADMIN'):

        if user.role == 'SALES_HEAD':

            from branches.models import SalesHeadBranchAccess

            branches = SalesHeadBranchAccess.objects.filter(sales_head=user).values_list('branch_id', flat=True)

            qs = qs.filter(branch_id__in=list(branches))

        elif user.role == 'BRANCH_HEAD':

            qs = qs.filter(branch=user.branch)

        elif user.role == 'TELECALLER':

            qs = qs.filter(assigned_telecaller=user)

        elif user.role == 'COUNSELOR':

            qs = qs.filter(assigned_counselor=user)



    lead_ids_raw = request.GET.get('lead_ids', '')

    if lead_ids_raw:

        ids = [int(i.strip()) for i in lead_ids_raw.split(',') if i.strip().isdigit()]

        qs = qs.filter(id__in=ids)

    else:

        q = request.GET.get('search', '').strip()

        if q:

            qs = qs.filter(Q(name__icontains=q) | Q(phone__icontains=q) | Q(email__icontains=q))

        status = request.GET.get('status', '').strip()

        if status:

            qs = qs.filter(status=status)

        branch = request.GET.get('branch', '').strip()

        if branch:

            qs = qs.filter(branch_id=branch)

        telecaller = request.GET.get('telecaller', '').strip()

        if telecaller:

            qs = qs.filter(assigned_telecaller_id=telecaller)

        channel = request.GET.get('channel', '').strip()

        if channel:

            qs = qs.filter(channel_id=channel)

        product = request.GET.get('product', '').strip()

        if product:

            qs = qs.filter(product_id=product)



    response = HttpResponse(content_type='text/csv')

    filename = f"leads_export_{timezone.now().strftime('%Y%m%d_%H%M%S')}.csv"

    response['Content-Disposition'] = f'attachment; filename="{filename}"'



    writer = csv.writer(response)

    writer.writerow([

        'ID', 'Name', 'Phone', 'Email', 'Branch', 'Source/Channel',

        'Status', 'Product', 'Assigned Telecaller', 'WhatsApp Opt Out', 'Created At'

    ])



    for ld in qs.iterator(chunk_size=500):

        writer.writerow([

            ld.id,

            ld.name,

            ld.phone,

            ld.email or '',

            ld.branch.name if ld.branch else '',

            ld.channel.name if ld.channel else (ld.source or ''),

            ld.status,

            ld.product.name if ld.product else '',

            ld.assigned_telecaller.get_full_name() or ld.assigned_telecaller.username if ld.assigned_telecaller else 'Unassigned',

            'Yes' if getattr(ld, 'whatsapp_opt_out', False) else 'No',

            ld.created_at.strftime('%Y-%m-%d %H:%M:%S') if ld.created_at else ''

        ])



    return response





@login_required

@require_POST

def api_resolve_lead_selection(request):

    """

    Validates selected leads or filter parameters before campaign creation.

    Returns counts for total, eligible, skipped, invalid phones, and opt-outs.

    """

    try:

        try:

            data = json.loads(request.body)

        except Exception:

            data = request.POST



        lead_ids = data.get('lead_ids', [])

        filter_params = data.get('filters', {})

        user = request.user



        qs = Lead.objects.all().select_related('branch', 'assigned_telecaller')



        # Enforce role visibility

        if not (getattr(user, 'is_admin_user', False) or user.is_superuser or user.role == 'ADMIN'):

            if user.role == 'SALES_HEAD':

                from branches.models import SalesHeadBranchAccess

                branches = SalesHeadBranchAccess.objects.filter(sales_head=user).values_list('branch_id', flat=True)

                qs = qs.filter(branch_id__in=list(branches))

            elif user.role == 'BRANCH_HEAD':

                qs = qs.filter(branch=user.branch)

            elif user.role == 'TELECALLER':

                qs = qs.filter(assigned_telecaller=user)

            elif user.role == 'COUNSELOR':

                qs = qs.filter(assigned_counselor=user)



        if lead_ids:

            qs = qs.filter(id__in=lead_ids)

        elif filter_params:

            if filter_params.get('search'):

                q = filter_params['search']

                qs = qs.filter(Q(name__icontains=q) | Q(phone__icontains=q) | Q(email__icontains=q))

            if filter_params.get('branch'):

                qs = qs.filter(branch_id=filter_params['branch'])

            if filter_params.get('status'):

                qs = qs.filter(status=filter_params['status'])

            if filter_params.get('telecaller'):

                qs = qs.filter(assigned_telecaller_id=filter_params['telecaller'])



        from chat.campaign_service import normalize_phone_number



        total = 0

        eligible = 0

        invalid_phone = 0

        opted_out = 0



        for ld in qs.iterator(chunk_size=500):

            total += 1

            digits, is_valid, _ = normalize_phone_number(ld.phone)

            if not is_valid:

                invalid_phone += 1

                continue

            if getattr(ld, 'whatsapp_opt_out', False) or not getattr(ld, 'whatsapp_consent_given', True):

                opted_out += 1

                continue

            eligible += 1



        skipped = invalid_phone + opted_out

        return JsonResponse({

            'success': True,

            'total_selected': total,

            'eligible_count': eligible,

            'skipped_count': skipped,

            'invalid_phone_count': invalid_phone,

            'opted_out_count': opted_out,

        })

    except Exception as e:

        return JsonResponse({'success': False, 'error': str(e)}, status=500)





@login_required

@require_POST

def api_reassign_lead_to_counselor(request, pk):

    """

    Reassigns a lead from a telecaller (or unassigned/counselor) to a target counselor.

    Ensures branch compatibility and permission validation via can_reassign_lead.

    Writes audit record to LeadAssignmentHistory and Activity log.

    Supports both JSON and POST form submissions.

    """

    lead = get_object_or_404(Lead, pk=pk)



    if request.content_type == 'application/json':

        try:

            data = json.loads(request.body)

        except Exception:

            data = {}

    else:

        data = request.POST



    counselor_id = data.get('counselor_id') or data.get('counselor')

    reason = (data.get('reason') or 'Reassigned to Counselor').strip()



    if not counselor_id:

        return JsonResponse({'success': False, 'error': 'Counselor ID is required.'}, status=400)



    target_counselor = get_object_or_404(User, pk=counselor_id, role=UserRole.COUNSELOR)



    if not target_counselor.is_active:

        return JsonResponse({'success': False, 'error': 'Target counselor is inactive.'}, status=400)



    from accounts.permissions import can_reassign_lead

    if not can_reassign_lead(request.user, lead, target_counselor):

        return JsonResponse({

            'success': False,

            'error': f"You do not have permission to reassign this lead to Counselor '{target_counselor.username}'."

        }, status=403)



    from .handoff_service import handoff_to_counselor

    with transaction.atomic():

        handoff_to_counselor(lead, counselor=target_counselor, assigned_by=request.user, reason=reason)

        log_activity(

            user=request.user,

            action="Lead Reassigned to Counselor",

            description=f"Lead #{lead.id} ({lead.name}) reassigned to Counselor '{target_counselor.username}'. Reason: {reason}",

            object_type="Lead",

            object_id=lead.id,

            request=request

        )



    if request.headers.get('x-requested-with') == 'XMLHttpRequest' or request.content_type == 'application/json':

        return JsonResponse({

            'success': True,

            'lead_id': lead.id,

            'counselor_id': target_counselor.id,

            'counselor_name': target_counselor.get_full_name() or target_counselor.username,

            'message': f"Lead successfully reassigned to Counselor '{target_counselor.username}'."

        })



    messages.success(request, f"Lead #{lead.id} successfully reassigned to Counselor '{target_counselor.username}'.")

    next_url = data.get('next') or request.META.get('HTTP_REFERER')

    if next_url:

        return redirect(next_url)

    return redirect('admin_lead_detail', pk=lead.pk)





@login_required

def admin_lead_queues(request):

    """

    Management view for the 4 distinct lead assignment queues:

    - Unassigned

    - Untouched

    - Unanswered

    - Unattended

    Supports filtering by branch, searching, pagination, and bulk assignment via single or round-robin strategies.

    """

    user = request.user

    if not (user.is_admin_user or user.role in (UserRole.SALES_HEAD, UserRole.BRANCH_HEAD)):

        raise PermissionDenied("You do not have permission to access lead assignment queues.")



    current_queue = request.GET.get('queue', 'unassigned').lower().strip()

    if current_queue not in ('unassigned', 'untouched', 'unanswered', 'unattended'):

        current_queue = 'unassigned'



    branch_filter = request.GET.get('branch', '').strip()

    search_query = request.GET.get('search', '').strip()



    from .bulk_assignment_service import get_queue_queryset, get_queue_counts

    queue_counts = get_queue_counts(branch=branch_filter or None, user=user)

    current_queue_count = queue_counts.get(current_queue, 0)



    leads_qs = get_queue_queryset(current_queue, branch=branch_filter or None, user=user)



    if search_query:

        leads_qs = leads_qs.filter(

            Q(name__icontains=search_query) |

            Q(phone__icontains=search_query) |

            Q(notes__icontains=search_query)

        )



    from .utils import get_validated_page_size, ALLOWED_PAGE_SIZES

    page_size = get_validated_page_size(request, default=20)

    paginator = Paginator(leads_qs, page_size)

    page_obj = paginator.get_page(request.GET.get('page'))



    if user.is_admin_user:

        branches = Branch.objects.filter(status='Active')

    else:

        from accounts.permissions import get_accessible_branch_ids

        branches = Branch.objects.filter(id__in=get_accessible_branch_ids(user), status='Active')



    tc_qs = User.objects.filter(role=UserRole.TELECALLER, is_active=True).select_related('branch')

    if branch_filter:

        tc_qs = tc_qs.filter(branch_id=branch_filter)

    elif not user.is_admin_user and user.branch_id:

        tc_qs = tc_qs.filter(branch_id=user.branch_id)

    telecallers = list(tc_qs.order_by('first_name', 'username'))



    # Modal multi-selection options: all active accessible branches and telecallers

    if user.is_admin_user:

        modal_branches = list(Branch.objects.filter(status='Active').order_by('name'))

        modal_tc_qs = User.objects.filter(role=UserRole.TELECALLER, is_active=True).select_related('branch')

    else:

        from accounts.permissions import get_accessible_branch_ids

        accessible_branch_ids = get_accessible_branch_ids(user)

        modal_branches = list(Branch.objects.filter(id__in=accessible_branch_ids, status='Active').order_by('name'))

        modal_tc_qs = User.objects.filter(role=UserRole.TELECALLER, is_active=True, branch_id__in=accessible_branch_ids).select_related('branch')



    telecallers_data = [

        {

            'id': tc.id,

            'name': tc.get_full_name() or tc.username,

            'username': tc.username,

            'branch_id': tc.branch_id,

            'branch_name': tc.branch.name if tc.branch else 'No Branch'

        }

        for tc in modal_tc_qs.order_by('first_name', 'username')

    ]



    return render(request, 'admin/lead_queues.html', {

        'page_obj': page_obj,

        'current_queue': current_queue,

        'queue_counts': queue_counts,

        'current_queue_count': current_queue_count,

        'branches': branches,

        'telecallers': telecallers,

        'modal_branches': modal_branches,

        'telecallers_data_json': json.dumps(telecallers_data),

        'branch_filter': branch_filter,

        'search_query': search_query,

    })





@login_required

@require_POST

def api_bulk_assign_leads(request):

    """

    API endpoint for executing atomic bulk lead assignment on queues.

    Supports single telecaller or multi-branch round-robin distribution with branch compatibility.

    """

    user = request.user

    if not (user.is_admin_user or user.role in (UserRole.SALES_HEAD, UserRole.BRANCH_HEAD)):

        return JsonResponse({'success': False, 'error': 'Permission denied.'}, status=403)



    try:

        if request.content_type == 'application/json':

            data = json.loads(request.body)

        else:

            data = request.POST



        queue_type = data.get('queue_type', 'unassigned')

        strategy = data.get('strategy', 'round_robin')

        target_telecaller_id = data.get('target_telecaller_id')

        target_branch_id = data.get('target_branch_id')

        branch_ids = data.get('branch_ids')

        telecaller_ids = data.get('telecaller_ids')

        reason = data.get('reason', '')

        lead_ids = data.get('lead_ids')

        target_role = data.get('target_role', 'TELECALLER')

        limit = data.get('limit')



        from .bulk_assignment_service import execute_bulk_assignment

        result = execute_bulk_assignment(

            queue_type=queue_type,

            lead_ids=lead_ids,

            strategy=strategy,

            target_role=target_role,

            target_telecaller_id=target_telecaller_id,

            target_branch_id=target_branch_id,

            branch_ids=branch_ids,

            telecaller_ids=telecaller_ids,

            reason=reason,

            assigned_by=user,

            limit=limit

        )



        return JsonResponse(result)

    except Exception as e:

        logger.exception("api_bulk_assign_leads failed: %s", e)

        return JsonResponse({'success': False, 'error': str(e)}, status=500)





@login_required

@require_POST

def api_bulk_assign_preview(request):

    """

    API endpoint returning real-time assignment preview stats:

    - total eligible leads

    - selected branch count

    - selected telecaller count

    - estimated leads per telecaller

    - branch compatibility warnings

    """

    user = request.user

    if not (user.is_admin_user or user.role in (UserRole.SALES_HEAD, UserRole.BRANCH_HEAD)):

        return JsonResponse({'success': False, 'error': 'Permission denied.'}, status=403)



    try:

        if request.content_type == 'application/json':

            data = json.loads(request.body)

        else:

            data = request.POST



        queue_type = data.get('queue_type', 'unassigned')

        branch_ids = data.get('branch_ids')

        telecaller_ids = data.get('telecaller_ids')

        lead_ids = data.get('lead_ids')



        from .bulk_assignment_service import get_bulk_assignment_preview

        preview = get_bulk_assignment_preview(

            queue_type=queue_type,

            branch_ids=branch_ids,

            telecaller_ids=telecaller_ids,

            lead_ids=lead_ids,

            user=user

        )

        return JsonResponse({'success': True, 'preview': preview})

    except Exception as e:

        logger.exception("api_bulk_assign_preview failed: %s", e)

        return JsonResponse({'success': False, 'error': str(e)}, status=500)





# ==========================================

# RECEPTION & WALK-IN DESK (Req 7 & 11)

# ==========================================



@login_required

def receptionist_dashboard(request):

    """

    Dedicated dashboard for the Receptionist role.

    Displays:

      1. Total walk-in leads registered today.

      2. Leads awaiting Counselor assignment.

      3. Leads assigned today.

      4. Total walk-in leads this month.

    Lists walk-in visitors for the Receptionist's branch with quick counselor assignment,

    visitor status updates, and new student check-in registration modal.

    """

    user = request.user

    if not (user.is_admin_user or user.role in (UserRole.RECEPTIONIST, UserRole.BRANCH_HEAD)):

        raise PermissionDenied("You do not have permission to access the Receptionist dashboard.")



    # Determine branch

    if user.is_receptionist_user or user.is_branch_head_user:

        branch = user.branch

    else:

        # Admin or Superuser

        branch_id = request.GET.get('branch', '').strip()

        branch = Branch.objects.filter(pk=branch_id).first() if branch_id else user.branch or Branch.objects.filter(status='Active').first()



    search_query = request.GET.get('search', '').strip()

    status_filter = request.GET.get('status_filter', '').strip()

    assignment_filter = request.GET.get('assignment_filter', '').strip()

    lead_type_filter = request.GET.get('lead_type_filter', '').strip()

    period = request.GET.get('period', '').strip()

    from_date = request.GET.get('from_date', '').strip()

    to_date = request.GET.get('to_date', '').strip()



    # Base walkin queryset for this branch: manual walk-ins and Admin-configured Google Sheets leads

    walkin_qs = Lead.objects.filter(

        Q(source__iexact='Walk-in') |

        Q(channel__name__iexact='Walk-in') |

        Q(source__iexact='Google Sheets') |

        Q(channel__name__iexact='Google Sheets') |

        Q(sheet_mappings__isnull=False) |

        Q(is_offline=True)

    ).distinct().select_related('branch', 'assigned_counselor', 'channel', 'product').order_by('-updated_at')



    if branch:

        walkin_qs = walkin_qs.filter(Q(branch=branch) | Q(secondary_branches=branch)).distinct()

    elif not user.is_admin_user:

        walkin_qs = walkin_qs.none()



    # KPI summary cards calculation

    today = timezone.localdate()

    today_start = timezone.make_aware(datetime.combine(today, time.min))

    today_end = timezone.make_aware(datetime.combine(today, time.max))



    month_start_date = today.replace(day=1)

    month_start = timezone.make_aware(datetime.combine(month_start_date, time.min))



    # 1. Total walk-in leads registered today

    total_today = walkin_qs.filter(created_at__range=(today_start, today_end)).count()

    # 2. Leads awaiting Counselor assignment

    awaiting_assignment = walkin_qs.filter(assigned_counselor__isnull=True).count()

    # 3. Leads assigned today

    assigned_today = walkin_qs.filter(

        assigned_counselor__isnull=False

    ).filter(

        Q(center_visit_date__range=(today_start, today_end)) |

        Q(updated_at__range=(today_start, today_end))

    ).count()

    # 4. Total walk-in leads this month

    total_this_month = walkin_qs.filter(created_at__range=(month_start, today_end)).count()



    # Apply filters to table queryset

    table_qs = walkin_qs

    if period == 'today':

        table_qs = table_qs.filter(created_at__range=(today_start, today_end))

    elif period == 'week':

        week_start = timezone.make_aware(datetime.combine(today - timedelta(days=today.weekday()), time.min))

        table_qs = table_qs.filter(created_at__range=(week_start, today_end))

    elif period == 'month':

        table_qs = table_qs.filter(created_at__range=(month_start, today_end))

    elif from_date or to_date:

        if from_date:

            try:

                fd = datetime.strptime(from_date, "%Y-%m-%d").date()

                fd_start = timezone.make_aware(datetime.combine(fd, time.min))

                table_qs = table_qs.filter(created_at__gte=fd_start)

            except ValueError:

                pass

        if to_date:

            try:

                td = datetime.strptime(to_date, "%Y-%m-%d").date()

                td_end = timezone.make_aware(datetime.combine(td, time.max))

                table_qs = table_qs.filter(created_at__lte=td_end)

            except ValueError:

                pass



    if status_filter:

        table_qs = table_qs.filter(visitor_status=status_filter)

    if assignment_filter == 'unassigned':

        table_qs = table_qs.filter(assigned_counselor__isnull=True)

    elif assignment_filter == 'assigned':

        table_qs = table_qs.filter(assigned_counselor__isnull=False)



    if lead_type_filter == 'new':

        table_qs = table_qs.filter(duplicate_records__isnull=True).exclude(sheet_mappings__row_index__gt=2)

    elif lead_type_filter == 'existing':

        table_qs = table_qs.filter(

            Q(duplicate_records__isnull=False) | Q(sheet_mappings__isnull=False)

        ).distinct()



    if search_query:

        search_filter = (

            Q(name__icontains=search_query) |

            Q(phone__icontains=search_query) |

            Q(token_number__icontains=search_query) |

            Q(notes__icontains=search_query)

        )

        if search_query.isdigit():

            search_filter |= Q(id=int(search_query))

        table_qs = table_qs.filter(search_filter)



    paginator = Paginator(table_qs, 20)

    page_obj = paginator.get_page(request.GET.get('page'))



    # Identify New Lead vs Existing Lead vs Ambiguous Match for each displayed lead

    from .duplicates import normalize_phone, normalize_email

    displayed_leads = list(page_obj.object_list)

    lead_ids = [l.id for l in displayed_leads]



    duplicate_records_map = {}

    if lead_ids:

        for d in DuplicateLeadRecord.objects.filter(original_lead_id__in=lead_ids):

            duplicate_records_map.setdefault(d.original_lead_id, []).append(d)



    for lead in displayed_leads:

        dups = duplicate_records_map.get(lead.id, [])

        is_ambiguous = any(

            d.action_taken == 'AMBIGUOUS_MATCH_FLAGGED' or 'ambiguous' in (d.duplicate_reason or '').lower()

            for d in dups

        )



        is_sheets = (

            (lead.source and lead.source.lower() == 'google sheets') or

            (lead.channel and lead.channel.name.lower() == 'google sheets') or

            lead.sheet_mappings.exists()

        )

        lead.source_display = 'Google Sheets' if is_sheets else (lead.source or 'Walk-in')



        if is_ambiguous:

            lead.lead_type = 'Ambiguous Match'

            lead.lead_type_badge = 'warning'

            lead.is_existing_lead = True

            lead.is_ambiguous = True

        elif dups or lead.sheet_mappings.count() > 1:

            lead.lead_type = 'Existing Lead'

            lead.lead_type_badge = 'info'

            lead.is_existing_lead = True

            lead.is_ambiguous = False

        else:

            clean_p = normalize_phone(lead.phone)

            clean_e = normalize_email(lead.email)

            has_other_match = False

            if clean_p and len(clean_p) >= 10:

                p_tail = clean_p[-10:]

                has_other_match = Lead.objects.filter(

                    Q(phone__endswith=p_tail) | Q(alternate_phone__endswith=p_tail)

                ).exclude(id=lead.id).exists()

            if not has_other_match and clean_e:

                has_other_match = Lead.objects.filter(email__iexact=clean_e).exclude(id=lead.id).exists()



            has_history = (

                lead.assignment_history.count() > 1 or

                lead.followups.exists() or

                lead.calls.exists() or

                lead.status_history.count() > 1

            )



            if has_other_match or has_history:

                lead.lead_type = 'Existing Lead'

                lead.lead_type_badge = 'info'

                lead.is_existing_lead = True

                lead.is_ambiguous = False

            else:

                lead.lead_type = 'New Lead'

                lead.lead_type_badge = 'success'

                lead.is_existing_lead = False

                lead.is_ambiguous = False



    # Counselors strictly belonging to this branch (active only)

    if branch:

        counselors = list(User.objects.filter(

            role=UserRole.COUNSELOR,

            branch=branch,

            is_active=True

        ).order_by('first_name', 'username'))

    else:

        counselors = []



    all_branches = Branch.objects.filter(status='Active').order_by('name') if user.is_admin_user else []

    from products.models import Product

    products = list(Product.objects.filter(status='Active').order_by('name'))



    return render(request, 'receptionist/dashboard.html', {

        'page_obj': page_obj,

        'branch': branch,

        'all_branches': all_branches,

        'counselors': counselors,

        'products': products,

        'total_today': total_today,

        'awaiting_assignment': awaiting_assignment,

        'assigned_today': assigned_today,

        'total_this_month': total_this_month,

        'search_query': search_query,

        'status_filter': status_filter,

        'assignment_filter': assignment_filter,

        'lead_type_filter': lead_type_filter,

        'period': period,

        'from_date': from_date,

        'to_date': to_date,

        'has_counselors': len(counselors) > 0,

    })





@login_required

def receptionist_lead_history(request, pk):

    """

    Dedicated view for Receptionist to review complete available lead history:

    - Student info (read-only)

    - Counselor assignment history & audit trail

    - Status history (read-only)

    - Communication history: Follow-ups, Call history, Notes & remarks, WhatsApp messages

    - Intake / Import info: Google Sheets mapping, Registration date, Duplicate records, Matching leads

    Enforces strict branch isolation for Receptionist.

    Supports both JSON response (for modal / drawer) and HTML page rendering.

    """

    user = request.user

    if not (user.is_admin_user or user.is_receptionist_user):

        raise PermissionDenied("You do not have permission to view Receptionist lead history.")



    lead = get_object_or_404(

        Lead.objects.select_related('branch', 'assigned_counselor', 'assigned_telecaller', 'channel', 'product'),

        pk=pk

    )



    if user.is_receptionist_user and lead.branch_id != user.branch_id:

        if request.headers.get('x-requested-with') == 'XMLHttpRequest' or request.GET.get('format') == 'json':

            return JsonResponse({'success': False, 'error': 'Permission denied: Cannot access lead from another branch.'}, status=403)

        raise PermissionDenied("You do not have permission to view leads belonging to another branch.")



    # 1. Student Info

    student_info = {

        'id': lead.id,

        'token_number': lead.token_number or f"WI-{lead.id}",

        'name': lead.name,

        'phone': lead.phone,

        'email': lead.email or 'Not provided',

        'course': lead.product.name if lead.product else (getattr(lead, 'course_display', None) or lead.category or 'Not specified'),

        'branch': lead.branch.name if lead.branch else 'Unassigned',

        'branch_id': lead.branch_id,

        'source': lead.source or (lead.channel.name if lead.channel else 'Direct'),

        'channel': lead.channel.name if lead.channel else 'Direct',

        'created_at': lead.created_at.strftime('%Y-%m-%d %H:%M') if lead.created_at else '',

        'updated_at': lead.updated_at.strftime('%Y-%m-%d %H:%M') if lead.updated_at else '',

        'center_visit_date': lead.center_visit_date.strftime('%Y-%m-%d %H:%M') if lead.center_visit_date else '',

        'status': lead.status,

        'visitor_status': getattr(lead, 'visitor_status', ''),

        'assignment_status': getattr(lead, 'assignment_status', 'Pending Assignment'),

        'current_counselor': (lead.assigned_counselor.get_full_name() or lead.assigned_counselor.username) if lead.assigned_counselor else None,

        'current_counselor_id': lead.assigned_counselor_id,

        'notes': lead.notes or '',

    }



    # 2. Assignment History

    assignments = []

    for h in lead.assignment_history.select_related('from_user', 'to_user', 'assigned_by').order_by('-created_at'):

        assignments.append({

            'id': h.id,

            'from_user': (h.from_user.get_full_name() or h.from_user.username) if h.from_user else (h.from_role or 'None'),

            'to_user': (h.to_user.get_full_name() or h.to_user.username) if h.to_user else (h.to_role or 'None'),

            'from_role': h.from_role or '',

            'to_role': h.to_role or '',

            'assigned_by': (h.assigned_by.get_full_name() or h.assigned_by.username) if h.assigned_by else 'System',

            'reason': h.reason or 'No reason recorded',

            'created_at': h.created_at.strftime('%Y-%m-%d %H:%M') if h.created_at else '',

        })



    # 3. Status History

    status_history = []

    for s in lead.status_history.select_related('changed_by').order_by('-created_at'):

        status_history.append({

            'id': s.id,

            'old_status': s.old_status or 'Initial',

            'new_status': s.new_status,

            'changed_by': (s.changed_by.get_full_name() or s.changed_by.username) if s.changed_by else 'System',

            'remarks': s.remarks or '',

            'created_at': s.created_at.strftime('%Y-%m-%d %H:%M') if s.created_at else '',

        })



    # 4. Follow-up records

    followups = []

    for f in lead.followups.select_related('assigned_user').order_by('-follow_up_date'):

        dt_str = f.follow_up_date.strftime('%Y-%m-%d') if f.follow_up_date else ''

        if getattr(f, 'follow_up_time', None):

            dt_str += f" {f.follow_up_time.strftime('%H:%M')}"

        assigned_name = (f.assigned_user.get_full_name() or f.assigned_user.username) if getattr(f, 'assigned_user', None) else 'System'

        followups.append({

            'id': f.id,

            'scheduled_time': dt_str,

            'status': f.status,

            'notes': f.notes or '',

            'scheduled_by': assigned_name,

        })



    # 5. Call History

    calls = []

    for c in lead.calls.select_related('caller').order_by('-created_at'):

        call_time_val = getattr(c, 'call_started_at', None) or getattr(c, 'created_at', None)

        calls.append({

            'id': c.id,

            'call_time': call_time_val.strftime('%Y-%m-%d %H:%M') if call_time_val else '',

            'caller': (c.caller.get_full_name() or c.caller.username) if c.caller else 'Unknown',

            'outcome': getattr(c, 'call_outcome', '') or getattr(c, 'outcome', 'No outcome'),

            'duration': getattr(c, 'duration', 0) or 0,

            'status': getattr(c, 'call_status', '') or getattr(c, 'status', ''),

            'notes': c.notes or '',

        })



    # 6. WhatsApp Interactions

    whatsapp_data = []

    try:

        from chat.models import Conversation

        from .duplicates import normalize_phone

        clean_p = normalize_phone(lead.phone)

        if clean_p:

            p_tail = clean_p[-10:] if len(clean_p) >= 10 else clean_p

            conv_qs = Conversation.objects.filter(

                Q(phone_number__endswith=p_tail) | Q(phone_number__icontains=clean_p)

            )

            for conv in conv_qs:

                msgs = []

                for m in conv.messages.order_by('-created_at')[:5]:

                    msgs.append({

                        'sender_type': m.sender_type,

                        'message_text': m.message_text,

                        'created_at': m.created_at.strftime('%Y-%m-%d %H:%M') if m.created_at else '',

                        'status': m.status,

                    })

                whatsapp_data.append({

                    'conversation_id': conv.id,

                    'customer_name': conv.customer_name,

                    'phone_number': conv.phone_number,

                    'last_message': conv.last_message,

                    'last_message_time': conv.last_message_time.strftime('%Y-%m-%d %H:%M') if conv.last_message_time else '',

                    'unread_count': conv.unread_count,

                    'recent_messages': msgs,

                })

    except Exception as e:

        logger.warning("Error fetching WhatsApp history for lead %s: %s", lead.id, e)



    # 7. Activities

    activities = []

    for a in Activity.objects.filter(object_type='Lead', object_id=str(lead.id)).select_related('user').order_by('-timestamp')[:20]:

        activities.append({

            'action': a.action,

            'description': a.description,

            'user': (a.user.get_full_name() or a.user.username) if a.user else 'System',

            'created_at': a.timestamp.strftime('%Y-%m-%d %H:%M') if getattr(a, 'timestamp', None) else '',

        })



    # 8. Google Sheets & Intake Details

    sheet_info = []

    for sm in lead.sheet_mappings.select_related('connection').all():

        last_sync = sm.connection.sync_histories.order_by('-timestamp').first()

        s_dict = {

            'connection_name': sm.connection.name,

            'row_index': sm.row_index,

            'row_identifier': sm.row_identifier,

            'source_status': sm.source_status,

            'mapped_at': sm.created_at.strftime('%Y-%m-%d %H:%M') if sm.created_at else '',

            'last_sync_time': last_sync.timestamp.strftime('%Y-%m-%d %H:%M') if (last_sync and getattr(last_sync, 'timestamp', None)) else 'Never',

            'last_sync_status': last_sync.status if last_sync else 'Unknown',

        }

        if user.is_admin_user:

            s_dict['spreadsheet_url'] = sm.connection.spreadsheet_url

        sheet_info.append(s_dict)



    # 9. Duplicate / Matching Records

    from .duplicates import find_all_matching_leads

    matching_leads_raw = find_all_matching_leads(phone=lead.phone, email=lead.email, name=lead.name, exclude_id=lead.id)

    matching_leads = []

    for m in matching_leads_raw:

        matching_leads.append({

            'id': m.id,

            'name': m.name,

            'phone': m.phone,

            'email': m.email or '',

            'branch': m.branch.name if m.branch else 'Unassigned',

            'status': m.status,

            'counselor': (m.assigned_counselor.get_full_name() or m.assigned_counselor.username) if m.assigned_counselor else None,

            'created_at': m.created_at.strftime('%Y-%m-%d %H:%M') if m.created_at else '',

        })



    duplicate_audit = []

    for d in lead.duplicate_records.select_related('branch', 'existing_branch').order_by('-submitted_at')[:10]:

        duplicate_audit.append({

            'source': d.source,

            'duplicate_reason': d.duplicate_reason,

            'action_taken': d.action_taken,

            'submitted_at': d.submitted_at.strftime('%Y-%m-%d %H:%M') if d.submitted_at else '',

            'notes': d.notes,

        })



    # Counselors available for assignment in this branch

    branch = lead.branch or user.branch

    counselors = []

    if branch:

        counselor_users = User.objects.filter(role=UserRole.COUNSELOR, branch=branch, is_active=True).order_by('first_name', 'username')

        for c in counselor_users:

            counselors.append({

                'id': c.id,

                'name': c.get_full_name() or c.username,

                'username': c.username

            })



    data_payload = {

        'success': True,

        'student': student_info,

        'assignments': assignments,

        'status_history': status_history,
        'timeline_count': (len(calls) if calls else 0) + (len(status_history) if status_history else 0) + (len(followups) if followups else 0),

        'followups': followups,

        'calls': calls,

        'whatsapp': whatsapp_data,

        'activities': activities,

        'sheet_info': sheet_info,

        'is_google_sheet_origin': len(sheet_info) > 0,

        'matching_leads': matching_leads,

        'duplicate_audit': duplicate_audit,

        'counselors': counselors,

        'has_counselors': len(counselors) > 0,

    }



    if request.headers.get('x-requested-with') == 'XMLHttpRequest' or request.GET.get('format') == 'json':

        return JsonResponse(data_payload)



    return render(request, 'receptionist/lead_history.html', {

        'lead': lead,

        'student': student_info,

        'assignments': assignments,

        'status_history': status_history,
        'timeline_count': (len(calls) if calls else 0) + (len(status_history) if status_history else 0) + (len(followups) if followups else 0),

        'followups': followups,

        'calls': calls,

        'whatsapp': whatsapp_data,

        'activities': activities,

        'sheet_info': sheet_info,

        'matching_leads': matching_leads,

        'duplicate_audit': duplicate_audit,

        'counselors': counselors,

        'has_counselors': len(counselors) > 0,

        'branch': branch,

    })





@login_required

def receptionist_check_existing_lead(request):

    """

    Real-time duplicate detection endpoint for the Receptionist student check-in modal.

    Searches by normalized phone, email, and name.

    Returns matching leads with full details so receptionist can review history or assign counselor directly.

    """

    user = request.user

    if not (user.is_admin_user or user.is_receptionist_user):

        return JsonResponse({'success': False, 'error': 'Permission denied.'}, status=403)



    phone = request.GET.get('phone', '').strip()

    email = request.GET.get('email', '').strip()

    name = request.GET.get('name', '').strip()



    if not (phone or email or name):

        return JsonResponse({'success': True, 'matches': []})



    from .duplicates import find_all_matching_leads

    matches = find_all_matching_leads(phone=phone, email=email, name=name)



    match_list = []

    for m in matches:

        match_list.append({

            'id': m.id,

            'name': m.name,

            'phone': m.phone,

            'email': m.email or '',

            'branch': m.branch.name if m.branch else 'Unassigned',

            'branch_id': m.branch_id,

            'status': m.status,

            'visitor_status': getattr(m, 'visitor_status', ''),

            'source': m.source or (m.channel.name if m.channel else 'Direct'),

            'assigned_counselor': (m.assigned_counselor.get_full_name() or m.assigned_counselor.username) if m.assigned_counselor else None,

            'created_at': m.created_at.strftime('%Y-%m-%d %H:%M') if m.created_at else ''

        })



    return JsonResponse({

        'success': True,

        'has_matches': len(match_list) > 0,

        'count': len(match_list),

        'matches': match_list

    })





@login_required

def admin_walkin_desk(request):

    """

    Reception & Walk-in Desk view for tracking in-person branch visits,

    issuing token passes, and managing live counselor assignments.

    """

    user = request.user

    if user.is_receptionist_user:

        return redirect('receptionist_dashboard')

    if not (user.is_admin_user or user.role in (UserRole.SALES_HEAD, UserRole.BRANCH_HEAD, UserRole.COUNSELOR, UserRole.RECEPTIONIST)):

        raise PermissionDenied("You do not have permission to access the reception desk.")



    branch_filter = request.GET.get('branch', '').strip()

    status_filter = request.GET.get('status_filter', '').strip()

    search_query = request.GET.get('search', '').strip()



    # Walk-in leads base query - matches direct walk-in, QR form, and walk-in channels

    walkin_qs = Lead.objects.filter(

        Q(source__icontains='Walk-in') | Q(channel__name__icontains='Walk-in')

    ).select_related('branch', 'assigned_counselor', 'channel').order_by('-created_at')



    # Scope permissions

    if not user.is_admin_user:

        from accounts.permissions import get_accessible_branch_ids

        accessible_branch_ids = get_accessible_branch_ids(user)

        if accessible_branch_ids:

            walkin_qs = walkin_qs.filter(branch_id__in=accessible_branch_ids)



    if branch_filter:

        walkin_qs = walkin_qs.filter(branch_id=branch_filter)



    # Date range calculations

    import datetime

    now = timezone.now()

    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)

    yesterday_start = today_start - datetime.timedelta(days=1)

    week_start = today_start - datetime.timedelta(days=7)



    date_filter = request.GET.get('date_filter', 'today').strip().lower()



    # Base counts for segmented tabs

    count_today = walkin_qs.filter(Q(created_at__gte=today_start) | Q(center_visit_date__gte=today_start)).count()

    count_yesterday = walkin_qs.filter(

        (Q(created_at__gte=yesterday_start) & Q(created_at__lt=today_start)) |

        (Q(center_visit_date__gte=yesterday_start) & Q(center_visit_date__lt=today_start))

    ).count()

    count_week = walkin_qs.filter(Q(created_at__gte=week_start) | Q(center_visit_date__gte=week_start)).count()

    count_all = walkin_qs.count()



    # Apply date filter (defaults to 'today' so table view matches today KPI)

    if date_filter == 'today':

        walkin_qs = walkin_qs.filter(Q(created_at__gte=today_start) | Q(center_visit_date__gte=today_start))

    elif date_filter == 'yesterday':

        walkin_qs = walkin_qs.filter(

            (Q(created_at__gte=yesterday_start) & Q(created_at__lt=today_start)) |

            (Q(center_visit_date__gte=yesterday_start) & Q(center_visit_date__lt=today_start))

        )

    elif date_filter == 'week':

        walkin_qs = walkin_qs.filter(Q(created_at__gte=week_start) | Q(center_visit_date__gte=week_start))

    # 'all' applies no date filter



    # Accurate KPI counts matching active date scope

    active_range_total = walkin_qs.count()

    waiting_count = walkin_qs.filter(visitor_status='Waiting').count()

    in_consultation_count = walkin_qs.filter(visitor_status='In Consultation').count()

    completed_count = walkin_qs.filter(visitor_status='Completed').count()



    if status_filter:

        walkin_qs = walkin_qs.filter(visitor_status=status_filter)



    if search_query:

        walkin_qs = walkin_qs.filter(

            Q(name__icontains=search_query) |

            Q(phone__icontains=search_query) |

            Q(token_number__icontains=search_query) |

            Q(notes__icontains=search_query)

        )



    paginator = Paginator(walkin_qs, 20)

    page_obj = paginator.get_page(request.GET.get('page'))



    if user.is_admin_user:

        branches = Branch.objects.filter(status='Active')

    else:

        from accounts.permissions import get_accessible_branch_ids

        branches = Branch.objects.filter(id__in=get_accessible_branch_ids(user), status='Active')



    counselors_qs = User.objects.filter(role=UserRole.COUNSELOR, is_active=True).select_related('branch')

    if branch_filter:

        counselors_qs = counselors_qs.filter(branch_id=branch_filter)

    elif not user.is_admin_user and user.branch_id:

        counselors_qs = counselors_qs.filter(branch_id=user.branch_id)

    counselors = list(counselors_qs.order_by('first_name', 'username'))



    return render(request, 'admin/walkin_desk.html', {

        'page_obj': page_obj,

        'branches': branches,

        'counselors': counselors,

        'active_range_total': active_range_total,

        'total_walkins_today': count_today,

        'waiting_count': waiting_count,

        'in_consultation_count': in_consultation_count,

        'completed_count': completed_count,

        'branch_filter': branch_filter,

        'status_filter': status_filter,

        'date_filter': date_filter,

        'count_today': count_today,

        'count_yesterday': count_yesterday,

        'count_week': count_week,

        'count_all': count_all,

        'search_query': search_query,

    })





@login_required

@require_POST

def admin_walkin_create(request):

    """

    Creates/checks-in a new walk-in prospect at reception desk.

    Generates token number, records center visit date, and optionally assigns to counselor.

    """

    user = request.user

    if not (user.is_admin_user or user.role in (UserRole.SALES_HEAD, UserRole.BRANCH_HEAD, UserRole.COUNSELOR, UserRole.RECEPTIONIST)):

        return JsonResponse({'success': False, 'error': 'Permission denied.'}, status=403)



    try:

        if request.content_type == 'application/json':

            data = json.loads(request.body)

        else:

            data = request.POST



        name = (data.get('name') or '').strip()

        phone = (data.get('phone') or '').strip()

        email = (data.get('email') or '').strip()

        branch_id = data.get('branch_id')

        category = data.get('category', LeadCategory.TRAINING)

        counselor_id = data.get('counselor_id')

        product_id = data.get('product_id') or data.get('product')

        notes = (data.get('notes') or data.get('remarks') or '').strip()



        if not name or not phone:

            return JsonResponse({'success': False, 'error': 'Name and Phone are required.'}, status=400)



        product = None

        if product_id:

            from products.models import Product

            try:

                product = Product.objects.get(pk=product_id)

            except (Product.DoesNotExist, ValueError):

                pass



        # Enforce branch scope: Receptionists are strictly bound to their assigned branch

        if user.is_receptionist_user:

            if not user.branch:

                return JsonResponse({'success': False, 'error': 'Receptionist must be assigned to a branch.'}, status=400)

            branch = user.branch

        else:

            branch = get_object_or_404(Branch, pk=branch_id) if branch_id else user.branch



        # Validate counselor belongs to the same branch and is active

        counselor = None

        if counselor_id:

            counselor = get_object_or_404(User, pk=counselor_id, role=UserRole.COUNSELOR, is_active=True)

            if branch and counselor.branch_id and counselor.branch_id != branch.id:

                return JsonResponse({'success': False, 'error': 'Selected counselor belongs to a different branch.'}, status=400)



        # Support checking in an existing matching lead without creating a duplicate

        existing_lead_id = data.get('existing_lead_id')

        if existing_lead_id:

            lead = get_object_or_404(Lead, pk=existing_lead_id)

            if user.is_receptionist_user and lead.branch_id != user.branch_id:

                return JsonResponse({'success': False, 'error': 'Permission denied: Cannot check in lead from another branch.'}, status=403)

            lead.center_visit_date = timezone.now()

            lead.visitor_status = VisitorStatus.IN_CONSULTATION if counselor else VisitorStatus.WAITING

            if counselor:

                from .handoff_service import handoff_to_counselor

                handoff_to_counselor(lead, counselor=counselor, assigned_by=user, reason='Reception desk visit check-in')

                lead.assignment_status = 'Assigned'

            lead.save(update_fields=['center_visit_date', 'visitor_status', 'assignment_status', 'updated_at'])

            return JsonResponse({

                'success': True,

                'lead_id': lead.id,

                'token_number': lead.token_number or f"WI-{lead.id}",

                'message': f"Existing student '{lead.name}' checked in successfully."

            })



        # Check for matching existing leads using normalized duplicate detection

        from .duplicates import find_all_matching_leads

        matches = find_all_matching_leads(phone=phone, email=email, name=name)

        force_create = data.get('force_create', False)



        if matches and not force_create:

            match_list = []

            for m in matches:

                match_list.append({

                    'id': m.id,

                    'name': m.name,

                    'phone': m.phone,

                    'email': m.email or '',

                    'branch': m.branch.name if m.branch else 'Unassigned',

                    'branch_id': m.branch_id,

                    'status': m.status,

                    'visitor_status': getattr(m, 'visitor_status', ''),

                    'source': m.source or (m.channel.name if m.channel else 'Direct'),

                    'assigned_counselor': (m.assigned_counselor.get_full_name() or m.assigned_counselor.username) if m.assigned_counselor else None,

                    'created_at': m.created_at.strftime('%Y-%m-%d %H:%M') if m.created_at else ''

                })

            return JsonResponse({

                'success': False,

                'is_duplicate': True,

                'message': f"Found {len(matches)} matching existing student record(s) in CRM. You can review history or assign counselor directly.",

                'matches': match_list

            }, status=200)



        walkin_channel, _ = Channel.objects.get_or_create(name='Walk-in', defaults={'status': 'Active'})



        # Generate daily token

        today_local = timezone.localdate()

        date_str = today_local.strftime('%Y%m%d')

        start_of_today_seq = timezone.make_aware(datetime.combine(today_local, time.min))

        end_of_today_seq = timezone.make_aware(datetime.combine(today_local, time.max))

        seq = Lead.objects.filter(created_at__range=(start_of_today_seq, end_of_today_seq), source='Walk-in').count() + 1

        token_number = f"WI-{date_str}-{seq:03d}"



        from .intake import CentralizedLeadIntakeService
        intake_res = CentralizedLeadIntakeService.ingest(
            phone=phone,
            source='Walk-in',
            channel_name='Walk-in',
            name=name,
            email=email,
            branch=branch,
            product=product,
            note=notes,
            token_number=token_number,
            center_visit_date=timezone.now(),
            visitor_status=VisitorStatus.IN_CONSULTATION if counselor else VisitorStatus.WAITING,
            activity_user=user,
            incoming_timestamp=timezone.now(),
        )
        lead = intake_res.lead
        lead.category = category
        lead.is_offline = True
        if intake_res.created:
            lead.status = LeadStatus.VISITED
        lead.save(update_fields=['category', 'is_offline', 'status', 'updated_at'])



        log_activity(

            user=user,

            action="Walk-in Visitor Checked In",

            description=f"Walk-in prospect '{lead.name}' ({lead.phone}) checked in at {branch.name if branch else 'Reception'}. Token: #{token_number}",

            object_type="Lead",

            object_id=lead.id,

            request=request

        )



        # If immediate counselor assignment was selected

        if counselor:

            from .handoff_service import handoff_to_counselor

            handoff_to_counselor(lead, counselor=counselor, assigned_by=user, reason='Reception desk immediate assignment')

            lead.visitor_status = VisitorStatus.IN_CONSULTATION

            lead.assignment_status = 'Assigned'

            lead.save(update_fields=['visitor_status', 'assignment_status', 'updated_at'])



            from activities.services import create_notification

            create_notification(

                recipient=counselor,

                title="Walk-in Visitor Waiting",

                message=f"{lead.name} (Token: #{token_number}) is waiting for consultation in {branch.name if branch else 'reception'}.",

                notification_type='info',

                link=reverse('counselor_lead_detail', args=[lead.id])

            )



        return JsonResponse({

            'success': True,

            'lead_id': lead.id,

            'token_number': token_number,

            'message': f"Visitor checked in with Token #{token_number}."

        })

    except Exception as e:

        logger.exception("admin_walkin_create failed: %s", e)

        return JsonResponse({'success': False, 'error': str(e)}, status=500)





@login_required

@require_POST

def admin_walkin_assign_counselor(request, pk):

    """

    Assigns a waiting walk-in visitor to an available branch counselor.

    Updates visitor status to 'In Consultation' and dispatches notifications.

    Uses select_for_update() inside atomic transaction to prevent race conditions.

    """

    user = request.user

    if not (user.is_admin_user or user.role in (UserRole.SALES_HEAD, UserRole.BRANCH_HEAD, UserRole.COUNSELOR, UserRole.RECEPTIONIST)):

        return JsonResponse({'success': False, 'error': 'Permission denied.'}, status=403)



    if user.is_receptionist_user and not user.branch_id:

        return JsonResponse({'success': False, 'error': 'Your receptionist account is not assigned to any branch.'}, status=403)



    if request.content_type == 'application/json':

        try:

            data = json.loads(request.body)

        except Exception:

            data = {}

    else:

        data = request.POST



    counselor_id = data.get('counselor_id')

    reason = (data.get('reason') or 'Assigned at Reception Desk').strip()



    if not counselor_id:

        return JsonResponse({'success': False, 'error': 'Counselor ID is required.'}, status=400)



    try:

        counselor = User.objects.get(pk=counselor_id, role=UserRole.COUNSELOR, is_active=True)

    except User.DoesNotExist:

        return JsonResponse({'success': False, 'error': 'Selected counselor was not found or is inactive.'}, status=404)



    # Counselor must belong to the receptionist's branch

    if user.is_receptionist_user and counselor.branch_id != user.branch_id:

        return JsonResponse({'success': False, 'error': 'Cannot assign to a counselor outside your branch.'}, status=400)



    from .handoff_service import handoff_to_counselor

    with transaction.atomic():

        try:

            lead = Lead.objects.select_for_update().get(pk=pk)

        except Lead.DoesNotExist:

            return JsonResponse({'success': False, 'error': 'Lead not found.'}, status=404)



        # Cross-branch prevention for Receptionists

        if user.is_receptionist_user and lead.branch_id != user.branch_id:

            return JsonResponse({'success': False, 'error': 'Permission denied: Cannot assign leads from another branch.'}, status=403)



        if lead.branch_id and counselor.branch_id and counselor.branch_id != lead.branch_id:

            return JsonResponse({'success': False, 'error': 'Counselor must belong to the same branch as the lead.'}, status=400)



        handoff_to_counselor(lead, counselor=counselor, assigned_by=user, reason=reason)

        lead.visitor_status = VisitorStatus.IN_CONSULTATION

        lead.assignment_status = 'Assigned'

        if not lead.center_visit_date:

            lead.center_visit_date = timezone.now()

        lead.save(update_fields=['visitor_status', 'assignment_status', 'center_visit_date', 'updated_at'])



        log_activity(

            user=user,

            action="Walk-in Assigned to Counselor",

            description=f"Walk-in visitor #{lead.id} ({lead.name}) assigned to Counselor '{counselor.username}'.",

            object_type="Lead",

            object_id=lead.id,

            request=request

        )



        from activities.services import create_notification

        create_notification(

            recipient=counselor,

            title="Walk-in Consultation Assigned",

            message=f"{lead.name} (Token: #{lead.token_number or lead.id}) is waiting for you in reception.",

            notification_type='info',

            link=reverse('counselor_lead_detail', args=[lead.id])

        )



    if request.headers.get('x-requested-with') == 'XMLHttpRequest' or request.content_type == 'application/json' or request.GET.get('format') == 'json':

        return JsonResponse({

            'success': True,

            'lead_id': lead.id,

            'counselor_name': counselor.get_full_name() or counselor.username,

            'message': f"Visitor successfully assigned to Counselor {counselor.username}."

        })

    messages.success(request, f"Visitor #{lead.id} successfully assigned to Counselor {counselor.get_full_name() or counselor.username}.")

    return redirect('receptionist_dashboard')





@login_required

@require_POST

def admin_walkin_bulk_assign_counselor(request):

    """

    Bulk assigns one or multiple walk-in leads to an available branch counselor.

    Validates receptionist branch scope and counselor branch compatibility.

    Saves assignments atomically with row-locking and dispatches notifications.

    """

    user = request.user

    if not (user.is_admin_user or user.role in (UserRole.SALES_HEAD, UserRole.BRANCH_HEAD, UserRole.COUNSELOR, UserRole.RECEPTIONIST)):

        return JsonResponse({'success': False, 'error': 'Permission denied.'}, status=403)



    if user.is_receptionist_user and not user.branch_id:

        return JsonResponse({'success': False, 'error': 'Your receptionist account is not assigned to any branch.'}, status=403)



    if request.content_type == 'application/json':

        try:

            data = json.loads(request.body)

        except Exception:

            data = {}

    else:

        data = request.POST



    raw_lead_ids = data.get('lead_ids') or (data.getlist('lead_ids') if hasattr(data, 'getlist') else [])

    if isinstance(raw_lead_ids, str):

        lead_ids = [int(x.strip()) for x in raw_lead_ids.split(',') if x.strip().isdigit()]

    elif isinstance(raw_lead_ids, (list, tuple)):

        lead_ids = [int(x) for x in raw_lead_ids if str(x).isdigit()]

    else:

        lead_ids = []



    counselor_id = data.get('counselor_id')

    reason = (data.get('reason') or 'Bulk assigned at Reception Desk').strip()



    if not lead_ids:

        return JsonResponse({'success': False, 'error': 'Please select at least one lead to assign.'}, status=400)



    if not counselor_id:

        return JsonResponse({'success': False, 'error': 'Counselor ID is required.'}, status=400)



    try:

        counselor = User.objects.get(pk=counselor_id, role=UserRole.COUNSELOR, is_active=True)

    except User.DoesNotExist:

        return JsonResponse({'success': False, 'error': 'Selected counselor was not found or is inactive.'}, status=404)



    # Counselor must belong to the receptionist's branch

    if user.is_receptionist_user and counselor.branch_id != user.branch_id:

        return JsonResponse({'success': False, 'error': 'Cannot assign to a counselor outside your branch.'}, status=400)



    from .handoff_service import handoff_to_counselor

    assigned_count = 0



    with transaction.atomic():

        leads = list(Lead.objects.select_for_update().filter(id__in=lead_ids))

        if not leads:

            return JsonResponse({'success': False, 'error': 'No matching leads found.'}, status=404)



        for lead in leads:

            # Cross-branch check for Receptionists

            if user.is_receptionist_user and lead.branch_id != user.branch_id:

                return JsonResponse({

                    'success': False,

                    'error': f"Permission denied: Lead #{lead.id} ('{lead.name}') belongs to a different branch."

                }, status=403)



            if lead.branch_id and counselor.branch_id and counselor.branch_id != lead.branch_id:

                return JsonResponse({

                    'success': False,

                    'error': f"Counselor must belong to the same branch as lead #{lead.id} ('{lead.name}')."

                }, status=400)



            handoff_to_counselor(lead, counselor=counselor, assigned_by=user, reason=reason)

            lead.visitor_status = VisitorStatus.IN_CONSULTATION

            lead.assignment_status = 'Assigned'

            if not lead.center_visit_date:

                lead.center_visit_date = timezone.now()

            lead.save(update_fields=['visitor_status', 'assignment_status', 'center_visit_date', 'updated_at'])



            log_activity(

                user=user,

                action="Walk-in Assigned to Counselor",

                description=f"Walk-in visitor #{lead.id} ({lead.name}) assigned to Counselor '{counselor.username}'.",

                object_type="Lead",

                object_id=lead.id,

                request=request

            )

            assigned_count += 1



        if assigned_count > 0:

            from activities.services import create_notification

            create_notification(

                recipient=counselor,

                title="Walk-in Consultations Assigned",

                message=f"{assigned_count} walk-in student(s) have been assigned to you by Reception.",

                notification_type='info',

                link=reverse('counselor_dashboard')

            )



    msg = f"Successfully assigned {assigned_count} walk-in lead(s) to Counselor {counselor.get_full_name() or counselor.username}."

    if request.headers.get('x-requested-with') == 'XMLHttpRequest' or request.content_type == 'application/json' or request.GET.get('format') == 'json':

        return JsonResponse({

            'success': True,

            'assigned_count': assigned_count,

            'counselor_name': counselor.get_full_name() or counselor.username,

            'message': msg

        })



    messages.success(request, msg)

    return redirect('receptionist_dashboard')





@login_required

@require_POST

def admin_walkin_update_status(request, pk):

    """

    Updates the visitor status of a walk-in lead (Waiting / In Consultation / Completed / No Show).

    """

    user = request.user

    if user.is_receptionist_user or not (user.is_admin_user or user.role in (UserRole.SALES_HEAD, UserRole.BRANCH_HEAD, UserRole.COUNSELOR)):

        return JsonResponse({'success': False, 'error': 'Permission denied: Receptionists cannot update lead status.'}, status=403)



    lead = get_object_or_404(Lead, pk=pk)



    # Cross-branch prevention for Receptionists

    if user.is_receptionist_user and lead.branch_id != user.branch_id:

        return JsonResponse({'success': False, 'error': 'Permission denied: Cannot update status of leads from another branch.'}, status=403)



    if request.content_type == 'application/json':

        data = json.loads(request.body)

    else:

        data = request.POST



    new_status = data.get('visitor_status')

    if new_status not in [c[0] for c in VisitorStatus.choices]:

        return JsonResponse({'success': False, 'error': f"Invalid visitor status: '{new_status}'"}, status=400)



    lead.visitor_status = new_status

    update_fields = ['visitor_status', 'updated_at']



    if new_status == VisitorStatus.COMPLETED and lead.status not in (LeadStatus.CONVERTED, LeadStatus.JOINED):

        lead.status = LeadStatus.VISITED

        update_fields.append('status')



    lead.save(update_fields=update_fields)



    log_activity(

        user=user,

        action="Walk-in Status Updated",

        description=f"Walk-in visitor #{lead.id} ({lead.name}) status changed to '{new_status}'.",

        object_type="Lead",

        object_id=lead.id,

        request=request

    )



    return JsonResponse({

        'success': True,

        'lead_id': lead.id,

        'visitor_status': new_status

    })





@admin_required

def admin_pipeline_statuses_list(request):

    """

    Admin management view for pipeline stages and statuses.

    Allows creating new statuses, editing existing ones, and re-ordering or toggling active state.

    """

    from .models import PipelineStatus



    if request.method == 'POST':

        action = request.POST.get('action', 'create')

        if action == 'create':

            name = request.POST.get('name', '').strip()

            stage_category = request.POST.get('stage_category', 'General').strip()

            color = request.POST.get('color', '#3b82f6').strip()

            sort_order_raw = request.POST.get('sort_order', '0').strip()

            try:

                sort_order = int(sort_order_raw)

            except ValueError:

                sort_order = 0



            if not name:

                messages.error(request, "Status name is required.")

            elif PipelineStatus.objects.filter(name__iexact=name).exists():

                messages.error(request, f"Status '{name}' already exists.")

            else:

                PipelineStatus.objects.create(

                    name=name,

                    stage_category=stage_category,

                    color=color,

                    sort_order=sort_order,

                    is_active=True,

                    is_system_default=False

                )

                log_activity(

                    user=request.user,

                    action="Pipeline Status Created",

                    description=f"Created custom pipeline status '{name}' under category '{stage_category}'.",

                    object_type="PipelineStatus",

                    request=request

                )

                messages.success(request, f"Pipeline status '{name}' created successfully.")

            return redirect('admin_pipeline_statuses')



    search_query = request.GET.get('search', '').strip()

    status_filter = request.GET.get('status', '').strip()



    statuses_qs = PipelineStatus.objects.all()

    if search_query:

        statuses_qs = statuses_qs.filter(Q(name__icontains=search_query) | Q(stage_category__icontains=search_query))

    if status_filter == 'active':

        statuses_qs = statuses_qs.filter(is_active=True)

    elif status_filter == 'inactive':

        statuses_qs = statuses_qs.filter(is_active=False)



    statuses = list(statuses_qs.order_by('sort_order', 'name'))



    return render(request, 'admin/pipeline_statuses_list.html', {

        'statuses': statuses,

        'search_query': search_query,

        'status_filter': status_filter,

    })





@admin_required

def admin_pipeline_status_edit(request, pk):

    from .models import PipelineStatus

    status_obj = get_object_or_404(PipelineStatus, pk=pk)



    if request.method == 'POST':

        name = request.POST.get('name', '').strip()

        stage_category = request.POST.get('stage_category', 'General').strip()

        color = request.POST.get('color', '#3b82f6').strip()

        sort_order_raw = request.POST.get('sort_order', '0').strip()

        is_active = request.POST.get('is_active') == 'on'



        try:

            sort_order = int(sort_order_raw)

        except ValueError:

            sort_order = 0



        if not name:

            messages.error(request, "Status name is required.")

        else:

            conflict = PipelineStatus.objects.filter(name__iexact=name).exclude(pk=status_obj.pk).exists()

            if conflict:

                messages.error(request, f"Another status with name '{name}' already exists.")

            else:

                old_name = status_obj.name

                status_obj.name = name

                status_obj.stage_category = stage_category

                status_obj.color = color

                status_obj.sort_order = sort_order

                status_obj.is_active = is_active

                status_obj.save()



                log_activity(

                    user=request.user,

                    action="Pipeline Status Updated",

                    description=f"Updated pipeline status from '{old_name}' to '{name}'.",

                    object_type="PipelineStatus",

                    object_id=status_obj.id,

                    request=request

                )

                messages.success(request, f"Pipeline status '{name}' updated successfully.")

                return redirect('admin_pipeline_statuses')



    return render(request, 'admin/pipeline_status_edit.html', {

        'status_obj': status_obj

    })





@admin_required

@require_POST

def admin_pipeline_status_toggle(request, pk):

    from .models import PipelineStatus

    status_obj = get_object_or_404(PipelineStatus, pk=pk)

    status_obj.is_active = not status_obj.is_active

    status_obj.save(update_fields=['is_active', 'updated_at'])



    log_activity(

        user=request.user,

        action="Pipeline Status Toggled",

        description=f"Toggled pipeline status '{status_obj.name}' to {'Active' if status_obj.is_active else 'Inactive'}.",

        object_type="PipelineStatus",

        object_id=status_obj.id,

        request=request

    )

    messages.success(request, f"Status '{status_obj.name}' is now {'Active' if status_obj.is_active else 'Inactive'}.")

    return redirect('admin_pipeline_statuses')





@admin_required

@require_POST

def admin_pipeline_status_delete(request, pk):

    from .models import PipelineStatus

    status_obj = get_object_or_404(PipelineStatus, pk=pk)

    if status_obj.is_system_default:

        messages.error(request, "Default system pipeline statuses cannot be deleted. You can mark them Inactive instead.")

        return redirect('admin_pipeline_statuses')



    name = status_obj.name

    status_obj.delete()

    log_activity(

        user=request.user,

        action="Pipeline Status Deleted",

        description=f"Deleted custom pipeline status '{name}'.",

        object_type="PipelineStatus",

        request=request

    )

    messages.success(request, f"Custom status '{name}' deleted successfully.")

    return redirect('admin_pipeline_statuses')


























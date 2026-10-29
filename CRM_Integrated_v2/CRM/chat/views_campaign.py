"""
Views for Bulk WhatsApp Campaigns in TECHPANDA CRM.
Handles campaign listing, composer wizard, real-time telemetry, recipient filtering,
CSV export, and lifecycle controls (start, pause, resume, cancel).
"""

import json
import csv
from datetime import datetime
from django.shortcuts import render, get_object_or_404, redirect
from django.http import JsonResponse, HttpResponse
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST, require_GET
from django.utils import timezone
from django.db.models import Q, Count, Sum
from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator
from django.urls import reverse

from chat.models import (
    WhatsAppSender,
    WhatsAppTemplate,
    WhatsAppCampaign,
    WhatsAppCampaignRecipient,
    BusinessAccount
)
from leads.models import Lead
from chat.campaign_service import (
    ensure_default_senders_and_templates,
    get_eligible_senders_for_user,
    resolve_campaign_recipients,
    dispatch_campaign_batch,
    run_campaign_worker_loop
)
from chat.tasks import trigger_campaign_execution_async


def is_campaign_authorized(user) -> bool:
    """Verifies that the user has permission to manage or view campaigns: Admin, Superadmin, and Sales Head only."""
    if not (user and user.is_authenticated and user.is_active):
        return False
    return bool(
        getattr(user, 'is_admin_user', False)
        or getattr(user, 'is_sales_head_user', False)
        or getattr(user, 'role', '') == 'SALES_HEAD'
    )


def can_manage_campaign(user, campaign: WhatsAppCampaign = None) -> bool:
    """Verifies that the user has permission to manage or view this campaign: Admin, Superadmin, and Sales Head only."""
    if not is_campaign_authorized(user):
        return False
    if getattr(user, 'is_admin_user', False):
        return True
    if campaign and campaign.created_by == user:
        return True
    # Sales Head can access campaigns in their assigned branches
    if user.role == 'SALES_HEAD':
        from branches.models import SalesHeadBranchAccess
        branches = SalesHeadBranchAccess.objects.filter(sales_head=user).values_list('branch_id', flat=True)
        if campaign and campaign.branch_id and campaign.branch_id in branches:
            return True
        return True
    return False


@login_required
def campaigns_list_view(request):
    """
    Overview list of all bulk WhatsApp campaigns with KPI metrics and status filtering.
    """
    if not is_campaign_authorized(request.user):
        raise PermissionDenied("Only Admin and Sales Head can access WhatsApp Campaigns.")
    ensure_default_senders_and_templates()
    user = request.user

    qs = WhatsAppCampaign.objects.all().select_related(
        'created_by', 'selected_sender', 'template', 'branch'
    )

    if not (getattr(user, 'is_admin_user', False) or user.is_superuser or user.role == 'ADMIN'):
        if user.role == 'SALES_HEAD':
            from branches.models import SalesHeadBranchAccess
            branches = SalesHeadBranchAccess.objects.filter(sales_head=user).values_list('branch_id', flat=True)
            qs = qs.filter(Q(created_by=user) | Q(branch_id__in=branches))
        elif user.role == 'BRANCH_HEAD':
            qs = qs.filter(Q(created_by=user) | Q(branch=user.branch))
        else:
            qs = qs.filter(created_by=user)

    search_query = request.GET.get('search', '').strip()
    status_filter = request.GET.get('status', '').strip()

    if search_query:
        qs = qs.filter(name__icontains=search_query)
    if status_filter:
        qs = qs.filter(status=status_filter)

    # Calculate overall KPIs
    total_campaigns = qs.count()
    active_count = qs.filter(status__in=['running', 'scheduled']).count()
    total_delivered = qs.aggregate(sum_del=Sum('delivered_count'))['sum_del'] or 0
    total_submitted = qs.aggregate(sum_sub=Sum('submitted_count'))['sum_sub'] or 0
    delivery_rate = int((total_delivered / total_submitted) * 100) if total_submitted else 0

    paginator = Paginator(qs, 15)
    page_obj = paginator.get_page(request.GET.get('page'))

    return render(request, 'chat/campaigns/campaigns_list.html', {
        'page_obj': page_obj,
        'total_campaigns': total_campaigns,
        'active_count': active_count,
        'total_delivered': total_delivered,
        'delivery_rate': delivery_rate,
        'search_query': search_query,
        'status_filter': status_filter,
        'status_choices': WhatsAppCampaign.STATUS_CHOICES,
    })


@login_required
def campaign_create_wizard_view(request):
    """
    Clean, responsive campaign composer wizard supporting:
    - Campaign information
    - Sender mode selection (Mode 1: assigned telecaller, Mode 2: one selected sender)
    - Recipient preview with validation counts (eligible, skipped, invalid phone)
    - Approved templates and deterministic placeholder mapping
    - Final confirmation, draft save, and background dispatch.
    """
    if not is_campaign_authorized(request.user):
        raise PermissionDenied("Only Admin and Sales Head can create WhatsApp Campaigns.")
    ensure_default_senders_and_templates()
    user = request.user

    # Leads passed from leads listing page
    raw_lead_ids = request.GET.get('lead_ids', '')
    lead_ids = [int(i.strip()) for i in raw_lead_ids.split(',') if i.strip().isdigit()]

    # Filters passed from leads listing page
    filter_params = {
        'search': request.GET.get('search', '').strip(),
        'branch': request.GET.get('branch', '').strip(),
        'status': request.GET.get('status', '').strip(),
        'telecaller': request.GET.get('telecaller', '').strip(),
        'channel': request.GET.get('channel', '').strip(),
        'product': request.GET.get('product', '').strip(),
    }
    has_filters = any(filter_params.values())

    eligible_senders = get_eligible_senders_for_user(user)
    approved_templates = WhatsAppTemplate.objects.filter(is_active=True, status='APPROVED')

    if request.method == 'POST':
        camp_name = request.POST.get('name', '').strip()
        if not camp_name:
            camp_name = f"Campaign - {timezone.now().strftime('%d %b %Y %H:%M')}"

        sender_mode = request.POST.get('sender_mode', WhatsAppCampaign.MODE_SELECTED_SENDER)
        selected_sender_id = request.POST.get('selected_sender')
        template_id = request.POST.get('template')
        custom_msg = request.POST.get('custom_message', '').strip()
        media_url = request.POST.get('media_url', '').strip()
        action_type = request.POST.get('action_type', 'send_now')  # 'send_now', 'save_draft', 'schedule'
        schedule_time_str = request.POST.get('scheduled_at', '').strip()

        selected_sender = WhatsAppSender.objects.filter(id=selected_sender_id).first() if selected_sender_id else None
        template = WhatsAppTemplate.objects.filter(id=template_id).first() if template_id else None

        # Build campaign instance
        campaign = WhatsAppCampaign.objects.create(
            name=camp_name,
            created_by=user,
            branch=user.branch,
            sender_mode=sender_mode,
            selected_sender=selected_sender,
            template=template,
            message_type=WhatsAppCampaign.MESSAGE_TYPE_TEMPLATE if template else WhatsAppCampaign.MESSAGE_TYPE_TEXT,
            custom_message=custom_msg,
            media_url=media_url,
            status=WhatsAppCampaign.STATUS_DRAFT,
            filter_criteria=filter_params if (not lead_ids and has_filters) else {},
        )

        # Parse schedule time if chosen
        if action_type == 'schedule' and schedule_time_str:
            try:
                campaign.scheduled_at = datetime.fromisoformat(schedule_time_str)
                campaign.status = WhatsAppCampaign.STATUS_SCHEDULED
            except Exception:
                pass

        # Populate recipients
        target_ids = lead_ids if lead_ids else None
        target_filters = filter_params if (not lead_ids and has_filters) else None
        resolve_campaign_recipients(campaign, lead_ids=target_ids, filter_criteria=target_filters, user=user)

        # Execute campaign if requested
        if action_type == 'send_now':
            campaign.status = WhatsAppCampaign.STATUS_RUNNING
            campaign.started_at = timezone.now()
            campaign.save(update_fields=['status', 'started_at', 'updated_at'])
            trigger_campaign_execution_async(campaign.id)

        return redirect('whatsapp_campaign_detail', pk=campaign.id)

    # Initial recipient resolution preview count for GET
    initial_total = 0
    if lead_ids:
        initial_total = len(lead_ids)
    elif has_filters:
        qs = Lead.objects.all()
        if filter_params['search']:
            q = filter_params['search']
            qs = qs.filter(Q(name__icontains=q) | Q(phone__icontains=q) | Q(email__icontains=q))
        if filter_params['branch']:
            qs = qs.filter(branch_id=filter_params['branch'])
        if filter_params['status']:
            qs = qs.filter(status=filter_params['status'])
        if filter_params['telecaller']:
            qs = qs.filter(assigned_telecaller_id=filter_params['telecaller'])
        initial_total = qs.count()

    return render(request, 'chat/campaigns/campaign_composer.html', {
        'senders': eligible_senders,
        'templates': approved_templates,
        'lead_ids_str': ','.join(str(i) for i in lead_ids),
        'lead_count': initial_total,
        'filter_params_json': json.dumps(filter_params),
        'has_filters': has_filters,
    })


@login_required
def campaign_detail_view(request, pk):
    """
    Detailed campaign status monitor showing live delivery telemetry,
    searchable recipient table with skip reasons, and campaign control actions.
    """
    if not is_campaign_authorized(request.user):
        raise PermissionDenied("Only Admin and Sales Head can view WhatsApp Campaigns.")
    campaign = get_object_or_404(WhatsAppCampaign, pk=pk)
    if not can_manage_campaign(request.user, campaign):
        raise PermissionDenied("Unauthorized to view this campaign")

    recipient_qs = campaign.recipients.all().select_related('lead', 'resolved_sender')

    # Filter recipients
    search_q = request.GET.get('search', '').strip()
    status_filter = request.GET.get('status', '').strip()

    if search_q:
        recipient_qs = recipient_qs.filter(
            Q(lead_name__icontains=search_q) |
            Q(phone_number__icontains=search_q) |
            Q(provider_message_id__icontains=search_q)
        )
    if status_filter:
        recipient_qs = recipient_qs.filter(status=status_filter)

    paginator = Paginator(recipient_qs, 20)
    page_obj = paginator.get_page(request.GET.get('page'))

    return render(request, 'chat/campaigns/campaign_detail.html', {
        'campaign': campaign,
        'page_obj': page_obj,
        'search_q': search_q,
        'status_filter': status_filter,
        'status_choices': WhatsAppCampaignRecipient.STATUS_CHOICES,
    })


@login_required
@require_POST
def api_campaign_control(request, pk):
    """
    AJAX endpoint to start, pause, resume, cancel, or re-run a campaign.
    """
    if not is_campaign_authorized(request.user):
        return JsonResponse({'success': False, 'error': 'Permission denied. Only Admin and Sales Head can manage campaigns.'}, status=403)
    campaign = get_object_or_404(WhatsAppCampaign, pk=pk)
    if not can_manage_campaign(request.user, campaign):
        return JsonResponse({'success': False, 'error': 'Permission denied'}, status=403)

    try:
        data = json.loads(request.body)
    except Exception:
        data = request.POST

    action = data.get('action')

    if action == 'start' or action == 'resume':
        if campaign.status in [WhatsAppCampaign.STATUS_COMPLETED, WhatsAppCampaign.STATUS_CANCELLED]:
            return JsonResponse({'success': False, 'error': f"Cannot resume {campaign.status} campaign"}, status=400)
        campaign.status = WhatsAppCampaign.STATUS_RUNNING
        if not campaign.started_at:
            campaign.started_at = timezone.now()
        campaign.save(update_fields=['status', 'started_at', 'updated_at'])
        trigger_campaign_execution_async(campaign.id)
        return JsonResponse({'success': True, 'status': 'running', 'message': 'Campaign dispatched'})

    elif action == 'pause':
        campaign.status = WhatsAppCampaign.STATUS_PAUSED
        campaign.save(update_fields=['status', 'updated_at'])
        return JsonResponse({'success': True, 'status': 'paused', 'message': 'Campaign paused'})

    elif action == 'cancel':
        campaign.status = WhatsAppCampaign.STATUS_CANCELLED
        campaign.save(update_fields=['status', 'updated_at'])
        # Cancel any queued recipients
        campaign.recipients.filter(status__in=['eligible', 'queued']).update(status='cancelled')
        campaign.refresh_counters_from_db()
        return JsonResponse({'success': True, 'status': 'cancelled', 'message': 'Campaign cancelled'})

    elif action == 'retry_failed':
        retried = campaign.recipients.filter(status='failed').update(
            status='queued',
            attempt_count=0,
            error_message=''
        )
        campaign.status = WhatsAppCampaign.STATUS_RUNNING
        campaign.save(update_fields=['status', 'updated_at'])
        campaign.refresh_counters_from_db()
        trigger_campaign_execution_async(campaign.id)
        return JsonResponse({'success': True, 'retried_count': retried, 'message': f'Retrying {retried} failed recipients'})

    return JsonResponse({'success': False, 'error': f"Unknown action '{action}'"}, status=400)


@login_required
@require_GET
def api_campaign_progress(request, pk):
    """
    Real-time JSON endpoint for live UI polling of campaign telemetry.
    """
    if not is_campaign_authorized(request.user):
        return JsonResponse({'success': False, 'error': 'Permission denied.'}, status=403)
    campaign = get_object_or_404(WhatsAppCampaign, pk=pk)
    if not can_manage_campaign(request.user, campaign):
        return JsonResponse({'success': False, 'error': 'Permission denied'}, status=403)

    return JsonResponse({
        'success': True,
        'status': campaign.status,
        'status_display': campaign.get_status_display(),
        'progress_percentage': campaign.progress_percentage,
        'total_recipients': campaign.total_recipients,
        'eligible_count': campaign.eligible_count,
        'skipped_count': campaign.skipped_count,
        'queued_count': campaign.queued_count,
        'submitted_count': campaign.submitted_count,
        'sent_count': campaign.sent_count,
        'delivered_count': campaign.delivered_count,
        'read_count': campaign.read_count,
        'failed_count': campaign.failed_count,
        'is_active': campaign.status in [WhatsAppCampaign.STATUS_RUNNING, WhatsAppCampaign.STATUS_SCHEDULED],
    })


@login_required
def campaign_export_csv_view(request, pk):
    """
    Exports full campaign delivery telemetry and recipient results to CSV.
    """
    if not is_campaign_authorized(request.user):
        raise PermissionDenied("Only Admin and Sales Head can export WhatsApp Campaigns.")
    campaign = get_object_or_404(WhatsAppCampaign, pk=pk)
    if not can_manage_campaign(request.user, campaign):
        raise PermissionDenied("Unauthorized")

    response = HttpResponse(content_type='text/csv')
    filename = f"whatsapp_campaign_{campaign.id}_{timezone.now().strftime('%Y%m%d_%H%M')}.csv"
    response['Content-Disposition'] = f'attachment; filename="{filename}"'

    writer = csv.writer(response)
    writer.writerow([
        'Recipient ID', 'Lead ID', 'Lead Name', 'Phone Number', 'Status',
        'Skip Reason', 'Sender Number', 'Provider Message ID', 'Attempts',
        'Submitted At', 'Sent At', 'Delivered At', 'Read At', 'Failed At', 'Error'
    ])

    for r in campaign.recipients.all().select_related('lead'):
        writer.writerow([
            r.id,
            r.lead_id or '',
            r.lead_name,
            r.phone_number,
            r.status,
            r.skip_reason,
            r.sender_phone_number,
            r.provider_message_id,
            r.attempt_count,
            r.submitted_at.strftime('%Y-%m-%d %H:%M:%S') if r.submitted_at else '',
            r.sent_at.strftime('%Y-%m-%d %H:%M:%S') if r.sent_at else '',
            r.delivered_at.strftime('%Y-%m-%d %H:%M:%S') if r.delivered_at else '',
            r.read_at.strftime('%Y-%m-%d %H:%M:%S') if r.read_at else '',
            r.failed_at.strftime('%Y-%m-%d %H:%M:%S') if r.failed_at else '',
            r.error_message
        ])

    return response


@login_required
@require_POST
def api_toggle_lead_whatsapp_consent(request, pk):
    """
    Updates WhatsApp consent or opt-out status for a specific lead.
    """
    if not is_campaign_authorized(request.user):
        return JsonResponse({'success': False, 'error': 'Permission denied.'}, status=403)
    lead = get_object_or_404(Lead, pk=pk)
    try:
        data = json.loads(request.body)
    except Exception:
        data = request.POST

    action = data.get('action')
    if action == 'opt_out':
        lead.whatsapp_opt_out = True
        lead.save(update_fields=['whatsapp_opt_out', 'updated_at'])
        return JsonResponse({'success': True, 'whatsapp_opt_out': True, 'message': 'Lead opted out of WhatsApp'})
    elif action == 'opt_in':
        lead.whatsapp_opt_out = False
        lead.whatsapp_consent_given = True
        lead.whatsapp_consent_date = timezone.now()
        lead.save(update_fields=['whatsapp_opt_out', 'whatsapp_consent_given', 'whatsapp_consent_date', 'updated_at'])
        return JsonResponse({'success': True, 'whatsapp_opt_out': False, 'message': 'Lead consented to WhatsApp messages'})

    return JsonResponse({'success': False, 'error': f"Unknown action '{action}'"}, status=400)


@login_required
@require_POST
def api_create_campaign_sender(request):
    """
    Registers or updates an authorized WhatsApp number (channel) and sender profile
    for bulk campaigns and outbound communications.
    """
    if not is_campaign_authorized(request.user):
        return JsonResponse({'success': False, 'error': 'Permission denied. Only Admin and Sales Head can manage campaign senders.'}, status=403)

    try:
        data = json.loads(request.body)
    except Exception:
        data = request.POST

    name = str(data.get('name', '')).strip()
    phone_number = str(data.get('phone_number', '')).strip()
    phone_number_id = str(data.get('phone_number_id', '')).strip()
    business_account_id = str(data.get('business_account_id', '')).strip()
    access_token = str(data.get('access_token', '')).strip()
    daily_limit_raw = data.get('daily_limit', 1000)
    branch_id = data.get('branch_id')

    if not name:
        return JsonResponse({'success': False, 'error': 'Sender channel name is required.'}, status=400)
    if not phone_number:
        return JsonResponse({'success': False, 'error': 'Display phone number is required.'}, status=400)
    if not phone_number_id:
        return JsonResponse({'success': False, 'error': 'Meta Phone Number ID is required.'}, status=400)

    try:
        daily_limit = int(daily_limit_raw)
        if daily_limit < 1:
            daily_limit = 1000
    except (ValueError, TypeError):
        daily_limit = 1000

    # 1. Update or create the underlying BusinessAccount channel
    ba_defaults = {
        'name': name,
        'phone_number': phone_number,
        'business_account_id': business_account_id,
        'is_active': True,
    }
    if access_token:
        ba_defaults['access_token'] = access_token
    if branch_id:
        ba_defaults['crm_branch_id'] = branch_id

    business_account, _ = BusinessAccount.objects.update_or_create(
        phone_number_id=phone_number_id,
        defaults=ba_defaults
    )

    # 2. Update or create the WhatsAppSender
    sender, created = WhatsAppSender.objects.update_or_create(
        phone_number_id=phone_number_id,
        defaults={
            'name': name,
            'business_account': business_account,
            'display_phone_number': phone_number,
            'is_active': True,
            'is_verified': True,
            'quality_rating': 'GREEN',
            'daily_limit': daily_limit,
        }
    )

    if branch_id:
        sender.allowed_branches.add(branch_id)
    elif request.user.branch:
        sender.allowed_branches.add(request.user.branch)

    return JsonResponse({
        'success': True,
        'created': created,
        'sender': {
            'id': sender.id,
            'name': sender.name,
            'display_phone_number': sender.display_phone_number,
            'phone_number_id': sender.phone_number_id,
            'daily_limit': sender.daily_limit,
            'quality_rating': sender.quality_rating,
        },
        'message': f"WhatsApp number '{sender.name}' registered successfully."
    })


@login_required
@require_POST
def api_create_whatsapp_template(request):
    """
    Registers a pre-approved Meta WhatsApp Message Template in the CRM
    so it can be immediately selected and previewed in bulk campaigns.
    """
    if not is_campaign_authorized(request.user):
        return JsonResponse({'success': False, 'error': 'Permission denied. Only Admin and Sales Head can manage WhatsApp templates.'}, status=403)

    try:
        data = json.loads(request.body)
    except Exception:
        data = request.POST

    name = str(data.get('name', '')).strip().lower().replace(' ', '_')
    display_title = str(data.get('display_title', '')).strip()
    language = str(data.get('language', 'en_US')).strip()
    category = str(data.get('category', WhatsAppTemplate.CATEGORY_MARKETING)).strip().upper()
    body_text = str(data.get('body_text', '')).strip()
    header_type = str(data.get('header_type', WhatsAppTemplate.HEADER_NONE)).strip().upper()
    footer_text = str(data.get('footer_text', '')).strip()

    if not name:
        return JsonResponse({'success': False, 'error': 'Meta Template Name (snake_case identifier) is required.'}, status=400)
    if not body_text:
        return JsonResponse({'success': False, 'error': 'Template body text is required.'}, status=400)

    # Valid categories and headers
    valid_categories = dict(WhatsAppTemplate.CATEGORY_CHOICES).keys()
    if category not in valid_categories:
        category = WhatsAppTemplate.CATEGORY_MARKETING

    valid_headers = dict(WhatsAppTemplate.HEADER_CHOICES).keys()
    if header_type not in valid_headers:
        header_type = WhatsAppTemplate.HEADER_NONE

    template, created = WhatsAppTemplate.objects.update_or_create(
        name=name,
        defaults={
            'display_title': display_title or name,
            'language': language or 'en_US',
            'category': category,
            'header_type': header_type,
            'body_text': body_text,
            'footer_text': footer_text,
            'status': WhatsAppTemplate.STATUS_APPROVED,
            'is_active': True,
        }
    )

    return JsonResponse({
        'success': True,
        'created': created,
        'template': {
            'id': template.id,
            'name': template.name,
            'display_title': template.display_title or template.name,
            'language': template.language,
            'category': template.category,
            'header_type': template.header_type,
            'body_text': template.body_text,
            'footer_text': template.footer_text,
        },
        'message': f"Template '{template.name}' ({template.language}) registered successfully."
    })

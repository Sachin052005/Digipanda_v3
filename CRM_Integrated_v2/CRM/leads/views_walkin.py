import io

import base64

import json

import logging

from django.shortcuts import render, get_object_or_404, redirect

from django.http import JsonResponse, HttpResponse

from django.views.decorators.csrf import csrf_exempt

from django.views.decorators.http import require_http_methods

from django.utils import timezone

from django.utils.text import slugify

from django.urls import reverse

from django.contrib.auth.decorators import login_required

from django.db import transaction

from django.db.models import F

import qrcode

import qrcode.image.svg

from accounts.models import User, UserRole
from accounts.permissions import admin_required, role_required

from branches.models import Branch

from lead_channels.models import Channel

from products.models import Product

from leads.models import (

    Lead, LeadCategory, LeadStatus, VisitorStatus, LeadOwnerType,

    DuplicateLeadRecord, WalkinEnquiryForm

)

logger = logging.getLogger(__name__)

def normalize_phone_number(phone_raw):

    """Sanitizes phone input to standard 10 digits for Indian numbers."""

    if not phone_raw:

        return ''

    digits = ''.join(c for c in str(phone_raw) if c.isdigit())

    if digits.startswith('91') and len(digits) == 12:

        digits = digits[2:]

    elif digits.startswith('0') and len(digits) == 11:

        digits = digits[1:]

    return digits[-10:] if len(digits) >= 10 else digits

@require_http_methods(["GET", "POST"])

def public_student_enquiry_form(request, branch_id=None, slug=None):

    """

    Public student-facing enquiry form for Walk-in visitors at the reception desk.

    Accessible without authentication via QR code scan on mobile devices.

    Dynamically renders the active WalkinEnquiryForm schema if available.

    """

    selected_branch = None

    if branch_id:

        selected_branch = Branch.objects.filter(id=branch_id, status='Active').first()

    # Query active branches and products for selection if needed

    active_branches = Branch.objects.filter(status='Active').order_by('name')

    active_products = Product.objects.filter(status='Active').order_by('name')

    # Resolve active form configuration

    form_config = None

    if slug:

        form_config = WalkinEnquiryForm.objects.filter(slug=slug, is_active=True).first()

    if not form_config and selected_branch:

        form_config = WalkinEnquiryForm.objects.filter(branch=selected_branch, is_active=True).first()

    if not form_config:

        form_config = WalkinEnquiryForm.objects.filter(is_default=True, is_active=True).first()

    if not form_config:

        form_config = WalkinEnquiryForm.objects.filter(is_active=True).first()

    # Default branch from form if not explicitly given in URL

    if not selected_branch and form_config and form_config.branch:

        selected_branch = form_config.branch

    schema = form_config.form_schema if form_config else None

    branding = dict((schema.get('branding') if (schema and isinstance(schema, dict)) else {}) or {})

    if not branding.get('icon'):

        branding['icon'] = '🐼'

    if not branding.get('brand_name'):

        branding['brand_name'] = 'digipanda'

    if not branding.get('subtitle'):

        branding['subtitle'] = (form_config.description if form_config else '') or 'Training & Placement Admission Form' 

    # Calculate live token preview for the form
    preview_now = timezone.now()
    preview_branch_code = (selected_branch.name[:3].upper() if selected_branch and selected_branch.name else 'HQ')
    preview_daily_count = 1
    try:
        preview_walkin_channel = Channel.objects.filter(name='Walk-in').first()
        if preview_walkin_channel and selected_branch:
            today_start = preview_now.replace(hour=0, minute=0, second=0, microsecond=0)
            preview_daily_count = Lead.objects.filter(
                branch=selected_branch,
                created_at__gte=today_start,
                channel=preview_walkin_channel
            ).count() + 1
    except Exception:
        pass
    token_preview = f"WI-{preview_branch_code}-{preview_daily_count:03d}"

    if request.method == "GET":
        return render(request, 'public/student_enquiry_form.html', {
            'form_config': form_config,
            'schema': schema,
            'branding': branding,
            'branch': selected_branch,
            'branches': active_branches,
            'products': active_products,
            'token_preview': token_preview,
        })

    # --- Process POST Submission ---
    try:
        custom_payload = {}
        name = (request.POST.get('name') or request.POST.get('full_name') or '').strip()
        phone_raw = (request.POST.get('phone') or request.POST.get('phone_number') or request.POST.get('mobile') or '').strip()
        email = (request.POST.get('email') or '').strip()
        post_branch_id = request.POST.get('branch_id')
        product_id = request.POST.get('product_id')

        # Standard Student Enquiry Form Fields Extraction
        custom_payload['dob'] = (request.POST.get('dob') or '').strip()
        custom_payload['home_address'] = (request.POST.get('home_address') or request.POST.get('address') or '').strip()
        custom_payload['city'] = (request.POST.get('city') or '').strip()
        custom_payload['state'] = (request.POST.get('state') or '').strip()
        custom_payload['zip_code'] = (request.POST.get('zip_code') or '').strip()
        custom_payload['gender'] = (request.POST.get('gender') or '').strip()
        custom_payload['preferred_contact'] = (request.POST.get('preferred_contact') or '').strip()

        # Education Qualifications
        custom_payload['experience_type'] = (request.POST.get('experience_type') or 'Fresher').strip()
        custom_payload['years_of_experience'] = (request.POST.get('years_of_experience') or '').strip()
        custom_payload['ug_qualification'] = (request.POST.get('ug_qualification') or request.POST.get('ug_degree') or '').strip()
        custom_payload['ug_passed_out_year'] = (request.POST.get('ug_passed_out_year') or request.POST.get('ug_year') or '').strip()
        custom_payload['pg_qualification'] = (request.POST.get('pg_qualification') or request.POST.get('pg_degree') or '').strip()
        custom_payload['pg_passed_out_year'] = (request.POST.get('pg_passed_out_year') or request.POST.get('pg_year') or '').strip()
        custom_payload['backlogs'] = (request.POST.get('backlogs') or 'No').strip()
        custom_payload['highest_education'] = (request.POST.get('highest_education') or '').strip()

        # Current Professional Status
        prof_statuses = {}
        for pkey in ['status_student_fresher', 'status_non_it', 'status_bpo', 'status_freelancer', 'status_it', 'status_business', 'status_career_break']:
            pval = (request.POST.get(pkey) or '').strip()
            if pval:
                prof_statuses[pkey.replace('status_', '')] = pval
        if request.POST.get('status_others'):
            prof_statuses['others'] = request.POST.get('status_others').strip()
        custom_payload['professional_status'] = prof_statuses

        # Career Goals
        career_goals = request.POST.getlist('career_goals')
        goal_other = (request.POST.get('goal_other_text') or '').strip()
        if goal_other:
            career_goals.append(f"Other: {goal_other}")
        custom_payload['career_goals'] = career_goals

        # Prior Digital Marketing Experience
        dm_exp = request.POST.getlist('dm_experience')
        custom_payload['dm_experience'] = dm_exp

        # Interested Course
        interested_courses = request.POST.getlist('interested_course')
        custom_payload['interested_course'] = interested_courses
        course_track = ', '.join(interested_courses) if interested_courses else (request.POST.get('course_track') or '')

        # Student References
        custom_payload['student_reference_1'] = (request.POST.get('student_reference_1') or request.POST.get('ref_1_name') or '').strip()
        custom_payload['student_reference_2'] = (request.POST.get('student_reference_2') or request.POST.get('ref_2_name') or '').strip()

        # Form Metadata
        custom_payload['enquiry_date'] = (request.POST.get('enquiry_date') or '').strip()
        custom_payload['enquiry_time'] = (request.POST.get('enquiry_time') or '').strip()
        
        # Helper data dict for redisplay on validation error
        form_data_dict = dict(request.POST.items())
        form_data_dict['career_goals_str'] = ' | '.join(career_goals)
        form_data_dict['dm_experience_str'] = ' | '.join(dm_exp)
        form_data_dict['interested_course_str'] = ' | '.join(interested_courses)
        if not name or not phone_raw:

            return render(request, 'public/student_enquiry_form.html', {

                'form_config': form_config,

                'schema': schema,

                'branch': selected_branch,

                'branches': active_branches,

                'products': active_products,

                'error': 'Please enter your Full Name and Mobile Phone Number.',

                'form_data': form_data_dict,
                'token_preview': token_preview,

            }, status=400)

        phone_clean = normalize_phone_number(phone_raw)

        if len(phone_clean) < 10:

            return render(request, 'public/student_enquiry_form.html', {

                'form_config': form_config,

                'schema': schema,

                'branch': selected_branch,

                'branches': active_branches,

                'products': active_products,

                'error': 'Please enter a valid 10-digit mobile phone number.',

                'form_data': form_data_dict,
                'token_preview': token_preview,

            }, status=400)

        # Resolve branch

        branch = selected_branch

        if not branch and post_branch_id:

            branch = Branch.objects.filter(id=post_branch_id).first()

        if not branch and form_config and form_config.branch:

            branch = form_config.branch

        if not branch:

            branch = active_branches.first()

        # Resolve product

        product = None

        if product_id:

            product = Product.objects.filter(id=product_id).first()

        if not product and course_track:
            product = Product.objects.filter(name__icontains=course_track).first()
        if not product and interested_courses:
            for ic in interested_courses:
                p_match = Product.objects.filter(name__icontains=ic).first()
                if p_match:
                    product = p_match
                    break

        custom_payload.update({

            'course_track': course_track,

            'enquiry_submitted_via': 'Walk-in QR Standee',

            'form_name': form_config.title if form_config else 'Default Walk-in Form',

            'submitted_at': timezone.now().isoformat(),

        })

        # Generate sequential token

        now = timezone.now()

        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)

        walkin_channel, _ = Channel.objects.get_or_create(name='Walk-in', defaults={'status': 'Active'})

        branch_code = (branch.name[:3].upper() if branch and branch.name else 'HQ')

        daily_count = Lead.objects.filter(

            branch=branch,

            created_at__gte=today_start,

            channel=walkin_channel

        ).count() + 1

        token_number = f"WI-{branch_code}-{daily_count:03d}"

        # Route through CentralizedLeadIntakeService for unified duplicate detection,
        # 10-day branch governance, progressive enrichment, and audit logging.
        from leads.intake import CentralizedLeadIntakeService
        initial_notes = (
            f"Student Walk-in Enquiry Form submitted via Reception Desk QR Code.\n"
            f"Date: {now.strftime('%d-%b-%Y %I:%M %p')}\n"
            f"Assigned Token: #{token_number}\n"
            f"Form: {form_config.title if form_config else 'Default'}\n"
        )
        with transaction.atomic():
            intake_res = CentralizedLeadIntakeService.ingest(
                phone=phone_clean,
                source='Walk-in QR Form',
                channel_name='Walk-in',
                name=name,
                email=email,
                branch=branch,
                product=product,
                note=initial_notes,
                token_number=token_number,
                center_visit_date=now,
                visitor_status=VisitorStatus.WAITING,
                data_payload=custom_payload,
                incoming_timestamp=now,
            )
            lead = intake_res.lead
            is_re_enquiry = not intake_res.created

            lead.is_offline = True
            lead.category = LeadCategory.TRAINING
            merged_cf = dict(lead.custom_fields or {})
            merged_cf.update(custom_payload)
            lead.custom_fields = merged_cf
            lead.save(update_fields=['is_offline', 'category', 'custom_fields', 'updated_at'])

            # Increment submission count on form

            if form_config:

                WalkinEnquiryForm.objects.filter(id=form_config.id).update(submissions_count=F('submissions_count') + 1)

        return render(request, 'public/student_enquiry_success.html', {

            'lead': lead,

            'name': name,

            'token_number': token_number,

            'branch': branch,

            'is_re_enquiry': is_re_enquiry,

            'submitted_at': now,

        })

    except Exception as e:

        logger.exception("Failed to process public student enquiry: %s", e)

        return render(request, 'public/student_enquiry_form.html', {

            'form_config': form_config,

            'schema': schema,

            'branch': selected_branch,

            'branches': active_branches,

            'products': active_products,

            'error': f'An unexpected error occurred while submitting your enquiry: {str(e)}',

            'form_data': form_data_dict,
                'token_preview': token_preview,

        }, status=500)

@require_http_methods(["GET", "POST"])

def public_student_enquiry_form_by_slug(request, slug, branch_id=None):

    """Route alias to open a specific walk-in form by its slug."""

    return public_student_enquiry_form(request, branch_id=branch_id, slug=slug)

# ==========================================================================

# Admin Walk-in Forms Dashboard & Visual Studio Views

# ==========================================================================

@admin_required
def admin_walkin_forms_list(request):

    """

    GET /admin/walkin-forms/

    Dashboard listing all Walk-in Enquiry Forms with branch tags, status, and stats.

    """

    forms = WalkinEnquiryForm.objects.all().select_related('branch', 'created_by')

    branches = Branch.objects.filter(status='Active').order_by('name')

    # Total stats

    total_forms = forms.count()

    active_forms = forms.filter(is_active=True).count()

    total_submissions = sum(f.submissions_count for f in forms)

    return render(request, 'admin/walkin_forms_list.html', {

        'forms': forms,

        'branches': branches,

        'total_forms': total_forms,

        'active_forms': active_forms,

        'total_submissions': total_submissions,

    })

@admin_required
def admin_walkin_form_create(request):
    """Form creation disabled: Student Enquiry Form is the permanent default."""
    from django.contrib import messages
    messages.info(request, "The DigiPanda Student Enquiry Form is the permanent standardized Walk-in form. Template creation is disabled.")
    return redirect('admin_walkin_forms_list')

@admin_required
def admin_walkin_form_edit(request, pk):
    """Form structure editor disabled: Student Enquiry Form is the permanent default."""
    from django.contrib import messages
    messages.info(request, "The DigiPanda Student Enquiry Form is the permanent standardized Walk-in form. Field customization has been locked.")
    return redirect('admin_walkin_forms_list')

@admin_required
@require_http_methods(["POST"])
def admin_walkin_form_duplicate(request, pk):

    """Duplicates an existing form with a new unique slug."""

    orig = get_object_or_404(WalkinEnquiryForm, pk=pk)

    ts = int(timezone.now().timestamp())

    new_slug = f"{orig.slug}-copy-{ts}"

    new_title = f"{orig.title} (Copy)"

    clone = WalkinEnquiryForm.objects.create(

        title=new_title,

        slug=new_slug,

        description=orig.description,

        branch=orig.branch,

        theme_color=orig.theme_color,

        is_default=False,

        is_active=True,

        form_schema=orig.form_schema,

        created_by=request.user,

    )

    return redirect('admin_walkin_form_edit', pk=clone.pk)

@admin_required
@require_http_methods(["POST"])
def admin_walkin_form_toggle_status(request, pk):

    """Toggles active/inactive status."""

    form_obj = get_object_or_404(WalkinEnquiryForm, pk=pk)

    form_obj.is_active = not form_obj.is_active

    form_obj.save(update_fields=['is_active', 'updated_at'])

    return redirect('admin_walkin_forms_list')

@admin_required
@require_http_methods(["POST"])
def admin_walkin_form_delete(request, pk):

    """Deletes a form safely."""

    form_obj = get_object_or_404(WalkinEnquiryForm, pk=pk)

    title = form_obj.title

    form_obj.delete()

    return redirect('admin_walkin_forms_list')

@role_required(UserRole.ADMIN, UserRole.SUPERADMIN, UserRole.BRANCH_HEAD, UserRole.RECEPTIONIST)
def walkin_form_qr_standee_view(request, pk):

    """

    Renders a printable A4 Standee Poster for a specific WalkinEnquiryForm.

    """

    form_obj = get_object_or_404(WalkinEnquiryForm, pk=pk)

    branch = form_obj.branch

    if not branch:

        branch = Branch.objects.filter(status='Active').first()

    relative_url = reverse('public_student_enquiry_slug', kwargs={'slug': form_obj.slug})

    enquiry_url = request.build_absolute_uri(relative_url)

    qr_b64 = ''

    qr_svg = ''

    try:

        qr = qrcode.QRCode(

            version=1,

            error_correction=qrcode.constants.ERROR_CORRECT_H,

            box_size=10,

            border=2,

        )

        qr.add_data(enquiry_url)

        qr.make(fit=True)

        img = qr.make_image(fill_color="#0f172a", back_color="#ffffff")

        buf = io.BytesIO()

        img.save(buf, format='PNG')

        qr_b64 = base64.b64encode(buf.getvalue()).decode('utf-8')

        factory = qrcode.image.svg.SvgPathImage

        svg_qr = qrcode.make(enquiry_url, image_factory=factory, box_size=12, border=2)

        svg_buf = io.BytesIO()

        svg_qr.save(svg_buf)

        qr_svg = svg_buf.getvalue().decode('utf-8')

    except Exception as e:

        logger.exception("Failed to generate QR for form %s: %s", form_obj.id, e)

    branding = dict((form_obj.form_schema or {}).get('branding') or {})

    if not branding.get('icon'):

        branding['icon'] = '🐼'

    if not branding.get('brand_name'):

        branding['brand_name'] = 'digipanda'

    if not branding.get('subtitle'):

        branding['subtitle'] = form_obj.description or 'Training & Placement Admission Form' 

    return render(request, 'admin/walkin_form_qr_poster.html', {

        'form_obj': form_obj,

        'branch': branch,

        'enquiry_url': enquiry_url,

        'qr_b64': qr_b64,

        'qr_svg': qr_svg,

        'branding': branding,

    })

@role_required(UserRole.ADMIN, UserRole.SUPERADMIN, UserRole.BRANCH_HEAD, UserRole.RECEPTIONIST)
def branch_qr_standee_view(request, branch_id):

    """

    Renders a high-resolution, printable A4 / Desk Standee poster for a specific branch.

    The QR code encodes the branch's direct public walk-in enquiry form URL.

    """

    branch = get_object_or_404(Branch, id=branch_id)

    form_obj = WalkinEnquiryForm.objects.filter(branch=branch, is_active=True).first()

    if not form_obj:

        form_obj = WalkinEnquiryForm.objects.filter(is_default=True, is_active=True).first()

    if form_obj:

        relative_url = reverse('public_student_enquiry_slug_branch', kwargs={'slug': form_obj.slug, 'branch_id': branch.id})

    else:

        relative_url = reverse('public_student_enquiry_branch', kwargs={'branch_id': branch.id})

    enquiry_url = request.build_absolute_uri(relative_url)

    qr_b64 = ''

    qr_svg = ''

    try:

        qr = qrcode.QRCode(

            version=1,

            error_correction=qrcode.constants.ERROR_CORRECT_H,

            box_size=10,

            border=2,

        )

        qr.add_data(enquiry_url)

        qr.make(fit=True)

        img = qr.make_image(fill_color="#0f172a", back_color="#ffffff")

        buf = io.BytesIO()

        img.save(buf, format='PNG')

        qr_b64 = base64.b64encode(buf.getvalue()).decode('utf-8')

        factory = qrcode.image.svg.SvgPathImage

        svg_qr = qrcode.make(enquiry_url, image_factory=factory, box_size=12, border=2)

        svg_buf = io.BytesIO()

        svg_qr.save(svg_buf)

        qr_svg = svg_buf.getvalue().decode('utf-8')

    except Exception as e:

        logger.exception("Failed to generate QR code for branch %s: %s", branch.id, e)

    return render(request, 'admin/branch_qr_poster.html', {

        'branch': branch,

        'enquiry_url': enquiry_url,

        'qr_b64': qr_b64,

        'qr_svg': qr_svg,

    })

@role_required(UserRole.ADMIN, UserRole.SUPERADMIN, UserRole.BRANCH_HEAD, UserRole.RECEPTIONIST)
def receptionist_qr_standee_view(request):

    """

    Convenience endpoint for receptionists to quickly open their branch's QR Standee.

    """

    user = request.user

    branch = getattr(user, 'branch', None)

    if not branch:

        branch = Branch.objects.filter(status='Active').first()

    if not branch:

        return HttpResponse("No active branch configured in the system.", status=404)

    return redirect('branch_qr_standee', branch_id=branch.id)

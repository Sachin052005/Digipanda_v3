# -*- coding: utf-8 -*-
"""
Patch leads/views.py and leads/urls.py with full duplicate table explorer capabilities:
- search, filtering by branch and record_type
- raw payload JSON inspector view
- CSV export
- promote duplicate to independent lead
"""

# 1. Update leads/views.py
views_path = 'D:/CRM_Integrated_v2/CRM_Integrated_v2/CRM/leads/views.py'
with open(views_path, 'r', encoding='utf-8') as f:
    text = f.read()

old_dup_view = '''@admin_required
def admin_duplicate_leads_view(request):
    """
    Renders the Duplicate Leads Review page showing duplicate submission records
    (Section 13) including:
    - Lead Name
    - Phone (masked as 98765xxxxx)
    - Email
    - Original Branch & Submission Date
    - Duplicate Branch & Submission Date
    - Warning Banner: ⚠ Same lead details detected in another branch within 10 days.
    - Status: DUPLICATE
    - Button: [ View Original Lead ]
    - Button: [ Keep Single Lead ]
    """
    dup_records = DuplicateLeadRecord.objects.select_related('original_lead', 'branch', 'original_lead__branch').order_by('-submitted_at')

    formatted_duplicates = []
    for rec in dup_records:
        orig = rec.original_lead
        orig_branch = orig.branch.name if orig.branch else 'N/A'
        dup_branch = rec.branch.name if rec.branch else (rec.branch_name or 'N/A')
        is_cross_branch_10day = (orig_branch != dup_branch and 'within 10 days' in (rec.notes or '').lower())

        time_delta = rec.submitted_at - orig.created_at
        diff_days = max(0.0, round(time_delta.total_seconds() / 86400.0, 1))
        diff_days_str = f"{int(diff_days)} days" if diff_days.is_integer() else f"{diff_days} days"

        status_label = rec.status or ('DUPLICATE' if diff_days <= 10.0 else 'New Submission (>10 Days)')

        formatted_duplicates.append({
            'id': rec.id,
            'name': rec.name,
            'phone': mask_phone(rec.phone),
            'email': rec.email or '',
            'original_lead_id': orig.id,
            'original_lead_url': reverse('admin_lead_detail', args=[orig.id]),
            'original_branch': orig_branch,
            'original_date': timezone.localtime(orig.created_at).strftime('%d %b %Y, %I:%M %p'),
            'duplicate_branch': dup_branch,
            'duplicate_date': timezone.localtime(rec.submitted_at).strftime('%d %b %Y, %I:%M %p'),
            'days_difference': diff_days,
            'days_difference_display': diff_days_str,
            'status': status_label,
            'notes': rec.notes,
            'is_cross_branch_10day': is_cross_branch_10day,
            'lead_ids_str': f"{orig.id}",
        })

    groups, total_groups_count = detect_all_duplicate_groups()

    return render(request, 'admin/duplicate_leads.html', {
        'duplicate_records': formatted_duplicates,
        'duplicate_groups': groups,
        'total_duplicate_count': len(formatted_duplicates),
        'total_groups_count': len(formatted_duplicates) if formatted_duplicates else total_groups_count,
    })'''

new_dup_view = '''@admin_required
def admin_duplicate_leads_view(request):
    """
    Renders the Duplicate Leads Dedicated Table Explorer page with full search,
    branch filtering, record type filtering, raw JSON payload inspection, and promotion.
    """
    qs = DuplicateLeadRecord.objects.select_related('original_lead', 'branch', 'original_lead__branch').order_by('-submitted_at')

    # Filter by Search Query
    search_q = request.GET.get('q', '').strip()
    if search_q:
        clean_p = re.sub(r'\\D', '', search_q)
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
        rec.notes = f"{rec.notes}\\n[Promoted to separate Lead #{new_lead.id} on {timezone.now().strftime('%d %b %Y, %I:%M %p')}]"
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

    qs = DuplicateLeadRecord.objects.select_related('original_lead', 'branch', 'original_lead__branch').order_by('-submitted_at')

    # Apply same filters
    search_q = request.GET.get('q', '').strip()
    if search_q:
        clean_p = re.sub(r'\\D', '', search_q)
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

    return response'''

if old_dup_view in text:
    text = text.replace(old_dup_view, new_dup_view)
    with open(views_path, 'w', encoding='utf-8') as f:
        f.write(text)
    print("Successfully patched leads/views.py!")
else:
    print("Error: old_dup_view not found in leads/views.py")


# 2. Update leads/urls.py
urls_path = 'D:/CRM_Integrated_v2/CRM_Integrated_v2/CRM/leads/urls.py'
with open(urls_path, 'r', encoding='utf-8') as f:
    u_text = f.read()

old_url_line = "path('admin/duplicate-leads/keep-single/', views.admin_duplicate_leads_keep_single, name='admin_duplicate_leads_keep_single'),"
new_url_lines = """path('admin/duplicate-leads/keep-single/', views.admin_duplicate_leads_keep_single, name='admin_duplicate_leads_keep_single'),
    path('admin/duplicate-leads/export/', views.admin_duplicate_leads_export, name='admin_duplicate_leads_export'),
    path('admin/duplicate-leads/<int:rec_id>/payload/', views.admin_duplicate_lead_payload, name='admin_duplicate_lead_payload'),
    path('admin/duplicate-leads/<int:rec_id>/promote/', views.admin_duplicate_lead_promote, name='admin_duplicate_lead_promote'),"""

if old_url_line in u_text:
    u_text = u_text.replace(old_url_line, new_url_lines)
    with open(urls_path, 'w', encoding='utf-8') as f:
        f.write(u_text)
    print("Successfully patched leads/urls.py!")
else:
    print("Error: old_url_line not found in leads/urls.py")

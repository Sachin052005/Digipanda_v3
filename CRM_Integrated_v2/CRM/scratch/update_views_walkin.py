import os
import re

views_path = r"D:\CRM_Integrated_v2\CRM_Integrated_v2\CRM\leads\views_walkin.py"
with open(views_path, "r", encoding="utf-8") as f:
    content = f.read()

# 1. Update GET context in public_student_enquiry_form to pass token_preview
old_get_block = """    if request.method == "GET":

        return render(request, 'public/student_enquiry_form.html', {

            'form_config': form_config,

            'schema': schema,

            'branding': branding,

            'branch': selected_branch,

            'branches': active_branches,

            'products': active_products,

        })"""

new_get_block = """    # Calculate live token preview for the form
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
        })"""

if old_get_block in content:
    content = content.replace(old_get_block, new_get_block)
    print("Replaced GET block successfully!")
else:
    # Try normalizing newlines
    import re
    get_pattern = r'if request\.method == "GET":\s+return render\(request, \'public/student_enquiry_form\.html\', \{.*?\}\)'
    m = re.search(get_pattern, content, flags=re.DOTALL)
    if m:
        content = content[:m.start()] + new_get_block + content[m.end():]
        print("Replaced GET block via regex!")

# 2. Update POST extraction logic
post_extraction_old = re.search(r'# --- Process POST Submission ---.*?(?=if not name or not phone_raw:)', content, flags=re.DOTALL)
if post_extraction_old:
    new_post_extraction = '''# --- Process POST Submission ---
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
        '''
    content = content[:post_extraction_old.start()] + new_post_extraction + content[post_extraction_old.end():]
    print("Replaced POST extraction logic!")

with open(views_path, "w", encoding="utf-8") as f:
    f.write(content)
print("Updated views_walkin.py successfully!")

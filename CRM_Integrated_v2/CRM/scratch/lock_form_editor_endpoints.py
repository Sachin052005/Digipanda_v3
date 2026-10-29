views_path = r"D:\CRM_Integrated_v2\CRM_Integrated_v2\CRM\leads\views_walkin.py"
with open(views_path, "r", encoding="utf-8") as f:
    content = f.read()

import re

# Lock admin_walkin_form_create
create_pattern = r'@admin_required\s+@require_http_methods\(\["GET", "POST"\]\)\s+def admin_walkin_form_create\(request\):.*?(?=@admin_required)'
create_replacement = '''@admin_required
def admin_walkin_form_create(request):
    """Form creation disabled: Student Enquiry Form is the permanent default."""
    from django.contrib import messages
    messages.info(request, "The DigiPanda Student Enquiry Form is the permanent standardized Walk-in form. Template creation is disabled.")
    return redirect('admin_walkin_forms_list')

'''

content = re.sub(create_pattern, create_replacement, content, flags=re.DOTALL, count=1)

# Lock admin_walkin_form_edit
edit_pattern = r'@admin_required\s+def admin_walkin_form_edit\(request, pk\):.*?(?=@admin_required\s+def admin_walkin_form_duplicate)'
edit_replacement = '''@admin_required
def admin_walkin_form_edit(request, pk):
    """Form structure editor disabled: Student Enquiry Form is the permanent default."""
    from django.contrib import messages
    messages.info(request, "The DigiPanda Student Enquiry Form is the permanent standardized Walk-in form. Field customization has been locked.")
    return redirect('admin_walkin_forms_list')

'''

content = re.sub(edit_pattern, edit_replacement, content, flags=re.DOTALL, count=1)

# Lock admin_walkin_form_save
save_pattern = r'@admin_required\s+@require_POST\s+def admin_walkin_form_save\(request, pk\):.*?(?=@admin_required\s+@require_POST\s+def admin_walkin_form_duplicate)'
save_replacement = '''@admin_required
@require_POST
def admin_walkin_form_save(request, pk):
    """Save disabled: Student Enquiry Form is the permanent default."""
    return JsonResponse({'error': 'The DigiPanda Student Enquiry Form is standardized. Structural edits are disabled.'}, status=403)

'''
content = re.sub(save_pattern, save_replacement, content, flags=re.DOTALL, count=1)

with open(views_path, "w", encoding="utf-8") as f:
    f.write(content)
print("Locked admin form editor endpoints in views_walkin.py")

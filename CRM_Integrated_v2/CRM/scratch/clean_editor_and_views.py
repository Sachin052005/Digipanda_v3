import os
import re

# 1. Update walkin_forms_list.html
forms_list_path = r"D:\CRM_Integrated_v2\CRM_Integrated_v2\CRM\templates\admin\walkin_forms_list.html"
with open(forms_list_path, "r", encoding="utf-8") as f:
    c = f.read()

# Replace card-action-bar
c = re.sub(
    r'<div class="card-action-bar">.*?</div>\s*</div>\s*\{%\s*endfor\s*%\}',
    '''<div class="card-action-bar">
        <div style="display: flex; gap: 8px; flex-wrap: wrap;">
          <a href="{% url 'public_student_enquiry_slug' form.slug %}" target="_blank" class="btn-cyber-primary" title="Open Standard Student Enquiry Form">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6"></path><polyline points="15 3 21 3 21 9"></polyline><line x1="10" y1="14" x2="21" y2="3"></line></svg>
            Open Live Form
          </a>
          <a href="{% url 'walkin_form_qr_standee' form.id %}" target="_blank" class="btn-cyber-outline" title="Printable A4 QR Standee">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="3" y="3" width="7" height="7"></rect><rect x="14" y="3" width="7" height="7"></rect><rect x="14" y="14" width="7" height="7"></rect><rect x="3" y="14" width="7" height="7"></rect></svg>
            Print QR Standee
          </a>
        </div>
      </div>
    </div>
    {% endfor %}''',
    c, flags=re.DOTALL
)

# Remove the createFormModal and its JS
modal_block = re.search(r'<!-- Create Form Modal -->.*?{% endblock %}', c, flags=re.DOTALL)
if modal_block:
    clean_js = '''<script>
  function copyFormLink(slug, btn) {
    const fullUrl = window.location.origin + '/enquiry/f/' + slug + '/';
    navigator.clipboard.writeText(fullUrl).then(() => {
      const orig = btn.innerHTML;
      btn.innerHTML = '<span style="color:#10b981; font-weight:700;">✓</span>';
      setTimeout(() => { btn.innerHTML = orig; }, 1500);
    });
  }
</script>
{% endblock %}'''
    c = c[:modal_block.start()] + clean_js + c[modal_block.end():]

with open(forms_list_path, "w", encoding="utf-8") as f:
    f.write(c)
print("Updated walkin_forms_list.html completely!")

# 2. Update admin_walkin_form_edit in views_walkin.py
views_path = r"D:\CRM_Integrated_v2\CRM_Integrated_v2\CRM\leads\views_walkin.py"
with open(views_path, "r", encoding="utf-8") as f:
    vc = f.read()

edit_fn = re.search(r'@admin_required\s+@require_http_methods\(.*?def admin_walkin_form_edit\(request, pk\):.*?(?=@admin_required)', vc, flags=re.DOTALL)
if edit_fn:
    replacement = '''@admin_required
def admin_walkin_form_edit(request, pk):
    """Form structure editor disabled: Student Enquiry Form is the permanent default."""
    from django.contrib import messages
    messages.info(request, "The DigiPanda Student Enquiry Form is the permanent standardized Walk-in form. Field customization has been locked.")
    return redirect('admin_walkin_forms_list')

'''
    vc = vc[:edit_fn.start()] + replacement + vc[edit_fn.end():]

with open(views_path, "w", encoding="utf-8") as f:
    f.write(vc)
print("Updated admin_walkin_form_edit in views_walkin.py!")

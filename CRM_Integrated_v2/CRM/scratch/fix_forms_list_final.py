path = r"D:\CRM_Integrated_v2\CRM_Integrated_v2\CRM\templates\admin\walkin_forms_list.html"
with open(path, "r", encoding="utf-8") as f:
    c = f.read()

import re

# Replace card-action-bar
c = re.sub(
    r'<!-- Action Footer -->\s*<div class="card-action-bar">.*?</div>\s*</div>\s*</div>\s*{% empty %}',
    '''<!-- Action Footer -->
      <div class="card-action-bar">
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
    {% empty %}''',
    c, flags=re.DOTALL
)

# Remove modal and openCreateFormModal JS
c = re.sub(
    r'<!-- CREATE NEW FORM MODAL -->.*?<script>',
    '''<script>''',
    c, flags=re.DOTALL
)

c = re.sub(
    r'function openCreateFormModal\(.*?function autoGenerateSlug',
    '''function autoGenerateSlug''',
    c, flags=re.DOTALL
)

with open(path, "w", encoding="utf-8") as f:
    f.write(c)

print("Updated walkin_forms_list.html successfully!")

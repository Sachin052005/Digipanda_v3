import os
import re

# 1. Update base.html nav link text
base_path = r"D:\CRM_Integrated_v2\CRM_Integrated_v2\CRM\templates\base.html"
with open(base_path, "r", encoding="utf-8") as f:
    c = f.read()

c = c.replace(
    '<span class="nav-text">Walk-in Forms &amp; QR</span>',
    '<span class="nav-text">Walk-in Enquiry Form</span>'
)
c = c.replace(
    '<span class="nav-text">Walk-in Forms & QR</span>',
    '<span class="nav-text">Walk-in Enquiry Form</span>'
)
with open(base_path, "w", encoding="utf-8") as f:
    f.write(c)
print("Updated base.html nav text")

# 2. Update walkin_desk.html
desk_path = r"D:\CRM_Integrated_v2\CRM_Integrated_v2\CRM\templates\admin\walkin_desk.html"
with open(desk_path, "r", encoding="utf-8") as f:
    c = f.read()

c = c.replace(
    '<span>Form Studio &amp; QR</span>',
    '<span>Open Enquiry Form</span>'
)
c = c.replace(
    '<span>Form Studio & QR</span>',
    '<span>Open Enquiry Form</span>'
)
c = c.replace(
    '<a href="{% url \'admin_walkin_forms_list\' %}" class="btn btn-secondary"',
    '<a href="{% url \'public_student_enquiry_form\' %}" target="_blank" class="btn btn-secondary"'
)
with open(desk_path, "w", encoding="utf-8") as f:
    f.write(c)
print("Updated walkin_desk.html")

# 3. Streamline walkin_forms_list.html (decommission editor controls)
forms_list_path = r"D:\CRM_Integrated_v2\CRM_Integrated_v2\CRM\templates\admin\walkin_forms_list.html"
with open(forms_list_path, "r", encoding="utf-8") as f:
    c = f.read()

# Update hero badge & title
c = c.replace("<span>NO-CODE FORM STUDIO</span>", "<span>OFFICIAL DEFAULT FORM</span>")
c = c.replace("WALK-IN ENQUIRY FORM STUDIO", "WALK-IN ENQUIRY FORM &amp; QR")
c = c.replace("Visual no-code field builder, dynamic branch assignment, real-time smartphone simulator, and printable reception QR standees.",
              "Standardized DigiPanda Student Enquiry Form, branch reception desk tracking, and printable A4 QR standees.")

# Remove "Create New Form" button from hero
c = re.sub(r'<button type="button" class="btn-cyber-primary" onclick="openCreateFormModal\(\)">.*?</button>',
           r'<a href="{% url \'public_student_enquiry_form\' %}" target="_blank" class="btn-cyber-primary"><svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6"></path><polyline points="15 3 21 3 21 9"></polyline><line x1="10" y1="14" x2="21" y2="3"></line></svg> Open Live Form</a>',
           c, flags=re.DOTALL)

# In card-action-bar, remove "Visual Studio", "Duplicate", and "Delete" buttons
# Replace card-action-bar contents cleanly
c = re.sub(
    r'<div class="card-action-bar">.*?</div>\s*</div>\s*{% endfor %}',
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

# Remove create modal HTML and modal functions
c = re.sub(r'<!-- Create Form Modal -->.*?{% endblock %}', r'{% endblock %}', c, flags=re.DOTALL)

with open(forms_list_path, "w", encoding="utf-8") as f:
    f.write(c)
print("Updated walkin_forms_list.html (editor controls decommissioned)")

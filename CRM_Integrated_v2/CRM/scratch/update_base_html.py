with open(r"D:\CRM_Integrated_v2\CRM_Integrated_v2\CRM\templates\base.html", "r", encoding="utf-8") as f:
    content = f.read()

# Let's inspect sidebar brand block
import re

# 1. Update sidebar header
old_sidebar_pat = r'<div class="sidebar-header">[\s\S]*?</div>\s*</a>\s*</div>'
new_sidebar = """<div class="sidebar-header">
        <a href="{% url 'login_redirect' %}" class="brand-logo" style="display: flex; align-items: center; gap: 8px; text-decoration: none;">
          <img src="{% static 'images/digipanda_symbol.png' %}" alt="DigiPanda" width="30" height="30" style="object-fit: contain; flex-shrink: 0;" class="brand-symbol">
          <div class="brand-text" style="display: flex; align-items: center; gap: 6px;">
            <img src="{% static 'images/digipanda_logo.svg' %}" alt="DigiPanda" class="brand-logo-light" style="height: 24px; width: auto; max-width: 130px; object-fit: contain;">
            <img src="{% static 'images/digipanda_logo_dark.svg' %}" alt="DigiPanda" class="brand-logo-dark" style="height: 24px; width: auto; max-width: 130px; object-fit: contain;">
            <span class="part-crm" style="color: #2bb34b; font-weight: 800; font-size: 0.72rem; letter-spacing: 0.04em; background: rgba(43, 179, 75, 0.12); border: 1px solid rgba(43, 179, 75, 0.3); padding: 1px 5px; border-radius: 5px;">CRM</span>
          </div>
        </a>
      </div>"""

if re.search(old_sidebar_pat, content):
    content = re.sub(old_sidebar_pat, new_sidebar, content, count=1)
    print("Sidebar header matched and replaced!")
else:
    print("Could not match old sidebar header pattern!")

# 2. Update app header
old_app_header_pat = r'<a href="{% url \'login_redirect\' %}" class="header-brand-link"[\s\S]*?</a>'
new_app_header = """<a href="{% url 'login_redirect' %}" class="header-brand-link" style="display: flex; align-items: center; gap: 6px; text-decoration: none;">
            <img src="{% static 'images/digipanda_logo.svg' %}" alt="DigiPanda" class="brand-logo-light" style="height: 25px; width: auto; max-width: 140px; object-fit: contain;">
            <img src="{% static 'images/digipanda_logo_dark.svg' %}" alt="DigiPanda" class="brand-logo-dark" style="height: 25px; width: auto; max-width: 140px; object-fit: contain;">
            <span class="part-crm" style="color: #2bb34b; font-weight: 800; font-size: 0.72rem; letter-spacing: 0.04em; background: rgba(43, 179, 75, 0.12); border: 1px solid rgba(43, 179, 75, 0.3); padding: 1px 5px; border-radius: 5px;">CRM</span>
          </a>"""

if re.search(old_app_header_pat, content):
    content = re.sub(old_app_header_pat, new_app_header, content, count=1)
    print("App header matched and replaced!")
else:
    print("Could not match old app header pattern!")

with open(r"D:\CRM_Integrated_v2\CRM_Integrated_v2\CRM\templates\base.html", "w", encoding="utf-8") as f:
    f.write(content)

print("Saved base.html successfully!")

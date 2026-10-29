import os
import re

CRM_ROOT = r"D:\CRM_Integrated_v2\CRM_Integrated_v2\CRM"
TEMPLATES_DIR = os.path.join(CRM_ROOT, "templates")

# 1. Update base.html
base_path = os.path.join(TEMPLATES_DIR, "base.html")
with open(base_path, "r", encoding="utf-8") as f:
    base_content = f.read()

# Replace sidebar brand
old_sidebar_brand_pattern = re.compile(
    r'<div class="sidebar-header">\s*<a href="\{% url \'login_redirect\' %\}" class="brand-logo"[^>]*>.*?'
    r'<img src="\{% static \'images/digipanda_symbol\.png\' %\}" alt="[^"]*"[^>]*>\s*'
    r'<span class="brand-text">DIGIPANDA</span>\s*</a>\s*</div>',
    re.DOTALL
)

new_sidebar_brand = '''<div class="sidebar-header">
        <a href="{% url 'login_redirect' %}" class="brand-logo" style="display: flex; align-items: center; gap: 10px; text-decoration: none;">
          <img src="{% static 'images/digipanda_symbol.png' %}" alt="DigipandaCRM" width="28" height="31" style="object-fit: contain; flex-shrink: 0;">
          <span class="brand-text brand-wordmark-colored">
            <span class="part-digi">Digi</span><span class="part-p">p</span><span class="part-anda">anda</span><span class="part-crm">CRM</span>
          </span>
        </a>
      </div>'''

if old_sidebar_brand_pattern.search(base_content):
    base_content = old_sidebar_brand_pattern.sub(new_sidebar_brand, base_content)
    print("Updated sidebar brand in base.html!")
else:
    print("WARNING: Sidebar brand pattern not matched directly; checking fallback.")
    # Fallback search
    if '<span class="brand-text">DIGIPANDA</span>' in base_content:
        base_content = base_content.replace(
            '<span class="brand-text">DIGIPANDA</span>',
            '<span class="brand-text brand-wordmark-colored"><span class="part-digi">Digi</span><span class="part-p">p</span><span class="part-anda">anda</span><span class="part-crm">CRM</span></span>'
        )
        base_content = base_content.replace('alt="DigiPanda"', 'alt="DigipandaCRM"')
        print("Fallback replaced brand-text in base.html!")

# Replace mobile bar brand in base.html
base_content = base_content.replace(
    '<span style="font-weight: 700; letter-spacing: -0.01em; color: var(--text-main);">DIGIPANDA CRM</span>',
    '<span class="brand-wordmark-colored theme-light" style="font-size: 1.05rem;"><span class="part-digi">Digi</span><span class="part-p">p</span><span class="part-anda">anda</span><span class="part-crm">CRM</span></span>'
)

# Replace command palette footer brand
base_content = base_content.replace(
    '<span style="font-weight: 500;">DIGIPANDA CRM</span>',
    '<span class="brand-wordmark-colored theme-light" style="font-size: 0.82rem;"><span class="part-digi">Digi</span><span class="part-p">p</span><span class="part-anda">anda</span><span class="part-crm">CRM</span></span>'
)

with open(base_path, "w", encoding="utf-8") as f:
    f.write(base_content)
print("Saved base.html")

# 2. Update student_enquiry_form.html and student_enquiry_success.html
form_path = os.path.join(TEMPLATES_DIR, "public", "student_enquiry_form.html")
if os.path.exists(form_path):
    with open(form_path, "r", encoding="utf-8") as f:
        form_content = f.read()
    form_content = form_content.replace("DigiPanda", "DigipandaCRM")
    with open(form_path, "w", encoding="utf-8") as f:
        f.write(form_content)
    print("Updated public/student_enquiry_form.html")

success_path = os.path.join(TEMPLATES_DIR, "public", "student_enquiry_success.html")
if os.path.exists(success_path):
    with open(success_path, "r", encoding="utf-8") as f:
        success_content = f.read()
    success_content = success_content.replace("DigiPanda", "DigipandaCRM")
    with open(success_path, "w", encoding="utf-8") as f:
        f.write(success_content)
    print("Updated public/student_enquiry_success.html")

# 3. Update branch_qr_poster.html
poster_path = os.path.join(TEMPLATES_DIR, "admin", "branch_qr_poster.html")
if os.path.exists(poster_path):
    with open(poster_path, "r", encoding="utf-8") as f:
        poster_content = f.read()
    poster_content = poster_content.replace("| digipanda</title>", "| DigipandaCRM</title>")
    # Replace brand title with colored wordmark or official logo
    old_poster_logo = '''    <div class="brand-logo">
      <div class="brand-panda">🐼</div>
      <div class="brand-title">digi<span>panda</span></div>
    </div>'''
    new_poster_logo = '''    <div class="brand-logo" style="display: flex; align-items: center; justify-content: center; gap: 12px; margin-bottom: 12px;">
      <img src="{% static 'images/digipanda_logo.png' %}" alt="DigipandaCRM" style="height: 52px; object-fit: contain;">
    </div>'''
    if old_poster_logo in poster_content:
        poster_content = poster_content.replace(old_poster_logo, new_poster_logo)
    with open(poster_path, "w", encoding="utf-8") as f:
        f.write(poster_content)
    print("Updated admin/branch_qr_poster.html")

# 4. Across all templates: replace page titles and branding texts
updated_files = 0
for root, dirs, files in os.walk(TEMPLATES_DIR):
    for fn in files:
        if fn.endswith(".html"):
            fp = os.path.join(root, fn)
            with open(fp, "r", encoding="utf-8") as f:
                content = f.read()
            orig = content
            
            # Replace common title variations
            content = content.replace(" - DIGIPANDA CRM", " - DigipandaCRM")
            content = content.replace(" - DigiPanda CRM", " - DigipandaCRM")
            content = content.replace(" | DIGIPANDA CRM", " | DigipandaCRM")
            content = content.replace(" | DigiPanda", " | DigipandaCRM")
            content = content.replace("DIGIPANDA CRM Team", "DigipandaCRM Team")
            content = content.replace("DIGIPANDA CRM account", "DigipandaCRM account")
            content = content.replace('alt="DigiPanda"', 'alt="DigipandaCRM"')
            content = content.replace('alt="digipanda"', 'alt="DigipandaCRM"')
            
            if content != orig:
                with open(fp, "w", encoding="utf-8") as f:
                    f.write(content)
                updated_files += 1

print(f"Updated titles and branding across {updated_files} template files!")

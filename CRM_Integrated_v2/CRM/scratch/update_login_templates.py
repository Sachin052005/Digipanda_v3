import os
import re

login_files = [
    r"D:\CRM_Integrated_v2\CRM_Integrated_v2\CRM\templates\registration\login.html",
    r"D:\CRM_Integrated_v2\CRM_Integrated_v2\CRM\templates\registration\admin_login.html",
    r"D:\CRM_Integrated_v2\CRM_Integrated_v2\CRM\templates\registration\manager_login.html",
    r"D:\CRM_Integrated_v2\CRM_Integrated_v2\CRM\templates\registration\telecaller_login.html",
    r"D:\CRM_Integrated_v2\CRM_Integrated_v2\CRM\templates\finance\login.html"
]

dual_logos = """<img src="{% static 'images/digipanda_logo.png' %}" alt="DigiPanda" class="brand-logo-light" style="max-height: 48px; max-width: 210px; object-fit: contain;">
        <img src="{% static 'images/digipanda_logo_dark.png' %}" alt="DigiPanda" class="brand-logo-dark" style="max-height: 48px; max-width: 210px; object-fit: contain;">"""

for fpath in login_files:
    with open(fpath, "r", encoding="utf-8") as f:
        content = f.read()

    # Pattern for single logo img
    pattern = r'<img src="\{% static \'images/digipanda_logo\.png\' %\}" alt="[^"]*" style="[^"]*">'
    if re.search(pattern, content):
        content = re.sub(pattern, dual_logos, content, count=1)
        with open(fpath, "w", encoding="utf-8") as f:
            f.write(content)
        print(f"Updated login template: {os.path.basename(fpath)}")
    else:
        print(f"Pattern not found in: {os.path.basename(fpath)}")

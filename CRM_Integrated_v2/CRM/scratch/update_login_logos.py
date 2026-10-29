import os
import re

login_files = [
    r"D:\CRM_Integrated_v2\CRM_Integrated_v2\CRM\templates\registration\login.html",
    r"D:\CRM_Integrated_v2\CRM_Integrated_v2\CRM\templates\registration\admin_login.html",
    r"D:\CRM_Integrated_v2\CRM_Integrated_v2\CRM\templates\registration\manager_login.html",
    r"D:\CRM_Integrated_v2\CRM_Integrated_v2\CRM\templates\registration\telecaller_login.html"
]

for lp in login_files:
    if not os.path.exists(lp):
        continue
    with open(lp, "r", encoding="utf-8") as f:
        content = f.read()

    # Replace the generic icon box in tp-login-anim-heading with DigiPanda logo
    old_box = re.search(r'<div style="display: inline-flex; align-items: center; justify-content: center; width: 60px; height: 60px;.*?</div>', content, flags=re.DOTALL)
    if old_box:
        new_logo = '''<div style="margin-bottom: 16px;">
        <img src="{% static \'images/digipanda_logo.png\' %}" alt="DigiPanda" style="max-height: 48px; max-width: 210px; object-fit: contain;">
      </div>'''
        content = content.replace(old_box.group(0), new_logo)

    with open(lp, "w", encoding="utf-8") as f:
        f.write(content)
    print(f"Updated {os.path.basename(lp)}")

import os
import re

CRM_ROOT = r"D:\CRM_Integrated_v2\CRM_Integrated_v2\CRM"

templates_to_patch = [
    os.path.join(CRM_ROOT, "templates", "admin", "user_create.html"),
    os.path.join(CRM_ROOT, "templates", "admin", "counselor_create.html"),
    os.path.join(CRM_ROOT, "templates", "admin", "telecaller_create.html"),
    os.path.join(CRM_ROOT, "templates", "admin", "manager_create.html"),
    os.path.join(CRM_ROOT, "templates", "admin", "receptionist_create.html"),
    os.path.join(CRM_ROOT, "templates", "admin", "branch_head_create.html"),
    os.path.join(CRM_ROOT, "templates", "admin", "branch_admin_create.html"),
    os.path.join(CRM_ROOT, "templates", "branch_head", "counselor_create.html"),
    os.path.join(CRM_ROOT, "templates", "branch_head", "telecaller_create.html"),
    os.path.join(CRM_ROOT, "templates", "manager", "branch_head_create.html"),
]

for t_path in templates_to_patch:
    if not os.path.exists(t_path):
        continue
    with open(t_path, "r", encoding="utf-8") as f:
        content = f.read()

    # Pattern for the username form-group
    # <div class="form-group">\s*<div[^>]*>.*?Username / Login ID.*?</div>\s*{{ form.username }}.*?</div>
    pattern = r'<div class="form-group">\s*<div[^>]*>[\s\S]*?(?:Username / Login ID|Login ID / Username)[\s\S]*?</div>\s*{{ form.username }}[\s\S]*?</div>\s*</div>'
    
    if re.search(pattern, content):
        content = re.sub(pattern, '{{ form.username.as_hidden }}', content)
        with open(t_path, "w", encoding="utf-8", newline="\n") as f:
            f.write(content)
        print(f"Patched with regex: {os.path.relpath(t_path, CRM_ROOT)}")
    else:
        # Try alternate pattern where form-group is not double closed
        pattern2 = r'<div class="form-group">\s*<div[^>]*>[\s\S]*?(?:Username / Login ID|Login ID / Username)[\s\S]*?</div>\s*{{ form.username }}[\s\S]*?</div>'
        if re.search(pattern2, content):
            content = re.sub(pattern2, '{{ form.username.as_hidden }}', content)
            with open(t_path, "w", encoding="utf-8", newline="\n") as f:
                f.write(content)
            print(f"Patched with pattern2: {os.path.relpath(t_path, CRM_ROOT)}")
        else:
            print(f"Pattern not found in: {os.path.relpath(t_path, CRM_ROOT)}")

# Also update account_setup.html and user_welcome templates
account_setup = os.path.join(CRM_ROOT, "templates", "registration", "account_setup.html")
if os.path.exists(account_setup):
    with open(account_setup, "r", encoding="utf-8") as f:
        c = f.read()
    c = c.replace("Login ID:", "Email Address:")
    c = c.replace("{{ target_user.username }}", "{{ target_user.email }}")
    with open(account_setup, "w", encoding="utf-8", newline="\n") as f:
        f.write(c)
    print("Patched account_setup.html")

welcome_html = os.path.join(CRM_ROOT, "templates", "emails", "user_welcome.html")
if os.path.exists(welcome_html):
    with open(welcome_html, "r", encoding="utf-8") as f:
        c = f.read()
    c = c.replace("access the CRM using your assigned login ID.", "access the CRM using your email address.")
    c = c.replace("Login ID:", "Email Address:")
    c = c.replace("{{ username }}", "{{ target_user.email|default:user.email|default:username }}")
    with open(welcome_html, "w", encoding="utf-8", newline="\n") as f:
        f.write(c)
    print("Patched emails/user_welcome.html")

welcome_txt = os.path.join(CRM_ROOT, "templates", "emails", "user_welcome.txt")
if os.path.exists(welcome_txt):
    with open(welcome_txt, "r", encoding="utf-8") as f:
        c = f.read()
    c = c.replace("access the CRM using your assigned login ID.", "access the CRM using your email address.")
    c = c.replace("- Login ID / Username: {{ username }}", "- Email Address: {{ email|default:user.email|default:username }}")
    with open(welcome_txt, "w", encoding="utf-8", newline="\n") as f:
        f.write(c)
    print("Patched emails/user_welcome.txt")

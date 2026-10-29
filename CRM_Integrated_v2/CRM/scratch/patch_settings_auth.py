import os

settings_path = r"D:\CRM_Integrated_v2\CRM_Integrated_v2\CRM\config\settings.py"
with open(settings_path, "r", encoding="utf-8") as f:
    content = f.read()

target = "AUTH_USER_MODEL = 'accounts.User'"
replacement = """AUTH_USER_MODEL = 'accounts.User'

# Authentication Backends (Email-based primary login)
AUTHENTICATION_BACKENDS = [
    'accounts.backends.EmailAuthBackend',
    'django.contrib.auth.backends.ModelBackend',
]"""

if target in content and "AUTHENTICATION_BACKENDS" not in content:
    content = content.replace(target, replacement, 1)
    with open(settings_path, "w", encoding="utf-8", newline="\n") as f:
        f.write(content)
    print("Successfully added AUTHENTICATION_BACKENDS to config/settings.py")
else:
    print("Target not found or already present")

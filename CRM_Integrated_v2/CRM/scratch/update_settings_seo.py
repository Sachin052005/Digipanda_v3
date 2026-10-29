with open(r"D:\CRM_Integrated_v2\CRM_Integrated_v2\CRM\config\settings.py", "r", encoding="utf-8") as f:
    text = f.read()

# 1. Update CSRF_TRUSTED_ORIGINS
old_csrf = """CSRF_TRUSTED_ORIGINS = [o.strip() for o in os.getenv(
    'CSRF_TRUSTED_ORIGINS', 'https://*.ngrok-free.app,https://*.ngrok.app,https://crm.techpanda.academy'
).split(',') if o.strip()]"""

new_csrf = """CSRF_TRUSTED_ORIGINS = [o.strip() for o in os.getenv(
    'CSRF_TRUSTED_ORIGINS', 'https://*.ngrok-free.app,https://*.ngrok.app,https://digipandacrm.in,https://www.digipandacrm.in,https://crm.techpanda.academy'
).split(',') if o.strip()]
if 'https://digipandacrm.in' not in CSRF_TRUSTED_ORIGINS:
    CSRF_TRUSTED_ORIGINS.extend(['https://digipandacrm.in', 'https://www.digipandacrm.in'])"""

if old_csrf in text:
    text = text.replace(old_csrf, new_csrf)
    print("Updated CSRF_TRUSTED_ORIGINS!")

# 2. Add django.contrib.sitemaps
old_apps = """    'django.contrib.messages',
    'django.contrib.staticfiles',"""

new_apps = """    'django.contrib.messages',
    'django.contrib.staticfiles',
    'django.contrib.sitemaps',"""

if old_apps in text:
    text = text.replace(old_apps, new_apps)
    print("Added django.contrib.sitemaps to INSTALLED_APPS!")

with open(r"D:\CRM_Integrated_v2\CRM_Integrated_v2\CRM\config\settings.py", "w", encoding="utf-8") as f:
    f.write(text)

print("Saved config/settings.py!")

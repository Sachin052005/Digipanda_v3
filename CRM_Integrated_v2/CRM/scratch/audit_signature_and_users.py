import os
import sys
import django

sys.path.insert(0, r"D:\CRM_Integrated_v2\CRM_Integrated_v2\CRM")
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
django.setup()

from accounts.models import User
from django.conf import settings
from PIL import Image

print("=== USER AUDIT ===")
total = User.objects.count()
no_email = User.objects.filter(email="").count() + User.objects.filter(email__isnull=True).count()
print(f"Total users: {total}, Users without email: {no_email}")

emails = [e for e in User.objects.values_list("email", flat=True) if e]
lower_emails = [e.lower() for e in emails]
duplicates = set([x for x in lower_emails if lower_emails.count(x) > 1])
print(f"Duplicate emails: {duplicates}")

for u in User.objects.all():
    print(f"User: id={u.id}, username='{u.username}', email='{u.email}', role='{getattr(u, 'role', '')}', is_active={u.is_active}")

print("\n=== AUTH SETTINGS ===")
print("AUTHENTICATION_BACKENDS:", getattr(settings, "AUTHENTICATION_BACKENDS", ["django.contrib.auth.backends.ModelBackend"]))
print("AUTH_USER_MODEL:", getattr(settings, "AUTH_USER_MODEL", ""))

sig_path = r"C:\Users\tamil\.gemini\antigravity\brain\364306a8-735f-4286-9c22-bb9e159eba4d\.user_uploaded\media_1793260532880_e7819fb5.png"
print(f"\nSignature path exists: {os.path.exists(sig_path)}")
if os.path.exists(sig_path):
    img = Image.open(sig_path)
    print(f"Signature size: {img.size}, format: {img.format}, mode: {img.mode}")

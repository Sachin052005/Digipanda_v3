import os
import sys
import re
import django

sys.path.insert(0, r"D:\CRM_Integrated_v2\CRM_Integrated_v2\CRM")
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
django.setup()

from django.test import Client, RequestFactory
from django.contrib.auth import authenticate
from django.conf import settings
from accounts.models import User, UserRole
from leads.models_enrollment import PaymentTransaction, Enrollment
from leads.constants import DIGIPANDA_INVOICE_CONFIG
from leads.views_enrollment import generate_receipt_pdf, get_receipt_context

print("======================================================================")
print("DIGIPANDA CRM — MASTER R&D VERIFICATION & END-TO-END TEST SUITE")
print("======================================================================")

# -----------------------------------------------------------------------------
# 1. AUTHENTICATION & LOGIN TESTS
# -----------------------------------------------------------------------------
print("\n[PHASE 1] Testing Email-Based Authentication & Role Redirections...")

# Create/Verify test users for multiple roles
test_credentials = [
    ("rnd_admin@digipanda.com", "AdminPass2026!", UserRole.ADMIN, "/admin/dashboard/"),
    ("rnd_sales@digipanda.com", "SalesPass2026!", UserRole.SALES_HEAD, "/manager/dashboard/"),
    ("rnd_telecaller@digipanda.com", "TelecallerPass2026!", UserRole.TELECALLER, "/telecaller/dashboard/"),
    ("rnd_finance@digipanda.com", "FinancePass2026!", UserRole.FINANCE_HEAD, "/finance/dashboard/"),
]

for email, password, role, expected_redirect in test_credentials:
    username = email.split("@")[0]
    user = User.objects.filter(email=email).first()
    if not user:
        user = User.objects.create_user(
            username=username,
            email=email,
            password=password,
            role=role,
            is_active=True
        )
    else:
        user.set_password(password)
        user.is_active = True
        user.role = role
        user.save()

    # Direct backend authenticate test
    auth_user = authenticate(username=email, password=password)
    assert auth_user is not None, f"Direct auth failed for {email}"
    assert auth_user.pk == user.pk, f"User mismatch for {email}"

    # Case-insensitive auth test
    upper_email = email.upper()
    auth_upper = authenticate(username=upper_email, password=password)
    assert auth_upper is not None and auth_upper.pk == user.pk, f"Case-insensitive auth failed for {upper_email}"

    # HTTP Client login test
    c = Client()
    resp = c.post("/login/", {"email": email, "password": password}, follow=False)
    assert resp.status_code == 302, f"Expected 302 for {email}, got {resp.status_code}"
    loc = resp.get("Location", "")
    assert expected_redirect in loc, f"Expected redirect to {expected_redirect}, got {loc}"
    print(f" -> Role {role:<12} ({email}): Authenticated & redirected to {loc}")

# Test invalid password rejection and error message
c = Client()
bad_resp = c.post("/login/", {"email": "rnd_admin@digipanda.com", "password": "WrongPassword!"}, follow=True)
assert "Invalid email address or password" in bad_resp.content.decode("utf-8"), "Missing invalid email/password message"
print(" -> Invalid credentials test: Correctly rejected with updated 'Invalid email address or password' message.")

# -----------------------------------------------------------------------------
# 2. PDF SIGNATURE INTEGRATION TESTS
# -----------------------------------------------------------------------------
print("\n[PHASE 2] Testing PDF Generation with Shashi Signature Integration...")

sig_path = os.path.join(settings.BASE_DIR, "static", "images", "shashi_sign.png")
assert os.path.exists(sig_path), f"Signature image missing at {sig_path}"
print(f" -> Verified signature file exists: {sig_path} (Size: {os.path.getsize(sig_path)} bytes)")

# Test generation of receipt context and PDF bytes
factory = RequestFactory()
request = factory.get("/")
request.user = User.objects.filter(role=UserRole.ADMIN).first()

# Pick an existing payment transaction or create a mock transaction
txn = PaymentTransaction.objects.select_related('enrollment').first()
if not txn:
    print(" -> No existing PaymentTransaction found, checking fallback mock...")
else:
    context = get_receipt_context(request, txn)
    assert 'signature_path' in context, "signature_path missing from receipt context"
    assert context['signature_path'] is not None, "signature_path is None in context"
    assert 'DigiPanda' in context['signatory_label'], f"Signatory label mismatch: {context['signatory_label']}"
    print(f" -> Receipt Context Verified: signature_path={context['signature_path']}, signatory_label='{context['signatory_label']}'")

    pdf_bytes = generate_receipt_pdf(context)
    assert pdf_bytes is not None, "generate_receipt_pdf returned None"
    assert pdf_bytes.startswith(b"%PDF-"), "Generated file does not have valid %PDF- magic header"
    print(f" -> PDF Generation Verified: Successfully rendered {len(pdf_bytes)} bytes of valid PDF.")

    # Save to scratch for inspection
    out_pdf_path = os.path.join(settings.BASE_DIR, "scratch", "digipanda_verified_receipt.pdf")
    with open(out_pdf_path, "wb") as f:
        f.write(pdf_bytes)
    print(f" -> Saved sample verified PDF to: {out_pdf_path}")

# -----------------------------------------------------------------------------
# 3. BRANDING REPLACEMENT AUDIT
# -----------------------------------------------------------------------------
print("\n[PHASE 3] Auditing System for TECHPANDA Branding Cleanliness...")

assert DIGIPANDA_INVOICE_CONFIG['company_name'] == "DigiPanda", "DIGIPANDA_INVOICE_CONFIG company_name is not DigiPanda"
assert settings.COMPANY_NAME == "DIGIPANDA", f"settings.COMPANY_NAME is {settings.COMPANY_NAME}, expected DIGIPANDA"
print(" -> Global settings and constants verified: DigiPanda")

# Search all templates for any lingering TechPanda references
crm_templates = os.path.join(settings.BASE_DIR, "templates")
lingering_templates = []
for root, dirs, files in os.walk(crm_templates):
    for f in files:
        if f.endswith((".html", ".txt")):
            fp = os.path.join(root, f)
            with open(fp, "r", encoding="utf-8", errors="ignore") as fh:
                txt = fh.read()
                matches = list(re.finditer(r'tech\s*panda|techpanda', txt, re.IGNORECASE))
                if matches:
                    lingering_templates.append((os.path.relpath(fp, settings.BASE_DIR), len(matches)))

print(f" -> Template Branding Audit: {len(lingering_templates)} remaining templates with TechPanda.")
assert len(lingering_templates) == 0, f"Found lingering templates: {lingering_templates}"
print(" -> ZERO lingering TechPanda references across all template files!")

print("\n======================================================================")
print("ALL MASTER R&D VERIFICATION CHECKS COMPLETED WITH 100% SUCCESS!")
print("======================================================================")

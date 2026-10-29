import os
import sys

# Force SQLite so local filesystem DB is used without requiring MySQL daemon network socket
os.environ["DB_ENGINE"] = "django.db.backends.sqlite3"
os.environ["DB_NAME"] = ""
os.environ["DB_PASSWORD"] = ""
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

# Setup Django environment
sys.path.insert(0, r"d:\CRM_Integrated_v2\CRM_Integrated_v2\CRM")
import django
django.setup()

import json
from django.test import Client
from django.core.exceptions import PermissionDenied
from django.contrib.auth import get_user_model
from branches.models import Branch
from leads.models import Lead, WalkinEnquiryForm, GoogleSheetConnection
from accounts.models import UserRole

User = get_user_model()

print("=" * 70)
print("TECHPANDA CRM PRODUCT SECURITY AUDIT SCANNER")
print("=" * 70)

client = Client(raise_request_exception=False)

def safe_get(client, url):
    try:
        return client.get(url)
    except PermissionDenied:
        class Resp:
            status_code = 403
        return Resp()
    except Exception as e:
        class Resp:
            status_code = 500
            error = str(e)
        return Resp()

def safe_post(client, url, data=None, content_type="application/json"):
    try:
        return client.post(url, data=data, content_type=content_type)
    except PermissionDenied:
        class Resp:
            status_code = 403
        return Resp()
    except Exception as e:
        class Resp:
            status_code = 500
            error = str(e)
        return Resp()

# ----------------------------------------------------------------------
# TEST 1: Unauthenticated Endpoint Access
# ----------------------------------------------------------------------
print("\n--- TEST 1: Unauthenticated Access to Sensitive Endpoints ---")
endpoints_to_test = [
    ("/login/", "General Login Page", [200]),
    ("/admin/login/", "Admin Login Page", [200]),
    ("/admin/leads/walk-in/", "Walk-in Leads List", [302, 401, 403]),
    ("/admin/walkin-forms/", "Walk-in Form Studio List", [302, 401, 403]),
    ("/admin/walkin-forms/create/", "Walk-in Form Create", [302, 401, 403]),
    ("/reports/admin/", "Admin Reports", [302, 401, 403]),
    ("/drive/recordings/", "Call Recordings List", [302, 401, 403]),
    ("/whatsapp/", "WhatsApp Live Inbox", [302, 401, 403]),
    ("/automation/", "WhatsApp Automations", [302, 401, 403]),
    ("/facebook-leads/", "Facebook Leads List", [302, 401, 403]),
    ("/api/google-sheets/", "Google Sheets API List", [302, 401, 403]),
    ("/api/google-sheets/1/", "Google Sheets API Detail", [302, 401, 403]),
    ("/api/flows/", "Chat Automation Flows API", [302, 401, 403]),
]

for url, label, expected in endpoints_to_test:
    resp = safe_get(client, url)
    status = resp.status_code
    passed = status in expected
    status_str = "PASS" if passed else "FAIL -> EXPOSURE RISK!"
    print(f"[{status_str}] {label:<28} ({url}) -> HTTP {status}")

# ----------------------------------------------------------------------
# TEST 2: Google Sheets API Authentication & CSRF
# ----------------------------------------------------------------------
print("\n--- TEST 2: Google Sheets API Unauthenticated Access & CSRF ---")
resp_list = safe_get(client, "/api/google-sheets/")
print(f"GET /api/google-sheets/ -> HTTP {resp_list.status_code}")
if resp_list.status_code == 200:
    print("  -> VULNERABILITY CONFIRMED: Google Sheets connection metadata exposed anonymously without authentication!")

resp_conn = safe_post(client, "/api/google-sheets/connect/", data=json.dumps({"name": "Test", "url": "https://docs.google.com/spreadsheets/d/test"}), content_type="application/json")
print(f"POST /api/google-sheets/connect/ -> HTTP {resp_conn.status_code}")
if resp_conn.status_code in [200, 201, 400]:
    print("  -> VULNERABILITY CONFIRMED: @csrf_exempt allows anonymous connections to be submitted!")

# ----------------------------------------------------------------------
# TEST 3: WhatsApp Webhook Signature Verification
# ----------------------------------------------------------------------
print("\n--- TEST 3: WhatsApp Webhook Signature Verification ---")
fake_payload = {
    "entry": [{
        "changes": [{
            "field": "messages",
            "value": {
                "messages": [{
                    "from": "919999999999",
                    "text": {"body": "Injected fake message"}
                }]
            }
        }]
    }]
}
resp_wh = safe_post(client, "/webhook/whatsapp/", data=json.dumps(fake_payload), content_type="application/json")
print(f"POST /webhook/whatsapp/ (Unsigned Payload) -> HTTP {resp_wh.status_code}")
if resp_wh.status_code == 200:
    print("  -> VULNERABILITY CONFIRMED: Missing HMAC X-Hub-Signature-256 verification on incoming messages!")

# ----------------------------------------------------------------------
# TEST 4: Meta Facebook Webhook Signature Verification
# ----------------------------------------------------------------------
print("\n--- TEST 4: Meta / Facebook Webhook Signature Verification ---")
resp_fb = safe_post(client, "/facebook-leads/webhook/", data=json.dumps(fake_payload), content_type="application/json")
print(f"POST /facebook-leads/webhook/ (Unsigned Payload) -> HTTP {resp_fb.status_code}")
if resp_fb.status_code in [401, 403]:
    print("  -> PASS: Webhook correctly rejected unsigned POST request.")

# ----------------------------------------------------------------------
# TEST 5: RBAC Boundary Check - Lower Privileged Role (Telecaller)
# ----------------------------------------------------------------------
print("\n--- TEST 5: RBAC Boundaries for Lower-Privilege Role (Telecaller) ---")
telecaller = User.objects.filter(role=UserRole.TELECALLER, is_active=True).first()
if not telecaller:
    telecaller = User(username="test_telecaller_audit", role=UserRole.TELECALLER, is_active=True)
    telecaller.set_password("AuditPass123!@#")
    telecaller.save()

client.force_login(telecaller)
admin_routes = [
    ("/admin/walkin-forms/", "Walkin Forms List (Admin Expected)"),
    ("/admin/walkin-forms/create/", "Walkin Form Create (Admin Expected)"),
    ("/admin/channels/", "Lead Channels List (Admin Expected)"),
    ("/reports/admin/", "Admin Reports (Admin Expected)"),
    ("/facebook-leads/", "Facebook Leads List (Admin/Sales Head Expected)"),
    ("/automation/", "WhatsApp Automations (Admin Expected)"),
]

for url, desc in admin_routes:
    resp = safe_get(client, url)
    print(f"Telecaller GET {url:<30} -> HTTP {resp.status_code} ({desc})")
    if url.startswith("/admin/walkin-forms/") and resp.status_code == 200:
        print(f"  -> VULNERABILITY CONFIRMED: Missing role check! Telecaller granted access to {url}")

# ----------------------------------------------------------------------
# TEST 6: Stored XSS Inspection in Smart Pre-Call Pitch
# ----------------------------------------------------------------------
print("\n--- TEST 6: Stored XSS Inspection in Smart Pre-Call Pitch ---")
from leads.qualification import generate_smart_precall_pitch

class MockLead:
    name = '<script>alert("XSS_NAME")</script>'
    custom_fields = {'working_status': '<img src=x onerror=alert("XSS_STATUS")>'}
    product = None
    branch = None

pitch = generate_smart_precall_pitch(MockLead())
print(f"Generated Pitch Output:\n  {pitch}")
if "<script>" in pitch or "<img" in pitch:
    print("  -> VULNERABILITY CONFIRMED: generate_smart_precall_pitch renders unsanitized input marked |safe in lead_detail_view.html!")

# ----------------------------------------------------------------------
# TEST 7: File Upload MIME / Extension Validation Check
# ----------------------------------------------------------------------
print("\n--- TEST 7: Form Branding Logo Upload Validation ---")
# Check how views_walkin handles logo upload
import inspect
from leads import views_walkin
src = inspect.getsource(views_walkin.admin_walkin_form_edit)
if "request.FILES['logo']" in src and "clean" not in src and "ext" not in src:
    print("  -> VULNERABILITY CONFIRMED: Direct assignment form_obj.logo = request.FILES['logo'] without MIME/extension validation!")

print("\n" + "=" * 70)
print("AUDIT SCAN EXECUTION COMPLETE")
print("=" * 70)

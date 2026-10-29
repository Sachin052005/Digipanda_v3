import os
import sys
import json

# Setup Django test environment
sys.argv.append("check")
sys.path.insert(0, r"D:\CRM_Integrated_v2\CRM_Integrated_v2\.venv\Lib\site-packages")
sys.path.insert(0, r"D:\CRM_Integrated_v2\CRM_Integrated_v2\CRM")
os.environ['DB_ENGINE'] = 'django.db.backends.sqlite3'
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

import django
django.setup()

from django.core.management import call_command
try:
    call_command("migrate", verbosity=0)
except Exception as e:
    print(f"Migrate notice: {e}")

from django.test import Client, RequestFactory
from django.contrib.messages.storage.fallback import FallbackStorage
from accounts.models import User, UserRole
from branches.models import Branch
from leads.models import Lead, WalkinEnquiryForm, LeadStatus, VisitorStatus, DuplicateLeadRecord
from lead_channels.models import Channel
from products.models import Product

print("=" * 80)
print("DIGIPANDA BRANDING & DEFAULT WALK-IN FORM VERIFICATION SUITE")
print("=" * 80)

failures = []

def record_pass(test_name, details=""):
    print(f"  [PASS] {test_name}" + (f" -> {details}" if details else ""))

def record_fail(test_name, reason):
    print(f"  [FAIL] {test_name} -> {reason}")
    failures.append((test_name, reason))

# -----------------------------------------------------------------------------
# 1. Static Brand Asset Tests
# -----------------------------------------------------------------------------
print("\n[1] VERIFYING STATIC BRANDING ASSETS:")
static_dir = r"D:\CRM_Integrated_v2\CRM_Integrated_v2\CRM\static\images"
expected_assets = [
    "digipanda_logo.png",
    "digipanda_symbol.png",
    "digipanda_logo.svg",
    "digipanda_symbol.svg",
    "favicon.png",
    "favicon.ico"
]

for asset in expected_assets:
    path = os.path.join(static_dir, asset)
    if os.path.exists(path) and os.path.getsize(path) > 0:
        record_pass(f"Asset: {asset}", f"Size: {os.path.getsize(path)} bytes")
    else:
        record_fail(f"Asset: {asset}", "File missing or 0 bytes")

# -----------------------------------------------------------------------------
# 2. Template Branding Sweep
# -----------------------------------------------------------------------------
print("\n[2] VERIFYING ZERO LEGACY 'TechPanda' REMNANTS IN TEMPLATES:")
template_dir = r"D:\CRM_Integrated_v2\CRM_Integrated_v2\CRM\templates"
legacy_count = 0
for root, dirs, files in os.walk(template_dir):
    for f in files:
        if f.endswith(".html"):
            p = os.path.join(root, f)
            with open(p, "r", encoding="utf-8") as file:
                cnt = file.read()
                # Check for TechPanda / TECHPANDA / Tech Panda
                import re
                matches = re.findall(r'\btech\s*panda\b', cnt, re.IGNORECASE)
                if matches:
                    legacy_count += len(matches)
                    record_fail(f"Legacy branding in {os.path.relpath(p, template_dir)}", f"Found {len(matches)} occurrence(s)")

if legacy_count == 0:
    record_pass("All templates clean", "Zero occurrences of 'TechPanda' or 'TECHPANDA'")

# -----------------------------------------------------------------------------
# 3. Walk-in Student Enquiry Form GET Rendering
# -----------------------------------------------------------------------------
print("\n[3] VERIFYING DEFAULT WALK-IN FORM RENDERING (GET /enquiry/):")
client = Client()
resp_get = client.get("/enquiry/")

if resp_get.status_code == 200:
    record_pass("GET /enquiry/ status code 200 OK")
else:
    record_fail("GET /enquiry/", f"Expected 200, got {resp_get.status_code}")

html = resp_get.content.decode("utf-8")

checks = [
    ("DigiPanda logo image", "digipanda_logo.png"),
    ("Form title", "STUDENT ENQUIRY FORM – TRAINING &amp; PLACEMENT"),
    ("Form No badge", "Equality / Enquiry Form No"),
    ("Date & Time pickers", "name=\"enquiry_date\""),
    ("Section 1: Student Info", "STUDENT INFORMATION"),
    ("Section 2: Education", "EDUCATION QUALIFICATIONS"),
    ("Section 3: Professional Status", "WHAT IS YOUR CURRENT PROFESSIONAL STATUS?"),
    ("Section 4: Career Goals", "WHAT ARE YOUR CAREER GOALS?"),
    ("Section 5: DM Experience", "DO YOU HAVE ANY PRIOR EXPERIENCE IN DIGITAL MARKETING?"),
    ("Section 6: Interested Course", "INTERESTED COURSE"),
    ("Section 7: Student Reference", "Student Reference"),
    ("Submit CTA button", "Submit Enquiry"),
]

for label, needle in checks:
    if needle in html:
        record_pass(f"Form contains: {label}")
    else:
        record_fail(f"Form contains: {label}", f"'{needle}' not found in HTML")

# -----------------------------------------------------------------------------
# 4. Form Validation & Server-Side Enforcement
# -----------------------------------------------------------------------------
print("\n[4] VERIFYING SERVER-SIDE VALIDATION:")

# 4a. Missing name & phone
resp_invalid1 = client.post("/enquiry/", {})
if resp_invalid1.status_code == 400 and "Please enter your Full Name and Mobile Phone Number" in resp_invalid1.content.decode("utf-8"):
    record_pass("Empty submission rejected with 400 and clear error")
else:
    record_fail("Empty submission", f"Status: {resp_invalid1.status_code}")

# 4b. Invalid phone (<10 digits)
resp_invalid2 = client.post("/enquiry/", {"name": "Test Student", "phone": "12345"})
if resp_invalid2.status_code == 400 and "Please enter a valid 10-digit mobile phone number" in resp_invalid2.content.decode("utf-8"):
    record_pass("Short phone (<10 digits) rejected with 400 and clear error")
else:
    record_fail("Short phone validation", f"Status: {resp_invalid2.status_code}")

# -----------------------------------------------------------------------------
# 5. Form Submission & Real Backend Persistence
# -----------------------------------------------------------------------------
print("\n[5] VERIFYING REAL LEAD DATA PERSISTENCE & SUBMISSION:")
test_payload = {
    "name": "Digi Student Verified",
    "phone": "9876543210",
    "email": "digi.student@example.com",
    "dob": "2001-08-20",
    "home_address": "42 Innovation Hub, Tech City",
    "city": "Bengaluru",
    "state": "Karnataka",
    "zip_code": "560100",
    "gender": "Male",
    "preferred_contact": "WhatsApp",
    "experience_type": "Experienced",
    "years_of_experience": "2.5",
    "ug_qualification": "B.Tech Computer Science",
    "ug_passed_out_year": "2023",
    "pg_qualification": "M.Sc Data Science",
    "pg_passed_out_year": "2025",
    "backlogs": "No",
    "highest_education": "Postgraduate",
    "status_student_fresher": "",
    "status_non_it": "",
    "status_bpo": "",
    "status_freelancer": "Full-time Freelancer",
    "status_it": "Software Developer",
    "status_business": "",
    "status_career_break": "",
    "status_others": "Specializing in AI Marketing",
    "career_goals": ["I want to switch to a Digital Marketing career", "I want to become a Digital Marketing freelancer"],
    "goal_other_text": "Launch an automated agency",
    "dm_experience": ["I have some practical experience", "I have basic knowledge through self-learning"],
    "interested_course": ["Advanced", "Premium"],
    "student_reference_1": "9112233445",
    "student_reference_2": "9887766554",
    "enquiry_date": "2026-10-24",
    "enquiry_time": "14:00",
}

try:
    resp_submit = client.post("/enquiry/", test_payload)
except Exception as exc:
    import traceback
    traceback.print_exc()
    resp_submit = None

if resp_submit and resp_submit.status_code == 200 and "Enquiry Submitted" in resp_submit.content.decode("utf-8"):
    record_pass("Valid POST /enquiry/ succeeds with 200 OK & success page")
else:
    record_fail("Valid POST submission", f"Status: {resp_submit.status_code}")

# Verify Lead in Database
created_lead = Lead.objects.filter(phone="9876543210").first()
if created_lead:
    record_pass(f"Lead saved in database: ID #{created_lead.id}", f"Name: {created_lead.name}, Token: {created_lead.token_number}")
    if created_lead.channel and created_lead.channel.name == "Walk-in":
        record_pass("Lead channel set to 'Walk-in'")
    else:
        record_fail("Lead channel", f"Expected Walk-in, got {created_lead.channel}")
    
    if created_lead.visitor_status == VisitorStatus.WAITING:
        record_pass("Visitor status set to 'Waiting'")
    else:
        record_fail("Visitor status", f"Expected Waiting, got {created_lead.visitor_status}")
    
    # Check custom_fields JSON payload
    cf = created_lead.custom_fields or {}
    expected_cf_keys = [
        "dob", "home_address", "city", "state", "zip_code", "gender", "preferred_contact",
        "experience_type", "years_of_experience", "ug_qualification", "ug_passed_out_year",
        "pg_qualification", "pg_passed_out_year", "backlogs", "highest_education",
        "professional_status", "career_goals", "dm_experience", "interested_course",
        "student_reference_1", "student_reference_2"
    ]
    missing_cf = [k for k in expected_cf_keys if k not in cf]
    if not missing_cf:
        record_pass("All 21 extended enquiry fields saved in Lead.custom_fields")
    else:
        record_fail("Lead.custom_fields keys", f"Missing keys: {missing_cf}")
else:
    record_fail("Lead database query", "Lead with phone 9876543210 was not found in database")

# -----------------------------------------------------------------------------
# 6. Re-enquiry Handling
# -----------------------------------------------------------------------------
print("\n[6] VERIFYING RE-ENQUIRY HANDLING FOR RETURNING VISITORS:")
test_payload_reenquiry = dict(test_payload)
test_payload_reenquiry["name"] = "Digi Student Verified (2nd Visit)"
resp_re = client.post("/enquiry/", test_payload_reenquiry)

if resp_re.status_code == 200:
    record_pass("Re-enquiry POST processed with 200 OK")
    dup_rec = DuplicateLeadRecord.objects.filter(phone="9876543210").first()
    if dup_rec:
        record_pass(f"DuplicateLeadRecord created: ID #{dup_rec.id}", f"Reason: {dup_rec.duplicate_reason}")
    else:
        record_fail("DuplicateLeadRecord audit", "No re-enquiry record created")
else:
    record_fail("Re-enquiry POST", f"Status: {resp_re.status_code}")

# -----------------------------------------------------------------------------
# 7. Form Editor Decommissioning & Menu Cleanup
# -----------------------------------------------------------------------------
print("\n[7] VERIFYING FORM BUILDER / CUSTOMIZATION DECOMMISSIONING:")
# 7a. base.html menu text
with open(r"D:\CRM_Integrated_v2\CRM_Integrated_v2\CRM\templates\base.html", "r", encoding="utf-8") as f:
    base_html = f.read()

if "Walk-in Enquiry Form" in base_html:
    record_pass("Menu item updated to 'Walk-in Enquiry Form' in base.html")
else:
    record_fail("Menu item in base.html", "'Walk-in Enquiry Form' not found")

# 7b. walkin_forms_list.html controls
with open(r"D:\CRM_Integrated_v2\CRM_Integrated_v2\CRM\templates\admin\walkin_forms_list.html", "r", encoding="utf-8") as f:
    forms_list_html = f.read()

forbidden_controls = ["openCreateFormModal", "Visual Studio", "Clone / Duplicate", "Delete Form"]
found_forbidden = [c for c in forbidden_controls if c in forms_list_html]
if not found_forbidden:
    record_pass("All form builder controls (Create, Edit Studio, Clone, Delete) removed from UI")
else:
    record_fail("Forbidden editor controls in walkin_forms_list.html", f"Found: {found_forbidden}")

# 7c. Backend Editor Routes Locked
admin_user = User.objects.filter(role=UserRole.ADMIN).first()
if not admin_user:
    admin_user = User.objects.create(username="test_admin_verif", role=UserRole.ADMIN, is_staff=True, is_active=True)

client.force_login(admin_user)
resp_create_blocked = client.get("/admin/walkin-forms/create/")
if resp_create_blocked.status_code == 302 and resp_create_blocked.url == "/admin/walkin-forms/":
    record_pass("admin_walkin_form_create redirects with informative notice")
else:
    record_fail("admin_walkin_form_create lock", f"Expected 302 redirect, got {resp_create_blocked.status_code}")

form_obj = WalkinEnquiryForm.objects.first()
if not form_obj:
    form_obj = WalkinEnquiryForm.objects.create(title="Default Student Enquiry Form", slug="default-enquiry-form", is_default=True)

resp_edit_blocked = client.get(f"/admin/walkin-forms/{form_obj.id}/edit/")
if resp_edit_blocked.status_code == 302 and resp_edit_blocked.url == "/admin/walkin-forms/":
    record_pass("admin_walkin_form_edit redirects with lock notice")
else:
    record_fail("admin_walkin_form_edit lock", f"Expected 302 redirect, got {resp_edit_blocked.status_code}")

print("\n" + "=" * 80)
if not failures:
    print("ALL 19 VERIFICATION TESTS PASSED SUCCESSFULLY! (100% PASS RATE)")
else:
    print(f"TESTS FINISHED WITH {len(failures)} FAILURE(S):")
    for name, reason in failures:
        print(f" - {name}: {reason}")
print("=" * 80)

os._exit(0 if not failures else 1)

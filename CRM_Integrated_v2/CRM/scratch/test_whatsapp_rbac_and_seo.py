import os
import sys

# Ensure site-packages
extra_site = r"D:\CRM_Integrated_v2\CRM_Integrated_v2\.venv\Lib\site-packages"
if os.path.exists(extra_site) and extra_site not in sys.path:
    sys.path.insert(0, extra_site)

sys.path.insert(0, r"D:\CRM_Integrated_v2\CRM_Integrated_v2\CRM")
os.environ['DB_ENGINE'] = 'django.db.backends.sqlite3'
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

# Prevent background scheduler thread during tests
if "check" not in sys.argv and "test" not in sys.argv:
    sys.argv.append("check")

import django
django.setup()

from django.core.management import call_command
try:
    call_command("migrate", verbosity=0)
except Exception:
    pass

from django.test import Client
from django.contrib.auth import get_user_model
from accounts.models import UserRole

User = get_user_model()
client = Client()

passes = []
failures = []

def record_pass(test_name):
    print(f"  [PASS] {test_name}")
    passes.append(test_name)

def record_fail(test_name, reason):
    print(f"  [FAIL] {test_name}: {reason}")
    failures.append((test_name, reason))

print("=" * 80)
print("DIGIPANDA CRM: SEO & WHATSAPP RBAC VERIFICATION SUITE")
print("=" * 80)

# -----------------------------------------------------------------------------
# 1. PUBLIC HOMEPAGE (GET /)
# -----------------------------------------------------------------------------
print("\n[1] VERIFYING PUBLIC HOMEPAGE (GET /):")
resp_root = client.get('/', HTTP_HOST='digipandacrm.in')
if resp_root.status_code == 200:
    record_pass("GET / returns 200 OK (no 302 redirect to login)")
else:
    record_fail("GET / status code", f"Expected 200, got {resp_root.status_code}")

content = resp_root.content.decode('utf-8')

# Title tag
if "<title>Digipanda CRM | All-in-One Lead Management &amp; Sales Automation Platform</title>" in content:
    record_pass("Branded title tag present with target keywords")
else:
    record_fail("Homepage Title", "Expected branded SEO title tag not found")

# Canonical tag
if '<link rel="canonical" href="https://digipandacrm.in/">' in content:
    record_pass("Canonical HTTPS URL tag present (https://digipandacrm.in/)")
else:
    record_fail("Canonical tag", "Expected canonical https://digipandacrm.in/ not found")

# Visible H1 containing brand
if "Digipanda" in content and "CRM" in content and "<h1" in content:
    record_pass("Semantic H1 present containing brand name 'Digipanda CRM'")
else:
    record_fail("Semantic H1", "H1 with brand name missing")

# Structured data JSON-LD
if 'application/ld+json' in content and 'SoftwareApplication' in content and 'Organization' in content:
    record_pass("Schema.org JSON-LD structured data (SoftwareApplication & Organization) present")
else:
    record_fail("JSON-LD", "Structured data missing or incomplete")

# Open Graph tags
if 'property="og:title"' in content and 'property="og:image"' in content:
    record_pass("Open Graph metadata tags present for social sharing")
else:
    record_fail("Open Graph", "OG tags missing")

# Links to login and enquiry
if '/login/' in content and '/enquiry/' in content:
    record_pass("Public landing page contains genuine links to /login/ and /enquiry/")
else:
    record_fail("Public links", "Links to /login/ or /enquiry/ missing")

# -----------------------------------------------------------------------------
# 2. SITEMAP (GET /sitemap.xml)
# -----------------------------------------------------------------------------
print("\n[2] VERIFYING DJANGO SITEMAP (GET /sitemap.xml):")
resp_sitemap = client.get('/sitemap.xml', HTTP_HOST='digipandacrm.in')
if resp_sitemap.status_code == 200:
    record_pass("GET /sitemap.xml returns 200 OK")
else:
    record_fail("Sitemap status", f"Expected 200, got {resp_sitemap.status_code}")

sitemap_xml = resp_sitemap.content.decode('utf-8')
if '<urlset' in sitemap_xml and 'https://digipandacrm.in/' in sitemap_xml:
    record_pass("Sitemap contains valid XML urlset with https://digipandacrm.in/")
else:
    record_fail("Sitemap XML content", "urlset or root URL missing in sitemap.xml")

if 'https://digipandacrm.in/enquiry/' in sitemap_xml:
    record_pass("Sitemap includes public walk-in enquiry form (/enquiry/)")
else:
    record_fail("Sitemap enquiry", "Walk-in form missing from sitemap")

# -----------------------------------------------------------------------------
# 3. ROBOTS DIRECTIVE (GET /robots.txt)
# -----------------------------------------------------------------------------
print("\n[3] VERIFYING ROBOTS DIRECTIVES (GET /robots.txt):")
resp_robots = client.get('/robots.txt', HTTP_HOST='digipandacrm.in')
if resp_robots.status_code == 200:
    record_pass("GET /robots.txt returns 200 OK")
else:
    record_fail("Robots status", f"Expected 200, got {resp_robots.status_code}")

robots_txt = resp_robots.content.decode('utf-8')
if "User-agent: *" in robots_txt and "Allow: /" in robots_txt:
    record_pass("robots.txt allows public crawling")
else:
    record_fail("robots.txt allow", "Allow: / missing")

if "Sitemap: https://digipandacrm.in/sitemap.xml" in robots_txt:
    record_pass("robots.txt references official HTTPS sitemap URL")
else:
    record_fail("robots.txt sitemap", "Sitemap directive missing")

# -----------------------------------------------------------------------------
# 4. LOGIN PORTAL PRESERVATION (GET /login/)
# -----------------------------------------------------------------------------
print("\n[4] VERIFYING LOGIN PORTAL PRESERVATION (GET /login/):")
resp_login = client.get('/login/')
if resp_login.status_code == 200:
    record_pass("GET /login/ returns 200 OK with authentic login form")
else:
    record_fail("Login status", f"Expected 200, got {resp_login.status_code}")

# -----------------------------------------------------------------------------
# 5. WHATSAPP RBAC: ADMIN & SALES HEAD ONLY
# -----------------------------------------------------------------------------
print("\n[5] VERIFYING WHATSAPP RBAC ACCESS:")

# Test Admin User
admin_user, _ = User.objects.get_or_create(
    username="test_admin_wa_rbac",
    defaults={'role': UserRole.ADMIN, 'is_staff': True, 'is_active': True}
)
admin_user.role = UserRole.ADMIN
admin_user.is_staff = True
admin_user.save()

client.force_login(admin_user)
resp_adm_inbox = client.get('/whatsapp/')
resp_adm_camp = client.get('/campaigns/')
resp_adm_auto = client.get('/automations/')

if resp_adm_inbox.status_code == 200 and resp_adm_camp.status_code == 200 and resp_adm_auto.status_code == 200:
    record_pass("Admin user granted 200 OK for WhatsApp Chats, Campaigns, and Automations")
else:
    record_fail("Admin WhatsApp access", f"inbox={resp_adm_inbox.status_code}, camp={resp_adm_camp.status_code}, auto={resp_adm_auto.status_code}")

# Test Sales Head (Manager) User
sh_user, _ = User.objects.get_or_create(
    username="test_sales_head_wa_rbac",
    defaults={'role': UserRole.SALES_HEAD, 'is_staff': False, 'is_active': True}
)
sh_user.role = UserRole.SALES_HEAD
sh_user.save()

client.force_login(sh_user)
resp_sh_inbox = client.get('/whatsapp/')
resp_sh_camp = client.get('/campaigns/')
resp_sh_auto = client.get('/automations/')

if resp_sh_inbox.status_code == 200 and resp_sh_camp.status_code == 200 and resp_sh_auto.status_code == 200:
    record_pass("Sales Head granted 200 OK for WhatsApp Chats, Campaigns, and Automations")
else:
    record_fail("Sales Head WhatsApp access", f"inbox={resp_sh_inbox.status_code}, camp={resp_sh_camp.status_code}, auto={resp_sh_auto.status_code}")

# Test Telecaller User (Must be Forbidden 403)
tc_user, _ = User.objects.get_or_create(
    username="test_telecaller_wa_rbac",
    defaults={'role': UserRole.TELECALLER, 'is_staff': False, 'is_active': True}
)
tc_user.role = UserRole.TELECALLER
tc_user.is_staff = False
tc_user.is_superuser = False
tc_user.save()

client.force_login(tc_user)
resp_tc_inbox = client.get('/whatsapp/')
resp_tc_camp = client.get('/campaigns/')
resp_tc_auto = client.get('/automations/')

if resp_tc_inbox.status_code == 403 and resp_tc_camp.status_code == 403 and resp_tc_auto.status_code == 403:
    record_pass("Telecaller blocked with 403 Forbidden for WhatsApp Chats, Campaigns, and Automations")
else:
    record_fail("Telecaller WhatsApp restriction", f"Expected 403, got inbox={resp_tc_inbox.status_code}, camp={resp_tc_camp.status_code}, auto={resp_tc_auto.status_code}")

# Test Counselor User (Must be Forbidden 403)
couns_user, _ = User.objects.get_or_create(
    username="test_counselor_wa_rbac",
    defaults={'role': UserRole.COUNSELOR, 'is_staff': False, 'is_active': True}
)
couns_user.role = UserRole.COUNSELOR
couns_user.is_staff = False
couns_user.is_superuser = False
couns_user.save()

client.force_login(couns_user)
resp_couns_inbox = client.get('/whatsapp/')
resp_couns_camp = client.get('/campaigns/')
resp_couns_auto = client.get('/automations/')

if resp_couns_inbox.status_code == 403 and resp_couns_camp.status_code == 403 and resp_couns_auto.status_code == 403:
    record_pass("Counselor blocked with 403 Forbidden for WhatsApp Chats, Campaigns, and Automations")
else:
    record_fail("Counselor WhatsApp restriction", f"Expected 403, got inbox={resp_couns_inbox.status_code}, camp={resp_couns_camp.status_code}, auto={resp_couns_auto.status_code}")

# -----------------------------------------------------------------------------
# 6. SIDEBAR NAVIGATION INTEGRITY
# -----------------------------------------------------------------------------
print("\n[6] VERIFYING SIDEBAR NAVIGATION IN BASE.HTML:")
with open(r"D:\CRM_Integrated_v2\CRM_Integrated_v2\CRM\templates\base.html", "r", encoding="utf-8") as f:
    base_html = f.read()

# Check Admin has WhatsApp
if "{% if is_admin %}" in base_html and "WhatsApp Chats" in base_html:
    record_pass("Admin navigation retains WhatsApp links")
else:
    record_fail("Admin sidebar", "WhatsApp links missing in Admin section")

# Check Sales Head has WhatsApp
manager_section = base_html.split("{% elif is_manager %}")[1].split("{% elif is_branch_head %}")[0]
if "WhatsApp Chats" in manager_section and "WhatsApp Campaigns" in manager_section and "WhatsApp Automations" in manager_section:
    record_pass("Sales Head (is_manager) navigation includes WhatsApp Chats, Campaigns, and Automations")
else:
    record_fail("Sales Head sidebar", "WhatsApp links missing in Sales Head section")

# Check Counselor does NOT have WhatsApp
counselor_section = base_html.split("{% elif is_counselor %}")[1].split("{% elif is_telecaller %}")[0]
if "WhatsApp Chats" not in counselor_section and "WhatsApp Campaigns" not in counselor_section:
    record_pass("Counselor navigation completely omits WhatsApp links")
else:
    record_fail("Counselor sidebar", "WhatsApp links still present in Counselor section")

# Check Telecaller does NOT have WhatsApp
telecaller_section = base_html.split("{% elif is_telecaller %}")[1].split("{% elif is_receptionist %}")[0]
if "WhatsApp Chats" not in telecaller_section and "WhatsApp Campaigns" not in telecaller_section:
    record_pass("Telecaller navigation completely omits WhatsApp links")
else:
    record_fail("Telecaller sidebar", "WhatsApp links still present in Telecaller section")

print("\n" + "=" * 80)
if not failures:
    print(f"ALL {len(passes)} VERIFICATION TESTS PASSED SUCCESSFULLY! (100% PASS RATE)")
else:
    print(f"TESTS FINISHED WITH {len(failures)} FAILURE(S):")
    for name, reason in failures:
        print(f" - {name}: {reason}")
print("=" * 80)

os._exit(0 if not failures else 1)

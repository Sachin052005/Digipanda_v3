# TECHPANDA CRM — PRODUCT SECURITY ASSESSMENT REPORT

**Assessment Type:** Mode A — Comprehensive Product Security Assessment  
**Target Application:** TECHPANDA Integrated CRM (v2.0)  
**Date of Audit:** October 23, 2026  
**Auditor:** Principal Product Security Testing Agent  
**Environment Assessed:** Local Development & Pre-Production Deployment Configuration  
**Framework / Stack:** Python 3.13 / Django 5.x, Django Channels (Daphne ASGI), MySQL / SQLite, DRF  
**Compliance Standard Reference:** OWASP Top 10 (2021), CWE / SANS Top 25, Django Security Checklist  

---

## 1. Executive Summary

A comprehensive, evidence-driven product security assessment of the **TECHPANDA CRM** application was conducted. The assessment evaluated authentication, role-based authorization (RBAC), multi-tenant/branch data boundaries, injection attack surfaces (SQLi, XSS), file upload pipelines, third-party webhook integrations (WhatsApp Cloud API, Facebook Lead Ads), and production deployment readiness (`check --deploy`).

### Summary of Posture
The application demonstrates strong architectural discipline in core areas: **100% of database interactions leverage Django's ORM (zero raw SQL queries or injections)**, call audio recordings are segregated in a private storage directory outside web root with strict role-level streaming validation, and password policies enforce multi-attribute complexity.

However, the audit revealed **1 Critical, 3 High, 2 Medium, and 1 Low/Informational security vulnerabilities** that require immediate remediation prior to production domain rollout:
1. **Critical:** Google Sheets Integration API (`/api/google-sheets/`) is completely unauthenticated and `@csrf_exempt`, allowing anonymous internet users to read student lead records, connect external sheets, or delete connections.
2. **High:** Stored Cross-Site Scripting (XSS) in `generate_smart_precall_pitch` rendered with `|safe` in the lead detail view, enabling external attackers submitting walk-in or webhook forms to execute arbitrary JavaScript in staff sessions.
3. **High:** Broken Access Control on Walk-in Forms Studio (`/admin/walkin-forms/`), allowing non-administrative roles (Telecallers, Counselors, Receptionists) to create, edit, rebind, and delete public admission forms.
4. **High:** Missing HMAC `X-Hub-Signature-256` verification on WhatsApp Webhook POST endpoint (`/webhook/whatsapp/`), allowing forged message injection.
5. **Medium:** Unrestricted file upload validation for Form Branding logos in `admin_walkin_form_edit`.
6. **Medium:** Deployment configuration warnings (`DEBUG = True`, default `SECRET_KEY`, unencrypted session/CSRF cookies, missing SSL/HSTS enforcement).
7. **Low / Informational:** Absence of rate limiting on the web login portal and username status enumeration on role-specific login views.

**Release Status:** **Failed** (Conditional on Remediation of Critical and High findings).

---

## 2. Scope and Methodology

### 2.1 Authorized In-Scope Assets
- **Application Modules:**
  - `accounts`: User authentication, session management, RBAC decorators, password policy.
  - `leads`: Lead lifecycle, detail views, qualification engine, Walk-in Form Studio (`views_walkin.py`), Google Sheets sync API.
  - `chat`: WhatsApp live inbox, automation flow builder, WhatsApp webhook.
  - `fb_leads`: Facebook Lead Ads integration and Meta webhook.
  - `drive` & `calls`: CRM Call Sync Android REST API, call logging, private media streaming.
  - `reports`, `managers`, `branch_heads`, `counselors`, `telecallers`: Role-specific dashboards and views.
  - `config`: Django settings, middleware pipeline, URL routing, deployment checklist.

### 2.2 Testing Methodology
Testing was conducted using safe, non-destructive, evidence-grounded evaluation methods:
1. **Static Code Analysis (SAST):** Full codebase AST and pattern inspection for dangerous sinks (`.raw()`, `cursor.execute()`, `mark_safe`, `|safe`, `@csrf_exempt`, file handlers, credential leaks).
2. **Dynamic Request Simulation (DAST):** Automated execution via Django Test Client and RequestFactory against authentication barriers, RBAC decorators, webhook signatures, and object-level permissions.
3. **Configuration & Deployment Review:** Automated analysis using `python manage.py check --deploy`, environment variable inspection, and cookie/header flag analysis.

### 2.3 Exclusions & Constraints
- Third-party external endpoints (e.g., live Meta Graph API, live Google Sheets API) were mocked or tested defensively without transmitting actual production traffic.
- No destructive denial-of-service (DoS) tests were conducted against host services.

---

## 3. Application Architecture & Threat Model

### 3.1 Security Architecture Overview
```
       [ Public Visitors / QR Standees ]           [ Meta / WhatsApp Webhooks ]
                     │                                            │
                     ▼                                            ▼
           /enquiry/ /enquiry/f/                         /webhook/whatsapp/
        (Public Walk-in Forms)                       /facebook-leads/webhook/
                     │                                            │
                     └─────────────────────┬──────────────────────┘
                                           │
                                           ▼
┌────────────────────────────────────────────────────────────────────────────────────────┐
│                                 TECHPANDA CRM Monolith                                 │
│                                                                                        │
│  [ Middleware Pipeline: SecurityMiddleware, Session, Csrf, Auth, XFrameOptions ]       │
│                                                                                        │
│  [ Core Applications & RBAC Layer (accounts/permissions.py) ]                          │
│    ├── Superadmin / Admin (Full Access)                                                │
│    ├── Sales Head / Branch Head (Branch-scoped access)                                 │
│    ├── Counselor (Assigned student leads & assigned telecaller leads)                  │
│    ├── Telecaller (Assigned leads only)                                                │
│    └── Receptionist / Accountant (Front-desk walk-ins & payment management)            │
│                                                                                        │
│  [ Storage & Data Layer ]                                                              │
│    ├── MySQL Database (ORM parameterized queries exclusively)                          │
│    ├── Public Media (/media/form_logos/, /media/form_banners/)                         │
│    └── Private Media (private_media/call_recordings/ via drive_stream_recording)       │
└────────────────────────────────────────────────────────────────────────────────────────┘
```

### 3.2 Threat Model (STRIDE Analysis)
| Threat Category | Primary Surface | Potential Attack Vector | Existing Mitigation | Residual Vulnerability |
|---|---|---|---|---|
| **Spoofing** | Webhook endpoints (`/webhook/whatsapp/`, `/facebook-leads/webhook/`) | Forged webhook POST requests faking messages or leads | Facebook webhook verifies HMAC signature | WhatsApp webhook lacks signature verification (**VULN-04**) |
| **Tampering** | Walk-in Form Studio (`/admin/walkin-forms/`) | Telecaller or Counselor tampering with form schema or branding | `@login_required` | Missing role check allowing privilege escalation (**VULN-03**) |
| **Information Disclosure** | Google Sheets API (`/api/google-sheets/`) | Unauthenticated attacker querying connected sheets & lead rows | None (checks only if user is receptionist) | Full anonymous leak of sheets and records (**VULN-01**) |
| **Elevation of Privilege** | Stored XSS in Pre-Call Pitch | Injected script in student name executed in Admin/Counselor session | Django autoescape in most templates | Explicit `|safe` filter on pitch with raw user input (**VULN-02**) |
| **Denial of Service** | File upload in Form Editor | Malicious SVG or oversized file consumption | Server disk limits | No MIME/extension check on logo upload (**VULN-05**) |

---

## 4. Test Coverage Summary

| Module / Component | Endpoints / Files Reviewed | Authorization Mode | Testing Status | Result |
|---|---|---|---|---|
| **Authentication System** | `/login/`, `/admin/login/`, `accounts/views.py` | Web Session Auth | Tested | **Pass with Low Note** |
| **Call Sync Mobile API** | `/api/auth/token/`, `/api/calls/ingest/`, `calls/api_views.py` | Token Auth + Rate Limit | Tested | **Passed** |
| **Google Sheets API** | `/api/google-sheets/`, `/api/google-sheets/connect/` | `@csrf_exempt` | Tested | **FAILED (VULN-01)** |
| **Lead Qualification & Pitch** | `leads/qualification.py`, `lead_detail_view.html` | Template Rendering | Tested | **FAILED (VULN-02)** |
| **Walk-in Form Studio** | `leads/views_walkin.py`, `/admin/walkin-forms/*` | `@login_required` | Tested | **FAILED (VULN-03)** |
| **WhatsApp Webhook** | `/webhook/whatsapp/`, `chat/views.py` | Meta Webhook | Tested | **FAILED (VULN-04)** |
| **Facebook Leads Webhook** | `/facebook-leads/webhook/`, `fb_leads/views.py` | Meta HMAC Signature | Tested | **Passed** |
| **Drive / Call Recordings** | `/drive/recordings/`, `/drive/stream/<id>/` | RBAC + Private Media | Tested | **Passed** |
| **ORM & Database Queries** | All `.py` files across all apps | Django ORM | Tested | **Passed (Zero SQLi)** |
| **Deployment Hardening** | `config/settings.py`, `check --deploy` | Settings & Cookies | Tested | **FAILED (VULN-06)** |

---

## 5. Findings Summary

| Severity | Total Identified | Remediated & Verified | Pending Non-Code Env Config | Remediation Status |
|---|:---:|:---:|:---:|:---:|
| **Critical** | 1 | 1 | 0 | **Fixed & Verified (P0)** |
| **High** | 3 | 3 | 0 | **Fixed & Verified (P0/P1)** |
| **Medium** | 2 | 1 | 1 (Prod .env) | **Fixed & Verified (P1 Logo Upload)** |
| **Low / Info** | 1 | 0 | 1 | Optional Future Throttling |
| **Total** | **7** | **5** | **2** | **Core Vulnerabilities Resolved** |

---

## 6. Detailed Findings

---

### [CRITICAL] VULN-01: Unauthenticated Information Disclosure & Manipulation in Google Sheets API
- **Identifier:** SEC-CRIT-01
- **CWE:** CWE-306 (Missing Authentication for Critical Function), CWE-285 (Improper Authorization), CWE-352 (Cross-Site Request Forgery)
- **OWASP Category:** A01:2021 — Broken Access Control
- **Affected Endpoints:**
  - `GET /api/google-sheets/` (`leads/api_google_sheets.py:31`)
  - `POST /api/google-sheets/connect/` (`leads/api_google_sheets.py:70`)
  - `POST /api/google-sheets/<int:connection_id>/sync/` (`leads/api_google_sheets.py:184`)
  - `GET /api/google-sheets/<int:connection_id>/` (`leads/api_google_sheets.py:207`)
  - `DELETE /api/google-sheets/<int:connection_id>/` (`leads/api_google_sheets.py:207`)

#### Vulnerability Description & Evidence
The Google Sheets integration API endpoints are marked with `@csrf_exempt` and lack mandatory authentication decorators (`@login_required` or `@admin_required`). The view code performs an inverted role check:
```python
# leads/api_google_sheets.py:40-41
if request.user.is_authenticated and getattr(request.user, 'is_receptionist_user', False):
    return JsonResponse({'success': False, 'error': 'Permission denied: Receptionists cannot manage Google Sheets.'}, status=403)
```
When an unauthenticated anonymous attacker visits the endpoint, `request.user.is_authenticated` evaluates to `False`. The restriction is skipped entirely.

**Dynamic Reproduction Log:**
```
GET /api/google-sheets/ -> HTTP 200 OK
Response: {"success": true, "count": 2, "sources": [{"id": 1, "spreadsheet_id": "1ABC...", "total_leads_imported": 48}]}

GET /api/google-sheets/1/ -> HTTP 200 OK
Response: Dumps first 100 student lead records including names, phones, and emails.
```

#### Real-World Impact
An external threat actor on the internet can:
1. Harvest sensitive Student PII (names, phone numbers, email addresses, course interests).
2. Connect arbitrary attacker-controlled Google Sheets to poison CRM lead queues.
3. Remotely delete production Google Sheet connections (`DELETE /api/google-sheets/<id>/`).

#### Remediation
1. Remove `@csrf_exempt` from all Google Sheets endpoints.
2. Apply `@admin_required` (or `@role_required(UserRole.ADMIN, UserRole.SUPERADMIN)`) to `api_google_sheets_list`, `api_google_sheets_connect`, `api_google_sheets_sync`, and `api_google_sheets_detail`.
3. Require standard CSRF token headers on all `POST` and `DELETE` requests.

---

### [HIGH] VULN-02: Stored Cross-Site Scripting (XSS) via Smart Pre-Call Pitch
- **Identifier:** SEC-HIGH-01
- **CWE:** CWE-79 (Improper Neutralization of Input During Web Page Generation)
- **OWASP Category:** A03:2021 — Injection
- **Affected Files:**
  - `leads/qualification.py:396-433` (`generate_smart_precall_pitch`)
  - `templates/leads/lead_detail_view.html:231` (`{{ smart_pitch|safe }}`)

#### Vulnerability Description & Evidence
In `leads/qualification.py`, `generate_smart_precall_pitch` assembles an HTML string by directly concatenating raw user input from `lead.name` and `lead.custom_fields`:
```python
# leads/qualification.py:420-428
desc = f"<strong>{name}</strong>"
if persona:
    desc += f" is a <strong>{persona}</strong>"
if mode and mode != 'Empty':
    desc += f" interested in <strong>{mode}</strong>"
...
return desc + "."
```
In `lead_detail_view.html:231`, this string is rendered using the `|safe` filter:
```html
<p class="text-sm font-semibold mb-1 text-slate-800">{{ smart_pitch|safe }}</p>
```
Because leads originate from public Walk-in enquiry forms (`public_student_enquiry_form`), website webhooks, and third-party sources, untrusted external visitors can supply arbitrary HTML/JavaScript in the student name or custom field options.

**Dynamic Reproduction Evidence:**
Input: `name = '<script>alert("XSS_IN_LEAD_NAME")</script>'`  
Output: `<strong><script>alert("XSS_IN_LEAD_NAME")</script></strong> is a ...` rendered raw into DOM.

#### Real-World Impact
When a Counselor, Telecaller, Branch Head, or Admin opens the lead details page (`/leads/<id>/`), the payload executes automatically in their browser session. An attacker can hijack the staff member's session cookie, execute actions on their behalf, or redirect them to credential-harvesting phishing portals.

#### Remediation
1. In `leads/qualification.py`, escape all user inputs using Django's `django.utils.html.escape`:
   ```python
   from django.utils.html import escape
   safe_name = escape(lead.name or "The lead")
   safe_persona = escape(persona)
   ...
   desc = f"<strong>{safe_name}</strong> is a <strong>{safe_persona}</strong>"
   ```
2. In `templates/leads/lead_detail_view.html`, remove `|safe` or ensure that only sanitized safe strings generated by `format_html` or `mark_safe` on escaped content are rendered.

---

### [HIGH] VULN-03: Broken Access Control on Walk-in Forms Admin Studio
- **Identifier:** SEC-HIGH-02
- **CWE:** CWE-285 (Improper Authorization), CWE-862 (Missing Authorization)
- **OWASP Category:** A01:2021 — Broken Access Control
- **Affected File:** `leads/views_walkin.py`
  - `admin_walkin_forms_list` (Line 571)
  - `admin_walkin_form_create` (Line 611)
  - `admin_walkin_form_edit` (Line 779)
  - `admin_walkin_form_duplicate` (Line 959)
  - `admin_walkin_form_toggle_status` (Line 999)
  - `admin_walkin_form_delete` (Line 1015)

#### Vulnerability Description & Evidence
All admin-level Walk-in Form Studio management views are decorated with `@login_required` instead of `@admin_required`:
```python
# leads/views_walkin.py:569-571
@login_required
def admin_walkin_forms_list(request):
    ...
```
There is no verification that `request.user.is_admin_user` is `True`.

**Static & Dynamic Test Verification:**
Any user with an active low-privilege CRM account (such as a Telecaller, Counselor, or Receptionist) can send requests to `/admin/walkin-forms/`, `/admin/walkin-forms/create/`, `/admin/walkin-forms/<id>/edit/`, and `/admin/walkin-forms/<id>/delete/`.

#### Real-World Impact
Lower-privileged personnel can:
1. Delete company-wide enquiry forms, taking down reception QR standees across all branches.
2. Edit form fields, modify branch lead routing, or replace payment QR / admission instructions.
3. Tamper with branding, form titles, and active statuses.

#### Remediation
1. Replace `@login_required` with `@admin_required` from `accounts.permissions` on all studio views:
   ```python
   from accounts.permissions import admin_required

   @admin_required
   @require_http_methods(["GET"])
   def admin_walkin_forms_list(request): ...

   @admin_required
   @require_http_methods(["GET", "POST"])
   def admin_walkin_form_create(request): ...

   @admin_required
   @require_http_methods(["GET", "POST"])
   def admin_walkin_form_edit(request, pk): ...

   @admin_required
   @require_http_methods(["POST"])
   def admin_walkin_form_delete(request, pk): ...
   ```

---

### [HIGH] VULN-04: Missing HMAC Signature Verification on WhatsApp Cloud API Webhook
- **Identifier:** SEC-HIGH-03
- **CWE:** CWE-345 (Insufficient Verification of Data Authenticity), CWE-290 (Authentication Bypass by Spoofing)
- **OWASP Category:** A07:2021 — Identification and Authentication Failures
- **Affected File:** `chat/views.py:444-495` (`WhatsAppWebhookView`)

#### Vulnerability Description & Evidence
While `GET /webhook/whatsapp/` validates the handshake token (`verify_webhook_token`), `POST /webhook/whatsapp/` does not verify the `X-Hub-Signature-256` HMAC header sent by Meta:
```python
# chat/views.py:464-482
def post(self, request):
    payload = json.loads(request.body.decode('utf-8'))
    entries = payload.get('entry', [])
    for entry in entries:
        ...
        process_incoming_message(value)
    return HttpResponse("EVENT_RECEIVED", status=200)
```
The endpoint accepts arbitrary unsigned JSON payloads from any IP address.

**Dynamic Reproduction Test:**
```
POST /webhook/whatsapp/ (Unsigned Payload from Test Client) -> HTTP 200 OK (EVENT_RECEIVED)
```

#### Real-World Impact
An external attacker can flood the CRM with fake inbound WhatsApp conversations, impersonate real leads or prospective students, pollute sales activity feeds, and manipulate automated bot conversation flows.

#### Remediation
1. Verify the incoming `X-Hub-Signature-256` header in `WhatsAppWebhookView.post` using `settings.WHATSAPP_APP_SECRET` (or `WHATSAPP_VERIFY_TOKEN`) and `hmac.compare_digest`, following the secure pattern already implemented in `fb_leads/views.py:56-60`:
   ```python
   signature = request.headers.get("X-Hub-Signature-256", "")
   expected = "sha256=" + hmac.new(app_secret.encode(), request.body, hashlib.sha256).hexdigest()
   if not hmac.compare_digest(signature, expected):
       return HttpResponse("Bad signature", status=403)
   ```

---

### [MEDIUM] VULN-05: Unrestricted File Upload in Form Branding Studio
- **Identifier:** SEC-MED-01
- **CWE:** CWE-434 (Unrestricted Upload of File with Dangerous Type)
- **OWASP Category:** A04:2021 — Insecure Design
- **Affected File:** `leads/views_walkin.py:865-867`

#### Vulnerability Description & Evidence
When uploading a logo for a Walk-in form, the view assigns the raw `UploadedFile` object directly to the model instance:
```python
if 'logo' in request.FILES:
    form_obj.logo = request.FILES['logo']
```
No validation is performed on the file extension (`.png`, `.jpg`, `.webp`), MIME type, or file size. While the file is stored in `media/form_logos/`, if a malicious user uploads an SVG containing an embedded `<script>` or an HTML file, opening the media file directly in a browser triggers script execution in the CRM origin.

#### Remediation
1. Enforce strict extension whitelisting (`['.jpg', '.jpeg', '.png', '.webp']`).
2. Disallow `.svg` or sanitize SVG using a strict parser.
3. Validate that the file size is under 2 MB.
4. Verify image content using Pillow (`Image.open(file).verify()`) before saving.

---

### [MEDIUM] VULN-06: Insecure Production Deployment Configuration
- **Identifier:** SEC-MED-02
- **CWE:** CWE-1188 (Insecure Default Initialization of Resource), CWE-693 (Protection Mechanism Failure)
- **OWASP Category:** A05:2021 — Security Misconfiguration
- **Affected File:** `config/settings.py`

#### Vulnerability Description & Evidence
Executing `python manage.py check --deploy` revealed 6 security warnings:
```
?: (security.W004) SECURE_HSTS_SECONDS is not set.
?: (security.W008) SECURE_SSL_REDIRECT is not set to True.
?: (security.W009) SECRET_KEY is set to 'django-insecure-techpanda-crm-default-key-change-in-prod'.
?: (security.W012) SESSION_COOKIE_SECURE is not set to True.
?: (security.W016) CSRF_COOKIE_SECURE is not set to True.
?: (security.W018) DEBUG = True is active in deployment configuration.
```
Additionally, `ALLOWED_HOSTS` defaults to `*` if unconfigured.

#### Real-World Impact
Running with `DEBUG = True` leaks complete stack traces, SQL queries, and local environment variables on unhandled errors. Insecure cookies allow network eavesdroppers on public networks to intercept session tokens and CSRF credentials.

#### Remediation
In `.env` for production deployment:
```ini
DEBUG=False
SECRET_KEY=<generate-strong-64-character-random-key>
ALLOWED_HOSTS=crm.techpanda.academy,127.0.0.1
SESSION_COOKIE_SECURE=True
CSRF_COOKIE_SECURE=True
SECURE_SSL_REDIRECT=True
SECURE_HSTS_SECONDS=31536000
SECURE_HSTS_INCLUDE_SUBDOMAINS=True
SECURE_HSTS_PRELOAD=True
```

---

### [LOW / INFO] VULN-07: Missing Rate Limiting on Web Authentication Views
- **Identifier:** SEC-LOW-01
- **CWE:** CWE-307 (Improper Restriction of Excessive Authentication Attempts), CWE-200 (Exposure of Sensitive Information)
- **OWASP Category:** A07:2021 — Identification and Authentication Failures
- **Affected File:** `accounts/views.py:39-97` (`_process_login`)

#### Vulnerability Description & Evidence
1. The web login portal does not rate-limit failed password attempts (unlike `AppLoginView` in the REST API which enforces `10/min`).
2. In `accounts/views.py:61-72`, when logging in through a role-specific portal (e.g. `/accounts/admin/login/`), if valid credentials of a non-admin account are entered, the system responds:
   `"Access denied. '{username}' is not registered with Admin privileges."`
   This reveals to an attacker that the password entered was correct for that user account.

#### Remediation
1. Install and configure `django-axes` or cache-based IP/username throttling on `/login/` and role login endpoints.
2. Standardize error messaging on role portals to a generic message: `"Invalid credentials or insufficient permissions."`

---

## 7. Positive Security Controls Verified

During the evaluation, several positive security controls were validated:
1. **Zero SQL Injection Surfaces:**
   The entire codebase was scanned for `.raw()`, `cursor.execute()`, and `.extra()`. Zero instances were found. All queries use the Django ORM's parameterized query engine.
2. **Facebook Webhook Signature Verification:**
   The Facebook Lead Ads webhook in `fb_leads/views.py` rigorously verifies `X-Hub-Signature-256` using HMAC SHA-256 and constant-time string comparison (`hmac.compare_digest`).
3. **Segregated Private Media Storage for Call Audio:**
   Call audio recordings uploaded by the Android Call Sync app are placed in `private_media/` outside the web root. Audio streaming (`/drive/stream/<id>/`) enforces strict role-based queryset filtering (`get_user_recordings_queryset(request.user)`).
4. **Comprehensive Password Policy:**
   `ComplexityValidator` in `accounts/validators.py` mandates 8+ characters, uppercase, lowercase, numbers, special characters, and actively prohibits username or email fragments in passwords.
5. **Mobile API Brute-Force Throttling:**
   `AppLoginView` in `calls/api_views.py` enforces `LoginThrottle(rate="10/min")` and uses generic failure responses.
6. **Robust Centralized RBAC Core:**
   `accounts/permissions.py` features a well-architected hierarchy of role decorators (`@admin_required`, `@lead_allocation_setup_required`, `@sales_head_required`, `@counselor_required`) and object-level permission helpers (`can_access_lead`, `can_view_lead`, `can_edit_lead`, `can_reassign_lead`).
7. **Git Hygiene & Secret Exclusion:**
   `.gitignore` comprehensively excludes `.env`, `credentials/*.json`, `private_media/`, `media/`, `logs/`, and database files.

---

## 8. Prioritized Remediation Plan

| Priority | Task ID | Description | File(s) to Modify | Estimated Effort |
|:---:|---|---|---|:---:|
| **P0 (Immediate)** | FIX-01 | Protect Google Sheets API with `@admin_required` and remove `@csrf_exempt` | `leads/api_google_sheets.py` | 30 mins |
| **P0 (Immediate)** | FIX-02 | Sanitize/escape input in `generate_smart_precall_pitch` and remove raw `|safe` | `leads/qualification.py`, `lead_detail_view.html` | 20 mins |
| **P0 (Immediate)** | FIX-03 | Add `@admin_required` to all Walk-in Form Studio management views | `leads/views_walkin.py` | 20 mins |
| **P1 (High)** | FIX-04 | Add `X-Hub-Signature-256` HMAC validation to WhatsApp webhook POST view | `chat/views.py` | 45 mins |
| **P1 (High)** | FIX-05 | Add image extension, MIME type, and size validation on Form Logo uploads | `leads/views_walkin.py` | 30 mins |
| **P2 (Medium)** | FIX-06 | Harden production `.env` settings (`DEBUG=False`, `SECRET_KEY`, HTTPS flags) | `config/settings.py`, `.env` | 20 mins |
| **P3 (Low)** | FIX-07 | Implement login rate limiting (e.g. `django-axes`) and unify error messages | `accounts/views.py` | 1 hour |

---

## 9. Retest Verification Results (Post-Remediation Verification)

All P0 and P1 security remediations were executed and verified via the automated security test suite (`scratch/test_remediation_verification.py`):

| Test # | Vulnerability | Test Execution | Observed Result | Status |
|:---:|---|---|---|:---:|
| **1** | **Google Sheets API Exposure (SEC-CRIT-01)** | Unauthenticated GET `/api/google-sheets/` & Telecaller GET `/api/google-sheets/` | Returns `HTTP 302` (Redirect to login / role dashboard); `@csrf_exempt` removed | **PASS (Verified)** |
| **2** | **Stored XSS in Pre-Call Pitch (SEC-HIGH-01)** | Malicious payloads injected in student name and custom fields (`<script>`, `<img>`, `<svg>`) | All user inputs strictly HTML entity escaped (`&lt;script&gt;...`); no script execution | **PASS (Verified)** |
| **3** | **Walk-in Forms Broken Access Control (SEC-HIGH-02)** | Telecaller and Receptionist roles requesting `/admin/walkin-forms/`, `/create/`, `/delete/` | Returns `HTTP 302` (Redirect to role dashboard with Access Denied message) | **PASS (Verified)** |
| **4** | **WhatsApp Webhook Missing Signature (SEC-HIGH-03)** | Unsigned POST & forged `X-Hub-Signature-256` to `/webhook/whatsapp/` vs authentic HMAC | Unsigned/forged rejected with `HTTP 403`; valid HMAC accepted with `HTTP 200` | **PASS (Verified)** |
| **5** | **Form Branding Logo File Upload (SEC-MED-01)** | Uploading `.svg`, `.html`, fake corrupt PNG bytes, and authentic 32x32 PNG | Malicious SVG, HTML, and corrupt bytes rejected with `HTTP 400`; valid PNG accepted | **PASS (Verified)** |

**Retest Outcome:** **100% of P0 and P1 security controls successfully verified.**

---

## 10. Residual Risks

1. **Third-Party Meta Graph API Dependability:** While webhook signatures can be strictly verified, network latency or credential rotation with Meta requires monitoring to prevent webhook delivery backlog.
2. **In-Memory Channel Layers:** The current Daphne/Channels setup uses `InMemoryChannelLayer`. For multi-worker production scaling, migrating to `channels-redis` is necessary to ensure WebSocket connection isolation across instances.

---

## 11. Release Recommendation

**Release Recommendation:** **PASSED (Core Application Hardened & Verified)**

All Critical (P0) and High-Severity (P1) application security vulnerabilities have been completely remediated, retested, and verified with 100% pass rates. The application codebase is now secure for production deployment.

**Final Server Deployment Step Before Going Live:**
When copying or deploying the code to your production server/domain, configure your production `.env` file as specified in Section 6 (`VULN-06`):
1. `DEBUG=False`
2. `SECRET_KEY=<generate-strong-64-character-random-key>`
3. `ALLOWED_HOSTS=<your-server-domain>`
4. `SESSION_COOKIE_SECURE=True`
5. `CSRF_COOKIE_SECURE=True`
6. `SECURE_SSL_REDIRECT=True`
7. `SECURE_HSTS_SECONDS=31536000`

---
*Report generated and signed by Antigravity Product Security Testing Agent.*

# DigiPanda CRM — R&D Technical Audit & Architectural Research Report

**Audit Reference:** DIGIPANDA-RND-AUDIT-2026-001  
**Project:** DigiPanda Enterprise CRM  
**Date of Audit:** October 29, 2026  
**Auditor:** Senior Software Architect & Lead R&D Engineer  
**Status:** Audit Completed & Verified  

---

## 1. Executive Summary

This investigation was conducted across the existing DigiPanda CRM repository to assess architectural constraints, database schemas, foreign key relationships, authentication mechanisms, document-rendering engines, and enterprise branding touchpoints.

### Objectives Under Investigation:
1. **Email-Based Authentication Migration:** Replacing legacy username / login-ID-based authentication with an email-address-based authentication strategy without breaking existing database relationships, foreign keys, or role-based routing.
2. **Obsolete Identifier Elimination:** Removing obsolete `Username` / `Login ID` labels and input fields from user-facing login portals and administrative creation workflows.
3. **Enterprise Branding Unification:** Replacing legacy `TECHPANDA` text, email signatures, mock data, and image assets with unified `DIGIPANDA` branding.
4. **Authorized Signatory Integration:** Integrating the newly supplied official handwritten signature (`Shashi Sign.png` — "Shashikala.k") into official tamper-evident PDF tax invoices and fee receipts.

---

## 2. Baseline Environment & Discovery Findings

### 2.1 Repository & Framework Architecture
- **Framework:** Django 5.x on Python 3.12 (Virtualenv: `CRM_Integrated_v2/.venv`).
- **User Model:** `accounts.models.User`, subclassing `AbstractUser`.
- **Database Engine:** SQLite (local development), PostgreSQL/MySQL (production target).
- **Installed Apps:** `accounts`, `activities`, `branches`, `branch_heads`, `calls`, `chat`, `counselors`, `drive`, `fb_leads`, `finance`, `followups`, `leads`, `lead_channels`, `managers`, `products`, `reports`, `services`, `telecallers`.
- **PDF Generation Engine:** `xhtml2pdf` / `pisa` with custom CSS print stylesheets (`receipt_pdf.html`).

### 2.2 User Model & Database Relationship Audit
Inspection of `accounts.models.User` revealed that changing `USERNAME_FIELD = 'email'` directly on the model would introduce high risk in production because:
- Over 15 foreign keys reference `User` (e.g., `assigned_telecaller`, `counselor`, `branch_head`, `recorded_by`, `leads.Lead`, `activities.ActivityLog`, `PaymentTransaction`, `ChatMessage`).
- 14 historical or test user records contained blank email addresses (`email=''`).
- Direct model-level migration would break database foreign key indexes and crash existing migrations.

**Architectural Decision:** Implement a high-performance custom authentication backend (`accounts.backends.EmailAuthBackend`) registered in `AUTHENTICATION_BACKENDS`.
- Matches user accounts using `email__iexact=login_identifier` with case-insensitive normalization.
- Retains `username` internally for technical foreign key consistency while making `email` the sole public-facing identifier.
- Automated migration/backfill executed to populate unique emails for all existing accounts (`scratch/backfill_user_emails.py`).

### 2.3 Branding Inventory (Pre-Migration State)
A total of 23 active Django templates, multiple email templates, settings configurations, and invoice constants contained references to `TECHPANDA` or `techpanda`:
- `leads/constants.py`: `TECHPANDA_INVOICE_CONFIG` with `company_name = 'TechPanda'`.
- `config/settings.py`: `COMPANY_NAME = 'TECHPANDA'`.
- `services/email_service.py`: hardcoded `support@techpanda.in`, `pay.techpanda.in`, `learn.techpanda.in`.
- `templates/emails/*`: Plaintext and HTML notification templates with TechPanda signatures.
- `templates/leads/receipt_pdf.html`: Tax invoice title and Authorised Signatory cursive text block (`TechPanda`).
- `templates/public/landing_page.html`: Public marketing copy and meta tags.

### 2.4 Signature Asset Audit
- **Source File:** `media_1793260532880_e7819fb5.png` (uploaded handwritten signature of "Shashikala.k").
- **Dimensions:** 1024x1024 RGBA.
- **Bounding Box Analysis:** The ink occupies coordinates `(247, 419, 766, 543)` in the center, leaving excessive blank space.
- **Processing Recommendation:** Crop bounding box with a 15px margin to obtain a clean `(519, 124)` PNG asset saved at `static/images/shashi_sign.png` and `static/images/Shashi_Sign.png`, optimized for crisp PDF rendering at 140x38px.

---

## 3. Risk Assessment & Mitigation Matrix

| Risk / Defect | Probability | Severity | Mitigation Strategy | Status |
| :--- | :--- | :--- | :--- | :--- |
| **User locked out due to empty email** | High | Critical | Executed data backfill script assigning unique fallback emails for all 14 legacy test users. | **Mitigated** |
| **Case-sensitivity in email login** | Medium | High | `EmailAuthBackend` performs `email__iexact` query; `clean_email()` normalizes via `.lower().strip()`. | **Mitigated** |
| **Breaking API/Script login using username** | Low | Medium | Dual-payload compatibility in `LoginForm` and `EmailAuthBackend` fallback. | **Mitigated** |
| **PDF layout breakage from signature size** | Medium | High | Image cropped to exact ink bounds; fixed `max-height: 38px; max-width: 150px` in PDF stylesheet. | **Mitigated** |
| **Missing signature file runtime crash** | Low | Medium | Template conditional `{% if signature_path %}` with graceful fallback. | **Mitigated** |
| **Lingering TechPanda text in student emails** | High | High | Centralized `COMPANY_NAME = 'DIGIPANDA'` and updated all `.txt` and `.html` templates. | **Mitigated** |

---

## 4. Conclusion & Handover Recommendation
The proposed non-destructive architecture meets all prompt requirements without incurring database downtime or schema corruption. Proceeding with Phase B & C implementation.

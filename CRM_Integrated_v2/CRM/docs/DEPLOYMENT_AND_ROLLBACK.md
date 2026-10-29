# DigiPanda CRM — Deployment & Rollback Guide

**Guide Reference:** DIGIPANDA-DEPLOY-GUIDE-2026-001  
**Target Applications:** DigiPanda CRM (Core, Accounts, Leads, Finance, Templates, Static)  
**Effective Date:** October 29, 2026  

---

## 1. Pre-Deployment Checklist

1. **Environment Consistency:** Ensure Python 3.12+ and Django 5.x virtual environment is active.
2. **Static Asset Compilation:** Run `collectstatic` to ensure `shashi_sign.png` and `digipanda_logo.png` are linked to the web server's static root.
3. **Database Audit:** Ensure all user records have unique email addresses. If any new users were imported with blank emails, execute `python scratch/backfill_user_emails.py`.

---

## 2. Step-by-Step Deployment Procedure

### Step 1: Deploy Backend & Configuration Files
Deploy updated source files:
- `accounts/backends.py`
- `accounts/forms.py`
- `accounts/views.py`
- `accounts/services.py`
- `config/settings.py`
- `finance/views.py`
- `leads/constants.py`
- `leads/views_enrollment.py`
- `services/email_service.py`
- `chat/campaign_service.py`
- `lead_channels/views.py`

### Step 2: Deploy Static Assets & Processed Signature
Copy signature and logo files to your production static directory:
```bash
cp static/images/shashi_sign.png <PRODUCTION_STATIC_ROOT>/images/
cp static/images/Shashi_Sign.png <PRODUCTION_STATIC_ROOT>/images/
cp static/images/digipanda_logo.png <PRODUCTION_STATIC_ROOT>/images/
```
Run Django static collection:
```bash
python manage.py collectstatic --noinput
```

### Step 3: Run Database Email Backfill (If Migrating Existing DB)
```bash
python scratch/backfill_user_emails.py
```

### Step 4: Validate Django Integrity
```bash
python manage.py check
python scratch/test_master_rnd_suite.py
```

### Step 5: Reload WSGI / ASGI Application Server
Reload Gunicorn / uWSGI / Systemd service:
```bash
sudo systemctl restart gunicorn-crm
```

---

## 3. Rollback Procedure

If any unforeseen production issue arises, follow these steps to instantly roll back:

### Step 1: Revert Git Commits / Working Tree
```bash
git checkout HEAD -- accounts/ config/ finance/ leads/ services/ templates/
```

### Step 2: Reset `AUTHENTICATION_BACKENDS`
In `config/settings.py`, remove `'accounts.backends.EmailAuthBackend'` from `AUTHENTICATION_BACKENDS`. Django will fall back to default username-based `ModelBackend`.

### Step 3: Reload WSGI / Application Server
```bash
sudo systemctl restart gunicorn-crm
```

### Step 4: Verify System Access
Verify that username logins are operational via `curl` or browser test.

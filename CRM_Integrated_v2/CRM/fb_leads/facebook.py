"""Talks to Facebook's Graph API and saves leads into the FacebookLead table.
Supports multi-account and multi-page routing while maintaining fallback to settings.
"""

import logging
import requests
from django.conf import settings
from django.utils import timezone
from django.utils.dateparse import parse_datetime

from .models import FacebookAccount, FacebookPage, FacebookLead

log = logging.getLogger("crm")


def _graph():
    return f"https://graph.facebook.com/{getattr(settings, 'FB_GRAPH_VERSION', 'v23.0') or 'v23.0'}"


LEAD_FIELDS = "id,created_time,field_data,form_id,ad_id,ad_name,campaign_name"

# Facebook form field names -> our columns (covers common English names)
NAME_KEYS = ("full_name", "name", "first_name")
PHONE_KEYS = ("phone_number", "phone", "mobile_number", "whatsapp_number")
EMAIL_KEYS = ("email", "email_address")
CITY_KEYS = ("city", "location")

_page_token_cache = {}


def _check_settings():
    missing = [k for k in ("FB_PAGE_TOKEN", "FB_PAGE_ID") if not getattr(settings, k, "")]
    if missing:
        raise RuntimeError("Facebook is not set up: add " + ", ".join(missing) + " to your .env file")


def get_token_for_page(page_id=None):
    """
    Returns the page access token for a given page_id from the database if available;
    otherwise falls back to settings.FB_PAGE_TOKEN / settings.FB_PAGE_ID.
    """
    if page_id:
        fb_page = FacebookPage.objects.filter(page_id=page_id, status='CONNECTED').first()
        if fb_page and fb_page.page_access_token:
            return fb_page.page_access_token

    # Fallback to single page setup from settings
    if "token" in _page_token_cache:
        return _page_token_cache["token"]

    _check_settings()
    try:
        r = requests.get(
            f"{_graph()}/{settings.FB_PAGE_ID}",
            params={"fields": "access_token", "access_token": settings.FB_PAGE_TOKEN},
            timeout=20,
        )
        data = r.json()
        token = data.get("access_token")
        if not token:
            if "error" in data:
                raise RuntimeError("Could not get Page token: " + data["error"].get("message", ""))
            token = settings.FB_PAGE_TOKEN  # already a Page token
        _page_token_cache["token"] = token
        return token
    except Exception as exc:
        log.warning("Could not fetch page token dynamically, falling back to FB_PAGE_TOKEN: %s", exc)
        return settings.FB_PAGE_TOKEN


def _get(path, params=None, page_id=None, token=None):
    params = dict(params or {})
    params["access_token"] = token or get_token_for_page(page_id)
    r = requests.get(f"{_graph()}/{path}", params=params, timeout=20)
    data = r.json()
    if "error" in data:
        _page_token_cache.clear()  # try a fresh token next time
        raise RuntimeError(data["error"].get("message", "Facebook API error"))
    return data


def _pick(answers, keys):
    for k in keys:
        if answers.get(k):
            return answers[k]
    return ""


def subscribe_page(page_id=None):
    """
    Link the Page to this app so Facebook sends new leads to our webhook.
    Safe to run many times.
    """
    target_page_id = page_id or getattr(settings, 'FB_PAGE_ID', '')
    if not target_page_id:
        raise RuntimeError("No page ID provided to subscribe.")

    token = get_token_for_page(target_page_id)
    r = requests.post(
        f"{_graph()}/{target_page_id}/subscribed_apps",
        data={"subscribed_fields": "leadgen", "access_token": token},
        timeout=20,
    )
    data = r.json()
    if "error" in data:
        raise RuntimeError("Page link failed: " + data["error"].get("message", ""))

    success = data.get("success", False)
    if success and page_id:
        FacebookPage.objects.filter(page_id=page_id).update(webhook_subscribed=True)
    return success


def unsubscribe_page(page_id):
    """Unsubscribe a Facebook Page from leadgen webhooks."""
    token = get_token_for_page(page_id)
    r = requests.delete(
        f"{_graph()}/{page_id}/subscribed_apps",
        data={"access_token": token},
        timeout=20,
    )
    data = r.json()
    success = data.get("success", False)
    if success:
        FacebookPage.objects.filter(page_id=page_id).update(webhook_subscribed=False)
    return success


def sync_pages_for_account(account):
    """
    Fetches all Facebook Pages accessible with the account's access token via me/accounts
    and saves or updates FacebookPage records in the database.
    """
    r = requests.get(
        f"{_graph()}/me/accounts",
        params={"fields": "id,name,access_token,category,tasks", "access_token": account.access_token},
        timeout=20,
    )
    data = r.json()
    if "error" in data:
        account.last_error = data["error"].get("message", "Failed to retrieve pages")
        account.save(update_fields=['last_error'])
        raise RuntimeError(account.last_error)

    pages_synced = 0
    for page_info in data.get("data", []):
        p_id = page_info.get("id")
        p_name = page_info.get("name")
        p_token = page_info.get("access_token")
        if p_id and p_token:
            fb_page, created = FacebookPage.objects.update_or_create(
                account=account,
                page_id=p_id,
                defaults={
                    "page_name": p_name,
                    "page_access_token": p_token,
                    "status": "CONNECTED",
                    "last_error": "",
                }
            )
            try:
                subscribe_page(p_id)
            except Exception as e:
                log.info("Could not auto-subscribe page %s: %s", p_id, e)
            pages_synced += 1

    account.last_verified_at = timezone.now()
    account.last_error = ""
    account.save(update_fields=['last_verified_at', 'last_error'])
    return pages_synced


def save_lead(lead, page_id="", form_name=""):
    """Save one lead dict (as returned by Facebook). Returns (obj, created)."""
    answers = {}
    for item in lead.get("field_data", []):
        values = item.get("values") or []
        answers[item.get("name", "")] = ", ".join(values)

    first_last = " ".join(x for x in (answers.get("first_name"), answers.get("last_name")) if x)
    
    # Locate FacebookPage / FacebookAccount if exists
    fb_page = None
    account = None
    if page_id:
        fb_page = FacebookPage.objects.filter(page_id=page_id).first()
        if fb_page:
            account = fb_page.account

    obj, created = FacebookLead.objects.update_or_create(
        leadgen_id=lead["id"],
        defaults={
            "full_name": answers.get("full_name") or first_last or _pick(answers, NAME_KEYS),
            "phone": _pick(answers, PHONE_KEYS),
            "email": _pick(answers, EMAIL_KEYS),
            "city": _pick(answers, CITY_KEYS),
            "page_id": page_id,
            "fb_page": fb_page,
            "account": account,
            "form_id": lead.get("form_id", ""),
            "form_name": form_name,
            "ad_id": lead.get("ad_id", ""),
            "ad_name": lead.get("ad_name", ""),
            "campaign_name": lead.get("campaign_name", ""),
            "all_answers": answers,
            "created_on_facebook": parse_datetime(lead["created_time"]) if lead.get("created_time") else None,
        },
    )
    # CRM: every Facebook lead becomes (or updates) a CRM lead with source "Facebook".
    if not obj.lead_id:
        from .crm import push_to_crm
        push_to_crm(obj)
    return obj, created


def fetch_and_save_lead(leadgen_id, page_id=""):
    """Called by the webhook: get full lead details by ID and save it."""
    lead = _get(leadgen_id, {"fields": LEAD_FIELDS}, page_id=page_id)
    form_name = ""
    if lead.get("form_id"):
        try:
            form_name = _get(lead["form_id"], {"fields": "name"}, page_id=page_id).get("name", "")
        except RuntimeError:
            pass
    return save_lead(lead, page_id=page_id, form_name=form_name)


def sync_page_leads(page_id):
    """Pull leads for a specific Facebook Page. Returns new count."""
    token = get_token_for_page(page_id)
    new_count = 0
    forms = _get(f"{page_id}/leadgen_forms", {"fields": "id,name", "limit": 100}, token=token)
    for form in forms.get("data", []):
        url_path, params = f"{form['id']}/leads", {"fields": LEAD_FIELDS, "limit": 100}
        while True:
            page = _get(url_path, params, token=token)
            for lead in page.get("data", []):
                _, created = save_lead(lead, page_id=page_id, form_name=form.get("name", ""))
                new_count += int(created)
            after = page.get("paging", {}).get("cursors", {}).get("after")
            if not page.get("paging", {}).get("next") or not after:
                break
            params = {"fields": LEAD_FIELDS, "limit": 100, "after": after}

    FacebookPage.objects.filter(page_id=page_id).update(
        last_sync_at=timezone.now(),
        last_sync_status=f"Synced {new_count} new leads",
        last_error=""
    )
    return new_count


def sync_all_leads():
    """Pull every lead from every connected Page or default page. Returns total new count."""
    connected_pages = FacebookPage.objects.filter(status='CONNECTED')
    total_new = 0
    if connected_pages.exists():
        for p in connected_pages:
            try:
                total_new += sync_page_leads(p.page_id)
            except Exception as e:
                log.warning("Failed to sync leads for page %s: %s", p.page_id, e)
        return total_new

    # Fallback to single page settings
    page_id = settings.FB_PAGE_ID
    return sync_page_leads(page_id)
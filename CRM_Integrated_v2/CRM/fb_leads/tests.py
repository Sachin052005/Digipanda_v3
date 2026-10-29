"""
Facebook Lead Ads -> CRM leads (source Facebook): signed webhook, Graph API fetch (mocked),
branch / course from form answers, duplicates, errors, Sync button, page access.
"""
import hashlib
import hmac
import json
from io import StringIO
from unittest.mock import patch

from django.core.management import call_command
from django.test import Client, TestCase, override_settings
from django.urls import reverse

from accounts.models import User, UserRole
from branches.models import Branch
from fb_leads.models import FacebookLead
from lead_channels.models import Channel
from leads.models import Lead, LeadStatus, TelecallerLeadSetup
from products.models import Product

SECRET = "app-secret-123"
FB = dict(FB_VERIFY_TOKEN="verify-me", FB_APP_SECRET=SECRET, FB_PAGE_TOKEN="page-token", FB_PAGE_ID="PAGE1")


def graph_lead(lead_id="L1", phone="+91 98765 11111", name="Priya S", extra=None, form_id="F1", email=None):
    lead_email = email if email is not None else (f"{lead_id.lower()}@example.com" if lead_id != "L1" else "priya@example.com")
    fields = [{"name": "full_name", "values": [name]},
              {"name": "phone_number", "values": [phone]},
              {"name": "email", "values": [lead_email]}]
    for k, v in (extra or {}).items():
        fields.append({"name": k, "values": [v]})
    return {"id": lead_id, "created_time": "2026-10-10T09:30:00+0000", "field_data": fields,
            "form_id": form_id, "ad_id": "AD1", "ad_name": "DS Oct", "campaign_name": "Admissions Oct"}


def fake_graph(leads, form_name="Data Science Enquiry"):
    """Stand-in for fb_leads.facebook._get (Graph API)."""
    by_id = {l["id"]: l for l in leads}

    def _get(path, params=None, page_id=None, token=None, *args, **kwargs):
        if path in by_id:
            return by_id[path]
        if path.endswith("/leadgen_forms"):
            return {"data": [{"id": "F1", "name": form_name}]}
        if path == "F1/leads":
            return {"data": leads, "paging": {}}
        if path == "F1":
            return {"name": form_name}
        raise RuntimeError(f"unexpected Graph call {path}")
    return _get


def signed(body):
    return "sha256=" + hmac.new(SECRET.encode(), body, hashlib.sha256).hexdigest()


@override_settings(**FB)
class FacebookToCRMTests(TestCase):
    def setUp(self):
        self.velachery = Branch.objects.create(name="Velachery FB")
        self.tnagar = Branch.objects.create(name="T Nagar FB")
        self.tc = User.objects.create_user(username="tc_fb", password="pwd", role=UserRole.TELECALLER,
                                           branch=self.velachery)
        TelecallerLeadSetup.objects.create(telecaller=self.tc, branch=self.velachery, assignment_percentage=100)
        self.admin = User.objects.create_user(username="admin_fb", password="pwd", role=UserRole.ADMIN, is_staff=True)
        self.product = Product.objects.create(name="Data Science")
        self.client = Client()

    def post_lead(self, lead_id="L1", url=None):
        body = json.dumps({"object": "page", "entry": [{"changes": [
            {"field": "leadgen", "value": {"leadgen_id": lead_id, "page_id": "PAGE1", "form_id": "F1"}}]}]}).encode()
        return self.client.post(url or reverse("fb_leads:facebook_leads_webhook"), data=body, content_type="application/json",
                                HTTP_X_HUB_SIGNATURE_256=signed(body))

    def test_webhook_verification(self):
        url = reverse("fb_leads:facebook_leads_webhook")
        r = self.client.get(url, {"hub.mode": "subscribe", "hub.verify_token": "verify-me", "hub.challenge": "42"})
        self.assertEqual(r.content, b"42")
        r = self.client.get(url, {"hub.mode": "subscribe", "hub.verify_token": "nope", "hub.challenge": "42"})
        self.assertEqual(r.status_code, 403)

    def test_signed_lead_becomes_assigned_facebook_crm_lead(self):
        leads = [graph_lead(extra={"preferred_branch": "velachery fb", "which_course": "Data Science"})]
        with patch("fb_leads.facebook._get", side_effect=fake_graph(leads)):
            r = self.post_lead()
        self.assertEqual(r.status_code, 200)
        fb = FacebookLead.objects.get(leadgen_id="L1")
        self.assertEqual(fb.form_name, "Data Science Enquiry")
        lead = fb.lead
        self.assertIsNotNone(lead)
        self.assertEqual(fb.crm_result, "new")
        self.assertEqual(lead.phone, "9876511111")
        self.assertEqual(lead.name, "Priya S")
        self.assertEqual(lead.email, "priya@example.com")
        self.assertEqual(lead.source, "Facebook")
        self.assertEqual(lead.channel, Channel.objects.get(name="Facebook"))
        self.assertEqual(lead.branch, self.velachery)
        self.assertEqual(lead.product, self.product)
        self.assertEqual(lead.assigned_telecaller, self.tc)
        self.assertIn("Facebook Lead Ad", lead.notes)
        self.assertIn("Campaign: Admissions Oct", lead.notes)

        # Facebook re-sends the same lead: nothing duplicated
        with patch("fb_leads.facebook._get", side_effect=fake_graph(leads)):
            self.post_lead()
        self.assertEqual(Lead.objects.count(), 1)
        self.assertEqual(FacebookLead.objects.count(), 1)

    def test_old_crm_meta_url_is_the_same_secure_webhook(self):
        with patch("fb_leads.facebook._get", side_effect=fake_graph([graph_lead()])):
            r = self.post_lead(url=reverse("meta_webhook_endpoint"))
        self.assertEqual(r.status_code, 200)
        self.assertTrue(Lead.objects.filter(phone="9876511111", source="Facebook").exists())

    def test_unsigned_or_unconfigured_webhook_is_refused(self):
        body = b'{"entry": []}'
        r = self.client.post(reverse("fb_leads:facebook_leads_webhook"), data=body, content_type="application/json",
                             HTTP_X_HUB_SIGNATURE_256="sha256=bad")
        self.assertEqual(r.status_code, 403)
        with override_settings(FB_APP_SECRET=""):
            r = self.client.post(reverse("fb_leads:facebook_leads_webhook"), data=body, content_type="application/json",
                                 HTTP_X_HUB_SIGNATURE_256=signed(body))
            self.assertEqual(r.status_code, 403)
        with override_settings(FB_VERIFY_TOKEN=""):
            r = self.client.get(reverse("fb_leads:facebook_leads_webhook"),
                                {"hub.mode": "subscribe", "hub.verify_token": "", "hub.challenge": "1"})
            self.assertEqual(r.status_code, 403)

    def test_existing_lead_keeps_source_and_owner(self):
        wa = Lead.objects.create(name="WA Student", phone="9876511111", source="WhatsApp",
                                 status=LeadStatus.INTERESTED, branch=self.tnagar)
        with patch("fb_leads.facebook._get", side_effect=fake_graph([graph_lead()])):
            self.post_lead()
        fb = FacebookLead.objects.get()
        self.assertEqual(fb.lead, wa)
        self.assertEqual(fb.crm_result, "existing")
        wa.refresh_from_db()
        self.assertEqual(wa.source, "WhatsApp")
        self.assertEqual(wa.status, LeadStatus.INTERESTED)
        self.assertEqual(wa.email, "priya@example.com")      # blank filled
        self.assertEqual(Lead.objects.count(), 1)

    def test_branch_from_form_name_and_default_setting(self):
        with patch("fb_leads.facebook._get", side_effect=fake_graph([graph_lead()], form_name="T Nagar FB - Python")):
            self.post_lead()
        self.assertEqual(FacebookLead.objects.get().lead.branch, self.tnagar)
        with override_settings(FB_DEFAULT_BRANCH="Velachery FB"):
            with patch("fb_leads.facebook._get", side_effect=fake_graph([graph_lead("L2", phone="9000000002")],
                                                                        form_name="General")):
                self.post_lead("L2")
        self.assertEqual(FacebookLead.objects.get(leadgen_id="L2").lead.branch, self.velachery)

    def test_no_branch_is_pending_assignment(self):
        with patch("fb_leads.facebook._get", side_effect=fake_graph([graph_lead()], form_name="General")):
            self.post_lead()
        lead = FacebookLead.objects.get().lead
        self.assertIsNone(lead.branch)
        self.assertEqual(lead.assignment_status, "Pending Assignment")

    def test_lead_without_phone_is_kept_with_error(self):
        with patch("fb_leads.facebook._get", side_effect=fake_graph([graph_lead(phone="")])):
            self.post_lead()
        fb = FacebookLead.objects.get()
        self.assertIsNone(fb.lead)
        self.assertEqual(fb.crm_result, "error")
        self.assertIn("Invalid phone", fb.crm_error)
        self.assertFalse(Lead.objects.exists())

    def test_sync_button_and_page_access(self):
        leads = [graph_lead("L1", phone="9000000001"), graph_lead("L2", phone="9000000002", name="Arun")]
        self.client.force_login(self.admin)
        with patch("fb_leads.facebook._get", side_effect=fake_graph(leads)), \
                patch("fb_leads.views.subscribe_page", return_value=True):
            r = self.client.post(reverse("fb_leads:facebook_leads_sync"))
        self.assertEqual(r.status_code, 302)
        self.assertEqual(Lead.objects.filter(source="Facebook").count(), 2)
        page = self.client.get(reverse("fb_leads:facebook_leads"))
        self.assertContains(page, "Arun")
        self.assertContains(page, "New lead")
        self.client.force_login(self.tc)
        self.assertEqual(self.client.get(reverse("fb_leads:facebook_leads")).status_code, 403)

    def test_management_command_crm_only(self):
        FacebookLead.objects.create(leadgen_id="OLD1", full_name="Imported", phone="9000000009")
        out = StringIO()
        call_command("sync_fb_leads", "--crm-only", stdout=out)
        self.assertIn("1 Facebook lead(s) added to the CRM", out.getvalue())
        self.assertEqual(FacebookLead.objects.get().lead.source, "Facebook")

    def test_lead_page_shows_facebook_form(self):
        with patch("fb_leads.facebook._get", side_effect=fake_graph([graph_lead(extra={"preferred_branch": "Velachery"})])):
            self.post_lead()
        lead = FacebookLead.objects.get().lead
        self.client.force_login(self.admin)
        r = self.client.get(reverse("admin_lead_detail", args=[lead.pk]))
        self.assertContains(r, "Facebook Lead Ad")
        self.assertContains(r, "Data Science Enquiry")

    def test_auto_sync_toggle_and_scheduler(self):
        from fb_leads.models import FacebookAccount, FacebookPage
        from fb_leads.scheduler import run_auto_sync_cycle

        self.client.force_login(self.admin)
        acc = FacebookAccount.objects.create(account_name="Marketing Corp", access_token="EAA123")
        page = FacebookPage.objects.create(
            account=acc,
            page_id="PAGE99",
            page_name="TechPanda Chennai",
            page_access_token="tok99",
            branch=self.velachery,
            auto_sync_enabled=True,
            sync_interval_minutes=3,
        )
        self.assertTrue(page.auto_sync_enabled)
        self.assertEqual(page.sync_interval_minutes, 3)

        # 1. Toggle Auto-Sync via POST
        r = self.client.post(
            reverse("fb_leads:fb_page_toggle_autosync", args=[page.id]),
            HTTP_X_REQUESTED_WITH="XMLHttpRequest"
        )
        self.assertEqual(r.status_code, 200)
        data = r.json()
        self.assertFalse(data["auto_sync_enabled"])
        page.refresh_from_db()
        self.assertFalse(page.auto_sync_enabled)

        # 2. Toggle back on
        r = self.client.post(
            reverse("fb_leads:fb_page_toggle_autosync", args=[page.id]),
            HTTP_X_REQUESTED_WITH="XMLHttpRequest"
        )
        data = r.json()
        self.assertTrue(data["auto_sync_enabled"])
        page.refresh_from_db()
        self.assertTrue(page.auto_sync_enabled)
        self.assertIsNotNone(page.next_sync_at)

        # 3. Update Interval to 1 minute
        r = self.client.post(
            reverse("fb_leads:fb_page_update_interval", args=[page.id]),
            data={"interval": "1"},
            HTTP_X_REQUESTED_WITH="XMLHttpRequest"
        )
        self.assertEqual(r.status_code, 200)
        page.refresh_from_db()
        self.assertEqual(page.sync_interval_minutes, 1)

        # 4. Status API
        r = self.client.get(
            reverse("fb_leads:fb_api_autosync_status"),
            HTTP_X_REQUESTED_WITH="XMLHttpRequest"
        )
        self.assertEqual(r.status_code, 200)
        status_data = r.json()
        self.assertTrue(status_data["success"])
        page_entry = [p for p in status_data["pages"] if p["id"] == page.id][0]
        self.assertEqual(page_entry["sync_interval_minutes"], 1)
        self.assertTrue(page_entry["auto_sync_enabled"])


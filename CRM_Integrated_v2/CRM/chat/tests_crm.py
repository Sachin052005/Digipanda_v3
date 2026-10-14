"""
WhatsApp -> CRM integration: chats become CRM leads (source WhatsApp), flow answers fill the lead,
CRM flow steps (Lead Status, Assign Telecaller), role-scoped inbox, lead page link, backfill command.
"""
import json
from io import StringIO
from unittest.mock import patch

from django.core.management import call_command
from django.test import Client, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from accounts.models import User, UserRole
from branches.models import Branch, SalesHeadBranchAccess
from chat.models import AutomationFlow, BusinessAccount, Conversation, UserFlowSession
from followups.models import FollowUp
from lead_channels.models import Channel
from leads.models import Lead, LeadStatus, LeadStatusHistory, TelecallerLeadSetup
from products.models import Product

SEND = 'chat.whatsapp.client.WhatsAppClient.send_payload'
SENT_OK = {'messages': [{'id': 'wamid.mock'}]}


def webhook_payload(phone, text, name="Student", phone_number_id="PNID-1", wamid=None):
    return {
        "object": "whatsapp_business_account",
        "entry": [{"id": "1", "changes": [{"field": "messages", "value": {
            "messaging_product": "whatsapp",
            "metadata": {"display_phone_number": "918000000000", "phone_number_id": phone_number_id},
            "contacts": [{"profile": {"name": name}, "wa_id": phone}],
            "messages": [{"from": phone, "id": wamid or f"wamid.{phone}.{text}",
                          "timestamp": str(int(timezone.now().timestamp())),
                          "text": {"body": text}, "type": "text"}],
        }}]}],
    }


def crm_flow():
    """trigger -> ask name -> ask branch -> Lead Status (Interested) -> Assign (branch rules) -> end"""
    nodes = [
        {"id": "t", "type": "trigger", "data": {"trigger_type": "first_incoming_message"}},
        {"id": "q_name", "type": "question", "data": {"text": "Your name?", "variable_name": "name"}},
        {"id": "q_branch", "type": "question", "data": {"text": "Which branch?", "variable_name": "branch"}},
        {"id": "q_course", "type": "question", "data": {"text": "Which course?", "variable_name": "course"}},
        {"id": "st", "type": "lead_status", "data": {"status": "Interested", "follow_up_hours": 24}},
        {"id": "as", "type": "assign_telecaller", "data": {"mode": "auto", "only_if_unassigned": True}},
        {"id": "e", "type": "end", "data": {"text": "Thanks {{name}}!"}},
    ]
    order = ["t", "q_name", "q_branch", "q_course", "st", "as", "e"]
    connections = [{"source": a, "target": b, "source_output": "default"} for a, b in zip(order, order[1:])]
    return {"nodes": nodes, "connections": connections}


class WhatsAppCRMBase(TestCase):
    def setUp(self):
        self.velachery = Branch.objects.create(name="Velachery WA")
        self.tnagar = Branch.objects.create(name="T Nagar WA")
        self.sales_head = User.objects.create_user(username="sh_wa", password="pwd", role=UserRole.SALES_HEAD)
        SalesHeadBranchAccess.objects.create(sales_head=self.sales_head, branch=self.velachery)
        self.tc = User.objects.create_user(username="tc_wa", password="pwd", role=UserRole.TELECALLER,
                                           branch=self.velachery, first_name="Divya")
        self.tc_tn = User.objects.create_user(username="tc_tn", password="pwd", role=UserRole.TELECALLER,
                                              branch=self.tnagar, first_name="Karthik")
        TelecallerLeadSetup.objects.create(telecaller=self.tc, branch=self.velachery, assignment_percentage=100)
        TelecallerLeadSetup.objects.create(telecaller=self.tc_tn, branch=self.tnagar, assignment_percentage=100)
        self.admin = User.objects.create_user(username="admin_wa", password="pwd", role=UserRole.ADMIN, is_staff=True)
        self.biz = BusinessAccount.objects.create(name="Velachery Admissions", phone_number="+91 80000 00000",
                                                  phone_number_id="PNID-1", is_default=True,
                                                  automation_enabled=False, crm_branch=self.velachery)
        self.client = Client()

    def post_webhook(self, phone, text, **kw):
        with patch(SEND, return_value=SENT_OK):
            return self.client.post(reverse('whatsapp-webhook'), data=json.dumps(webhook_payload(phone, text, **kw)),
                                    content_type="application/json")


class WhatsAppLeadCreationTests(WhatsAppCRMBase):
    def test_new_whatsapp_contact_becomes_assigned_crm_lead(self):
        r = self.post_webhook("919876500011", "Hi", name="Anitha")
        self.assertEqual(r.status_code, 200)
        lead = Lead.objects.get(phone="9876500011")
        self.assertEqual(lead.source, "WhatsApp")
        self.assertEqual(lead.channel, Channel.objects.get(name="WhatsApp"))
        self.assertEqual(lead.name, "Anitha")
        self.assertEqual(lead.status, LeadStatus.NEW)
        self.assertEqual(lead.branch, self.velachery)          # from the WhatsApp number's CRM branch
        self.assertEqual(lead.assigned_telecaller, self.tc)     # branch Lead Setup (100%)
        self.assertEqual(lead.assigned_sales_head, self.sales_head)
        self.assertIn("New lead from WhatsApp", lead.notes)

        # More messages on the same chat: still one lead, no extra timeline noise
        self.post_webhook("919876500011", "Course fees?", name="Anitha")
        self.assertEqual(Lead.objects.filter(phone="9876500011").count(), 1)

    def test_existing_facebook_lead_is_not_duplicated_or_changed(self):
        fb = Lead.objects.create(name="FB Student", phone="+91 98765 00012", source="Facebook",
                                 status=LeadStatus.INTERESTED, branch=self.tnagar, assigned_telecaller=self.tc_tn)
        self.post_webhook("919876500012", "Hello")
        self.assertEqual(Lead.objects.count(), 1)
        fb.refresh_from_db()
        self.assertEqual(fb.source, "Facebook")
        self.assertEqual(fb.status, LeadStatus.INTERESTED)
        self.assertEqual(fb.assigned_telecaller, self.tc_tn)
        self.assertEqual(fb.branch, self.tnagar)
        self.assertIn("Started a WhatsApp chat", fb.notes)

    def test_no_branch_means_pending_assignment(self):
        self.biz.crm_branch = None
        self.biz.save()
        self.post_webhook("919876500013", "Hi")
        lead = Lead.objects.get(phone="9876500013")
        self.assertIsNone(lead.assigned_telecaller)
        self.assertEqual(lead.assignment_status, "Pending Assignment")

    @override_settings(WHATSAPP_DEFAULT_BRANCH="T Nagar WA")
    def test_default_branch_setting(self):
        self.biz.crm_branch = None
        self.biz.save()
        self.post_webhook("919876500014", "Hi")
        lead = Lead.objects.get(phone="9876500014")
        self.assertEqual(lead.branch, self.tnagar)
        self.assertEqual(lead.assigned_telecaller, self.tc_tn)

    def test_backfill_command_creates_leads_for_old_chats(self):
        Conversation.objects.create(business_account=self.biz, customer_name="Old Chat", phone_number="+919876500015")
        Conversation.objects.create(business_account=self.biz, customer_name="+919876500016", phone_number="+919876500016")
        out = StringIO()
        call_command('sync_whatsapp_leads', stdout=out)
        self.assertIn("2 new WhatsApp lead(s)", out.getvalue())
        self.assertEqual(Lead.objects.get(phone="9876500015").name, "Old Chat")
        self.assertEqual(Lead.objects.get(phone="9876500016").name, "9876500016")
        call_command('sync_whatsapp_leads', stdout=StringIO())
        self.assertEqual(Lead.objects.count(), 2)


class WhatsAppFlowCRMStepsTests(WhatsAppCRMBase):
    def setUp(self):
        super().setUp()
        self.biz.crm_branch = None          # branch comes from the student's answer
        self.biz.automation_enabled = True
        self.biz.save()
        self.product = Product.objects.create(name="Data Science")
        AutomationFlow.objects.create(
            business_account=self.biz, name="CRM flow", slug="crm-flow", version=1,
            status=AutomationFlow.STATUS_PUBLISHED, trigger_type=AutomationFlow.TRIGGER_FIRST_MESSAGE,
            trigger_keywords="hi", flow_data=crm_flow(), is_active=True, published_at=timezone.now())

    def test_answers_and_crm_steps_update_the_lead(self):
        phone = "919876500021"
        self.post_webhook(phone, "hi", name="+919876500021", wamid="w1")
        lead = Lead.objects.get(phone="9876500021")
        self.assertEqual(lead.assignment_status, "Pending Assignment")   # no branch yet

        self.post_webhook(phone, "Ramya Krishnan", wamid="w2")
        self.post_webhook(phone, "T Nagar", wamid="w3")
        self.post_webhook(phone, "data science", wamid="w4")

        lead.refresh_from_db()
        self.assertEqual(lead.name, "Ramya Krishnan")
        self.assertEqual(lead.branch, self.tnagar)                        # "T Nagar" -> "T Nagar WA"
        self.assertEqual(lead.product, self.product)
        self.assertEqual(lead.assigned_telecaller, self.tc_tn)            # assigned once the branch was known
        self.assertEqual(lead.status, LeadStatus.INTERESTED)              # Lead Status step
        self.assertTrue(LeadStatusHistory.objects.filter(lead=lead, new_status=LeadStatus.INTERESTED).exists())
        self.assertTrue(FollowUp.objects.filter(lead=lead, notes__icontains="WhatsApp automation").exists())
        self.assertIn("WhatsApp answers — Name: Ramya Krishnan", lead.notes)
        self.assertEqual(lead.notes.count("Name: Ramya Krishnan"), 1)     # recorded once
        session = UserFlowSession.objects.get(conversation__phone_number="+" + phone)
        self.assertEqual(session.status, UserFlowSession.STATUS_COMPLETED)

    def test_specific_telecaller_step(self):
        from chat import crm
        lead = Lead.objects.create(name="X", phone="9876500022", branch=self.velachery)
        crm.assign_lead(lead, mode='specific', telecaller_id=self.tc_tn.pk)
        lead.refresh_from_db()
        self.assertEqual(lead.assigned_telecaller, self.tc_tn)
        with self.assertRaises(ValueError):
            crm.assign_lead(lead, mode='specific', telecaller_id=99999)
        # only_if_unassigned keeps the current telecaller
        self.assertIsNone(crm.assign_lead(lead, mode='specific', telecaller_id=self.tc.pk, only_if_unassigned=True))

    def test_validator_checks_crm_steps(self):
        from chat.automation.validator import validate_flow_graph
        data = crm_flow()
        data["nodes"][4]["data"]["status"] = "NOT_A_STATUS"
        data["nodes"][5]["data"] = {"mode": "specific", "telecaller_id": None}
        result = validate_flow_graph(data)
        messages = " ".join(e["message"] for e in result["errors"])
        self.assertIn("Lead Status step", messages)
        self.assertIn("Assign Telecaller step", messages)
        self.assertTrue(validate_flow_graph(crm_flow())["valid"])


class WhatsAppAccessTests(WhatsAppCRMBase):
    def setUp(self):
        super().setUp()
        self.mine = Lead.objects.create(name="Mine", phone="9876500031", assigned_telecaller=self.tc, branch=self.velachery)
        self.other = Lead.objects.create(name="Other", phone="9876500032", assigned_telecaller=self.tc_tn, branch=self.tnagar)
        self.c_mine = Conversation.objects.create(business_account=self.biz, customer_name="Mine", phone_number="+919876500031")
        self.c_other = Conversation.objects.create(business_account=self.biz, customer_name="Other", phone_number="+919876500032")

    def test_inbox_requires_login(self):
        r = self.client.get(reverse('inbox'))
        self.assertEqual(r.status_code, 302)
        r = self.client.get(reverse('api-conversations'))
        self.assertIn(r.status_code, (401, 403))

    def test_telecaller_sees_only_own_lead_chats(self):
        self.client.force_login(self.tc)
        self.assertEqual(self.client.get(reverse('inbox')).status_code, 200)
        ids = [c['id'] for c in self.client.get(reverse('api-conversations')).json()]
        self.assertEqual(ids, [self.c_mine.pk])
        self.assertEqual(self.client.get(reverse('api-conversation-messages', args=[self.c_mine.pk])).status_code, 200)
        self.assertEqual(self.client.get(reverse('api-conversation-messages', args=[self.c_other.pk])).status_code, 403)
        # cannot start a chat with someone else's lead
        with patch(SEND, return_value=SENT_OK):
            r = self.client.post(reverse('api-message-send'), {"phone_number": "+919876500032", "message_text": "hi"})
        self.assertEqual(r.status_code, 403)

    def test_admin_sees_all_and_manages_automations(self):
        self.client.force_login(self.admin)
        ids = {c['id'] for c in self.client.get(reverse('api-conversations')).json()}
        self.assertEqual(ids, {self.c_mine.pk, self.c_other.pk})
        self.assertEqual(self.client.get(reverse('automation-list')).status_code, 200)
        opts = self.client.get(reverse('api-crm-options')).json()
        self.assertIn('Follow-up', [s['value'] for s in opts['statuses']])
        self.assertIn(self.tc.pk, [t['id'] for t in opts['telecallers']])

    def test_telecaller_cannot_open_automations(self):
        self.client.force_login(self.tc)
        self.assertEqual(self.client.get(reverse('automation-list')).status_code, 403)
        self.assertEqual(self.client.get(reverse('api-flows')).status_code, 403)
        self.assertEqual(self.client.get(reverse('api-crm-options')).status_code, 403)

    def test_sales_head_sees_branch_chats(self):
        self.client.force_login(self.sales_head)
        ids = {c['id'] for c in self.client.get(reverse('api-conversations')).json()}
        self.assertEqual(ids, {self.c_mine.pk})

    def test_lead_page_links_to_whatsapp_chat(self):
        self.client.force_login(self.tc)
        r = self.client.get(reverse('telecaller_lead_detail', args=[self.mine.pk]))
        self.assertContains(r, "WHATSAPP &amp; FACEBOOK")
        self.assertContains(r, f"{reverse('inbox')}?conversation={self.c_mine.pk}")

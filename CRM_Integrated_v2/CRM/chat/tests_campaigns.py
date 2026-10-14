"""
Unit and integration tests for Bulk WhatsApp Campaigns in TECHPANDA TELE CRM.
Covers:
- Phone number normalization & compliance guards
- Sender resolution (Mode 1: assigned telecaller vs Mode 2: selected sender)
- Placeholder rendering & template component assembly
- Recipient cohort generation & chunked streaming
- Batch dispatching & atomic concurrency locking
- Webhook status progression & regression protection
- Campaign lifecycle controls (pause, resume, cancel) & CSV exports
"""

from unittest.mock import patch, MagicMock
from django.test import TestCase, Client
from django.utils import timezone
from django.urls import reverse

from accounts.models import User, UserRole
from branches.models import Branch
from products.models import Product
from leads.models import Lead
from chat.models import (
    BusinessAccount,
    WhatsAppSender,
    WhatsAppTemplate,
    WhatsAppCampaign,
    WhatsAppCampaignRecipient,
    Conversation,
    Message,
)
from chat.campaign_service import (
    normalize_phone_number,
    check_lead_consent_eligibility,
    get_eligible_senders_for_user,
    resolve_sender_for_lead,
    get_lead_placeholder_values,
    render_message_for_recipient,
    resolve_campaign_recipients,
    dispatch_campaign_batch,
    update_recipient_from_webhook_status,
    ensure_default_senders_and_templates,
)


class PhoneNormalizationTests(TestCase):
    def test_normalize_10_digit_indian_number(self):
        norm, valid, err = normalize_phone_number("9876543210")
        self.assertTrue(valid)
        self.assertEqual(norm, "919876543210")
        self.assertIsNone(err)

    def test_normalize_number_with_country_code_and_formatting(self):
        norm, valid, err = normalize_phone_number("+91 (98765) 43210")
        self.assertTrue(valid)
        self.assertEqual(norm, "919876543210")
        self.assertIsNone(err)

    def test_normalize_number_with_leading_zero(self):
        norm, valid, err = normalize_phone_number("09876543210")
        self.assertTrue(valid)
        self.assertEqual(norm, "919876543210")

    def test_invalid_short_number(self):
        norm, valid, err = normalize_phone_number("12345")
        self.assertFalse(valid)
        self.assertIn("Invalid phone length", err)

    def test_empty_or_none_number(self):
        norm, valid, err = normalize_phone_number("")
        self.assertFalse(valid)
        self.assertIn("Missing phone number", err)

        norm, valid, err = normalize_phone_number(None)
        self.assertFalse(valid)


class ComplianceAndConsentTests(TestCase):
    def setUp(self):
        self.lead = Lead.objects.create(
            name="Rahul Sharma",
            phone="9876543210",
            whatsapp_opt_out=False,
            whatsapp_consent_given=True
        )

    def test_eligible_lead_passes_compliance(self):
        ok, reason = check_lead_consent_eligibility(self.lead)
        self.assertTrue(ok)
        self.assertIsNone(reason)

    def test_opt_out_lead_rejected(self):
        self.lead.whatsapp_opt_out = True
        self.lead.save()
        ok, reason = check_lead_consent_eligibility(self.lead)
        self.assertFalse(ok)
        self.assertIn("opted out", reason.lower())

    def test_missing_consent_lead_rejected(self):
        self.lead.whatsapp_consent_given = False
        self.lead.save()
        ok, reason = check_lead_consent_eligibility(self.lead)
        self.assertFalse(ok)
        self.assertIn("consent", reason.lower())


class SenderAndPlaceholderTests(TestCase):
    def setUp(self):
        self.branch1 = Branch.objects.create(name="Chennai Central")
        self.branch2 = Branch.objects.create(name="Coimbatore North")

        self.admin = User.objects.create_user(
            username="admin_test",
            password="password123",
            role=UserRole.ADMIN
        )
        self.telecaller = User.objects.create_user(
            username="telecaller_test",
            password="password123",
            role=UserRole.TELECALLER,
            branch=self.branch1,
            first_name="Priya",
            last_name="Rajan"
        )

        self.course = Product.objects.create(name="Full Stack Python Mastery", price=25000)

        self.lead = Lead.objects.create(
            name="Karthik",
            phone="9876543210",
            branch=self.branch1,
            product=self.course,
            assigned_telecaller=self.telecaller
        )

        self.sender1 = WhatsAppSender.objects.create(
            name="Official Sender Chennai",
            phone_number_id="10001",
            display_phone_number="+91 84382 39448",
            is_active=True
        )
        self.sender1.allowed_branches.add(self.branch1)

        self.template = WhatsAppTemplate.objects.create(
            name="course_inquiry_followup",
            display_title="Course Inquiry Follow-up",
            language="en_US",
            category="MARKETING",
            status="APPROVED",
            body_text="Hi {{1}}, regarding {{2}} at {{3}}, contact {{4}}.",
            parameter_mapping=["lead_name", "course", "branch", "assigned_telecaller"],
            is_active=True
        )

    def test_placeholder_extraction(self):
        vals = get_lead_placeholder_values(self.lead)
        self.assertEqual(vals['lead_name'], "Karthik")
        self.assertEqual(vals['branch'], "Chennai Central")
        self.assertEqual(vals['course'], "Full Stack Python Mastery")
        self.assertEqual(vals['assigned_telecaller'], "Priya Rajan")

    def test_message_rendering_with_template(self):
        campaign = WhatsAppCampaign.objects.create(
            name="Test Camp",
            created_by=self.admin,
            sender_mode=WhatsAppCampaign.MODE_SELECTED_SENDER,
            selected_sender=self.sender1,
            template=self.template,
            message_type=WhatsAppCampaign.MESSAGE_TYPE_TEMPLATE
        )
        rendered, components, err = render_message_for_recipient(self.lead, campaign)
        self.assertIsNone(err)
        self.assertIn("Hi Karthik", rendered)
        self.assertIn("Full Stack Python Mastery", rendered)
        self.assertIn("Chennai Central", rendered)
        self.assertIn("Priya Rajan", rendered)
        self.assertEqual(len(components), 1)
        self.assertEqual(components[0]['type'], 'body')
        self.assertEqual(len(components[0]['parameters']), 4)

    def test_sender_resolution_mode_selected(self):
        campaign = WhatsAppCampaign.objects.create(
            name="Mode 2 Test",
            created_by=self.admin,
            sender_mode=WhatsAppCampaign.MODE_SELECTED_SENDER,
            selected_sender=self.sender1
        )
        sender, err = resolve_sender_for_lead(self.lead, campaign)
        self.assertIsNone(err)
        self.assertEqual(sender.id, self.sender1.id)

    def test_sender_resolution_mode_assigned_telecaller(self):
        # Attach a personal sender for this telecaller
        caller_sender = WhatsAppSender.objects.create(
            name="Priya Direct Line",
            phone_number_id="20002",
            display_phone_number="+91 99999 11111",
            user=self.telecaller,
            is_active=True
        )
        campaign = WhatsAppCampaign.objects.create(
            name="Mode 1 Test",
            created_by=self.admin,
            sender_mode=WhatsAppCampaign.MODE_ASSIGNED_TELECALLER
        )
        sender, err = resolve_sender_for_lead(self.lead, campaign)
        self.assertIsNone(err)
        self.assertEqual(sender.id, caller_sender.id)


class RecipientResolutionAndDispatchTests(TestCase):
    def setUp(self):
        self.branch = Branch.objects.create(name="T Nagar")
        self.admin = User.objects.create_user(
            username="admin_rec",
            password="password123",
            role=UserRole.ADMIN
        )
        self.sender = WhatsAppSender.objects.create(
            name="Official Sender",
            phone_number_id="11111",
            display_phone_number="+91 84382 39448",
            is_active=True
        )
        self.template = WhatsAppTemplate.objects.create(
            name="welcome_lead_intro",
            display_title="Welcome",
            language="en_US",
            category="MARKETING",
            status="APPROVED",
            body_text="Hello {{1}} from {{2}}",
            parameter_mapping=["lead_name", "branch"],
            is_active=True
        )

        # Create 3 leads: 1 valid, 1 opted-out, 1 invalid-phone
        self.lead_valid = Lead.objects.create(
            name="Valid Lead",
            phone="9876543210",
            branch=self.branch,
            whatsapp_opt_out=False,
            whatsapp_consent_given=True
        )
        self.lead_optout = Lead.objects.create(
            name="Opted Out Lead",
            phone="9876543211",
            branch=self.branch,
            whatsapp_opt_out=True,
            whatsapp_consent_given=True
        )
        self.lead_badphone = Lead.objects.create(
            name="Bad Phone Lead",
            phone="123",  # Invalid short
            branch=self.branch,
            whatsapp_opt_out=False,
            whatsapp_consent_given=True
        )

        self.campaign = WhatsAppCampaign.objects.create(
            name="Resolution Test Campaign",
            created_by=self.admin,
            sender_mode=WhatsAppCampaign.MODE_SELECTED_SENDER,
            selected_sender=self.sender,
            template=self.template,
            message_type=WhatsAppCampaign.MESSAGE_TYPE_TEMPLATE
        )

    def test_resolve_campaign_recipients_classification(self):
        res = resolve_campaign_recipients(
            self.campaign,
            lead_ids=[self.lead_valid.id, self.lead_optout.id, self.lead_badphone.id],
            user=self.admin
        )
        self.assertEqual(res['total_selected'], 3)
        self.assertEqual(res['eligible'], 1)
        self.assertEqual(res['skipped'], 2)
        self.assertEqual(res['opted_out'], 1)
        self.assertEqual(res['invalid_phone'], 1)

        # Check entries in recipient table
        rec_valid = WhatsAppCampaignRecipient.objects.get(campaign=self.campaign, lead=self.lead_valid)
        self.assertEqual(rec_valid.status, WhatsAppCampaignRecipient.STATUS_ELIGIBLE)
        self.assertEqual(rec_valid.phone_number, "919876543210")

        rec_optout = WhatsAppCampaignRecipient.objects.get(campaign=self.campaign, lead=self.lead_optout)
        self.assertEqual(rec_optout.status, WhatsAppCampaignRecipient.STATUS_SKIPPED)
        self.assertIn("opted out", rec_optout.skip_reason.lower())

        rec_bad = WhatsAppCampaignRecipient.objects.get(campaign=self.campaign, lead=self.lead_badphone)
        self.assertEqual(rec_bad.status, WhatsAppCampaignRecipient.STATUS_SKIPPED)
        self.assertIn("length", rec_bad.skip_reason.lower())

    @patch('chat.campaign_service.WhatsAppClient.send_payload')
    def test_dispatch_campaign_batch_success(self, mock_send):
        mock_send.return_value = {
            "messaging_product": "whatsapp",
            "messages": [{"id": "wamid.HBgLMTIzNDU2"}],
            "mocked": False
        }

        resolve_campaign_recipients(
            self.campaign,
            lead_ids=[self.lead_valid.id],
            user=self.admin
        )

        processed, remaining = dispatch_campaign_batch(self.campaign.id, batch_size=10)
        self.assertEqual(processed, 1)
        self.assertEqual(remaining, 0)

        # Check recipient updated
        rec = WhatsAppCampaignRecipient.objects.get(campaign=self.campaign, lead=self.lead_valid)
        self.assertEqual(rec.status, WhatsAppCampaignRecipient.STATUS_SUBMITTED)
        self.assertEqual(rec.provider_message_id, "wamid.HBgLMTIzNDU2")
        self.assertIsNotNone(rec.submitted_at)

        # Check campaign counters and status
        self.campaign.refresh_from_db()
        self.assertEqual(self.campaign.submitted_count, 1)
        self.assertEqual(self.campaign.status, WhatsAppCampaign.STATUS_COMPLETED)

        # Check inbox sync created Conversation and Message
        conv = Conversation.objects.filter(phone_number="+919876543210").first()
        self.assertIsNotNone(conv)
        self.assertTrue(Message.objects.filter(conversation=conv, whatsapp_message_id="wamid.HBgLMTIzNDU2").exists())


class WebhookProgressionTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_user(username="admin_hook", password="password123", role=UserRole.ADMIN)
        self.campaign = WhatsAppCampaign.objects.create(name="Webhook Test", created_by=self.admin)
        self.recipient = WhatsAppCampaignRecipient.objects.create(
            campaign=self.campaign,
            phone_number="919876543210",
            lead_name="Test Lead",
            status=WhatsAppCampaignRecipient.STATUS_SUBMITTED,
            provider_message_id="wamid.test_12345"
        )

    def test_status_progression_sent_delivered_read(self):
        # 1. Update to sent
        update_recipient_from_webhook_status("wamid.test_12345", "sent")
        self.recipient.refresh_from_db()
        self.assertEqual(self.recipient.status, WhatsAppCampaignRecipient.STATUS_SENT)
        self.assertIsNotNone(self.recipient.sent_at)

        # 2. Update to delivered
        update_recipient_from_webhook_status("wamid.test_12345", "delivered")
        self.recipient.refresh_from_db()
        self.assertEqual(self.recipient.status, WhatsAppCampaignRecipient.STATUS_DELIVERED)
        self.assertIsNotNone(self.recipient.delivered_at)

        # 3. Update to read
        update_recipient_from_webhook_status("wamid.test_12345", "read")
        self.recipient.refresh_from_db()
        self.assertEqual(self.recipient.status, WhatsAppCampaignRecipient.STATUS_READ)
        self.assertIsNotNone(self.recipient.read_at)

    def test_status_regression_protection(self):
        # If recipient is read, an out-of-order delivered event must NOT overwrite read
        self.recipient.status = WhatsAppCampaignRecipient.STATUS_READ
        self.recipient.read_at = timezone.now()
        self.recipient.save()

        update_recipient_from_webhook_status("wamid.test_12345", "delivered")
        self.recipient.refresh_from_db()
        self.assertEqual(self.recipient.status, WhatsAppCampaignRecipient.STATUS_READ)

    def test_failure_webhook_status(self):
        err = {"code": 131026, "message": "Message undeliverable"}
        update_recipient_from_webhook_status("wamid.test_12345", "failed", error_details=err)
        self.recipient.refresh_from_db()
        self.assertEqual(self.recipient.status, WhatsAppCampaignRecipient.STATUS_FAILED)
        self.assertEqual(self.recipient.error_code, "131026")
        self.assertIn("Message undeliverable", self.recipient.error_message)


class ViewsAndWorkflowTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.admin = User.objects.create_user(
            username="admin_view",
            password="password123",
            role=UserRole.ADMIN
        )
        self.client.force_login(self.admin)

        self.sender = WhatsAppSender.objects.create(
            name="Official Sender",
            phone_number_id="11111",
            display_phone_number="+91 84382 39448",
            is_active=True
        )
        self.template = WhatsAppTemplate.objects.create(
            name="welcome_view",
            display_title="Welcome",
            language="en_US",
            category="MARKETING",
            status="APPROVED",
            body_text="Hello {{1}}",
            parameter_mapping=["lead_name"],
            is_active=True
        )
        self.campaign = WhatsAppCampaign.objects.create(
            name="Workflow Test Campaign",
            created_by=self.admin,
            selected_sender=self.sender,
            template=self.template,
            status=WhatsAppCampaign.STATUS_RUNNING
        )

    def test_campaigns_list_view(self):
        response = self.client.get(reverse('whatsapp_campaigns_list'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Workflow Test Campaign")

    def test_campaign_detail_view(self):
        response = self.client.get(reverse('whatsapp_campaign_detail', args=[self.campaign.id]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Workflow Test Campaign")

    def test_campaign_control_pause_resume_cancel(self):
        # Pause
        resp_pause = self.client.post(
            reverse('whatsapp_campaign_api_control', args=[self.campaign.id]),
            {'action': 'pause'}
        )
        self.assertEqual(resp_pause.status_code, 200)
        self.campaign.refresh_from_db()
        self.assertEqual(self.campaign.status, WhatsAppCampaign.STATUS_PAUSED)

        # Resume
        resp_resume = self.client.post(
            reverse('whatsapp_campaign_api_control', args=[self.campaign.id]),
            {'action': 'resume'}
        )
        self.assertEqual(resp_resume.status_code, 200)
        self.campaign.refresh_from_db()
        self.assertEqual(self.campaign.status, WhatsAppCampaign.STATUS_RUNNING)

        # Cancel
        resp_cancel = self.client.post(
            reverse('whatsapp_campaign_api_control', args=[self.campaign.id]),
            {'action': 'cancel'}
        )
        self.assertEqual(resp_cancel.status_code, 200)
        self.campaign.refresh_from_db()
        self.assertEqual(self.campaign.status, WhatsAppCampaign.STATUS_CANCELLED)

    def test_campaign_export_csv(self):
        WhatsAppCampaignRecipient.objects.create(
            campaign=self.campaign,
            phone_number="919876543210",
            lead_name="Export Lead",
            status=WhatsAppCampaignRecipient.STATUS_DELIVERED
        )
        response = self.client.get(reverse('whatsapp_campaign_export_csv', args=[self.campaign.id]))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'text/csv')
        self.assertIn("Export Lead", response.content.decode('utf-8'))

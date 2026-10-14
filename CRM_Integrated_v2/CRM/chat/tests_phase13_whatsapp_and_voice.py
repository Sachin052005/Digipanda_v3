from django.test import TestCase, Client
from django.urls import reverse
import json

from accounts.models import User, UserRole
from branches.models import Branch
from leads.models import Lead, LeadStatus, LeadCategory
from chat.models import BusinessAccount, Conversation, Message
from activities.models import Activity


class WhatsAppMessagingAndVoiceTestCase(TestCase):
    def setUp(self):
        self.client = Client()
        self.branch = Branch.objects.create(name="Cyber Branch", status="Active")

        # Telecaller user
        self.telecaller = User.objects.create_user(
            username="tc_wa", email="tc_wa@test.com", password="password123",
            role=UserRole.TELECALLER, branch=self.branch
        )

        # Another telecaller in different branch
        self.branch_other = Branch.objects.create(name="Remote Branch", status="Active")
        self.other_tc = User.objects.create_user(
            username="tc_other", email="tc_other@test.com", password="password123",
            role=UserRole.TELECALLER, branch=self.branch_other
        )

        # Lead assigned to telecaller
        self.lead = Lead.objects.create(
            name="Charlie WhatsApp", phone="+919876543299", branch=self.branch,
            assigned_telecaller=self.telecaller, status=LeadStatus.CONTACTED,
            category=LeadCategory.TRAINING
        )

        # Business Account for testing
        self.biz = BusinessAccount.objects.create(
            name="Cyber WhatsApp", phone_number="+919876543200",
            phone_number_id="109876543210987", is_default=True, is_active=True,
            crm_branch=self.branch
        )

    def test_telecaller_send_whatsapp_template(self):
        self.client.login(username="tc_wa", password="password123")
        url = reverse('api_telecaller_send_whatsapp', kwargs={'lead_id': self.lead.pk})
        payload = {
            'template_key': 'welcome'
        }
        response = self.client.post(url, data=json.dumps(payload), content_type='application/json')
        self.assertEqual(response.status_code, 200)

        data = response.json()
        self.assertTrue(data['success'])
        self.assertIn("welcome to TECHPANDA", data['text'])

        # Verify Message record
        msg = Message.objects.get(id=data['message_id'])
        self.assertEqual(msg.sender, Message.SENDER_AGENT)
        self.assertIn("Charlie WhatsApp", msg.message_text)

        # Verify Conversation record
        conv = Conversation.objects.get(id=data['conversation_id'])
        self.assertEqual(conv.customer_name, "Charlie WhatsApp")

        # Verify Activity Log
        act = Activity.objects.filter(object_id=self.lead.id, action="WhatsApp Message Sent").first()
        self.assertIsNotNone(act)
        self.assertEqual(act.user, self.telecaller)

    def test_telecaller_send_whatsapp_custom_message(self):
        self.client.login(username="tc_wa", password="password123")
        url = reverse('api_telecaller_send_whatsapp', kwargs={'lead_id': self.lead.pk})
        payload = {
            'template_key': 'custom',
            'message_text': 'Hello Charlie, this is a personalized custom message.'
        }
        response = self.client.post(url, data=json.dumps(payload), content_type='application/json')
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data['success'])
        self.assertEqual(data['text'], 'Hello Charlie, this is a personalized custom message.')

    def test_whatsapp_voice_capability_endpoint(self):
        self.client.login(username="tc_wa", password="password123")
        url = reverse('api_whatsapp_voice_capability', kwargs={'lead_id': self.lead.pk})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

        data = response.json()
        self.assertTrue(data['success'])
        self.assertEqual(data['capability'], 'whatsapp_voice_calling')
        self.assertIn('tel_url', data)
        self.assertIn('wa_call_url', data)
        self.assertIsInstance(data['prerequisites'], list)
        self.assertGreater(len(data['prerequisites']), 0)

    def test_bulk_action_category_update(self):
        # Admin updating category
        admin = User.objects.create_user(
            username="admin_cat", email="adm_cat@test.com", password="password123",
            role=UserRole.ADMIN, is_staff=True, is_superuser=True
        )
        self.client.login(username="admin_cat", password="password123")
        url = reverse('api_bulk_action')
        payload = {
            'action': 'category_update',
            'lead_ids': [self.lead.id],
            'new_category': LeadCategory.PLACEMENT
        }
        response = self.client.post(url, data=json.dumps(payload), content_type='application/json')
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data['success'])
        self.assertEqual(data['updated_count'], 1)

        self.lead.refresh_from_db()
        self.assertEqual(self.lead.category, LeadCategory.PLACEMENT)

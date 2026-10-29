import json
from unittest.mock import patch
from django.test import override_settings
from django.test import TestCase, Client
from django.urls import reverse
from django.conf import settings
from django.utils import timezone
from chat.models import BusinessAccount, Conversation, Message


class WhatsAppCRMTests(TestCase):
    def setUp(self):
        self.client = Client()
        # Inside the CRM the inbox and automations need a logged-in user (Admin can do everything).
        from accounts.models import User, UserRole
        self.crm_admin = User.objects.create_user(username=f'wa_admin_{id(self)}', password='pwd', role=UserRole.ADMIN, is_staff=True)
        self.client.force_login(self.crm_admin)
        self.business_acc1 = BusinessAccount.objects.create(
            name="Main Line",
            phone_number="+91 84382 39448",
            phone_number_id="1294166677119820",
            is_default=True,
            is_active=True
        )
        self.business_acc2 = BusinessAccount.objects.create(
            name="Support Line",
            phone_number="+91 80000 12345",
            phone_number_id="1294166677119999",
            is_default=False,
            is_active=True
        )

        self.conv1 = Conversation.objects.create(
            business_account=self.business_acc1,
            customer_name="Priya Kumar",
            phone_number="+919876543210",
            last_message="Hi, I need course details",
            unread_count=2,
            is_pinned=True,
            is_online=True,
            last_seen="online"
        )
        self.msg1 = Message.objects.create(
            conversation=self.conv1,
            sender=Message.SENDER_CUSTOMER,
            message_type=Message.TYPE_TEXT,
            message_text="Hi, I need course details",
            status=Message.STATUS_DELIVERED,
            whatsapp_message_id="wamid.test_001"
        )
        self.conv2 = Conversation.objects.create(
            business_account=self.business_acc1,
            customer_name="Arun Kumar",
            phone_number="+919876543211",
            last_message="Thanks team",
            unread_count=0,
            is_pinned=False,
            is_online=False,
            last_seen="yesterday"
        )
        self.conv_supp = Conversation.objects.create(
            business_account=self.business_acc2,
            customer_name="Karthik Raja",
            phone_number="+919876543301",
            last_message="Need help with ticket",
            unread_count=1,
            is_pinned=False,
            is_online=True,
        )

    def test_business_accounts_api(self):
        """Test GET /api/business-accounts/."""
        response = self.client.get(reverse('api-business-accounts'))
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(len(data), 2)
        self.assertEqual(data[0]['name'], "Main Line")

    def test_inbox_view(self):
        """Test that main 2-panel inbox view renders HTTP 200."""
        response = self.client.get(reverse('inbox'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'CONVERSATIONS')
        self.assertContains(response, 'chat-panel')
        self.assertNotContains(response, 'Lead Details')
        self.assertNotContains(response, 'CRM Analytics')

    def test_inbox_crm_layout_integration(self):
        """Verify WhatsApp inbox is rendered inside the main CRM shell and layout."""
        response = self.client.get(reverse('inbox'))
        self.assertEqual(response.status_code, 200)

        # 1. Standard CRM layout components are present
        self.assertContains(response, 'class="app-sidebar"')
        self.assertContains(response, 'class="app-header"')
        self.assertContains(response, 'TECHPANDA CRM')
        self.assertContains(response, 'class="content-wrapper inbox-content-wrapper"')
        self.assertContains(response, 'theme-toggle')
        self.assertContains(response, 'call-dialer-overlay')

        # 2. WhatsApp Chats navigation item is active with blue highlight class
        self.assertContains(response, 'class="nav-item active"')
        self.assertContains(response, 'WhatsApp Chats')

        # 3. WhatsApp workspace components are nested inside content
        self.assertContains(response, 'class="whatsapp-workspace"')
        self.assertContains(response, 'id="appContainer"')
        self.assertContains(response, 'class="crm-app-container"')
        self.assertContains(response, 'id="conversationsPanel"')
        self.assertContains(response, 'id="chatPanel"')
        self.assertContains(response, 'window.CRM_CONFIG')
        self.assertContains(response, 'chat/js/inbox.js')

        # 4. No duplicate html/body documents
        content = response.content.decode('utf-8')
        self.assertEqual(content.count('<html'), 1)
        self.assertEqual(content.count('<body'), 1)

        # 5. Verify for Telecaller user role as well
        from accounts.models import User, UserRole
        telecaller = User.objects.create_user(username=f'wa_telecaller_{id(self)}', password='pwd', role=UserRole.TELECALLER)
        self.client.force_login(telecaller)
        tc_response = self.client.get(reverse('inbox'))
        self.assertEqual(tc_response.status_code, 200)
        self.assertContains(tc_response, 'class="app-sidebar"')
        self.assertContains(tc_response, 'class="nav-item active"')
        self.assertContains(tc_response, 'WhatsApp Chats')
        self.assertContains(tc_response, 'class="whatsapp-workspace"')

    def test_conversations_api(self):
        """Test GET /api/conversations/ and filtering by business account."""
        response = self.client.get(reverse('api-conversations'))
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(len(data), 3)

        # Test filtering by business_account_id
        response_acc1 = self.client.get(f"{reverse('api-conversations')}?business_account_id={self.business_acc1.id}")
        self.assertEqual(len(response_acc1.json()), 2)

        response_acc2 = self.client.get(f"{reverse('api-conversations')}?business_account_id={self.business_acc2.id}")
        self.assertEqual(len(response_acc2.json()), 1)
        self.assertEqual(response_acc2.json()[0]['customer_name'], "Karthik Raja")

        # Test unread filter
        response_unread = self.client.get(f"{reverse('api-conversations')}?filter=unread")
        data_unread = response_unread.json()
        self.assertEqual(len(data_unread), 2)

    def test_conversation_messages_api_and_mark_read(self):
        """Test GET /api/conversations/<id>/messages/ and resetting unread count."""
        self.assertEqual(self.conv1.unread_count, 2)
        response = self.client.get(reverse('api-conversation-messages', kwargs={'pk': self.conv1.id}))
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(len(data), 1)
        self.assertEqual(data[0]['message_text'], "Hi, I need course details")

        # Refresh from db to verify unread count is reset to 0
        self.conv1.refresh_from_db()
        self.assertEqual(self.conv1.unread_count, 0)

    def test_send_message_api(self):
        """Test POST /api/messages/send/."""
        payload = {
            "conversation_id": self.conv1.id,
            "message_text": "Sure Priya! Happy to help.",
            "message_type": "text"
        }
        response = self.client.post(
            reverse('api-message-send'),
            data=json.dumps(payload),
            content_type="application/json"
        )
        self.assertEqual(response.status_code, 201)
        data = response.json()
        self.assertEqual(data['message_text'], "Sure Priya! Happy to help.")
        self.assertEqual(data['sender'], "agent")

        # Verify database updated
        self.conv1.refresh_from_db()
        self.assertEqual(self.conv1.last_message, "Sure Priya! Happy to help.")

    def test_search_api(self):
        """Test GET /api/search/?q=..."""
        response = self.client.get(f"{reverse('api-search')}?q=Priya")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(len(data), 1)
        self.assertEqual(data[0]['customer_name'], "Priya Kumar")

        # Search by phone number
        response_phone = self.client.get(f"{reverse('api-search')}?q=9876543211")
        data_phone = response_phone.json()
        self.assertEqual(len(data_phone), 1)
        self.assertEqual(data_phone[0]['customer_name'], "Arun Kumar")

    @override_settings(WHATSAPP_VERIFY_TOKEN='test_verify_token')
    def test_webhook_get_verification(self):
        """Test Meta webhook verification handshake."""
        verify_token = getattr(settings, 'WHATSAPP_VERIFY_TOKEN', 'whatsapp_crm_verify_token_secure')
        challenge = "random_challenge_code_12345"

        # Valid challenge
        url = f"{reverse('whatsapp-webhook')}?hub.mode=subscribe&hub.verify_token={verify_token}&hub.challenge={challenge}"
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content.decode('utf-8'), challenge)

        # Invalid token
        url_bad = f"{reverse('whatsapp-webhook')}?hub.mode=subscribe&hub.verify_token=wrong_token&hub.challenge={challenge}"
        response_bad = self.client.get(url_bad)
        self.assertEqual(response_bad.status_code, 403)

    def test_webhook_post_incoming_message_and_status(self):
        """Test incoming message ingestion and status update via webhook POST."""
        webhook_payload = {
            "object": "whatsapp_business_account",
            "entry": [
                {
                    "id": "123456789",
                    "changes": [
                        {
                            "field": "messages",
                            "value": {
                                "messaging_product": "whatsapp",
                                "metadata": {
                                    "display_phone_number": "918000012345",
                                    "phone_number_id": "1294166677119999"
                                },
                                "contacts": [{"profile": {"name": "Meena Raj"}, "wa_id": "919876543299"}],
                                "messages": [
                                    {
                                        "from": "919876543299",
                                        "id": "wamid.incoming_webhook_999",
                                        "timestamp": str(int(timezone.now().timestamp())),
                                        "text": {"body": "Is recording available?"},
                                        "type": "text"
                                    }
                                ],
                                "statuses": [
                                    {
                                        "id": "wamid.test_001",
                                        "status": "read",
                                        "recipient_id": "919876543210"
                                    }
                                ]
                            }
                        }
                    ]
                }
            ]
        }

        with patch('chat.whatsapp.client.WhatsAppClient.send_payload', return_value={'messages': [{'id': 'wamid.mock'}]}), \
             patch('chat.whatsapp.messages.send_text_message', return_value={'messages': [{'id': 'wamid.mock'}]}):
            response = self.client.post(
                reverse('whatsapp-webhook'),
                data=json.dumps(webhook_payload),
                content_type="application/json"
            )
        self.assertEqual(response.status_code, 200)

        # Check that Meena Raj conversation and message were created and linked to business_acc2
        new_conv = Conversation.objects.get(phone_number="+919876543299")
        self.assertEqual(new_conv.customer_name, "Meena Raj")
        self.assertEqual(new_conv.unread_count, 1)
        self.assertEqual(new_conv.business_account, self.business_acc2)

        new_msg = Message.objects.get(whatsapp_message_id="wamid.incoming_webhook_999")
        self.assertEqual(new_msg.message_text, "Is recording available?")
        self.assertEqual(new_msg.sender, Message.SENDER_CUSTOMER)

        # Check that msg1 status updated to read
        self.msg1.refresh_from_db()
        self.assertEqual(self.msg1.status, Message.STATUS_READ)


class WhatsAppAutomationTests(TestCase):
    """
    Test suite for WhatsApp Automation Engine, No-Code Flow Builder API,
    interactive message traversal, dynamic Course/Branch models, and human handover mechanisms.
    Covers all 20 Master Requirements from Section 30.
    """

    def setUp(self):
        from unittest.mock import patch
        from chat.models import Course, Branch, AutomationFlow
        from chat.automation.templates import get_default_admissions_flow_data

        self.client = Client()
        # Inside the CRM the inbox and automations need a logged-in user (Admin can do everything).
        from accounts.models import User, UserRole
        self.crm_admin = User.objects.create_user(username=f'wa_admin_{id(self)}', password='pwd', role=UserRole.ADMIN, is_staff=True)
        self.client.force_login(self.crm_admin)
        self.business_account = BusinessAccount.objects.create(
            name="Admissions Line",
            phone_number="+91 84382 39448",
            phone_number_id="1294166677119820",
            automation_enabled=True,
            is_default=True,
            is_active=True
        )
        self.conversation = Conversation.objects.create(
            business_account=self.business_account,
            customer_name="Sanjay Raman",
            phone_number="+919876540001",
            last_message="Hi",
            unread_count=0
        )

        # Seed dynamic courses
        self.course1 = Course.objects.create(
            name="Full Stack Python",
            code="PY-01",
            duration="4 Months",
            brochure_url="https://example.com/python.pdf",
            is_active=True,
            display_order=1
        )
        self.course2 = Course.objects.create(
            name="Full Stack Java",
            code="JV-01",
            duration="4 Months",
            brochure_url="https://example.com/java.pdf",
            is_active=True,
            display_order=2
        )

        # Seed dynamic branch
        self.branch1 = Branch.objects.create(
            name="Tech Academy Central",
            address="100 Tech Park, Anna Salai, Chennai",
            latitude=13.0827,
            longitude=80.2707,
            is_active=True
        )

        # Seed default published flow
        self.flow = AutomationFlow.objects.create(
            business_account=self.business_account,
            name="Admissions & Training Flow",
            slug="admissions-training-flow",
            version=1,
            status=AutomationFlow.STATUS_PUBLISHED,
            trigger_type=AutomationFlow.TRIGGER_FIRST_MESSAGE,
            trigger_keywords="hi, hello, hey, start, menu, info, admission, course, training",
            flow_data=get_default_admissions_flow_data(),
            is_active=True,
            published_at=timezone.now()
        )

    def test_normalize_text(self):
        """Test regex text normalization for triggers."""
        from chat.automation.engine import normalize_text
        self.assertEqual(normalize_text("Hi!!!"), "hi")
        self.assertEqual(normalize_text("  HELLO   WORLD  "), "hello world")
        self.assertEqual(normalize_text("What's up???"), "whats up")
        self.assertEqual(normalize_text(""), "")

    def test_flow_builder_view(self):
        """Test that /automation/ page renders successfully."""
        response = self.client.get(reverse('flow-builder'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'flow-name')
        self.assertContains(response, 'palette-nodes-list')
        self.assertContains(response, 'canvasArea')
        self.assertContains(response, 'simulatorDrawer')

    def test_1_first_incoming_message_starts_flow(self):
        """1. First incoming message starts flow and creates an active session."""
        from unittest.mock import patch
        from chat.automation.engine import AutomationEngine
        from chat.models import UserFlowSession

        with patch('chat.whatsapp.client.WhatsAppClient.send_payload', return_value={'messages': [{'id': 'wamid.mock'}]}):
            acted = AutomationEngine.process_incoming(self.conversation, "Hi")
            self.assertTrue(acted)

            session = UserFlowSession.objects.filter(conversation=self.conversation).first()
            self.assertIsNotNone(session)
            self.assertEqual(session.status, UserFlowSession.STATUS_ACTIVE)
            self.assertEqual(session.flow_version, 1)

    def test_2_second_message_does_not_restart_flow(self):
        """2. Second incoming message does not restart the flow."""
        from unittest.mock import patch
        from chat.automation.engine import AutomationEngine
        from chat.models import UserFlowSession

        with patch('chat.whatsapp.client.WhatsAppClient.send_payload', return_value={'messages': [{'id': 'wamid.mock'}]}):
            AutomationEngine.process_incoming(self.conversation, "Hi")
            session = UserFlowSession.objects.get(conversation=self.conversation)
            initial_node = session.current_node_id

            # Customer sends greeting again while session is active
            AutomationEngine.process_incoming(self.conversation, "Hello there")
            session.refresh_from_db()

            # Must NOT restart to greeting or trigger node
            self.assertNotEqual(session.current_node_id, 'trigger_1')
            self.assertNotEqual(session.current_node_id, 'greeting_1')

    def test_3_active_session_continues_current_node(self):
        """3. Active session continues current node and advances on user input."""
        from unittest.mock import patch
        from chat.automation.engine import AutomationEngine
        from chat.models import UserFlowSession

        with patch('chat.whatsapp.client.WhatsAppClient.send_payload', return_value={'messages': [{'id': 'wamid.mock'}]}):
            AutomationEngine.process_incoming(self.conversation, "Hi")
            session = UserFlowSession.objects.get(conversation=self.conversation)
            self.assertEqual(session.current_node_id, 'looking_for_1')

            # User taps button choice 'Training'
            AutomationEngine.process_incoming(
                self.conversation,
                "Training",
                incoming_data={'button_reply': {'id': 'opt_training', 'title': 'Training'}}
            )
            session.refresh_from_db()
            self.assertEqual(session.collected_data.get('looking_for'), 'Training')
            self.assertEqual(session.current_node_id, 'course_list_1')

    def test_4_handed_over_session_stays_silent(self):
        """4. Handed-over session stays completely silent."""
        from chat.automation.engine import AutomationEngine
        from chat.models import UserFlowSession

        session = UserFlowSession.objects.create(
            conversation=self.conversation,
            flow=self.flow,
            flow_version=1,
            current_node_id='course_list_1',
            status=UserFlowSession.STATUS_HANDED_OVER,
            handed_over_at=timezone.now()
        )
        acted = AutomationEngine.process_incoming(self.conversation, "Can someone help me?")
        self.assertFalse(acted)

    def test_5_resume_automation_continues_current_node(self):
        """5. Resuming automation continues at the current node without restarting."""
        from chat.models import UserFlowSession

        session = UserFlowSession.objects.create(
            conversation=self.conversation,
            flow=self.flow,
            flow_version=1,
            current_node_id='date_time_1',
            status=UserFlowSession.STATUS_HANDED_OVER,
            handed_over_at=timezone.now()
        )
        resp = self.client.post(reverse('api-resume-automation', kwargs={'pk': self.conversation.id}))
        self.assertEqual(resp.status_code, 200)

        session.refresh_from_db()
        self.assertEqual(session.status, UserFlowSession.STATUS_ACTIVE)
        self.assertEqual(session.current_node_id, 'date_time_1')

    def test_6_completed_session_stays_silent(self):
        """6. Completed session stays silent on subsequent messages."""
        from chat.automation.engine import AutomationEngine
        from chat.models import UserFlowSession

        session = UserFlowSession.objects.create(
            conversation=self.conversation,
            flow=self.flow,
            flow_version=1,
            current_node_id='end_1',
            status=UserFlowSession.STATUS_COMPLETED,
            completed_at=timezone.now()
        )
        acted = AutomationEngine.process_incoming(self.conversation, "Thank you!")
        self.assertFalse(acted)

    def test_7_completed_flow_does_not_restart_on_new_message(self):
        """7. Completed flow never auto-restarts a session."""
        from chat.automation.engine import AutomationEngine
        from chat.models import UserFlowSession

        session = UserFlowSession.objects.create(
            conversation=self.conversation,
            flow=self.flow,
            flow_version=1,
            current_node_id='end_1',
            status=UserFlowSession.STATUS_COMPLETED,
            completed_at=timezone.now()
        )
        AutomationEngine.process_incoming(self.conversation, "menu")
        self.assertEqual(UserFlowSession.objects.filter(conversation=self.conversation).count(), 1)
        session.refresh_from_db()
        self.assertEqual(session.status, UserFlowSession.STATUS_COMPLETED)

    def test_8_condition_branches_correctly(self):
        """8. Condition node branches correctly to YES or NO target."""
        from unittest.mock import patch
        from chat.automation.engine import AutomationEngine
        from chat.models import UserFlowSession

        # Test condition YES branch
        session = UserFlowSession.objects.create(
            conversation=self.conversation,
            flow=self.flow,
            flow_version=1,
            current_node_id='condition_branch_visit',
            collected_data={'branch_visit': 'YES, Schedule Visit'},
            status=UserFlowSession.STATUS_ACTIVE
        )
        with patch('chat.whatsapp.client.WhatsAppClient.send_payload', return_value={'messages': [{'id': 'wamid.mock'}]}):
            AutomationEngine.execute_node(self.conversation, session, 'condition_branch_visit')
            session.refresh_from_db()
            self.assertEqual(session.current_node_id, 'date_time_1')

        # Test condition NO branch
        session.current_node_id = 'condition_branch_visit'
        session.collected_data = {'branch_visit': 'NO, Online Only'}
        session.save()
        with patch('chat.whatsapp.client.WhatsAppClient.send_payload', return_value={'messages': [{'id': 'wamid.mock'}]}):
            AutomationEngine.execute_node(self.conversation, session, 'condition_branch_visit')
            session.refresh_from_db()
            # NO branch transitions directly to summary_1 and through brochure to end_1
            self.assertEqual(session.status, UserFlowSession.STATUS_COMPLETED)

    def test_9_save_data_stores_values(self):
        """9. Save data node stores values into session collected_data."""
        from unittest.mock import patch
        from chat.automation.engine import AutomationEngine
        from chat.models import AutomationFlow, UserFlowSession

        flow_data = {
            "nodes": [
                {"id": "save_1", "type": "save_data", "data": {"variable": "lead_source", "value": "direct_whatsapp"}},
                {"id": "end_1", "type": "end", "data": {"text": "Done"}}
            ],
            "connections": [
                {"source": "save_1", "source_output": "default", "target": "end_1", "target_input": "input"}
            ]
        }
        flow = AutomationFlow.objects.create(
            name="Save Data Flow", slug="save-data-flow", version=1,
            status=AutomationFlow.STATUS_PUBLISHED, flow_data=flow_data
        )
        session = UserFlowSession.objects.create(
            conversation=self.conversation, flow=flow, flow_version=1,
            current_node_id="save_1", status=UserFlowSession.STATUS_ACTIVE
        )
        with patch('chat.whatsapp.client.WhatsAppClient.send_payload', return_value={'messages': [{'id': 'wamid.mock'}]}):
            AutomationEngine.execute_node(self.conversation, session, "save_1")
            session.refresh_from_db()
            self.assertEqual(session.collected_data.get('lead_source'), 'direct_whatsapp')

    def test_10_dynamic_course_list_loads_courses(self):
        """10. Dynamic course list node loads courses from database Course model."""
        from unittest.mock import patch
        from chat.automation.engine import AutomationEngine
        from chat.models import UserFlowSession

        session = UserFlowSession.objects.create(
            conversation=self.conversation, flow=self.flow, flow_version=1,
            current_node_id='course_list_1', status=UserFlowSession.STATUS_ACTIVE
        )
        with patch('chat.whatsapp.client.WhatsAppClient.send_payload', return_value={'messages': [{'id': 'wamid.mock'}]}) as mock_send:
            AutomationEngine.execute_node(self.conversation, session, 'course_list_1')
            self.assertTrue(mock_send.called)
            payload = mock_send.call_args[0][0]
            interactive = payload.get('interactive', {})
            sections = interactive.get('action', {}).get('sections', [])
            rows = sections[0].get('rows', [])
            titles = [r['title'] for r in rows]
            self.assertIn("Full Stack Python", titles)
            self.assertIn("Full Stack Java", titles)

    def test_11_selected_course_id_is_saved(self):
        """11. Selected course ID and name are saved into session collected_data."""
        from unittest.mock import patch
        from chat.automation.engine import AutomationEngine
        from chat.models import UserFlowSession

        session = UserFlowSession.objects.create(
            conversation=self.conversation, flow=self.flow, flow_version=1,
            current_node_id='course_list_1', status=UserFlowSession.STATUS_ACTIVE
        )
        with patch('chat.whatsapp.client.WhatsAppClient.send_payload', return_value={'messages': [{'id': 'wamid.mock'}]}):
            AutomationEngine.process_incoming(
                self.conversation,
                "Full Stack Python",
                incoming_data={'list_reply': {'id': f"course_{self.course1.id}", 'title': "Full Stack Python"}}
            )
            session.refresh_from_db()
            self.assertEqual(session.collected_data.get('course_id'), self.course1.id)
            self.assertEqual(session.collected_data.get('course_name'), "Full Stack Python")

    def test_12_correct_course_brochure_is_sent(self):
        """12. Course brochure node sends brochure matching the selected course."""
        from unittest.mock import patch
        from chat.automation.engine import AutomationEngine
        from chat.models import UserFlowSession

        session = UserFlowSession.objects.create(
            conversation=self.conversation, flow=self.flow, flow_version=1,
            current_node_id='course_brochure_1',
            collected_data={'course_id': self.course1.id, 'course_name': 'Full Stack Python'},
            status=UserFlowSession.STATUS_ACTIVE
        )
        with patch('chat.whatsapp.client.WhatsAppClient.send_payload', return_value={'messages': [{'id': 'wamid.mock'}]}) as mock_send:
            AutomationEngine.execute_node(self.conversation, session, 'course_brochure_1')
            self.assertTrue(mock_send.called)
            doc_calls = [c[0][0] for c in mock_send.call_args_list if c[0][0].get('type') == 'document']
            self.assertTrue(len(doc_calls) > 0)
            payload = doc_calls[0]
            self.assertEqual(payload['type'], 'document')
            self.assertEqual(payload['document']['link'], self.course1.brochure_url)

    def test_13_correct_branch_location_is_sent(self):
        """13. Branch location node sends GPS location from Branch model."""
        from unittest.mock import patch
        from chat.automation.engine import AutomationEngine
        from chat.models import UserFlowSession

        session = UserFlowSession.objects.create(
            conversation=self.conversation, flow=self.flow, flow_version=1,
            current_node_id='branch_location_1', status=UserFlowSession.STATUS_ACTIVE
        )
        with patch('chat.whatsapp.client.WhatsAppClient.send_payload', return_value={'messages': [{'id': 'wamid.mock'}]}) as mock_send:
            AutomationEngine.execute_node(self.conversation, session, 'branch_location_1')
            self.assertTrue(mock_send.called)
            loc_calls = [c[0][0] for c in mock_send.call_args_list if c[0][0].get('type') == 'location']
            self.assertTrue(len(loc_calls) > 0)
            payload = loc_calls[0]
            self.assertEqual(payload['type'], 'location')
            self.assertEqual(payload['location']['name'], self.branch1.name)
            self.assertEqual(payload['location']['latitude'], self.branch1.latitude)

    def test_14_duplicate_webhook_does_not_execute_twice(self):
        """14. Duplicate webhook delivery does not process or execute twice."""
        from unittest.mock import patch
        from chat.whatsapp.webhook import handle_incoming_webhook_message
        from chat.models import Message

        webhook_msg = {
            "from": "919876540001",
            "id": "wamid.idempotent_test_001",
            "timestamp": "1730000000",
            "type": "text",
            "text": {"body": "Hi"}
        }
        with patch('chat.whatsapp.client.WhatsAppClient.send_payload', return_value={'messages': [{'id': 'wamid.mock'}]}):
            handle_incoming_webhook_message(webhook_msg, self.business_account)
            self.assertEqual(Message.objects.filter(whatsapp_message_id="wamid.idempotent_test_001").count(), 1)
            msg_count_before = Message.objects.count()

            # Redelivery of same message
            handle_incoming_webhook_message(webhook_msg, self.business_account)
            self.assertEqual(Message.objects.filter(whatsapp_message_id="wamid.idempotent_test_001").count(), 1)
            self.assertEqual(Message.objects.count(), msg_count_before)

    def test_15_published_flow_version_cannot_be_modified(self):
        """15. Published flow version cannot be modified in place (HTTP 400)."""
        resp = self.client.put(
            reverse('api-flow-detail', kwargs={'pk': self.flow.id}),
            data=json.dumps({"name": "Modifying Published Flow"}),
            content_type="application/json"
        )
        self.assertEqual(resp.status_code, 400)
        self.assertIn("Cannot modify published flow", resp.json().get('error', ''))

    def test_16_existing_session_remains_on_old_flow_version(self):
        """16. Existing session remains pinned on old flow version after publish."""
        from chat.models import UserFlowSession

        session = UserFlowSession.objects.create(
            conversation=self.conversation, flow=self.flow, flow_version=1,
            current_node_id='looking_for_1', status=UserFlowSession.STATUS_ACTIVE
        )

        # Create draft and publish as v2
        draft_resp = self.client.post(reverse('api-flow-create-draft', kwargs={'pk': self.flow.id}))
        draft_id = draft_resp.json()['flow']['id']
        pub_resp = self.client.post(reverse('api-flow-publish', kwargs={'pk': draft_id}))
        self.assertEqual(pub_resp.status_code, 200)

        # Existing session must stay on flow_version 1
        session.refresh_from_db()
        self.assertEqual(session.flow_version, 1)

    def test_17_new_session_uses_latest_published_version(self):
        """17. New session uses the latest published flow version."""
        from unittest.mock import patch
        from chat.automation.engine import AutomationEngine
        from chat.models import UserFlowSession, Conversation

        draft_resp = self.client.post(reverse('api-flow-create-draft', kwargs={'pk': self.flow.id}))
        draft_id = draft_resp.json()['flow']['id']
        pub_resp = self.client.post(reverse('api-flow-publish', kwargs={'pk': draft_id}))
        self.assertEqual(pub_resp.status_code, 200)

        new_conv = Conversation.objects.create(
            business_account=self.business_account,
            customer_name="Pooja Sharma",
            phone_number="+919876549999"
        )
        with patch('chat.whatsapp.client.WhatsAppClient.send_payload', return_value={'messages': [{'id': 'wamid.mock'}]}):
            AutomationEngine.process_incoming(new_conv, "Hi")
            new_session = UserFlowSession.objects.get(conversation=new_conv)
            self.assertEqual(new_session.flow_version, 2)

    def test_18_invalid_graph_cannot_be_published(self):
        """18. Invalid graph without End node or broken connections cannot be published."""
        from chat.models import AutomationFlow

        invalid_flow = AutomationFlow.objects.create(
            name="Broken Flow", slug="broken-flow", version=1,
            status=AutomationFlow.STATUS_DRAFT,
            flow_data={"nodes": [{"id": "t1", "type": "trigger"}], "connections": []}
        )
        resp = self.client.post(reverse('api-flow-publish', kwargs={'pk': invalid_flow.id}))
        self.assertEqual(resp.status_code, 400)
        self.assertIn("details", resp.json())

    def test_19_end_marks_session_completed(self):
        """19. End node marks session completed with completed_at timestamp."""
        from unittest.mock import patch
        from chat.automation.engine import AutomationEngine
        from chat.models import UserFlowSession

        session = UserFlowSession.objects.create(
            conversation=self.conversation, flow=self.flow, flow_version=1,
            current_node_id='end_1', status=UserFlowSession.STATUS_ACTIVE
        )
        with patch('chat.whatsapp.client.WhatsAppClient.send_payload', return_value={'messages': [{'id': 'wamid.mock'}]}):
            AutomationEngine.execute_node(self.conversation, session, 'end_1')
            session.refresh_from_db()
            self.assertEqual(session.status, UserFlowSession.STATUS_COMPLETED)
            self.assertIsNotNone(session.completed_at)

    def test_20_agent_message_causes_human_handover(self):
        """20. Manual agent message causes human handover and records handed_over_at."""
        from unittest.mock import patch
        from chat.models import UserFlowSession

        session = UserFlowSession.objects.create(
            conversation=self.conversation, flow=self.flow, flow_version=1,
            current_node_id='course_list_1', status=UserFlowSession.STATUS_ACTIVE
        )
        with patch('chat.whatsapp.client.WhatsAppClient.send_payload', return_value={'messages': [{'id': 'wamid.mock'}]}):
            resp = self.client.post(
                reverse('api-message-send'),
                data=json.dumps({"conversation_id": self.conversation.id, "message_text": "Hello, I am taking over."}),
                content_type="application/json"
            )
            self.assertEqual(resp.status_code, 201)
            session.refresh_from_db()
            self.assertEqual(session.status, UserFlowSession.STATUS_HANDED_OVER)
            self.assertIsNotNone(session.handed_over_at)

    def test_business_account_automation_toggle(self):
        """Verify bot does not reply when automation_enabled is False."""
        from chat.automation.engine import AutomationEngine

        self.business_account.automation_enabled = False
        self.business_account.save()

        acted = AutomationEngine.process_incoming(self.conversation, "Hi")
        self.assertFalse(acted)

    def test_21_question_validation_email_retry_and_fallback(self):
        """21. Question node validates email format, retries upon invalid input, and falls back at max retries."""
        from unittest.mock import patch
        from chat.automation.engine import AutomationEngine
        from chat.models import AutomationFlow, UserFlowSession

        flow_data = {
            "nodes": [
                {"id": "q1", "type": "question", "title": "Ask Email", "body": "Please reply with your email:", "variable_name": "student_email", "expected_type": "email", "retry_limit": 2, "invalid_message": "Invalid email address. Please retry:", "next_node_id": "end_step"},
                {"id": "end_step", "type": "end", "title": "End Step", "body": "Thank you!"}
            ],
            "connections": [
                {"source": "q1", "source_output": "default", "target": "end_step", "target_input": "input"}
            ]
        }
        test_flow = AutomationFlow.objects.create(
            name="Email Validation Flow", slug="email-val-flow", version=1,
            status=AutomationFlow.STATUS_DRAFT, flow_data=flow_data
        )
        session = UserFlowSession.objects.create(
            conversation=self.conversation, flow=test_flow, flow_version=1,
            current_node_id='q1', status=UserFlowSession.STATUS_ACTIVE
        )

        with patch('chat.whatsapp.client.WhatsAppClient.send_payload', return_value={'messages': [{'id': 'wamid.mock'}]}) as mock_send:
            # 1. Provide invalid email - first attempt
            acted = AutomationEngine.process_incoming(self.conversation, "not-an-email")
            self.assertTrue(acted)
            session.refresh_from_db()
            self.assertEqual(session.current_node_id, 'q1')
            self.assertEqual(session.collected_data.get('__retry_q1'), 1)

            # 2. Provide invalid email - second attempt (hits max retries 2 -> fallback routes to end_step)
            acted = AutomationEngine.process_incoming(self.conversation, "still-not-email")
            self.assertTrue(acted)
            session.refresh_from_db()
            self.assertEqual(session.status, UserFlowSession.STATUS_COMPLETED)
            self.assertEqual(session.current_node_id, 'end_step')

    def test_22_question_validation_number_success(self):
        """22. Question node with number expected type accepts valid digits and saves variable."""
        from unittest.mock import patch
        from chat.automation.engine import AutomationEngine
        from chat.models import AutomationFlow, UserFlowSession

        flow_data = {
            "nodes": [
                {"id": "q_num", "type": "question", "title": "Ask Age", "body": "Your age?", "variable_name": "user_age", "expected_type": "number", "retry_limit": 3, "next_node_id": "end_step"},
                {"id": "end_step", "type": "end", "title": "Done", "body": "Done!"}
            ],
            "connections": [
                {"source": "q_num", "source_output": "default", "target": "end_step", "target_input": "input"}
            ]
        }
        test_flow = AutomationFlow.objects.create(
            name="Number Flow", slug="num-flow", version=1,
            status=AutomationFlow.STATUS_DRAFT, flow_data=flow_data
        )
        session = UserFlowSession.objects.create(
            conversation=self.conversation, flow=test_flow, flow_version=1,
            current_node_id='q_num', status=UserFlowSession.STATUS_ACTIVE
        )

        with patch('chat.whatsapp.client.WhatsAppClient.send_payload', return_value={'messages': [{'id': 'wamid.mock'}]}):
            acted = AutomationEngine.process_incoming(self.conversation, "25")
            self.assertTrue(acted)
            session.refresh_from_db()
            self.assertEqual(session.collected_data.get('user_age'), '25')
            self.assertEqual(session.current_node_id, 'end_step')

    def test_23_loop_guard_max_depth_prevents_infinite_recursion(self):
        """23. Engine MAX_DEPTH loop guard safely halts cyclical non-waiting loops."""
        from unittest.mock import patch
        from chat.automation.engine import AutomationEngine
        from chat.models import AutomationFlow, UserFlowSession

        # Two message nodes linking to each other in an infinite non-waiting loop
        flow_data = {
            "nodes": [
                {"id": "loop_a", "type": "message", "title": "A", "body": "A", "next_node_id": "loop_b"},
                {"id": "loop_b", "type": "message", "title": "B", "body": "B", "next_node_id": "loop_a"}
            ],
            "connections": [
                {"source": "loop_a", "source_output": "default", "target": "loop_b", "target_input": "input"},
                {"source": "loop_b", "source_output": "default", "target": "loop_a", "target_input": "input"}
            ]
        }
        loop_flow = AutomationFlow.objects.create(
            name="Cycle Flow", slug="cycle-flow", version=1,
            status=AutomationFlow.STATUS_DRAFT, flow_data=flow_data
        )
        session = UserFlowSession.objects.create(
            conversation=self.conversation, flow=loop_flow, flow_version=1,
            current_node_id='loop_a', status=UserFlowSession.STATUS_ACTIVE
        )

        with patch('chat.whatsapp.client.WhatsAppClient.send_payload', return_value={'messages': [{'id': 'wamid.mock'}]}):
            # Must not crash or raise RecursionError
            AutomationEngine.execute_node(self.conversation, session, 'loop_a')
            session.refresh_from_db()
            self.assertIn(session.current_node_id, ['loop_a', 'loop_b'])

    def test_24_validate_flow_api(self):
        """24. ValidateFlowAPI inspects graph and returns errors, warnings, and plain-language messages."""
        # 1. Broken graph validation returns 400 with validation details
        invalid_payload = {
            "flow_data": {
                "nodes": [{"id": "t1", "type": "trigger", "title": "Trigger"}],
                "connections": []
            }
        }
        resp = self.client.post(
            reverse('api-flow-validate-direct'),
            data=json.dumps(invalid_payload),
            content_type="application/json"
        )
        self.assertEqual(resp.status_code, 400)
        data = resp.json()
        self.assertFalse(data['valid'])
        self.assertGreater(data['error_count'], 0)

        # 2. Existing valid template flow validation
        resp_existing = self.client.post(
            reverse('api-flow-validate', kwargs={'pk': self.flow.id})
        )
        self.assertEqual(resp_existing.status_code, 200)
        data_existing = resp_existing.json()
        self.assertTrue(data_existing['valid'])

    def test_25_ai_flow_assistant_api(self):
        """25. AIFlowAssistantAPI generates valid workflow graph from natural language description."""
        payload = {
            "prompt": "Create an appointment booking flow for student counseling",
            "name": "Student Counseling Flow",
            "business_account_id": self.business_account.id
        }
        resp = self.client.post(
            reverse('api-flow-ai-generate'),
            data=json.dumps(payload),
            content_type="application/json"
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertIn('flow', data)
        generated_flow = data['flow']
        nodes = generated_flow['flow_data']['nodes']
        connections = generated_flow['flow_data']['connections']
        self.assertGreaterEqual(len(nodes), 4)
        self.assertGreaterEqual(len(connections), 3)
        self.assertEqual(generated_flow['name'], "Student Counseling Flow")




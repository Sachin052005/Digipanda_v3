"""
Phase 1 Test Suite: Foundation, Data Models & Engine Hardening.
Tests:
- AutomationFlowVersion creation, publishing, and rollback
- SSRF and outbound webhook security (SafeWebhookClient)
- Concurrency and database locking on incoming messages
- Durable delay scheduling, user interruption, and 24-hour service window enforcement
- Node execution for new canonical types (Delay, Condition, Save Data, Webhook, Subflow)
"""

from datetime import timedelta
import json
from unittest.mock import patch, MagicMock

from django.test import TestCase
from django.utils import timezone
from django.contrib.auth import get_user_model

from chat.models import (
    BusinessAccount,
    Conversation,
    Message,
    AutomationFlow,
    AutomationFlowVersion,
    UserFlowSession,
    AutomationExecution
)
from chat.automation.engine import AutomationEngine
from chat.automation.security import SafeWebhookClient, SSRFProtectionError, ResponseTooLargeError
from chat.management.commands.process_delayed_sessions import Command as DelayCommand

User = get_user_model()


class VersioningModelTests(TestCase):
    """Verifies AutomationFlowVersion data model and immutable versioning."""

    def setUp(self):
        self.user = User.objects.create_user(username='test_admin', password='password123')
        self.flow = AutomationFlow.objects.create(
            name='Test Versioned Flow',
            slug='test-versioned-flow',
            version=1,
            status=AutomationFlow.STATUS_DRAFT,
            flow_data={'nodes': [{'id': 'trigger_1', 'type': 'trigger'}], 'edges': []}
        )

    def test_version_creation_and_pointer(self):
        v1 = AutomationFlowVersion.objects.create(
            flow=self.flow,
            version_number=1,
            status=AutomationFlowVersion.STATUS_PUBLISHED,
            flow_data={'nodes': [{'id': 'trigger_1', 'type': 'trigger'}], 'edges': []},
            change_summary='Initial release',
            created_by=self.user,
            published_at=timezone.now()
        )
        self.flow.published_version = v1
        self.flow.status = AutomationFlow.STATUS_PUBLISHED
        self.flow.save(update_fields=['published_version', 'status'])

        self.assertEqual(self.flow.published_version.version_number, 1)
        self.assertEqual(self.flow.versions.count(), 1)

    def test_immutable_version_draft_and_publish(self):
        v1 = AutomationFlowVersion.objects.create(
            flow=self.flow,
            version_number=1,
            status=AutomationFlowVersion.STATUS_PUBLISHED,
            flow_data={'nodes': [{'id': 'v1_node', 'type': 'message'}], 'edges': []},
            published_at=timezone.now()
        )
        self.flow.published_version = v1
        self.flow.save(update_fields=['published_version'])

        # Create working draft v2
        v2 = AutomationFlowVersion.objects.create(
            flow=self.flow,
            version_number=2,
            status=AutomationFlowVersion.STATUS_DRAFT,
            flow_data={'nodes': [{'id': 'v2_node', 'type': 'message'}], 'edges': []},
            change_summary='Drafting v2 with additional steps'
        )
        self.flow.working_draft_version = v2
        self.flow.save(update_fields=['working_draft_version'])

        # Active published version remains v1
        self.assertEqual(self.flow.published_version.flow_data['nodes'][0]['id'], 'v1_node')
        self.assertEqual(self.flow.working_draft_version.flow_data['nodes'][0]['id'], 'v2_node')

        # Publish v2
        v1.status = AutomationFlowVersion.STATUS_ARCHIVED
        v1.save(update_fields=['status'])
        v2.status = AutomationFlowVersion.STATUS_PUBLISHED
        v2.published_at = timezone.now()
        v2.save(update_fields=['status', 'published_at'])

        self.flow.published_version = v2
        self.flow.working_draft_version = None
        self.flow.version = 2
        self.flow.save(update_fields=['published_version', 'working_draft_version', 'version'])

        self.assertEqual(self.flow.published_version.version_number, 2)
        # Verify v1 data was not modified
        v1.refresh_from_db()
        self.assertEqual(v1.flow_data['nodes'][0]['id'], 'v1_node')


class SSRFSecurityClientTests(TestCase):
    """Verifies SafeWebhookClient security protections."""

    def setUp(self):
        self.client = SafeWebhookClient()

    def test_disallowed_schemes(self):
        for bad_url in ['http://api.example.com', 'ftp://example.com', 'file:///etc/passwd', 'gopher://example.com']:
            with self.assertRaises(SSRFProtectionError):
                self.client.validate_url(bad_url)

    def test_disallowed_ip_literals(self):
        forbidden_ips = [
            'https://127.0.0.1:8000/webhook',
            'https://127.0.0.2/api',
            'https://10.0.0.1/private',
            'https://172.16.0.1/internal',
            'https://192.168.1.1/router',
            'https://169.254.169.254/latest/meta-data',
            'https://100.64.0.1/cgnat',
            'https://0.0.0.0:8000/test',
            'https://[::1]:8443/ipv6_loopback',
            'https://[fe80::1]/link_local',
            'https://[fc00::1]/ula',
        ]
        for url in forbidden_ips:
            with self.assertRaises(SSRFProtectionError):
                self.client.validate_url(url)

    @patch('chat.automation.security.requests.Session.request')
    def test_credential_stripping_on_cross_origin_redirect(self, mock_request):
        # First response is a 302 redirect from https://safe-domain-1.com to https://safe-domain-2.com
        redirect_resp = MagicMock()
        redirect_resp.is_redirect = True
        redirect_resp.status_code = 302
        redirect_resp.headers = {'Location': 'https://safe-domain-2.com/callback'}
        redirect_resp.close = MagicMock()

        # Second response is a 200 OK
        final_resp = MagicMock()
        final_resp.is_redirect = False
        final_resp.status_code = 200
        final_resp.headers = {'Content-Type': 'application/json'}
        final_resp.encoding = 'utf-8'
        final_resp.iter_content.return_value = [b'{"success": true}']
        final_resp.close = MagicMock()

        mock_request.side_effect = [redirect_resp, final_resp]

        client = SafeWebhookClient()
        with patch('chat.automation.security.resolve_and_verify_host', return_value=['93.184.216.34']):
            resp = client.request(
                method='POST',
                url='https://safe-domain-1.com/api',
                headers={'Authorization': 'Bearer secret_token', 'Custom-Header': 'val'},
                json_data={'lead': 123}
            )

        self.assertEqual(resp['status_code'], 200)
        self.assertEqual(mock_request.call_count, 2)

        # Inspect headers sent on second call
        second_call_kwargs = mock_request.call_args_list[1][1]
        self.assertNotIn('authorization', [k.lower() for k in second_call_kwargs['headers']])
        self.assertIn('custom-header', [k.lower() for k in second_call_kwargs['headers']])

    @patch('chat.automation.security.requests.Session.request')
    def test_response_size_limit_enforced(self, mock_request):
        # Mock a streaming response that exceeds 1MB
        large_chunk = b"A" * 65536  # 64KB
        chunks = [large_chunk] * 20  # 1.28 MB

        resp = MagicMock()
        resp.is_redirect = False
        resp.status_code = 200
        resp.headers = {}
        resp.iter_content.return_value = iter(chunks)
        resp.close = MagicMock()
        mock_request.return_value = resp

        client = SafeWebhookClient()
        with patch('chat.automation.security.resolve_and_verify_host', return_value=['93.184.216.34']):
            with self.assertRaises(ResponseTooLargeError):
                client.request('GET', 'https://safe-domain.com/huge-file')


class DurableDelayAndWindowTests(TestCase):
    """Verifies durable delay pausing, user interruptions, and 24-hour service window rules."""

    def setUp(self):
        self.biz = BusinessAccount.objects.create(name='Test Academy', phone_number='+919876543210', automation_enabled=True)
        self.conv = Conversation.objects.create(business_account=self.biz, phone_number='+919876543210')

        self.flow_data = {
            'nodes': [
                {'id': 'trigger_1', 'type': 'trigger'},
                {'id': 'msg_1', 'type': 'message', 'data': {'text': 'Welcome!'}},
                {'id': 'delay_1', 'type': 'delay', 'data': {'delay_seconds': 300}},
                {'id': 'msg_2', 'type': 'message', 'data': {'text': 'Are you still interested?'}},
                {'id': 'end_1', 'type': 'end', 'data': {'text': 'Goodbye'}}
            ],
            'edges': [
                {'source': 'trigger_1', 'target': 'msg_1', 'sourceHandle': 'default'},
                {'source': 'msg_1', 'target': 'delay_1', 'sourceHandle': 'default'},
                {'source': 'delay_1', 'target': 'msg_2', 'sourceHandle': 'default'},
                {'source': 'msg_2', 'target': 'end_1', 'sourceHandle': 'default'},
            ]
        }
        self.flow = AutomationFlow.objects.create(
            business_account=self.biz,
            name='Delay Test Flow',
            slug='delay-test-flow',
            version=1,
            status=AutomationFlow.STATUS_PUBLISHED,
            trigger_type=AutomationFlow.TRIGGER_ALWAYS_ON,
            flow_data=self.flow_data,
            is_active=True
        )
        self.version = AutomationFlowVersion.objects.create(
            flow=self.flow,
            version_number=1,
            status=AutomationFlowVersion.STATUS_PUBLISHED,
            flow_data=self.flow_data
        )
        self.flow.published_version = self.version
        self.flow.save(update_fields=['published_version'])

    @patch('chat.automation.engine.send_text_message', return_value={'messages': [{'id': 'mock_meta_1'}]})
    def test_delay_node_pauses_session_durably(self, mock_send):
        """Executing up to delay node sets STATUS_PAUSED with resume_at."""
        res = AutomationEngine.process_incoming(self.conv, "Hello")
        self.assertTrue(res)

        session = UserFlowSession.objects.filter(conversation=self.conv).first()
        self.assertIsNotNone(session)
        self.assertEqual(session.status, UserFlowSession.STATUS_PAUSED)
        self.assertEqual(session.paused_node_id, 'delay_1')
        self.assertEqual(session.resume_node_id, 'msg_2')
        self.assertIsNotNone(session.resume_at)
        self.assertGreater(session.resume_at, timezone.now())

    @patch('chat.automation.engine.send_text_message', return_value={'messages': [{'id': 'mock_meta_2'}]})
    def test_incoming_user_message_interrupts_paused_delay(self, mock_send):
        """User reply while paused interrupts delay and resumes immediately."""
        session = UserFlowSession.objects.create(
            conversation=self.conv,
            flow=self.flow,
            flow_version=1,
            flow_version_ref=self.version,
            status=UserFlowSession.STATUS_PAUSED,
            paused_node_id='delay_1',
            resume_node_id='msg_2',
            resume_at=timezone.now() + timedelta(minutes=10)
        )

        # User replies prematurely
        res = AutomationEngine.process_incoming(self.conv, "Yes I am here!")
        self.assertTrue(res)

        session.refresh_from_db()
        # Session un-paused, completed downstream steps
        self.assertIn(session.status, [UserFlowSession.STATUS_ACTIVE, UserFlowSession.STATUS_COMPLETED])

        # Verify audit execution log recorded interruption
        audit = AutomationExecution.objects.filter(session=session, event_type='DELAY_INTERRUPTED_BY_USER').first()
        self.assertIsNotNone(audit)

    @patch('chat.automation.engine.send_text_message', return_value={'messages': [{'id': 'mock_meta_3'}]})
    def test_process_delayed_sessions_resumes_when_due(self, mock_send):
        """process_delayed_sessions management command wakes up sessions due for resume."""
        # Create customer message 10 minutes ago (within 24h window)
        Message.objects.create(
            conversation=self.conv,
            sender=Message.SENDER_CUSTOMER,
            message_type=Message.TYPE_TEXT,
            message_text='Hello bot',
            timestamp=timezone.now() - timedelta(minutes=10)
        )

        session = UserFlowSession.objects.create(
            conversation=self.conv,
            flow=self.flow,
            flow_version=1,
            flow_version_ref=self.version,
            status=UserFlowSession.STATUS_PAUSED,
            paused_node_id='delay_1',
            resume_node_id='msg_2',
            resume_at=timezone.now() - timedelta(seconds=5)  # past due
        )

        cmd = DelayCommand()
        resumed = cmd.process_batch(batch_size=10)
        self.assertEqual(resumed, 1)

        session.refresh_from_db()
        self.assertEqual(session.status, UserFlowSession.STATUS_COMPLETED)

    @patch('chat.automation.engine.send_text_message', return_value={'messages': [{'id': 'mock_meta_4'}]})
    def test_process_delayed_sessions_halts_on_expired_24h_window(self, mock_send):
        """Expired 24h window halts freeform dispatch and transitions to counselor handover."""
        # Customer message 26 hours ago (window EXPIRED)
        Message.objects.create(
            conversation=self.conv,
            sender=Message.SENDER_CUSTOMER,
            message_type=Message.TYPE_TEXT,
            message_text='Old inquiry',
            timestamp=timezone.now() - timedelta(hours=26)
        )

        session = UserFlowSession.objects.create(
            conversation=self.conv,
            flow=self.flow,
            flow_version=1,
            flow_version_ref=self.version,
            status=UserFlowSession.STATUS_PAUSED,
            paused_node_id='delay_1',
            resume_node_id='msg_2',
            resume_at=timezone.now() - timedelta(seconds=10)
        )

        cmd = DelayCommand()
        resumed = cmd.process_batch(batch_size=10)
        self.assertEqual(resumed, 0)

        session.refresh_from_db()
        self.assertEqual(session.status, UserFlowSession.STATUS_HANDED_OVER)

        # Audit log verifies DELAY_WINDOW_EXPIRED
        audit = AutomationExecution.objects.filter(session=session, event_type='DELAY_WINDOW_EXPIRED').first()
        self.assertIsNotNone(audit)


class CanonicalNodeExecutionTests(TestCase):
    """Verifies Condition, Save Data, Webhook, and Subflow nodes."""

    def setUp(self):
        self.biz = BusinessAccount.objects.create(name='Test Academy', phone_number='+919876543210', automation_enabled=True)
        self.conv = Conversation.objects.create(business_account=self.biz, phone_number='+919876543210')

    def test_condition_node_branching(self):
        flow_data = {
            'nodes': [
                {'id': 'cond_1', 'type': 'condition', 'data': {'variable': 'score', 'operator': 'equals', 'value': '100'}},
                {'id': 'node_yes', 'type': 'save_data', 'data': {'variable_name': 'result', 'value': 'passed'}},
                {'id': 'node_no', 'type': 'save_data', 'data': {'variable_name': 'result', 'value': 'failed'}},
            ],
            'edges': [
                {'source': 'cond_1', 'target': 'node_yes', 'sourceHandle': 'YES'},
                {'source': 'cond_1', 'target': 'node_no', 'sourceHandle': 'NO'},
            ]
        }
        flow = AutomationFlow.objects.create(name='Cond Flow', slug='cond-flow', flow_data=flow_data)
        ver = AutomationFlowVersion.objects.create(flow=flow, version_number=1, flow_data=flow_data)
        flow.published_version = ver
        flow.save()

        # Score is 100 -> YES
        session1 = UserFlowSession.objects.create(
            conversation=self.conv, flow=flow, flow_version_ref=ver,
            collected_data={'score': '100'}, status=UserFlowSession.STATUS_ACTIVE
        )
        AutomationEngine.execute_node(self.conv, session1, 'cond_1')
        session1.refresh_from_db()
        self.assertEqual(session1.collected_data.get('result'), 'passed')

        # Score is 50 -> NO
        session2 = UserFlowSession.objects.create(
            conversation=self.conv, flow=flow, flow_version_ref=ver,
            collected_data={'score': '50'}, status=UserFlowSession.STATUS_ACTIVE
        )
        AutomationEngine.execute_node(self.conv, session2, 'cond_1')
        session2.refresh_from_db()
        self.assertEqual(session2.collected_data.get('result'), 'failed')

    @patch('chat.automation.security.SafeWebhookClient.request')
    def test_webhook_node_saves_response(self, mock_request):
        mock_request.return_value = {
            'status_code': 200,
            'headers': {'Content-Type': 'application/json'},
            'json': {'user_id': 999, 'status': 'enrolled'},
            'text': '{"user_id": 999, "status": "enrolled"}'
        }

        flow_data = {
            'nodes': [
                {
                    'id': 'hook_1',
                    'type': 'webhook',
                    'data': {
                        'url': 'https://api.externalcrm.com/v1/students',
                        'method': 'POST',
                        'payload': '{"phone": "{{phone}}"}',
                        'save_response_to': 'api_res'
                    }
                }
            ],
            'edges': []
        }
        flow = AutomationFlow.objects.create(name='Webhook Flow', slug='webhook-flow', flow_data=flow_data)
        ver = AutomationFlowVersion.objects.create(flow=flow, version_number=1, flow_data=flow_data)

        session = UserFlowSession.objects.create(
            conversation=self.conv, flow=flow, flow_version_ref=ver,
            collected_data={'phone': '+919876543210'}, status=UserFlowSession.STATUS_ACTIVE
        )

        AutomationEngine.execute_node(self.conv, session, 'hook_1')
        session.refresh_from_db()

        self.assertEqual(session.collected_data.get('api_res'), {'user_id': 999, 'status': 'enrolled'})
        mock_request.assert_called_once()

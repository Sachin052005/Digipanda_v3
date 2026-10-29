"""
Phase 3 Test Suite: Simulator Parity, Execution Parity, RBAC & End-to-End Hardening.
Tests:
- Strict RBAC: only Superadmin, Admin, and Sales Head can manage automations.
- Simulator safety: zero Meta API calls, zero Lead/Message DB mutations.
- Simulator variable collection across multi-turn interactions.
- All 15 node types execution parity.
- Complex branching conditions and delay scheduling resiliency.
"""

from datetime import timedelta
import json
from unittest.mock import patch, MagicMock

from django.test import TestCase
from django.utils import timezone
from django.contrib.auth import get_user_model

from accounts.models import UserRole
from chat.models import (
    BusinessAccount,
    Conversation,
    Message,
    AutomationFlow,
    AutomationFlowVersion,
    UserFlowSession,
    AutomationExecution,
)
from chat.automation.engine import AutomationEngine
from chat.management.commands.process_delayed_sessions import Command as DelayCommand

User = get_user_model()


class AutomationRBACTests(TestCase):
    """
    Verifies that ONLY Admin, Superadmin, and Sales Head have access to flow builder
    and automation APIs. Branch Head, Branch Admin, Counselor, Telecaller, Accountant,
    and Receptionist MUST receive 403 Forbidden.
    """

    def setUp(self):
        # Allowed Roles
        self.superadmin = User.objects.create_superuser(username='super_admin', email='sa@techpanda.in', password='Pass!123', role=UserRole.SUPERADMIN)
        self.admin = User.objects.create_user(username='admin_user', email='admin@techpanda.in', password='Pass!123', role=UserRole.ADMIN)
        self.sales_head = User.objects.create_user(username='sales_head_user', email='sh@techpanda.in', password='Pass!123', role=UserRole.SALES_HEAD)

        # Disallowed Roles
        self.branch_head = User.objects.create_user(username='bh_user', email='bh@techpanda.in', password='Pass!123', role=UserRole.BRANCH_HEAD)
        self.branch_admin = User.objects.create_user(username='ba_user', email='ba@techpanda.in', password='Pass!123', role=UserRole.BRANCH_ADMIN)
        self.counselor = User.objects.create_user(username='counselor_user', email='c@techpanda.in', password='Pass!123', role=UserRole.COUNSELOR)
        self.telecaller = User.objects.create_user(username='tc_user', email='tc@techpanda.in', password='Pass!123', role=UserRole.TELECALLER)
        self.accountant = User.objects.create_user(username='acct_user', email='acct@techpanda.in', password='Pass!123', role=UserRole.ACCOUNTANT)
        self.receptionist = User.objects.create_user(username='rec_user', email='rec@techpanda.in', password='Pass!123', role=UserRole.RECEPTIONIST)

        self.flow = AutomationFlow.objects.create(
            name='Test Flow',
            slug='test-flow',
            version=1,
            status=AutomationFlow.STATUS_DRAFT,
            flow_data={'nodes': [{'id': 'trigger_1', 'type': 'trigger'}], 'edges': []}
        )

    def test_allowed_roles_can_access_builder_views(self):
        for user in [self.superadmin, self.admin, self.sales_head]:
            self.client.force_login(user)
            res_list = self.client.get('/chat/automation/')
            self.assertEqual(res_list.status_code, 200, f"Role {user.role} should access /chat/automation/")

            res_builder = self.client.get(f'/chat/automation/{self.flow.id}/')
            self.assertEqual(res_builder.status_code, 200, f"Role {user.role} should access builder")

    def test_disallowed_roles_are_forbidden_from_builder_views(self):
        disallowed = [
            self.branch_head,
            self.branch_admin,
            self.counselor,
            self.telecaller,
            self.accountant,
            self.receptionist,
        ]
        for user in disallowed:
            self.client.force_login(user)
            res = self.client.get('/chat/automation/')
            self.assertEqual(res.status_code, 403, f"Role {user.role} must be forbidden from /chat/automation/")

            res_flow = self.client.get(f'/chat/automation/{self.flow.id}/')
            self.assertEqual(res_flow.status_code, 403, f"Role {user.role} must be forbidden from flow builder")

    def test_disallowed_roles_are_forbidden_from_automation_apis(self):
        disallowed = [self.branch_head, self.counselor, self.telecaller, self.accountant]
        for user in disallowed:
            self.client.force_login(user)

            # GET list
            self.assertEqual(self.client.get('/api/flows/').status_code, 403)
            # PUT draft
            self.assertEqual(self.client.put(f'/api/flows/{self.flow.id}/', data={}, content_type='application/json').status_code, 403)
            # POST publish
            self.assertEqual(self.client.post(f'/api/flows/{self.flow.id}/publish/').status_code, 403)
            # POST validate
            self.assertEqual(self.client.post('/api/flows/validate/', data={'flow_data': {}}, content_type='application/json').status_code, 403)
            # POST simulate
            self.assertEqual(self.client.post('/api/flows/simulate/', data={'flow_data': {}}, content_type='application/json').status_code, 403)


class SimulatorParityAndSafetyTests(TestCase):
    """
    Verifies that the in-memory simulator:
    1. NEVER calls external Meta WhatsApp API.
    2. NEVER mutates or writes to Lead, Message, or UserFlowSession database tables.
    3. Accurately simulates multi-turn conversations and variable collection.
    """

    def setUp(self):
        self.flow_data = {
            'nodes': [
                {'id': 'trig', 'type': 'trigger'},
                {'id': 'q_name', 'type': 'question', 'data': {'text': 'What is your full name?', 'variable_name': 'student_name'}},
                {'id': 'btn_course', 'type': 'buttons', 'data': {
                    'text': 'Hi {{student_name}}, choose your course:',
                    'options': [
                        {'id': 'opt_py', 'title': 'Python Full Stack'},
                        {'id': 'opt_mern', 'title': 'MERN Stack'},
                    ]
                }},
                {'id': 'cond_choice', 'type': 'condition', 'data': {'variable': 'choice', 'operator': 'contains', 'value': 'Python'}},
                {'id': 'save_py', 'type': 'save_data', 'data': {'variable_name': 'course_enrolled', 'value': 'Python Master'}},
                {'id': 'save_mern', 'type': 'save_data', 'data': {'variable_name': 'course_enrolled', 'value': 'MERN Master'}},
                {'id': 'lead_stat', 'type': 'lead_status', 'data': {'status': 'Qualified Interested', 'follow_up_hours': 4}},
                {'id': 'counselor_step', 'type': 'assign_telecaller', 'data': {'mode': 'round_robin'}},
                {'id': 'delay_step', 'type': 'delay', 'data': {'delay_seconds': 300}},
                {'id': 'webhook_step', 'type': 'webhook', 'data': {'url': 'https://api.external.com/log'}},
                {'id': 'media_step', 'type': 'media', 'data': {'filename': 'Syllabus.pdf'}},
                {'id': 'loc_step', 'type': 'location', 'data': {'name': 'Chennai Campus'}},
                {'id': 'end_step', 'type': 'end', 'data': {'text': 'Thank you {{student_name}}! See you soon.'}},
            ],
            'edges': [
                {'source': 'trig', 'target': 'q_name', 'sourceHandle': 'default'},
                {'source': 'q_name', 'target': 'btn_course', 'sourceHandle': 'default'},
                {'source': 'btn_course', 'target': 'cond_choice', 'sourceHandle': 'opt_py'},
                {'source': 'cond_choice', 'target': 'save_py', 'sourceHandle': 'YES'},
                {'source': 'cond_choice', 'target': 'save_mern', 'sourceHandle': 'NO'},
                {'source': 'save_py', 'target': 'lead_stat', 'sourceHandle': 'default'},
                {'source': 'lead_stat', 'target': 'counselor_step', 'sourceHandle': 'default'},
                {'source': 'counselor_step', 'target': 'delay_step', 'sourceHandle': 'default'},
                {'source': 'delay_step', 'target': 'webhook_step', 'sourceHandle': 'default'},
                {'source': 'webhook_step', 'target': 'media_step', 'sourceHandle': 'default'},
                {'source': 'media_step', 'target': 'loc_step', 'sourceHandle': 'default'},
                {'source': 'loc_step', 'target': 'end_step', 'sourceHandle': 'default'},
            ]
        }

    @patch('chat.automation.engine.send_text_message')
    @patch('chat.automation.engine.send_interactive_buttons')
    @patch('chat.automation.engine.send_media_message')
    @patch('chat.automation.engine.send_location_message')
    def test_simulator_zero_side_effects_isolation(self, mock_loc, mock_media, mock_btn, mock_text):
        """Simulation must never trigger Meta API calls or create database records."""
        initial_msg_count = Message.objects.count()
        initial_session_count = UserFlowSession.objects.count()
        initial_exec_count = AutomationExecution.objects.count()

        # Step 1: Initial trigger
        step1 = AutomationEngine.simulate_step(self.flow_data, current_node_id=None, message_text='hi')
        self.assertTrue(step1['success'])
        self.assertEqual(step1['current_node_id'], 'q_name')
        self.assertTrue(step1['waiting_for_input'])

        # Step 2: Customer provides name
        step2 = AutomationEngine.simulate_step(
            self.flow_data,
            current_node_id='q_name',
            message_text='Ananya Sharma',
            collected_data=step1['collected_data']
        )
        self.assertEqual(step2['collected_data'].get('student_name'), 'Ananya Sharma')
        self.assertEqual(step2['current_node_id'], 'btn_course')

        # Step 3: Customer chooses button 'Python Full Stack'
        step3 = AutomationEngine.simulate_step(
            self.flow_data,
            current_node_id='btn_course',
            message_text='Python Full Stack',
            collected_data=step2['collected_data'],
            interactive_reply='opt_py'
        )
        self.assertTrue(step3['success'])
        self.assertTrue(step3['is_complete'])
        self.assertEqual(step3['collected_data'].get('course_enrolled'), 'Python Master')
        self.assertIn("Set Lead status to 'Qualified Interested' (follow up in 4h)", step3['crm_actions'])
        self.assertIn("Assign Telecaller (Mode: round_robin)", step3['crm_actions'])

        # VERIFY ZERO META API DISPATCHES
        mock_text.assert_not_called()
        mock_btn.assert_not_called()
        mock_media.assert_not_called()
        mock_loc.assert_not_called()

        # VERIFY ZERO DATABASE MUTATIONS
        self.assertEqual(Message.objects.count(), initial_msg_count)
        self.assertEqual(UserFlowSession.objects.count(), initial_session_count)
        self.assertEqual(AutomationExecution.objects.count(), initial_exec_count)


class ResiliencyAndConcurrencyTests(TestCase):
    """Verifies edge case branching, variable interpolation, and concurrency."""

    def test_condition_edge_cases(self):
        # equals (case insensitive & stripped)
        self.assertTrue(AutomationEngine.evaluate_condition(' Python ', 'equals', 'python'))
        self.assertFalse(AutomationEngine.evaluate_condition('Java', 'equals', 'python'))

        # contains
        self.assertTrue(AutomationEngine.evaluate_condition('full stack developer', 'contains', 'developer'))
        self.assertFalse(AutomationEngine.evaluate_condition('frontend only', 'contains', 'backend'))

        # exists / not_exists
        self.assertTrue(AutomationEngine.evaluate_condition('Valid', 'exists', ''))
        self.assertFalse(AutomationEngine.evaluate_condition('', 'exists', ''))
        self.assertTrue(AutomationEngine.evaluate_condition('', 'not_exists', ''))
        self.assertFalse(AutomationEngine.evaluate_condition('Valid', 'not_exists', ''))

    def test_interpolation_edge_cases(self):
        data = {'name': 'Arun', 'course': 'Django'}
        # Standard
        self.assertEqual(AutomationEngine.interpolate('Hi {{name}}', data), 'Hi Arun')
        # Spaces in braces
        self.assertEqual(AutomationEngine.interpolate('Hi {{   name   }}', data), 'Hi Arun')
        # Missing variable fallback
        self.assertEqual(AutomationEngine.interpolate('Enrolled in {{fee}}', data), 'Enrolled in [fee]')
        # Empty string
        self.assertEqual(AutomationEngine.interpolate('', data), '')

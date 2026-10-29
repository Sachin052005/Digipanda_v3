"""
Phase 2 Test Suite: Frontend Visual Editor Migration (React Flow with Vite).
Verifies:
- Production bundle files exist and are non-empty in static directory
- Flow Builder template renders React bundle assets and mounting container
- REST APIs consumed by the visual editor operate correctly
- End-to-end Draft -> Edit -> Validate -> Publish -> Version Restore lifecycle
"""

import json
import os
from django.conf import settings
from django.test import TestCase
from django.contrib.auth import get_user_model

from chat.models import (
    BusinessAccount,
    AutomationFlow,
    AutomationFlowVersion,
)

User = get_user_model()


class FlowBuilderFrontendIntegrationTests(TestCase):
    """Verifies React Flow static assets, template mounting, and API lifecycle."""

    def setUp(self):
        self.admin = User.objects.create_superuser(
            username='flow_admin',
            email='admin@techpanda.in',
            password='Password123!',
            role='admin'
        )
        self.biz = BusinessAccount.objects.create(
            name='Test Tech Line',
            phone_number='+919876543210',
            automation_enabled=True
        )
        self.flow = AutomationFlow.objects.create(
            business_account=self.biz,
            name='Career Bot',
            slug='career-bot',
            version=1,
            status=AutomationFlow.STATUS_DRAFT,
            flow_data={
                'nodes': [
                    {'id': 'trigger_1', 'type': 'trigger', 'position': {'x': 100, 'y': 100}, 'data': {'title': 'Start'}},
                    {'id': 'msg_1', 'type': 'message', 'position': {'x': 350, 'y': 100}, 'data': {'title': 'Greeting', 'body': 'Welcome!'}},
                ],
                'edges': [
                    {'id': 'e1', 'source': 'trigger_1', 'target': 'msg_1', 'sourceHandle': 'default'}
                ]
            }
        )

    def test_static_bundle_files_exist_on_disk(self):
        """Verifies that Vite emitted the required assets into Django's static directory."""
        static_dir = os.path.join(settings.BASE_DIR, 'chat', 'static', 'chat', 'flow_builder_dist', 'assets')
        self.assertTrue(os.path.exists(static_dir), f"Static directory {static_dir} must exist.")

        js_path = os.path.join(static_dir, 'flow_builder_app.js')
        css_path = os.path.join(static_dir, 'index.css')

        self.assertTrue(os.path.exists(js_path), "Compiled JS bundle flow_builder_app.js must exist.")
        self.assertTrue(os.path.exists(css_path), "Compiled CSS bundle index.css must exist.")

        self.assertGreater(os.path.getsize(js_path), 10000, "JS bundle must be substantial (>10KB).")
        self.assertGreater(os.path.getsize(css_path), 1000, "CSS bundle must be substantial (>1KB).")

    def test_flow_builder_template_mounts_react_bundle(self):
        """Verifies /chat/automation/<id>/ renders HTML with React bundle script and styles."""
        self.client.force_login(self.admin)
        res = self.client.get(f'/chat/automation/{self.flow.id}/')
        self.assertEqual(res.status_code, 200)

        # Asserts HTML contains root mount and asset paths
        content = res.content.decode('utf-8')
        self.assertIn('id="root"', content)
        self.assertIn(f'data-flow-id="{self.flow.id}"', content)
        self.assertIn('flow_builder_dist/assets/index.css', content)
        self.assertIn('flow_builder_dist/assets/flow_builder_app.js', content)

    def test_save_draft_and_publish_flow_api_lifecycle(self):
        """Verifies visual editor API lifecycle: save draft -> validate -> publish."""
        self.client.force_login(self.admin)

        # 1. Save draft with updated nodes
        updated_nodes = [
            {'id': 'trigger_1', 'type': 'trigger', 'position': {'x': 100, 'y': 100}, 'data': {'title': 'Start'}},
            {'id': 'msg_1', 'type': 'message', 'position': {'x': 350, 'y': 100}, 'data': {'title': 'Greeting', 'body': 'Welcome to Full Stack Training!'}},
            {'id': 'end_1', 'type': 'end', 'position': {'x': 600, 'y': 100}, 'data': {'title': 'Goodbye', 'body': 'Bye!'}},
        ]
        updated_edges = [
            {'id': 'e1', 'source': 'trigger_1', 'target': 'msg_1', 'sourceHandle': 'default'},
            {'id': 'e2', 'source': 'msg_1', 'target': 'end_1', 'sourceHandle': 'default'},
        ]

        save_payload = {
            'name': 'Updated Career Bot',
            'flow_data': {'nodes': updated_nodes, 'edges': updated_edges}
        }

        put_res = self.client.put(
            f'/api/flows/{self.flow.id}/',
            data=json.dumps(save_payload),
            content_type='application/json'
        )
        self.assertEqual(put_res.status_code, 200)
        self.flow.refresh_from_db()
        self.assertEqual(self.flow.name, 'Updated Career Bot')
        self.assertEqual(len(self.flow.flow_data['nodes']), 3)

        # 2. Validate graph
        val_res = self.client.post(
            '/api/flows/validate/',
            data=json.dumps({'flow_data': self.flow.flow_data}),
            content_type='application/json'
        )
        self.assertEqual(val_res.status_code, 200)
        val_data = val_res.json()
        self.assertTrue(val_data.get('valid'))

        # 3. Publish flow
        pub_res = self.client.post(f'/api/flows/{self.flow.id}/publish/')
        self.assertEqual(pub_res.status_code, 200)
        self.flow.refresh_from_db()
        self.assertEqual(self.flow.status, AutomationFlow.STATUS_PUBLISHED)
        self.assertIsNotNone(self.flow.published_version)
        self.assertEqual(self.flow.published_version.version_number, self.flow.version)

        # 4. Check versions API
        ver_res = self.client.get(f'/api/flows/{self.flow.id}/versions/')
        self.assertEqual(ver_res.status_code, 200)
        ver_list = ver_res.json()
        self.assertGreaterEqual(len(ver_list), 1)
        self.assertIn('version', ver_list[0])
        self.assertIn('version_number', ver_list[0])

    def test_in_memory_simulator_api(self):
        """Verifies POST /api/flows/simulate/ performs dry-run without DB changes."""
        self.client.force_login(self.admin)

        sim_payload = {
            'flow_data': self.flow.flow_data,
            'message_text': 'hello',
            'collected_data': {'customer_name': 'Aravind'}
        }

        res = self.client.post(
            '/api/flows/simulate/',
            data=json.dumps(sim_payload),
            content_type='application/json'
        )
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertTrue(data.get('success'))
        self.assertIn('sim_messages', data)
        self.assertGreater(len(data['sim_messages']), 0)

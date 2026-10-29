import json
from unittest.mock import patch
from django.test import TestCase, Client, override_settings
from django.urls import reverse
from django.utils import timezone

from accounts.models import User, UserRole
from chat.models import BusinessAccount, AutomationFlow, UserFlowSession
from chat.automation.engine import AutomationEngine
from chat.automation.validator import validate_flow_graph


class WhatsAppVisualFlowBuilderTests(TestCase):
    """
    Comprehensive test suite verifying Milestones 1 through 5 of the
    TECHPANDA CRM WhatsApp Automation Visual Flow Builder & Simulator.
    """

    def setUp(self):
        self.client = Client()
        # Admin user with full automation permissions
        self.admin = User.objects.create_user(
            username=f'flow_admin_{id(self)}',
            password='Password123!',
            role=UserRole.ADMIN,
            is_staff=True,
            is_superuser=True
        )

        # Telecaller without automation management permissions
        self.telecaller = User.objects.create_user(
            username=f'flow_telecaller_{id(self)}',
            password='Password123!',
            role=UserRole.TELECALLER,
            is_staff=False
        )

        self.business_account = BusinessAccount.objects.create(
            name="Main Admissions Line",
            phone_number="+91 84382 39448",
            phone_number_id="1294166677119820",
            is_default=True,
            is_active=True
        )

        self.valid_flow_data = {
            "nodes": [
                {
                    "id": "trigger_1",
                    "type": "trigger",
                    "position": {"x": 100, "y": 100},
                    "next_node_id": "msg_welcome",
                    "trigger_type": "all_incoming"
                },
                {
                    "id": "msg_welcome",
                    "type": "message",
                    "title": "Welcome Greeting",
                    "body": "Welcome to TECHPANDA! Are you looking for courses or career advice?",
                    "position": {"x": 350, "y": 100},
                    "next_node_id": "q_name"
                },
                {
                    "id": "q_name",
                    "type": "question",
                    "title": "Ask Name",
                    "body": "What is your full name?",
                    "variable_name": "student_name",
                    "expected_type": "text",
                    "position": {"x": 600, "y": 100},
                    "next_node_id": "end_flow"
                },
                {
                    "id": "end_flow",
                    "type": "end",
                    "title": "Session End",
                    "body": "Thank you, {{student_name}}! An advisor will reach out shortly.",
                    "position": {"x": 850, "y": 100}
                }
            ],
            "connections": [
                {"id": "conn_1", "from": "trigger_1", "to": "msg_welcome"},
                {"id": "conn_2", "from": "msg_welcome", "to": "q_name"},
                {"id": "conn_3", "from": "q_name", "to": "end_flow"}
            ]
        }

        self.flow = AutomationFlow.objects.create(
            business_account=self.business_account,
            name="Admissions Onboarding Flow",
            status="draft",
            version=1,
            flow_data=self.valid_flow_data
        )

    # =========================================================================
    # Milestone 1: Routes, Permissions & Template Rendering
    # =========================================================================

    def test_routes_exist_and_accessible_for_admin(self):
        """Verify /chat/automation/, /automation/, and /chat/automations/ are accessible."""
        self.client.force_login(self.admin)

        # 1. Flow Builder Canvas views
        for route in ['/chat/automation/', '/automation/']:
            response = self.client.get(route)
            self.assertEqual(response.status_code, 200, f"Route {route} failed with {response.status_code}")
            self.assertContains(response, 'id="canvasViewport"')
            self.assertContains(response, 'id="canvasPlane"')
            self.assertContains(response, 'id="btnSaveDraft"')
            self.assertContains(response, 'id="btnPublishFlow"')
            self.assertContains(response, 'id="btnValidateFlow"')
            self.assertContains(response, 'id="btnVersionHistory"')
            self.assertContains(response, 'id="simulatorDrawer"')

        # 2. Automations Dashboard List view
        res_dash = self.client.get('/chat/automations/')
        self.assertEqual(res_dash.status_code, 200)
        self.assertContains(res_dash, 'btnCreateNewAutomation')

    def test_permissions_unauthorized_user_blocked(self):
        """Telecaller without automation permissions cannot access or modify flows."""
        self.client.force_login(self.telecaller)

        # UI view redirects or blocks
        res_view = self.client.get('/chat/automation/')
        self.assertIn(res_view.status_code, [302, 403])

        # API endpoint blocks
        res_api = self.client.get(f'/api/flows/{self.flow.id}/')
        self.assertIn(res_api.status_code, [403, 401])

        # Publish API blocks
        res_pub = self.client.post(f'/api/flows/{self.flow.id}/publish/')
        self.assertIn(res_pub.status_code, [403, 401])

    # =========================================================================
    # Milestone 2: Flow CRUD, Save Draft & Auto-Fork
    # =========================================================================

    def test_update_draft_flow_success(self):
        """Updating a draft flow persists modifications correctly."""
        self.client.force_login(self.admin)

        updated_data = dict(self.valid_flow_data)
        updated_data["nodes"][1]["body"] = "Updated welcome message for new applicants."

        response = self.client.put(
            f'/api/flows/{self.flow.id}/',
            data=json.dumps({
                "name": "Updated Admissions Flow",
                "flow_data": updated_data
            }),
            content_type='application/json'
        )
        self.assertEqual(response.status_code, 200)

        self.flow.refresh_from_db()
        self.assertEqual(self.flow.name, "Updated Admissions Flow")
        self.assertEqual(self.flow.flow_data["nodes"][1]["body"], "Updated welcome message for new applicants.")

    def test_published_flow_cannot_be_mutated_directly(self):
        """A published flow returns HTTP 400 when attempting to overwrite without auto_fork_draft."""
        self.client.force_login(self.admin)
        self.flow.status = 'published'
        self.flow.save()

        response = self.client.put(
            f'/api/flows/{self.flow.id}/',
            data=json.dumps({"name": "Corrupt Published"}),
            content_type='application/json'
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("Cannot modify published flow", response.json().get('error', ''))

    def test_published_flow_auto_fork_draft(self):
        """Saving changes on a published flow with auto_fork_draft creates a new draft version transparently."""
        self.client.force_login(self.admin)
        self.flow.status = 'published'
        self.flow.version = 1
        self.flow.save()

        response = self.client.put(
            f'/api/flows/{self.flow.id}/',
            data=json.dumps({
                "name": "Admissions Flow (Forked)",
                "flow_data": self.valid_flow_data,
                "auto_fork_draft": True
            }),
            content_type='application/json'
        )
        self.assertIn(response.status_code, [200, 201])
        res_json = response.json()
        new_flow_id = res_json.get('id') or res_json.get('flow', {}).get('id')

        # Original published flow remains unchanged and published
        self.flow.refresh_from_db()
        self.assertEqual(self.flow.status, 'published')
        self.assertEqual(self.flow.version, 1)

        # New draft flow exists with incremented version
        new_draft = AutomationFlow.objects.get(id=new_flow_id)
        self.assertEqual(new_draft.status, 'draft')
        self.assertEqual(new_draft.version, 2)
        self.assertEqual(new_draft.name, "Admissions Flow (Forked)")

    # =========================================================================
    # Milestone 3: Version History & Rollback / Restore
    # =========================================================================

    def test_version_history_and_restore(self):
        """Verifies Flow versions are listed and can be restored to a new draft."""
        self.client.force_login(self.admin)

        # Publish version 1
        pub_res = self.client.post(f'/api/flows/{self.flow.id}/publish/')
        self.assertEqual(pub_res.status_code, 200)

        # Check version list API
        versions_res = self.client.get(f'/api/flows/{self.flow.id}/versions/')
        self.assertEqual(versions_res.status_code, 200)
        versions_data = versions_res.json()
        versions_list = versions_data if isinstance(versions_data, list) else versions_data.get('versions', [])
        self.assertGreaterEqual(len(versions_list), 1)
        self.assertEqual(versions_list[0]['version'], 1)

        # Restore version 1 to a new editable draft
        restore_res = self.client.post(f'/api/flows/{self.flow.id}/restore-version/')
        self.assertIn(restore_res.status_code, [200, 201])
        restore_json = restore_res.json()
        self.assertIn('flow', restore_json)
        restored_flow_id = restore_json['flow']['id']

        restored_flow = AutomationFlow.objects.get(id=restored_flow_id)
        self.assertEqual(restored_flow.status, 'draft')
        self.assertEqual(restored_flow.version, 2)

    # =========================================================================
    # Milestone 4: Graph Validation Engine
    # =========================================================================

    def test_validator_detects_broken_or_orphan_nodes(self):
        """Validator flags orphan nodes, unreachable nodes, and non-existent targets."""
        invalid_graph = {
            "nodes": [
                {
                    "id": "trigger_1",
                    "type": "trigger",
                    "next_node_id": "ghost_node"  # Broken target
                },
                {
                    "id": "orphan_node",
                    "type": "message",
                    "title": "Nobody points here",
                    "body": "Orphan text"
                }
            ],
            "connections": []
        }

        val_res = validate_flow_graph(invalid_graph)
        self.assertFalse(val_res["valid"])
        self.assertGreaterEqual(len(val_res["errors"]), 1)

        # API endpoint validation
        self.client.force_login(self.admin)
        res = self.client.post(
            '/api/flows/validate/',
            data=json.dumps({"flow_data": invalid_graph}),
            content_type='application/json'
        )
        self.assertIn(res.status_code, [200, 400])
        data = res.json()
        self.assertFalse(data['valid'])
        self.assertIn('errors', data)

    # =========================================================================
    # Milestone 5: WhatsApp In-Memory Simulator (Zero Meta API, Zero DB mutations)
    # =========================================================================

    def test_simulator_dry_run_step_execution(self):
        """Backend simulator evaluates node execution in pure memory with zero external calls."""
        self.client.force_login(self.admin)

        # Step 1: Start at trigger -> engine auto-advances through welcome message to the question
        sim_step_1 = self.client.post(
            f'/api/flows/{self.flow.id}/simulate/',
            data=json.dumps({
                "flow_data": self.valid_flow_data,
                "current_node_id": None,
                "user_input": None,
                "collected_data": {}
            }),
            content_type='application/json'
        )
        self.assertEqual(sim_step_1.status_code, 200)
        data_1 = sim_step_1.json()
        self.assertTrue(data_1.get('success'))
        self.assertEqual(data_1.get('current_node_id'), 'q_name')
        messages = data_1.get('sim_messages', [])
        self.assertTrue(any("Welcome to TECHPANDA" in (m.get('body') or '') for m in messages))
        self.assertTrue(any("full name" in (m.get('body') or '') for m in messages))

        # Step 2: Provide user response to question -> completes question and moves to end node
        sim_step_2 = self.client.post(
            f'/api/flows/{self.flow.id}/simulate/',
            data=json.dumps({
                "flow_data": self.valid_flow_data,
                "current_node_id": 'q_name',
                "user_input": "Rajesh Sharma",
                "collected_data": {}
            }),
            content_type='application/json'
        )
        self.assertEqual(sim_step_2.status_code, 200)
        data_2 = sim_step_2.json()
        self.assertEqual(data_2.get('collected_data', {}).get('student_name'), 'Rajesh Sharma')
        self.assertEqual(data_2.get('current_node_id'), 'end_flow')
        end_msgs = data_2.get('sim_messages', [])
        self.assertTrue(any("Thank you, Rajesh Sharma" in (m.get('body') or '') for m in end_msgs))

    # =========================================================================
    # QA End-to-End: Create a New Flow in Editor Lifecycle
    # =========================================================================

    def test_end_to_end_create_new_flow_in_editor_lifecycle(self):
        """
        QA verification test simulating full administrator journey:
        1. Click 'New Flow' in editor -> Create new flow via POST /api/flows/
        2. Open flow in editor by route /chat/automation/<id>/ (context contains data-flow-id)
        3. Edit nodes & connections in canvas (buttons, question, save_data, lead_status, end)
        4. Save Draft via PUT /api/flows/<id>/
        5. Validate flow via POST /api/flows/<id>/validate/
        6. Dry-run simulate conversation turns via POST /api/flows/<id>/simulate/
        7. Publish flow live via POST /api/flows/<id>/publish/
        """
        self.client.force_login(self.admin)

        # 1. Administrator creates a new flow in the editor
        create_payload = {
            "name": "Python Full-Stack Career Bot",
            "slug": "python-full-stack-career-bot",
            "trigger_type": "keyword",
            "trigger_keywords": "python, django, fullstack",
            "business_account": self.business_account.id,
            "flow_data": {
                "nodes": [
                    {
                        "id": "trigger_1",
                        "type": "trigger",
                        "title": "Keyword Trigger",
                        "trigger_type": "keyword",
                        "data": {"keywords": "python, django, fullstack"},
                        "next_node_id": "msg_intro",
                        "position": {"x": 100, "y": 100}
                    },
                    {
                        "id": "msg_intro",
                        "type": "message",
                        "title": "Welcome Greeting",
                        "body": "Welcome to TECHPANDA Python Career Track! Are you a beginner or experienced developer?",
                        "next_node_id": "btn_level",
                        "position": {"x": 350, "y": 100}
                    },
                    {
                        "id": "btn_level",
                        "type": "buttons",
                        "title": "Select Level",
                        "body": "Please choose your experience level:",
                        "options": [
                            {"id": "opt_beg", "title": "Beginner", "next_node_id": "q_contact"},
                            {"id": "opt_adv", "title": "Experienced", "next_node_id": "q_contact"}
                        ],
                        "position": {"x": 600, "y": 100}
                    },
                    {
                        "id": "q_contact",
                        "type": "question",
                        "title": "Ask Email",
                        "body": "Please share your email address so we can send the Python syllabus:",
                        "variable_name": "student_email",
                        "expected_type": "email",
                        "next_node_id": "end_done",
                        "position": {"x": 850, "y": 100}
                    },
                    {
                        "id": "end_done",
                        "type": "end",
                        "title": "Session Completed",
                        "body": "Thank you! Our admissions mentor will email the syllabus to {{student_email}} shortly.",
                        "position": {"x": 1100, "y": 100}
                    }
                ],
                "connections": [
                    {"id": "c1", "source": "trigger_1", "source_output": "default", "target": "msg_intro", "target_input": "input"},
                    {"id": "c2", "source": "msg_intro", "source_output": "default", "target": "btn_level", "target_input": "input"},
                    {"id": "c3", "source": "btn_level", "source_output": "opt_beg", "target": "q_contact", "target_input": "input"},
                    {"id": "c4", "source": "btn_level", "source_output": "opt_adv", "target": "q_contact", "target_input": "input"},
                    {"id": "c5", "source": "q_contact", "source_output": "default", "target": "end_done", "target_input": "input"}
                ]
            }
        }

        res_create = self.client.post('/api/flows/', data=json.dumps(create_payload), content_type='application/json')
        self.assertEqual(res_create.status_code, 201)
        created_data = res_create.json()
        new_flow_id = created_data['id']
        self.assertEqual(created_data['name'], "Python Full-Stack Career Bot")
        self.assertEqual(created_data['status'], "draft")
        self.assertEqual(created_data['version'], 1)

        # 2. Open created flow directly by URL in the visual editor
        res_editor = self.client.get(f'/chat/automation/{new_flow_id}/')
        self.assertEqual(res_editor.status_code, 200)
        self.assertContains(res_editor, f'data-flow-id="{new_flow_id}"')
        self.assertContains(res_editor, 'id="btnNewFlow"')
        self.assertContains(res_editor, 'id="newFlowModal"')

        # 3. Modify flow nodes & connections in canvas (Save Draft)
        updated_flow_data = dict(create_payload["flow_data"])
        updated_flow_data["nodes"][1]["body"] = "Welcome to TECHPANDA! Top-rated Full-Stack training."
        res_update = self.client.put(
            f'/api/flows/{new_flow_id}/',
            data=json.dumps({"name": "Python Full-Stack Career Bot (Updated)", "flow_data": updated_flow_data}),
            content_type='application/json'
        )
        self.assertEqual(res_update.status_code, 200)

        # 4. Validate graph integrity
        res_val = self.client.post(f'/api/flows/{new_flow_id}/validate/')
        self.assertEqual(res_val.status_code, 200)
        val_data = res_val.json()
        self.assertTrue(val_data['valid'])
        self.assertEqual(len(val_data['errors']), 0)

        # 5. Dry-run conversation simulation
        # Turn 1: Bot triggers, plays greeting, and presents options
        sim_turn_1 = self.client.post(
            f'/api/flows/{new_flow_id}/simulate/',
            data=json.dumps({
                "flow_data": updated_flow_data,
                "current_node_id": None,
                "user_input": None,
                "collected_data": {}
            }),
            content_type='application/json'
        )
        self.assertEqual(sim_turn_1.status_code, 200)
        turn_1_data = sim_turn_1.json()
        self.assertEqual(turn_1_data.get('current_node_id'), 'btn_level')
        self.assertTrue(turn_1_data.get('waiting_for_input'))

        # Turn 2: User clicks "Beginner" -> advances to question asking email
        sim_turn_2 = self.client.post(
            f'/api/flows/{new_flow_id}/simulate/',
            data=json.dumps({
                "flow_data": updated_flow_data,
                "current_node_id": 'btn_level',
                "user_input": "Beginner",
                "interactive_reply": {"type": "button_reply", "id": "opt_beg"},
                "collected_data": turn_1_data.get('collected_data', {})
            }),
            content_type='application/json'
        )
        self.assertEqual(sim_turn_2.status_code, 200)
        turn_2_data = sim_turn_2.json()
        self.assertEqual(turn_2_data.get('current_node_id'), 'q_contact')
        self.assertTrue(turn_2_data.get('waiting_for_input'))

        # Turn 3: User enters valid email -> advances to end node
        sim_turn_3 = self.client.post(
            f'/api/flows/{new_flow_id}/simulate/',
            data=json.dumps({
                "flow_data": updated_flow_data,
                "current_node_id": 'q_contact',
                "user_input": "candidate@gmail.com",
                "collected_data": turn_2_data.get('collected_data', {})
            }),
            content_type='application/json'
        )
        self.assertEqual(sim_turn_3.status_code, 200)
        turn_3_data = sim_turn_3.json()
        self.assertEqual(turn_3_data.get('current_node_id'), 'end_done')
        self.assertTrue(turn_3_data.get('is_complete'))
        self.assertEqual(turn_3_data.get('collected_data', {}).get('student_email'), 'candidate@gmail.com')

        # 6. Publish flow live
        res_pub = self.client.post(f'/api/flows/{new_flow_id}/publish/')
        self.assertEqual(res_pub.status_code, 200)
        pub_json = res_pub.json()
        self.assertEqual(pub_json['flow']['status'], 'published')
        self.assertEqual(pub_json['flow']['version'], 1)

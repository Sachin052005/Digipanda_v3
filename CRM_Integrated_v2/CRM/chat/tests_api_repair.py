import json
from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth import get_user_model
from rest_framework import status

from accounts.models import UserRole
from branches.models import Branch
from chat.models import (
    BusinessAccount,
    AutomationFlow,
    AutomationFlowVersion,
    UserFlowSession,
    Message
)
from fb_leads.models import FacebookLead
from fb_leads.crm import push_to_crm
from leads.models import Lead

User = get_user_model()


class FlowBuilderAPIRepairTests(TestCase):
    def setUp(self):
        # Create active branch
        self.branch = Branch.objects.create(name="Velachery Branch")

        # Create authorized Admin user
        self.admin_user = User.objects.create_user(
            username="admin_repair",
            password="password123",
            role=UserRole.ADMIN,
            is_active=True
        )

        # Create authorized Sales Head user
        self.sales_head = User.objects.create_user(
            username="sales_head_repair",
            password="password123",
            role=UserRole.SALES_HEAD,
            is_active=True
        )

        # Create unauthorized Counselor user
        self.counselor = User.objects.create_user(
            username="counselor_repair",
            password="password123",
            role=UserRole.COUNSELOR,
            is_active=True
        )

        # Create WhatsApp business account
        self.biz_account = BusinessAccount.objects.create(
            name="Digipanda Support Line",
            phone_number="+918438239448",
            phone_number_id="1294166677119820",
            business_account_id="1107454935187904",
            is_default=True,
            is_active=True
        )

        # Create test Automation Flow
        self.flow = AutomationFlow.objects.create(
            name="Admissions Onboarding",
            slug="admissions-onboarding",
            version=1,
            status=AutomationFlow.STATUS_DRAFT,
            trigger_type=AutomationFlow.TRIGGER_FIRST_MESSAGE,
            business_account=self.biz_account,
            flow_data={
                "nodes": [
                    {"id": "trigger_1", "type": "trigger", "title": "Trigger", "position": {"x": 100, "y": 100}},
                    {"id": "msg_1", "type": "message", "title": "Welcome", "position": {"x": 100, "y": 250}, "data": {"text": "Welcome to DigiPanda!"}}
                ],
                "edges": [
                    {"id": "e_1", "source": "trigger_1", "target": "msg_1", "sourceHandle": "default"}
                ]
            }
        )

        self.version1 = AutomationFlowVersion.objects.create(
            flow=self.flow,
            version_number=1,
            status=AutomationFlowVersion.STATUS_DRAFT,
            flow_data=self.flow.flow_data,
            change_summary="Initial setup draft"
        )
        self.flow.working_draft_version = self.version1
        self.flow.save()

        self.client = Client()

    def test_flow_detail_and_404_behavior(self):
        """GET /api/flows/<id>/ returns flow detail or clean 404 for non-existent IDs."""
        self.client.force_login(self.admin_user)

        # Existing flow
        res = self.client.get(f"/api/flows/{self.flow.id}/")
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res.json()["name"], "Admissions Onboarding")
        self.assertEqual(res.json()["id"], self.flow.id)

        # Non-existent flow ID (such as legacy fallback ID 9999)
        res_404 = self.client.get("/api/flows/9999/")
        self.assertEqual(res_404.status_code, status.HTTP_404_NOT_FOUND)

    def test_flow_versions_endpoint(self):
        """GET /api/flows/<id>/versions/ returns list of immutable version records."""
        self.client.force_login(self.admin_user)
        res = self.client.get(f"/api/flows/{self.flow.id}/versions/")
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        versions = res.json()
        self.assertTrue(isinstance(versions, list))
        self.assertGreaterEqual(len(versions), 1)
        self.assertEqual(versions[0]["version_number"], 1)

    def test_business_accounts_endpoint_and_alias(self):
        """Both /api/business-accounts/ and /api/whatsapp/business-accounts/ return 200 OK."""
        self.client.force_login(self.admin_user)

        res1 = self.client.get("/api/business-accounts/")
        self.assertEqual(res1.status_code, status.HTTP_200_OK)
        self.assertGreaterEqual(len(res1.json()), 1)

        res2 = self.client.get("/api/whatsapp/business-accounts/")
        self.assertEqual(res2.status_code, status.HTTP_200_OK)
        self.assertEqual(len(res1.json()), len(res2.json()))
        self.assertEqual(res2.json()[0]["name"], "Digipanda Support Line")

    def test_branches_api_endpoint(self):
        """GET /api/branches/ returns active CRM branches."""
        self.client.force_login(self.admin_user)
        res = self.client.get("/api/branches/")
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        branches = res.json()
        self.assertTrue(isinstance(branches, list))
        self.assertTrue(any(b["name"] == "Velachery Branch" for b in branches))

    def test_flow_create_valid_payload(self):
        """POST /api/flows/ creates new draft flow and initializes working draft version."""
        self.client.force_login(self.admin_user)
        payload = {
            "name": "Summer Camp Journey",
            "trigger_type": "keyword",
            "trigger_keywords": "summer, camp",
            "flow_data": {
                "nodes": [{"id": "t1", "type": "trigger"}],
                "edges": []
            }
        }
        res = self.client.post("/api/flows/", data=json.dumps(payload), content_type="application/json")
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        data = res.json()
        self.assertEqual(data["name"], "Summer Camp Journey")
        self.assertEqual(data["status"], "draft")

        # Verify database record and working draft version
        created_flow = AutomationFlow.objects.get(id=data["id"])
        self.assertIsNotNone(created_flow.working_draft_version)
        self.assertEqual(created_flow.working_draft_version.version_number, 1)

    def test_flow_create_validation_errors(self):
        """POST /api/flows/ returns clear field-level 400 errors for invalid/missing fields."""
        self.client.force_login(self.admin_user)

        # Blank name
        res_blank = self.client.post("/api/flows/", data=json.dumps({"name": ""}), content_type="application/json")
        self.assertEqual(res_blank.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("name", res_blank.json())

        # Invalid trigger type
        res_trig = self.client.post("/api/flows/", data=json.dumps({"name": "Valid Name", "trigger_type": "unknown_trigger"}), content_type="application/json")
        self.assertEqual(res_trig.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("trigger_type", res_trig.json())

    def test_put_draft_flow_update(self):
        """PUT /api/flows/<id>/ updates canvas nodes, edges and triggers."""
        self.client.force_login(self.admin_user)
        new_nodes = [
            {"id": "trigger_1", "type": "trigger", "position": {"x": 50, "y": 50}},
            {"id": "msg_2", "type": "message", "position": {"x": 50, "y": 200}, "data": {"text": "Updated greeting text."}}
        ]
        payload = {
            "name": "Admissions Onboarding Updated",
            "flow_data": {
                "nodes": new_nodes,
                "edges": [{"id": "e_2", "source": "trigger_1", "target": "msg_2"}]
            }
        }
        res = self.client.put(f"/api/flows/{self.flow.id}/", data=json.dumps(payload), content_type="application/json")
        self.assertEqual(res.status_code, status.HTTP_200_OK)

        self.flow.refresh_from_db()
        self.assertEqual(self.flow.name, "Admissions Onboarding Updated")
        self.assertEqual(len(self.flow.flow_data["nodes"]), 2)

    def test_simulator_isolation(self):
        """POST /api/flows/simulate/ executes in-memory without database mutations."""
        self.client.force_login(self.admin_user)
        session_count_before = UserFlowSession.objects.count()
        message_count_before = Message.objects.count()
        lead_count_before = Lead.objects.count()

        payload = {
            "flow_id": self.flow.id,
            "current_node_id": "trigger_1",
            "user_input": "hello",
            "session_data": {"student_name": "Test Visitor"}
        }
        res = self.client.post("/api/flows/simulate/", data=json.dumps(payload), content_type="application/json")
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        sim_data = res.json()
        self.assertTrue(sim_data.get("success"))
        self.assertTrue("current_node_id" in sim_data or "next_node_id" in sim_data)

        # Zero DB mutations
        self.assertEqual(UserFlowSession.objects.count(), session_count_before)
        self.assertEqual(Message.objects.count(), message_count_before)
        self.assertEqual(Lead.objects.count(), lead_count_before)

    def test_facebook_lead_missing_phone_graceful_handling(self):
        """Facebook lead with empty phone or Meta test tool string is handled gracefully without error."""
        # 1. Test lead with empty phone
        fb_empty = FacebookLead.objects.create(
            leadgen_id="test_lead_empty_phone_999",
            full_name="Meta Tester No Phone",
            email="tester@facebook.com",
            phone="",
            all_answers={"email": "tester@facebook.com", "full_name": "Meta Tester No Phone"}
        )
        res_empty = push_to_crm(fb_empty)
        self.assertIsNone(res_empty)
        fb_empty.refresh_from_db()
        self.assertEqual(fb_empty.crm_result, "skipped_no_phone")
        self.assertIn("skipped CRM lead creation", fb_empty.crm_error)

        # 2. Test lead with Meta Test dummy string
        fb_dummy = FacebookLead.objects.create(
            leadgen_id="test_lead_dummy_phone_888",
            full_name="Meta Dummy Phone",
            email="tester2@facebook.com",
            phone="<test lead: dummy data for phone_number>",
            all_answers={"phone_number": "<test lead: dummy data for phone_number>"}
        )
        res_dummy = push_to_crm(fb_dummy)
        self.assertIsNone(res_dummy)
        fb_dummy.refresh_from_db()
        self.assertEqual(fb_dummy.crm_result, "skipped_no_phone")

    def test_rbac_counselor_forbidden(self):
        """Counselor is denied access to flow builder endpoints (403 Forbidden)."""
        self.client.force_login(self.counselor)
        res_flows = self.client.get("/api/flows/")
        self.assertEqual(res_flows.status_code, status.HTTP_403_FORBIDDEN)

        res_branches = self.client.get("/api/branches/")
        self.assertEqual(res_branches.status_code, status.HTTP_403_FORBIDDEN)

    def test_unpublish_flow_endpoint(self):
        """POST /api/flows/<id>/unpublish/ pauses live flow, sets status=draft and is_active=False."""
        self.client.force_login(self.admin_user)
        # Configure valid graph that passes validation
        self.flow.flow_data = {
            "nodes": [
                {"id": "trigger_1", "type": "trigger", "position": {"x": 100, "y": 100}, "data": {"title": "Start"}},
                {"id": "msg_1", "type": "message", "position": {"x": 350, "y": 100}, "data": {"title": "Greeting", "body": "Welcome!"}},
                {"id": "end_1", "type": "end", "position": {"x": 600, "y": 100}, "data": {"title": "Goodbye", "body": "Bye!"}}
            ],
            "edges": [
                {"id": "e1", "source": "trigger_1", "target": "msg_1", "sourceHandle": "default"},
                {"id": "e2", "source": "msg_1", "target": "end_1", "sourceHandle": "default"}
            ]
        }
        self.flow.save()

        # First publish
        pub_res = self.client.post(f"/api/flows/{self.flow.id}/publish/")
        self.assertEqual(pub_res.status_code, status.HTTP_200_OK)
        self.flow.refresh_from_db()
        self.assertEqual(self.flow.status, AutomationFlow.STATUS_PUBLISHED)
        self.assertTrue(self.flow.is_active)

        # Now unpublish
        unpub_res = self.client.post(f"/api/flows/{self.flow.id}/unpublish/")
        self.assertEqual(unpub_res.status_code, status.HTTP_200_OK)
        self.flow.refresh_from_db()
        self.assertEqual(self.flow.status, AutomationFlow.STATUS_DRAFT)
        self.assertFalse(self.flow.is_active)

    def test_flow_with_all_15_node_types_persistence(self):
        """PUT /api/flows/<id>/ persists all 15 node types with rich custom form configurations."""
        self.client.force_login(self.admin_user)
        all_15_nodes = [
            {"id": "node_1", "type": "trigger", "position": {"x": 100, "y": 50}, "data": {"title": "Start Trigger", "trigger_type": "always_on", "trigger_keywords": "hi, hello"}},
            {"id": "node_2", "type": "message", "position": {"x": 100, "y": 150}, "data": {"title": "Greeting Text", "body": "Welcome to DigiPanda!"}},
            {"id": "node_3", "type": "buttons", "position": {"x": 100, "y": 250}, "data": {"title": "Program Buttons", "header": "Admissions", "body": "Choose track:", "options": [{"id": "b1", "title": "Web Dev"}, {"id": "b2", "title": "Data Science"}]}},
            {"id": "node_4", "type": "list", "position": {"x": 100, "y": 350}, "data": {"title": "Course Menu", "button_text": "Select Course", "source": "database"}},
            {"id": "node_5", "type": "media", "position": {"x": 100, "y": 450}, "data": {"title": "Syllabus Brochure", "source": "selected_course_brochure", "filename": "Syllabus.pdf", "caption": "Download syllabus"}},
            {"id": "node_6", "type": "location", "position": {"x": 100, "y": 550}, "data": {"title": "Main Campus GPS", "source": "custom", "name": "DigiPanda HQ", "address": "123 Anna Salai, Chennai", "latitude": 13.0827, "longitude": 80.2707}},
            {"id": "node_7", "type": "condition", "position": {"x": 100, "y": 650}, "data": {"title": "Check Qualification", "variable": "degree", "operator": "equals", "value": "BTech"}},
            {"id": "node_8", "type": "delay", "position": {"x": 100, "y": 750}, "data": {"title": "Follow Up Delay", "amount": 30, "unit": "minutes", "delay_seconds": 1800}},
            {"id": "node_9", "type": "question", "position": {"x": 100, "y": 850}, "data": {"title": "Ask Highest Degree", "variable_name": "degree", "expected_type": "text"}},
            {"id": "node_10", "type": "subflow", "position": {"x": 100, "y": 950}, "data": {"title": "Invoke Subflow", "flow_id": None, "target_node_id": "start"}},
            {"id": "node_11", "type": "end", "position": {"x": 100, "y": 1050}, "data": {"title": "End Journey", "body": "Thank you for contacting DigiPanda!"}},
            {"id": "node_12", "type": "save_data", "position": {"x": 100, "y": 1150}, "data": {"title": "Update CRM Lead", "status": "Qualified Interested", "follow_up_hours": 2}},
            {"id": "node_13", "type": "assign_telecaller", "position": {"x": 100, "y": 1250}, "data": {"title": "Assign Counselor", "mode": "round_robin", "only_if_unassigned": True}},
            {"id": "node_14", "type": "human_handover", "position": {"x": 100, "y": 1350}, "data": {"title": "Live Counselor Transfer", "body": "Connecting you with an agent now..."}},
            {"id": "node_15", "type": "webhook", "position": {"x": 100, "y": 1450}, "data": {"title": "External Sync", "url": "https://api.example.com/sync", "method": "POST", "save_response_to": "sync_status"}},
        ]

        payload = {
            "name": "Complete 15 Node Admissions Journey",
            "business_account": self.biz_account.id,
            "flow_data": {
                "nodes": all_15_nodes,
                "edges": [{"id": f"e_{i}", "source": f"node_{i}", "target": f"node_{i+1}"} for i in range(1, 15)]
            }
        }
        res = self.client.put(f"/api/flows/{self.flow.id}/", data=json.dumps(payload), content_type="application/json")
        self.assertEqual(res.status_code, status.HTTP_200_OK)

        self.flow.refresh_from_db()
        self.assertEqual(self.flow.name, "Complete 15 Node Admissions Journey")
        self.assertEqual(self.flow.business_account_id, self.biz_account.id)
        saved_nodes = self.flow.flow_data.get("nodes", [])
        self.assertEqual(len(saved_nodes), 15)

        # Verify specific nodes have preserved their data
        types_saved = [n.get("type") for n in saved_nodes]
        for expected_type in ["trigger", "message", "buttons", "list", "media", "location", "condition", "delay", "question", "subflow", "end", "save_data", "assign_telecaller", "human_handover", "webhook"]:
            self.assertIn(expected_type, types_saved)

    def test_dashboard_access_and_back_navigation(self):
        """GET /automations/ renders automations dashboard with clean HTTP 200."""
        self.client.force_login(self.admin_user)
        res = self.client.get("/automations/")
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        # Verify content contains automations title and flow list container
        self.assertIn(b"Automations", res.content)

    def test_media_upload_endpoint_pdf(self):
        """POST /api/flows/upload-media/ allows uploading PDF brochures and returns URL."""
        from django.core.files.uploadedfile import SimpleUploadedFile
        self.client.force_login(self.admin_user)
        pdf_content = b"%PDF-1.4 ... test syllabus document content ..."
        uploaded_file = SimpleUploadedFile("Admissions_Syllabus.pdf", pdf_content, content_type="application/pdf")
        res = self.client.post("/api/flows/upload-media/", {"file": uploaded_file}, format="multipart")
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        data = res.json()
        self.assertTrue(data.get("success"))
        self.assertIn("file_url", data)
        self.assertIn("Admissions_Syllabus", data.get("filename", ""))

    def test_create_automation_from_dashboard_modal(self):
        """POST /api/flows/ succeeds with blank keywords when creating first_incoming_message trigger."""
        self.client.force_login(self.admin_user)
        payload = {
            "name": "Weekend Batch Admissions",
            "slug": "weekend-batch-admissions-12345",
            "version": 1,
            "trigger_type": "first_incoming_message",
            "trigger_keywords": "",  # Blank keywords from modal
            "flow_data": {
                "nodes": [
                    {"id": "trigger_1", "type": "trigger", "data": {"title": "Start"}},
                    {"id": "msg_1", "type": "message", "data": {"text": "Welcome to DigiPanda!"}},
                    {"id": "end_1", "type": "end", "data": {"text": "Goodbye!"}}
                ],
                "connections": [
                    {"source": "trigger_1", "target": "msg_1"},
                    {"source": "msg_1", "target": "end_1"}
                ]
            }
        }
        res = self.client.post("/api/flows/", data=json.dumps(payload), content_type="application/json")
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        created_flow = res.json()
        self.assertEqual(created_flow["name"], "Weekend Batch Admissions")
        self.assertIsNotNone(created_flow.get("id"))

    def test_location_dispatch_custom_coordinates(self):
        """AutomationEngine correctly dispatches custom latitude and longitude without Branch model crashes."""
        from unittest.mock import patch
        from chat.automation.engine import AutomationEngine
        from chat.models import Conversation

        conversation = Conversation.objects.create(
            business_account=self.biz_account,
            phone_number="+919876543210",
            customer_name="Visitor Student"
        )
        session = UserFlowSession.objects.create(
            conversation=conversation,
            flow=self.flow,
            flow_version=self.flow.version,
            status=UserFlowSession.STATUS_ACTIVE,
            current_node_id="loc_1"
        )
        flow_data = {
            "nodes": [
                {
                    "id": "loc_1",
                    "type": "location",
                    "source": "custom",
                    "name": "DigiPanda Tech Park Campus",
                    "address": "100 GST Road, Guindy, Chennai",
                    "latitude": 13.0067,
                    "longitude": 80.2025
                }
            ],
            "edges": []
        }

        self.flow.flow_data = flow_data
        self.flow.save()
        session.flow = self.flow

        with patch("chat.automation.engine.send_location_message") as mock_loc:
            mock_loc.return_value = {"messages": [{"id": "loc_msg_123"}]}
            result = AutomationEngine.execute_node(conversation, session, "loc_1")
            self.assertTrue(result)
            mock_loc.assert_called_once()
            _, kwargs = mock_loc.call_args
            self.assertEqual(kwargs.get("to_phone_number"), "+919876543210")
            self.assertAlmostEqual(kwargs.get("latitude"), 13.0067, places=4)
            self.assertAlmostEqual(kwargs.get("longitude"), 80.2025, places=4)
            self.assertEqual(kwargs.get("name"), "DigiPanda Tech Park Campus")

    def test_list_node_custom_answers_persistence(self):
        """PUT /api/flows/<id>/ correctly saves and retrieves custom answers / row options in list node."""
        self.client.force_login(self.admin_user)
        list_node = {
            "id": "list_1",
            "type": "list",
            "data": {
                "title": "Select Specialization",
                "button_text": "Choose Domain",
                "body": "Which area do you want to master?",
                "source": "static",
                "sections": [
                    {
                        "title": "Options",
                        "rows": [
                            {"id": "opt_fullstack", "title": "Full Stack Dev", "description": "Python, React & PostgreSQL"},
                            {"id": "opt_data_ai", "title": "AI & Data Science", "description": "Machine Learning & GenAI"},
                            {"id": "opt_cloud", "title": "Cloud DevOps", "description": "AWS, Docker & Kubernetes"}
                        ]
                    }
                ]
            }
        }
        payload = {
            "name": "Admissions with Custom List",
            "flow_data": {
                "nodes": [list_node],
                "edges": []
            }
        }
        res = self.client.put(f"/api/flows/{self.flow.id}/", data=json.dumps(payload), content_type="application/json")
        self.assertEqual(res.status_code, status.HTTP_200_OK)

        self.flow.refresh_from_db()
        nodes = self.flow.flow_data.get("nodes", [])
        self.assertEqual(len(nodes), 1)
        saved_rows = nodes[0].get("data", {}).get("sections", [{}])[0].get("rows", [])
        self.assertEqual(len(saved_rows), 3)
        self.assertEqual(saved_rows[0]["title"], "Full Stack Dev")
        self.assertEqual(saved_rows[1]["title"], "AI & Data Science")

    def test_simulator_list_message_and_row_selection_branching(self):
        """Simulate list message execution and interactive row selection branch routing."""
        self.client.force_login(self.admin_user)
        flow_data = {
            "nodes": [
                {
                    "id": "start_1",
                    "type": "trigger"
                },
                {
                    "id": "list_1",
                    "type": "list",
                    "data": {
                        "body": "Select your domain of interest:",
                        "button_text": "Select Domain",
                        "sections": [
                            {
                                "title": "Programs",
                                "rows": [
                                    {"id": "opt_ai", "title": "AI Engineering", "description": "PyTorch and LLMs"},
                                    {"id": "opt_web", "title": "Web Engineering", "description": "Django and React"}
                                ]
                            }
                        ]
                    }
                },
                {
                    "id": "msg_ai",
                    "type": "message",
                    "data": {
                        "text": "Welcome to AI Engineering!"
                    }
                },
                {
                    "id": "msg_web",
                    "type": "message",
                    "data": {
                        "text": "Welcome to Web Engineering!"
                    }
                }
            ],
            "edges": [
                {"source": "start_1", "target": "list_1", "sourceHandle": "default"},
                {"source": "list_1", "target": "msg_ai", "sourceHandle": "opt_ai"},
                {"source": "list_1", "target": "msg_web", "sourceHandle": "opt_web"}
            ]
        }

        # Step 1: Trigger simulator -> Should return the interactive list card
        res1 = self.client.post("/api/flows/simulate/", data=json.dumps({
            "flow_data": flow_data,
            "message_text": "Hi"
        }), content_type="application/json")
        self.assertEqual(res1.status_code, status.HTTP_200_OK)
        data1 = res1.json()
        self.assertTrue(data1.get("success"))
        self.assertEqual(data1.get("current_node_id"), "list_1")
        self.assertTrue(data1.get("waiting_for_input"))
        sim_msgs = data1.get("sim_messages", [])
        self.assertEqual(len(sim_msgs), 1)
        self.assertEqual(sim_msgs[0]["type"], "list")
        self.assertEqual(sim_msgs[0]["button_text"], "Select Domain")
        self.assertEqual(len(sim_msgs[0]["sections"][0]["rows"]), 2)

        # Step 2: User taps 'AI Engineering' row (interactive_reply = 'opt_ai')
        res2 = self.client.post("/api/flows/simulate/", data=json.dumps({
            "flow_data": flow_data,
            "current_node_id": "list_1",
            "message_text": "AI Engineering",
            "interactive_reply": "opt_ai",
            "collected_data": data1.get("collected_data", {})
        }), content_type="application/json")
        self.assertEqual(res2.status_code, status.HTTP_200_OK)
        data2 = res2.json()
        self.assertTrue(data2.get("success"))
        self.assertEqual(data2.get("current_node_id"), "msg_ai")
        self.assertEqual(data2.get("sim_messages", [])[0]["body"], "Welcome to AI Engineering!")

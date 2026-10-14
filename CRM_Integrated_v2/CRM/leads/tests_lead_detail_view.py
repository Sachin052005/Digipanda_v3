import json
from django.test import TestCase, Client
from django.urls import reverse
from accounts.models import User, UserRole
from branches.models import Branch
from lead_channels.models import Channel
from products.models import Product
from leads.models import Lead, LeadStatus
from calls.models import CallHistory, CallOutcome, CallStatus
from leads.detail_service import build_lead_detail_context, extract_parsed_lead_attributes

class LeadDetailInterfaceTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.branch = Branch.objects.create(name="Bangalore Central")
        self.channel = Channel.objects.create(name="Website Form")
        self.product = Product.objects.create(name="Data Science", price=30000)

        self.telecaller = User.objects.create_user(
            username="tc_test", password="pwd", role=UserRole.TELECALLER,
            first_name="Test", last_name="Caller", branch=self.branch
        )

        self.lead = Lead.objects.create(
            name="Aarav Patel",
            phone="9876543210",
            email="aarav@example.com",
            channel=self.channel,
            product=self.product,
            branch=self.branch,
            assigned_telecaller=self.telecaller,
            status=LeadStatus.CONTACTED,
            notes="Degree: B.Tech Computer Science | PassedOut: 2024 | Working status: Working professional | Preferred Branch: Bangalore Central"
        )

    def test_extract_parsed_lead_attributes(self):
        attrs = extract_parsed_lead_attributes(self.lead.notes)
        self.assertEqual(attrs.get('degree'), 'B.Tech Computer Science')
        self.assertEqual(attrs.get('passed_out'), '2024')
        self.assertEqual(attrs.get('working_status'), 'Working professional')
        self.assertEqual(attrs.get('pref_branch'), 'Bangalore Central')

    def test_build_lead_detail_context(self):
        ctx = build_lead_detail_context(self.lead, self.telecaller)
        self.assertEqual(ctx['lead'], self.lead)
        self.assertEqual(ctx['whatsapp_phone'], '919876543210')
        self.assertEqual(ctx['assignee_name'], 'Test Caller')
        self.assertEqual(ctx['assignee_initials'], 'TC')
        self.assertTrue(len(ctx['col1_fields']) > 0)
        self.assertTrue(len(ctx['col2_fields']) > 0)

        # Verify degree and passed_out are populated and not empty
        degree_f = next((f for f in ctx['col1_fields'] if f['key'] == 'degree'), None)
        self.assertIsNotNone(degree_f)
        self.assertEqual(degree_f['value'], 'B.Tech Computer Science')
        self.assertFalse(degree_f['is_empty'])

    def test_api_quick_details(self):
        self.client.login(username="tc_test", password="pwd")
        url = reverse('api_lead_quick_details', kwargs={'pk': self.lead.pk})
        response = self.client.get(url, HTTP_X_REQUESTED_WITH='XMLHttpRequest')
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data['success'])
        self.assertEqual(data['name'], 'Aarav Patel')
        self.assertEqual(data['phone'], '9876543210')
        self.assertEqual(data['degree'], 'B.Tech Computer Science')
        self.assertEqual(data['passed_out'], '2024')
        self.assertEqual(data['assignee_initials'], 'TC')
        self.assertIn('wa.me/919876543210', data['whatsapp_url'])

    def test_telecaller_lead_detail_view_rendering(self):
        self.client.login(username="tc_test", password="pwd")
        url = reverse('telecaller_lead_detail', kwargs={'pk': self.lead.pk})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'leads/lead_detail_view.html')
        self.assertContains(response, 'Aarav Patel')
        self.assertContains(response, 'B.Tech Computer Science')
        self.assertContains(response, 'Hide Empty Fields')
        self.assertContains(response, 'Call Outcome &amp; Notes')

    def test_complete_call_record(self):
        self.client.login(username="tc_test", password="pwd")
        call = CallHistory.objects.create(
            lead=self.lead,
            caller=self.telecaller,
            call_status=CallStatus.IN_PROGRESS
        )
        url = reverse('complete_call_record')
        payload = {
            'call_id': call.pk,
            'lead_id': self.lead.pk,
            'duration': '45',
            'notes': 'Candidate is interested in weekend data science batch.',
            'call_outcome': 'Interested',
            'lead_status': 'Interested'
        }
        response = self.client.post(url, data=payload, HTTP_X_REQUESTED_WITH='XMLHttpRequest')
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data['success'])

        call.refresh_from_db()
        self.assertEqual(call.call_status, CallStatus.COMPLETED)
        self.assertEqual(call.call_outcome, CallOutcome.INTERESTED)
        self.assertEqual(call.notes, 'Candidate is interested in weekend data science batch.')
        self.assertEqual(call.duration, 45)

        self.lead.refresh_from_db()
        self.assertEqual(self.lead.status, LeadStatus.INTERESTED)

    def test_inline_update_custom_field(self):
        self.client.login(username="tc_test", password="pwd")
        url = reverse('api_update_lead_field', kwargs={'pk': self.lead.pk})
        
        # 1. Update Degree
        resp = self.client.post(
            url,
            data=json.dumps({'field': 'degree', 'value': 'M.Tech Artificial Intelligence'}),
            content_type='application/json',
            HTTP_X_REQUESTED_WITH='XMLHttpRequest'
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertTrue(data['success'])
        self.assertEqual(data['value'], 'M.Tech Artificial Intelligence')

        self.lead.refresh_from_db()
        self.assertIn('Degree: M.Tech Artificial Intelligence', self.lead.notes)

        # 2. Update Working status
        resp2 = self.client.post(
            url,
            data=json.dumps({'field': 'working_status', 'value': 'Student'}),
            content_type='application/json',
            HTTP_X_REQUESTED_WITH='XMLHttpRequest'
        )
        self.assertEqual(resp2.status_code, 200)
        self.lead.refresh_from_db()
        self.assertIn('Working status: Student', self.lead.notes)

    def test_inline_update_phone_duplicate_protection(self):
        self.client.login(username="tc_test", password="pwd")
        # Create another lead with phone 9111122222
        other_lead = Lead.objects.create(
            name="Conflicting Lead",
            phone="9111122222",
            channel=self.channel,
            branch=self.branch,
            assigned_telecaller=self.telecaller
        )
        url = reverse('api_update_lead_field', kwargs={'pk': self.lead.pk})

        # Try to update self.lead to conflicting phone
        resp = self.client.post(
            url,
            data=json.dumps({'field': 'phone', 'value': '+91 91111 22222'}),
            content_type='application/json',
            HTTP_X_REQUESTED_WITH='XMLHttpRequest'
        )
        self.assertEqual(resp.status_code, 400)
        data = resp.json()
        self.assertFalse(data['success'])
        self.assertIn('already associated with lead', data['error'])

        # Valid non-conflicting phone update
        resp_ok = self.client.post(
            url,
            data=json.dumps({'field': 'phone', 'value': '+91 98888 77777'}),
            content_type='application/json',
            HTTP_X_REQUESTED_WITH='XMLHttpRequest'
        )
        self.assertEqual(resp_ok.status_code, 200)
        self.lead.refresh_from_db()
        self.assertEqual(self.lead.phone, '9888877777')

    def test_inline_update_readonly_field_blocked(self):
        self.client.login(username="tc_test", password="pwd")
        url = reverse('api_update_lead_field', kwargs={'pk': self.lead.pk})

        resp = self.client.post(
            url,
            data=json.dumps({'field': 'captured_on', 'value': '2020-01-01'}),
            content_type='application/json',
            HTTP_X_REQUESTED_WITH='XMLHttpRequest'
        )
        self.assertEqual(resp.status_code, 400)
        data = resp.json()
        self.assertFalse(data['success'])
        self.assertIn('system-managed', data['error'])

    def test_activity_logged_on_inline_edit(self):
        from activities.models import Activity
        self.client.login(username="tc_test", password="pwd")
        url = reverse('api_update_lead_field', kwargs={'pk': self.lead.pk})

        resp = self.client.post(
            url,
            data=json.dumps({'field': 'name', 'value': 'Aarav Patel (Updated)'}),
            content_type='application/json',
            HTTP_X_REQUESTED_WITH='XMLHttpRequest'
        )
        self.assertEqual(resp.status_code, 200)
        self.lead.refresh_from_db()
        self.assertEqual(self.lead.name, 'Aarav Patel (Updated)')

        # Verify activity was logged
        act = Activity.objects.filter(object_id=str(self.lead.pk), action="Lead Field Updated").first()
        self.assertIsNotNone(act)
        self.assertIn("Updated 'Name'", act.description)

    def test_inline_update_all_screenshot_fields(self):
        self.client.login(username="tc_test", password="pwd")
        url = reverse('api_update_lead_field', kwargs={'pk': self.lead.pk})

        fields_to_test = [
            ('passed_out', '2023'),
            ('purpose', 'Upskilling'),
            ('pref_exam_loc', 'Chennai'),
            ('total_experience', '3 Years'),
            ('college', 'Anna University'),
            ('join_preference', 'Online'),
            ('pref_branch', 'Bangalore Central'),
            ('retargeted', 'Yes'),
            ('pipeline_substatus', 'Interested'),
        ]

        for field_key, val in fields_to_test:
            resp = self.client.post(
                url,
                data=json.dumps({'field': field_key, 'value': val}),
                content_type='application/json',
                HTTP_X_REQUESTED_WITH='XMLHttpRequest'
            )
            self.assertEqual(resp.status_code, 200, f"Failed on field: {field_key}")
            data = resp.json()
            self.assertTrue(data['success'], f"Not successful on field: {field_key}")
            self.assertEqual(data['field'], field_key)

        self.lead.refresh_from_db()
        self.assertEqual(self.lead.status, LeadStatus.INTERESTED)
        attrs = extract_parsed_lead_attributes(self.lead.notes)
        self.assertEqual(attrs.get('passed_out'), '2023')
        self.assertEqual(attrs.get('purpose'), 'Upskilling')
        self.assertEqual(attrs.get('pref_exam_loc'), 'Chennai')
        self.assertEqual(attrs.get('college'), 'Anna University')
        self.assertEqual(attrs.get('retargeted'), 'Yes')

    def test_auto_save_template_elements_and_no_manual_save_buttons(self):
        self.client.login(username="tc_test", password="pwd")
        url = reverse('telecaller_lead_detail', kwargs={'pk': self.lead.pk})
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)
        html = resp.content.decode('utf-8')

        # 1. Verify individual manual save/cancel checkmark buttons are removed
        self.assertNotIn('class="btn-inline-save"', html)
        self.assertNotIn('class="btn-inline-cancel"', html)
        self.assertNotIn("saveFieldEdit('pref_exam_loc')", html)

        # 2. Verify auto-save status elements and wrappers exist
        self.assertIn('lead-inline-status-wrap', html)
        self.assertIn('lead-field-status', html)
        self.assertIn('status-pref_exam_loc', html)
        self.assertIn('status-lead-name', html)

        # 3. Verify primary WhatsApp action button is 'Open WhatsApp & Send'
        self.assertIn('Open WhatsApp &amp; Send', html)
        self.assertIn('sendTelecallerWhatsApp()', html)



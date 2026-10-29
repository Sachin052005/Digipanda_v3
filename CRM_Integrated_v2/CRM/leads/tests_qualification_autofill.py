from django.test import TestCase
from django.utils import timezone

from leads.models import Lead, LeadStatus
from branches.models import Branch
from products.models import Product
from leads.qualification import (
    match_canonical_field,
    normalize_value,
    extract_course_from_text,
    normalize_inbound_payload,
    autofill_lead_qualification,
    generate_smart_precall_pitch,
)
from leads.detail_service import build_lead_detail_context, update_lead_attribute


class LeadQualificationAutofillTests(TestCase):
    def setUp(self):
        self.branch = Branch.objects.create(name="Coimbatore", status="Active")
        self.product = Product.objects.create(name="Digital Marketing Course", status="Active")

    def test_alias_matching(self):
        self.assertEqual(match_canonical_field('prefer_learning_mode?'), 'join_preference')
        self.assertEqual(match_canonical_field('which_batch_would_you_prefer?'), 'join_preference')
        self.assertEqual(match_canonical_field('what_best_describes_you?'), 'working_status')
        self.assertEqual(match_canonical_field('highest_qualification'), 'degree')
        self.assertEqual(match_canonical_field('year_of_passing'), 'passed_out')
        self.assertEqual(match_canonical_field('college_name'), 'college')
        self.assertEqual(match_canonical_field('current_ctc'), 'current_ctc')

    def test_normalize_values(self):
        val, sec = normalize_value('join_preference', 'classroom_training')
        self.assertEqual(val, 'Classroom')

        val, sec = normalize_value('join_preference', 'weekday_batch')
        self.assertEqual(val, 'Weekday Batch')

        val, sec = normalize_value('working_status', 'career_switcher')
        self.assertEqual(val, 'Working professional')
        self.assertEqual(sec, ('purpose', 'Career Transition'))

        val, sec = normalize_value('passed_out', 'Passed out in 2024')
        self.assertEqual(val, '2024')

        val, sec = normalize_value('location', 'chennai')
        self.assertEqual(val, 'Chennai')

    def test_extract_course_from_ad_text(self):
        text = "DP | Leads | Digital Marketing Course | Oct 06 2026 ad"
        course = extract_course_from_text(text)
        self.assertEqual(course, "Digital Marketing Course")

    def test_facebook_lead_autofill(self):
        lead = Lead.objects.create(
            name="Sandhiya Babu",
            phone="6383822799",
            source="Facebook"
        )
        fb_payload = {
            'city': 'Coimbatore',
            'prefer_learning_mode?': 'classroom_training',
            'what_best_describes_you?': 'career_switcher',
            'which_batch_would_you_prefer?': 'weekday_batch',
            'ad_name': 'DP | Leads | Digital Marketing Course | Oct 06 2026 ad',
            'campaign_name': 'DP | Leads | Digital Marketing Course',
        }
        applied = autofill_lead_qualification(lead, fb_payload, source='Facebook')
        lead.refresh_from_db()

        self.assertIn('location', applied)
        self.assertEqual(lead.custom_fields.get('location'), 'Coimbatore')
        self.assertEqual(lead.custom_fields.get('join_preference'), 'Classroom')
        self.assertEqual(lead.custom_fields.get('working_status'), 'Working professional')
        self.assertEqual(lead.custom_fields.get('purpose'), 'Career Transition')
        self.assertEqual(lead.custom_fields.get('_field_origins', {}).get('location'), 'Facebook')

        # Product and Branch resolution
        self.assertEqual(lead.product, self.product)
        self.assertEqual(lead.branch, self.branch)

        # Smart pitch verification
        pitch = generate_smart_precall_pitch(lead)
        self.assertIn("Sandhiya Babu", pitch)
        self.assertIn("Career Transition", pitch)
        self.assertIn("Classroom", pitch)
        self.assertIn("Digital Marketing Course", pitch)

    def test_whatsapp_flow_autofill(self):
        lead = Lead.objects.create(
            name="Rahul Sharma",
            phone="9876543210",
            source="WhatsApp"
        )
        wa_answers = {
            'qualification': 'B.Tech IT',
            'passing_year': '2023',
            'mode_of_training': 'online_live',
            'current_status': 'looking_for_job',
            'college': 'Anna University',
        }
        applied = autofill_lead_qualification(lead, wa_answers, source='WhatsApp')
        lead.refresh_from_db()

        self.assertEqual(lead.custom_fields.get('degree'), 'B.Tech IT')
        self.assertEqual(lead.custom_fields.get('passed_out'), '2023')
        self.assertEqual(lead.custom_fields.get('join_preference'), 'Online')
        self.assertEqual(lead.custom_fields.get('working_status'), 'Looking for job')
        self.assertEqual(lead.custom_fields.get('college'), 'Anna University')
        self.assertEqual(lead.custom_fields.get('_field_origins', {}).get('degree'), 'WhatsApp')

    def test_google_sheets_autofill(self):
        lead = Lead.objects.create(
            name="Deepa R",
            phone="9123456789",
            source="Google Sheets"
        )
        sheet_row = {
            'Degree': 'MBA HR',
            'Year of Pass': '2022',
            'Employment Status': 'working_professional',
            'Current Role': 'HR Executive',
            'City': 'Coimbatore',
        }
        applied = autofill_lead_qualification(lead, sheet_row, source='Google Sheets')
        lead.refresh_from_db()

        self.assertEqual(lead.custom_fields.get('degree'), 'MBA HR')
        self.assertEqual(lead.custom_fields.get('passed_out'), '2022')
        self.assertEqual(lead.custom_fields.get('working_status'), 'Working professional')
        self.assertEqual(lead.custom_fields.get('designation'), 'HR Executive')
        self.assertEqual(lead.custom_fields.get('location'), 'Coimbatore')

    def test_detail_service_context_and_manual_edit_precedence(self):
        lead = Lead.objects.create(
            name="Karthik N",
            phone="9988776655",
            source="Facebook",
            custom_fields={
                'location': 'Coimbatore',
                'join_preference': 'Classroom',
                '_field_origins': {'location': 'Facebook', 'join_preference': 'Facebook'}
            }
        )
        ctx = build_lead_detail_context(lead)
        self.assertIsNotNone(ctx.get('smart_pitch'))
        
        # Check that origin is attached to fields
        col1_dict = {f['key']: f for f in ctx['col1_fields']}
        self.assertEqual(col1_dict['location']['value'], 'Coimbatore')
        self.assertEqual(col1_dict['location']['origin'], 'Facebook')
        self.assertEqual(col1_dict['join_preference']['value'], 'Classroom')
        self.assertEqual(col1_dict['join_preference']['origin'], 'Facebook')

        # Test preserve manual edits: new inbound payload should not overwrite manual edit
        lead.custom_fields['location'] = 'Madurai'
        lead.custom_fields['_field_origins']['location'] = 'Manual'
        lead.save()

        new_fb_payload = {'city': 'Salem'}
        autofill_lead_qualification(lead, new_fb_payload, source='Facebook', preserve_manual_edits=True)
        lead.refresh_from_db()
        self.assertEqual(lead.custom_fields['location'], 'Madurai')

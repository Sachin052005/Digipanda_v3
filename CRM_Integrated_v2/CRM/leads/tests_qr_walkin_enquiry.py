from django.test import TestCase, Client
from django.urls import reverse
from django.utils import timezone
from accounts.models import User, UserRole
from branches.models import Branch
from lead_channels.models import Channel
from leads.models import Lead, VisitorStatus, LeadStatus, LeadCategory


class QRWalkinStudentEnquiryTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.branch = Branch.objects.create(name='Velachery', status='Active', phone='9876543210', address='123 Bypass Road, Velachery, Chennai')
        self.walkin_channel, _ = Channel.objects.get_or_create(name='Walk-in', defaults={'status': 'Active'})

        self.admin = User.objects.create_user(
            username='admin_test',
            email='admin@test.com',
            password='Password@123',
            role=UserRole.ADMIN,
            is_staff=True
        )

    def test_public_enquiry_form_get(self):
        """Public enquiry form loads without login."""
        url = reverse('public_student_enquiry_branch', kwargs={'branch_id': self.branch.id})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Student Enquiry Form')
        self.assertContains(response, 'Velachery')

    def test_public_enquiry_submission_creates_walkin_lead(self):
        """Student submits form, creating a Walk-in lead with token and custom fields."""
        url = reverse('public_student_enquiry_branch', kwargs={'branch_id': self.branch.id})
        data = {
            'name': 'Karthik Subramanian',
            'phone': '9840123456',
            'email': 'karthik@example.com',
            'branch_id': self.branch.id,
            'dob': '2001-05-15',
            'gender': 'Male',
            'address': 'Flat 4B, Lotus Apartments',
            'city': 'Chennai',
            'state': 'Tamil Nadu',
            'zip_code': '600042',
            'preferred_contact': 'WhatsApp',
            'experience_type': 'Fresher',
            'ug_degree': 'B.Com',
            'ug_year': '2024',
            'backlogs': 'No',
            'highest_education': 'B.Com',
            'professional_status': 'Student / Fresher',
            'career_objective': 'Get a Job in Digital Marketing',
            'dm_experience': 'Beginner',
            'course_track': 'Premium',
            'ref_1_name': 'Suresh',
            'ref_1_phone': '9840999999',
        }
        response = self.client.post(url, data)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Welcome, Karthik Subramanian!')
        self.assertContains(response, 'WI-VEL-')

        # Verify DB
        lead = Lead.objects.filter(phone='9840123456').first()
        self.assertIsNotNone(lead)
        self.assertEqual(lead.name, 'Karthik Subramanian')
        self.assertEqual(lead.channel.name, 'Walk-in')
        self.assertEqual(lead.source, 'Walk-in QR Form')
        self.assertEqual(lead.visitor_status, VisitorStatus.WAITING)
        self.assertTrue(lead.is_offline)
        self.assertTrue(lead.token_number.startswith('WI-VEL-'))

        # Verify Custom fields
        cf = lead.custom_fields
        self.assertEqual(cf.get('ug_degree'), 'B.Com')
        self.assertEqual(cf.get('ug_year'), '2024')
        self.assertEqual(cf.get('career_objective'), 'Get a Job in Digital Marketing')
        self.assertEqual(cf.get('course_track'), 'Premium')
        self.assertEqual(cf.get('reference_1_name'), 'Suresh')

    def test_re_enquiry_existing_student(self):
        """When an existing student walks in and scans QR, it updates visit and logs re-enquiry."""
        existing_lead = Lead.objects.create(
            name='Priya Raman',
            phone='9791000111',
            email='priya@example.com',
            channel=self.walkin_channel,
            branch=self.branch,
            status=LeadStatus.NEW
        )

        url = reverse('public_student_enquiry_branch', kwargs={'branch_id': self.branch.id})
        data = {
            'name': 'Priya Raman',
            'phone': '9791000111',
            'email': 'priya@example.com',
            'branch_id': self.branch.id,
            'ug_degree': 'B.Tech IT',
            'ug_year': '2023',
            'professional_status': 'Working in BPO / Customer Support',
            'career_objective': 'Switch to Digital Marketing',
            'dm_experience': 'Practical Experience',
            'course_track': 'Advanced',
        }
        response = self.client.post(url, data)
        self.assertEqual(response.status_code, 200)

        existing_lead.refresh_from_db()
        self.assertEqual(existing_lead.visitor_status, VisitorStatus.WAITING)
        self.assertTrue(existing_lead.token_number.startswith('WI-VEL-'))
        self.assertEqual(existing_lead.custom_fields.get('ug_degree'), 'B.Tech IT')
        self.assertIn('Re-enquiry', existing_lead.notes)

    def test_branch_qr_standee_view(self):
        """Admin can access and view the printable QR standee poster."""
        self.client.force_login(self.admin)
        url = reverse('branch_qr_standee', kwargs={'branch_id': self.branch.id})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Reception Desk Standee')
        self.assertContains(response, 'Velachery')
        self.assertContains(response, 'data:image/png;base64,')

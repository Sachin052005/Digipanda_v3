from django.test import TestCase, Client
from django.urls import reverse
from django.utils import timezone
from leads.models import Lead, DuplicateLeadRecord, LeadStatus
from branches.models import Branch
from products.models import Product
from accounts.models import User, UserRole
from activities.models import Notification

class DuplicateModalAndNotificationTests(TestCase):
    def setUp(self):
        self.branch, _ = Branch.objects.get_or_create(name="Anna Nagar")
        self.admin = User.objects.create_user(
            username="admin_test", email="admin@test.com", password="password123",
            role=UserRole.ADMIN, is_staff=True, is_superuser=True
        )
        self.counselor = User.objects.create_user(
            username="counselor_priya", email="priya@test.com", password="password123",
            role=UserRole.SALES_HEAD, is_active=True
        )
        self.course, _ = Product.objects.get_or_create(name="Full Stack Web Dev", defaults={'price': 45000})

        self.lead = Lead.objects.create(
            name="Rahul Sharma",
            phone="9150688755",
            email="rahul@example.com",
            branch=self.branch,
            product=self.course,
            status=LeadStatus.ENROLLED,
            assigned_counselor=self.counselor,
            source="Google Ads"
        )

        self.dup_record = DuplicateLeadRecord.objects.create(
            original_lead=self.lead,
            record_type='INCOMING_DUPLICATE',
            name="Rahul Sharma",
            phone="9150688755",
            normalized_phone="9150688755",
            email="rahul@example.com",
            branch=self.branch,
            branch_name="Anna Nagar",
            source="WhatsApp",
            action_taken="RETAINED_WITHIN_10_DAYS",
            duplicate_reason="Started a WhatsApp chat on Line (+918438239448)",
            notes="Started a WhatsApp chat on Line (+918438239448)",
            data_payload={"whatsapp_line": "+918438239448", "course": "Python & AI"}
        )

        self.client = Client()
        self.client.force_login(self.admin)

    def test_duplicate_info_endpoint_returns_rich_data(self):
        url = reverse('admin_lead_duplicate_info', args=[self.lead.pk])
        resp = self.client.get(url, HTTP_X_REQUESTED_WITH='XMLHttpRequest')
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertTrue(data['success'])

        # Check Lead data
        ld = data['lead']
        self.assertEqual(ld['id'], self.lead.id)
        self.assertEqual(ld['name'], "Rahul Sharma")
        self.assertEqual(ld['phone'], "9150688755")
        self.assertEqual(ld['branch'], "Anna Nagar")
        self.assertEqual(ld['course'], "Full Stack Web Dev")
        self.assertEqual(ld['status'], "Enrolled")
        self.assertIn("counselor_priya", ld['assigned_staff'])

        # Check Summary
        summary = data['summary']
        self.assertEqual(summary['total_duplicates'], 1)
        self.assertIn("after original", summary['latest_elapsed'])

        # Check Duplicate Records list
        dups = data['duplicate_records']
        self.assertEqual(len(dups), 1)
        first_dup = dups[0]
        self.assertEqual(first_dup['source'], "WhatsApp")
        self.assertEqual(first_dup['course'], "Python & AI")
        self.assertEqual(first_dup['whatsapp_line'], "+918438239448")

    def test_notify_counselor_endpoint(self):
        url = reverse('admin_lead_notify_duplicate_counselor', args=[self.lead.pk])
        resp = self.client.post(url, HTTP_X_REQUESTED_WITH='XMLHttpRequest')
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertTrue(data['success'])
        self.assertIn("counselor_priya", data['message'])

        # Verify notification created in DB
        notif = Notification.objects.filter(recipient=self.counselor).latest('timestamp')
        self.assertIsNotNone(notif)
        self.assertIn("Duplicate Alert", notif.title)
        self.assertIn("9150688755", notif.message)

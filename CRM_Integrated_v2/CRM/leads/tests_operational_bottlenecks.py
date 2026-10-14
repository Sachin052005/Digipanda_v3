from django.test import TestCase, Client
from django.urls import reverse
from django.utils import timezone
from datetime import timedelta
from accounts.models import User, UserRole
from branches.models import Branch
from leads.models import Lead, LeadStatus, LeadOwnerType, TelecallerLeadSetup
from activities.models import Notification

class OperationalBottlenecksResolutionTests(TestCase):
    def setUp(self):
        self.branch = Branch.objects.create(name='Test Branch Chennai', status='Active')
        
        # Create Admin
        self.admin = User.objects.create_superuser(username='admin_test', email='admin@test.com', password='password123')
        
        # Create Counselor
        self.counselor = User.objects.create_user(
            username='counselor_test',
            email='counselor@test.com',
            password='password123',
            role=UserRole.COUNSELOR,
            branch=self.branch
        )
        
        # Create Telecallers
        self.tc1 = User.objects.create_user(
            username='telecaller_1',
            email='tc1@test.com',
            password='password123',
            role=UserRole.TELECALLER,
            branch=self.branch
        )
        self.tc2 = User.objects.create_user(
            username='telecaller_2',
            email='tc2@test.com',
            password='password123',
            role=UserRole.TELECALLER,
            branch=self.branch
        )
        
        TelecallerLeadSetup.objects.create(
            telecaller=self.tc1,
            branch=self.branch,
            assignment_percentage=50,
            is_active=True
        )
        TelecallerLeadSetup.objects.create(
            telecaller=self.tc2,
            branch=self.branch,
            assignment_percentage=50,
            is_active=True
        )
        
        self.client = Client()

    def test_auto_handoff_telecaller_to_counselor_on_visit_scheduled(self):
        """Bottleneck 1: When lead status changes to 'Visit Scheduled', auto-assigns branch counselor and dispatches notification."""
        lead = Lead.objects.create(
            name='Student Ramesh',
            phone='+919999900001',
            branch=self.branch,
            assigned_telecaller=self.tc1,
            status=LeadStatus.NEW
        )
        
        self.client.force_login(self.tc1)
        response = self.client.post(reverse('telecaller_lead_edit', args=[lead.id]), {
            'status': LeadStatus.VISIT_SCHEDULED,
            'category': 'Training',
            'notes': 'Convinced student to visit campus tomorrow.'
        })
        self.assertEqual(response.status_code, 302)
        
        lead.refresh_from_db()
        self.assertEqual(lead.status, LeadStatus.VISIT_SCHEDULED)
        self.assertEqual(lead.assigned_counselor, self.counselor)
        self.assertEqual(lead.current_owner_type, LeadOwnerType.COUNSELOR)
        
        # Verify notification created for counselor
        notif = Notification.objects.filter(recipient=self.counselor).first()
        self.assertIsNotNone(notif)
        self.assertIn('Visit Scheduled', notif.title)
        self.assertIn('Student Ramesh', notif.message)

    def test_notification_polling_api(self):
        """Bottleneck 2: Verifies /notifications/latest/ returns unread count and notification items for polling chime."""
        Notification.objects.create(
            recipient=self.counselor,
            title='Walk-in Student Assigned',
            message='Rajesh is waiting in reception.',
            link='/counselor/leads/1/'
        )
        
        self.client.force_login(self.counselor)
        res = self.client.get('/notifications/latest/')
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data['unread_count'], 1)
        self.assertEqual(len(data['notifications']), 1)
        self.assertEqual(data['notifications'][0]['title'], 'Walk-in Student Assigned')

    def test_sla_escalation_engine_and_admin_api(self):
        """Bottleneck 3: Uncontacted leads past SLA are automatically escalated and reassigned."""
        # Create an old New lead untouched past 24 hours
        lead = Lead.objects.create(
            name='Uncontacted Lead Priya',
            phone='+919999900002',
            branch=self.branch,
            assigned_telecaller=self.tc1,
            status=LeadStatus.NEW
        )
        Lead.objects.filter(id=lead.id).update(created_at=timezone.now() - timedelta(hours=30))
        
        self.client.force_login(self.admin)
        res = self.client.post(reverse('admin_trigger_sla_escalation'))
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertTrue(data['success'])
        self.assertEqual(data['summary']['escalated_fresh'], 1)
        
        lead.refresh_from_db()
        self.assertEqual(lead.assigned_telecaller, self.tc2)
        
        # Verify tc2 received escalation notification
        notif = Notification.objects.filter(recipient=self.tc2).first()
        self.assertIsNotNone(notif)
        self.assertIn('Escalated Lead', notif.title)

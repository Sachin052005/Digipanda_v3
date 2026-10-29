from datetime import date, time, timedelta
from django.test import TestCase
from django.utils import timezone
from django.core.exceptions import ValidationError
from accounts.models import User, UserRole
from branches.models import Branch
from leads.models import Lead, LeadStatus, DuplicateLeadRecord
from followups.models import FollowUp, FollowUpStatus
from followups.forms import AdminFollowUpForm, FollowUpRescheduleForm
from leads.intake import intake_lead, is_potential_family_member


class Phase4FollowUpAndFamilyRemediationTests(TestCase):
    def setUp(self):
        self.branch = Branch.objects.create(name="Phase4 Branch")
        self.admin_user = User.objects.create_user(
            username="p4_admin",
            email="p4_admin@example.com",
            password="testpassword",
            role=UserRole.ADMIN,
            branch=self.branch
        )
        self.manager = User.objects.create_user(
            username="p4_manager",
            email="p4_mgr@example.com",
            password="testpassword",
            role=UserRole.SALES_HEAD,
            branch=self.branch
        )
        self.telecaller = User.objects.create_user(
            username="p4_telecaller",
            email="p4_tc@example.com",
            password="testpassword",
            role=UserRole.TELECALLER,
            branch=self.branch
        )
        self.lead = Lead.objects.create(
            name="Rahul Sharma",
            phone="9876543210",
            email="rahul@example.com",
            branch=self.branch,
            assigned_sales_head=self.manager,
            assigned_telecaller=self.telecaller
        )

    def test_duplicate_pending_followup_rejected_on_admin_form(self):
        """AdminFollowUpForm must reject scheduling a duplicate pending follow-up for the same lead on the same date."""
        target_date = date.today() + timedelta(days=3)

        # Existing pending follow-up
        FollowUp.objects.create(
            lead=self.lead,
            follow_up_date=target_date,
            follow_up_time=time(14, 0),
            status=FollowUpStatus.PENDING,
            assigned_user=self.telecaller
        )

        # Attempt to schedule second pending follow-up on the exact same date
        form_data = {
            'lead': self.lead.pk,
            'follow_up_date': target_date,
            'follow_up_time': '16:00',
            'status': FollowUpStatus.PENDING,
            'assigned_user': self.telecaller.pk,
            'notes': 'Accidental duplicate attempt'
        }
        form = AdminFollowUpForm(data=form_data)
        self.assertFalse(form.is_valid())
        self.assertTrue(any("already scheduled" in err for err in form.non_field_errors()))

    def test_valid_repeat_followups_allowed_on_different_dates(self):
        """Follow-ups scheduled on different dates for the same lead are valid."""
        date1 = date.today() + timedelta(days=2)
        date2 = date.today() + timedelta(days=5)

        FollowUp.objects.create(
            lead=self.lead,
            follow_up_date=date1,
            status=FollowUpStatus.PENDING,
            assigned_user=self.telecaller
        )

        form_data = {
            'lead': self.lead.pk,
            'follow_up_date': date2,
            'status': FollowUpStatus.PENDING,
            'assigned_user': self.telecaller.pk,
            'notes': 'Valid next week follow-up'
        }
        form = AdminFollowUpForm(data=form_data)
        self.assertTrue(form.is_valid(), f"Errors: {form.errors}")

    def test_valid_repeat_followup_after_completion_on_same_date(self):
        """If a previous follow-up on the same date was completed or cancelled, a new follow-up is allowed."""
        target_date = date.today() + timedelta(days=1)

        # First follow-up completed
        FollowUp.objects.create(
            lead=self.lead,
            follow_up_date=target_date,
            status=FollowUpStatus.COMPLETED,
            assigned_user=self.telecaller
        )

        form_data = {
            'lead': self.lead.pk,
            'follow_up_date': target_date,
            'status': FollowUpStatus.PENDING,
            'assigned_user': self.telecaller.pk,
            'notes': 'New pending follow-up on same day after completing call'
        }
        form = AdminFollowUpForm(data=form_data)
        self.assertTrue(form.is_valid(), f"Errors: {form.errors}")

    def test_followup_reschedule_validation(self):
        """FollowUpRescheduleForm prevents rescheduling onto an existing pending follow-up date."""
        date1 = date.today() + timedelta(days=2)
        date2 = date.today() + timedelta(days=4)

        fu1 = FollowUp.objects.create(
            lead=self.lead,
            follow_up_date=date1,
            status=FollowUpStatus.PENDING,
            assigned_user=self.telecaller
        )
        fu2 = FollowUp.objects.create(
            lead=self.lead,
            follow_up_date=date2,
            status=FollowUpStatus.PENDING,
            assigned_user=self.telecaller
        )

        # Trying to reschedule fu1 to date2 (which already has fu2 pending)
        form = FollowUpRescheduleForm(
            data={'follow_up_date': date2, 'notes': 'Move to date2'},
            followup=fu1
        )
        self.assertFalse(form.is_valid())
        self.assertTrue(any("already scheduled" in err for err in form.non_field_errors()))

        # Rescheduling fu1 to a free date (e.g. +7 days) succeeds
        free_date = date.today() + timedelta(days=7)
        form_free = FollowUpRescheduleForm(
            data={'follow_up_date': free_date, 'notes': 'Move to free date'},
            followup=fu1
        )
        self.assertTrue(form_free.is_valid())

    def test_model_level_clean_validation(self):
        """FollowUp.clean() raises ValidationError on duplicate pending follow-up."""
        target_date = date.today() + timedelta(days=3)

        FollowUp.objects.create(
            lead=self.lead,
            follow_up_date=target_date,
            status=FollowUpStatus.PENDING
        )

        duplicate_fu = FollowUp(
            lead=self.lead,
            follow_up_date=target_date,
            status=FollowUpStatus.PENDING
        )
        with self.assertRaises(ValidationError):
            duplicate_fu.clean()

    def test_family_member_shared_phone_detection(self):
        """Different student name on same phone is flagged as FAMILY_MEMBER_POTENTIAL_DUPLICATE without corrupting name."""
        self.assertTrue(is_potential_family_member("Pooja Sharma", "Rahul Sharma"))
        self.assertFalse(is_potential_family_member("Rahul S", "Rahul Sharma"))
        self.assertFalse(is_potential_family_member("", "Rahul Sharma"))

        # Intake submission for sibling on existing lead's phone
        res = intake_lead(
            phone="9876543210",
            source="Website",
            name="Pooja Sharma",
            email="pooja@example.com",
            branch=self.branch,
        )

        self.assertFalse(res.created)
        self.assertEqual(res.action_taken, "FAMILY_MEMBER_POTENTIAL_DUPLICATE")

        # Original lead student name must NOT be overwritten
        self.lead.refresh_from_db()
        self.assertEqual(self.lead.name, "Rahul Sharma")

        # Audit record created
        audit = DuplicateLeadRecord.objects.filter(original_lead=self.lead).first()
        self.assertIsNotNone(audit)
        self.assertEqual(audit.action_taken, "FAMILY_MEMBER_POTENTIAL_DUPLICATE")
        self.assertIn("Pooja Sharma", audit.duplicate_reason)

        # Lead notes contain relationship verification note
        self.assertIn("Potential Family/Sibling Enquiry", self.lead.notes)
        self.assertIn("Pooja Sharma", self.lead.notes)

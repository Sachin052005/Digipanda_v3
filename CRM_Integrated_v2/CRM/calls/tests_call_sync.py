"""
CRM Call Sync (Android app) integration tests:
app login, Google Ads call ingest -> leads + missed-call follow-ups, recording upload -> drive.CallRecording,
callbacks cleared by recordings / completed CRM calls / the lead-page button, playback permissions.
"""
import shutil
import tempfile
from datetime import timedelta

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone
from rest_framework.authtoken.models import Token

from accounts.models import User, UserRole
from branches.models import Branch, SalesHeadBranchAccess
from calls.models import CallDevice, CallEvent, CallHistory, CallOutcome, CallStatus
from drive.models import CallRecording
from followups.models import FollowUp, FollowUpStatus
from leads.models import Lead, LeadAssignmentHistory, LeadStatus, TelecallerLeadSetup

TMP_MEDIA = tempfile.mkdtemp(prefix="crm_private_media_")


def ms(dt):
    return int(dt.timestamp() * 1000)


@override_settings(CALLS={"PRIVATE_MEDIA_ROOT": TMP_MEDIA})
class CallSyncTestBase(TestCase):
    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        shutil.rmtree(TMP_MEDIA, ignore_errors=True)

    def setUp(self):
        self.branch = Branch.objects.create(name="Velachery Sync")
        self.other_branch = Branch.objects.create(name="T Nagar Sync")
        self.sales_head = User.objects.create_user(username="sh_sync", password="pwd", role=UserRole.SALES_HEAD,
                                                   branch=self.branch)
        SalesHeadBranchAccess.objects.create(sales_head=self.sales_head, branch=self.branch)
        self.tc = User.objects.create_user(username="tc_sync", password="pwd", role=UserRole.TELECALLER,
                                           branch=self.branch, first_name="Priya")
        self.tc2 = User.objects.create_user(username="tc2_sync", password="pwd", role=UserRole.TELECALLER,
                                            branch=self.branch, first_name="Arun")
        self.admin = User.objects.create_user(username="admin_sync", password="pwd", role=UserRole.ADMIN,
                                              is_staff=True)
        self.api = Client()
        self.token = Token.objects.create(user=self.tc)
        self.auth = {"HTTP_AUTHORIZATION": f"Token {self.token.key}"}

    def ingest(self, calls, token=None):
        headers = {"HTTP_AUTHORIZATION": f"Token {token.key}"} if token else self.auth
        return self.api.post(reverse("app_calls_ingest"), {"calls": calls}, content_type="application/json",
                             **headers)

    def upload(self, *, file_id="101", number="9876543210", direction="outgoing", duration=95,
               started=None, name="Call_9876543210.m4a", token=None):
        headers = {"HTTP_AUTHORIZATION": f"Token {token.key}"} if token else self.auth
        data = {
            "audio_file": SimpleUploadedFile(name, b"ID3fake-audio-bytes" * 50, content_type="audio/mp4"),
            "device_file_id": file_id,
            "phone_number": number,
            "direction": direction,
            "duration_seconds": str(duration),
        }
        if started is not None:
            data["call_started_at"] = started.strftime("%Y-%m-%dT%H:%M:%SZ")
        return self.api.post(reverse("app_recording_upload"), data, **headers)


class AppLoginTests(CallSyncTestBase):
    def test_telecaller_login_returns_token_and_creates_device(self):
        r = self.api.post(reverse("app_login"), {"username": "tc_sync", "password": "pwd"},
                          HTTP_X_APP_VERSION="1.2", HTTP_X_GOOGLE_SIM="all")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()["token"], self.token.key)
        self.assertEqual(r.json()["name"], "Priya")
        device = CallDevice.objects.get(user=self.tc)
        self.assertEqual(device.app_version, "1.2")
        self.assertEqual(device.google_sim, "all")

    def test_wrong_password_is_400(self):
        r = self.api.post(reverse("app_login"), {"username": "tc_sync", "password": "nope"})
        self.assertEqual(r.status_code, 400)

    def test_admin_and_sales_head_cannot_use_app(self):
        for username in ("admin_sync", "sh_sync"):
            r = self.api.post(reverse("app_login"), {"username": username, "password": "pwd"})
            self.assertEqual(r.status_code, 403, username)

    def test_missing_or_bad_token_is_401(self):
        r = self.api.post(reverse("app_calls_ingest"), {"calls": []}, content_type="application/json")
        self.assertEqual(r.status_code, 401)
        r = self.api.post(reverse("app_calls_ingest"), {"calls": []}, content_type="application/json",
                          HTTP_AUTHORIZATION="Token bad")
        self.assertEqual(r.status_code, 401)

    def test_deactivated_user_token_is_401(self):
        self.tc.is_active = False
        self.tc.save()
        r = self.ingest([])
        self.assertEqual(r.status_code, 401)


class GoogleCallIngestTests(CallSyncTestBase):
    def test_missed_call_from_new_number_creates_assigned_lead_and_followup(self):
        when = timezone.now() - timedelta(minutes=2)
        r = self.ingest([{"number": "+91 98765 43210", "call_type": "missed", "timestamp_ms": ms(when),
                          "duration_sec": 0, "sim_account_id": "1", "contact_name": "Kavya"}])
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()["created"], 1)
        self.assertEqual(r.json()["new_leads"], 1)

        lead = Lead.objects.get(phone="9876543210")
        self.assertEqual(lead.name, "Kavya")
        self.assertEqual(lead.source, "Google Call")
        self.assertEqual(lead.channel.name, "Google Ads")
        self.assertEqual(lead.status, LeadStatus.NEW)
        self.assertEqual(lead.branch, self.branch)
        self.assertEqual(lead.assigned_telecaller, self.tc)
        self.assertEqual(lead.assigned_sales_head, self.sales_head)
        self.assertEqual(lead.assignment_status, "Assigned")
        self.assertIn("Missed Google call", lead.notes)
        self.assertTrue(LeadAssignmentHistory.objects.filter(lead=lead, to_user=self.tc).exists())

        event = CallEvent.objects.get(lead=lead)
        self.assertTrue(event.needs_callback)
        self.assertTrue(event.is_new_lead)
        fu = event.followup
        self.assertIsNotNone(fu)
        self.assertEqual(fu.status, FollowUpStatus.PENDING)
        self.assertEqual(fu.assigned_user, self.tc)
        due = timezone.make_aware(timezone.datetime.combine(fu.follow_up_date, fu.follow_up_time))
        self.assertLess(abs((due - (when + timedelta(minutes=15))).total_seconds()), 61)

    def test_receiver_counter_increments_in_branch_setup(self):
        setup = TelecallerLeadSetup.objects.create(telecaller=self.tc, branch=self.branch,
                                                   assignment_percentage=100)
        self.ingest([{"number": "9000000001", "call_type": "incoming", "timestamp_ms": ms(timezone.now()),
                      "duration_sec": 30}])
        setup.refresh_from_db()
        self.assertEqual(setup.current_leads_assigned, 1)

    def test_existing_lead_keeps_source_status_and_telecaller(self):
        lead = Lead.objects.create(name="FB Student", phone="+91 98400 12345", source="Meta",
                                   status=LeadStatus.INTERESTED, branch=self.other_branch,
                                   assigned_telecaller=self.tc2)
        r = self.ingest([{"number": "09840012345", "call_type": "missed", "timestamp_ms": ms(timezone.now()),
                          "duration_sec": 0}])
        self.assertEqual(r.json()["new_leads"], 0)
        lead.refresh_from_db()
        self.assertEqual(lead.source, "Meta")
        self.assertEqual(lead.status, LeadStatus.INTERESTED)
        self.assertEqual(lead.branch, self.other_branch)
        self.assertEqual(lead.assigned_telecaller, self.tc2)
        self.assertEqual(Lead.objects.count(), 1)
        fu = CallEvent.objects.get(lead=lead).followup
        self.assertEqual(fu.assigned_user, self.tc2)  # the lead's own telecaller calls back

    def test_alternate_phone_matches_existing_lead(self):
        lead = Lead.objects.create(name="Alt", phone="9111111111", alternate_phone="9222222222",
                                   assigned_telecaller=self.tc)
        self.ingest([{"number": "+919222222222", "call_type": "incoming", "timestamp_ms": ms(timezone.now()),
                      "duration_sec": 40}])
        self.assertEqual(Lead.objects.count(), 1)
        self.assertEqual(CallEvent.objects.get().lead, lead)

    def test_unassigned_existing_lead_gets_receiver(self):
        lead = Lead.objects.create(name="Pending", phone="9333333333", branch=self.branch,
                                   assignment_status="Pending Assignment")
        self.ingest([{"number": "9333333333", "call_type": "incoming", "timestamp_ms": ms(timezone.now()),
                      "duration_sec": 12}])
        lead.refresh_from_db()
        self.assertEqual(lead.assigned_telecaller, self.tc)

    def test_answered_call_needs_no_callback(self):
        self.ingest([{"number": "9444444444", "call_type": "incoming", "timestamp_ms": ms(timezone.now()),
                      "duration_sec": 125}])
        event = CallEvent.objects.get()
        self.assertFalse(event.needs_callback)
        self.assertIsNone(event.followup)
        self.assertFalse(FollowUp.objects.exists())
        self.assertIn("answered by Priya (2m 05s)", event.lead.notes)

    def test_zero_second_incoming_counts_as_missed(self):
        self.ingest([{"number": "9444444445", "call_type": "incoming", "timestamp_ms": ms(timezone.now()),
                      "duration_sec": 0}])
        self.assertTrue(CallEvent.objects.get().needs_callback)

    def test_closed_lead_gets_no_followup(self):
        Lead.objects.create(name="Joined", phone="9555555555", status=LeadStatus.JOINED,
                            assigned_telecaller=self.tc)
        self.ingest([{"number": "9555555555", "call_type": "rejected", "timestamp_ms": ms(timezone.now()),
                      "duration_sec": 0}])
        event = CallEvent.objects.get()
        self.assertTrue(event.needs_callback)
        self.assertIsNone(event.followup)
        self.assertFalse(FollowUp.objects.exists())

    def test_earlier_pending_followup_is_reused(self):
        lead = Lead.objects.create(name="Has FU", phone="9666666666", assigned_telecaller=self.tc)
        earlier = timezone.localtime() - timedelta(hours=1)
        fu = FollowUp.objects.create(lead=lead, assigned_user=self.tc, follow_up_date=earlier.date(),
                                     follow_up_time=earlier.time(), status=FollowUpStatus.PENDING)
        self.ingest([{"number": "9666666666", "call_type": "missed", "timestamp_ms": ms(timezone.now()),
                      "duration_sec": 0}])
        self.assertEqual(FollowUp.objects.count(), 1)
        self.assertEqual(CallEvent.objects.get().followup, fu)

    def test_duplicate_calls_and_bad_items(self):
        t = ms(timezone.now())
        call = {"number": "9777777777", "call_type": "missed", "timestamp_ms": t, "duration_sec": 0}
        self.ingest([call])
        r = self.ingest([call, {"number": "12", "call_type": "missed", "timestamp_ms": t},
                         {"number": "9888888888", "call_type": "outgoing", "timestamp_ms": t}])
        body = r.json()
        self.assertEqual(body["created"], 0)
        self.assertEqual(body["duplicates"], 1)
        self.assertEqual([e["index"] for e in body["errors"]], [1, 2])
        self.assertEqual(CallEvent.objects.count(), 1)

    def test_body_validation(self):
        r = self.api.post(reverse("app_calls_ingest"), {"foo": 1}, content_type="application/json", **self.auth)
        self.assertEqual(r.status_code, 400)
        r = self.ingest([{}] * 501)
        self.assertEqual(r.status_code, 400)

    def test_branch_head_receiver_falls_back_to_branch_engine(self):
        bh = User.objects.create_user(username="bh_sync", password="pwd", role=UserRole.BRANCH_HEAD,
                                      branch=self.branch)
        token = Token.objects.create(user=bh)
        # No 100% setup for this branch -> CRM rule: Pending Assignment
        self.ingest([{"number": "9012345678", "call_type": "incoming", "timestamp_ms": ms(timezone.now()),
                      "duration_sec": 10}], token=token)
        lead = Lead.objects.get(phone="9012345678")
        self.assertIsNone(lead.assigned_telecaller)
        self.assertEqual(lead.assignment_status, "Pending Assignment")
        # With a valid setup the branch engine assigns it
        TelecallerLeadSetup.objects.create(telecaller=self.tc2, branch=self.branch, assignment_percentage=100)
        self.ingest([{"number": "9012345679", "call_type": "incoming", "timestamp_ms": ms(timezone.now()),
                      "duration_sec": 10}], token=token)
        self.assertEqual(Lead.objects.get(phone="9012345679").assigned_telecaller, self.tc2)


class RecordingUploadTests(CallSyncTestBase):
    def setUp(self):
        super().setUp()
        self.lead = Lead.objects.create(name="Rahul", phone="9876543210", branch=self.branch,
                                        assigned_telecaller=self.tc, assigned_sales_head=self.sales_head)

    def test_upload_matches_lead_and_saves_file_outside_db(self):
        started = timezone.now() - timedelta(minutes=3)
        r = self.upload(started=started)
        self.assertEqual(r.status_code, 201)
        rec = CallRecording.objects.get(pk=r.json()["id"])
        self.assertEqual(rec.source, CallRecording.SOURCE_APP)
        self.assertEqual(rec.lead, self.lead)
        self.assertEqual(rec.match_status, "MATCHED")
        self.assertEqual(rec.telecaller, self.tc)
        self.assertEqual(rec.direction, "outgoing")
        self.assertEqual(rec.duration, "01:35")
        self.assertEqual(rec.duration_seconds, 95)
        self.assertIsNone(rec.drive_file_id)
        self.assertFalse(rec.audio_data)
        self.assertTrue(rec.audio_file.name.startswith("call_recordings/"))
        self.assertTrue(rec.audio_file.storage.exists(rec.audio_file.name))
        self.assertTrue(rec.audio_file.path.startswith(TMP_MEDIA))
        self.assertLess(abs((rec.recording_date - started).total_seconds()), 2)
        self.lead.refresh_from_db()
        self.assertIn("Outgoing call recording by Priya (1m 35s)", self.lead.notes)
        self.assertIn(rec, self.lead.drive_recordings.all())

    def test_duplicate_upload_returns_existing(self):
        first = self.upload(file_id="55")
        again = self.upload(file_id="55")
        self.assertEqual(again.status_code, 200)
        self.assertTrue(again.json()["duplicate"])
        self.assertEqual(again.json()["id"], first.json()["id"])
        self.assertEqual(CallRecording.objects.count(), 1)

    def test_unknown_number_never_creates_lead(self):
        r = self.upload(number="9000099999", file_id="77")
        rec = CallRecording.objects.get(pk=r.json()["id"])
        self.assertIsNone(rec.lead)
        self.assertEqual(rec.match_status, "UNMATCHED")
        self.assertIn("No matching CRM lead found", rec.unmatched_reason)
        self.assertEqual(Lead.objects.count(), 1)

    def test_no_number(self):
        r = self.upload(number="", file_id="78")
        rec = CallRecording.objects.get(pk=r.json()["id"])
        self.assertIn("could not be identified", rec.unmatched_reason)

    def test_bad_files_rejected_with_400(self):
        r = self.upload(name="notes.txt", file_id="80")
        self.assertEqual(r.status_code, 400)
        r = self.api.post(reverse("app_recording_upload"), {"device_file_id": "81"}, **self.auth)
        self.assertEqual(r.status_code, 400)
        self.assertFalse(CallRecording.objects.exists())

    def test_links_to_crm_call_history_closest_in_time(self):
        now = timezone.now()
        old = CallHistory.objects.create(lead=self.lead, caller=self.tc, telecaller=self.tc,
                                         call_started_at=now - timedelta(hours=3), duration=50)
        near = CallHistory.objects.create(lead=self.lead, caller=self.tc, telecaller=self.tc,
                                          call_started_at=now - timedelta(minutes=1), duration=0,
                                          call_status=CallStatus.CONNECTED, notes_completed=False)
        r = self.upload(started=now - timedelta(seconds=50), duration=70)
        rec = CallRecording.objects.get(pk=r.json()["id"])
        self.assertEqual(rec.call_history, near)
        near.refresh_from_db()
        self.assertEqual(near.duration, 70)  # filled from the phone because the CRM timer had 0
        old.refresh_from_db()
        self.assertEqual(old.duration, 50)

    def test_answered_outgoing_recording_clears_missed_call(self):
        missed_at = timezone.now() - timedelta(minutes=20)
        self.ingest([{"number": "9876543210", "call_type": "missed", "timestamp_ms": ms(missed_at),
                      "duration_sec": 0}])
        event = CallEvent.objects.get()
        self.assertTrue(event.needs_callback)
        self.upload(direction="outgoing", duration=60, started=timezone.now() - timedelta(minutes=1))
        event.refresh_from_db()
        self.assertFalse(event.needs_callback)
        self.assertEqual(event.called_back_by, "Priya")
        self.assertEqual(event.followup.status, FollowUpStatus.COMPLETED)
        self.lead.refresh_from_db()
        self.assertIn("Missed Google call returned by Priya", self.lead.notes)

    def test_unanswered_or_incoming_recording_keeps_callback(self):
        self.ingest([{"number": "9876543210", "call_type": "missed", "timestamp_ms": ms(timezone.now()),
                      "duration_sec": 0}])
        self.upload(direction="outgoing", duration=0, file_id="90")
        self.upload(direction="incoming", duration=40, file_id="91")
        self.assertTrue(CallEvent.objects.get().needs_callback)

    def test_recording_matched_to_google_call(self):
        when = timezone.now() - timedelta(minutes=5)
        self.ingest([{"number": "9876543210", "call_type": "incoming", "timestamp_ms": ms(when),
                      "duration_sec": 60}])
        r = self.upload(direction="incoming", started=when + timedelta(seconds=2))
        self.assertEqual(r.json()["call_event_id"], CallEvent.objects.get().pk)


class PlaybackAndPagesTests(CallSyncTestBase):
    def setUp(self):
        super().setUp()
        self.lead = Lead.objects.create(name="Rahul", phone="9876543210", branch=self.branch,
                                        assigned_telecaller=self.tc, assigned_sales_head=self.sales_head)
        r = self.upload(started=timezone.now())
        self.rec = CallRecording.objects.get(pk=r.json()["id"])
        self.web = Client()

    def test_owner_telecaller_and_admin_can_stream(self):
        for user in (self.tc, self.admin):
            self.web.force_login(user)
            resp = self.web.get(reverse("drive_stream_recording", args=[self.rec.pk]))
            self.assertEqual(resp.status_code, 200, user.username)
            self.assertEqual(b"".join(resp.streaming_content), b"ID3fake-audio-bytes" * 50)

    def test_range_request_returns_206(self):
        self.web.force_login(self.tc)
        resp = self.web.get(reverse("drive_stream_recording", args=[self.rec.pk]), HTTP_RANGE="bytes=0-9")
        self.assertEqual(resp.status_code, 206)
        self.assertEqual(resp.content, b"ID3fake-au")
        self.assertEqual(resp["Content-Range"], f"bytes 0-9/{len(b'ID3fake-audio-bytes' * 50)}")

    def test_other_telecaller_is_denied(self):
        self.web.force_login(self.tc2)
        resp = self.web.get(reverse("drive_stream_recording", args=[self.rec.pk]))
        self.assertEqual(resp.status_code, 403)

    def test_lead_page_shows_recording_google_calls_and_called_back_button(self):
        self.ingest([{"number": "9876543210", "call_type": "missed", "timestamp_ms": ms(timezone.now()),
                      "duration_sec": 0}])
        self.web.force_login(self.tc)
        resp = self.web.get(reverse("telecaller_lead_detail", args=[self.lead.pk]))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "CALL RECORDINGS (1)")
        self.assertContains(resp, "Call Sync app")
        self.assertContains(resp, "<audio controls")
        self.assertContains(resp, "GOOGLE ADS CALLS (1)")
        self.assertContains(resp, "Mark called back")

        resp = self.web.post(reverse("mark_lead_called_back", args=[self.lead.pk]),
                             {"next": reverse("telecaller_lead_detail", args=[self.lead.pk])})
        self.assertEqual(resp.status_code, 302)
        event = CallEvent.objects.get()
        self.assertFalse(event.needs_callback)
        self.assertEqual(event.followup.status, FollowUpStatus.COMPLETED)

    def test_all_role_lead_pages_render_card(self):
        bh = User.objects.create_user(username="bh_pages", password="pwd", role=UserRole.BRANCH_HEAD,
                                      branch=self.branch)
        counselor = User.objects.create_user(username="co_pages", password="pwd", role=UserRole.COUNSELOR,
                                             branch=self.branch)
        self.lead.assigned_counselor = counselor
        self.lead.assigned_branch_head = bh
        self.lead.save()
        for user, url_name in ((self.admin, "admin_lead_detail"), (self.sales_head, "manager_lead_detail"),
                               (bh, "branch_head_lead_detail"), (counselor, "counselor_lead_detail"),
                               (self.tc, "telecaller_lead_detail")):
            self.web.force_login(user)
            resp = self.web.get(reverse(url_name, args=[self.lead.pk]))
            self.assertEqual(resp.status_code, 200, url_name)
            self.assertContains(resp, "CALL RECORDINGS (1)", msg_prefix=url_name)

    def test_other_telecaller_cannot_mark_called_back(self):
        self.web.force_login(self.tc2)
        resp = self.web.post(reverse("mark_lead_called_back", args=[self.lead.pk]))
        self.assertEqual(resp.status_code, 403)

    def test_missed_calls_list_is_role_scoped(self):
        self.ingest([{"number": "9876543210", "call_type": "missed", "timestamp_ms": ms(timezone.now()),
                      "duration_sec": 0}])
        self.web.force_login(self.tc)
        resp = self.web.get(reverse("missed_calls_list"))
        self.assertContains(resp, "Rahul")
        self.web.force_login(self.tc2)
        resp = self.web.get(reverse("missed_calls_list"))
        self.assertNotContains(resp, "Rahul")
        self.web.force_login(self.admin)
        resp = self.web.get(reverse("missed_calls_list"))
        self.assertContains(resp, "Rahul")

    def test_completed_crm_call_clears_callback_but_no_answer_does_not(self):
        self.ingest([{"number": "9876543210", "call_type": "missed", "timestamp_ms": ms(timezone.now()),
                      "duration_sec": 0}])
        self.web.force_login(self.tc)
        self.web.post(reverse("complete_call_record"), {
            "lead_id": self.lead.pk, "duration": 20, "call_outcome": CallOutcome.NO_ANSWER,
            "notes": "Rang out"})
        self.assertTrue(CallEvent.objects.get().needs_callback)
        self.web.post(reverse("complete_call_record"), {
            "lead_id": self.lead.pk, "duration": 120, "call_outcome": CallOutcome.INTERESTED,
            "notes": "Wants weekend batch"})
        event = CallEvent.objects.get()
        self.assertFalse(event.needs_callback)
        self.assertEqual(event.followup.status, FollowUpStatus.COMPLETED)

    def test_call_recordings_page_is_role_scoped(self):
        self.web.force_login(self.admin)
        resp = self.web.get(reverse("call_recordings_list"))
        self.assertContains(resp, "Rahul")
        self.assertContains(resp, reverse("drive_stream_recording", args=[self.rec.pk]))
        self.assertNotContains(resp, "Add Drive")
        self.web.force_login(self.tc)
        self.assertContains(self.web.get(reverse("call_recordings_list")), "Rahul")
        self.web.force_login(self.tc2)
        self.assertNotContains(self.web.get(reverse("call_recordings_list")), "Rahul")
        # filters
        self.web.force_login(self.admin)
        resp = self.web.get(reverse("call_recordings_list"), {"direction": "incoming"})
        self.assertNotContains(resp, reverse("drive_stream_recording", args=[self.rec.pk]))

    def test_unmatched_recording_rematched_after_lead_created(self):
        r = self.upload(number="9000077777", file_id="999")
        rec = CallRecording.objects.get(pk=r.json()["id"])
        self.assertEqual(rec.match_status, "UNMATCHED")
        Lead.objects.create(name="Later", phone="+91 90000 77777", assigned_telecaller=self.tc)
        self.web.force_login(self.admin)
        self.web.post(reverse("recordings_retry_match"))
        rec.refresh_from_db()
        self.assertEqual(rec.match_status, "MATCHED")
        self.assertEqual(rec.lead.name, "Later")

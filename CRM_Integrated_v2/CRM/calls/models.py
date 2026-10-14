from django.db import models
from django.conf import settings
from django.utils import timezone

class CallStatus(models.TextChoices):
    QUEUED = 'Queued', 'Queued'
    DIALING = 'Dialing', 'Dialing'
    RINGING = 'Ringing', 'Ringing'
    IN_PROGRESS = 'In Progress', 'In Progress'
    INITIATED = 'Initiated', 'Initiated'
    CONNECTED = 'Connected', 'Connected'
    COMPLETED = 'Completed', 'Completed'
    FAILED = 'Failed', 'Failed'
    NO_ANSWER = 'No Answer', 'No Answer'
    BUSY = 'Busy', 'Busy'
    MISSED = 'Missed', 'Missed'
    CANCELLED = 'Cancelled', 'Cancelled'

class CallOutcome(models.TextChoices):
    INTERESTED = 'Interested', 'Interested'
    NOT_INTERESTED = 'Not Interested', 'Not Interested'
    FOLLOW_UP_REQUIRED = 'Follow-up Required', 'Follow-up Required'
    CALLBACK_REQUESTED = 'Callback Requested', 'Callback Requested'
    CONVERTED = 'Converted', 'Converted'
    NO_ANSWER = 'No Answer', 'No Answer'
    BUSY = 'Busy', 'Busy'
    RNR = 'RNR', 'RNR (Ring No Response)'

class CallHistory(models.Model):
    lead = models.ForeignKey(
        'leads.Lead',
        on_delete=models.CASCADE,
        related_name='calls'
    )
    caller = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='conducted_calls'
    )
    manager = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='manager_calls'
    )
    telecaller = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='telecaller_calls'
    )
    call_started_at = models.DateTimeField(default=timezone.now)
    dialed_at = models.DateTimeField(null=True, blank=True)
    answered_at = models.DateTimeField(null=True, blank=True)
    call_ended_at = models.DateTimeField(null=True, blank=True)
    duration = models.IntegerField(default=0, help_text="Duration in seconds")
    call_status = models.CharField(
        max_length=30,
        choices=CallStatus.choices,
        default=CallStatus.QUEUED
    )
    call_outcome = models.CharField(
        max_length=30,
        choices=CallOutcome.choices,
        default=CallOutcome.FOLLOW_UP_REQUIRED
    )
    notes = models.TextField(blank=True, default='')
    notes_completed = models.BooleanField(
        default=True,
        db_index=True,
        help_text="True if call notes have been submitted and call record is finalized"
    )
    recording_url = models.CharField(max_length=500, blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name_plural = 'Call histories'

    def __str__(self):
        caller_name = self.caller.username if self.caller else 'Unknown'
        lead_name = self.lead.name if self.lead else 'Unknown Lead'
        return f"Call with {lead_name} by {caller_name} ({self.duration}s)"


    @property
    def formatted_duration(self):
        minutes, seconds = divmod(self.duration, 60)
        hours, minutes = divmod(minutes, 60)
        if hours > 0:
            return f"{hours:02d}:{minutes:02d}:{seconds:02d}"
        return f"{minutes:02d}:{seconds:02d}"


# =====================================================================
# CRM CALL SYNC (Android app) — Google Ads calls
# =====================================================================

class CallDevice(models.Model):
    """One row per CRM login using the CRM Call Sync Android app. Created automatically."""

    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='call_device')
    google_sim = models.CharField(
        max_length=100, blank=True, default='',
        help_text="What the app reports: '' = Google calls off, 'all' = every SIM, else the SIM's account id",
    )
    app_version = models.CharField(max_length=20, blank=True, default='')
    last_seen_at = models.DateTimeField(null=True, blank=True)
    last_call_sync_at = models.DateTimeField(null=True, blank=True)
    last_recording_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['user__username']

    def __str__(self):
        return f"{self.user.get_full_name() or self.user.username}'s phone"


class RemoteOutgoingCall(models.Model):
    """
    Queue of outgoing call requests initiated from CRM on laptop/desktop.
    Fetched by the companion Android app to prompt/trigger dialing directly on the phone.
    """
    device = models.ForeignKey(CallDevice, on_delete=models.CASCADE, related_name='pending_dials')
    lead = models.ForeignKey('leads.Lead', on_delete=models.CASCADE, related_name='remote_dials')
    call_history = models.ForeignKey(CallHistory, on_delete=models.CASCADE, null=True, blank=True, related_name='remote_outgoing_calls')
    phone_number = models.CharField(max_length=40)
    status = models.CharField(max_length=30, choices=CallStatus.choices, default=CallStatus.QUEUED)
    dialed_at = models.DateTimeField(null=True, blank=True)
    answered_at = models.DateTimeField(null=True, blank=True)
    ended_at = models.DateTimeField(null=True, blank=True)
    duration = models.IntegerField(default=0, help_text="Duration in seconds")
    created_at = models.DateTimeField(auto_now_add=True)
    is_dispatched = models.BooleanField(default=False)
    dispatched_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"Dial {self.phone_number} for {self.device.user.username}"


class CallEventType(models.TextChoices):
    INCOMING = 'incoming', 'Incoming'
    MISSED = 'missed', 'Missed'
    REJECTED = 'rejected', 'Rejected'


class CallEvent(models.Model):
    """A call to the Google Ads number, read from the telecaller phone's call log."""

    device = models.ForeignKey(CallDevice, on_delete=models.CASCADE, related_name='calls')
    telecaller = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='google_call_events', help_text="Login of the phone that received the call",
    )
    lead = models.ForeignKey(
        'leads.Lead', on_delete=models.SET_NULL, null=True, blank=True, related_name='call_events'
    )
    followup = models.ForeignKey(
        'followups.FollowUp', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='google_call_events', help_text="Call-back follow-up created for a missed call",
    )
    phone = models.CharField(max_length=20, db_index=True, help_text="Normalized 10-digit number")
    raw_number = models.CharField(max_length=40)
    call_type = models.CharField(max_length=10, choices=CallEventType.choices)
    started_at = models.DateTimeField(db_index=True)
    duration_sec = models.PositiveIntegerField(default=0)
    sim_account_id = models.CharField(max_length=100, blank=True, default='')
    contact_name = models.CharField(max_length=150, blank=True, default='')

    is_new_lead = models.BooleanField(default=False, help_text="This call created the lead.")
    needs_callback = models.BooleanField(default=False, db_index=True)
    called_back_at = models.DateTimeField(null=True, blank=True)
    called_back_by = models.CharField(max_length=150, blank=True, default='')

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-started_at']
        constraints = [
            # The phone may resend the same call (retries); keep only one row.
            models.UniqueConstraint(fields=['device', 'raw_number', 'started_at'], name='uniq_google_call_per_device')
        ]

    def __str__(self):
        return f"{self.phone} {self.call_type} {self.started_at:%d-%b %H:%M}"

    @property
    def is_answered(self):
        return self.call_type == CallEventType.INCOMING and self.duration_sec > 0

    @property
    def formatted_duration(self):
        minutes, seconds = divmod(int(self.duration_sec or 0), 60)
        return f"{minutes:02d}:{seconds:02d}"

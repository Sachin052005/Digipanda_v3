from django.db import models
from django.conf import settings
from django.utils import timezone

from calls.storage import private_storage


class DriveConnection(models.Model):
    name = models.CharField(max_length=200, default='Call Recordings')
    folder_url = models.URLField(max_length=500)
    folder_id = models.CharField(max_length=150, db_index=True)
    connection_status = models.CharField(max_length=50, default='Connected')
    is_active = models.BooleanField(default=True, db_index=True)
    is_syncing = models.BooleanField(default=False)
    last_sync_status = models.CharField(max_length=50, default='Success')
    last_error_message = models.TextField(blank=True, default='')
    last_sync_at = models.DateTimeField(null=True, blank=True)
    branch = models.ForeignKey(
        'branches.Branch',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='drive_connections'
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='drive_connections'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.name} ({self.folder_id})"

    @property
    def folder_name(self):
        return self.name

    @folder_name.setter
    def folder_name(self, value):
        self.name = value

    @property
    def total_recordings_count(self):
        return self.recordings.count()

    @property
    def matched_recordings_count(self):
        return self.recordings.filter(match_status='MATCHED').count()

    @property
    def unmatched_recordings_count(self):
        return self.recordings.filter(match_status='UNMATCHED').count()


class CallRecording(models.Model):
    MATCH_STATUS_CHOICES = [
        ('MATCHED', 'Matched'),
        ('UNMATCHED', 'Unmatched'),
    ]
    ARCHIVE_STATUS_CHOICES = [
        ('PENDING', 'Pending'),
        ('ARCHIVED', 'Archived'),
        ('FAILED', 'Failed'),
    ]

    lead = models.ForeignKey(
        'leads.Lead',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='drive_recordings'
    )
    call_history = models.ForeignKey(
        'calls.CallHistory',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='drive_recordings'
    )
    drive_connection = models.ForeignKey(
        DriveConnection,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='recordings'
    )
    telecaller = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='archived_call_recordings'
    )
    source_folder_id = models.CharField(max_length=150, blank=True, default='', db_index=True)
    SOURCE_DRIVE = 'DRIVE'
    SOURCE_APP = 'APP'
    SOURCE_CHOICES = [
        (SOURCE_APP, 'CRM Call Sync App'),
        (SOURCE_DRIVE, 'Archived (Legacy Drive)'),
    ]
    DIRECTION_CHOICES = [
        ('incoming', 'Incoming'),
        ('outgoing', 'Outgoing'),
        ('unknown', 'Unknown'),
    ]

    source = models.CharField(max_length=10, choices=SOURCE_CHOICES, default=SOURCE_APP, db_index=True)
    # App recordings: uploaded by the CRM Call Sync Android app, stored on disk (private_media/)
    device = models.ForeignKey(
        'calls.CallDevice',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='recordings'
    )
    device_file_id = models.CharField(max_length=64, null=True, blank=True,
                                      help_text="MediaStore id on the phone (for de-duplication)")
    call_event = models.ForeignKey(
        'calls.CallEvent',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='recordings',
        help_text="Google Ads call this recording belongs to"
    )
    audio_file = models.FileField(storage=private_storage, upload_to='call_recordings/%Y/%m/',
                                  max_length=255, blank=True, default='')
    direction = models.CharField(max_length=10, choices=DIRECTION_CHOICES, default='unknown')
    duration_seconds = models.PositiveIntegerField(default=0)

    drive_file_id = models.CharField(max_length=150, unique=True, null=True, blank=True, db_index=True)
    file_name = models.CharField(max_length=255)
    mobile_number = models.CharField(max_length=30, blank=True, default='')
    normalized_mobile_number = models.CharField(max_length=20, blank=True, default='', db_index=True)
    drive_url = models.URLField(max_length=500, blank=True, default='')
    mime_type = models.CharField(max_length=50, default='audio/mpeg')
    duration = models.CharField(max_length=20, default='04:32')
    file_size = models.BigIntegerField(default=0)
    audio_data = models.BinaryField(null=True, blank=True)
    archive_status = models.CharField(
        max_length=20,
        choices=ARCHIVE_STATUS_CHOICES,
        default='PENDING',
        db_index=True
    )
    recording_date = models.DateTimeField(null=True, blank=True)
    match_status = models.CharField(
        max_length=20,
        choices=MATCH_STATUS_CHOICES,
        default='UNMATCHED',
        db_index=True
    )
    unmatched_reason = models.CharField(max_length=255, blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-recording_date', '-created_at']
        verbose_name = 'Call Recording'
        verbose_name_plural = 'Call Recordings'
        indexes = [
            models.Index(fields=['drive_file_id']),
            models.Index(fields=['normalized_mobile_number']),
            models.Index(fields=['match_status']),
        ]
        constraints = [
            # App retries never create a second row for the same phone file.
            models.UniqueConstraint(fields=['device', 'device_file_id'], name='uniq_app_recording_per_device')
        ]

    def __str__(self):
        return f"{self.file_name} ({self.match_status})"

    @property
    def is_app_recording(self):
        return self.source == self.SOURCE_APP

    @property
    def has_audio(self):
        return bool(self.audio_file) or bool(self.audio_data)

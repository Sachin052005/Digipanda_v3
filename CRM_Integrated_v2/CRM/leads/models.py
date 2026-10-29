import uuid
from django.db import models
from django.conf import settings
from django.core.exceptions import ValidationError

class LeadTag(models.Model):
    name = models.CharField(max_length=50, unique=True, db_index=True)
    color = models.CharField(max_length=20, default='#3b82f6', blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['name']

    def __str__(self):
        return self.name

class LeadStatus(models.TextChoices):
    NEW = 'New', 'New'
    CONTACTED = 'Contacted', 'Contacted'
    INTERESTED = 'Interested', 'Interested'
    FOLLOW_UP = 'Follow-up', 'Follow-up'
    DEMO_SCHEDULED = 'Demo Scheduled', 'Demo Scheduled'
    INSTITUTE_VISIT = 'Institute Visit', 'Institute Visit'
    CONVERTED = 'Converted', 'Converted'
    ENROLLED = 'Enrolled', 'Enrolled'
    LOST = 'Lost', 'Lost'
    LATER = 'Later', 'Later'
    DISCUSSION = 'Discussion', 'Discussion'
    VISIT_SCHEDULED = 'Visit Scheduled', 'Visit Scheduled'
    VISITED = 'Visited', 'Visited'
    COUNSELING = 'Counseling', 'Counseling'
    JOINED = 'Joined', 'Joined'
    NOT_INTERESTED = 'Not Interested', 'Not Interested'
    NO_ANSWER = 'No Answer', 'No Answer'
    BUSY = 'Busy', 'Busy'
    NOT_JOINED = 'Not Joined', 'Not Joined'
    SWITCHED_OFF = 'Switched Off', 'Switched Off'
    HISTORICAL = 'Historical', 'Historical'

class PipelineStatus(models.Model):
    name = models.CharField(max_length=50, unique=True)
    stage_category = models.CharField(max_length=50, default='General', blank=True)
    color = models.CharField(max_length=30, default='#3b82f6', blank=True)
    sort_order = models.IntegerField(default=0)
    is_active = models.BooleanField(default=True)
    is_system_default = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['sort_order', 'name']
        verbose_name = 'Pipeline Status'
        verbose_name_plural = 'Pipeline Statuses'

    def __str__(self):
        return self.name

class LeadCategory(models.TextChoices):
    TRAINING = 'Training', 'Training'
    PLACEMENT = 'Placement', 'Placement'

class VisitorStatus(models.TextChoices):
    WAITING = 'Waiting', 'Waiting in Reception'
    IN_CONSULTATION = 'In Consultation', 'In Consultation'
    COMPLETED = 'Completed', 'Consultation Completed'
    CANCELLED = 'Cancelled', 'Cancelled'
    NO_SHOW = 'No Show', 'No Show'

class LeadOwnerType(models.TextChoices):
    UNASSIGNED = 'UNASSIGNED', 'Unassigned'
    TELECALLER = 'TELECALLER', 'Telecaller'
    COUNSELOR = 'COUNSELOR', 'Counselor'
    BRANCH_HEAD = 'BRANCH_HEAD', 'Branch Head'
    SALES_HEAD = 'SALES_HEAD', 'Sales Head'
    ADMIN = 'ADMIN', 'Admin'

class Lead(models.Model):
    name = models.CharField(max_length=150)
    category = models.CharField(
        max_length=20,
        choices=LeadCategory.choices,
        default=LeadCategory.TRAINING,
        blank=True,
        db_index=True,
        help_text="Segmentation: Training vs Placement"
    )
    phone = models.CharField(max_length=20)
    normalized_phone = models.CharField(
        max_length=20,
        blank=True,
        default='',
        db_index=True,
        help_text="Canonical 10-digit digits-only contact number for high-speed indexing"
    )
    email = models.EmailField(blank=True, default='')
    alternate_phone = models.CharField(max_length=20, blank=True, default='')
    channel = models.ForeignKey(
        'channels.Channel',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='leads'
    )
    status = models.CharField(
        max_length=30,
        choices=LeadStatus.choices,
        default=LeadStatus.NEW
    )
    assigned_sales_head = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='manager_leads'
    )
    assigned_telecaller = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='telecaller_leads'
    )
    assigned_branch_head = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='branch_head_leads',
        limit_choices_to={'role': 'BRANCH_HEAD'}
    )
    assigned_counselor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='counselor_leads',
        limit_choices_to={'role': 'COUNSELOR'}
    )
    current_owner_type = models.CharField(
        max_length=20,
        choices=LeadOwnerType.choices,
        default=LeadOwnerType.UNASSIGNED,
        db_index=True
    )
    product = models.ForeignKey(
        'products.Product',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='leads'
    )
    branch = models.ForeignKey(
        'branches.Branch',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='leads'
    )
    secondary_branches = models.ManyToManyField(
        'branches.Branch',
        blank=True,
        related_name='multi_branch_leads',
        help_text="Additional branches where this lead has appeared"
    )
    notes = models.TextField(blank=True, default='')
    source = models.CharField(max_length=50, default='Manual', blank=True, db_index=True)
    is_offline = models.BooleanField(default=False, db_index=True)
    assignment_status = models.CharField(
        max_length=50,
        default='Assigned',
        blank=True,
        db_index=True,
        help_text="Status of assignment: Assigned, Pending Assignment, or Unassigned"
    )
    assigned_at = models.DateTimeField(null=True, blank=True)
    pending_assignment_reason = models.CharField(max_length=255, blank=True, default='')
    visitor_status = models.CharField(
        max_length=30,
        choices=VisitorStatus.choices,
        default=VisitorStatus.WAITING,
        blank=True,
        db_index=True,
        help_text="Front-desk reception status for walk-in visitors"
    )
    center_visit_date = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Actual or scheduled center visit date and time"
    )
    token_number = models.CharField(
        max_length=30,
        blank=True,
        default='',
        help_text="Reception token / visitor pass number"
    )
    rating = models.PositiveSmallIntegerField(
        default=1,
        choices=[(i, f"{i} Star{'s' if i > 1 else ''}") for i in range(1, 6)],
        db_index=True,
        help_text="Priority rating from 1 to 5 stars"
    )
    tags = models.ManyToManyField(
        'LeadTag',
        blank=True,
        related_name='leads',
        help_text="Custom tags or segment groups"
    )
    custom_fields = models.JSONField(
        default=dict,
        blank=True,
        help_text="Key-value pairs of editable custom attributes"
    )
    whatsapp_opt_out = models.BooleanField(default=False, db_index=True, help_text="Lead has opted out of WhatsApp communications")
    whatsapp_consent_given = models.BooleanField(default=True, db_index=True, help_text="Explicit consent on record to message via WhatsApp")
    whatsapp_consent_date = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.name} - {self.phone} ({self.status})"

    @property
    def assigned_manager(self):
        """Backward-compat read-only alias for templates not yet updated to assigned_sales_head."""
        return self.assigned_sales_head

    @property
    def masked_phone(self):
        if not self.phone:
            return ''
        digits = str(self.phone).strip()
        if len(digits) >= 5:
            return f"{digits[:5]}xxxxx"
        return digits

    @property
    def has_duplicate_attempts(self):
        """Returns True if this lead has actual incoming duplicate touches (excluding initial creation)."""
        if hasattr(self, '_prefetched_objects_cache') and 'duplicate_records' in self._prefetched_objects_cache:
            return any(r.record_type != 'ORIGINAL_INGESTION' for r in self.duplicate_records.all())
        return self.duplicate_records.exclude(record_type='ORIGINAL_INGESTION').exists()

    @property
    def last_three_calls(self):
        """Returns the last 3 call attempts for quick history and modal display."""
        return list(self.calls.select_related('caller', 'telecaller').order_by('-call_started_at')[:3])

    def get_all_branches(self):
        branches_list = []
        if self.branch:
            branches_list.append(self.branch)
        for b in self.secondary_branches.all():
            if b not in branches_list:
                branches_list.append(b)
        return branches_list

    def get_all_branch_names(self):
        return [b.name for b in self.get_all_branches()]

    def get_source_spreadsheets(self):
        from .models import GoogleSheetConnection
        conns = list(GoogleSheetConnection.objects.filter(row_mappings__lead=self).distinct())
        if not conns and self.source:
            conn_by_name = GoogleSheetConnection.objects.filter(name__iexact=self.source).first()
            if conn_by_name:
                conns.append(conn_by_name)
        return conns

    @property
    def source_spreadsheet_names(self):
        conns = self.get_source_spreadsheets()
        if conns:
            return [c.name for c in conns]
        if self.source and self.source != 'Manual':
            return [self.source]
        return []

    @property
    def parsed_notes_data(self):
        """
        Parses lead notes into structured clean columns (Field | Value),
        strips [Sheet Update] and [Form Data], separates general remarks / call logs.
        """
        import re
        if not self.notes:
            return {'fields': [], 'logs': []}

        clean = self.notes
        clean = re.sub(r'\[Sheet Update\]:?', '', clean)
        clean = re.sub(r'\[Form Data\]:?', '', clean)

        fields = []
        logs = []

        for line in clean.splitlines():
            line = line.strip()
            if not line:
                continue
            if re.match(r'^\[\d{4}-\d{2}-\d{2}.*?\]', line):
                logs.append(line)
                continue

            if '|' in line:
                tokens = line.split('|')
                for token in tokens:
                    token = token.strip()
                    if ':' in token:
                        k, v = token.split(':', 1)
                        if k.strip().lower() != 'timestamp':
                            fields.append((k.strip(), v.strip()))
                    elif token:
                        fields.append(('Note', token))
            elif ':' in line and not line.startswith('http'):
                k, v = line.split(':', 1)
                if k.strip().lower() != 'timestamp':
                    fields.append((k.strip(), v.strip()))
            else:
                if line.lower() in ['gen ai', 'data science', 'cyber security', 'full stack']:
                    fields.append(('Domain / Course', line))
                else:
                    logs.append(line)

        return {'fields': fields, 'logs': logs}

    def clean(self):
        super().clean()
        if self.assigned_telecaller and self.branch_id and self.assigned_telecaller.branch_id and self.assigned_telecaller.branch_id != self.branch_id:
            raise ValidationError({
                'assigned_telecaller': f"Telecaller '{self.assigned_telecaller.username}' belongs to a different branch."
            })
        if self.assigned_counselor_id and self.branch_id and self.assigned_counselor.branch_id and self.assigned_counselor.branch_id != self.branch_id:
            raise ValidationError({
                'assigned_counselor': f"Counselor '{self.assigned_counselor.username}' belongs to a different branch."
            })
        if self.assigned_branch_head_id and self.branch_id and self.assigned_branch_head.branch_id and self.assigned_branch_head.branch_id != self.branch_id:
            raise ValidationError({
                'assigned_branch_head': f"Branch Head '{self.assigned_branch_head.username}' belongs to a different branch."
            })

    def save(self, *args, **kwargs):
        if self.phone and not str(self.phone).startswith('NoPhone-'):
            from .duplicates import normalize_phone
            norm = normalize_phone(self.phone)
            if norm.startswith('+'):
                self.normalized_phone = norm
            else:
                self.normalized_phone = norm[-10:] if len(norm) >= 10 else norm
            update_fields = kwargs.get('update_fields')
            if update_fields is not None:
                update_fields = set(update_fields)
                update_fields.add('normalized_phone')
                kwargs['update_fields'] = list(update_fields)
        elif not self.phone or str(self.phone).startswith('NoPhone-'):
            self.normalized_phone = ''
        super().save(*args, **kwargs)


class LeadAssignmentHistory(models.Model):
    lead = models.ForeignKey(Lead, on_delete=models.CASCADE, related_name='assignment_history')
    from_user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='+')
    to_user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='+')
    from_role = models.CharField(max_length=20, blank=True, default='')
    to_role = models.CharField(max_length=20, blank=True, default='')
    branch = models.ForeignKey('branches.Branch', on_delete=models.SET_NULL, null=True, blank=True, related_name='+')
    reason = models.CharField(max_length=255, blank=True, default='')
    assigned_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='+')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name_plural = 'Lead assignment histories'

    def __str__(self):
        return f"{self.lead_id}: {self.from_role or '-'} -> {self.to_role or '-'} ({self.created_at:%Y-%m-%d %H:%M})"


class LeadStatusHistory(models.Model):
    lead = models.ForeignKey(Lead, on_delete=models.CASCADE, related_name='status_history')
    old_status = models.CharField(max_length=30, blank=True, default='')
    new_status = models.CharField(max_length=30)
    changed_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='+')
    remarks = models.TextField(blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name_plural = 'Lead status histories'

    def __str__(self):
        return f"{self.lead_id}: {self.old_status or '-'} -> {self.new_status} ({self.created_at:%Y-%m-%d %H:%M})"


class BulkOperationStatus(models.TextChoices):
    PENDING = 'PENDING', 'Pending'
    RUNNING = 'RUNNING', 'Running'
    COMPLETED = 'COMPLETED', 'Completed'
    COMPLETED_WITH_ERRORS = 'COMPLETED_WITH_ERRORS', 'Completed with Errors'
    FAILED = 'FAILED', 'Failed'


class BulkOperationRecord(models.Model):
    operation_id = models.CharField(max_length=64, unique=True, db_index=True)
    idempotency_key = models.CharField(max_length=128, blank=True, default='', db_index=True)
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='bulk_operations')
    operation_type = models.CharField(max_length=50, default='bulk_edit', db_index=True)
    status = models.CharField(max_length=30, choices=BulkOperationStatus.choices, default=BulkOperationStatus.PENDING, db_index=True)
    total_requested = models.IntegerField(default=0)
    total_authorized = models.IntegerField(default=0)
    success_count = models.IntegerField(default=0)
    skipped_count = models.IntegerField(default=0)
    failed_count = models.IntegerField(default=0)
    requested_changes = models.JSONField(default=dict, blank=True)
    error_summary = models.JSONField(default=list, blank=True)
    reassignment_note = models.TextField(blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['operation_type', 'status'], name='idx_bulk_op_type_status'),
            models.Index(fields=['created_at'], name='idx_bulk_op_created_at'),
        ]

    def __str__(self):
        return f"BulkOp #{self.operation_id[:8]} ({self.status}) - {self.success_count}/{self.total_authorized}"


class LeadImportHistory(models.Model):
    file_name = models.CharField(max_length=255)
    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='lead_imports'
    )
    uploaded_on = models.DateTimeField(auto_now_add=True)
    records = models.IntegerField(default=0)
    successful = models.IntegerField(default=0)
    failed = models.IntegerField(default=0)
    status = models.CharField(max_length=30, default='Completed')
    error_log = models.TextField(blank=True, default='')

    class Meta:
        ordering = ['-uploaded_on']
        verbose_name_plural = 'Lead import histories'

    def __str__(self):
        return f"{self.file_name} ({self.uploaded_on.strftime('%Y-%m-%d %H:%M')})"

class ConnectionState(models.TextChoices):
    ACTIVE = 'ACTIVE', 'Active'
    PAUSED = 'PAUSED', 'Paused'
    DISCONNECTED = 'DISCONNECTED', 'Disconnected'

class SyncStatus(models.TextChoices):
    NEVER_SYNCED = 'NEVER_SYNCED', 'Never Synced'
    RUNNING = 'RUNNING', 'Running'
    SUCCESS = 'SUCCESS', 'Success'
    FAILED = 'FAILED', 'Failed'

class GoogleSheetConnection(models.Model):
    name = models.CharField(max_length=200)
    spreadsheet_url = models.URLField(max_length=500)
    spreadsheet_id = models.CharField(max_length=150, db_index=True)
    gid = models.CharField(max_length=50, blank=True, default='0', db_index=True)
    worksheet_name = models.CharField(max_length=150, default='Sheet1')
    branch = models.ForeignKey(
        'branches.Branch',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='google_sheet_connections'
    )
    channel = models.ForeignKey(
        'channels.Channel',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='google_sheet_connections'
    )
    assignment_method = models.CharField(
        max_length=20,
        choices=[('Automatic', 'Automatic'), ('Manual', 'Manual')],
        default='Automatic'
    )
    field_mapping = models.JSONField(default=dict, blank=True)
    is_active = models.BooleanField(default=True)
    connection_status = models.CharField(
        max_length=20,
        choices=ConnectionState.choices,
        default=ConnectionState.ACTIVE,
        db_index=True
    )
    sync_interval_seconds = models.IntegerField(default=60)
    last_sync_time = models.DateTimeField(null=True, blank=True)
    last_sync_status = models.CharField(max_length=50, default='Connected')
    last_sync_error = models.TextField(blank=True, default='')
    total_leads_imported = models.IntegerField(default=0)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='google_sheet_connections'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def save(self, *args, **kwargs):
        update_fields = kwargs.get('update_fields')
        if update_fields is not None:
            update_fields = set(update_fields)
            if 'is_active' in update_fields:
                if self.is_active:
                    self.connection_status = ConnectionState.ACTIVE
                elif self.last_sync_status == 'Paused':
                    self.connection_status = ConnectionState.PAUSED
                else:
                    self.connection_status = ConnectionState.DISCONNECTED
                update_fields.add('connection_status')
            elif 'connection_status' in update_fields:
                self.is_active = (self.connection_status == ConnectionState.ACTIVE)
                update_fields.add('is_active')
            kwargs['update_fields'] = list(update_fields)
        else:
            if not self.is_active:
                if self.last_sync_status == 'Paused':
                    self.connection_status = ConnectionState.PAUSED
                else:
                    self.connection_status = ConnectionState.DISCONNECTED
            else:
                self.connection_status = ConnectionState.ACTIVE
        super().save(*args, **kwargs)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.name} ({self.worksheet_name})"

    @property
    def default_branch(self):
        return self.branch

    @default_branch.setter
    def default_branch(self, value):
        self.branch = value

    @property
    def default_branch_id(self):
        return self.branch_id

    @default_branch_id.setter
    def default_branch_id(self, value):
        self.branch_id = value

    @property
    def sheet_url(self):
        return self.spreadsheet_url

    @sheet_url.setter
    def sheet_url(self, value):
        self.spreadsheet_url = value

    @property
    def last_synced_at(self):
        return self.last_sync_time

    @last_synced_at.setter
    def last_synced_at(self, value):
        self.last_sync_time = value


# Alias GoogleSheetSource to GoogleSheetConnection for suggested architecture conformity
GoogleSheetSource = GoogleSheetConnection


class GoogleSheetRowMapping(models.Model):
    connection = models.ForeignKey(
        GoogleSheetConnection,
        on_delete=models.CASCADE,
        related_name='row_mappings'
    )
    lead = models.ForeignKey(
        Lead,
        on_delete=models.CASCADE,
        related_name='sheet_mappings'
    )
    row_identifier = models.CharField(max_length=255, db_index=True)
    row_index = models.IntegerField()
    row_data_hash = models.CharField(max_length=64, blank=True)
    source_status = models.CharField(max_length=50, default='Active')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('connection', 'row_identifier')
        ordering = ['row_index']

    def __str__(self):
        return f"{self.connection.name} - Row {self.row_index} -> {self.lead.name}"

class GoogleSheetSyncHistory(models.Model):
    connection = models.ForeignKey(
        GoogleSheetConnection,
        on_delete=models.CASCADE,
        related_name='sync_histories'
    )
    timestamp = models.DateTimeField(auto_now_add=True)
    rows_checked = models.IntegerField(default=0)
    new_leads = models.IntegerField(default=0)
    updated_leads = models.IntegerField(default=0)
    skipped = models.IntegerField(default=0)
    failed = models.IntegerField(default=0)
    assigned_leads = models.IntegerField(default=0)
    status = models.CharField(max_length=50, default='Completed')
    error_summary = models.TextField(blank=True, default='')

    class Meta:
        ordering = ['-timestamp']

    def __str__(self):
        return f"Sync {self.connection.name} at {self.timestamp.strftime('%Y-%m-%d %H:%M')} ({self.status})"


# =====================================================================
# GOOGLE FORM CONNECTION MODEL
# =====================================================================
class GoogleFormConnection(models.Model):
    name = models.CharField(max_length=200, default='Google Form Leads')
    form_url = models.CharField(max_length=500)
    form_id = models.CharField(max_length=150, blank=True, default='', db_index=True)
    is_active = models.BooleanField(default=True)
    last_sync_time = models.DateTimeField(null=True, blank=True)
    last_sync_status = models.CharField(max_length=50, default='Connected')
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='google_form_connections'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.name} ({self.form_url})"


# =====================================================================
# SETTINGS -> LEAD SETUP MODELS
# =====================================================================
class AssignmentMethod(models.TextChoices):
    PERCENTAGE = 'PERCENTAGE', 'Percentage Based'
    COUNT = 'COUNT', 'Number Of Leads Based'


class LeadSetupConfig(models.Model):
    """
    Global configuration for Lead Setup assignment method.
    """
    assignment_method = models.CharField(
        max_length=20,
        choices=AssignmentMethod.choices,
        default=AssignmentMethod.PERCENTAGE
    )
    updated_at = models.DateTimeField(auto_now=True)

    @classmethod
    def get_current_method(cls):
        cfg = cls.objects.first()
        if not cfg:
            cfg = cls.objects.create(assignment_method=AssignmentMethod.PERCENTAGE)
        return cfg.assignment_method


CANONICAL_LEAD_SOURCES = [
    'WhatsApp',
    'Facebook',
    'Website',
    'Google Sheets',
    'Walk-in',
    'Google Call',
    'Manual',
]


def normalize_lead_source(src: str) -> str:
    """Normalizes raw lead source strings into canonical CRM lead sources."""
    if not src:
        return ''
    s = str(src).strip()
    sl = s.lower()
    if 'walk' in sl:
        return 'Walk-in'
    if 'whatsapp' in sl:
        return 'WhatsApp'
    if 'facebook' in sl or 'meta' in sl or 'lead form' in sl:
        return 'Facebook'
    if 'sheet' in sl:
        return 'Google Sheets'
    if 'google call' in sl or 'call' in sl:
        return 'Google Call'
    if 'web' in sl or 'google ad' in sl or 'seo' in sl:
        return 'Website'
    if 'manual' in sl:
        return 'Manual'
    return s


class TelecallerLeadSetup(models.Model):
    """
    Branch- and Lead-Source-based Telecaller assignment rules:
    - Hierarchy: Branch -> Lead Source -> Eligible Telecallers -> Allocation Percentages (100% total per source)
    """
    telecaller = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='lead_setup_rules'
    )
    branch = models.ForeignKey(
        'branches.Branch',
        on_delete=models.CASCADE,
        related_name='telecaller_lead_setups'
    )
    source = models.CharField(
        max_length=100,
        blank=True,
        default='',
        db_index=True,
        help_text="Lead source (e.g. WhatsApp, Facebook, Website, Google Sheets, Walk-in, Google Call, Manual). Empty = Branch Default."
    )
    channel = models.ForeignKey(
        'channels.Channel',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='telecaller_lead_setups'
    )
    channel_name = models.CharField(max_length=100, blank=True, default='', db_index=True)
    assignment_percentage = models.IntegerField(default=0, help_text="e.g. 40 for 40%")
    lead_count = models.IntegerField(default=0, help_text="Target / Limit lead count")
    current_leads_assigned = models.IntegerField(default=0, help_text="Count of leads assigned under this rule")
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('telecaller', 'branch', 'source')
        ordering = ['branch__name', 'source', 'telecaller__username']

    def __str__(self):
        name = self.telecaller.get_full_name() or self.telecaller.username
        src = self.source or self.channel_name or "General"
        return f"{name} - {self.branch.name} [{src}] ({self.assignment_percentage}%, {self.lead_count} leads)"


class LeadAllocationConfigAudit(models.Model):
    """
    Audit log of lead assignment configuration changes across branches and sources.
    Tracks who changed what allocation, previous values, new values, and timestamp.
    """
    branch = models.ForeignKey(
        'branches.Branch',
        on_delete=models.CASCADE,
        related_name='allocation_audits'
    )
    source = models.CharField(max_length=100, blank=True, default='', db_index=True)
    changed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='lead_allocation_audits'
    )
    previous_config = models.JSONField(default=dict, blank=True)
    new_config = models.JSONField(default=dict, blank=True)
    notes = models.CharField(max_length=255, blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        by = self.changed_by.username if self.changed_by else 'System'
        return f"Allocation Audit: {self.branch.name} [{self.source or 'General'}] by {by} at {self.created_at}"



# =====================================================================
# DUPLICATE LEAD RECORD MODEL (10-Day Rule)
# =====================================================================
class DuplicateLeadRecord(models.Model):
    """
    Stores duplicate submission details and audit trail for a lead in a dedicated separate table.
    Tracks cross-source duplicate detections under the 10-day rule and pre-merge archives.
    """
    RECORD_TYPE_CHOICES = [
        ('INCOMING_DUPLICATE', 'Incoming Duplicate (<= 10 Days)'),
        ('REENQUIRY_DUPLICATE', 'Re-enquiry Duplicate (> 10 Days)'),
        ('MERGED_ARCHIVE', 'Merged / Consolidated Lead Archive'),
        ('MANUAL_PROMOTED', 'Promoted to Independent Lead'),
    ]

    original_lead = models.ForeignKey(
        Lead,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='duplicate_records'
    )
    record_type = models.CharField(
        max_length=50,
        choices=RECORD_TYPE_CHOICES,
        default='INCOMING_DUPLICATE',
        db_index=True
    )
    name = models.CharField(max_length=150)
    phone = models.CharField(max_length=20)
    normalized_phone = models.CharField(max_length=20, blank=True, default='', db_index=True)
    email = models.EmailField(blank=True, default='')
    branch = models.ForeignKey(
        'branches.Branch',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='duplicate_lead_records'
    )
    branch_name = models.CharField(max_length=150, blank=True, default='')
    existing_branch = models.ForeignKey(
        'branches.Branch',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='audit_existing_records'
    )
    existing_branch_name = models.CharField(max_length=150, blank=True, default='')
    existing_source = models.CharField(max_length=100, blank=True, default='')
    existing_lead_created_at = models.DateTimeField(null=True, blank=True)
    elapsed_days = models.FloatField(null=True, blank=True)
    status = models.CharField(max_length=50, blank=True, default='New')
    duplicate_reason = models.CharField(max_length=255, blank=True, default='')
    action_taken = models.CharField(max_length=100, blank=True, default='', db_index=True)
    field_changes = models.JSONField(default=dict, blank=True)
    notes = models.TextField(blank=True, default='Same lead details detected.')
    source = models.CharField(max_length=100, default='Google Form')
    provider_event_id = models.CharField(max_length=255, null=True, blank=True, default=None, db_index=True)
    processing_status = models.CharField(max_length=50, default='PROCESSED', db_index=True)
    notification_status = models.CharField(max_length=50, default='PENDING')
    data_payload = models.JSONField(default=dict, blank=True)
    submitted_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-submitted_at']
        indexes = [
            models.Index(fields=['source', 'provider_event_id'], name='idx_dup_lead_src_event'),
            models.Index(fields=['normalized_phone'], name='idx_dup_lead_norm_phone'),
            models.Index(fields=['record_type', 'submitted_at'], name='idx_dup_lead_type_sub'),
        ]

    def __str__(self):
        return f"Duplicate: {self.name} ({self.phone}) [{self.action_taken}] in {self.branch_name or 'N/A'}"


class WalkinEnquiryForm(models.Model):
    title = models.CharField(max_length=200, default="Student Enquiry Form")
    slug = models.SlugField(max_length=200, unique=True, db_index=True)
    description = models.CharField(max_length=500, blank=True, default="Training & Placement Enquiry")
    branch = models.ForeignKey(
        'branches.Branch',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='walkin_forms',
        help_text="If assigned, leads from this form automatically belong to this branch."
    )
    is_default = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    theme_color = models.CharField(max_length=20, default="#4f46e5")
    logo = models.ImageField(upload_to='form_logos/', null=True, blank=True)
    banner_image = models.ImageField(upload_to='form_banners/', null=True, blank=True)
    form_schema = models.JSONField(
        default=dict,
        blank=True,
        help_text="JSON structure holding sections, fields, choices, and validation."
    )
    submissions_count = models.PositiveIntegerField(default=0)
    created_by = models.ForeignKey('accounts.User', on_delete=models.SET_NULL, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-is_default', '-created_at']

    def __str__(self):
        branch_str = f" ({self.branch.name})" if self.branch else ""
        return f"{self.title}{branch_str}"


from .models_enrollment import (
    Enrollment,
    Installment,
    PaymentTransaction,
    PaymentVerificationHistory,
    InstallmentScheduleHistory,
    PaymentEmailLog,
    GSTTreatment,
    PaymentPlan,
    InstallmentMethod,
    EnrollmentStatus,
    EnrollmentPaymentStatus,
    InstallmentStatus,
    PaymentMethod,
    PaymentTransactionStatus,
)




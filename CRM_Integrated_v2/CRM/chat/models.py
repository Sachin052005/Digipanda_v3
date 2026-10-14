from django.db import models
from django.utils import timezone
from django.conf import settings


class BusinessAccount(models.Model):
    """
    Represents a WhatsApp Business Account phone number (channel).
    Allows managing multiple WhatsApp numbers on the same CRM.
    """
    name = models.CharField(max_length=128, help_text="e.g. Home AI, Sales, Support")
    phone_number = models.CharField(max_length=32, help_text="Display phone number (e.g. +91 84382 39448)")
    phone_number_id = models.CharField(max_length=64, unique=True, db_index=True, help_text="Meta Phone Number ID")
    business_account_id = models.CharField(max_length=64, blank=True, default='', help_text="Meta WABA ID")
    access_token = models.TextField(blank=True, default='', help_text="Custom Access Token for this number (optional)")
    is_default = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    automation_enabled = models.BooleanField(default=True, help_text="Enable or disable automated chatbot flows on this number")
    crm_branch = models.ForeignKey(
        'branches.Branch', on_delete=models.SET_NULL, null=True, blank=True, related_name='whatsapp_numbers',
        help_text="CRM branch for new WhatsApp leads on this number (leads are then auto-assigned to that branch's telecallers)",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-is_default', 'name']
        verbose_name = 'Business Account'
        verbose_name_plural = 'Business Accounts'

    def __str__(self):
        return f"{self.name} ({self.phone_number})"


class Conversation(models.Model):
    """
    Represents a WhatsApp chat conversation with a customer on a specific business number.
    """
    business_account = models.ForeignKey(
        BusinessAccount,
        on_delete=models.CASCADE,
        related_name='conversations',
        null=True,
        blank=True
    )
    customer_name = models.CharField(max_length=255, db_index=True)
    phone_number = models.CharField(
        max_length=32,
        db_index=True,
        help_text="E.164 formatted phone number (e.g., +919876543210)"
    )
    profile_image = models.ImageField(
        upload_to='images/avatars/',
        null=True,
        blank=True
    )
    last_message = models.TextField(blank=True, default='')
    last_message_time = models.DateTimeField(null=True, blank=True, db_index=True)
    unread_count = models.PositiveIntegerField(default=0)
    is_pinned = models.BooleanField(default=False, db_index=True)
    is_archived = models.BooleanField(default=False, db_index=True)
    is_online = models.BooleanField(default=False)
    last_seen = models.CharField(max_length=64, blank=True, default='online')

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True, db_index=True)

    class Meta:
        ordering = ['-is_pinned', '-last_message_time', '-updated_at']
        unique_together = [('business_account', 'phone_number')]
        verbose_name = 'Conversation'
        verbose_name_plural = 'Conversations'

    def __str__(self):
        account_name = self.business_account.name if self.business_account else "Default"
        return f"[{account_name}] {self.customer_name} ({self.phone_number})"

    def mark_as_read(self):
        """Reset unread count when opened by agent."""
        if self.unread_count > 0:
            self.unread_count = 0
            self.save(update_fields=['unread_count', 'updated_at'])

    @property
    def display_time(self):
        """Format the last_message_time for WhatsApp UI display."""
        if not self.last_message_time:
            return ""
        now = timezone.now()
        local_time = timezone.localtime(self.last_message_time)
        if local_time.date() == now.date():
            return local_time.strftime('%I:%M %p').lstrip('0')
        elif (now.date() - local_time.date()).days == 1:
            return "Yesterday"
        elif (now.date() - local_time.date()).days < 7:
            return local_time.strftime('%A')
        return local_time.strftime('%d/%m/%Y')


class Message(models.Model):
    """
    Represents an individual message in a WhatsApp conversation.
    """
    SENDER_CUSTOMER = 'customer'
    SENDER_AGENT = 'agent'
    SENDER_CHOICES = [
        (SENDER_CUSTOMER, 'Customer'),
        (SENDER_AGENT, 'Agent'),
    ]

    TYPE_TEXT = 'text'
    TYPE_IMAGE = 'image'
    TYPE_VIDEO = 'video'
    TYPE_AUDIO = 'audio'
    TYPE_DOCUMENT = 'document'
    MESSAGE_TYPE_CHOICES = [
        (TYPE_TEXT, 'Text'),
        (TYPE_IMAGE, 'Image'),
        (TYPE_VIDEO, 'Video'),
        (TYPE_AUDIO, 'Audio'),
        (TYPE_DOCUMENT, 'Document'),
    ]

    STATUS_SENT = 'sent'
    STATUS_DELIVERED = 'delivered'
    STATUS_READ = 'read'
    STATUS_FAILED = 'failed'
    STATUS_CHOICES = [
        (STATUS_SENT, 'Sent'),
        (STATUS_DELIVERED, 'Delivered'),
        (STATUS_READ, 'Read'),
        (STATUS_FAILED, 'Failed'),
    ]

    conversation = models.ForeignKey(
        Conversation,
        on_delete=models.CASCADE,
        related_name='messages'
    )
    sender = models.CharField(
        max_length=16,
        choices=SENDER_CHOICES,
        default=SENDER_AGENT
    )
    message_type = models.CharField(
        max_length=16,
        choices=MESSAGE_TYPE_CHOICES,
        default=TYPE_TEXT
    )
    message_text = models.TextField(blank=True, default='')
    media_file = models.FileField(
        upload_to='media/uploads/%Y/%m/%d/',
        null=True,
        blank=True
    )
    whatsapp_message_id = models.CharField(
        max_length=128,
        blank=True,
        default='',
        db_index=True
    )
    status = models.CharField(
        max_length=16,
        choices=STATUS_CHOICES,
        default=STATUS_SENT,
        db_index=True
    )
    timestamp = models.DateTimeField(default=timezone.now, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['timestamp', 'created_at']
        verbose_name = 'Message'
        verbose_name_plural = 'Messages'

    def __str__(self):
        return f"{self.sender.title()} to {self.conversation.customer_name}: {self.message_text[:30]}"

    @property
    def display_time(self):
        """Format timestamp for chat message bubble (e.g. 10:32 AM)."""
        local_time = timezone.localtime(self.timestamp)
        return local_time.strftime('%I:%M %p').lstrip('0')


class AutomationFlow(models.Model):
    """
    Represents an automation workflow / chatbot graph for WhatsApp.
    Supports draft/published versioning so admins can build without breaking live bots.
    """
    STATUS_DRAFT = 'draft'
    STATUS_PUBLISHED = 'published'
    STATUS_CHOICES = [
        (STATUS_DRAFT, 'Draft'),
        (STATUS_PUBLISHED, 'Published'),
    ]

    TRIGGER_FIRST_MESSAGE = 'first_incoming_message'
    TRIGGER_KEYWORD = 'keyword'
    TRIGGER_BUTTON = 'button_reply'
    TRIGGER_LIST = 'list_reply'
    TRIGGER_WEBHOOK = 'webhook_event'
    TRIGGER_ALWAYS_ON = 'always_on'
    TRIGGER_CHOICES = [
        (TRIGGER_FIRST_MESSAGE, 'First Incoming Message'),
        (TRIGGER_KEYWORD, 'Keyword Match'),
        (TRIGGER_BUTTON, 'Button Reply'),
        (TRIGGER_LIST, 'List Reply'),
        (TRIGGER_WEBHOOK, 'Webhook Event'),
        (TRIGGER_ALWAYS_ON, 'First Message / Always On'),
    ]

    business_account = models.ForeignKey(
        BusinessAccount,
        on_delete=models.CASCADE,
        related_name='automation_flows',
        null=True,
        blank=True,
        help_text="Leave empty for global fallback flow"
    )
    name = models.CharField(max_length=128)
    slug = models.SlugField(max_length=128, blank=True, default='')
    version = models.PositiveIntegerField(default=1)
    status = models.CharField(max_length=16, choices=STATUS_CHOICES, default=STATUS_PUBLISHED)
    trigger_type = models.CharField(max_length=32, choices=TRIGGER_CHOICES, default=TRIGGER_FIRST_MESSAGE)
    trigger_keywords = models.TextField(
        default='hi, hello, hey, start, menu, info, admission, course',
        help_text="Normalized keywords that trigger this flow"
    )
    flow_data = models.JSONField(
        default=dict,
        help_text="JSON representation of nodes, connections, and metadata for Flow Builder"
    )
    is_active = models.BooleanField(default=True)
    published_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-is_active', '-updated_at']
        verbose_name = 'Automation Flow'
        verbose_name_plural = 'Automation Flows'

    def __str__(self):
        return f"{self.name} (v{self.version} - {self.status.title()})"


class UserFlowSession(models.Model):
    """
    Tracks a customer's active progress through a multi-step AutomationFlow.
    Includes state machine and human handover flags.
    """
    STATUS_ACTIVE = 'active'
    STATUS_PAUSED = 'paused'
    STATUS_HANDED_OVER = 'handed_over'
    STATUS_COMPLETED = 'completed'
    STATUS_EXPIRED = 'expired'
    STATUS_CHOICES = [
        (STATUS_ACTIVE, 'Active (Bot Replying)'),
        (STATUS_PAUSED, 'Paused'),
        (STATUS_HANDED_OVER, 'Handed Over to Human'),
        (STATUS_COMPLETED, 'Completed'),
        (STATUS_EXPIRED, 'Expired'),
    ]

    conversation = models.ForeignKey(
        Conversation,
        on_delete=models.CASCADE,
        related_name='flow_sessions'
    )
    flow = models.ForeignKey(
        AutomationFlow,
        on_delete=models.CASCADE,
        related_name='sessions'
    )
    flow_version = models.PositiveIntegerField(default=1)
    current_node_id = models.CharField(max_length=64, default='trigger_1')
    waiting_for_input = models.BooleanField(
        default=False,
        help_text="True when currently paused waiting for customer input on a Question node"
    )
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default=STATUS_ACTIVE,
        db_index=True
    )
    collected_data = models.JSONField(
        default=dict,
        help_text="Stores collected student choices, selections, inputs"
    )
    started_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    paused_at = models.DateTimeField(null=True, blank=True)
    handed_over_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    expires_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-updated_at']
        verbose_name = 'User Flow Session'
        verbose_name_plural = 'User Flow Sessions'

    def __str__(self):
        return f"Session for {self.conversation.phone_number} on {self.flow.name} v{self.flow_version} [{self.status}]"


class Course(models.Model):
    """
    Available training courses for the automated course list and brochure delivery.
    """
    name = models.CharField(max_length=128, blank=True, default='')
    title = models.CharField(max_length=128)
    code = models.CharField(max_length=32, unique=True)
    description = models.TextField(blank=True, default='')
    duration = models.CharField(max_length=64, default='3 Months')
    brochure_file = models.FileField(upload_to='brochures/', null=True, blank=True)
    brochure_url = models.URLField(blank=True, default='')
    display_order = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['display_order', 'title']

    def __str__(self):
        return self.name or self.title

    def save(self, *args, **kwargs):
        if not self.name and self.title:
            self.name = self.title
        elif not self.title and self.name:
            self.title = self.name
        super().save(*args, **kwargs)

    def get_brochure_url(self):
        if self.brochure_url:
            return self.brochure_url
        if self.brochure_file:
            try:
                return self.brochure_file.url
            except Exception:
                return ''
        return ''


class Branch(models.Model):
    """
    Physical institute branches for location sharing and visits.
    """
    name = models.CharField(max_length=128)
    address = models.TextField()
    latitude = models.FloatField(default=13.0827)
    longitude = models.FloatField(default=80.2707)
    google_maps_url = models.URLField(blank=True, default='')
    phone = models.CharField(max_length=32, blank=True, default='')
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ['name']
        verbose_name = 'Branch'
        verbose_name_plural = 'Branches'

    def __str__(self):
        return self.name


class AutomationExecution(models.Model):
    """
    Detailed audit and debugging execution log for WhatsApp automation flows.
    """
    session = models.ForeignKey(
        UserFlowSession,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='execution_logs'
    )
    flow = models.ForeignKey(
        AutomationFlow,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='execution_logs'
    )
    flow_version = models.PositiveIntegerField(default=1)
    node_id = models.CharField(max_length=64, blank=True, default='')
    event_type = models.CharField(max_length=64, db_index=True)
    input_data = models.JSONField(default=dict, blank=True)
    output_data = models.JSONField(default=dict, blank=True)
    error = models.TextField(blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Automation Execution Log'
        verbose_name_plural = 'Automation Execution Logs'

    def __str__(self):
        return f"[{self.event_type}] node={self.node_id} (Session {self.session_id})"


class WhatsAppSender(models.Model):
    """
    Authorized WhatsApp outbound sender channel.
    Connects telecallers or branches to registered Meta WABA phone number IDs.
    """
    name = models.CharField(max_length=128, help_text="e.g. Priyadharshini - Outbound, Bangalore Sales Line")
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='whatsapp_senders',
        help_text="Optional assigned telecaller / staff member"
    )
    business_account = models.ForeignKey(
        BusinessAccount,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='senders',
        help_text="Linked Meta Business Account channel"
    )
    provider = models.CharField(max_length=32, default='meta_cloud', help_text="Provider platform e.g. meta_cloud")
    phone_number_id = models.CharField(max_length=64, db_index=True, help_text="Meta Phone Number ID")
    display_phone_number = models.CharField(max_length=32, help_text="E.164 or formatted display number e.g. +91 98765 43210")
    is_active = models.BooleanField(default=True, db_index=True)
    is_verified = models.BooleanField(default=True)
    quality_rating = models.CharField(max_length=32, default='GREEN', help_text="Meta Quality Rating (GREEN, YELLOW, RED)")
    daily_limit = models.PositiveIntegerField(default=1000, help_text="Provider tier messaging limit per 24 hours")
    allowed_branches = models.ManyToManyField(
        'branches.Branch',
        blank=True,
        related_name='whatsapp_senders',
        help_text="Branches permitted to dispatch campaigns through this sender (leave empty for all)"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['name']
        verbose_name = 'WhatsApp Sender'
        verbose_name_plural = 'WhatsApp Senders'

    def __str__(self):
        caller_str = f" - {self.user.get_full_name() or self.user.username}" if self.user else ""
        return f"{self.name} ({self.display_phone_number}){caller_str}"

    def can_be_used_by(self, user):
        """Verify role and branch authorization for this sender."""
        if not self.is_active:
            return False
        if getattr(user, 'is_admin_user', False) or user.is_superuser or user.role == 'ADMIN':
            return True
        allowed = list(self.allowed_branches.all())
        if allowed and user.branch and user.branch not in allowed:
            return False
        if self.user and self.user_id != user.id:
            if user.role not in ['ADMIN', 'SALES_HEAD']:
                return False
        return True


class WhatsAppTemplate(models.Model):
    """
    Pre-approved Meta WhatsApp Cloud API Message Template or CRM standard template.
    """
    CATEGORY_MARKETING = 'MARKETING'
    CATEGORY_UTILITY = 'UTILITY'
    CATEGORY_AUTHENTICATION = 'AUTHENTICATION'
    CATEGORY_CHOICES = [
        (CATEGORY_MARKETING, 'Marketing'),
        (CATEGORY_UTILITY, 'Utility'),
        (CATEGORY_AUTHENTICATION, 'Authentication'),
    ]

    STATUS_APPROVED = 'APPROVED'
    STATUS_PENDING = 'PENDING'
    STATUS_REJECTED = 'REJECTED'
    STATUS_CHOICES = [
        (STATUS_APPROVED, 'Approved'),
        (STATUS_PENDING, 'Pending Review'),
        (STATUS_REJECTED, 'Rejected'),
    ]

    HEADER_NONE = 'NONE'
    HEADER_TEXT = 'TEXT'
    HEADER_IMAGE = 'IMAGE'
    HEADER_DOCUMENT = 'DOCUMENT'
    HEADER_VIDEO = 'VIDEO'
    HEADER_CHOICES = [
        (HEADER_NONE, 'None'),
        (HEADER_TEXT, 'Text'),
        (HEADER_IMAGE, 'Image'),
        (HEADER_DOCUMENT, 'Document (PDF)'),
        (HEADER_VIDEO, 'Video'),
    ]

    name = models.CharField(max_length=128, unique=True, help_text="Meta Template Identifier (snake_case)")
    display_title = models.CharField(max_length=150, blank=True, default='')
    language = models.CharField(max_length=16, default='en_US', help_text="e.g. en_US, en, hi")
    category = models.CharField(max_length=32, choices=CATEGORY_CHOICES, default=CATEGORY_MARKETING)
    status = models.CharField(max_length=32, choices=STATUS_CHOICES, default=STATUS_APPROVED, db_index=True)
    header_type = models.CharField(max_length=16, choices=HEADER_CHOICES, default=HEADER_NONE)
    header_text = models.CharField(max_length=255, blank=True, default='')
    body_text = models.TextField(help_text="Body content with positional {{1}}, {{2}} or named {{lead_name}} variables")
    footer_text = models.CharField(max_length=128, blank=True, default='')
    buttons = models.JSONField(default=list, blank=True, help_text="Quick reply or call-to-action buttons")
    parameter_mapping = models.JSONField(
        default=list,
        blank=True,
        help_text="Ordered list of model field keys e.g. ['lead_name', 'course', 'branch'] to map to {{1}}, {{2}}..."
    )
    is_active = models.BooleanField(default=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['name']
        verbose_name = 'WhatsApp Template'
        verbose_name_plural = 'WhatsApp Templates'

    def __str__(self):
        title = self.display_title or self.name
        return f"{title} [{self.language}] ({self.status})"


class WhatsAppCampaign(models.Model):
    """
    Bulk WhatsApp Messaging Campaign instance with audience resolution, rate limiting, and delivery telemetry.
    """
    MODE_ASSIGNED_TELECALLER = 'assigned_telecaller'
    MODE_SELECTED_SENDER = 'selected_sender'
    SENDER_MODE_CHOICES = [
        (MODE_ASSIGNED_TELECALLER, "Assigned Telecaller's Connected Number"),
        (MODE_SELECTED_SENDER, "One Selected Telecaller / Business Number"),
    ]

    STATUS_DRAFT = 'draft'
    STATUS_SCHEDULED = 'scheduled'
    STATUS_RUNNING = 'running'
    STATUS_PAUSED = 'paused'
    STATUS_COMPLETED = 'completed'
    STATUS_CANCELLED = 'cancelled'
    STATUS_FAILED = 'failed'
    STATUS_CHOICES = [
        (STATUS_DRAFT, 'Draft'),
        (STATUS_SCHEDULED, 'Scheduled'),
        (STATUS_RUNNING, 'Running'),
        (STATUS_PAUSED, 'Paused'),
        (STATUS_COMPLETED, 'Completed'),
        (STATUS_CANCELLED, 'Cancelled'),
        (STATUS_FAILED, 'Failed'),
    ]

    MESSAGE_TYPE_TEMPLATE = 'template'
    MESSAGE_TYPE_TEXT = 'text'
    MESSAGE_TYPE_CHOICES = [
        (MESSAGE_TYPE_TEMPLATE, 'Approved Template'),
        (MESSAGE_TYPE_TEXT, 'Plain Text (24h Window Compliant)'),
    ]

    name = models.CharField(max_length=255)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='whatsapp_campaigns'
    )
    branch = models.ForeignKey(
        'branches.Branch',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='whatsapp_campaigns',
        help_text="Optional target branch"
    )
    sender_mode = models.CharField(
        max_length=32,
        choices=SENDER_MODE_CHOICES,
        default=MODE_SELECTED_SENDER
    )
    selected_sender = models.ForeignKey(
        WhatsAppSender,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='campaigns'
    )
    template = models.ForeignKey(
        WhatsAppTemplate,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='campaigns'
    )
    message_type = models.CharField(
        max_length=16,
        choices=MESSAGE_TYPE_CHOICES,
        default=MESSAGE_TYPE_TEMPLATE
    )
    custom_message = models.TextField(blank=True, default='')
    media_url = models.URLField(blank=True, default='')
    status = models.CharField(
        max_length=32,
        choices=STATUS_CHOICES,
        default=STATUS_DRAFT,
        db_index=True
    )
    filter_criteria = models.JSONField(
        default=dict,
        blank=True,
        help_text="Server-side query parameters used to resolve this recipient cohort"
    )
    scheduled_at = models.DateTimeField(null=True, blank=True)
    batch_size = models.PositiveIntegerField(default=50)
    rate_limit_per_minute = models.PositiveIntegerField(default=60)

    # Telemetry Counters
    total_recipients = models.PositiveIntegerField(default=0)
    eligible_count = models.PositiveIntegerField(default=0)
    skipped_count = models.PositiveIntegerField(default=0)
    queued_count = models.PositiveIntegerField(default=0)
    submitted_count = models.PositiveIntegerField(default=0)
    sent_count = models.PositiveIntegerField(default=0)
    delivered_count = models.PositiveIntegerField(default=0)
    read_count = models.PositiveIntegerField(default=0)
    failed_count = models.PositiveIntegerField(default=0)

    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'WhatsApp Campaign'
        verbose_name_plural = 'WhatsApp Campaigns'

    def __str__(self):
        return f"{self.name} [{self.get_status_display()}] ({self.total_recipients} leads)"

    @property
    def progress_percentage(self):
        if not self.eligible_count:
            return 0
        processed = self.submitted_count + self.failed_count
        return min(100, int((processed / self.eligible_count) * 100))

    def refresh_counters_from_db(self):
        """Atomically recalibrates telemetry counters from individual recipient states."""
        qs = self.recipients.all()
        self.total_recipients = qs.count()
        self.eligible_count = qs.exclude(status='skipped').count()
        self.skipped_count = qs.filter(status='skipped').count()
        self.queued_count = qs.filter(status='queued').count()
        self.submitted_count = qs.filter(status__in=['submitted', 'sent', 'delivered', 'read']).count()
        self.sent_count = qs.filter(status__in=['sent', 'delivered', 'read']).count()
        self.delivered_count = qs.filter(status__in=['delivered', 'read']).count()
        self.read_count = qs.filter(status='read').count()
        self.failed_count = qs.filter(status='failed').count()
        self.save(update_fields=[
            'total_recipients', 'eligible_count', 'skipped_count', 'queued_count',
            'submitted_count', 'sent_count', 'delivered_count', 'read_count',
            'failed_count', 'updated_at'
        ])


class WhatsAppCampaignRecipient(models.Model):
    """
    Individual recipient entry in a WhatsApp bulk campaign.
    Maintains idempotency, personalized message snapshots, provider IDs, and status transitions.
    """
    STATUS_ELIGIBLE = 'eligible'
    STATUS_SKIPPED = 'skipped'
    STATUS_QUEUED = 'queued'
    STATUS_SUBMITTED = 'submitted'
    STATUS_SENT = 'sent'
    STATUS_DELIVERED = 'delivered'
    STATUS_READ = 'read'
    STATUS_FAILED = 'failed'
    STATUS_CANCELLED = 'cancelled'

    STATUS_CHOICES = [
        (STATUS_ELIGIBLE, 'Eligible'),
        (STATUS_SKIPPED, 'Skipped'),
        (STATUS_QUEUED, 'Queued'),
        (STATUS_SUBMITTED, 'Submitted'),
        (STATUS_SENT, 'Sent'),
        (STATUS_DELIVERED, 'Delivered'),
        (STATUS_READ, 'Read'),
        (STATUS_FAILED, 'Failed'),
        (STATUS_CANCELLED, 'Cancelled'),
    ]

    campaign = models.ForeignKey(
        WhatsAppCampaign,
        on_delete=models.CASCADE,
        related_name='recipients'
    )
    lead = models.ForeignKey(
        'leads.Lead',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='whatsapp_campaign_entries'
    )
    phone_number = models.CharField(max_length=32, db_index=True)
    lead_name = models.CharField(max_length=255, blank=True, default='')
    resolved_sender = models.ForeignKey(
        WhatsAppSender,
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )
    sender_phone_number = models.CharField(max_length=32, blank=True, default='')
    status = models.CharField(
        max_length=32,
        choices=STATUS_CHOICES,
        default=STATUS_ELIGIBLE,
        db_index=True
    )
    skip_reason = models.CharField(max_length=255, blank=True, default='')
    personalized_message = models.TextField(blank=True, default='')
    template_parameters = models.JSONField(default=list, blank=True)
    provider_message_id = models.CharField(max_length=128, blank=True, default='', db_index=True)
    attempt_count = models.PositiveIntegerField(default=0)
    max_attempts = models.PositiveIntegerField(default=3)
    error_code = models.CharField(max_length=64, blank=True, default='')
    error_message = models.TextField(blank=True, default='')

    queued_at = models.DateTimeField(null=True, blank=True)
    submitted_at = models.DateTimeField(null=True, blank=True)
    sent_at = models.DateTimeField(null=True, blank=True)
    delivered_at = models.DateTimeField(null=True, blank=True)
    read_at = models.DateTimeField(null=True, blank=True)
    failed_at = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['id']
        unique_together = [('campaign', 'lead')]
        indexes = [
            models.Index(fields=['campaign', 'status']),
            models.Index(fields=['provider_message_id']),
        ]
        verbose_name = 'Campaign Recipient'
        verbose_name_plural = 'Campaign Recipients'

    def __str__(self):
        return f"Campaign #{self.campaign_id} -> {self.lead_name} ({self.phone_number}) [{self.status}]"




from django.db import models
from django.conf import settings


class FacebookAccount(models.Model):
    """
    Authorized Facebook User / Business connection.
    Supports multiple connected accounts simultaneously without overwriting.
    """
    account_name = models.CharField(max_length=255)
    meta_user_id = models.CharField(max_length=100, blank=True, default='', db_index=True)
    access_token = models.TextField(help_text="Encrypted or secure user/system access token")
    token_expires_at = models.DateTimeField(null=True, blank=True)
    status = models.CharField(max_length=50, default='CONNECTED', db_index=True)
    connected_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='facebook_accounts'
    )
    last_verified_at = models.DateTimeField(null=True, blank=True)
    last_error = models.TextField(blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.account_name} ({self.meta_user_id or 'No ID'}) [{self.status}]"


class FacebookPage(models.Model):
    """
    Facebook Page connection associated with an authorized FacebookAccount.
    Allows independent synchronization, webhook routing, branch assignment, and disconnection.
    """
    account = models.ForeignKey(
        FacebookAccount,
        on_delete=models.CASCADE,
        related_name='pages'
    )
    page_id = models.CharField(max_length=64, db_index=True)
    page_name = models.CharField(max_length=255)
    branch = models.ForeignKey(
        'branches.Branch',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='facebook_pages',
        help_text="Default CRM branch for incoming leads from this Facebook Page"
    )
    page_access_token = models.TextField(help_text="Page-level access token")
    webhook_subscribed = models.BooleanField(default=False)
    status = models.CharField(max_length=50, default='CONNECTED', db_index=True)
    last_sync_at = models.DateTimeField(null=True, blank=True)
    last_sync_status = models.CharField(max_length=50, default='Idle')
    last_error = models.TextField(blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['page_name']
        unique_together = ('account', 'page_id')

    def __str__(self):
        branch_name = self.branch.name if self.branch else 'No Branch'
        return f"{self.page_name} (ID: {self.page_id}) [{branch_name}]"


class FacebookLead(models.Model):
    """One lead that came from a Facebook Lead Ad form."""

    leadgen_id = models.CharField(max_length=64, unique=True)  # Facebook's lead ID (prevents duplicates)
    full_name = models.CharField(max_length=255, blank=True)
    phone = models.CharField(max_length=50, blank=True)
    email = models.CharField(max_length=255, blank=True)
    city = models.CharField(max_length=120, blank=True)

    page_id = models.CharField(max_length=64, blank=True)
    form_id = models.CharField(max_length=64, blank=True)
    form_name = models.CharField(max_length=255, blank=True)
    ad_id = models.CharField(max_length=64, blank=True)
    ad_name = models.CharField(max_length=255, blank=True)
    campaign_name = models.CharField(max_length=255, blank=True)

    all_answers = models.JSONField(default=dict, blank=True)  # every question/answer from the form
    created_on_facebook = models.DateTimeField(null=True, blank=True)
    received_at = models.DateTimeField(auto_now_add=True)

    # Connections
    fb_page = models.ForeignKey(
        FacebookPage,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='leads',
        help_text="Source Facebook Page connection"
    )
    account = models.ForeignKey(
        FacebookAccount,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='leads',
        help_text="Parent Facebook Account"
    )

    # CRM link: every Facebook lead becomes (or updates) a CRM Lead with source "Facebook"
    lead = models.ForeignKey(
        "leads.Lead", on_delete=models.SET_NULL, null=True, blank=True, related_name="facebook_entries",
        help_text="CRM lead created or updated from this Facebook lead",
    )
    crm_result = models.CharField(
        max_length=20, blank=True, default="",
        help_text="new = created a CRM lead · existing = added to an existing lead · error = see crm_error",
    )
    crm_error = models.CharField(max_length=255, blank=True, default="")

    class Meta:
        ordering = ["-created_on_facebook", "-received_at"]

    def __str__(self):
        return f"{self.full_name or 'Lead'} ({self.phone or self.email})"

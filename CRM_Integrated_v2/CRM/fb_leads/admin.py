from django.contrib import admin

from .models import FacebookLead


@admin.register(FacebookLead)
class FacebookLeadAdmin(admin.ModelAdmin):
    list_display = ("full_name", "phone", "email", "form_name", "ad_name", "created_on_facebook", "lead", "crm_result")
    raw_id_fields = ("lead",)
    search_fields = ("full_name", "phone", "email", "form_name", "ad_name", "campaign_name")
    list_filter = ("crm_result", "form_name", "campaign_name")

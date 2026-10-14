from django.urls import path

from . import views

app_name = "fb_leads"

urlpatterns = [
    path("webhook/", views.webhook, name="facebook_leads_webhook"),
    path("api/recent/", views.api_recent_leads, name="facebook_leads_recent_api"),
    path("", views.lead_list, name="facebook_leads"),
    path("sync/", views.sync_leads, name="facebook_leads_sync"),
    path("accounts/", views.fb_accounts, name="fb_accounts"),
    path("accounts/connect/", views.fb_account_connect, name="fb_account_connect"),
    path("accounts/<int:account_id>/disconnect/", views.fb_account_disconnect, name="fb_account_disconnect"),
    path("pages/<int:page_id>/branch/", views.fb_page_update_branch, name="fb_page_update_branch"),
    path("pages/<int:page_id>/toggle-webhook/", views.fb_page_toggle_webhook, name="fb_page_toggle_webhook"),
    path("pages/<int:page_id>/sync/", views.fb_page_sync, name="fb_page_sync"),
]

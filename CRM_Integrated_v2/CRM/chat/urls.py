from django.urls import path
from . import views, views_campaign

urlpatterns = [
    # Bulk WhatsApp Campaigns
    path('campaigns/', views_campaign.campaigns_list_view, name='whatsapp_campaigns_list'),
    path('campaigns/create/', views_campaign.campaign_create_wizard_view, name='whatsapp_campaign_create'),
    path('campaigns/<int:pk>/', views_campaign.campaign_detail_view, name='whatsapp_campaign_detail'),
    path('campaigns/<int:pk>/export/', views_campaign.campaign_export_csv_view, name='whatsapp_campaign_export_csv'),
    path('campaigns/api/<int:pk>/control/', views_campaign.api_campaign_control, name='api_campaign_control'),
    path('campaigns/api/<int:pk>/control-action/', views_campaign.api_campaign_control, name='whatsapp_campaign_api_control'),
    path('campaigns/api/<int:pk>/progress/', views_campaign.api_campaign_progress, name='api_campaign_progress'),
    path('campaigns/api/<int:pk>/progress-status/', views_campaign.api_campaign_progress, name='whatsapp_campaign_api_progress'),
    path('campaigns/api/leads/<int:pk>/consent/', views_campaign.api_toggle_lead_whatsapp_consent, name='api_toggle_lead_whatsapp_consent'),
    path('whatsapp/campaigns/', views_campaign.campaigns_list_view, name='whatsapp_campaigns_list_alt'),
    path('whatsapp/campaigns/create/', views_campaign.campaign_create_wizard_view, name='whatsapp_campaign_create_alt'),
    # Inbox UI
    path('whatsapp/', views.InboxView.as_view(), name='inbox'),
    path('whatsapp/', views.InboxView.as_view(), name='whatsapp_inbox'),

    # Automation Dashboard & Flow Builder UI
    path('automations/', views.AutomationListView.as_view(), name='automation-list'),
    path('automation/', views.FlowBuilderView.as_view(), name='flow-builder'),
    path('automation/<int:pk>/', views.FlowBuilderView.as_view(), name='flow-builder-detail'),

    # REST APIs
    path('api/business-accounts/', views.BusinessAccountListAPI.as_view(), name='api-business-accounts'),
    path('api/business-accounts/<int:pk>/', views.BusinessAccountDetailAPI.as_view(), name='api-business-account-detail'),
    path('api/flows/', views.AutomationFlowListAPI.as_view(), name='api-flows'),
    path('api/flows/<int:pk>/', views.AutomationFlowDetailAPI.as_view(), name='api-flow-detail'),
    path('api/flows/<int:pk>/publish/', views.AutomationFlowPublishAPI.as_view(), name='api-flow-publish'),
    path('api/flows/<int:pk>/create-draft/', views.AutomationFlowCreateDraftAPI.as_view(), name='api-flow-create-draft'),
    path('api/flows/<int:pk>/validate/', views.ValidateFlowAPI.as_view(), name='api-flow-validate'),
    path('api/flows/validate/', views.ValidateFlowAPI.as_view(), name='api-flow-validate-direct'),
    path('api/flows/generate-from-prompt/', views.AIFlowAssistantAPI.as_view(), name='api-flow-ai-generate'),
    path('api/conversations/', views.ConversationListAPI.as_view(), name='api-conversations'),
    path('api/conversations/<int:pk>/messages/', views.ConversationMessagesAPI.as_view(), name='api-conversation-messages'),
    path('api/conversations/<int:pk>/resume-automation/', views.ResumeAutomationAPI.as_view(), name='api-resume-automation'),
    path('api/messages/send/', views.SendMessageAPI.as_view(), name='api-message-send'),
    path('api/search/', views.SearchAPI.as_view(), name='api-search'),
    path('api/crm/options/', views.CRMOptionsAPI.as_view(), name='api-crm-options'),
    path('api/leads/<int:lead_id>/send-whatsapp/', views.api_telecaller_send_whatsapp, name='api_telecaller_send_whatsapp'),
    path('api/leads/<int:lead_id>/voice-capability/', views.api_whatsapp_voice_capability, name='api_whatsapp_voice_capability'),

    # Meta WhatsApp Webhooks
    path('webhook/whatsapp/', views.WhatsAppWebhookView.as_view(), name='whatsapp-webhook'),
]

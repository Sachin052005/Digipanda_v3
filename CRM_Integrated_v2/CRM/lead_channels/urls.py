from django.urls import path
from . import views
from fb_leads.views import webhook as fb_webhook

urlpatterns = [
    path('admin/channels/', views.admin_channels_list, name='admin_channels_list'),
    path('admin/channels/<int:pk>/edit/', views.admin_channel_edit, name='admin_channel_edit'),
    path('admin/channels/<int:pk>/delete/', views.admin_channel_delete, name='admin_channel_delete'),
    path('admin/channels/<int:pk>/toggle/', views.admin_channel_toggle_status, name='admin_channel_toggle_status'),
    path('admin/configuration/', views.admin_configuration_view, name='admin_configuration'),
    path('admin/configuration/add/', views.admin_configuration_add, name='admin_configuration_add'),
    path('admin/configuration/<int:pk>/manage/', views.admin_configuration_manage, name='admin_configuration_manage'),
    path('admin/configuration/<int:pk>/sync/', views.admin_configuration_sync, name='admin_configuration_sync'),
    path('admin/configuration/<int:pk>/disconnect/', views.admin_configuration_disconnect, name='admin_configuration_disconnect'),
    # Meta / Facebook Connection Dedicated Management & Webhooks
    path('admin/configuration/<int:pk>/meta/', views.admin_meta_manage_view, name='admin_meta_manage'),
    path('admin/configuration/<int:pk>/meta/test/', views.admin_meta_test_step, name='admin_meta_test_step'),
    path('admin/configuration/<int:pk>/meta/save/', views.admin_meta_save_config, name='admin_meta_save_config'),
    path('admin/configuration/<int:pk>/meta/sync/', views.admin_meta_sync_now, name='admin_meta_sync_now'),
    path('admin/configuration/<int:pk>/meta/disconnect/', views.admin_meta_disconnect, name='admin_meta_disconnect'),
    # Real Facebook Lead Ads webhook (verify token + signature check + Graph API fetch) from fb_leads.
    # The old unsigned endpoint saved fake data, so this URL now points to the secure one.
    path('api/webhooks/meta/leads/', fb_webhook, name='meta_webhook_endpoint'),
]


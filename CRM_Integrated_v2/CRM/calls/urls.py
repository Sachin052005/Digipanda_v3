from django.urls import path
from . import views
from . import api_views

urlpatterns = [
    # Global atomic call completion & lock endpoints (Section 48, 49)
    path('calls/start/', views.start_call_record, name='start_call_record'),
    path('calls/lock-check/', views.check_call_lock, name='check_call_lock'),
    path('calls/device-status/', views.check_device_status, name='check_device_status'),
    path('calls/<int:pk>/end/', views.end_call_record, name='end_call_record'),
    path('calls/complete/', views.complete_call_record, name='complete_call_record'),

    # Admin routes
    path('admin/calls/', views.admin_calls_list, name='admin_calls_list'),
    path('admin/calls/create/', views.admin_call_create, name='admin_call_create'),
    path('admin/calls/<int:pk>/', views.admin_call_detail, name='admin_call_detail'),

    # Manager routes
    path('manager/calls/', views.manager_calls_list, name='manager_calls_list'),

    # Telecaller routes
    path('telecaller/calls/', views.telecaller_calls_list, name='telecaller_calls_list'),

    # Missed Google Ads calls waiting for a call back (all roles, scoped)
    path('calls/missed/', views.missed_calls_list, name='missed_calls_list'),
    path('calls/lead/<int:lead_id>/called-back/', views.mark_lead_called_back, name='mark_lead_called_back'),

    # CRM Call Sync Android app (paths must stay as the app expects them)
    path('api/auth/token/', api_views.AppLoginView.as_view(), name='app_login'),
    path('api/calls/ingest/', api_views.CallIngestView.as_view(), name='app_calls_ingest'),
    path('api/call-recordings/upload/', api_views.RecordingUploadView.as_view(), name='app_recording_upload'),
    path('api/calls/pending-dial/', api_views.PendingCallDialView.as_view(), name='app_pending_dial'),
    path('api/calls/report-state/', api_views.CallStateReportView.as_view(), name='api_call_report_state'),
]


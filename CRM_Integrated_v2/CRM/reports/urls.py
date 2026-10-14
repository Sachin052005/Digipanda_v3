from django.urls import path
from . import views

urlpatterns = [
    path('admin/dashboard/', views.admin_dashboard, name='admin_dashboard'),
    path('admin/reports/', views.admin_reports, name='admin_reports'),
    path('manager/reports/', views.manager_reports, name='manager_reports'),
    path('reports/api/data/', views.reports_api_data, name='reports_api_data'),
    path('reports/api/sync-sheets/', views.reports_api_sync_sheets, name='reports_api_sync_sheets'),
    path('reports/telecaller-rnr/', views.telecaller_rnr_report, name='telecaller_rnr_report'),
    path('reports/api/management-charts/', views.management_charts_api, name='management_charts_api'),
    path('admin/api/trigger-sla-escalation/', views.trigger_lead_sla_escalation_api, name='admin_trigger_sla_escalation'),
]

from django.urls import path
from . import views, api_google_sheets, views_enrollment, views_bulk, views_accountant, views_walkin

urlpatterns = [
    # Admin Lead routes
    path('admin/leads/', views.admin_leads_list, name='admin_leads_list'),
    path('admin/leads/create/', views.admin_lead_create, name='admin_lead_create'),
    path('admin/leads/<int:pk>/', views.admin_lead_detail, name='admin_lead_detail'),
    path('admin/leads/<int:pk>/edit/', views.admin_lead_edit, name='admin_lead_edit'),
    path('admin/leads/<int:pk>/delete/', views.admin_lead_delete, name='admin_lead_delete'),
    path('admin/leads/import/', views.admin_leads_import, name='admin_leads_import'),
    path('admin/leads/<int:pk>/status/', views.admin_lead_update_status, name='admin_lead_update_status'),
    path('admin/duplicate-leads/', views.admin_duplicate_leads_view, name='admin_duplicate_leads'),
    path('admin/duplicate-leads/keep-single/', views.admin_duplicate_leads_keep_single, name='admin_duplicate_leads_keep_single'),
    path('admin/duplicate-leads/export/', views.admin_duplicate_leads_export, name='admin_duplicate_leads_export'),
    path('admin/duplicate-leads/<int:rec_id>/payload/', views.admin_duplicate_lead_payload, name='admin_duplicate_lead_payload'),
    path('admin/duplicate-leads/<int:rec_id>/promote/', views.admin_duplicate_lead_promote, name='admin_duplicate_lead_promote'),
    path('admin/leads/new/', views.admin_new_leads, name='admin_new_leads'),
    path('admin/leads/interested/', views.admin_interested_leads, name='admin_interested_leads'),
    path('admin/leads/demo-scheduled/', views.admin_demo_scheduled_leads, name='admin_demo_scheduled_leads'),
    path('admin/leads/converted/', views.admin_converted_leads, name='admin_converted_leads'),
    path('admin/leads/lost/', views.admin_lost_leads, name='admin_lost_leads'),
    path('admin/leads/later/', views.admin_later_leads, name='admin_later_leads'),
    path('admin/leads/discussion/', views.admin_discussion_leads, name='admin_discussion_leads'),

    path('admin/leads/<int:pk>/duplicate-info/', views.admin_lead_duplicate_info, name='admin_lead_duplicate_info'),
    path('admin/leads/<int:pk>/notify-counselor/', views.admin_lead_notify_duplicate_counselor, name='admin_lead_notify_duplicate_counselor'),
    path('admin/leads/retry-pending/', views.admin_retry_pending_assignments, name='admin_retry_pending_assignments'),
    path('admin/settings/lead-setup/', views.admin_lead_setup, name='admin_lead_setup'),
    path('admin/settings/pipeline-statuses/', views.admin_pipeline_statuses_list, name='admin_pipeline_statuses'),
    path('admin/settings/pipeline-statuses/<int:pk>/edit/', views.admin_pipeline_status_edit, name='admin_pipeline_status_edit'),
    path('admin/settings/pipeline-statuses/<int:pk>/toggle/', views.admin_pipeline_status_toggle, name='admin_pipeline_status_toggle'),
    path('admin/settings/pipeline-statuses/<int:pk>/delete/', views.admin_pipeline_status_delete, name='admin_pipeline_status_delete'),

    # Admin Offline Leads & Google Sheets / Google Form
    path('admin/offline-leads/', views.admin_offline_leads_list, name='admin_offline_leads'),
    path('admin/offline-leads/list/', views.admin_offline_leads_list, name='admin_offline_leads_list'),
    path('admin/offline-leads/google-form/connect/', views.admin_google_form_connect, name='admin_google_form_connect'),
    path('admin/offline-leads/google-form/disconnect/', views.admin_google_form_disconnect, name='admin_google_form_disconnect'),
    path('admin/offline-leads/google-form/submit-lead/', views.admin_google_form_submit_lead, name='admin_google_form_submit_lead'),
    path('admin/offline-leads/oauth/connect/', views.admin_google_oauth_connect, name='admin_google_oauth_connect'),
    path('admin/offline-leads/connect/', views.admin_google_sheet_connect, name='admin_google_sheet_connect'),
    path('admin/offline-leads/disconnect/', views.admin_google_sheet_disconnect, name='admin_offline_leads_disconnect'),
    path('admin/offline-leads/google-sheet/connect/', views.admin_google_sheet_connect, name='admin_google_sheet_connect_direct'),
    path('admin/offline-leads/google-sheet/<int:connection_id>/disconnect/', views.admin_google_sheet_disconnect, name='admin_google_sheet_disconnect'),
    path('admin/offline-leads/map/<int:connection_id>/', views.admin_google_sheet_save_mapping, name='admin_google_sheet_save_mapping'),
    path('admin/offline-leads/sync/<str:connection_id>/', views.admin_google_sheet_sync_now, name='admin_google_sheet_sync_now'),
    path('admin/offline-leads/toggle/<int:connection_id>/', views.admin_google_sheet_toggle, name='admin_google_sheet_toggle'),
    path('admin/offline-leads/delete/<int:connection_id>/', views.admin_google_sheet_delete, name='admin_google_sheet_delete'),
    path('admin/offline-leads/history/<int:connection_id>/', views.admin_google_sheet_history, name='admin_google_sheet_history'),
    path('admin/offline-leads/test/', views.admin_google_sheet_test, name='admin_google_sheet_test_new'),
    path('admin/offline-leads/test/<int:connection_id>/', views.admin_google_sheet_test, name='admin_google_sheet_test'),
    path('admin/offline-leads/edit/<int:connection_id>/', views.admin_google_sheet_edit, name='admin_google_sheet_edit'),
    path('admin/offline-leads/upload/', views.admin_offline_leads_upload, name='admin_offline_leads_upload'),
    path('admin/offline-leads/api/leads/', views.admin_offline_leads_data_api, name='admin_offline_leads_data_api'),
    path('admin/offline-leads/api/status/', views.admin_offline_leads_status_api, name='admin_offline_leads_status_api'),

    # Clean REST API endpoints for Google Sheets Data Integration
    path('api/google-sheets/', api_google_sheets.api_google_sheets_list, name='api_google_sheets_list'),
    path('api/google-sheets/connect/', api_google_sheets.api_google_sheets_connect, name='api_google_sheets_connect'),
    path('api/google-sheets/<int:connection_id>/', api_google_sheets.api_google_sheets_detail, name='api_google_sheets_detail'),
    path('api/google-sheets/<int:connection_id>/sync/', api_google_sheets.api_google_sheets_sync, name='api_google_sheets_sync'),
    path('api/google-sheets/inspect-mapping/', api_google_sheets.api_google_sheets_inspect_mapping, name='api_google_sheets_inspect_mapping'),
    path('api/google-sheets/preview-sync/', api_google_sheets.api_google_sheets_preview_sync, name='api_google_sheets_preview_sync'),
    path('api/google-sheets/<int:connection_id>/save-mapping/', api_google_sheets.api_google_sheets_save_mapping, name='api_google_sheets_save_mapping'),


    # Manager Lead routes
    path('manager/leads/', views.manager_leads_list, name='manager_leads_list'),
    path('manager/leads/create/', views.manager_lead_create, name='manager_lead_create'),
    path('manager/leads/import/', views.manager_lead_import, name='manager_lead_import'),
    path('manager/leads/<int:pk>/', views.manager_lead_detail, name='manager_lead_detail'),
    path('manager/leads/<int:pk>/edit/', views.manager_lead_edit, name='manager_lead_edit'),

    # Telecaller Lead routes
    path('telecaller/leads/', views.telecaller_leads_list, name='telecaller_leads_list'),
    path('telecaller/leads/create/', views.telecaller_lead_create, name='telecaller_lead_create'),
    path('telecaller/leads/import/', views.telecaller_lead_import, name='telecaller_lead_import'),
    path('telecaller/leads/<int:pk>/', views.telecaller_lead_detail, name='telecaller_lead_detail'),
    path('telecaller/leads/<int:pk>/edit/', views.telecaller_lead_edit, name='telecaller_lead_edit'),

    # Branch Head Lead routes (own branch)
    path('manager/branch-head/leads/', views.branch_head_leads_list, name='branch_head_leads_list'),
    path('manager/branch-head/leads/<int:pk>/', views.branch_head_lead_detail, name='branch_head_lead_detail'),

    # Counselor Lead routes (own leads)
    path('counselor/leads/', views.counselor_leads_list, name='counselor_leads_list'),
    path('counselor/leads/<int:pk>/', views.counselor_lead_detail, name='counselor_lead_detail'),
    path('counselor/leads/<int:pk>/status/', views.counselor_lead_update_status, name='counselor_lead_update_status'),

    # Global Quick Search endpoint for Command Palette (Ctrl+K)
    path('api/quick-search/', views.global_quick_search, name='global_quick_search'),

    # Interactive Kanban Pipeline Routes (Phase 3)
    path('leads/kanban/', views.leads_kanban_view, name='leads_kanban'),
    path('leads/api/update-status/', views.api_update_lead_status, name='api_update_lead_status'),

    # Enhanced Data Tables Bulk Operations (Phase 4)
    path('leads/api/bulk-action/', views.api_bulk_action, name='api_bulk_action'),

    # Modern Lead Details Quick View & Inline Edit APIs
    path('leads/api/<int:pk>/quick-details/', views.api_lead_quick_details, name='api_lead_quick_details'),
    path('leads/api/<int:pk>/update-field/', views.api_update_lead_field, name='api_update_lead_field'),

    # Advanced Bulk Edit Operations
    path('leads/api/bulk-edit/options/', views_bulk.api_bulk_edit_options, name='api_bulk_edit_options'),
    path('leads/api/bulk-edit/preview/', views_bulk.api_bulk_edit_preview, name='api_bulk_edit_preview'),
    path('leads/api/bulk-edit/execute/', views_bulk.api_bulk_edit_execute, name='api_bulk_edit_execute'),
    path('leads/api/bulk-edit/status/<str:operation_id>/', views_bulk.api_bulk_edit_status, name='api_bulk_edit_status'),
    path('leads/api/bulk-edit/options/alias/', views_bulk.api_bulk_edit_options, name='bulk_edit_options'),
    path('leads/api/bulk-edit/preview/alias/', views_bulk.api_bulk_edit_preview, name='bulk_edit_preview'),
    path('leads/api/bulk-edit/execute/alias/', views_bulk.api_bulk_edit_execute, name='bulk_edit_execute'),

    # Bulk Operations & Exports
    path('leads/export/', views.export_leads_csv, name='export_leads_csv'),
    path('leads/api/resolve-selection/', views.api_resolve_lead_selection, name='api_resolve_lead_selection'),
    path('leads/api/<int:pk>/reassign-counselor/', views.api_reassign_lead_to_counselor, name='api_reassign_lead_to_counselor'),

    # Lead Queues & Bulk Redistribution (Phase 5 & Multi-Branch Round Robin)
    path('admin/leads/queues/', views.admin_lead_queues, name='admin_lead_queues'),
    path('leads/api/bulk-assign/', views.api_bulk_assign_leads, name='api_bulk_assign_leads'),
    path('leads/api/bulk-assign/preview/', views.api_bulk_assign_preview, name='api_bulk_assign_preview'),

    # Reception & Walk-in Desk (Phase 6 - Req 7 & 11)
    path('receptionist/dashboard/', views.receptionist_dashboard, name='receptionist_dashboard'),
    path('receptionist/leads/<int:pk>/history/', views.receptionist_lead_history, name='receptionist_lead_history'),
    path('receptionist/leads/check-existing/', views.receptionist_check_existing_lead, name='receptionist_check_existing_lead'),
    path('admin/leads/walk-in/', views.admin_walkin_desk, name='admin_walkin_desk'),
    path('admin/leads/walk-in/create/', views.admin_walkin_create, name='admin_walkin_create'),
    path('admin/leads/walk-in/<int:pk>/assign-counselor/', views.admin_walkin_assign_counselor, name='admin_walkin_assign_counselor'),
    path('admin/leads/walk-in/bulk-assign/', views.admin_walkin_bulk_assign_counselor, name='admin_walkin_bulk_assign_counselor'),
    path('admin/leads/walk-in/<int:pk>/status/', views.admin_walkin_update_status, name='admin_walkin_update_status'),
    path('enquiry/', views_walkin.public_student_enquiry_form, name='public_student_enquiry_form'),
    path('enquiry/<int:branch_id>/', views_walkin.public_student_enquiry_form, name='public_student_enquiry_branch'),
    path('enquiry/f/<str:slug>/', views_walkin.public_student_enquiry_form_by_slug, name='public_student_enquiry_slug'),
    path('enquiry/f/<str:slug>/<int:branch_id>/', views_walkin.public_student_enquiry_form_by_slug, name='public_student_enquiry_slug_branch'),
    path('admin/branches/<int:branch_id>/qr-standee/', views_walkin.branch_qr_standee_view, name='branch_qr_standee'),
    path('receptionist/qr-standee/', views_walkin.receptionist_qr_standee_view, name='receptionist_qr_standee'),

    # Admin Walk-in Form Studio & Field Editor
    path('admin/walkin-forms/', views_walkin.admin_walkin_forms_list, name='admin_walkin_forms_list'),
    path('admin/walkin-forms/create/', views_walkin.admin_walkin_form_create, name='admin_walkin_form_create'),
    path('admin/walkin-forms/<int:pk>/edit/', views_walkin.admin_walkin_form_edit, name='admin_walkin_form_edit'),
    path('admin/walkin-forms/<int:pk>/duplicate/', views_walkin.admin_walkin_form_duplicate, name='admin_walkin_form_duplicate'),
    path('admin/walkin-forms/<int:pk>/toggle-status/', views_walkin.admin_walkin_form_toggle_status, name='admin_walkin_form_toggle_status'),
    path('admin/walkin-forms/<int:pk>/delete/', views_walkin.admin_walkin_form_delete, name='admin_walkin_form_delete'),
    path('admin/walkin-forms/<int:pk>/qr-standee/', views_walkin.walkin_form_qr_standee_view, name='walkin_form_qr_standee'),

    # Enrollment & Student Payment Lifecycle (Phase 7)
    path('admin/enrolled-students/', views_enrollment.admin_enrolled_students, name='admin_enrolled_students'),
    path('counselor/enrolled-students/', views_enrollment.counselor_enrolled_students, name='counselor_enrolled_students'),
    path('leads/<int:lead_id>/enroll/', views_enrollment.enrollment_create_or_edit, name='lead_enroll'),
    path('enrollments/<int:enrollment_id>/payment/', views_enrollment.enrollment_record_payment, name='enrollment_record_payment'),
    path('enrollments/installments/<int:installment_id>/update/', views_enrollment.enrollment_update_installment, name='enrollment_update_installment'),
    path('enrollments/receipt/<int:transaction_id>/', views_enrollment.enrollment_receipt_view, name='enrollment_receipt_view'),
    path('enrollments/receipt/<int:transaction_id>/pdf/', views_enrollment.enrollment_receipt_pdf_view, name='enrollment_receipt_pdf_view'),
    path('enrollments/api/<int:enrollment_id>/details/', views_enrollment.api_enrollment_details, name='api_enrollment_details'),
    path('enrollments/api/calculate-gst/', views_enrollment.api_calculate_gst_preview, name='api_calculate_gst_preview'),
    path('enrollments/reminders/trigger/', views_enrollment.trigger_installment_reminders, name='trigger_installment_reminders'),
    path('enrollments/payments/<int:payment_id>/resubmit/', views_enrollment.enrollment_resubmit_payment, name='enrollment_resubmit_payment'),

    # Accountant Portal, Dashboard, Verification Queue, Proofs & Reports
    path('accountant/dashboard/', views_accountant.accountant_dashboard, name='accountant_dashboard'),
    path('accountant/verification/', views_accountant.accountant_payment_verification, name='accountant_payment_verification'),
    path('accountant/verification/<int:payment_id>/approve/', views_accountant.accountant_approve_payment, name='accountant_approve_payment'),
    path('accountant/verification/<int:payment_id>/reject/', views_accountant.accountant_reject_payment, name='accountant_reject_payment'),
    path('accountant/proofs/<int:payment_id>/', views_accountant.accountant_payment_proof_view, name='accountant_payment_proof_view'),
    path('accountant/reports/monthly/excel/', views_accountant.accountant_monthly_report_excel, name='accountant_monthly_report_excel'),
]




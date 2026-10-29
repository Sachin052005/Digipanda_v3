from django.urls import path
from django.contrib.auth import views as auth_views
from . import views
from . import hierarchy_views
from . import receptionist_views
from . import accountant_views
from . import branch_admin_views

urlpatterns = [
    path('login/', views.general_login, name='login'),
    path('login/redirect/', views.login_redirect, name='login_redirect'),
    path('logout/', views.logout_view, name='logout'),
    
    # Password Reset
    path('password-reset/', auth_views.PasswordResetView.as_view(
        template_name='registration/password_reset_form.html',
        email_template_name='registration/password_reset_email.html',
        subject_template_name='registration/password_reset_subject.txt',
    ), name='password_reset'),
    path('password-reset/done/', auth_views.PasswordResetDoneView.as_view(
        template_name='registration/password_reset_done.html'
    ), name='password_reset_done'),
    path('password-reset-confirm/<uidb64>/<token>/', auth_views.PasswordResetConfirmView.as_view(
        template_name='registration/password_reset_confirm.html'
    ), name='password_reset_confirm'),
    path('password-reset-complete/', auth_views.PasswordResetCompleteView.as_view(
        template_name='registration/password_reset_complete.html'
    ), name='password_reset_complete'),
    
    # User Profile & Self Password Change (All Roles)
    path('profile/', views.user_profile, name='user_profile'),
    path('profile/change-password/', views.user_change_password, name='change_password'),

    # Admin Staff Password Operations (Reset Link & Set Password)
    path('admin/users/<int:pk>/send-reset-link/', views.admin_send_password_reset_link, name='admin_send_password_reset_link'),
    path('admin/users/<int:pk>/set-password/', views.admin_set_user_password, name='admin_set_user_password'),

    # Account Setup & Onboarding (Single-Use Token Link from Welcome Email)
    path('accounts/setup/<uidb64>/<token>/', views.account_setup_view, name='account_setup'),
    path('admin/users/create/', views.create_user_view, name='admin_user_create'),
    path('users/create/', views.create_user_view, name='create_user'),
    path('users/<int:pk>/resend-invitation/', views.resend_user_invitation, name='resend_user_invitation'),
    path('accounts/api/username-preview/', views.api_username_preview, name='api_username_preview'),
    path('api/username-preview/', views.api_username_preview, name='api_username_preview_alt'),

    
    # Role-specific authentication routes
    path('admin/login/', views.admin_login, name='admin_login'),
    path('admin/logout/', views.logout_view, name='admin_logout'),
    
    path('manager/login/', views.manager_login, name='manager_login'),
    path('manager/register/', views.manager_register, name='manager_register'),
    path('manager/logout/', views.logout_view, name='manager_logout'),
    
    path('telecaller/login/', views.telecaller_login, name='telecaller_login'),
    path('telecaller/register/', views.telecaller_register, name='telecaller_register'),
    path('telecaller/logout/', views.logout_view, name='telecaller_logout'),

    path('receptionist/login/', views.receptionist_login, name='receptionist_login'),

    # Universal User Profile Resolver (All Roles)
    path('users/<int:pk>/profile/', views.universal_user_profile_redirect, name='universal_user_profile'),

    # Admin Receptionist Oversight & Management
    path('admin/receptionists/', receptionist_views.admin_receptionists_list, name='admin_receptionists_list'),
    path('admin/receptionists/create/', receptionist_views.admin_receptionist_create, name='admin_receptionist_create'),
    path('admin/receptionists/<int:pk>/', receptionist_views.admin_receptionist_detail, name='admin_receptionist_detail'),
    path('admin/receptionists/<int:pk>/password/', receptionist_views.admin_receptionist_change_password, name='admin_receptionist_change_password'),
    path('admin/receptionists/<int:pk>/toggle-status/', receptionist_views.admin_receptionist_toggle_status, name='admin_receptionist_toggle_status'),

    # Admin Accountant Management
    path('admin/accountants/', accountant_views.admin_accountants_list, name='admin_accountants_list'),
    path('admin/accountants/<int:pk>/', accountant_views.admin_accountant_detail, name='admin_accountant_detail'),
    path('admin/accountants/<int:pk>/toggle-status/', accountant_views.admin_accountant_toggle_status, name='admin_accountant_toggle_status'),
    # Admin Branch Admin Oversight & Management
    path('admin/branch-admins/', branch_admin_views.admin_branch_admins_list, name='admin_branch_admins_list'),
    path('admin/branch-admins/create/', branch_admin_views.admin_branch_admin_create, name='admin_branch_admin_create'),
    path('admin/branch-admins/<int:pk>/', branch_admin_views.admin_branch_admin_detail, name='admin_branch_admin_detail'),
    path('admin/branch-admins/<int:pk>/edit/', branch_admin_views.admin_branch_admin_edit, name='admin_branch_admin_edit'),


    # Progressive Hierarchy Routes (Levels 1 - 5)
    path('sales-heads/', hierarchy_views.hierarchy_sales_heads_list, name='hierarchy_sales_heads_list'),
    path('sales-heads/<int:sales_head_id>/branch-heads/', hierarchy_views.hierarchy_branch_heads_list, name='sales_head_branch_heads'),
    path('sales-heads/<int:sales_head_id>/branch-heads/view/', hierarchy_views.hierarchy_branch_heads_list, name='hierarchy_sales_head_branch_heads'),
    
    path('branch-heads/', hierarchy_views.hierarchy_branch_heads_list, name='hierarchy_branch_heads_list'),
    path('branch-heads/<int:branch_head_id>/counselors/', hierarchy_views.hierarchy_counselors_list, name='branch_head_counselors'),
    path('branch-heads/<int:branch_head_id>/counselors/view/', hierarchy_views.hierarchy_counselors_list, name='hierarchy_branch_head_counselors'),
    
    path('counselors/', hierarchy_views.hierarchy_counselors_list, name='hierarchy_counselors_list'),
    path('counselors/<int:counselor_id>/telecallers/', hierarchy_views.hierarchy_telecallers_list, name='counselor_telecallers'),
    path('counselors/<int:counselor_id>/telecallers/view/', hierarchy_views.hierarchy_telecallers_list, name='hierarchy_counselor_telecallers'),
    
    path('telecallers/', hierarchy_views.hierarchy_telecallers_list, name='hierarchy_telecallers_list'),
    path('telecallers/<int:telecaller_id>/leads/', hierarchy_views.hierarchy_telecaller_leads, name='telecaller_leads'),
    path('telecallers/<int:telecaller_id>/leads/view/', hierarchy_views.hierarchy_telecaller_leads, name='hierarchy_telecaller_leads'),
]

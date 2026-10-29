from django.urls import path
from . import views

urlpatterns = [
    # Dedicated Authentication
    path('login/', views.finance_login, name='finance_login'),

    # Core Suite Views
    path('dashboard/', views.finance_dashboard, name='finance_dashboard'),
    path('pending/', views.finance_pending_payments, name='finance_pending_payments'),
    path('approvals/', views.finance_approvals, name='finance_approvals'),
    path('finance-oversight/', views.finance_oversight, name='finance_oversight'),
    path('expenses/', views.finance_expenses, name='finance_expenses'),
    path('internal-transfers/', views.finance_internal_transfers, name='finance_internal_transfers'),
    path('renewal-alerts/', views.finance_renewal_alerts, name='finance_renewal_alerts'),

    # HR & Payroll
    path('hr/employees/', views.finance_employees, name='finance_employees'),
    path('hr/payroll/', views.finance_payroll, name='finance_payroll'),
    path('hr/salary-arrears/', views.finance_salary_arrears, name='finance_salary_arrears'),

    # Administration
    path('incentive-track/', views.finance_incentive_track, name='finance_incentive_track'),

    # Settings & Help
    path('settings/', views.finance_settings, name='finance_settings'),

    # Exports
    path('audit-export/', views.finance_audit_export, name='finance_audit_export'),

    # Approval Actions
    path('approvals/payment/<int:payment_id>/approve/', views.finance_approve_payment_action, name='finance_approve_payment_action'),
    path('approvals/payment/<int:payment_id>/reject/', views.finance_reject_payment_action, name='finance_reject_payment_action'),
    path('approvals/expense/<int:expense_id>/approve/', views.finance_approve_expense_action, name='finance_approve_expense_action'),
    path('approvals/expense/<int:expense_id>/reject/', views.finance_reject_expense_action, name='finance_reject_expense_action'),
    path('approvals/payroll/<int:payroll_id>/approve/', views.finance_approve_payroll_action, name='finance_approve_payroll_action'),
]

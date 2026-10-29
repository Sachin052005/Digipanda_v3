from django import forms
from decimal import Decimal
from .models import (
    Expense,
    ExpenseCategory,
    InternalTransfer,
    RenewalAlert,
    RenewalAlertType,
    SalaryArrear,
    SalaryArrearSource,
    EmployeeProfile,
    BudgetForecast,
)
from branches.models import Branch


class ExpenseForm(forms.ModelForm):
    class Meta:
        model = Expense
        fields = [
            'category',
            'sub_category',
            'paid_by',
            'amount',
            'description',
            'paid_to',
            'expense_date',
            'proof',
        ]
        widgets = {
            'category': forms.Select(attrs={'class': 'form-select tp-custom-select'}),
            'sub_category': forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'e.g. Ad, Office Rent, Tea/Snacks'}),
            'paid_by': forms.Select(attrs={'class': 'form-select tp-custom-select'}),
            'amount': forms.NumberInput(attrs={'class': 'form-input', 'placeholder': 'e.g. 25000', 'step': '0.01'}),
            'description': forms.Textarea(attrs={'class': 'form-input', 'rows': 2, 'placeholder': 'Details / Voucher notes'}),
            'paid_to': forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'Vendor / Recipient'}),
            'expense_date': forms.DateInput(attrs={'class': 'form-input', 'type': 'date'}),
            'proof': forms.FileInput(attrs={'class': 'form-input'}),
        }

    def clean_amount(self):
        amt = self.cleaned_data.get('amount')
        if amt is None or amt <= Decimal('0.00'):
            raise forms.ValidationError("Expense amount must be greater than zero.")
        return amt


class InternalTransferForm(forms.ModelForm):
    class Meta:
        model = InternalTransfer
        fields = [
            'to_branch',
            'amount',
            'reason',
            'notes',
            'delivery_challan_doc',
        ]
        widgets = {
            'to_branch': forms.Select(attrs={'class': 'form-select tp-custom-select'}),
            'amount': forms.NumberInput(attrs={'class': 'form-input', 'placeholder': 'e.g. 50000', 'step': '0.01'}),
            'reason': forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'e.g. Cash Replenishment'}),
            'notes': forms.Textarea(attrs={'class': 'form-input', 'rows': 2, 'placeholder': 'Optional remarks'}),
            'delivery_challan_doc': forms.FileInput(attrs={'class': 'form-input'}),
        }

    def clean_amount(self):
        amt = self.cleaned_data.get('amount')
        if amt is None or amt <= Decimal('0.00'):
            raise forms.ValidationError("Transfer amount must be greater than zero.")
        return amt


class RenewalAlertForm(forms.ModelForm):
    class Meta:
        model = RenewalAlert
        fields = [
            'name',
            'alert_type',
            'branch',
            'contract_reference',
            'repeat_every_months',
            'due_date',
            'alert_starts_days_before',
            'amount',
            'recipient_finance_head',
            'recipient_branch_head',
            'notes',
        ]
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'e.g. Office Rent, Electricity, CRM Subscription'}),
            'alert_type': forms.Select(attrs={'class': 'form-select tp-custom-select'}),
            'branch': forms.Select(attrs={'class': 'form-select tp-custom-select'}),
            'contract_reference': forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'e.g. Lease-2026-VAD, Acc #44921'}),
            'repeat_every_months': forms.NumberInput(attrs={'class': 'form-input', 'min': 0, 'placeholder': '1 for monthly, 0 for one-time'}),
            'due_date': forms.DateInput(attrs={'class': 'form-input', 'type': 'date'}),
            'alert_starts_days_before': forms.NumberInput(attrs={'class': 'form-input', 'min': 1, 'max': 60, 'value': 7}),
            'amount': forms.NumberInput(attrs={'class': 'form-input', 'placeholder': 'Optional estimated amount', 'step': '0.01'}),
            'recipient_finance_head': forms.Select(attrs={'class': 'form-select tp-custom-select'}),
            'recipient_branch_head': forms.Select(attrs={'class': 'form-select tp-custom-select'}),
            'notes': forms.Textarea(attrs={'class': 'form-input', 'rows': 2, 'placeholder': 'Payment instructions, invoice notes, or owner instructions'}),
        }

    def __init__(self, *args, branch=None, **kwargs):
        super().__init__(*args, **kwargs)
        from accounts.models import User, UserRole
        if branch:
            self.fields['branch'].initial = branch
            self.fields['recipient_finance_head'].queryset = User.objects.filter(
                branch=branch, role=UserRole.FINANCE_HEAD, is_active=True
            ).order_by('first_name', 'username')
            self.fields['recipient_branch_head'].queryset = User.objects.filter(
                branch=branch, role=UserRole.BRANCH_HEAD, is_active=True
            ).order_by('first_name', 'username')
        else:
            self.fields['recipient_finance_head'].queryset = User.objects.filter(
                role=UserRole.FINANCE_HEAD, is_active=True
            ).order_by('first_name', 'username')
            self.fields['recipient_branch_head'].queryset = User.objects.filter(
                role=UserRole.BRANCH_HEAD, is_active=True
            ).order_by('first_name', 'username')

        self.fields['recipient_finance_head'].empty_label = "-- Select Financial Head (Auto-assigned if blank) --"
        self.fields['recipient_branch_head'].empty_label = "-- Select Branch Head (Auto-assigned if blank) --"
        self.fields['recipient_finance_head'].required = False
        self.fields['recipient_branch_head'].required = False
        self.fields['branch'].required = False

    def clean_amount(self):
        amt = self.cleaned_data.get('amount')
        if amt is not None and amt < Decimal('0.00'):
            raise forms.ValidationError("Amount cannot be negative.")
        return amt


class SalaryArrearForm(forms.ModelForm):
    class Meta:
        model = SalaryArrear
        fields = [
            'employee',
            'period_label',
            'source',
            'days_count',
            'amount',
            'reason',
        ]
        widgets = {
            'employee': forms.Select(attrs={'class': 'form-select tp-custom-select'}),
            'period_label': forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'e.g. September 2026'}),
            'source': forms.Select(attrs={'class': 'form-select tp-custom-select'}),
            'days_count': forms.NumberInput(attrs={'class': 'form-input', 'min': 0}),
            'amount': forms.NumberInput(attrs={'class': 'form-input', 'placeholder': 'e.g. 5000', 'step': '0.01'}),
            'reason': forms.Textarea(attrs={'class': 'form-input', 'rows': 2, 'placeholder': 'Reason for correction'}),
        }

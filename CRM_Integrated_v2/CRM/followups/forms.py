from django import forms
from accounts.models import User, UserRole
from leads.models import Lead
from .models import FollowUp, FollowUpStatus

class AdminFollowUpForm(forms.ModelForm):
    lead = forms.ModelChoiceField(
        queryset=Lead.objects.all().order_by('name'),
        widget=forms.Select(attrs={'class': 'form-select'}),
        help_text="Select lead for this follow-up"
    )
    assigned_user = forms.ModelChoiceField(
        queryset=User.objects.filter(is_active=True).order_by('username'),
        required=False,
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    manager = forms.ModelChoiceField(
        queryset=User.objects.filter(role=UserRole.SALES_HEAD, is_active=True).order_by('username'),
        required=False,
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    telecaller = forms.ModelChoiceField(
        queryset=User.objects.filter(role=UserRole.TELECALLER, is_active=True).order_by('username'),
        required=False,
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    follow_up_date = forms.DateField(
        widget=forms.DateInput(attrs={'type': 'date', 'class': 'form-control'})
    )
    follow_up_time = forms.TimeField(
        required=False,
        widget=forms.TimeInput(attrs={'type': 'time', 'class': 'form-control'})
    )
    status = forms.ChoiceField(
        choices=FollowUpStatus.choices,
        initial=FollowUpStatus.PENDING,
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    notes = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={'rows': 3, 'class': 'form-control', 'placeholder': 'Discussion notes or callback reason...'})
    )

    class Meta:
        model = FollowUp
        fields = [
            'lead',
            'assigned_user',
            'manager',
            'telecaller',
            'follow_up_date',
            'follow_up_time',
            'status',
            'notes',
        ]

    def clean(self):
        cleaned_data = super().clean()
        lead = cleaned_data.get('lead')
        follow_up_date = cleaned_data.get('follow_up_date')
        status = cleaned_data.get('status')
        manager = cleaned_data.get('manager')
        telecaller = cleaned_data.get('telecaller')

        if telecaller and manager:
            from accounts.permissions import get_accessible_branch_ids
            if telecaller.branch_id and telecaller.branch_id not in get_accessible_branch_ids(manager):
                raise forms.ValidationError(
                    f"Invalid assignment: Telecaller '{telecaller.username}' belongs to a branch not managed by '{manager.username}'."
                )

        # Accidental duplicate check: Prevent duplicate PENDING follow-ups on the exact same date for the same lead
        if lead and follow_up_date and status == FollowUpStatus.PENDING:
            existing_pending = FollowUp.objects.filter(
                lead=lead,
                follow_up_date=follow_up_date,
                status=FollowUpStatus.PENDING
            )
            if self.instance and self.instance.pk:
                existing_pending = existing_pending.exclude(pk=self.instance.pk)
            if existing_pending.exists():
                raise forms.ValidationError(
                    f"A pending follow-up is already scheduled for lead '{lead.name}' on {follow_up_date}."
                )

        return cleaned_data

class FollowUpRescheduleForm(forms.Form):
    follow_up_date = forms.DateField(
        widget=forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
        help_text="Select new follow-up date"
    )
    follow_up_time = forms.TimeField(
        required=False,
        widget=forms.TimeInput(attrs={'type': 'time', 'class': 'form-control'}),
        help_text="Optional time"
    )
    notes = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={'rows': 3, 'class': 'form-control', 'placeholder': 'Reason for rescheduling or additional notes...'}),
        help_text="Reschedule context or reason"
    )

    def __init__(self, *args, followup=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.followup = followup

    def clean(self):
        cleaned_data = super().clean()
        new_date = cleaned_data.get('follow_up_date')
        if getattr(self, 'followup', None) and self.followup.lead and new_date:
            exists = FollowUp.objects.filter(
                lead=self.followup.lead,
                follow_up_date=new_date,
                status=FollowUpStatus.PENDING
            ).exclude(pk=self.followup.pk).exists()
            if exists:
                raise forms.ValidationError(
                    f"A pending follow-up is already scheduled for lead '{self.followup.lead.name}' on {new_date}."
                )
        return cleaned_data

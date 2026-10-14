from django import forms
from django.core.exceptions import ValidationError
from django.contrib.auth.password_validation import validate_password
from accounts.models import User, UserRole
from branches.models import Branch

class AdminManagerCreateForm(forms.ModelForm):
    branches = forms.ModelMultipleChoiceField(
        queryset=Branch.objects.filter(status='Active'),
        required=False,
        widget=forms.CheckboxSelectMultiple
    )

    class Meta:
        model = User
        fields = ['first_name', 'last_name', 'username', 'email', 'phone', 'is_active']
        widgets = {
            'first_name': forms.TextInput(attrs={'class': 'form-control'}),
            'last_name': forms.TextInput(attrs={'class': 'form-control'}),
            'username': forms.TextInput(attrs={'class': 'form-control bg-light', 'readonly': 'readonly', 'placeholder': 'Generated automatically'}),
            'email': forms.EmailInput(attrs={'class': 'form-control'}),
            'phone': forms.TextInput(attrs={'class': 'form-control'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if not self.instance.pk:
            self.instance.role = UserRole.SALES_HEAD

    def clean_username(self):
        username = (self.cleaned_data.get('username') or '').strip()
        from accounts.services import generate_unique_username
        if not username:
            first = self.cleaned_data.get('first_name') or ''
            last = self.cleaned_data.get('last_name') or ''
            email = self.cleaned_data.get('email') or ''
            username = generate_unique_username(first_name=first, last_name=last, role=UserRole.SALES_HEAD, email=email)
        elif User.objects.filter(username__iexact=username).exists():
            username = generate_unique_username(first_name=username, role=UserRole.SALES_HEAD)
        return username

    def clean_email(self):
        email = self.cleaned_data.get('email')
        if not email:
            raise ValidationError("Email is required.")
        if User.objects.filter(email__iexact=email).exists():
            raise ValidationError("A user with this email address already exists.")
        return email

    def save(self, commit=True, created_by=None):
        user = super().save(commit=False)
        user.role = UserRole.SALES_HEAD
        from accounts.services import generate_unique_username
        if not user.username:
            user.username = generate_unique_username(
                first_name=user.first_name,
                last_name=user.last_name,
                role=UserRole.SALES_HEAD,
                email=user.email
            )
        user.set_unusable_password()
        user.must_change_password = True
        user.is_active = False
        user.invitation_status = 'PENDING'
        if commit:
            user.save()
            from branches.models import SalesHeadBranchAccess
            for branch in self.cleaned_data.get('branches', []):
                SalesHeadBranchAccess.objects.get_or_create(
                    sales_head=user, branch=branch, defaults={'created_by': created_by}
                )
        return user

class AdminManagerEditForm(forms.ModelForm):
    branches = forms.ModelMultipleChoiceField(
        queryset=Branch.objects.filter(status='Active'),
        required=False,
        widget=forms.CheckboxSelectMultiple
    )

    class Meta:
        model = User
        fields = ['first_name', 'last_name', 'email', 'phone', 'is_active']
        widgets = {
            'first_name': forms.TextInput(attrs={'class': 'form-control'}),
            'last_name': forms.TextInput(attrs={'class': 'form-control'}),
            'email': forms.EmailInput(attrs={'class': 'form-control'}),
            'phone': forms.TextInput(attrs={'class': 'form-control'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }

    def save(self, commit=True, created_by=None):
        user = super().save(commit=commit)
        if commit:
            from branches.models import SalesHeadBranchAccess
            selected_ids = set(b.pk for b in self.cleaned_data.get('branches', []))
            current_ids = set(user.branch_access.values_list('branch_id', flat=True))
            for branch_id in selected_ids - current_ids:
                SalesHeadBranchAccess.objects.get_or_create(
                    sales_head=user, branch_id=branch_id, defaults={'created_by': created_by}
                )
            SalesHeadBranchAccess.objects.filter(
                sales_head=user, branch_id__in=(current_ids - selected_ids)
            ).delete()
        return user

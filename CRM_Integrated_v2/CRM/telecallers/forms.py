from django import forms
from django.core.exceptions import ValidationError
from django.contrib.auth.password_validation import validate_password
from django.db.models import Q
from accounts.models import User, UserRole
from branches.models import Branch

class AdminTelecallerCreateForm(forms.ModelForm):
    counselor = forms.ModelChoiceField(
        queryset=User.objects.filter(role=UserRole.COUNSELOR, is_active=True),
        required=True,
        empty_label="-- Select Counselor (Required) --",
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    branch = forms.ModelChoiceField(
        queryset=Branch.objects.filter(status='Active'),
        required=False,
        empty_label="-- Select Branch (or inherit from Counselor) --",
        widget=forms.Select(attrs={'class': 'form-select'})
    )

    class Meta:
        model = User
        fields = ['first_name', 'last_name', 'username', 'email', 'phone', 'counselor', 'branch', 'is_active']
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
            self.instance.role = UserRole.TELECALLER

    def clean_username(self):
        username = (self.cleaned_data.get('username') or '').strip()
        from accounts.services import generate_unique_username
        if not username:
            first = self.cleaned_data.get('first_name') or ''
            last = self.cleaned_data.get('last_name') or ''
            email = self.cleaned_data.get('email') or ''
            username = generate_unique_username(first_name=first, last_name=last, role=UserRole.TELECALLER, email=email)
        elif User.objects.filter(username__iexact=username).exists():
            username = generate_unique_username(first_name=username, role=UserRole.TELECALLER)
        return username

    def clean_email(self):
        email = self.cleaned_data.get('email')
        if not email:
            raise ValidationError("Email is required.")
        if User.objects.filter(email__iexact=email).exists():
            raise ValidationError("A user with this email address already exists.")
        return email

    def clean(self):
        cleaned_data = super().clean()
        counselor = cleaned_data.get('counselor')
        branch = cleaned_data.get('branch')

        if not counselor:
            self.add_error('counselor', "Counselor is required. A Telecaller must be created under a Counselor.")
        else:
            if counselor.role != UserRole.COUNSELOR:
                self.add_error('counselor', "Selected user must have the Counselor role.")
            if not counselor.is_active:
                self.add_error('counselor', "Assigned counselor must be active.")
            if not branch and counselor.branch:
                cleaned_data['branch'] = counselor.branch
                branch = counselor.branch
            elif not branch and not counselor.branch:
                self.add_error('branch', "Branch is required. The assigned counselor does not have a branch.")
            elif branch and counselor.branch and branch != counselor.branch:
                self.add_error(
                    'counselor',
                    f"Assigned counselor '{counselor.username}' belongs to '{counselor.branch.name}', which does not match selected branch '{branch.name}'."
                )

        return cleaned_data

    def save(self, commit=True):
        user = super().save(commit=False)
        user.role = UserRole.TELECALLER
        if user.counselor and not user.branch:
            user.branch = user.counselor.branch
        from accounts.services import generate_unique_username
        if not user.username:
            user.username = generate_unique_username(
                first_name=user.first_name,
                last_name=user.last_name,
                role=UserRole.TELECALLER,
                email=user.email
            )
        user.set_unusable_password()
        user.must_change_password = True
        user.is_active = False
        user.invitation_status = 'PENDING'
        if commit:
            user.save()
        return user


class AdminTelecallerEditForm(forms.ModelForm):
    counselor = forms.ModelChoiceField(
        queryset=User.objects.filter(role=UserRole.COUNSELOR),
        required=True,
        empty_label="-- Select Counselor (Required) --",
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    branch = forms.ModelChoiceField(
        queryset=Branch.objects.all(),
        required=False,
        empty_label="-- Select Branch (or inherit from Counselor) --",
        widget=forms.Select(attrs={'class': 'form-select'})
    )

    class Meta:
        model = User
        fields = ['first_name', 'last_name', 'email', 'phone', 'counselor', 'branch', 'is_active']
        widgets = {
            'first_name': forms.TextInput(attrs={'class': 'form-control'}),
            'last_name': forms.TextInput(attrs={'class': 'form-control'}),
            'email': forms.EmailInput(attrs={'class': 'form-control'}),
            'phone': forms.TextInput(attrs={'class': 'form-control'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Ensure the counselor field includes active counselors AND the current counselor
        # so selection persists properly across page refresh and edit
        if self.instance and self.instance.counselor_id:
            self.fields['counselor'].queryset = User.objects.filter(
                Q(role=UserRole.COUNSELOR, is_active=True) | Q(pk=self.instance.counselor_id)
            ).order_by('first_name', 'username')
            self.fields['counselor'].initial = self.instance.counselor
        else:
            self.fields['counselor'].queryset = User.objects.filter(
                role=UserRole.COUNSELOR, is_active=True
            ).order_by('first_name', 'username')

    def clean(self):
        cleaned_data = super().clean()
        counselor = cleaned_data.get('counselor')
        branch = cleaned_data.get('branch')

        if not counselor:
            self.add_error('counselor', "Counselor is required. A Telecaller must have an assigned Counselor.")
        else:
            if counselor.role != UserRole.COUNSELOR:
                self.add_error('counselor', "Selected user must have the Counselor role.")
            if not counselor.is_active and (not self.instance or self.instance.counselor_id != counselor.id):
                self.add_error('counselor', "Assigned counselor must be active.")
            if branch and counselor.branch and branch != counselor.branch:
                self.add_error(
                    'counselor',
                    f"Assigned counselor '{counselor.username}' belongs to '{counselor.branch.name}', which does not match selected branch '{branch.name}'."
                )
        return cleaned_data

    def save(self, commit=True):
        user = super().save(commit=False)
        if user.counselor and not user.branch:
            user.branch = user.counselor.branch
        if commit:
            user.save()
        return user


class BranchHeadTelecallerCreateForm(forms.ModelForm):
    """Branch Head creates a Telecaller - branch is always auto-inherited, counselor is required."""
    counselor = forms.ModelChoiceField(
        queryset=User.objects.none(),
        required=True,
        empty_label="-- Select Counselor (Required) --",
        widget=forms.Select(attrs={'class': 'form-select'})
    )

    class Meta:
        model = User
        fields = ['first_name', 'last_name', 'username', 'email', 'phone', 'counselor', 'is_active']
        widgets = {
            'first_name': forms.TextInput(attrs={'class': 'form-control'}),
            'last_name': forms.TextInput(attrs={'class': 'form-control'}),
            'username': forms.TextInput(attrs={'class': 'form-control bg-light', 'readonly': 'readonly', 'placeholder': 'Generated automatically'}),
            'email': forms.EmailInput(attrs={'class': 'form-control'}),
            'phone': forms.TextInput(attrs={'class': 'form-control'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }

    def __init__(self, *args, branch=None, **kwargs):
        super().__init__(*args, **kwargs)
        if not self.instance.pk:
            self.instance.role = UserRole.TELECALLER
        self._branch = branch
        if branch is not None:
            self.fields['counselor'].queryset = User.objects.filter(
                role=UserRole.COUNSELOR, branch_id=branch.id, is_active=True
            ).order_by('first_name', 'username')

    def clean_username(self):
        username = (self.cleaned_data.get('username') or '').strip()
        from accounts.services import generate_unique_username
        if not username:
            first = self.cleaned_data.get('first_name') or ''
            last = self.cleaned_data.get('last_name') or ''
            email = self.cleaned_data.get('email') or ''
            username = generate_unique_username(first_name=first, last_name=last, role=UserRole.TELECALLER, email=email)
        elif User.objects.filter(username__iexact=username).exists():
            username = generate_unique_username(first_name=username, role=UserRole.TELECALLER)
        return username

    def clean_email(self):
        email = self.cleaned_data.get('email')
        if not email:
            raise ValidationError("Email is required.")
        if User.objects.filter(email__iexact=email).exists():
            raise ValidationError("A user with this email address already exists.")
        return email

    def clean(self):
        cleaned_data = super().clean()
        counselor = cleaned_data.get('counselor')
        if not counselor:
            self.add_error('counselor', "Counselor is required. A Telecaller must be assigned to a Counselor.")
        elif self._branch and counselor.branch_id != self._branch.id:
            self.add_error('counselor', f"Assigned counselor must belong to this branch ({self._branch.name}).")
        elif not counselor.is_active:
            self.add_error('counselor', "Assigned counselor must be active.")

        return cleaned_data

    def save(self, commit=True):
        user = super().save(commit=False)
        user.role = UserRole.TELECALLER
        user.branch = self._branch
        from accounts.services import generate_unique_username
        if not user.username:
            user.username = generate_unique_username(
                first_name=user.first_name,
                last_name=user.last_name,
                role=UserRole.TELECALLER,
                email=user.email
            )
        user.set_unusable_password()
        user.must_change_password = True
        user.is_active = False
        user.invitation_status = 'PENDING'
        if commit:
            user.save()
        return user


class TelecallerAssignForm(forms.Form):
    counselor = forms.ModelChoiceField(
        queryset=User.objects.filter(role=UserRole.COUNSELOR, is_active=True),
        required=True,
        empty_label="-- Select Counselor --",
        widget=forms.Select(attrs={'class': 'form-select'})
    )

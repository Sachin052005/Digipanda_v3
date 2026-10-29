from django import forms
from django.core.exceptions import ValidationError
from django.contrib.auth.password_validation import validate_password
from accounts.models import User, UserRole


class AdminCounselorCreateForm(forms.ModelForm):
    """Admin creates a Counselor directly, choosing the branch (Branch Head / Sales Head
    are then derived from that branch, same as everywhere else in the hierarchy)."""
    branch = forms.ModelChoiceField(queryset=User.objects.none(), required=True, widget=forms.Select(attrs={'class': 'form-select'}))

    class Meta:
        model = User
        fields = ['first_name', 'last_name', 'username', 'email', 'phone', 'branch', 'is_active']
        widgets = {
            'first_name': forms.TextInput(attrs={'class': 'form-control'}),
            'last_name': forms.TextInput(attrs={'class': 'form-control'}),
            'username': forms.TextInput(attrs={'class': 'form-control bg-light', 'readonly': 'readonly', 'placeholder': 'Generated automatically'}),
            'email': forms.EmailInput(attrs={'class': 'form-control'}),
            'phone': forms.TextInput(attrs={'class': 'form-control'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }

    def __init__(self, *args, allowed_branches=None, **kwargs):
        super().__init__(*args, **kwargs)
        if not self.instance.pk:
            self.instance.role = UserRole.COUNSELOR
        from branches.models import Branch
        self.fields['branch'].queryset = allowed_branches if allowed_branches is not None else Branch.objects.none()

    def clean_username(self):
        username = (self.cleaned_data.get('username') or '').strip()
        from accounts.services import generate_unique_username
        if not username:
            first = self.cleaned_data.get('first_name') or ''
            last = self.cleaned_data.get('last_name') or ''
            email = self.cleaned_data.get('email') or ''
            username = generate_unique_username(first_name=first, last_name=last, role=UserRole.COUNSELOR, email=email)
        elif User.objects.filter(username__iexact=username).exists():
            username = generate_unique_username(first_name=username, role=UserRole.COUNSELOR)
        return username

    def clean_email(self):
        email = self.cleaned_data.get('email')
        if not email:
            raise ValidationError("Email is required.")
        if User.objects.filter(email__iexact=email).exists():
            raise ValidationError("A user with this email address already exists.")
        return email

    def save(self, commit=True):
        user = super().save(commit=False)
        user.role = UserRole.COUNSELOR
        from accounts.services import generate_unique_username
        if not user.username:
            user.username = generate_unique_username(
                first_name=user.first_name,
                last_name=user.last_name,
                role=UserRole.COUNSELOR,
                email=user.email
            )
        password = self.data.get('password')
        if password:
            user.set_password(password)
            user.must_change_password = False
            user.invitation_status = 'ACCEPTED'
        else:
            user.set_unusable_password()
            user.must_change_password = True
            user.invitation_status = 'PENDING'

        if 'is_active' in self.cleaned_data:
            user.is_active = self.cleaned_data['is_active']
        elif user.is_active is None:
            user.is_active = True
        if commit:
            user.save()
        return user

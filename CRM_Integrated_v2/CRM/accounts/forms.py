from django import forms
from django.core.exceptions import ValidationError
from django.contrib.auth.password_validation import validate_password
from .models import User, UserRole

class LoginForm(forms.Form):
    email = forms.CharField(
        label="Email Address",
        max_length=254,
        widget=forms.EmailInput(attrs={
            'class': 'form-control',
            'placeholder': 'Enter your email address',
            'autofocus': True,
            'autocomplete': 'email',
            'id': 'id_email',
        })
    )
    password = forms.CharField(
        label="Password",
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'placeholder': 'Enter password',
            'autocomplete': 'current-password',
            'id': 'id_password',
        })
    )
    remember_me = forms.BooleanField(
        required=False,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'})
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Transparently accept 'username' parameter if submitted by legacy or automated tests
        if self.data:
            if 'email' not in self.data and 'username' in self.data:
                self.data = self.data.copy()
                self.data['email'] = self.data['username']

    def clean_email(self):
        email = (self.cleaned_data.get('email') or '').strip().lower()
        if not email:
            raise ValidationError("Email address is required.")
        return email

    def clean(self):
        cleaned_data = super().clean()
        email_val = cleaned_data.get('email')
        if email_val:
            cleaned_data['username'] = email_val
        return cleaned_data

class BaseRegistrationForm(forms.ModelForm):
    password = forms.CharField(
        widget=forms.PasswordInput(attrs={'class': 'form-control', 'placeholder': 'Create password'}),
        help_text="Password must be at least 8 characters and include uppercase, lowercase, numbers, and special characters."
    )
    confirm_password = forms.CharField(
        widget=forms.PasswordInput(attrs={'class': 'form-control', 'placeholder': 'Confirm password'})
    )

    class Meta:
        model = User
        fields = ['first_name', 'last_name', 'username', 'email', 'phone']
        widgets = {
            'first_name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'First name'}),
            'last_name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Last name'}),
            'username': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Username'}),
            'email': forms.EmailInput(attrs={'class': 'form-control', 'placeholder': 'Email address'}),
            'phone': forms.TextInput(attrs={'class': 'form-control', 'placeholder': '+91 XXXXX XXXXX'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if 'username' in self.fields:
            self.fields['username'].required = False

    def clean_username(self):
        username = (self.cleaned_data.get('username') or '').strip()
        from accounts.services import generate_unique_username
        if not username:
            first = self.cleaned_data.get('first_name') or ''
            last = self.cleaned_data.get('last_name') or ''
            email = self.cleaned_data.get('email') or ''
            username = generate_unique_username(first_name=first, last_name=last, email=email)
        elif User.objects.filter(username__iexact=username).exists():
            username = generate_unique_username(first_name=username)
        return username

    def clean_email(self):
        email = self.cleaned_data.get('email')
        if not email:
            raise ValidationError("Email address is required.")
        if User.objects.filter(email__iexact=email).exists():
            raise ValidationError("A user with this email address already exists.")
        return email

    def clean(self):
        cleaned_data = super().clean()
        password = cleaned_data.get('password')
        confirm_password = cleaned_data.get('confirm_password')

        if password and confirm_password:
            if password != confirm_password:
                self.add_error('confirm_password', "Passwords do not match.")
            else:
                user_instance = User(
                    username=cleaned_data.get('username'),
                    email=cleaned_data.get('email')
                )
                try:
                    validate_password(password, user=user_instance)
                except ValidationError as e:
                    self.add_error('password', e)
        return cleaned_data

class ManagerRegistrationForm(BaseRegistrationForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if not self.instance.pk:
            self.instance.role = UserRole.SALES_HEAD

    def save(self, commit=True):
        user = super().save(commit=False)
        user.role = UserRole.SALES_HEAD
        user.set_password(self.cleaned_data['password'])
        if commit:
            user.save()
        return user

class TelecallerRegistrationForm(BaseRegistrationForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if not self.instance.pk:
            self.instance.role = UserRole.TELECALLER
            self.instance._is_self_registration = True

    def save(self, commit=True):
        user = super().save(commit=False)
        user.role = UserRole.TELECALLER
        user.set_password(self.cleaned_data['password'])
        if commit:
            user.save()
        return user


class AdminReceptionistCreateForm(forms.ModelForm):
    """Admin creates a Receptionist directly, choosing the branch."""
    branch = forms.ModelChoiceField(queryset=None, required=True, widget=forms.Select(attrs={'class': 'form-select'}))

    class Meta:
        model = User
        fields = ['first_name', 'last_name', 'username', 'email', 'phone', 'branch', 'is_active']
        widgets = {
            'first_name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'First Name'}),
            'last_name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Last Name'}),
            'username': forms.TextInput(attrs={'class': 'form-control bg-light', 'readonly': 'readonly', 'placeholder': 'Generated automatically'}),
            'email': forms.EmailInput(attrs={'class': 'form-control', 'placeholder': 'Email address'}),
            'phone': forms.TextInput(attrs={'class': 'form-control', 'placeholder': '+91 XXXXX XXXXX'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }

    def __init__(self, *args, allowed_branches=None, **kwargs):
        super().__init__(*args, **kwargs)
        if not self.instance.pk:
            self.instance.role = UserRole.RECEPTIONIST
            self.fields['is_active'].initial = True
        from branches.models import Branch
        self.fields['branch'].queryset = allowed_branches if allowed_branches is not None else Branch.objects.filter(status='Active')

    def clean_username(self):
        username = (self.cleaned_data.get('username') or '').strip()
        from accounts.services import generate_unique_username
        if not username:
            first = self.cleaned_data.get('first_name') or ''
            last = self.cleaned_data.get('last_name') or ''
            email = self.cleaned_data.get('email') or ''
            username = generate_unique_username(first_name=first, last_name=last, role=UserRole.RECEPTIONIST, email=email)
        elif User.objects.filter(username__iexact=username).exists():
            username = generate_unique_username(first_name=username, role=UserRole.RECEPTIONIST)
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
        user.role = UserRole.RECEPTIONIST
        from accounts.services import generate_unique_username
        if not user.username:
            user.username = generate_unique_username(
                first_name=user.first_name,
                last_name=user.last_name,
                role=UserRole.RECEPTIONIST,
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


class AdminCreateUserForm(forms.ModelForm):
    """
    Unified administrator form to create any team member role.
    Login ID is automatically generated and previewed in a read-only field.
    Password setup is handled securely via the welcome email setup link workflow.
    """
    role = forms.ChoiceField(
        choices=UserRole.choices,
        widget=forms.Select(attrs={'class': 'form-select', 'id': 'id_role'}),
        help_text="Application access role"
    )
    username = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={'class': 'form-control bg-light', 'readonly': 'readonly', 'placeholder': 'Generated automatically'}),
        help_text="Automatically generated from First & Last Name"
    )
    branch = forms.ModelChoiceField(
        queryset=None,
        required=False,
        widget=forms.Select(attrs={'class': 'form-select', 'id': 'id_branch'}),
        empty_label="-- Select Branch --"
    )
    counselor = forms.ModelChoiceField(
        queryset=None,
        required=False,
        widget=forms.Select(attrs={'class': 'form-select', 'id': 'id_counselor'}),
        empty_label="-- Select Counselor (Required for Telecallers) --"
    )

    class Meta:
        model = User
        fields = ['first_name', 'last_name', 'username', 'email', 'phone', 'role', 'branch', 'counselor', 'is_active']
        widgets = {
            'first_name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'First Name'}),
            'last_name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Last Name'}),
            'email': forms.EmailInput(attrs={'class': 'form-control', 'placeholder': 'user@example.com'}),
            'phone': forms.TextInput(attrs={'class': 'form-control', 'placeholder': '+91 XXXXX XXXXX'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }

    def __init__(self, *args, allowed_branches=None, **kwargs):
        super().__init__(*args, **kwargs)
        from branches.models import Branch
        self.fields['branch'].queryset = allowed_branches if allowed_branches is not None else Branch.objects.filter(status='Active')
        self.fields['counselor'].queryset = User.objects.filter(role=UserRole.COUNSELOR, is_active=True).order_by('first_name', 'username')
        if not self.instance.pk:
            self.fields['is_active'].initial = True

    def clean_username(self):
        username = (self.cleaned_data.get('username') or '').strip()
        from accounts.services import generate_unique_username
        if not username:
            first = self.cleaned_data.get('first_name') or ''
            last = self.cleaned_data.get('last_name') or ''
            role = self.cleaned_data.get('role') or None
            email = self.cleaned_data.get('email') or ''
            username = generate_unique_username(first_name=first, last_name=last, role=role, email=email)
        elif User.objects.filter(username__iexact=username).exists():
            username = generate_unique_username(first_name=username, role=self.cleaned_data.get('role'))
        return username

    def clean_email(self):
        email = (self.cleaned_data.get('email') or '').strip()
        if not email:
            raise ValidationError("Email address is required.")
        if User.objects.filter(email__iexact=email).exists():
            raise ValidationError("A user with this email address already exists.")
        return email

    def clean(self):
        cleaned_data = super().clean()
        role = cleaned_data.get('role')
        branch = cleaned_data.get('branch')
        counselor = cleaned_data.get('counselor')

        # Role specific validation
        if role == UserRole.RECEPTIONIST and not branch:
            self.add_error('branch', "A Receptionist must be assigned to an active branch.")

        if role == UserRole.BRANCH_HEAD and not branch:
            self.add_error('branch', "A Branch Head must be assigned to an active branch.")

        if role == UserRole.TELECALLER:
            if not counselor:
                self.add_error('counselor', "A Telecaller must be assigned to an active Counselor.")
            elif not counselor.is_active:
                self.add_error('counselor', "Assigned counselor must be active.")
            elif branch and counselor.branch and branch != counselor.branch:
                self.add_error('counselor', f"Counselor belongs to '{counselor.branch.name}', which does not match selected branch '{branch.name}'.")
            elif not branch and counselor.branch:
                cleaned_data['branch'] = counselor.branch

        return cleaned_data

    def save(self, commit=True, created_by=None):
        user = super().save(commit=False)
        role = self.cleaned_data.get('role')
        user.role = role

        from accounts.services import generate_unique_username
        if not user.username:
            user.username = generate_unique_username(
                first_name=user.first_name,
                last_name=user.last_name,
                role=role,
                email=user.email
            )

        user.set_unusable_password()
        user.must_change_password = True
        user.is_active = False  # Activates upon completing setup link
        user.invitation_status = 'PENDING'

        if commit:
            user.save()
            # If Sales Head, attach branch access
            if role == UserRole.SALES_HEAD and user.branch:
                from branches.models import SalesHeadBranchAccess
                SalesHeadBranchAccess.objects.get_or_create(
                    sales_head=user, branch=user.branch, defaults={'created_by': created_by}
                )
            # If Telecaller, create lead setup
            if role == UserRole.TELECALLER and user.branch:
                from leads.models import TelecallerLeadSetup
                TelecallerLeadSetup.objects.get_or_create(
                    telecaller=user,
                    branch=user.branch,
                    defaults={'assignment_percentage': 0, 'lead_count': 0, 'is_active': False}
                )

        return user





class UserProfileUpdateForm(forms.ModelForm):
    """
    Self-service profile update form for authenticated users.
    Permits editing personal details (first name, last name, email, phone)
    while strictly guarding immutable system attributes (username, role, branch, permissions).
    """
    class Meta:
        model = User
        fields = ['first_name', 'last_name', 'email', 'phone']
        widgets = {
            'first_name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'First Name'}),
            'last_name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Last Name'}),
            'email': forms.EmailInput(attrs={'class': 'form-control', 'placeholder': 'user@example.com'}),
            'phone': forms.TextInput(attrs={'class': 'form-control', 'placeholder': '+91 XXXXX XXXXX'}),
        }

    def clean_email(self):
        email = (self.cleaned_data.get('email') or '').strip()
        if not email:
            raise ValidationError("Email address cannot be empty.")
        existing = User.objects.filter(email__iexact=email).exclude(pk=self.instance.pk).first()
        if existing:
            raise ValidationError("This email address is already in use by another user.")
        return email

    def clean_phone(self):
        phone = (self.cleaned_data.get('phone') or '').strip()
        if phone:
            digits = ''.join(c for c in phone if c.isdigit())
            if len(digits) < 10 or len(digits) > 15:
                raise ValidationError("Please enter a valid phone number (10 to 15 digits).")
        return phone

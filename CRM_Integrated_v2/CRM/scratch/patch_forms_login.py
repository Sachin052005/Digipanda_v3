import os

forms_path = r"D:\CRM_Integrated_v2\CRM_Integrated_v2\CRM\accounts\forms.py"
with open(forms_path, "r", encoding="utf-8") as f:
    code = f.read()

# Replace LoginForm
old_login_form = """class LoginForm(forms.Form):
    username = forms.CharField(
        label="Username or Email",
        max_length=150,
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Enter username or email address', 'autofocus': True})
    )
    password = forms.CharField(
        label="Password",
        widget=forms.PasswordInput(attrs={'class': 'form-control', 'placeholder': 'Enter password'})
    )
    remember_me = forms.BooleanField(
        required=False,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'})
    )"""

new_login_form = """class LoginForm(forms.Form):
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
        return cleaned_data"""

if old_login_form in code:
    code = code.replace(old_login_form, new_login_form)
    with open(forms_path, "w", encoding="utf-8", newline="\n") as f:
        f.write(code)
    print("Successfully updated LoginForm in accounts/forms.py")
else:
    print("Could not find exact old_login_form match in accounts/forms.py")

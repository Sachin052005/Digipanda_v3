import os

forms_path = r"D:\CRM_Integrated_v2\CRM_Integrated_v2\CRM\accounts\forms.py"
with open(forms_path, "r", encoding="utf-8") as f:
    code = f.read()

old_clean = """    def clean_username(self):
        username = self.cleaned_data.get('username')
        if User.objects.filter(username__iexact=username).exists():
            raise ValidationError("A user with this username already exists.")
        return username"""

new_clean = """    def __init__(self, *args, **kwargs):
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
        return username"""

if old_clean in code:
    code = code.replace(old_clean, new_clean)
    with open(forms_path, "w", encoding="utf-8", newline="\n") as f:
        f.write(code)
    print("Successfully patched BaseRegistrationForm in accounts/forms.py")
else:
    print("Could not find old_clean in accounts/forms.py")

# Now patch manager_register.html and telecaller_register.html
for reg_name in ["manager_register.html", "telecaller_register.html"]:
    reg_path = os.path.join(r"D:\CRM_Integrated_v2\CRM_Integrated_v2\CRM\templates\registration", reg_name)
    with open(reg_path, "r", encoding="utf-8") as f:
        rc = f.read()
    old_user_group = """      <div class="form-group">
        <label class="form-label">Username <span class="required">*</span></label>
        {{ form.username }}
        {% if form.username.errors %}<div class="form-error">{{ form.username.errors.0 }}</div>{% endif %}
      </div>"""
    if old_user_group in rc:
        rc = rc.replace(old_user_group, "{{ form.username.as_hidden }}")
        with open(reg_path, "w", encoding="utf-8", newline="\n") as f:
            f.write(rc)
        print(f"Patched {reg_name}")
    else:
        print(f"Could not find old_user_group in {reg_name}")

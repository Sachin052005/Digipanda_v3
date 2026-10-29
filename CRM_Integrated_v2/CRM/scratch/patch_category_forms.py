path_models = r'D:\CRM_Integrated_v2\CRM_Integrated_v2\CRM\leads\models.py'
with open(path_models, 'r', encoding='utf-8') as f:
    code = f.read()

target = """    category = models.CharField(
        max_length=20,
        choices=LeadCategory.choices,
        default=LeadCategory.TRAINING,
        db_index=True,
        help_text="Segmentation: Training vs Placement"
    )"""

replacement = """    category = models.CharField(
        max_length=20,
        choices=LeadCategory.choices,
        default=LeadCategory.TRAINING,
        blank=True,
        db_index=True,
        help_text="Segmentation: Training vs Placement"
    )"""

if target.replace('\r\n', '\n') in code.replace('\r\n', '\n'):
    code = code.replace('\r\n', '\n').replace(target.replace('\r\n', '\n'), replacement.replace('\r\n', '\n'))
    with open(path_models, 'w', encoding='utf-8') as f:
        f.write(code)
    print("Updated category blank=True in models.py")
else:
    print("Target not found in models.py")

path_forms = r'D:\CRM_Integrated_v2\CRM_Integrated_v2\CRM\leads\forms.py'
with open(path_forms, 'r', encoding='utf-8') as f:
    fcode = f.read()

# Make sure LeadCategory is imported in forms.py
if 'LeadCategory' not in fcode:
    fcode = fcode.replace('from .models import Lead,', 'from .models import Lead, LeadCategory,')
    print("Imported LeadCategory in forms.py")

# Add category definition in AdminLeadForm
admin_form_target = """    channel = forms.ModelChoiceField(queryset=Channel.objects.filter(status='Active'), required=False, widget=forms.Select(attrs={'class': 'form-select'}))
    product = forms.ModelChoiceField(queryset=Product.objects.filter(status='Active'), required=False, widget=forms.Select(attrs={'class': 'form-select'}))
    branch = forms.ModelChoiceField(queryset=Branch.objects.filter(status='Active'), required=False, widget=forms.Select(attrs={'class': 'form-select'}))"""

admin_form_replacement = """    category = forms.ChoiceField(choices=LeadCategory.choices, initial=LeadCategory.TRAINING, required=False, widget=forms.Select(attrs={'class': 'form-select'}))
    channel = forms.ModelChoiceField(queryset=Channel.objects.filter(status='Active'), required=False, widget=forms.Select(attrs={'class': 'form-select'}))
    product = forms.ModelChoiceField(queryset=Product.objects.filter(status='Active'), required=False, widget=forms.Select(attrs={'class': 'form-select'}))
    branch = forms.ModelChoiceField(queryset=Branch.objects.filter(status='Active'), required=False, widget=forms.Select(attrs={'class': 'form-select'}))"""

if admin_form_target.replace('\r\n', '\n') in fcode.replace('\r\n', '\n'):
    fcode = fcode.replace('\r\n', '\n').replace(admin_form_target.replace('\r\n', '\n'), admin_form_replacement.replace('\r\n', '\n'))
    print("Added explicit category field in AdminLeadForm")
else:
    print("AdminLeadForm target not found")

# Add category field to ManagerLeadCreateForm
mgr_create_target = """    channel = forms.ModelChoiceField(queryset=Channel.objects.filter(status='Active'), required=False, widget=forms.Select(attrs={'class': 'form-select'}))
    product = forms.ModelChoiceField(queryset=Product.objects.filter(status='Active'), required=False, widget=forms.Select(attrs={'class': 'form-select'}))
    branch = forms.ModelChoiceField(queryset=Branch.objects.filter(status='Active'), required=False, widget=forms.Select(attrs={'class': 'form-select'}))"""
# ManagerLeadForm and TelecallerLeadForm also
if 'category = forms.ChoiceField' not in fcode:
    print("Warning: category field insertion needs checking")

with open(path_forms, 'w', encoding='utf-8') as f:
    f.write(fcode)

print("Finished patching forms.py")

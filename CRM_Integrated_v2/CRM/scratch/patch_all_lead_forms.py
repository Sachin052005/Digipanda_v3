import re

path_forms = r'D:\CRM_Integrated_v2\CRM_Integrated_v2\CRM\leads\forms.py'
with open(path_forms, 'r', encoding='utf-8') as f:
    fcode = f.read()

# Check all classes in forms.py that are ModelForms for Lead:
# AdminLeadForm, ManagerLeadForm, TelecallerLeadForm, ManagerLeadCreateForm, TelecallerLeadCreateForm

def patch_form_class(code, class_name):
    # Ensure category = forms.ChoiceField is present if class has product/channel/etc
    # And ensure clean_category method is present
    pattern = rf"(class {class_name}\(.*?\):[\s\S]*?)(class \w+|\Z)"
    match = re.search(pattern, code)
    if not match:
        print(f"Class {class_name} not found")
        return code

    cls_body = match.group(1)
    
    # If category field definition not in class body:
    if "category = forms.ChoiceField" not in cls_body and "class Meta" in cls_body:
        cls_body = cls_body.replace(
            "class Meta:",
            "category = forms.ChoiceField(choices=LeadCategory.choices, initial=LeadCategory.TRAINING, required=False, widget=forms.Select(attrs={'class': 'form-select'}))\n\n    class Meta:"
        )

    # If clean_category not in class body:
    if "def clean_category" not in cls_body:
        clean_method = (
            "\n    def clean_category(self):\n"
            "        cat = self.cleaned_data.get('category')\n"
            "        if not cat:\n"
            "            if hasattr(self, 'instance') and self.instance and getattr(self.instance, 'category', None):\n"
            "                return self.instance.category\n"
            "            return LeadCategory.TRAINING\n"
            "        return cat\n"
        )
        # Insert before def save or at the end of class
        if "def save(" in cls_body:
            cls_body = cls_body.replace("def save(", clean_method + "\n    def save(")
        elif "def clean(" in cls_body:
            cls_body = cls_body.replace("def clean(", clean_method + "\n    def clean(")
        else:
            cls_body += clean_method

    code = code[:match.start(1)] + cls_body + code[match.end(1):]
    print(f"Patched {class_name}")
    return code

for cls in ['AdminLeadForm', 'ManagerLeadForm', 'TelecallerLeadForm', 'ManagerLeadCreateForm', 'TelecallerLeadCreateForm']:
    fcode = patch_form_class(fcode, cls)

with open(path_forms, 'w', encoding='utf-8') as f:
    f.write(fcode)

print("All lead forms patched with clean_category and optional category choice field!")

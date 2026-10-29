from django import forms
from django.core.exceptions import ValidationError
from accounts.models import User, UserRole
from accounts.permissions import get_accessible_branch_ids
from branches.models import Branch
from lead_channels.models import Channel
from products.models import Product
from .models import Lead, LeadStatus, LeadCategory
from .duplicates import normalize_phone, normalize_email, find_duplicate_lead

def infer_lead_branch(user=None, manager=None, telecaller=None, request=None, current_branch=None):
    """
    Infers lead branch following hierarchy:
    1. Explicit / Current branch on lead
    2. Assigned Telecaller's branch
    3. Assigned Manager's branch
    4. Current user's branch (if Manager or Telecaller)
    5. Active branch in Admin session if available
    6. Primary active Branch in database
    """
    if current_branch:
        return current_branch
    if telecaller and getattr(telecaller, 'branch', None):
        return telecaller.branch
    if manager and getattr(manager, 'branch', None):
        return manager.branch
    if user and getattr(user, 'branch', None):
        return user.branch
    if request and hasattr(request, 'session'):
        active_branch_id = request.session.get('active_branch_id')
        if active_branch_id:
            b = Branch.objects.filter(pk=active_branch_id, status='Active').first()
            if b:
                return b
    return Branch.objects.filter(status='Active').first()

class AdminLeadForm(forms.ModelForm):
    assigned_manager = forms.ModelChoiceField(
        queryset=User.objects.filter(role=UserRole.SALES_HEAD, is_active=True),
        required=False,
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    assigned_telecaller = forms.ModelChoiceField(
        queryset=User.objects.filter(role=UserRole.TELECALLER, is_active=True),
        required=False,
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    category = forms.ChoiceField(choices=LeadCategory.choices, initial=LeadCategory.TRAINING, required=False, widget=forms.Select(attrs={'class': 'form-select'}))
    channel = forms.ModelChoiceField(queryset=Channel.objects.filter(status='Active'), required=False, widget=forms.Select(attrs={'class': 'form-select'}))
    product = forms.ModelChoiceField(queryset=Product.objects.filter(status='Active'), required=False, widget=forms.Select(attrs={'class': 'form-select'}))
    branch = forms.ModelChoiceField(queryset=Branch.objects.filter(status='Active'), required=False, widget=forms.Select(attrs={'class': 'form-select'}))

    
    def clean_category(self):
        cat = self.cleaned_data.get('category')
        if not cat:
            if hasattr(self, 'instance') and self.instance and getattr(self.instance, 'category', None):
                return self.instance.category
            return LeadCategory.TRAINING
        return cat
    class Meta:
        model = Lead
        fields = [
            'name', 'phone', 'email', 'alternate_phone', 'channel', 'status', 'category',
            'assigned_manager', 'assigned_telecaller', 'product', 'branch', 'notes'
        ]
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Full name'}),
            'phone': forms.TextInput(attrs={'class': 'form-control', 'placeholder': '+91 XXXXX XXXXX'}),
            'email': forms.EmailInput(attrs={'class': 'form-control', 'placeholder': 'email@domain.com'}),
            'alternate_phone': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Optional alternate phone'}),
            'status': forms.Select(attrs={'class': 'form-select'}),
            'category': forms.Select(attrs={'class': 'form-select'}),
            'notes': forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': 'Inquiry details, background, course interest...'}),
        }

    def clean_phone(self):
        raw_phone = self.cleaned_data.get('phone')
        if not raw_phone:
            return raw_phone
        clean_phone = normalize_phone(raw_phone)
        if clean_phone and not clean_phone.startswith('NoPhone-'):
            if len(clean_phone) < 7:
                raise ValidationError("Please enter a valid phone number (at least 7 digits).")
            # Only validate duplicates during edits (when self.instance.pk exists)
            # On creation, admin_lead_create delegates to handle_incoming_lead_duplicate.
            if self.instance and self.instance.pk:
                conflict = find_duplicate_lead(phone=clean_phone, exclude_id=self.instance.pk)
                if conflict:
                    raise ValidationError(
                        f"Phone number '{raw_phone}' already belongs to existing Lead #{conflict.pk} ('{conflict.name}')."
                    )
        return clean_phone

    def clean_alternate_phone(self):
        raw_alt = self.cleaned_data.get('alternate_phone')
        if not raw_alt:
            return ''
        clean_alt = normalize_phone(raw_alt)
        if not clean_alt:
            return ''
        if len(clean_alt) < 7 and not clean_alt.startswith('NoPhone-'):
            raise ValidationError("Please enter a valid alternate phone number.")
        # Check if identical to primary phone on this lead
        primary = self.cleaned_data.get('phone') or getattr(self.instance, 'phone', '')
        if primary and normalize_phone(primary) == clean_alt:
            raise ValidationError("Alternate phone cannot be identical to the primary phone.")
        exclude_id = self.instance.pk if self.instance else None
        conflict = find_duplicate_lead(phone=clean_alt, exclude_id=exclude_id)
        if conflict:
            raise ValidationError(
                f"Alternate phone '{raw_alt}' already matches Lead #{conflict.pk} ('{conflict.name}')."
            )
        return clean_alt

    def clean_email(self):
        raw_email = self.cleaned_data.get('email')
        if not raw_email:
            return ''
        clean_email = normalize_email(raw_email)
        if not clean_email:
            return ''
        exclude_id = self.instance.pk if self.instance else None
        if exclude_id:
            conflict = Lead.objects.filter(email__iexact=clean_email).exclude(pk=exclude_id).first()
            if conflict:
                raise ValidationError(
                    f"Email '{raw_email}' already belongs to existing Lead #{conflict.pk} ('{conflict.name}')."
                )
        return clean_email

    def clean(self):
        cleaned_data = super().clean()
        mgr = cleaned_data.get('assigned_manager')
        tc = cleaned_data.get('assigned_telecaller')
        if mgr and tc:
            if tc.branch_id and tc.branch_id not in get_accessible_branch_ids(mgr):
                raise ValidationError({
                    'assigned_telecaller': f"Telecaller '{tc.username}' belongs to a branch not managed by '{mgr.username}'."
                })
        if not cleaned_data.get('branch'):
            current_b = getattr(self.instance, 'branch', None) if self.instance else None
            cleaned_data['branch'] = infer_lead_branch(
                manager=mgr,
                telecaller=tc,
                current_branch=current_b
            )
        return cleaned_data

    def save(self, commit=True):
        lead = super().save(commit=False)
        lead.assigned_sales_head = self.cleaned_data.get('assigned_manager')
        if not lead.branch:
            lead.branch = infer_lead_branch(
                manager=lead.assigned_manager,
                telecaller=lead.assigned_telecaller,
                current_branch=getattr(lead, 'branch', None)
            )
        if commit:
            lead.save()
        return lead

class ManagerLeadForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        manager = kwargs.pop('manager', None)
        self.manager = manager
        super().__init__(*args, **kwargs)
        if manager:
            self.fields['assigned_telecaller'].queryset = User.objects.filter(
                role=UserRole.TELECALLER,
                branch_id__in=get_accessible_branch_ids(manager),
                is_active=True
            )

    assigned_telecaller = forms.ModelChoiceField(
        queryset=User.objects.none(),
        required=False,
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    product = forms.ModelChoiceField(queryset=Product.objects.filter(status='Active'), required=False, widget=forms.Select(attrs={'class': 'form-select'}))
    branch = forms.ModelChoiceField(queryset=Branch.objects.filter(status='Active'), required=False, widget=forms.Select(attrs={'class': 'form-select'}))

    
    def clean_category(self):
        cat = self.cleaned_data.get('category')
        if not cat:
            if hasattr(self, 'instance') and self.instance and getattr(self.instance, 'category', None):
                return self.instance.category
            return LeadCategory.TRAINING
        return cat
    class Meta:
        model = Lead
        fields = ['status', 'category', 'assigned_telecaller', 'product', 'branch', 'alternate_phone', 'notes']
        widgets = {
            'status': forms.Select(attrs={'class': 'form-select'}),
            'category': forms.Select(attrs={'class': 'form-select'}),
            'alternate_phone': forms.TextInput(attrs={'class': 'form-control'}),
            'notes': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
        }

    def clean_alternate_phone(self):
        raw_alt = self.cleaned_data.get('alternate_phone')
        if not raw_alt:
            return ''
        clean_alt = normalize_phone(raw_alt)
        if not clean_alt:
            return ''
        if len(clean_alt) < 7 and not clean_alt.startswith('NoPhone-'):
            raise ValidationError("Please enter a valid alternate phone number.")
        primary = getattr(self.instance, 'phone', '')
        if primary and normalize_phone(primary) == clean_alt:
            raise ValidationError("Alternate phone cannot be identical to the primary phone.")
        exclude_id = self.instance.pk if self.instance else None
        conflict = find_duplicate_lead(phone=clean_alt, exclude_id=exclude_id)
        if conflict:
            raise ValidationError(
                f"Alternate phone '{raw_alt}' already matches Lead #{conflict.pk} ('{conflict.name}')."
            )
        return clean_alt

    def clean(self):
        cleaned_data = super().clean()
        tc = cleaned_data.get('assigned_telecaller')
        if not cleaned_data.get('branch'):
            current_b = getattr(self.instance, 'branch', None) if self.instance else None
            cleaned_data['branch'] = infer_lead_branch(
                user=self.manager,
                manager=self.manager,
                telecaller=tc,
                current_branch=current_b
            )
        return cleaned_data

    def save(self, commit=True):
        lead = super().save(commit=False)
        if not lead.branch:
            lead.branch = infer_lead_branch(
                user=self.manager,
                manager=self.manager,
                telecaller=lead.assigned_telecaller,
                current_branch=getattr(lead, 'branch', None)
            )
        if commit:
            lead.save()
        return lead

class TelecallerLeadForm(forms.ModelForm):
    
    def clean_category(self):
        cat = self.cleaned_data.get('category')
        if not cat:
            if hasattr(self, 'instance') and self.instance and getattr(self.instance, 'category', None):
                return self.instance.category
            return LeadCategory.TRAINING
        return cat
    class Meta:
        model = Lead
        fields = ['status', 'category', 'alternate_phone', 'email', 'notes']
        widgets = {
            'status': forms.Select(attrs={'class': 'form-select'}),
            'category': forms.Select(attrs={'class': 'form-select'}),
            'alternate_phone': forms.TextInput(attrs={'class': 'form-control'}),
            'email': forms.EmailInput(attrs={'class': 'form-control'}),
            'notes': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
        }

    def clean_status(self):
        status = self.cleaned_data.get('status')
        if status in (LeadStatus.ENROLLED, 'Enrolled', 'ENROLLED'):
            raise forms.ValidationError("Permission Denied: Telecallers are not authorized to mark a lead as 'Enrolled'.")
        return status

    def clean_alternate_phone(self):
        raw_alt = self.cleaned_data.get('alternate_phone')
        if not raw_alt:
            return ''
        clean_alt = normalize_phone(raw_alt)
        if not clean_alt:
            return ''
        if len(clean_alt) < 7 and not clean_alt.startswith('NoPhone-'):
            raise ValidationError("Please enter a valid alternate phone number.")
        primary = getattr(self.instance, 'phone', '')
        if primary and normalize_phone(primary) == clean_alt:
            raise ValidationError("Alternate phone cannot be identical to the primary phone.")
        exclude_id = self.instance.pk if self.instance else None
        conflict = find_duplicate_lead(phone=clean_alt, exclude_id=exclude_id)
        if conflict:
            raise ValidationError(
                f"Alternate phone '{raw_alt}' already matches Lead #{conflict.pk} ('{conflict.name}')."
            )
        return clean_alt

    def clean_email(self):
        raw_email = self.cleaned_data.get('email')
        if not raw_email:
            return ''
        clean_email = normalize_email(raw_email)
        if not clean_email:
            return ''
        exclude_id = self.instance.pk if self.instance else None
        if exclude_id:
            conflict = Lead.objects.filter(email__iexact=clean_email).exclude(pk=exclude_id).first()
            if conflict:
                raise ValidationError(
                    f"Email '{raw_email}' already belongs to existing Lead #{conflict.pk} ('{conflict.name}')."
                )
        return clean_email

class ManagerLeadCreateForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        manager = kwargs.pop('manager', None)
        self.manager = manager
        super().__init__(*args, **kwargs)
        if manager:
            self.fields['assigned_telecaller'].queryset = User.objects.filter(
                role=UserRole.TELECALLER,
                branch_id__in=get_accessible_branch_ids(manager),
                is_active=True
            )

    assigned_telecaller = forms.ModelChoiceField(
        queryset=User.objects.none(),
        required=False,
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    category = forms.ChoiceField(choices=LeadCategory.choices, initial=LeadCategory.TRAINING, required=False, widget=forms.Select(attrs={'class': 'form-select'}))
    channel = forms.ModelChoiceField(queryset=Channel.objects.filter(status='Active'), required=False, widget=forms.Select(attrs={'class': 'form-select'}))
    product = forms.ModelChoiceField(queryset=Product.objects.filter(status='Active'), required=False, widget=forms.Select(attrs={'class': 'form-select'}))
    branch = forms.ModelChoiceField(queryset=Branch.objects.filter(status='Active'), required=False, widget=forms.Select(attrs={'class': 'form-select'}))

    
    def clean_category(self):
        cat = self.cleaned_data.get('category')
        if not cat:
            if hasattr(self, 'instance') and self.instance and getattr(self.instance, 'category', None):
                return self.instance.category
            return LeadCategory.TRAINING
        return cat
    class Meta:
        model = Lead
        fields = [
            'name', 'phone', 'email', 'alternate_phone', 'channel', 'status', 'category',
            'assigned_telecaller', 'product', 'branch', 'notes'
        ]
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Full name'}),
            'phone': forms.TextInput(attrs={'class': 'form-control', 'placeholder': '+91 XXXXX XXXXX'}),
            'email': forms.EmailInput(attrs={'class': 'form-control', 'placeholder': 'email@domain.com'}),
            'alternate_phone': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Optional alternate phone'}),
            'status': forms.Select(attrs={'class': 'form-select'}),
            'category': forms.Select(attrs={'class': 'form-select'}),
            'notes': forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': 'Inquiry details, background...'}),
        }

    def clean_phone(self):
        raw = self.cleaned_data.get('phone')
        clean = normalize_phone(raw) if raw else ''
        return clean or raw

    def clean_alternate_phone(self):
        raw = self.cleaned_data.get('alternate_phone')
        if not raw:
            return ''
        clean = normalize_phone(raw)
        primary = self.cleaned_data.get('phone')
        if primary and normalize_phone(primary) == clean:
            raise ValidationError("Alternate phone cannot be identical to the primary phone.")
        return clean

    def clean_email(self):
        raw = self.cleaned_data.get('email')
        return normalize_email(raw) if raw else ''

    def clean(self):
        cleaned_data = super().clean()
        tc = cleaned_data.get('assigned_telecaller')
        if not cleaned_data.get('branch'):
            cleaned_data['branch'] = infer_lead_branch(
                user=self.manager,
                manager=self.manager,
                telecaller=tc
            )
        return cleaned_data

    def save(self, commit=True):
        lead = super().save(commit=False)
        if not lead.branch:
            lead.branch = infer_lead_branch(
                user=self.manager,
                manager=self.manager,
                telecaller=lead.assigned_telecaller
            )
        if commit:
            lead.save()
        return lead

class TelecallerLeadCreateForm(forms.ModelForm):
    channel = forms.ModelChoiceField(queryset=Channel.objects.filter(status='Active'), required=False, widget=forms.Select(attrs={'class': 'form-select'}))
    product = forms.ModelChoiceField(queryset=Product.objects.filter(status='Active'), required=False, widget=forms.Select(attrs={'class': 'form-select'}))

    
    def clean_category(self):
        cat = self.cleaned_data.get('category')
        if not cat:
            if hasattr(self, 'instance') and self.instance and getattr(self.instance, 'category', None):
                return self.instance.category
            return LeadCategory.TRAINING
        return cat
    class Meta:
        model = Lead
        fields = [
            'name', 'phone', 'email', 'alternate_phone', 'channel', 'product', 'category', 'notes'
        ]
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Full name'}),
            'phone': forms.TextInput(attrs={'class': 'form-control', 'placeholder': '+91 XXXXX XXXXX'}),
            'email': forms.EmailInput(attrs={'class': 'form-control', 'placeholder': 'email@domain.com'}),
            'alternate_phone': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Optional alternate phone'}),
            'category': forms.Select(attrs={'class': 'form-select'}),
            'notes': forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': 'Inquiry details, notes...'}),
        }

    def clean_phone(self):
        raw = self.cleaned_data.get('phone')
        clean = normalize_phone(raw) if raw else ''
        return clean or raw

    def clean_alternate_phone(self):
        raw = self.cleaned_data.get('alternate_phone')
        if not raw:
            return ''
        clean = normalize_phone(raw)
        primary = self.cleaned_data.get('phone')
        if primary and normalize_phone(primary) == clean:
            raise ValidationError("Alternate phone cannot be identical to the primary phone.")
        return clean

    def clean_email(self):
        raw = self.cleaned_data.get('email')
        return normalize_email(raw) if raw else ''

class LeadImportForm(forms.Form):
    file = forms.FileField(
        widget=forms.FileInput(attrs={'class': 'form-control', 'accept': '.csv, .xlsx'}),
        help_text="Upload .csv or .xlsx with headers: Name, Phone, Email, Channel, Product, Notes"
    )

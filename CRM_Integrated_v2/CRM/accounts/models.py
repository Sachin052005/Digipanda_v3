from django.contrib.auth.models import AbstractUser, UserManager
from django.db import models
from django.core.exceptions import ValidationError

class UserRole(models.TextChoices):
    SUPERADMIN = 'SUPERADMIN', 'Superadmin'
    ADMIN = 'ADMIN', 'Admin'
    SALES_HEAD = 'SALES_HEAD', 'Sales Head'
    BRANCH_HEAD = 'BRANCH_HEAD', 'Branch Head'
    BRANCH_ADMIN = 'BRANCH_ADMIN', 'Branch Admin'
    COUNSELOR = 'COUNSELOR', 'Counselor'
    TELECALLER = 'TELECALLER', 'Telecaller'
    RECEPTIONIST = 'RECEPTIONIST', 'Receptionist'
    ACCOUNTANT = 'ACCOUNTANT', 'Accountant'
    FINANCE_HEAD = 'FINANCE_HEAD', 'Finance Head'

class CustomUserManager(UserManager):
    """
    Custom user manager ensuring superusers are automatically provisioned
    with the authoritative SUPERADMIN role rather than defaulting to TELECALLER.
    """
    def create_superuser(self, username, email=None, password=None, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        extra_fields.setdefault('role', UserRole.SUPERADMIN)
        if extra_fields.get('is_staff') is not True:
            raise ValueError('Superuser must have is_staff=True.')
        if extra_fields.get('is_superuser') is not True:
            raise ValueError('Superuser must have is_superuser=True.')
        return super().create_superuser(username, email, password, **extra_fields)

class User(AbstractUser):
    role = models.CharField(
        max_length=20,
        choices=UserRole.choices,
        default=UserRole.TELECALLER,
        help_text="Application access role"
    )
    objects = CustomUserManager()
    phone = models.CharField(max_length=20, blank=True, default='')
    branch = models.ForeignKey(
        'branches.Branch',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='users'
    )
    counselor = models.ForeignKey(
        'self',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='assigned_telecallers',
        limit_choices_to={'role': UserRole.COUNSELOR}
    )
    must_change_password = models.BooleanField(
        default=False,
        help_text="Requires user to change password on first login after automated credential creation"
    )
    invitation_sent_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Timestamp when the welcome/invitation email was last sent"
    )
    invitation_status = models.CharField(
        max_length=20,
        choices=[
            ('PENDING', 'Pending Setup'),
            ('SENT', 'Invitation Sent'),
            ('FAILED', 'Delivery Failed'),
            ('ACTIVATED', 'Activated'),
        ],
        default='PENDING',
        help_text="Onboarding invitation status"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['username']

    def __str__(self):
        full = self.get_full_name()
        return f"{full} ({self.username})" if full else self.username

    @property
    def is_superadmin_user(self):
        return self.is_superuser or self.role == UserRole.SUPERADMIN

    @property
    def is_admin_user(self):
        return self.role in (UserRole.ADMIN, UserRole.SUPERADMIN) or self.is_superuser

    @property
    def is_sales_head_user(self):
        return self.role == UserRole.SALES_HEAD

    @property
    def is_branch_head_user(self):
        return self.role == UserRole.BRANCH_HEAD

    @property
    def is_branch_admin_user(self):
        return self.role == UserRole.BRANCH_ADMIN

    @property
    def is_counselor_user(self):
        return self.role == UserRole.COUNSELOR

    @property
    def is_telecaller_user(self):
        return (
            self.role == UserRole.TELECALLER
            and not self.is_superuser
            and not self.is_staff
            and self.role not in (UserRole.ADMIN, UserRole.SUPERADMIN)
        )

    @property
    def is_receptionist_user(self):
        return self.role == UserRole.RECEPTIONIST

    @property
    def is_accountant_user(self):
        return self.role == UserRole.ACCOUNTANT

    @property
    def is_finance_head_user(self):
        return self.role == UserRole.FINANCE_HEAD

    @classmethod
    def get_telecallers_queryset(cls):
        return cls.objects.filter(
            role=UserRole.TELECALLER,
            is_superuser=False,
            is_staff=False
        ).exclude(role__in=[UserRole.ADMIN, UserRole.SUPERADMIN])

    @property
    def display_role(self):
        if self.is_superuser or self.role == UserRole.SUPERADMIN:
            return "Superadmin"
        return dict(UserRole.choices).get(self.role, self.role)

    def save(self, *args, **kwargs):
        # Ensure Superadmins are never saved with TELECALLER default
        if self.is_superuser:
            if not self.role or self.role == UserRole.TELECALLER:
                self.role = UserRole.SUPERADMIN
        elif self.role == UserRole.SUPERADMIN:
            self.is_superuser = True
            self.is_staff = True
        super().save(*args, **kwargs)

    def clean(self):
        super().clean()
        if self.role in (UserRole.RECEPTIONIST, UserRole.BRANCH_ADMIN):
            if not self.branch_id:
                raise ValidationError({'branch': "A Receptionist must be assigned to a branch."})
        if self.role == UserRole.TELECALLER:
            if not getattr(self, '_is_self_registration', False):
                if not self.counselor_id:
                    raise ValidationError({'counselor': "A Telecaller must be assigned to a Counselor."})
            if self.counselor_id:
                if self.counselor_id == self.id:
                    raise ValidationError({'counselor': "A user cannot be their own counselor."})
                if self.counselor.role != UserRole.COUNSELOR:
                    raise ValidationError({'counselor': "Assigned counselor must have the COUNSELOR role."})
                if not self.counselor.is_active and not self.pk:
                    raise ValidationError({'counselor': "Assigned counselor must be active."})
                if self.branch_id and self.counselor.branch_id and self.branch_id != self.counselor.branch_id:
                    raise ValidationError({'counselor': "Assigned counselor must belong to the same branch as the telecaller."})
        elif self.counselor_id:
            raise ValidationError({'counselor': "Only Telecallers can have an assigned counselor."})



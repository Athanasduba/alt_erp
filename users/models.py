from django.contrib.auth.models import AbstractUser
from django.db import models
from django.core.exceptions import ValidationError

class User(AbstractUser):
    ROLE_CHOICES = [
        ('ADMIN', 'Admin'),
        ('MANAGER', 'Manager'),
        ('OFFICER', 'Officer in Charge'),
        ('STORE', 'Store'),
        ('ACCOUNTANT', 'Accountant'),
        ('AGENT', 'Agent'),
        ('SALES', 'Sales Officer'),
        ('CARE', 'Customer Care'),
    ]

    first_name = models.CharField(max_length=50)
    last_name = models.CharField(max_length=50)

    # ✅ Email is optional and not unique
    email = models.EmailField(blank=True, null=True, unique=False)

    phone_number = models.CharField(max_length=20, blank=True, null=True)

    # Default role ensures new users always have a role
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='AGENT')

    warehouses = models.ManyToManyField(
        'warehouses.Warehouse',
        blank=True,
        related_name='assigned_users',
        help_text="Warehouses linked to this user"
    )

    is_active = models.BooleanField(default=True)
    is_verified = models.BooleanField(default=False)

    def save(self, *args, **kwargs):
        """
        Ensure that ADMIN users and superusers can never be deactivated.
        """
        if self.is_superuser or self.role == 'ADMIN':
            self.is_active = True
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.username} ({self.role})"

    @property
    def full_name(self):
        return f"{self.first_name} {self.last_name}"

    # ✅ Role helper properties
    @property
    def is_admin(self):
        return self.role == 'ADMIN'

    @property
    def is_manager(self):
        return self.role == 'MANAGER'

    @property
    def is_officer(self):
        return self.role == 'OFFICER'

    @property
    def is_store(self):
        return self.role == 'STORE'

    @property
    def is_accountant(self):
        return self.role == 'ACCOUNTANT'

    @property
    def is_agent(self):
        return self.role == 'AGENT'

    @property
    def is_sales(self):
        return self.role == 'SALES'

    @property
    def is_care(self):
        return self.role == 'CARE'

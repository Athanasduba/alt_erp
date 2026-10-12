from django.db import models
from django.conf import settings
from warehouses.models import Warehouse

class Agent(models.Model):
    AGENT_TYPE_CHOICES = [
        ("INDIVIDUAL", "Individual"),
        ("COMPANY", "Company"),
    ]

    user = models.OneToOneField(   # ✅ link to your existing User model
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="agent_profile",
        null=True,    # ✅ allow nulls for existing rows
        blank=True    # ✅ allow blanks in forms
    )
    agent_type = models.CharField(
        max_length=20,
        choices=AGENT_TYPE_CHOICES,
        default="INDIVIDUAL"
    )
    warehouse = models.ForeignKey(
        Warehouse,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="agents"
    )
    supervisor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        limit_choices_to={"role": "MANAGER"},
        related_name="supervised_agents"
    )
    created_on = models.DateTimeField(auto_now_add=True)

    @property
    def display_name(self):
        """Return a human-readable name for the agent."""
        if hasattr(self, "individual_details") and self.individual_details:
            return self.individual_details.full_name
        elif hasattr(self, "company_details") and self.company_details:
            return self.company_details.company_name
        elif self.user:
            return self.user.username
        return "Unnamed Agent"

    def __str__(self):
        # ✅ handle case where user is null
        return f"{self.agent_type} Agent ({self.display_name})"


class IndividualAgent(models.Model):
    agent = models.OneToOneField(Agent, on_delete=models.CASCADE, related_name="individual_details")
    national_id = models.CharField(max_length=50, help_text="NIDA or Driving License")
    full_name = models.CharField(max_length=150)
    mobile_phone = models.CharField(max_length=20)
    office_location = models.CharField(max_length=255)
    business_license_number = models.CharField(max_length=50)
    email = models.EmailField(blank=True, null=True)
    license_upload = models.FileField(upload_to="agents/licenses/")
    contract_upload = models.FileField(upload_to="agents/contracts/")

    def __str__(self):
        return f"{self.full_name} ({self.national_id})"


class CompanyAgent(models.Model):
    agent = models.OneToOneField(Agent, on_delete=models.CASCADE, related_name="company_details")
    company_name = models.CharField(max_length=255)
    company_inc_number = models.CharField(max_length=100, help_text="BRELA INC Number")
    tin = models.CharField(max_length=50)
    business_license_number = models.CharField(max_length=50)
    representative_names = models.CharField(max_length=255)
    mobile_number = models.CharField(max_length=20)
    office_phone = models.CharField(max_length=20, blank=True, null=True)
    email = models.EmailField(blank=True, null=True)
    office_location = models.CharField(max_length=255)
    license_upload = models.FileField(upload_to="agents/licenses/")
    incorporation_upload = models.FileField(upload_to="agents/incorporation/")
    contract_upload = models.FileField(upload_to="agents/contracts/")

    def __str__(self):
        return f"{self.company_name} ({self.company_inc_number})"

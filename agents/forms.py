from django import forms
from .models import Agent, IndividualAgent, CompanyAgent

class AgentForm(forms.ModelForm):
    username = forms.CharField(
        label="Username",
        max_length=150,
        required=True,
        widget=forms.TextInput(attrs={"class": "form-control", "placeholder": "Enter username"})
    )
    new_password = forms.CharField(
        label="Password",
        max_length=128,
        required=False,
        widget=forms.PasswordInput(attrs={"class": "form-control", "placeholder": "Enter password"}),
        help_text="Leave blank to keep current password"
    )

    class Meta:
        model = Agent
        fields = ["agent_type", "warehouse", "supervisor"]
        widgets = {
            "agent_type": forms.Select(attrs={"class": "form-select"}),
            "warehouse": forms.Select(attrs={"class": "form-select"}),
            "supervisor": forms.Select(attrs={"class": "form-select"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.user:
            self.fields["username"].initial = self.instance.user.username


class IndividualAgentForm(forms.ModelForm):
    class Meta:
        model = IndividualAgent
        exclude = ["agent"]
        widgets = {
            "national_id": forms.TextInput(attrs={"class": "form-control"}),
            "full_name": forms.TextInput(attrs={"class": "form-control"}),
            "mobile_phone": forms.TextInput(attrs={"class": "form-control"}),
            "office_location": forms.TextInput(attrs={"class": "form-control"}),
            "business_license_number": forms.TextInput(attrs={"class": "form-control"}),
            "email": forms.EmailInput(attrs={"class": "form-control"}),
            "license_upload": forms.ClearableFileInput(attrs={"class": "form-control-file"}),
            "contract_upload": forms.ClearableFileInput(attrs={"class": "form-control-file"}),
        }


class CompanyAgentForm(forms.ModelForm):
    class Meta:
        model = CompanyAgent
        exclude = ["agent"]
        widgets = {
            "company_name": forms.TextInput(attrs={"class": "form-control"}),
            "company_inc_number": forms.TextInput(attrs={"class": "form-control"}),
            "tin": forms.TextInput(attrs={"class": "form-control"}),
            "business_license_number": forms.TextInput(attrs={"class": "form-control"}),
            "representative_names": forms.TextInput(attrs={"class": "form-control"}),
            "mobile_number": forms.TextInput(attrs={"class": "form-control"}),
            "office_phone": forms.TextInput(attrs={"class": "form-control"}),
            "email": forms.EmailInput(attrs={"class": "form-control"}),
            "office_location": forms.TextInput(attrs={"class": "form-control"}),
            "license_upload": forms.ClearableFileInput(attrs={"class": "form-control-file"}),
            "incorporation_upload": forms.ClearableFileInput(attrs={"class": "form-control-file"}),
            "contract_upload": forms.ClearableFileInput(attrs={"class": "form-control-file"}),
        }

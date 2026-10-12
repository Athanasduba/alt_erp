from django.contrib import admin
from django import forms
from django.contrib.auth.hashers import make_password
from django.contrib.auth import get_user_model
from .models import Agent, IndividualAgent, CompanyAgent

User = get_user_model()


class AgentAdminForm(forms.ModelForm):
    # Extra fields for linked User
    username = forms.CharField(required=True)
    new_password = forms.CharField(required=False, widget=forms.PasswordInput)

    class Meta:
        model = Agent
        fields = ["agent_type", "warehouse", "supervisor"]  # ✅ only Agent fields

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.user:
            self.fields["username"].initial = self.instance.user.username


@admin.register(Agent)
class AgentAdmin(admin.ModelAdmin):
    form = AgentAdminForm
    list_display = ("get_username", "agent_type", "warehouse", "supervisor", "created_on")
    search_fields = ("user__username", "agent_type")
    list_filter = ("agent_type", "warehouse", "supervisor")

    def get_username(self, obj):
        return obj.user.username
    get_username.short_description = "Username"

    def save_model(self, request, obj, form, change):
        username = form.cleaned_data.get("username")
        new_password = form.cleaned_data.get("new_password")

        if not obj.user_id:
            # Create linked User if new Agent
            user = User.objects.create(
                username=username,
                password=make_password(new_password) if new_password else None,
            )
            obj.user = user
        else:
            # Update linked User if editing
            obj.user.username = username
            if new_password:
                obj.user.password = make_password(new_password)
            obj.user.save()

        super().save_model(request, obj, form, change)

        # Save related details depending on agent_type
        if obj.agent_type == "INDIVIDUAL":
            IndividualAgent.objects.update_or_create(
                agent=obj,
                defaults={
                    "national_id": form.cleaned_data.get("national_id"),
                    "full_name": form.cleaned_data.get("full_name"),
                    "mobile_phone": form.cleaned_data.get("mobile_phone"),
                    "office_location": form.cleaned_data.get("office_location"),
                    "business_license_number": form.cleaned_data.get("business_license_number"),
                    "email": form.cleaned_data.get("email"),
                    "license_upload": form.cleaned_data.get("license_upload"),
                    "contract_upload": form.cleaned_data.get("contract_upload"),
                }
            )
        elif obj.agent_type == "COMPANY":
            CompanyAgent.objects.update_or_create(
                agent=obj,
                defaults={
                    "company_name": form.cleaned_data.get("company_name"),
                    "company_inc_number": form.cleaned_data.get("company_inc_number"),
                    "tin": form.cleaned_data.get("tin"),
                    "business_license_number": form.cleaned_data.get("business_license_number"),
                    "representative_names": form.cleaned_data.get("representative_names"),
                    "mobile_number": form.cleaned_data.get("mobile_number"),
                    "office_phone": form.cleaned_data.get("office_phone"),
                    "email": form.cleaned_data.get("email"),
                    "office_location": form.cleaned_data.get("office_location"),
                    "license_upload": form.cleaned_data.get("license_upload"),
                    "incorporation_upload": form.cleaned_data.get("incorporation_upload"),
                    "contract_upload": form.cleaned_data.get("contract_upload"),
                }
            )

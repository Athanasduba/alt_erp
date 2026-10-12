from django import forms
from .models import Customer, InstallmentPlan, LeasePlan
from users.models import User
from django.utils.timezone import now

# -------------------------------
# Customer Form
# -------------------------------
class CustomerForm(forms.ModelForm):
    class Meta:
        model = Customer
        fields = [
            "onboarding_type",
            "full_name",
            "mobile_number",
            "nearest_warehouse",
            "motorcycle",
            "agent",
            "agent_commission_percent",
            "per_initial_deposit_commission",   # ✅ new field
            "contract",
            "guarantor1_name",
            "guarantor1_mobile",
            "guarantor1_address",
            "guarantor1_national_id",
            "guarantor2_name",
            "guarantor2_mobile",
            "guarantor2_address",
            "guarantor2_national_id",
            "payment_model",
            "cash_amount",
            "officer_in_charge",
        ]
        widgets = {
            "onboarding_type": forms.Select(attrs={"class": "form-select", "id": "id_onboarding_type"}),
            "full_name": forms.TextInput(attrs={"class": "form-control"}),
            "mobile_number": forms.TextInput(attrs={"class": "form-control"}),
            "nearest_warehouse": forms.Select(attrs={"class": "form-select"}),
            "motorcycle": forms.Select(attrs={"class": "form-select", "id": "id_motorcycle"}),
            "agent": forms.Select(attrs={"class": "form-select", "id": "id_agent"}),
            "agent_commission_percent": forms.NumberInput(attrs={"class": "form-control", "id": "id_agent_commission_percent"}),
            "per_initial_deposit_commission": forms.NumberInput(attrs={
                "class": "form-control",
                "id": "id_per_initial_deposit_commission",
                "readonly": "readonly"
            }),
            "contract": forms.FileInput(attrs={"class": "form-control"}),
            "guarantor1_name": forms.TextInput(attrs={"class": "form-control"}),
            "guarantor1_mobile": forms.TextInput(attrs={"class": "form-control"}),
            "guarantor1_address": forms.Textarea(attrs={"class": "form-control", "rows": 2}),
            "guarantor1_national_id": forms.TextInput(attrs={"class": "form-control"}),
            "guarantor2_name": forms.TextInput(attrs={"class": "form-control"}),
            "guarantor2_mobile": forms.TextInput(attrs={"class": "form-control"}),
            "guarantor2_address": forms.Textarea(attrs={"class": "form-control", "rows": 2}),
            "guarantor2_national_id": forms.TextInput(attrs={"class": "form-control"}),
            "payment_model": forms.Select(attrs={"class": "form-select", "id": "id_payment_model"}),
            "cash_amount": forms.NumberInput(attrs={"class": "form-control"}),
            "officer_in_charge": forms.Select(attrs={"class": "form-select", "id": "id_officer_in_charge"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["officer_in_charge"].queryset = User.objects.filter(role="OFFICER")

        # Make per_initial_deposit_commission read-only
        if "per_initial_deposit_commission" in self.fields:
            self.fields["per_initial_deposit_commission"].disabled = True

        # Hide commission field for CASH and LEASE customers
        if self.instance and self.instance.payment_model in ["CASH", "LEASE"]:
            self.fields.pop("per_initial_deposit_commission", None)

    def clean(self):
        cleaned_data = super().clean()
        onboarding_type = cleaned_data.get("onboarding_type")
        payment_model = cleaned_data.get("payment_model")

        if onboarding_type == "DIRECT":
            cleaned_data["agent"] = None
            cleaned_data["agent_commission_percent"] = 0
        elif onboarding_type == "AGENT" and not cleaned_data.get("agent"):
            self.add_error("agent", "Agent must be selected when onboarding via agent.")

        if payment_model == "CASH":
            if not cleaned_data.get("cash_amount"):
                self.add_error("cash_amount", "Cash amount is required for cash payments.")
        elif payment_model in ["INSTALLMENT", "LEASE"]:
            cleaned_data["cash_amount"] = None

        cleaned_data["approval_status"] = "PENDING"
        return cleaned_data


# -------------------------------
# Customer Approval Form
# -------------------------------
class CustomerApprovalForm(forms.ModelForm):
    class Meta:
        model = Customer
        fields = ["approval_status"]
        widgets = {
            "approval_status": forms.Select(attrs={"class": "form-select", "id": "id_approval_status"}),
        }

    def save(self, commit=True):
        customer = super().save(commit=False)

        if customer.payment_model == "CASH":
            customer.approval_status = "APPROVED"
            customer.is_settled = True
            customer.balance_remaining = 0
            customer.last_financial_update = now()
            if customer.motorcycle:
                customer.motorcycle.sell_to_customer(customer, user=customer.officer_in_charge, payment_model="CASH")
                from invoices.tasks import generate_cash_invoice
                generate_cash_invoice.delay(customer.motorcycle.vin)

        elif customer.approval_status == "APPROVED":
            if customer.payment_model == "INSTALLMENT" and customer.motorcycle:
                customer.motorcycle.sell_to_customer(customer, user=customer.officer_in_charge, payment_model="INSTALLMENT")
                from invoices.tasks import generate_installment_invoices
                generate_installment_invoices.delay(customer.motorcycle.vin)

            elif customer.payment_model == "LEASE" and customer.motorcycle:
                customer.motorcycle.lease_to_customer(customer, user=customer.officer_in_charge)
                from invoices.tasks import generate_lease_invoices
                generate_lease_invoices.delay(customer.motorcycle.vin)

        if commit:
            customer.save()
        return customer


# -------------------------------
# Installment Plan Form
# -------------------------------
class InstallmentPlanForm(forms.ModelForm):
    start_date = forms.DateField(
        widget=forms.DateInput(attrs={"type": "date", "class": "form-control"})
    )

    class Meta:
        model = InstallmentPlan
        fields = [
            "total_amount",
            "initial_deposit",
            "number_of_installments",
            "payment_schedule",
            "start_date",
        ]
        widgets = {
            "total_amount": forms.NumberInput(attrs={"class": "form-control"}),
            "initial_deposit": forms.NumberInput(attrs={"class": "form-control"}),
            "number_of_installments": forms.NumberInput(attrs={"class": "form-control"}),
            "payment_schedule": forms.Select(attrs={"class": "form-select"}),
        }

    def clean(self):
        cleaned_data = super().clean()
        total_amount = cleaned_data.get("total_amount")
        initial_deposit = cleaned_data.get("initial_deposit")
        number_of_installments = cleaned_data.get("number_of_installments")
        payment_model = cleaned_data.get("payment_model")
        agent_commission_percent = cleaned_data.get("agent_commission_percent")

        # Deposit validation
        if total_amount is not None and initial_deposit is not None:
            if initial_deposit < 0:
                self.add_error("initial_deposit", "Initial deposit cannot be negative.")
            elif initial_deposit > total_amount:
                self.add_error("initial_deposit", "Initial deposit cannot exceed total amount.")

        # Installment count validation
        if number_of_installments is not None and number_of_installments < 1:
            self.add_error("number_of_installments", "Number of installments must be at least 1.")

        # ✅ Commission enforcement for INSTALLMENT customers
        if payment_model == "INSTALLMENT":
            if not agent_commission_percent or agent_commission_percent <= 0:
                self.add_error(
                    "agent_commission_percent",
                    "Commission percent is required and must be greater than 0 for installment customers."
                )

        return cleaned_data




# -------------------------------
# Lease Plan Form
# -------------------------------
class LeasePlanForm(forms.ModelForm):
    start_date = forms.DateField(
        widget=forms.DateInput(attrs={"type": "date", "class": "form-control"})
    )

    class Meta:
        model = LeasePlan
        fields = ["total_amount", "weekly_lease_amount", "start_date"]
        widgets = {
            "total_amount": forms.NumberInput(attrs={"class": "form-control"}),
            "weekly_lease_amount": forms.NumberInput(attrs={"class": "form-control"}),
        }

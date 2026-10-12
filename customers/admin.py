from django.contrib import admin
from .models import Customer

@admin.register(Customer)
class CustomerAdmin(admin.ModelAdmin):
    list_display = (
        'customer_id',
        'full_name',
        'account_number',
        'payment_model',
        'approval_status',
        'opening_balance',
        'balance_remaining',
        'credit_amount',
        'arrears_amount',
        'settled_flag',
        'missed_invoices_count',
        'repossession_flag',
        'nearest_warehouse',
        'motorcycle',               # ✅ show VIN link
        'agent',
        'agent_commission_percent', # ✅ show commission %
        'per_initial_deposit_commission',  # ✅ new column
        'officer_in_charge',
    )
    list_filter = (
        'approval_status',
        'payment_model',
        'nearest_warehouse',
        'agent',
        'settled_flag',
        'repossession_flag',
    )
    search_fields = (
        'customer_id',
        'full_name',
        'account_number',
        'mobile_number',
        # ✅ guarantor fields updated
        'guarantor1_name',
        'guarantor1_mobile',
        'guarantor1_national_id',
        'guarantor2_name',
        'guarantor2_mobile',
        'guarantor2_national_id',
    )

    readonly_fields = (
        'per_initial_deposit_commission',  # ✅ make read-only in admin
    )

    actions = ['approve_customers', 'reject_customers', 'return_for_correction']

    def get_readonly_fields(self, request, obj=None):
        """
        Only show per_initial_deposit_commission for INSTALLMENT customers.
        """
        ro_fields = list(super().get_readonly_fields(request, obj))
        if obj and obj.payment_model != "INSTALLMENT":
            # Hide the field for CASH and LEASE customers
            ro_fields = [f for f in ro_fields if f != "per_initial_deposit_commission"]
        return ro_fields

    def get_list_display(self, request):
        """
        Only show per_initial_deposit_commission column for INSTALLMENT customers.
        """
        fields = list(super().get_list_display(request))
        # If filtering by non-installment customers, drop the column
        if request.GET.get("payment_model") in ["CASH", "LEASE"]:
            if "per_initial_deposit_commission" in fields:
                fields.remove("per_initial_deposit_commission")
        return fields

    def approve_customers(self, request, queryset):
        for customer in queryset:
            customer.approval_status = 'APPROVED'
            customer.save()
            # 🔑 Later: trigger invoice generation here, including commission
        self.message_user(request, "Selected customers approved. Invoices will now be generated.")

    approve_customers.short_description = "Approve selected customers"

    def reject_customers(self, request, queryset):
        queryset.update(approval_status='REJECTED')
        self.message_user(request, "Selected customers rejected. No invoices generated.")
    reject_customers.short_description = "Reject selected customers"

    def return_for_correction(self, request, queryset):
        queryset.update(approval_status='PENDING')
        self.message_user(request, "Selected customers returned to officers for correction.")
    return_for_correction.short_description = "Return selected customers for correction"

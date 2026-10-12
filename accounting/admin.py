from django.contrib import admin
from .models import AgentAccount, CommissionPayout

@admin.register(AgentAccount)
class AgentAccountAdmin(admin.ModelAdmin):
    list_display = ("agent", "accrued_commission", "updated_at")
    list_filter = ("updated_at", "agent")  # ✅ officers can filter by agent or payout period
    search_fields = ("agent__name",)

    actions = ["pay_and_reset"]

    def pay_and_reset(self, request, queryset):
        """
        Admin action: pay selected agents and reset their commission balance.
        """
        for account in queryset:
            if account.accrued_commission > 0:
                CommissionPayout.objects.create(
                    agent=account.agent,
                    amount=account.accrued_commission
                )
                account.accrued_commission = 0
                account.save()
        self.message_user(request, "Selected agent accounts have been paid and reset.")
    pay_and_reset.short_description = "Pay selected agents and reset commission"


@admin.register(CommissionPayout)
class CommissionPayoutAdmin(admin.ModelAdmin):
    list_display = ("agent", "amount", "paid_on")
    list_filter = ("paid_on", "agent")
    search_fields = ("agent__name",)

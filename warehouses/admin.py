from django.contrib import admin
from .models import Warehouse, StockTransfer, TransferHistory, RetainedMotorcycle

@admin.register(Warehouse)
class WarehouseAdmin(admin.ModelAdmin):
    list_display = ('name', 'type', 'physical_location', 'created_at')
    search_fields = ('name', 'physical_location')
    list_filter = ('type',)

    def save_model(self, request, obj, form, change):
        # Automatically set created_by when a new warehouse is created
        if not obj.pk:  # only on creation
            obj.created_by = request.user
        super().save_model(request, obj, form, change)


# --- Transfer History Inline ---
class TransferHistoryInline(admin.TabularInline):
    model = TransferHistory
    extra = 0
    readonly_fields = ("action", "performed_by", "notes", "timestamp")


@admin.register(StockTransfer)
class StockTransferAdmin(admin.ModelAdmin):
    list_display = ("motorcycle", "from_warehouse", "to_warehouse", "initiated_by", "status", "created_at")
    list_filter = ("status", "from_warehouse", "to_warehouse")
    search_fields = ("motorcycle__vin", "motorcycle__model")
    inlines = [TransferHistoryInline]


@admin.register(TransferHistory)
class TransferHistoryAdmin(admin.ModelAdmin):
    list_display = ("transfer", "action", "performed_by", "notes", "timestamp")
    list_filter = ("action", "performed_by")
    search_fields = ("transfer__motorcycle__vin", "notes")


@admin.register(RetainedMotorcycle)
class RetainedMotorcycleAdmin(admin.ModelAdmin):
    list_display = ("motorcycle", "customer", "warehouse", "officer_in_charge", "status", "repossession_date")
    list_filter = ("status", "warehouse")
    search_fields = ("motorcycle__vin", "customer__name")

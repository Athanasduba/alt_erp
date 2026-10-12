from django.contrib import admin, messages
from django.shortcuts import redirect
from django.urls import path
import pandas as pd

from .models import Motorcycle, MotorcycleHistory
from warehouses.models import Warehouse


# --- Inline history logs ---
class HistoryInline(admin.TabularInline):
    model = MotorcycleHistory
    extra = 0
    readonly_fields = ("action", "performed_by", "notes", "timestamp")


@admin.register(Motorcycle)
class MotorcycleAdmin(admin.ModelAdmin):
    list_display = (
        'vin', 'model', 'brand', 'category',
        'color', 'warehouse', 'customer_account',
        'status', 'created_by', 'created_at'
    )
    search_fields = ('vin', 'model', 'brand', 'frame_number', 'engine_number')
    list_filter = ('status', 'category', 'warehouse', 'brand', 'color')
    inlines = [HistoryInline]
    actions = ["bulk_move_to_warehouse"]

    # --- Bulk move action ---
    def bulk_move_to_warehouse(self, request, queryset):
        """
        Admin action: bulk move selected motorcycles into a warehouse.
        """
        warehouse_id = request.POST.get("warehouse_id")
        if not warehouse_id:
            self.message_user(request, "Please select a warehouse.", level=messages.ERROR)
            return
        try:
            warehouse = Warehouse.objects.get(id=warehouse_id)
        except Warehouse.DoesNotExist:
            self.message_user(request, "Invalid warehouse selected.", level=messages.ERROR)
            return

        for motorcycle in queryset:
            motorcycle.move_to_warehouse(warehouse, request.user)
        self.message_user(request, f"{queryset.count()} motorcycles moved to {warehouse.name}.", level=messages.SUCCESS)

    bulk_move_to_warehouse.short_description = "Move selected motorcycles to warehouse"

    # --- Auto set created_by + log creation ---
    def save_model(self, request, obj, form, change):
        if not obj.pk:  # only on creation
            obj.created_by = request.user
            obj.save()
            MotorcycleHistory.objects.create(
                motorcycle=obj,
                action="CREATED",
                performed_by=request.user,
                notes="Motorcycle created"
            )
        else:
            super().save_model(request, obj, form, change)

    # --- Custom admin view for Excel upload ---
    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path("upload-excel/", self.admin_site.admin_view(self.upload_excel), name="motorcycle_upload_excel"),
        ]
        return custom_urls + urls

    def upload_excel(self, request):
        """
        Custom view: upload Excel file to bulk create motorcycles.
        Expected columns: vin, frame_number, engine_number, model, brand, color, category
        """
        if request.method == "POST" and request.FILES.get("excel_file"):
            excel_file = request.FILES["excel_file"]
            try:
                df = pd.read_excel(excel_file)
                created_count = 0
                for _, row in df.iterrows():
                    motorcycle = Motorcycle.objects.create(
                        vin=row["vin"],
                        frame_number=row["frame_number"],
                        engine_number=row["engine_number"],
                        model=row["model"],
                        brand=row["brand"],
                        color=row["color"],
                        category=row["category"],
                        created_by=request.user,
                        status="NEW"
                    )
                    MotorcycleHistory.objects.create(
                        motorcycle=motorcycle,
                        action="CREATED",
                        performed_by=request.user,
                        notes="Bulk upload via Excel"
                    )
                    created_count += 1
                self.message_user(request, f"{created_count} motorcycles uploaded successfully.", level=messages.SUCCESS)
            except Exception as e:
                self.message_user(request, f"Error processing file: {e}", level=messages.ERROR)
            return redirect("..")

        from django.http import HttpResponse
        return HttpResponse("""
            <h2>Upload Motorcycles via Excel</h2>
            <form method="post" enctype="multipart/form-data">
                <input type="file" name="excel_file" accept=".xls,.xlsx" required>
                <button type="submit">Upload</button>
            </form>
        """)

    # --- Add custom link beside "Add Motorcycle" ---
    def changelist_view(self, request, extra_context=None):
        if extra_context is None:
            extra_context = {}
        extra_context['upload_excel_url'] = "upload-excel/"
        return super().changelist_view(request, extra_context=extra_context)


@admin.register(MotorcycleHistory)
class MotorcycleHistoryAdmin(admin.ModelAdmin):
    list_display = ("motorcycle", "action", "performed_by", "notes", "timestamp")
    list_filter = ("action", "performed_by")
    search_fields = ("motorcycle__vin", "motorcycle__model", "notes")

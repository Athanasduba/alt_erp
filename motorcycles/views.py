from django import forms
from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.http import JsonResponse   # ✅ added for API response
import pandas as pd
from django.core.paginator import Paginator
from .models import Motorcycle, MotorcycleHistory
from warehouses.models import Warehouse


# --- Form for manual creation ---
class MotorcycleForm(forms.ModelForm):
    class Meta:
        model = Motorcycle
        fields = [
            "vin", "frame_number", "engine_number",
            "model", "brand", "color", "category"
        ]


@login_required
def motorcycle_list(request):
    motorcycles = Motorcycle.objects.all().order_by("-created_at")

    # 🔎 Apply filters from GET parameters
    vin_search = request.GET.get("vin_search")
    status = request.GET.get("status")
    warehouse_id = request.GET.get("warehouse_id")

    # ✅ VIN filter
    if vin_search:
        motorcycles = motorcycles.filter(vin__icontains=vin_search)

    # ✅ Status filter
    if status:
        motorcycles = motorcycles.filter(status=status)

    # ✅ Warehouse filter
    if warehouse_id:
        motorcycles = motorcycles.filter(warehouse_id=warehouse_id)

    # 📄 Pagination: 50 motorcycles per page
    paginator = Paginator(motorcycles, 50)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    return render(
        request,
        "motorcycles/motorcycle_list.html",
        {
            "motorcycles": page_obj,
            "page_obj": page_obj,
            "warehouses": Warehouse.objects.all(),  # ✅ for warehouse dropdown
        }
    )


@login_required
def motorcycle_detail(request, pk):
    """
    Show details of a single motorcycle with its history.
    """
    motorcycle = get_object_or_404(Motorcycle, pk=pk)
    history = motorcycle.history.all().order_by("-timestamp")
    return render(request, "motorcycles/motorcycle_detail.html", {
        "motorcycle": motorcycle,
        "history": history
    })


@login_required
def add_motorcycle(request):
    """
    Add a single motorcycle manually.
    """
    if request.method == "POST":
        form = MotorcycleForm(request.POST)
        if form.is_valid():
            motorcycle = form.save(commit=False)
            motorcycle.created_by = request.user
            motorcycle.status = "NEW"
            motorcycle.save()
            MotorcycleHistory.objects.create(
                motorcycle=motorcycle,
                action="CREATED",
                performed_by=request.user,
                notes="Manual add via form"
            )
            messages.success(request, f"Motorcycle {motorcycle.vin} added successfully.")
            return redirect("motorcycle_list")
    else:
        form = MotorcycleForm()
    return render(request, "motorcycles/add_motorcycle.html", {"form": form})

@login_required
def edit_motorcycle(request, pk):
    """
    Edit an existing motorcycle record.
    """
    motorcycle = get_object_or_404(Motorcycle, pk=pk)
    if request.method == "POST":
        form = MotorcycleForm(request.POST, instance=motorcycle)
        if form.is_valid():
            updated_motorcycle = form.save()
            MotorcycleHistory.objects.create(
                motorcycle=updated_motorcycle,
                action="UPDATED",
                performed_by=request.user,
                notes="Motorcycle details updated via form"
            )
            messages.success(request, f"Motorcycle {updated_motorcycle.vin} updated successfully.")
            return redirect("motorcycle_list")
    else:
        form = MotorcycleForm(instance=motorcycle)

    return render(request, "motorcycles/edit_motorcycle.html", {
        "form": form,
        "motorcycle": motorcycle
    })


@login_required
def delete_motorcycle(request, pk):
    """
    Soft delete a motorcycle record.
    Only Admin and Manager roles can delete.
    Logs deletion into MotorcycleHistory.
    """
    motorcycle = get_object_or_404(Motorcycle, pk=pk)

    # Restrict to Admin & Manager
    if request.user.role not in ["ADMIN", "MANAGER"]:
        messages.error(request, "You do not have permission to delete motorcycles.")
        return redirect("motorcycle_list")

    if request.method == "POST":
        vin = motorcycle.vin

        # Soft delete instead of hard delete
        motorcycle.status = "DELETED"
        motorcycle.save()

        MotorcycleHistory.objects.create(
            motorcycle=motorcycle,
            action="DELETED",
            performed_by=request.user,
            notes=f"Motorcycle {vin} soft-deleted by {request.user}"
        )

        messages.success(request, f"Motorcycle {vin} deleted successfully (soft delete).")
        return redirect("motorcycle_list")

    return render(request, "motorcycles/confirm_delete.html", {"motorcycle": motorcycle})

@login_required
def move_motorcycles(request):
    """
    Bulk move motorcycles into a warehouse.
    Accessible by Admin, Manager, Store roles.
    """
    if request.method == "POST":
        ids = request.POST.getlist("motorcycle_ids")
        warehouse_id = request.POST.get("warehouse_id")
        warehouse = get_object_or_404(Warehouse, pk=warehouse_id)

        for mid in ids:
            motorcycle = get_object_or_404(Motorcycle, pk=mid)
            motorcycle.move_to_warehouse(warehouse, request.user)

        messages.success(request, f"{len(ids)} motorcycles moved to {warehouse.name}.")
        return redirect("motorcycle_list")

    motorcycles = Motorcycle.objects.filter(status="NEW")
    warehouses = Warehouse.objects.all()
    return render(request, "motorcycles/move_motorcycles.html", {"motorcycles": motorcycles, "warehouses": warehouses})


@login_required
def upload_motorcycles_excel(request):
    """
    Upload Excel file to bulk create motorcycles.
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
            messages.success(request, f"{created_count} motorcycles uploaded successfully.")
        except Exception as e:
            messages.error(request, f"Error processing file: {e}")
        return redirect("motorcycle_list")

    return render(request, "motorcycles/upload_excel.html")


# ✅ NEW ENDPOINT: Fetch motorcycles by warehouse (for AJAX dropdown)
@login_required
def motorcycles_by_warehouse(request, warehouse_id):
    """
    Return JSON list of motorcycles belonging to a given warehouse.
    Only include motorcycles that are AVAILABLE or RETAINED.
    Used for AJAX dynamic dropdown in customer onboarding.
    """
    allowed_statuses = ["AVAILABLE", "RETAINED"]
    motorcycles = Motorcycle.objects.filter(
        warehouse_id=warehouse_id,
        status__in=allowed_statuses
    ).exclude(status="DELETED")

    data = [
        {
            "id": m.id,
            "vin": m.vin,
            "status": m.status,
        }
        for m in motorcycles
    ]
    return JsonResponse(data, safe=False)

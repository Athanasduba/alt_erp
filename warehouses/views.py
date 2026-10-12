from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect, get_object_or_404
from .models import Warehouse, StockTransfer, RetainedMotorcycle
from motorcycles.models import Motorcycle
from django.conf import settings

# --- Warehouse Views ---

@login_required
def warehouse_list(request):
    """Visible to all users, with motorcycle counts per warehouse, retained details, and pending transfers."""
    warehouses = Warehouse.objects.all()
    warehouse_data = []
    for wh in warehouses:
        warehouse_data.append({
            "warehouse": wh,
            "available_count": wh.motorcycles.filter(status="AVAILABLE").count(),
            "leased_count": wh.motorcycles.filter(status="LEASED").count(),

            # ✅ Separate counts for Sold
            "sold_cash_count": wh.motorcycles.filter(status="SOLD_CASH").count(),
            "sold_installment_count": wh.motorcycles.filter(status="SOLD_INSTALLMENT").count(),

            "retained_count": wh.motorcycles.filter(status="RETAINED").count(),

            # ✅ Separate counts for Resold
            "resold_cash_count": wh.motorcycles.filter(status="RESOLD_CASH").count(),
            "resold_installment_count": wh.motorcycles.filter(status="RESOLD_INSTALLMENT").count(),

            "released_count": wh.motorcycles.filter(status="RELEASED").count(),
            "lease_completed_count": wh.motorcycles.filter(status="LEASE_COMPLETED").count(),
            "installment_completed_count": wh.motorcycles.filter(status="INSTALLMENT_COMPLETED").count(),
        })

    # Retained motorcycles for details table
    retained_motorcycles = RetainedMotorcycle.objects.select_related(
        "motorcycle", "customer", "warehouse", "officer_in_charge"
    )

    # Pending transfers for dashboard table
    pending_transfers = StockTransfer.objects.filter(status="PENDING").select_related(
        "motorcycle", "from_warehouse", "to_warehouse", "initiated_by"
    )

    return render(
        request,
        "warehouses/warehouse_list.html",
        {
            "warehouse_data": warehouse_data,
            "retained_motorcycles": retained_motorcycles,
            "pending_transfers": pending_transfers,
        }
    )


@login_required
def warehouse_create(request):
    """Only Admin/Manager can create warehouses."""
    if request.user.role not in ["ADMIN", "MANAGER"]:
        messages.error(request, "You do not have permission to add warehouses.")
        return redirect("warehouse_list")

    if request.method == "POST":
        name = request.POST.get("name")
        type = request.POST.get("type")
        location = request.POST.get("physical_location")
        if name and type and location:
            Warehouse.objects.create(
                name=name,
                type=type,
                physical_location=location,
                created_by=request.user
            )
            messages.success(request, "Warehouse created successfully.")
            return redirect("warehouse_list")
    return render(request, "warehouses/warehouse_form.html")


# --- Stock Transfer Views ---

@login_required
def transfer_create(request):
    """Store role initiates transfer requests with source and destination warehouses, multiple motorcycles."""
    if request.user.role != "STORE":
        messages.error(request, "Only Store users can initiate transfers.")
        return redirect("warehouse_list")

    if request.method == "POST":
        motorcycle_ids = request.POST.getlist("motorcycles")  # multiple selection
        from_warehouse_id = request.POST.get("from_warehouse")
        to_warehouse_id = request.POST.get("to_warehouse")

        from_warehouse = get_object_or_404(Warehouse, pk=from_warehouse_id)
        to_warehouse = get_object_or_404(Warehouse, pk=to_warehouse_id)

        if from_warehouse == to_warehouse:
            messages.error(request, "Source and destination warehouses must be different.")
            return redirect("transfer_create")

        for motorcycle_id in motorcycle_ids:
            motorcycle = get_object_or_404(Motorcycle, pk=motorcycle_id)
            if motorcycle.warehouse != from_warehouse:
                messages.warning(request, f"Motorcycle {motorcycle.vin} is not in {from_warehouse.name}. Skipped.")
                continue

            StockTransfer.objects.create(
                motorcycle=motorcycle,
                from_warehouse=from_warehouse,
                to_warehouse=to_warehouse,
                initiated_by=request.user,
                status="PENDING"
            )

        messages.success(request, "Transfer request(s) submitted.")
        return redirect("warehouse_list")

    # Only motorcycles currently assigned to a warehouse
    motorcycles = Motorcycle.objects.filter(warehouse__isnull=False)
    warehouses = Warehouse.objects.all()
    return render(
        request,
        "warehouses/transfer_form.html",
        {"motorcycles": motorcycles, "warehouses": warehouses}
    )


@login_required
def transfer_approve(request, pk):
    """Admin/Manager approve or deny transfer requests."""
    transfer = get_object_or_404(StockTransfer, pk=pk)
    if request.user.role not in ["ADMIN", "MANAGER"]:
        messages.error(request, "You do not have permission to approve transfers.")
        return redirect("warehouse_list")

    if request.method == "POST":
        action = request.POST.get("action")
        reason = request.POST.get("reason", "")
        if action == "approve":
            transfer.approve(request.user)
            messages.success(request, "Transfer approved.")
        elif action == "deny":
            transfer.deny(request.user, reason, returned=False)
            messages.warning(request, "Transfer denied.")
        elif action == "return":
            transfer.deny(request.user, reason, returned=True)
            messages.info(request, "Transfer returned for correction.")
        return redirect("warehouse_list")

    return render(request, "warehouses/transfer_approve.html", {"transfer": transfer})


@login_required
def transfer_edit(request, pk):
    """Store role edits a returned transfer and resubmits for approval."""
    transfer = get_object_or_404(StockTransfer, pk=pk)

    if request.user.role != "STORE":
        messages.error(request, "Only Store users can edit transfers.")
        return redirect("warehouse_list")

    if transfer.status != "RETURNED":
        messages.error(request, "Only returned transfers can be edited.")
        return redirect("warehouse_list")

    if request.method == "POST":
        to_warehouse_id = request.POST.get("to_warehouse")
        to_warehouse = get_object_or_404(Warehouse, pk=to_warehouse_id)

        transfer.to_warehouse = to_warehouse
        transfer.status = "PENDING"  # resubmitted for approval
        transfer.save()

        messages.success(request, "Transfer updated and resubmitted for approval.")
        return redirect("warehouse_list")

    warehouses = Warehouse.objects.exclude(id=transfer.from_warehouse.id)
    return render(request, "warehouses/transfer_edit.html", {"transfer": transfer, "warehouses": warehouses})


# --- Retained Motorcycle Views ---

@login_required
def repossession_create(request):
    """Officer in charge initiates repossession requests."""
    if request.user.role != "OFFICER":
        messages.error(request, "Only Officers in charge can initiate repossession.")
        return redirect("warehouse_list")

    if request.method == "POST":
        motorcycle_id = request.POST.get("motorcycle")
        warehouse_id = request.POST.get("warehouse")
        motorcycle = get_object_or_404(Motorcycle, pk=motorcycle_id)
        warehouse = get_object_or_404(Warehouse, pk=warehouse_id)

        RetainedMotorcycle.objects.create(
            motorcycle=motorcycle,
            customer=motorcycle.customer,  # assuming Motorcycle links to Customer
            warehouse=warehouse,
            officer_in_charge=request.user,
            status="PENDING"
        )
        messages.success(request, "Repossession request submitted.")
        return redirect("warehouse_list")

    motorcycles = Motorcycle.objects.filter(status__in=["SOLD_CASH", "SOLD_INSTALLMENT"])
    warehouses = Warehouse.objects.all()
    return render(request, "warehouses/repossession_form.html", {"motorcycles": motorcycles, "warehouses": warehouses})


@login_required
def repossession_approve(request, pk):
    """Manager/Admin approve repossession requests."""
    repossession = get_object_or_404(RetainedMotorcycle, pk=pk)
    if request.user.role not in ["ADMIN", "MANAGER"]:
        messages.error(request, "You do not have permission to approve repossession.")
        return redirect("warehouse_list")

    if request.method == "POST":
        action = request.POST.get("action")
        reason = request.POST.get("reason", "")
        if action == "approve":
            repossession.approve(request.user)
            messages.success(request, "Repossession approved and motorcycle marked as retained.")
        elif action == "deny":
            repossession.deny(request.user, reason)
            messages.warning(request, "Repossession denied.")
        return redirect("warehouse_list")

    warehouses = Warehouse.objects.all()
    return render(request, "warehouses/repossession_approve.html", {"repossession": repossession, "warehouses": warehouses})

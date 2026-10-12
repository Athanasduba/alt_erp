from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required, user_passes_test
from django.views.decorators.http import require_POST
from django.contrib import messages
from django.http import JsonResponse
from .models import Customer
from warehouses.models import Warehouse
from django.db.models import Q
from .forms import CustomerForm, InstallmentPlanForm, LeasePlanForm, CustomerApprovalForm
from motorcycles.models import Motorcycle
from django.core.paginator import Paginator
from customers.utils import initialize_financial_tracking
from users.models import User   # ✅ adjust to your actual User/Officer model


# Utility check for manager or admin role
def is_manager_or_admin(user):
    return user.role in ['MANAGER', 'ADMIN']


@login_required
def customer_list(request):
    customers = Customer.objects.all().order_by("-created_at")

    # 🔎 Apply filters from GET parameters
    search_name = request.GET.get("search_name")
    approval_status = request.GET.get("approval_status")
    agent_name = request.GET.get("agent_name")
    credit_min = request.GET.get("credit_min")
    arrears_min = request.GET.get("arrears_min")
    warehouse_id = request.GET.get("warehouse_id")
    officer_name = request.GET.get("officer_name")
    start_date = request.GET.get("start_date")
    end_date = request.GET.get("end_date")

    # ✅ Customer name filter
    if search_name:
        customers = customers.filter(full_name__icontains=search_name)

    # ✅ Approval status filter
    if approval_status:
        customers = customers.filter(approval_status=approval_status)

    # ✅ Agent filter (combined Q logic)
    if agent_name:
        customers = customers.filter(
            Q(agent__user__username__icontains=agent_name) |
            Q(agent__individual_details__full_name__icontains=agent_name) |
            Q(agent__company_details__company_name__icontains=agent_name)
        )

    # ✅ Credit filter
    if credit_min:
        customers = customers.filter(credit_amount__gte=credit_min)

    # ✅ Arrears filter
    if arrears_min:
        customers = customers.filter(arrears_amount__gte=arrears_min)

    # ✅ Warehouse filter
    if warehouse_id:
        customers = customers.filter(nearest_warehouse_id=warehouse_id)

    # ✅ Officer filter (dropdown selection)
    if officer_name:
        customers = customers.filter(officer_in_charge__id=officer_name)

    # ✅ Date range filter
    if start_date:
        customers = customers.filter(created_at__date__gte=start_date)
    if end_date:
        customers = customers.filter(created_at__date__lte=end_date)

    # 📄 Pagination: 50 customers per page
    paginator = Paginator(customers, 50)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    return render(
        request,
        "customers/customer_list.html",
        {
            "customers": page_obj,
            "page_obj": page_obj,
            "warehouses": Warehouse.objects.all(),   # ✅ for warehouse dropdown
            "officers": User.objects.filter(role="OFFICER"),  # ✅ for officer dropdown
        }
    )




# ✅ Manager/Admin dashboard
@login_required
@user_passes_test(is_manager_or_admin)
def manager_dashboard(request):
    pending_customers = Customer.objects.filter(approval_status='PENDING')
    approved_customers = Customer.objects.filter(approval_status='APPROVED')
    rejected_customers = Customer.objects.filter(approval_status='REJECTED')
    return render(request, 'customers/manager_dashboard.html', {
        "pending_customers": pending_customers,
        "approved_customers": approved_customers,
        "rejected_customers": rejected_customers,
    })


# ✅ Manager/Admin approval form
@login_required
@user_passes_test(is_manager_or_admin)
def approve_customer(request, pk):
    customer = get_object_or_404(Customer, pk=pk)
    if request.method == "POST":
        form = CustomerApprovalForm(request.POST, instance=customer)
        if form.is_valid():
            # 🔑 Lifecycle + invoice generation handled inside CustomerApprovalForm.save()
            form.save()

            # ✅ Messages only (no manual lifecycle here)
            if customer.approval_status == "APPROVED":
                messages.success(request, f"{customer.full_name} has been APPROVED. Motorcycle {customer.motorcycle.vin} updated successfully.")
            elif customer.approval_status == "REJECTED":
                messages.warning(request, f"{customer.full_name} has been REJECTED.")
            elif customer.approval_status == "PENDING":
                messages.info(request, f"{customer.full_name} returned for correction.")

            return redirect("customer_list")
    else:
        form = CustomerApprovalForm(instance=customer)

    # ✅ Add warehouse counts for context in approval page
    warehouse_counts = None
    if customer.motorcycle and customer.motorcycle.warehouse:
        w = customer.motorcycle.warehouse
        warehouse_counts = {
            "available": w.available_count,
            "leased": w.leased_count,
            "sold": w.sold_count,
            "retained": w.retained_count,
            "resold": w.resold_count,
            "re_leased": w.re_leased_count,
            "lease_completed": w.lease_completed_count,
        }

    return render(
        request,
        "customers/approve_customer.html",
        {"form": form, "customer": customer, "warehouse_counts": warehouse_counts}
    )


# ✅ Update customer status (used in templates)
@login_required
@user_passes_test(is_manager_or_admin)
def update_customer_status(request, customer_id, status):
    customer = get_object_or_404(Customer, id=customer_id)
    if status in ["APPROVED", "REJECTED", "PENDING"]:
        customer.approval_status = status
        customer.save()

        if status == "APPROVED":
            # 🔑 Trigger invoice generation depending on payment model (VIN as traceable key)
            if customer.payment_model == "INSTALLMENT" and hasattr(customer, "installment_plan"):
                from invoices.tasks import generate_installment_invoices
                generate_installment_invoices.delay(customer.motorcycle.vin)

            elif customer.payment_model == "LEASE" and hasattr(customer, "lease_plan"):
                from invoices.tasks import generate_lease_invoices
                generate_lease_invoices.delay(customer.motorcycle.vin)

            elif customer.payment_model == "CASH":
                from invoices.tasks import generate_cash_invoice
                generate_cash_invoice.delay(customer.motorcycle.vin)

            messages.success(request, f"{customer.full_name} has been approved and invoices generated.")

        elif status == "REJECTED":
            messages.warning(request, f"{customer.full_name} has been rejected.")

        else:
            messages.info(request, f"{customer.full_name} returned for correction.")

    return redirect("customer_detail", pk=customer.id)


# ✅ Customer onboarding
@login_required
def customer_onboarding(request, pk=None):
    customer = None
    if pk:
        customer = get_object_or_404(Customer, pk=pk)

    if request.method == 'POST':
        customer_form = CustomerForm(request.POST, request.FILES, instance=customer)

        # Decide which plan form to bind based on payment_model in POST
        payment_model = request.POST.get("payment_model")
        if payment_model == "INSTALLMENT":
            installment_form = InstallmentPlanForm(request.POST, instance=getattr(customer, 'installment_plan', None))
            lease_form = LeasePlanForm(instance=getattr(customer, 'lease_plan', None))  # unbound
        elif payment_model == "LEASE":
            lease_form = LeasePlanForm(request.POST, instance=getattr(customer, 'lease_plan', None))
            installment_form = InstallmentPlanForm(instance=getattr(customer, 'installment_plan', None))  # unbound
        else:  # CASH
            installment_form = InstallmentPlanForm(instance=getattr(customer, 'installment_plan', None))
            lease_form = LeasePlanForm(instance=getattr(customer, 'lease_plan', None))

        if customer_form.is_valid():
            customer = customer_form.save(commit=False)
            customer.created_by = request.user

            if customer.payment_model in ['INSTALLMENT', 'LEASE']:
                customer.approval_status = "PENDING"
            elif customer.payment_model == 'CASH':
                customer.approval_status = "APPROVED"

            if customer.payment_model == 'INSTALLMENT':
                if installment_form.is_valid():
                    customer.save()
                    plan = installment_form.save(commit=False)
                    plan.customer = customer
                    plan.save()
                    # balances handled by signals
                else:
                    messages.error(request, "Installment plan form invalid.")
                    return render(request, 'customers/onboarding.html', {
                        "customer_form": customer_form,
                        "installment_form": installment_form,
                        "lease_form": lease_form,
                        "customer": customer,
                    })

            elif customer.payment_model == 'LEASE':
                if lease_form.is_valid():
                    customer.save()
                    plan = lease_form.save(commit=False)
                    plan.customer = customer
                    plan.save()
                    # balances handled by signals
                else:
                    messages.error(request, "Lease plan form invalid.")
                    return render(request, 'customers/onboarding.html', {
                        "customer_form": customer_form,
                        "installment_form": installment_form,
                        "lease_form": lease_form,
                        "customer": customer,
                    })

            else:  # CASH
                customer.save()
                # ✅ Immediately update balances and mark settled
                from customers.signals import update_financial_tracking
                update_financial_tracking(customer, cash_amount=customer.cash_amount)

            messages.success(request, f"Customer {customer.full_name} saved successfully.")
            return redirect('customer_detail', pk=customer.pk)

        else:
            messages.error(request, "Please correct the errors below.")

    else:
        customer_form = CustomerForm(instance=customer)
        installment_form = InstallmentPlanForm(instance=getattr(customer, 'installment_plan', None))
        lease_form = LeasePlanForm(instance=getattr(customer, 'lease_plan', None))

    return render(request, 'customers/onboarding.html', {
        "customer_form": customer_form,
        "installment_form": installment_form,
        "lease_form": lease_form,
        "customer": customer,
    })




# ✅ Customer Detail View
@login_required
def customer_detail(request, pk):
    customer = get_object_or_404(Customer, pk=pk)
    installment_plan = getattr(customer, 'installment_plan', None)
    lease_plan = getattr(customer, 'lease_plan', None)

    commission_info = {}
    if customer.agent and customer.agent_commission_percent > 0:
        if customer.payment_model == 'CASH':
            commission_info['cash_commission'] = customer.calculate_commission(customer.opening_balance)
        elif customer.payment_model == 'INSTALLMENT' and installment_plan:
            commission_info['installment_commission'] = customer.calculate_commission(installment_plan.installment_amount)
        elif customer.payment_model == 'LEASE' and lease_plan:
            commission_info['lease_commission'] = customer.calculate_commission(lease_plan.weekly_lease_amount)

    return render(request, 'customers/customer_detail.html', {
        "customer": customer,
        "installment_plan": installment_plan,
        "lease_plan": lease_plan,
        "commission_info": commission_info,
    })


# ✅ AJAX endpoint for available + retained motorcycles
@login_required
def available_motorcycles(request, warehouse_id):
    motorcycles = Motorcycle.objects.filter(
        warehouse_id=warehouse_id,
        status__in=["AVAILABLE", "RETAINED"]
    )

    result = []
    for m in motorcycles:
        # ✅ Label motorcycles clearly by VIN + model + status
        if m.status == "AVAILABLE":
            label = f"{m.vin} ({m.model}) [Available]"
            color = "green"
        elif m.status == "RETAINED":
            label = f"{m.vin} ({m.model}) [Retained]"
            color = "yellow"
        else:
            label = f"{m.vin} ({m.model})"
            color = "grey"

        result.append({
            "id": m.id,       # internal DB ID for selection
            "label": label,   # user-friendly label
            "color": color    # UI hint for status
        })

    return JsonResponse(result, safe=False)

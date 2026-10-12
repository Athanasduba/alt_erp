from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.db.models import Count, Sum
from customers.models import Customer
from invoices.models import Invoice
from accounting.models import CustomerAccount
from motorcycles.models import Motorcycle
from warehouses.models import Warehouse


@login_required
def dashboard_home(request):
    """
    Dashboard overview for managers/admins:
    - Customer settlement status
    - Invoice payment status
    - Accounting balances (credits/arrears)
    - Motorcycle status
    - Warehouses per location and stock breakdown
    """

    # Customers
    total_customers = Customer.objects.count()
    settled_customers = Customer.objects.filter(settled_flag=True)
    unsettled_customers = Customer.objects.filter(settled_flag=False)

    # Invoices
    invoice_stats = Invoice.objects.values('status').annotate(count=Count('id'))

    # Accounting
    credits_summary = CustomerAccount.objects.aggregate(total_credit=Sum('credit_balance'))
    arrears_summary = CustomerAccount.objects.aggregate(total_arrears=Sum('arrears_balance'))

    # Motorcycles overall
    motorcycle_stats = Motorcycle.objects.values('status').annotate(count=Count('id'))

    # Warehouses per physical location
    warehouse_stats = Warehouse.objects.values('physical_location').annotate(count=Count('id'))

    # Motorcycle stock per warehouse with status breakdown
    warehouse_motorcycle_stats = (
        Motorcycle.objects.values('warehouse__name', 'warehouse__physical_location', 'status')
        .annotate(count=Count('id'))
        .order_by('warehouse__name', 'status')
    )

    context = {
        "total_customers": total_customers,
        "settled_count": settled_customers.count(),
        "unsettled_count": unsettled_customers.count(),
        "settled_customers": settled_customers,
        "unsettled_customers": unsettled_customers,
        "invoice_stats": invoice_stats,
        "credits_summary": credits_summary,
        "arrears_summary": arrears_summary,
        "motorcycle_stats": motorcycle_stats,
        "warehouse_stats": warehouse_stats,
        "warehouse_motorcycle_stats": warehouse_motorcycle_stats,
    }
    return render(request, "dashboard/home.html", context)

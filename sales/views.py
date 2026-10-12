from django.shortcuts import render, get_object_or_404, redirect
from django.db.models import Sum
from .models import Sale, SalePayment
from .forms import SalePaymentForm

def sales_dashboard(request):
    sales = Sale.objects.all()

    summary = {
        "cash_count": sales.filter(payment_type="CASH").count(),
        "cash_total": sales.filter(payment_type="CASH").aggregate(Sum("total_amount"))["total_amount__sum"] or 0,
        "installment_count": sales.filter(payment_type="INSTALLMENT").count(),
        "installment_total": sales.filter(payment_type="INSTALLMENT").aggregate(Sum("total_amount"))["total_amount__sum"] or 0,
        "amount_paid": sales.aggregate(Sum("amount_paid"))["amount_paid__sum"] or 0,
        "balance_remaining": sales.aggregate(Sum("balance_remaining"))["balance_remaining__sum"] or 0,
        "agent_commission_total": SalePayment.objects.aggregate(Sum("agent_commission"))["agent_commission__sum"] or 0,
    }

    return render(request, "sales/sales_dashboard.html", {"sales": sales, "summary": summary})


def sale_list(request):
    sales = Sale.objects.all()
    return render(request, "sales/sale_list.html", {"sales": sales})


def sale_detail(request, sale_id):
    sale = get_object_or_404(Sale, id=sale_id)
    payments = sale.sale_payments.all()
    total_commission = payments.aggregate(Sum("agent_commission"))["agent_commission__sum"] or 0
    return render(request, "sales/sale_detail.html", {"sale": sale, "payments": payments, "total_commission": total_commission})


def add_payment(request, sale_id):
    sale = get_object_or_404(Sale, id=sale_id)
    if request.method == "POST":
        form = SalePaymentForm(request.POST)
        if form.is_valid():
            payment = form.save(commit=False)
            payment.sale = sale
            payment.save()  # commission + balance auto‑updated in model save()
            return redirect("sale_detail", sale_id=sale.id)
    else:
        form = SalePaymentForm()
    return render(request, "sales/add_payment.html", {"form": form, "sale": sale})

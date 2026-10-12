import json
import uuid
from django.db import models
from django.shortcuts import get_object_or_404, render, redirect
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib import messages
from .models import Payment
from invoices.models import Invoice
from payments.models import PaymentLog
from motorcycles.models import Motorcycle
from payments.utils import allocate_payment, verify_signature
from notifications.utils import notify_payment_processed


def payment_list(request):
    """Return all payments as JSON list or render template with filter."""
    status_filter = request.GET.get("status")
    payments = Payment.objects.all()
    if status_filter:
        payments = payments.filter(status=status_filter)

    if request.headers.get("Accept") == "application/json":
        return JsonResponse(list(payments.values(
            "id", "transaction_id", "selcom_transaction_id", "invoice_id", "customer_id",
            "motorcycle_id", "agent_id", "invoice_amount", "amount_paid",
            "credit", "arrears", "remaining_balance",
            "mobile_number", "bank_account", "company_number", "reference_vin",
            "agent_commission", "status", "timestamp"
        )), safe=False)

    return render(request, "payments/payment_list.html", {"payments": payments})


@csrf_exempt
def create_payment(request, payment_id):
    """Re-apply a failed payment by Payment ID."""
    # Fetch the failed payment
    payment = get_object_or_404(Payment, pk=payment_id)

    # Ensure it is actually failed
    if payment.status != "FAILED":
        return JsonResponse({
            "status": "error",
            "message": f"Payment {payment.transaction_id} is not marked as FAILED"
        }, status=400)

    # Get the linked invoice
    invoice = payment.invoice
    customer = payment.customer

    # --- Values come from ERP form (manual re-apply) ---
    amount = float(request.POST.get("amount_paid", payment.amount_paid))
    mobile_number = request.POST.get("mobile_number", payment.mobile_number)
    bank_account = request.POST.get("bank_account", payment.bank_account)

    # Create a new payment record (fresh ERP transaction ID)
    new_payment = Payment.objects.create(
        transaction_id=str(uuid.uuid4().hex[:10]).upper(),
        invoice=invoice,
        customer=customer,
        motorcycle=invoice.motorcycle,
        agent=invoice.agent,
        invoice_amount=invoice.amount_due,
        amount_paid=amount,
        remaining_balance=customer.balance_remaining,
        mobile_number=mobile_number,
        bank_account=bank_account,
        status="PARTIAL" if amount < invoice.amount_due else "FULL"
    )

    # Notify ERP that payment was processed
    notify_payment_processed(new_payment, invoice)

    return JsonResponse({
        "transaction_id": new_payment.transaction_id,
        "selcom_transaction_id": new_payment.selcom_transaction_id,
        "customer": customer.full_name,
        "motorcycle_vin": new_payment.motorcycle.vin if new_payment.motorcycle else None,
        "invoice_number": invoice.invoice_id,
        "invoice_amount": str(new_payment.invoice_amount),
        "amount_paid": str(new_payment.amount_paid),
        "credit": str(new_payment.credit),
        "arrears": str(new_payment.arrears),
        "remaining_balance": str(new_payment.remaining_balance),
        "mobile_number": new_payment.mobile_number,
        "bank_account": new_payment.bank_account,
        "agent_commission": str(new_payment.agent_commission),
        "status": new_payment.status,
        "timestamp": new_payment.timestamp,
    })



@csrf_exempt
def selcom_webhook(request):
    """Webhook endpoint for Selcom mobile payments."""
    if request.method != "POST":
        return JsonResponse({"status": "error", "message": "Invalid method"}, status=405)

    try:
        data = json.loads(request.body.decode("utf-8"))

        # --- Selcom provides signature in header ---
        signature = request.headers.get("X-Selcom-Signature")
        if not signature or not verify_signature(data, signature):
            PaymentLog.objects.create(
                motorcycle_vin=data.get("reference_vin", ""),
                transaction_id=data.get("transaction_id", ""),
                status="FAILED",
                reason="Invalid signature",
                amount=float(data.get("amount", 0)),
                company_number=data.get("company_number", ""),
                mobile_number=data.get("mobile_number", ""),
                raw_payload=request.body.decode("utf-8")
            )
            return JsonResponse({"status": "error", "message": "Invalid signature"}, status=403)

        # --- Extract Selcom payload ---
        company_number = data.get("company_number")
        reference_vin = data.get("reference_vin")
        amount = float(data.get("amount", 0))
        selcom_txn_id = data.get("transaction_id") or str(uuid.uuid4().hex[:10]).upper()
        mobile_number = data.get("mobile_number")
        selcom_status = data.get("status", "FAILED").upper()

        # ✅ Prevent duplicate payments
        if Payment.objects.filter(selcom_transaction_id=selcom_txn_id).exists():
            PaymentLog.objects.create(
                motorcycle_vin=reference_vin,
                transaction_id=selcom_txn_id,
                status="DUPLICATE",
                reason="Duplicate Selcom transaction ignored",
                amount=amount,
                company_number=company_number,
                mobile_number=mobile_number,
                raw_payload=request.body.decode("utf-8")
            )
            return JsonResponse({"status": "success", "message": "Duplicate Selcom transaction ignored"})

        # --- Lookup motorcycle by VIN ---
        try:
            motorcycle = Motorcycle.objects.get(vin=reference_vin)
        except Motorcycle.DoesNotExist:
            PaymentLog.objects.create(
                motorcycle_vin=reference_vin,
                transaction_id=selcom_txn_id,
                status="FAILED",
                reason="Motorcycle not found",
                amount=amount,
                company_number=company_number,
                mobile_number=mobile_number,
                raw_payload=request.body.decode("utf-8")
            )
            return JsonResponse({"status": "error", "message": "Motorcycle not found"}, status=404)

        customer = motorcycle.customer

        # --- Find oldest pending/overdue invoice ---
        invoice = customer.invoices.filter(
            motorcycle=motorcycle,
            status__in=["PENDING", "PARTIAL", "OVERDUE", "DEFAULTED"]
        ).order_by("due_date").first()

        if not invoice:
            PaymentLog.objects.create(
                motorcycle_vin=reference_vin,
                transaction_id=selcom_txn_id,
                status="FAILED",
                reason="No invoice found",
                amount=amount,
                company_number=company_number,
                mobile_number=mobile_number,
                raw_payload=request.body.decode("utf-8")
            )
            return JsonResponse({"status": "error", "message": "No invoice found"}, status=404)

        # ✅ Map Selcom status to ERP status
        erp_status = "FAILED" if selcom_status == "FAILED" else "PARTIAL"
        if amount >= invoice.amount_due:
            erp_status = "FULL"

        # --- Create payment record ---
        payment = Payment.objects.create(
            transaction_id=str(uuid.uuid4().hex[:10]).upper(),
            selcom_transaction_id=selcom_txn_id,
            invoice=invoice,
            customer=customer,
            motorcycle=motorcycle,
            agent=customer.agent,
            invoice_amount=invoice.amount_due,
            amount_paid=amount,
            mobile_number=mobile_number,
            company_number=company_number,
            reference_vin=reference_vin,
            status=erp_status,
        )

        # ✅ Log webhook
        PaymentLog.objects.create(
            invoice=invoice,
            transaction_id=payment.transaction_id,
            selcom_transaction_id=selcom_txn_id,
            status=erp_status,
            reason="Webhook processed",
            amount=amount,
            customer_id=customer.customer_id,
            customer_name=customer.full_name,
            motorcycle_vin=motorcycle.vin,
            company_number=company_number,
            mobile_number=mobile_number,
            raw_payload=request.body.decode("utf-8")
        )

        if erp_status != "FAILED":
            allocate_payment(customer, motorcycle, amount)
            notify_payment_processed(payment, invoice)
            return JsonResponse({"status": "success", "message": "Payment processed"})
        else:
            return JsonResponse({"status": "failed", "message": "Payment failed"}, status=400)

    except Exception as e:
        PaymentLog.objects.create(
            motorcycle_vin=data.get("reference_vin", ""),
            transaction_id=data.get("transaction_id", ""),
            status="FAILED",
            reason=str(e),
            amount=float(data.get("amount", 0)),
            company_number=data.get("company_number", ""),
            mobile_number=data.get("mobile_number", ""),
            raw_payload=request.body.decode("utf-8")
        )
        return JsonResponse({"status": "error", "message": str(e)}, status=500)



@login_required
def payment_dashboard(request):
    payments = Payment.objects.all()

    summary = {
        "full_count": payments.filter(status="FULL").count(),
        "full_total": payments.filter(status="FULL").aggregate(total=models.Sum("amount_paid"))["total"] or 0,

        "partial_count": payments.filter(status="PARTIAL").count(),
        "partial_total": payments.filter(status="PARTIAL").aggregate(total=models.Sum("amount_paid"))["total"] or 0,

        "settled_count": payments.filter(status="SETTLED").count(),
        "settled_total": payments.filter(status="SETTLED").aggregate(total=models.Sum("amount_paid"))["total"] or 0,

        "failed_count": payments.filter(status="FAILED").count(),
        "failed_total": payments.filter(status="FAILED").aggregate(total=models.Sum("amount_paid"))["total"] or 0,

        # ✅ Regenerated payments summary
        "regenerated_count": PaymentLog.objects.filter(status="REGENERATED").count(),
        "regenerated_total": PaymentLog.objects.filter(status="REGENERATED").aggregate(total=models.Sum("amount"))["total"] or 0,
    }

    context = {
        "full_payments": payments.filter(status="FULL"),
        "partial_payments": payments.filter(status="PARTIAL"),
        "settled_payments": payments.filter(status="SETTLED"),
        "failed_payments": payments.filter(status="FAILED"),
        "regenerated_logs": PaymentLog.objects.filter(status="REGENERATED").order_by("-created_on"),
        "summary": summary,
    }
    return render(request, "payments/payment_dashboard.html", context)


@login_required
def successful_payments(request):
    payments = Payment.objects.exclude(status="FAILED")
    return render(request, "payments/successful_payments.html", {"payments": payments})


@login_required
def failed_payments(request):
    payments = Payment.objects.filter(status="FAILED").order_by("-timestamp")
    return render(request, "payments/failed_payments.html", {"payments": payments})


@login_required
@user_passes_test(lambda u: getattr(u, "is_admin", False) or getattr(u, "is_manager", False) or getattr(u, "is_officer", False))
def regenerate_payment(request, payment_id):
    payment = get_object_or_404(Payment, pk=payment_id)

    if payment.status == "FAILED":
        try:
            invoice = payment.invoice
            # --- Reset status based on amount vs invoice ---
            if payment.amount_paid >= invoice.amount_due:
                payment.status = "FULL"
            elif payment.amount_paid > 0:
                payment.status = "PARTIAL"
            else:
                payment.status = "FAILED"

            payment.save()

            # --- Log regeneration action with both IDs ---
            PaymentLog.objects.create(
                invoice=invoice,
                transaction_id=payment.transaction_id,             # ERP internal ID
                selcom_transaction_id=payment.selcom_transaction_id,  # Selcom external ID
                status="REGENERATED",
                reason="Payment re-generated by admin/manager/officer",
                amount=payment.amount_paid,
                customer_id=payment.customer.customer_id if payment.customer else None,
                customer_name=payment.customer.full_name if payment.customer else None,
                motorcycle_vin=payment.motorcycle.vin if payment.motorcycle else None,
            )

            messages.success(request, f"Payment {payment.transaction_id} re-generated successfully.")
        except Exception as e:
            messages.error(request, f"Failed to re-generate payment {payment.transaction_id}: {str(e)}")
    else:
        messages.warning(request, f"Payment {payment.transaction_id} is not marked as FAILED.")

    return redirect("failed_payments")


# ✅ New Payment Logs view restricted to admins
@login_required
@user_passes_test(lambda u: getattr(u, "is_admin", False))
def payment_logs(request):
    logs = PaymentLog.objects.all()

    vin = request.GET.get("vin")
    customer = request.GET.get("customer")
    from_date = request.GET.get("from_date")
    to_date = request.GET.get("to_date")

    if vin:
        logs = logs.filter(motorcycle_vin__icontains=vin)
    if customer:
        logs = logs.filter(customer_name__icontains=customer)
    if from_date:
        logs = logs.filter(created_on__date__gte=from_date)
    if to_date:
        logs = logs.filter(created_on__date__lte=to_date)

    logs = logs.order_by("-created_on")
    return render(request, "payments/payment_logs.html", {"logs": logs})

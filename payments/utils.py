from decimal import Decimal
import hmac
import hashlib
import base64

# ⚠️ Replace with the actual secret key provided by Selcom
SELCOM_SECRET = "your_selcom_secret_key_here"


def allocate_payment(customer, motorcycle, amount_paid):
    """
    Allocate a payment across multiple invoices for a specific motorcycle VIN.
    - Oldest overdue invoices are cleared first.
    - Then pending invoices.
    - Any excess becomes credit in customer account.
    - Updates arrears and credits on invoices and customer.
    - Accumulates agent commission into agent account.
    """

    remaining_amount = Decimal(amount_paid)
    allocation_results = []

    # Step 1: Get all unpaid invoices for this motorcycle ordered by due_date
    invoices = customer.invoices.filter(
        motorcycle=motorcycle,
        status__in=["PENDING", "PARTIAL", "OVERDUE", "DEFAULTED"]
    ).order_by("due_date")

    for invoice in invoices:
        if remaining_amount <= 0:
            break

        # Outstanding balance for this invoice
        total_paid = sum(p.amount_paid for p in invoice.payments.all())
        outstanding = invoice.amount_due - total_paid

        if outstanding <= 0:
            continue  # already settled

        # Allocate payment to this invoice
        if remaining_amount >= outstanding:
            # Full settlement
            applied = outstanding
            remaining_amount -= outstanding
            invoice.status = "PAID"
            invoice.arrears = Decimal(0)
        else:
            # Partial settlement
            applied = remaining_amount
            remaining_amount = Decimal(0)
            invoice.status = "PARTIAL"
            invoice.arrears = outstanding - applied

        # Update invoice credit if overpayment
        if applied > outstanding:
            invoice.credit = applied - outstanding
        else:
            invoice.credit = Decimal(0)

        invoice.save(update_fields=["status", "arrears", "credit"])

        # ✅ Agent commission accumulation
        if invoice.agent and hasattr(invoice.agent, "commission_balance"):
            commission_rate = getattr(invoice.agent, "commission_rate", Decimal("0.05"))  # default 5%
            commission_amount = applied * commission_rate
            invoice.agent.commission_balance = getattr(invoice.agent, "commission_balance", Decimal(0)) + commission_amount
            invoice.agent.save(update_fields=["commission_balance"])
        else:
            commission_amount = Decimal(0)

        allocation_results.append({
            "invoice_id": invoice.invoice_id,
            "applied_amount": applied,
            "new_status": invoice.status,
            "arrears": str(invoice.arrears),
            "credit": str(invoice.credit),
            "agent_commission": str(commission_amount),
        })

    # Step 2: Handle excess payment as customer credit
    if remaining_amount > 0:
        allocation_results.append({
            "invoice_id": None,
            "applied_amount": remaining_amount,
            "new_status": "CREDIT"
        })
        customer.credit_balance = getattr(customer, "credit_balance", Decimal(0)) + remaining_amount
        customer.save(update_fields=["credit_balance"])

    return allocation_results


def verify_signature(payload: dict, signature: str) -> bool:
    """
    Verify Selcom webhook signature using HMAC-SHA256.
    - payload: dict of JSON body received
    - signature: value from Selcom header (e.g. X-Selcom-Signature)
    """
    try:
        # Convert payload dict into canonical string (Selcom docs define exact format)
        message = "&".join(f"{k}={v}" for k, v in sorted(payload.items()))
        computed_hmac = hmac.new(
            SELCOM_SECRET.encode("utf-8"),
            message.encode("utf-8"),
            hashlib.sha256
        ).digest()
        computed_signature = base64.b64encode(computed_hmac).decode()

        return hmac.compare_digest(computed_signature, signature)
    except Exception:
        return False

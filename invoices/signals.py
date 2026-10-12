import logging
from django.db.models.signals import post_save
from django.dispatch import receiver
from customers.models import Customer
from invoices.models import Invoice
from payments.models import Payment

logger = logging.getLogger(__name__)

# --- Customer Signal ---
@receiver(post_save, sender=Customer)
def handle_customer_post_save(sender, instance, created, **kwargs):
    logger.info(f"[Invoice Signal] Fired for {instance.full_name} ({instance.approval_status}, {instance.payment_model})")

    # --- Guard clause: only run if APPROVED and motorcycle exists ---
    if instance.approval_status != "APPROVED" or not instance.motorcycle:
        return

    # --- Guard clause: prevent duplicate invoice creation ---
    existing_invoice = Invoice.objects.filter(
        customer=instance,
        motorcycle=instance.motorcycle,
        scenario_type=instance.payment_model
    ).exists()
    if existing_invoice:
        logger.info(f"[Invoice Signal] Skipped duplicate invoice for {instance.full_name} ({instance.payment_model})")
        return

    # --- Balance calculation ---
    opening_balance = 0
    balance_remaining = 0
    credits = 0
    arrears = 0
    settled_flag = False

    try:
        if instance.payment_model == "INSTALLMENT" and hasattr(instance, "installment_plan"):
            plan = instance.installment_plan
            if plan and plan.installment_amount > 0:
                opening_balance = plan.total_amount
                balance_remaining = plan.total_amount
                settled_flag = False

        elif instance.payment_model == "LEASE" and hasattr(instance, "lease_plan"):
            plan = instance.lease_plan
            if plan and plan.weekly_lease_amount > 0:
                opening_balance = plan.total_amount
                balance_remaining = plan.total_amount
                settled_flag = False

        elif instance.payment_model == "CASH":
            opening_balance = instance.cash_amount or 0
            balance_remaining = 0
            settled_flag = True

    except (ValueError, TypeError):
        logger.error(f"[Invoice Signal] Invalid numeric values for {instance.full_name}")

    # ✅ Update balances only
    Customer.objects.filter(pk=instance.pk).update(
        opening_balance=opening_balance,
        balance_remaining=balance_remaining,
        credit_amount=credits,
        arrears_amount=arrears,
        settled_flag=settled_flag
    )

    # --- Lifecycle wiring ---
    if instance.payment_model == "CASH":
        instance.motorcycle.sell_to_customer(
            customer=instance,
            user=instance.officer_in_charge,
            payment_model="CASH"
        )
    elif instance.payment_model in ["INSTALLMENT", "LEASE"]:
        instance.motorcycle.lease_to_customer(
            customer=instance,
            user=instance.officer_in_charge
        )


# --- Payment Signal ---
@receiver(post_save, sender=Payment)
def handle_payment_post_save(sender, instance, created, **kwargs):
    customer = instance.customer
    logger.info(f"[Payment Signal] Fired for {customer.full_name} ({customer.payment_model})")

    if customer.payment_model == "CASH":
        customer.settled_flag = True

    elif customer.payment_model in ["INSTALLMENT", "LEASE"]:
        no_pending_invoices = not customer.invoices.filter(status="PENDING").exists()
        arrears_cleared = (customer.arrears_amount == 0)
        balance_cleared = (customer.balance_remaining == 0)
        customer.settled_flag = no_pending_invoices and arrears_cleared and balance_cleared

        # ❌ Lifecycle calls removed here
        # ✅ Only update flags, lifecycle handled by customer signal or tasks

    customer.save(update_fields=["settled_flag"])
    logger.info(f"[Payment Signal] Settlement recalculated for {customer.full_name}: {customer.settled_flag}")

import logging
from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import Payment
from customers.models import Customer

logger = logging.getLogger(__name__)

@receiver(post_save, sender=Payment)
def handle_payment(sender, instance, created, **kwargs):
    if not created:
        return

    customer = instance.customer
    logger.info(f"[Payment Signal] Fired for Payment {instance.transaction_id} (Customer {customer.full_name})")

    # --- Calculate arrears/credit ---
    if instance.amount_paid < instance.invoice_amount:
        instance.arrears = instance.invoice_amount - instance.amount_paid
        instance.credit = 0
        instance.status = "PARTIAL"
        logger.info(f"[Payment Signal] Partial payment: arrears {instance.arrears}")

    elif instance.amount_paid > instance.invoice_amount:
        instance.credit = instance.amount_paid - instance.invoice_amount
        instance.arrears = 0
        instance.status = "FULL"
        logger.info(f"[Payment Signal] Overpayment: credit {instance.credit}")

    else:
        instance.arrears = 0
        instance.credit = 0
        instance.status = "FULL"
        logger.info(f"[Payment Signal] Exact payment: invoice fully paid")

    # --- Update remaining balance ---
    customer.balance_remaining = max(customer.balance_remaining - instance.amount_paid, 0)
    instance.remaining_balance = customer.balance_remaining

    # --- Agent commission ---
    if instance.agent and customer.agent_commission_percent > 0:
        instance.agent_commission = (instance.amount_paid * customer.agent_commission_percent) / 100
        logger.info(f"[Payment Signal] Agent commission {instance.agent_commission}")

    # --- Settlement check ---
    if customer.balance_remaining <= 0:
        instance.status = "SETTLED"
        customer.settled_flag = True
        logger.info(f"[Payment Signal] Customer {customer.full_name} settled")
        # ❌ Removed motorcycle.mark_completed here

    customer.save(update_fields=["balance_remaining", "settled_flag", "repossession_flag"])
    instance.save(update_fields=["arrears", "credit", "remaining_balance", "agent_commission", "status"])

    # --- Recovery logic ---
    if customer.repossession_flag and instance.status in ["FULL", "SETTLED"]:
        customer.repossession_flag = False
        customer.save(update_fields=["repossession_flag"])
        logger.info(f"[Payment Signal] Repossession flag cleared for {customer.full_name}")
        # ❌ Removed motorcycle.restore_to_active here

import logging
from django.db.models.signals import post_save
from django.dispatch import receiver

from payments.models import Payment
from invoices.models import Invoice
from accounting.models import LedgerEntry, CustomerAccount, AgentAccount

logger = logging.getLogger(__name__)


@receiver(post_save, sender=Payment)
def handle_payment_post_save(sender, instance, created, **kwargs):
    """
    When a payment is posted:
    - Create a LedgerEntry with VIN + mobile number.
    - Update CustomerAccount balances (credit/arrears).
    - Accrue agent commission.
    """
    if not created:
        return

    customer = instance.customer
    invoice = instance.invoice
    motorcycle = invoice.motorcycle if invoice else None

    # Ledger entry with payment source
    LedgerEntry.objects.create(
        customer=customer,
        motorcycle=motorcycle,
        invoice=invoice,
        entry_type="CREDIT" if instance.amount_paid >= invoice.amount_due else "DEBIT",
        amount=instance.amount_paid,
        description="Payment received",
        transaction_id=instance.transaction_id,
        mobile_number=instance.mobile_number,
        bank_account=instance.bank_account,
    )
    logger.info(f"[Accounting Signal] Ledger entry created for {customer.full_name} payment {instance.transaction_id}")

    # Update CustomerAccount balances
    account, _ = CustomerAccount.objects.get_or_create(customer=customer, motorcycle=motorcycle)
    account.apply_payment(
        invoice,
        instance.amount_paid,
        transaction_id=instance.transaction_id,
        mobile_number=instance.mobile_number,
        bank_account=instance.bank_account
    )

    # Accrue agent commission
    if customer.agent and invoice:
        commission_amount = invoice.agent_commission
        agent_account, _ = AgentAccount.objects.get_or_create(agent=customer.agent)
        agent_account.accrue_commission(invoice, commission_amount)
        logger.info(f"[Accounting Signal] Commission {commission_amount} accrued for agent {customer.agent.name}")


@receiver(post_save, sender=Invoice)
def handle_invoice_post_save(sender, instance, created, **kwargs):
    """
    When a new invoice is created:
    - Apply available credits.
    - Apply arrears.
    """
    customer = instance.customer
    account, _ = CustomerAccount.objects.get_or_create(customer=customer, motorcycle=instance.motorcycle)
    account.apply_credit_to_invoice(instance)
    account.apply_arrears_to_invoice(instance)
    logger.info(f"[Accounting Signal] Applied credits/arrears to invoice {instance.invoice_id}")

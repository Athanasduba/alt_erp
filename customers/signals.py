import logging
from datetime import date
from django.db.models.signals import pre_save, post_save
from django.dispatch import receiver
from django.utils import timezone
from django.apps import apps
from .models import Customer, InstallmentPlan, LeasePlan
from invoices.tasks import generate_first_invoice
from payments.models import Payment

logger = logging.getLogger(__name__)
Motorcycle = apps.get_model("motorcycles", "Motorcycle")

# 🔑 Unified helper for financial tracking
def update_financial_tracking(customer, plan=None, cash_amount=None):
    if customer.payment_model == "CASH" and cash_amount:
        customer.opening_balance = cash_amount
        customer.balance_remaining = 0
        customer.credit_amount = cash_amount
        customer.settled_flag = True

    elif customer.payment_model == "INSTALLMENT" and plan:
        customer.opening_balance = plan.total_amount
        customer.balance_remaining = plan.total_amount
        customer.credit_amount = 0
        customer.settled_flag = False

    elif customer.payment_model == "LEASE" and plan:
        customer.opening_balance = plan.total_amount
        customer.balance_remaining = plan.total_amount
        customer.credit_amount = 0
        customer.settled_flag = False

    customer.arrears_amount = 0
    customer.missed_invoices_count = 0
    customer.repossession_flag = False
    customer.last_financial_update = timezone.now()

    customer._skip_signals = True
    customer.save(update_fields=[
        'opening_balance', 'balance_remaining', 'credit_amount',
        'arrears_amount', 'settled_flag', 'missed_invoices_count',
        'repossession_flag', 'last_financial_update'
    ])


# --- Track approval status change BEFORE save ---
@receiver(pre_save, sender=Customer)
def detect_approval_change(sender, instance, **kwargs):
    if getattr(instance, "_skip_signals", False):
        return
    if not instance.pk:
        return
    previous_status = Customer.objects.filter(pk=instance.pk).values_list("approval_status", flat=True).first()
    instance._was_pending = (previous_status == "PENDING")


# --- Handle customer AFTER save ---
@receiver(post_save, sender=Customer)
def handle_customer_post_save(sender, instance, created, **kwargs):
    if getattr(instance, "_skip_signals", False):
        return

    logger.info(f"[Customer Signal] Fired for {instance.full_name} ({instance.approval_status}, {instance.payment_model})")

    if instance.approval_status == "APPROVED" and instance.motorcycle:
        # ✅ Detect if motorcycle was retained before approval
        was_retained = (instance.motorcycle.status == "RETAINED")

        if instance.payment_model == "CASH":
            instance.motorcycle.sell_to_customer(
                customer=instance,
                user=instance.officer_in_charge,
                payment_model="CASH",
                is_resale=was_retained   # ensures RESOLD_CASH if retained
            )
        elif instance.payment_model == "INSTALLMENT":
            instance.motorcycle.sell_to_customer(
                customer=instance,
                user=instance.officer_in_charge,
                payment_model="INSTALLMENT",
                is_resale=was_retained   # ensures RESOLD_INSTALLMENT if retained
            )
        elif instance.payment_model == "LEASE":
            instance.motorcycle.lease_to_customer(
                customer=instance,
                user=instance.officer_in_charge,
                is_resale=was_retained   # ensures RELEASED if retained
            )

        # ✅ Trigger Celery task for first invoice
        generate_first_invoice.delay(instance.id)

    instance._skip_signals = False


# --- Attach motorcycle VIN to invoices ---
@receiver(post_save, sender=Motorcycle)
def update_invoices_with_motorcycle(sender, instance, created, **kwargs):
    if instance.customer_account:
        customer = instance.customer_account
        for invoice in customer.invoices.filter(motorcycle__isnull=True):
            invoice.motorcycle = instance
            invoice.save()


# --- Sync balances after payment ---
@receiver(post_save, sender=Payment)
def update_customer_balance_on_payment(sender, instance, created, **kwargs):
    if created:
        customer = instance.customer
        motorcycle = customer.motorcycle

        # Balance updates (existing logic)
        if customer.payment_model == "INSTALLMENT":
            plan = getattr(customer, "installment_plan", None)
            if plan and instance.invoice:
                if instance.invoice.scenario_type == "DEPOSIT":
                    customer.balance_remaining = customer.opening_balance - plan.initial_deposit
                else:
                    customer.balance_remaining = instance.remaining_balance
            else:
                customer.balance_remaining = instance.remaining_balance
        else:
            customer.balance_remaining = instance.remaining_balance

        customer.credit_amount = instance.credit
        customer.arrears_amount = instance.arrears
        customer.settled_flag = (customer.balance_remaining <= 0)
        customer.last_financial_update = timezone.now()

        missed_count = customer.invoices.filter(
            scenario_type="INSTALLMENT",
            status="PENDING",
            due_date__lt=date.today()
        ).count()
        customer.missed_invoices_count = missed_count

        customer._skip_signals = True
        customer.save(update_fields=[
            "credit_amount", "arrears_amount", "balance_remaining",
            "settled_flag", "last_financial_update", "missed_invoices_count"
        ])
        customer._skip_signals = False

        # --- Lifecycle wiring ---
        if motorcycle:
            if customer.settled_flag:
                motorcycle.mark_completed(payment_model=customer.payment_model)
            elif customer.arrears_amount == 0 and not customer.repossession_flag:
                motorcycle.return_to_customer(customer, user=customer.officer_in_charge)
            elif customer.repossession_flag:
                motorcycle.defaulted(user=customer.officer_in_charge)
                if getattr(customer, "resell_to_customer", None):
                    motorcycle.resell_after_default(
                        new_customer=customer.resell_to_customer,
                        user=customer.officer_in_charge,
                        payment_model=customer.payment_model
                    )

        logger.info(f"[Customer Signal] Financial + lifecycle updated for {customer.full_name} after payment {instance.transaction_id}")


# --- Update balances immediately after plan save ---
@receiver(post_save, sender=InstallmentPlan)
def update_financial_after_installment(sender, instance, created, **kwargs):
    customer = instance.customer
    if not getattr(customer, "_skip_signals", False):
        update_financial_tracking(customer, plan=instance)
        logger.info(f"[Financial Signal] Updated balances for {customer.full_name} after InstallmentPlan save.")


@receiver(post_save, sender=InstallmentPlan)
def update_initial_deposit_commission(sender, instance, created, **kwargs):
    customer = instance.customer
    if customer.agent_commission_percent > 0 and instance.initial_deposit > 0:
        commission = (instance.initial_deposit * customer.agent_commission_percent) / 100
        customer.per_initial_deposit_commission = commission
        customer._skip_signals = True
        customer.save(update_fields=["per_initial_deposit_commission"])
        customer._skip_signals = False
        logger.info(f"[Commission Signal] Initial deposit commission set for {customer.full_name}: {commission}")


@receiver(post_save, sender=LeasePlan)
def update_financial_after_lease(sender, instance, created, **kwargs):
    customer = instance.customer
    if not getattr(customer, "_skip_signals", False):
        update_financial_tracking(customer, plan=instance)
        logger.info(f"[Financial Signal] Updated balances for {customer.full_name} after LeasePlan save.")

from celery import shared_task
from datetime import date
from dateutil.relativedelta import relativedelta
from invoices.models import Invoice
from customers.models import Customer
from notifications.tasks import task_notify_invoice_generated
import logging

logger = logging.getLogger(__name__)

# --- Helper: Generate invoice ID ---
def generate_invoice_id(motorcycle, scenario_type):
    base = motorcycle.vin.replace(" ", "")
    existing_count = Invoice.objects.filter(motorcycle=motorcycle, scenario_type=scenario_type).count()
    sequence = str(existing_count + 1).zfill(4)
    return f"{base}{sequence}"

# --- First invoice after approval ---
@shared_task
def generate_first_invoice(customer_id):
    try:
        customer = Customer.objects.get(pk=customer_id)
        if customer.approval_status != "APPROVED":
            return

        motorcycle = customer.motorcycle
        if not motorcycle:
            return

        if customer.payment_model == "CASH" and customer.cash_amount:
            if not Invoice.objects.filter(motorcycle=motorcycle, scenario_type="CASH").exists():
                invoice_id = generate_invoice_id(motorcycle, "CASH")
                invoice = Invoice.objects.create(
                    customer=customer,
                    motorcycle=motorcycle,
                    agent=customer.agent,
                    invoice_id=invoice_id,
                    amount_due=customer.cash_amount,
                    agent_commission=customer.calculate_commission(customer.cash_amount),
                    due_date=date.today(),
                    status="PAID",
                    scenario_type="CASH"
                )
                task_notify_invoice_generated.delay(invoice.id)
                logger.info(f"[Celery Task] CASH invoice {invoice.invoice_id} created for VIN {motorcycle.vin}")

        elif customer.payment_model == "INSTALLMENT" and customer.installment_plan:
            plan = customer.installment_plan
            if plan.initial_deposit > 0 and not Invoice.objects.filter(motorcycle=motorcycle, scenario_type="DEPOSIT").exists():
                invoice_id = generate_invoice_id(motorcycle, "DEPOSIT")
                invoice = Invoice.objects.create(
                    customer=customer,
                    motorcycle=motorcycle,
                    agent=customer.agent,
                    invoice_id=invoice_id,
                    amount_due=plan.initial_deposit,
                    agent_commission=customer.calculate_commission(plan.initial_deposit),
                    due_date=plan.start_date,
                    status="PENDING",
                    scenario_type="DEPOSIT"
                )
                task_notify_invoice_generated.delay(invoice.id)
                logger.info(f"[Celery Task] Deposit invoice {invoice.invoice_id} created for VIN {motorcycle.vin}")

        elif customer.payment_model == "LEASE" and customer.lease_plan:
            plan = customer.lease_plan
            first_due_date = plan.start_date + relativedelta(weeks=1)
            if not Invoice.objects.filter(motorcycle=motorcycle, due_date=first_due_date, scenario_type="LEASE").exists():
                invoice_id = generate_invoice_id(motorcycle, "LEASE")
                invoice = Invoice.objects.create(
                    customer=customer,
                    motorcycle=motorcycle,
                    agent=customer.agent,
                    invoice_id=invoice_id,
                    amount_due=plan.weekly_lease_amount,
                    agent_commission=customer.calculate_commission(plan.weekly_lease_amount),
                    due_date=first_due_date,
                    status="PENDING",
                    scenario_type="LEASE"
                )
                task_notify_invoice_generated.delay(invoice.id)
                logger.info(f"[Celery Task] First lease invoice {invoice.invoice_id} created for VIN {motorcycle.vin} due {first_due_date}")

    except Customer.DoesNotExist:
        return

# --- Overdue check ---
@shared_task
def check_overdue_invoices():
    overdue_invoices = Invoice.objects.filter(due_date__lt=date.today(), status='PENDING')
    for invoice in overdue_invoices:
        invoice.status = 'OVERDUE'
        invoice.save()

        customer_invoices = Invoice.objects.filter(motorcycle=invoice.motorcycle).order_by('due_date')
        consecutive_overdue = 0
        for inv in customer_invoices:
            if inv.status == 'OVERDUE':
                consecutive_overdue += 1
                if consecutive_overdue >= 2:
                    inv.status = 'DEFAULTED'
                    inv.save()
                    motorcycle = inv.motorcycle
                    if motorcycle:
                        # ✅ Only call lifecycle once
                        motorcycle.defaulted(user=None)
                    break
            else:
                consecutive_overdue = 0

# --- Installment invoices (recurring) ---
@shared_task
def generate_installment_invoices(customer_id):
    try:
        customer = Customer.objects.get(pk=customer_id)
        plan = customer.installment_plan
        motorcycle = customer.motorcycle
        if not plan or not plan.start_date or not motorcycle:
            return

        if customer.balance_remaining <= 0:
            logger.info(f"[Celery Task] Customer {customer.full_name} settled, no more installment invoices for VIN {motorcycle.vin}")
            return

        last_invoice = Invoice.objects.filter(motorcycle=motorcycle, scenario_type="INSTALLMENT").order_by("-due_date").first()
        next_due_date = (last_invoice.due_date + plan.get_schedule_delta(1)) if last_invoice else plan.start_date

        if next_due_date <= plan.end_date:
            if Invoice.objects.filter(motorcycle=motorcycle, due_date=next_due_date, scenario_type="INSTALLMENT").exists():
                return

            adjusted_amount = max(plan.installment_amount + customer.arrears_amount - customer.credit_amount, 0)
            invoice_id = generate_invoice_id(motorcycle, "INSTALLMENT")
            status = "SCHEDULED" if next_due_date > date.today() else "PENDING"

            invoice = Invoice.objects.create(
                customer=customer,
                motorcycle=motorcycle,
                agent=customer.agent,
                invoice_id=invoice_id,
                amount_due=adjusted_amount,
                agent_commission=customer.calculate_commission(adjusted_amount),
                due_date=next_due_date,
                status=status,
                scenario_type="INSTALLMENT"
            )

            if status == "PENDING":
                task_notify_invoice_generated.delay(invoice.id)
                logger.info(f"[Celery Task] NEW Installment invoice {invoice.invoice_id} created for VIN {motorcycle.vin} due {next_due_date}")

            customer.arrears_amount = 0
            customer.credit_amount = 0
            customer.save(update_fields=["arrears_amount", "credit_amount"])

        if date.today() >= plan.end_date and customer.balance_remaining > 0:
            customer.arrears_amount = customer.balance_remaining
            customer.save(update_fields=["arrears_amount"])
            motorcycle.flag_arrears(user=None, amount=customer.arrears_amount)
        elif customer.balance_remaining <= 0:
            customer.settled_flag = True
            customer.save(update_fields=["settled_flag"])

    except Customer.DoesNotExist:
        return

# --- Lease invoices (recurring) ---
@shared_task
def generate_lease_invoices(customer_id):
    try:
        customer = Customer.objects.get(pk=customer_id)
        plan = customer.lease_plan
        motorcycle = customer.motorcycle
        if not plan or not plan.start_date or not motorcycle:
            return

        # stop if balance is cleared
        if customer.balance_remaining <= 0:
            logger.info(f"[Celery Task] Customer {customer.full_name} settled, no more lease invoices for VIN {motorcycle.vin}")
            return

        last_invoice = Invoice.objects.filter(motorcycle=motorcycle, scenario_type="LEASE").order_by("-due_date").first()
        if not last_invoice or not last_invoice.due_date:
            return

        next_due_date = last_invoice.due_date + relativedelta(weeks=1)
        if next_due_date <= plan.end_date:
            if Invoice.objects.filter(motorcycle=motorcycle, due_date=next_due_date, scenario_type="LEASE").exists():
                return

            adjusted_amount = max(plan.weekly_lease_amount + customer.arrears_amount - customer.credit_amount, 0)
            invoice_id = generate_invoice_id(motorcycle, "LEASE")
            status = "SCHEDULED" if next_due_date > date.today() else "PENDING"

            invoice = Invoice.objects.create(
                customer=customer,
                motorcycle=motorcycle,
                agent=customer.agent,
                invoice_id=invoice_id,
                amount_due=adjusted_amount,
                agent_commission=customer.calculate_commission(adjusted_amount),
                due_date=next_due_date,
                status=status,
                scenario_type="LEASE"
            )

            if status == "PENDING":
                task_notify_invoice_generated.delay(invoice.id)
                logger.info(f"[Celery Task] NEW Lease invoice {invoice.invoice_id} created for VIN {motorcycle.vin} due {next_due_date}")

            customer.arrears_amount = 0
            customer.credit_amount = 0
            customer.save(update_fields=["arrears_amount", "credit_amount"])

        if date.today() >= plan.end_date and customer.balance_remaining > 0:
            # Plan ended but balance still remains → mark arrears
            customer.arrears_amount = customer.balance_remaining
            customer.save(update_fields=["arrears_amount"])
            motorcycle.flag_arrears(user=None, amount=customer.arrears_amount)
            logger.info(f"[Celery Task] Lease plan ended with arrears for VIN {motorcycle.vin}")
        elif customer.balance_remaining <= 0:
            # Balance cleared → mark as settled
            customer.settled_flag = True
            customer.save(update_fields=["settled_flag"])
            logger.info(f"[Celery Task] Lease plan settled for VIN {motorcycle.vin}")

    except Customer.DoesNotExist:
        return

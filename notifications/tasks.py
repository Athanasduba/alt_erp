from celery import shared_task, group, chord
from monitoring.models import NotificationLog
from django.utils.timezone import now
from django.contrib.auth import get_user_model

User = get_user_model()

# Convert send_sms into a Celery task
@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def send_sms(self, phone_number, message, role, customer_name, motorcycle_vin):
    """
    Celery task to send SMS.
    Retries up to 3 times if sending fails.
    """
    try:
        # Replace with your actual SMS API integration logic
        print(f"[SMS] Sending to {phone_number} ({role}): {message}")
        # Example: sms_api.send(phone_number, message)
        return {"status": "SENT", "role": role, "customer": customer_name, "vin": motorcycle_vin}
    except Exception as exc:
        raise self.retry(exc=exc)

def log_notification(role, customer_name, motorcycle_vin, phone_number, message, status="QUEUED"):
    """Helper to persist notification logs into ERP, avoiding duplicates."""
    if not NotificationLog.objects.filter(
        role=role,
        customer_name=customer_name,
        motorcycle_vin=motorcycle_vin,
        phone_number=phone_number or "N/A",
        message=message
    ).exists():
        NotificationLog.objects.create(
            role=role,
            customer_name=customer_name,
            motorcycle_vin=motorcycle_vin,
            phone_number=phone_number or "N/A",
            message=message,
            sent_at=now(),
            status=status
        )

@shared_task
def task_notify_invoice_generated(invoice_id):
    """Triggered when a new invoice is created."""
    from invoices.models import Invoice
    try:
        invoice = Invoice.objects.get(id=invoice_id)
        customer = invoice.customer
        motorcycle = invoice.motorcycle

        sms_message = (
            f"Dear {customer.full_name},\n"
            f"Invoice {invoice.invoice_id} for Motorcycle {motorcycle.vin}\n"
            f"Amount: {invoice.amount_due}\n"
            f"Due Date: {invoice.due_date}\n"
            f"Help: Company No {getattr(customer, 'company_number', '')}, Ref {motorcycle.vin}"
        )

        tasks = []

        if customer.mobile_number:
            tasks.append(send_sms.s(customer.mobile_number, sms_message, "CUSTOMER", customer.full_name, motorcycle.vin))
            log_notification("CUSTOMER", customer.full_name, motorcycle.vin, customer.mobile_number, sms_message)

        if customer.agent and customer.agent.mobile_number:
            tasks.append(send_sms.s(customer.agent.mobile_number, sms_message, "AGENT", customer.full_name, motorcycle.vin))
            log_notification("AGENT", customer.full_name, motorcycle.vin, customer.agent.mobile_number, sms_message)

        if getattr(customer, "officer_number", None):
            tasks.append(send_sms.s(customer.officer_number, sms_message, "OFFICER", customer.full_name, motorcycle.vin))
            log_notification("OFFICER", customer.full_name, motorcycle.vin, customer.officer_number, sms_message)

        for acc in User.objects.filter(role="ACCOUNTANT"):
            if acc.phone_number:
                tasks.append(send_sms.s(acc.phone_number, sms_message, "ACCOUNTANT", customer.full_name, motorcycle.vin))
                log_notification("ACCOUNTANT", customer.full_name, motorcycle.vin, acc.phone_number, sms_message)

        # Run group in parallel with chord callback
        if tasks:
            chord(group(tasks))(batch_complete.s(f"Invoice {invoice.invoice_id} notifications complete"))

    except Invoice.DoesNotExist:
        print(f"[Celery] Invoice {invoice_id} not found for notification")

@shared_task
def task_notify_payment_processed(payment_id):
    """Triggered when a payment is created."""
    from payments.models import Payment
    try:
        payment = Payment.objects.get(id=payment_id)
        invoice = payment.invoice
        customer = payment.customer
        motorcycle = payment.motorcycle

        arrears = payment.arrears
        credit = payment.credit
        amount_due = invoice.amount_due + arrears - credit

        sms_message = (
            f"Payment received for {customer.full_name}\n"
            f"Invoice {invoice.invoice_id}, Motorcycle {motorcycle.vin}\n"
            f"Paid: {payment.amount_paid}, Credit: {credit}, Arrears: {arrears}\n"
            f"Balance Due: {amount_due}\n"
            f"Help: Company No {payment.company_number}, Ref {motorcycle.vin}"
        )

        tasks = []

        if customer.mobile_number:
            tasks.append(send_sms.s(customer.mobile_number, sms_message, "CUSTOMER", customer.full_name, motorcycle.vin))
            log_notification("CUSTOMER", customer.full_name, motorcycle.vin, customer.mobile_number, sms_message)

        if customer.agent and customer.agent.mobile_number:
            tasks.append(send_sms.s(customer.agent.mobile_number, sms_message, "AGENT", customer.full_name, motorcycle.vin))
            log_notification("AGENT", customer.full_name, motorcycle.vin, customer.agent.mobile_number, sms_message)

        if getattr(customer, "officer_number", None):
            tasks.append(send_sms.s(customer.officer_number, sms_message, "OFFICER", customer.full_name, motorcycle.vin))
            log_notification("OFFICER", customer.full_name, motorcycle.vin, customer.officer_number, sms_message)

        for acc in User.objects.filter(role="ACCOUNTANT"):
            if acc.phone_number:
                tasks.append(send_sms.s(acc.phone_number, sms_message, "ACCOUNTANT", customer.full_name, motorcycle.vin))
                log_notification("ACCOUNTANT", customer.full_name, motorcycle.vin, acc.phone_number, sms_message)

        if tasks:
            chord(group(tasks))(batch_complete.s(f"Payment {payment.transaction_id} notifications complete"))

    except Payment.DoesNotExist:
        print(f"[Celery] Payment {payment_id} not found for notification")

@shared_task
def task_send_payment_reminders():
    """Daily scheduled task (Celery beat)."""
    reminders = send_payment_reminders()
    tasks = []
    for reminder in reminders:
        tasks.append(send_sms.s(reminder["phone_number"], reminder["message"], "CUSTOMER",
                                reminder["customer_name"], reminder["motorcycle_vin"]))
        log_notification("CUSTOMER", reminder["customer_name"], reminder["motorcycle_vin"],
                         reminder["phone_number"], reminder["message"], status="QUEUED")

    if tasks:
        chord(group(tasks))(batch_complete.s("Daily payment reminders complete"))

@shared_task
def batch_complete(results, message):
    """Callback after all notifications in a group are done."""
    recipient_count = len(results)
    summary_message = f"{message} — {recipient_count} recipients notified"

    print(f"[Celery] {summary_message}")
    NotificationLog.objects.create(
        role="SYSTEM",
        customer_name="",
        motorcycle_vin="",
        phone_number="N/A",
        message=summary_message,
        sent_at=now(),
        status="SENT"
    )

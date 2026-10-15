from celery import shared_task, group, chord
from notifications.utils import send_sms, send_payment_reminders
from monitoring.models import NotificationLog
from django.utils.timezone import now
from django.contrib.auth import get_user_model

User = get_user_model()

@shared_task
def task_notify_invoice_generated(invoice_id):
    """
    Triggered when a new invoice is created.
    Queues SMS notifications for Customer, Agent, Officer, and Accountants as a group,
    and logs each notification to NotificationLog.
    """
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

        # Customer
        if getattr(customer, "mobile_number", None):
            tasks.append(send_sms.s(customer.mobile_number, sms_message,
                                    "CUSTOMER", customer.full_name, motorcycle.vin))
            NotificationLog.objects.create(
                role="CUSTOMER",
                customer_name=customer.full_name,
                motorcycle_vin=motorcycle.vin,
                phone_number=customer.mobile_number,
                message=sms_message,
                sent_at=now(),
                status="QUEUED"
            )

        # Agent
        if customer.agent and getattr(customer.agent, "mobile_number", None):
            tasks.append(send_sms.s(customer.agent.mobile_number, sms_message,
                                    "AGENT", customer.full_name, motorcycle.vin))
            NotificationLog.objects.create(
                role="AGENT",
                customer_name=customer.full_name,
                motorcycle_vin=motorcycle.vin,
                phone_number=customer.agent.mobile_number,
                message=sms_message,
                sent_at=now(),
                status="QUEUED"
            )

        # Officer
        officer_number = getattr(customer, "officer_number", None)
        if officer_number:
            tasks.append(send_sms.s(officer_number, sms_message,
                                    "OFFICER", customer.full_name, motorcycle.vin))
            NotificationLog.objects.create(
                role="OFFICER",
                customer_name=customer.full_name,
                motorcycle_vin=motorcycle.vin,
                phone_number=officer_number,
                message=sms_message,
                sent_at=now(),
                status="QUEUED"
            )

        # Accountants
        accountants = User.objects.filter(role="ACCOUNTANT")
        for acc in accountants:
            if acc.phone_number:
                tasks.append(send_sms.s(acc.phone_number, sms_message,
                                        "ACCOUNTANT", customer.full_name, motorcycle.vin))
                NotificationLog.objects.create(
                    role="ACCOUNTANT",
                    customer_name=customer.full_name,
                    motorcycle_vin=motorcycle.vin,
                    phone_number=acc.phone_number,
                    message=sms_message,
                    sent_at=now(),
                    status="QUEUED"
                )

        # Run group with chord callback
        chord(group(tasks))(batch_complete.s(f"Invoice {invoice.invoice_id} notifications complete"))

    except Invoice.DoesNotExist:
        print(f"[Celery] Invoice {invoice_id} not found for notification")

@shared_task
def task_notify_payment_processed(payment_id):
    """
    Triggered when a payment is created.
    Queues SMS notifications for Customer, Agent, Officer, and Accountants as a group,
    and logs each notification to NotificationLog.
    """
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

        # Customer
        if getattr(customer, "mobile_number", None):
            tasks.append(send_sms.s(customer.mobile_number, sms_message,
                                    "CUSTOMER", customer.full_name, motorcycle.vin))
            NotificationLog.objects.create(
                role="CUSTOMER",
                customer_name=customer.full_name,
                motorcycle_vin=motorcycle.vin,
                phone_number=customer.mobile_number,
                message=sms_message,
                sent_at=now(),
                status="QUEUED"
            )

        # Agent
        if customer.agent and getattr(customer.agent, "mobile_number", None):
            tasks.append(send_sms.s(customer.agent.mobile_number, sms_message,
                                    "AGENT", customer.full_name, motorcycle.vin))
            NotificationLog.objects.create(
                role="AGENT",
                customer_name=customer.full_name,
                motorcycle_vin=motorcycle.vin,
                phone_number=customer.agent.mobile_number,
                message=sms_message,
                sent_at=now(),
                status="QUEUED"
            )

        # Officer
        officer_number = getattr(customer, "officer_number", None)
        if officer_number:
            tasks.append(send_sms.s(officer_number, sms_message,
                                    "OFFICER", customer.full_name, motorcycle.vin))
            NotificationLog.objects.create(
                role="OFFICER",
                customer_name=customer.full_name,
                motorcycle_vin=motorcycle.vin,
                phone_number=officer_number,
                message=sms_message,
                sent_at=now(),
                status="QUEUED"
            )

        # Accountants
        accountants = User.objects.filter(role="ACCOUNTANT")
        for acc in accountants:
            if acc.phone_number:
                tasks.append(send_sms.s(acc.phone_number, sms_message,
                                        "ACCOUNTANT", customer.full_name, motorcycle.vin))
                NotificationLog.objects.create(
                    role="ACCOUNTANT",
                    customer_name=customer.full_name,
                    motorcycle_vin=motorcycle.vin,
                    phone_number=acc.phone_number,
                    message=sms_message,
                    sent_at=now(),
                    status="QUEUED"
                )

        # Run group with chord callback
        chord(group(tasks))(batch_complete.s(f"Payment {payment.transaction_id} notifications complete"))

    except Payment.DoesNotExist:
        print(f"[Celery] Payment {payment_id} not found for notification")

@shared_task
def task_send_payment_reminders():
    """
    Daily scheduled task (Celery beat).
    Sends reminders to customers only, starting 2 days after invoice creation.
    """
    send_payment_reminders()

@shared_task
def batch_complete(results, message):
    """
    Callback after all notifications in a group are done.
    Logs completion both to console and NotificationLog, including recipient count.
    """
    recipient_count = len(results)  # number of individual SMS tasks executed
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

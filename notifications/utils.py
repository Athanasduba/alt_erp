from django.utils.timezone import now
from datetime import timedelta
from monitoring.models import NotificationLog  # ✅ import NotificationLog model
from django.contrib.auth import get_user_model

User = get_user_model()

# -----------------------------
# Core SMS sender
# -----------------------------
def send_sms(to_number, message, role="CUSTOMER", customer_name="", motorcycle_vin=""):
    """
    Send SMS and log it in NotificationLog.
    Works for Customer, Agent, Officer, Accountant, etc.
    """
    if to_number:
        NotificationLog.objects.create(
            role=role,
            customer_name=customer_name,
            motorcycle_vin=motorcycle_vin,
            phone_number=to_number,
            message=message,
            sent_at=now(),
            status="SENT"
        )
        print(f"SMS to {role} ({to_number}): {message}")
        # TODO: integrate with SMS provider (Twilio, Selcom SMS API, Africa's Talking, etc.)
    else:
        NotificationLog.objects.create(
            role=role,
            customer_name=customer_name,
            motorcycle_vin=motorcycle_vin,
            phone_number="N/A",
            message=message,
            sent_at=now(),
            status="FAILED"
        )

# -----------------------------
# Invoice Notifications
# -----------------------------
def notify_invoice_generated(invoice):
    """Notify customer, agent, officer, and accountants when a new invoice is generated."""
    customer = invoice.customer
    motorcycle = invoice.motorcycle

    sms_message = (
        f"Dear {customer.full_name},\n"
        f"Invoice {invoice.invoice_id} for Motorcycle {motorcycle.vin}\n"
        f"Amount: {invoice.amount_due}\n"
        f"Due Date: {invoice.due_date}\n"
        f"Help: Company No {getattr(customer, 'company_number', '')}, Ref {motorcycle.vin}"
    )

    # Customer
    send_sms(getattr(customer, "mobile_number", None), sms_message,
             role="CUSTOMER", customer_name=customer.full_name, motorcycle_vin=motorcycle.vin)

    # Agent
    if customer.agent and getattr(customer.agent, "mobile_number", None):
        send_sms(customer.agent.mobile_number, sms_message,
                 role="AGENT", customer_name=customer.full_name, motorcycle_vin=motorcycle.vin)

    # Officer
    officer_number = getattr(customer, "officer_number", None)
    if officer_number:
        send_sms(officer_number, sms_message,
                 role="OFFICER", customer_name=customer.full_name, motorcycle_vin=motorcycle.vin)

    # Accountants (all users with role ACCOUNTANT)
    accountants = User.objects.filter(role="ACCOUNTANT")
    for acc in accountants:
        if acc.phone_number:
            send_sms(acc.phone_number, sms_message,
                     role="ACCOUNTANT", customer_name=customer.full_name, motorcycle_vin=motorcycle.vin)

# -----------------------------
# Payment Notifications
# -----------------------------
def notify_payment_processed(payment, invoice):
    """Notify customer, agent, officer, and accountants when a payment is processed."""
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

    # Customer
    send_sms(getattr(customer, "mobile_number", None), sms_message,
             role="CUSTOMER", customer_name=customer.full_name, motorcycle_vin=motorcycle.vin)

    # Agent
    if customer.agent and getattr(customer.agent, "mobile_number", None):
        send_sms(customer.agent.mobile_number, sms_message,
                 role="AGENT", customer_name=customer.full_name, motorcycle_vin=motorcycle.vin)

    # Officer
    officer_number = getattr(customer, "officer_number", None)
    if officer_number:
        send_sms(officer_number, sms_message,
                 role="OFFICER", customer_name=customer.full_name, motorcycle_vin=motorcycle.vin)

    # Accountants (all users with role ACCOUNTANT)
    accountants = User.objects.filter(role="ACCOUNTANT")
    for acc in accountants:
        if acc.phone_number:
            send_sms(acc.phone_number, sms_message,
                     role="ACCOUNTANT", customer_name=customer.full_name, motorcycle_vin=motorcycle.vin)

# -----------------------------
# Scheduled Reminders
# -----------------------------
def send_payment_reminders():
    """
    Daily task: send reminders to customers only.
    - Start 2 days after invoice creation.
    - Continue until invoice is paid.
    """
    from invoices.models import Invoice  # ✅ lazy import to avoid circular dependency

    today = now().date()
    invoices = Invoice.objects.filter(status__in=["PENDING", "PARTIAL", "OVERDUE"])

    for invoice in invoices:
        if (today - invoice.created_at.date()).days >= 2:
            customer = invoice.customer
            motorcycle = invoice.motorcycle
            arrears = sum(p.arrears for p in invoice.payments.all())
            credit = sum(p.credit for p in invoice.payments.all())
            amount_due = invoice.amount_due + arrears - credit

            sms_message = (
                f"Reminder: Dear {customer.full_name},\n"
                f"Invoice {invoice.invoice_id} for Motorcycle {motorcycle.vin}\n"
                f"Amount Due: {amount_due}\n"
                f"Pay before {invoice.due_date}\n"
                f"Help: Company No {getattr(customer, 'company_number', '')}, Ref {motorcycle.vin}"
            )
            send_sms(getattr(customer, "mobile_number", None), sms_message,
                     role="CUSTOMER", customer_name=customer.full_name, motorcycle_vin=motorcycle.vin)

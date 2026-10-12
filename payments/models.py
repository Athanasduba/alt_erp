import uuid
from decimal import Decimal
from django.db import models
from invoices.models import Invoice
from customers.models import Customer
from motorcycles.models import Motorcycle
from agents.models import Agent
from sales.models import Sale   # ✅ add Sale for Cash/Installment
from notifications.tasks import task_notify_payment_processed  # ✅ Celery task


def generate_transaction_id():
    return uuid.uuid4().hex[:10].upper()


class Payment(models.Model):
    STATUS_CHOICES = [
        ("FULL", "Full Paid"),
        ("PARTIAL", "Partial Paid"),
        ("SETTLED", "Settled (balance reached 0)"),
        ("FAILED", "Failed"),
    ]

    transaction_id = models.CharField(
        max_length=100,
        unique=True,
        default=generate_transaction_id
    )

    # --- NEW FIELD for Selcom integration ---
    selcom_transaction_id = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        unique=True,
        help_text="Unique transaction ID returned by Selcom API"
    )

    # ✅ Dual linkage: either invoice (Lease) or sale (Cash/Installment)
    invoice = models.ForeignKey(Invoice, on_delete=models.CASCADE, null=True, blank=True, related_name="payments")
    sale = models.ForeignKey(Sale, on_delete=models.CASCADE, null=True, blank=True, related_name="payments")

    # ✅ Reference by customer_id instead of numeric PK
    customer = models.ForeignKey(
        Customer,
        on_delete=models.CASCADE,
        related_name="payments",
        to_field="customer_id"
    )
    motorcycle = models.ForeignKey(Motorcycle, on_delete=models.SET_NULL, null=True, blank=True, related_name="payments")
    agent = models.ForeignKey(Agent, on_delete=models.SET_NULL, null=True, blank=True, related_name="payments")

    invoice_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    amount_paid = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    credit = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    arrears = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    remaining_balance = models.DecimalField(max_digits=12, decimal_places=2, default=0)

    # ✅ Selcom references
    mobile_number = models.CharField(max_length=20, blank=True, null=True)
    company_number = models.CharField(max_length=20, blank=True, null=True)
    reference_vin = models.CharField(max_length=50, blank=True, null=True)

    bank_account = models.CharField(max_length=50, blank=True, null=True)
    agent_commission = models.DecimalField(max_digits=12, decimal_places=2, default=0)

    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="PARTIAL")
    timestamp = models.DateTimeField(auto_now_add=True)

    def save(self, *args, **kwargs):
        is_new = self.pk is None

        # ✅ Branch logic: Sale vs Invoice
        if self.sale:  # Cash/Installment
            base_amount = self.sale.total_amount
        elif self.invoice:  # Lease
            base_amount = self.invoice.amount_due
        else:
            base_amount = self.invoice_amount

        if not self.invoice_amount:
            self.invoice_amount = base_amount

        # ✅ Arrears / credit logic
        if self.amount_paid < self.invoice_amount:
            self.arrears = self.invoice_amount - self.amount_paid
            self.credit = 0
            self.status = "PARTIAL"
        elif self.amount_paid == self.invoice_amount:
            self.arrears = 0
            self.credit = 0
            self.status = "FULL"
        else:
            self.arrears = 0
            self.credit = self.amount_paid - self.invoice_amount
            self.status = "SETTLED"

        # ✅ Update customer balance
        self.remaining_balance = max(self.customer.balance_remaining - self.amount_paid, 0)

        # ✅ Agent commission
        if self.agent and self.customer.agent_commission_percent > 0:
            self.agent_commission = (self.amount_paid * self.customer.agent_commission_percent) / 100

        super().save(*args, **kwargs)

        # ✅ Branch: Lease vs Sale
        if self.invoice:
            self._allocate_payment_to_invoices()
            self._handle_recovery_logic()
        elif self.sale:
            self.sale.update_balance(self.amount_paid)

        # ✅ Trigger Celery notification task only when payment is newly created
        if is_new:
            task_notify_payment_processed.delay(self.id)
            PaymentLog.objects.create(
                invoice=self.invoice,
                transaction_id=self.transaction_id,
                selcom_transaction_id=self.selcom_transaction_id,
                status=self.status,
                customer_id=self.customer.customer_id,
                customer_name=self.customer.full_name,
                motorcycle_vin=self.motorcycle.vin if self.motorcycle else None,
                amount=self.amount_paid
            )

    def _allocate_payment_to_invoices(self):
        """Lease customers: allocate payment across invoices."""
        remaining_amount = Decimal(self.amount_paid)
        invoices = self.customer.invoices.filter(
            motorcycle=self.motorcycle,
            status__in=["PENDING", "PARTIAL", "OVERDUE", "DEFAULTED"]
        ).order_by("due_date")

        for inv in invoices:
            if remaining_amount <= 0:
                break
            total_paid = sum(p.amount_paid for p in inv.payments.all())
            outstanding = inv.amount_due - total_paid
            if outstanding <= 0:
                continue
            if remaining_amount >= outstanding:
                inv.status = "PAID"
                remaining_amount -= outstanding
            else:
                inv.status = "PARTIAL"
                remaining_amount = 0
            inv.save(update_fields=["status"])

        if remaining_amount > 0:
            self.customer.credit_balance = getattr(self.customer, "credit_balance", Decimal(0)) + remaining_amount
            self.customer.save(update_fields=["credit_balance"])

    def _handle_recovery_logic(self):
        """Lease recovery logic for repossessed motorcycles."""
        if self.invoice and self.invoice.status == "PAID" and self.motorcycle:
            if self.motorcycle.status == "RETAINED":
                self.motorcycle.status = "ACTIVE"
                self.motorcycle.save(update_fields=["status"])
                self.customer.repossession_flag = False
                self.customer.save(update_fields=["repossession_flag"])
                if hasattr(self.motorcycle, "history"):
                    self.motorcycle.history.create(
                        action="UPDATED",
                        notes="Arrears cleared, motorcycle restored to ACTIVE"
                    )

    def __str__(self):
        return f"Payment {self.transaction_id} - {self.customer.customer_id} ({self.amount_paid})"


class PaymentLog(models.Model):
    invoice = models.ForeignKey("invoices.Invoice", on_delete=models.CASCADE, null=True, blank=True, related_name="payment_logs")

    # --- ERP internal transaction ID ---
    transaction_id = models.CharField(max_length=100, blank=True, null=True)

    # --- Selcom transaction ID for audit trail ---
    selcom_transaction_id = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        help_text="Unique transaction ID returned by Selcom API"
    )

    status = models.CharField(
        max_length=20,
        choices=[
            ("SUCCESS", "Success"),
            ("FAILED", "Failed"),
            ("REGENERATED", "Re-generated"),
            ("DUPLICATE", "Duplicate"),
            ("FULL", "Full Paid"),
            ("PARTIAL", "Partial Paid"),
        ]
    )
    reason = models.TextField(blank=True, null=True)

    # ✅ Keep both ID and name
    customer_id = models.CharField(max_length=30, blank=True, null=True)
    customer_name = models.CharField(max_length=255, blank=True, null=True)

    motorcycle_vin = models.CharField(max_length=100, blank=True, null=True)
    amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)

    # ✅ New fields for Selcom audit
    company_number = models.CharField(max_length=50, blank=True, null=True)
    mobile_number = models.CharField(max_length=20, blank=True, null=True)
    raw_payload = models.TextField(blank=True, null=True)

    created_on = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return (
            f"PaymentLog {self.transaction_id or 'N/A'} / "
            f"{self.selcom_transaction_id or 'N/A'} - {self.status} "
            f"({self.customer_id or 'N/A'} - {self.customer_name or 'N/A'})"
        )

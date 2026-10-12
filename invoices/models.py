import uuid
from datetime import timedelta
from django.db import models
from motorcycles.models import Motorcycle
from agents.models import Agent
from notifications.tasks import task_notify_invoice_generated


class Invoice(models.Model):
    STATUS_CHOICES = [
        ('PENDING', 'Pending'),
        ('PARTIAL', 'Partial'),
        ('PAID', 'Paid'),
        ('OVERDUE', 'Overdue'),
        ('DEFAULTED', 'Defaulted'),
        ('FAILED', 'Failed'),
    ]

    SCENARIO_CHOICES = [
        ('CASH', 'Cash'),
        ('INSTALLMENT', 'Installment'),
        ('LEASE', 'Lease'),
    ]

    customer = models.ForeignKey(
        "customers.Customer",
        on_delete=models.CASCADE,
        related_name="invoices",
        to_field="customer_id"
    )
    motorcycle = models.ForeignKey(Motorcycle, on_delete=models.SET_NULL, null=True, blank=True, related_name="invoices")
    agent = models.ForeignKey(Agent, on_delete=models.SET_NULL, null=True, blank=True, related_name="invoices")

    invoice_id = models.CharField(max_length=100, unique=True, editable=False)

    amount_due = models.DecimalField(max_digits=12, decimal_places=2)
    agent_commission = models.DecimalField(max_digits=12, decimal_places=2, default=0)

    due_date = models.DateField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PENDING')

    scenario_type = models.CharField(max_length=20, choices=SCENARIO_CHOICES, default='CASH')
    parent_invoice = models.ForeignKey(
        "self",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="child_invoices"
    )

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["customer", "due_date", "scenario_type"],
                name="unique_customer_due_date_scenario"
            )
        ]

    def save(self, *args, **kwargs):
        is_new = self.pk is None

        try:
            if not self.invoice_id:
                base = f"{self.customer.customer_id}"
                if self.motorcycle and hasattr(self.motorcycle, "vin"):
                    base += f"-{self.motorcycle.vin}"
                self.invoice_id = f"{base}-{uuid.uuid4().hex[:6].upper()}"

            if self.agent and hasattr(self.customer, "agent_commission_percent") and self.customer.agent_commission_percent > 0:
                self.agent_commission = (self.amount_due * self.customer.agent_commission_percent) / 100

            # First save to populate created_at
            super().save(*args, **kwargs)

            if is_new:
                # ✅ Now created_at is available, calculate due_date
                if self.scenario_type == "CASH":
                    self.due_date = self.created_at.date()
                elif self.scenario_type == "INSTALLMENT":
                    interval_days = getattr(self.customer.installment_plan, "interval_days", 7)
                    self.due_date = (self.created_at + timedelta(days=interval_days)).date()
                elif self.scenario_type == "LEASE":
                    interval_days = getattr(self.customer.lease_plan, "interval_days", 7)  # weekly lease = 7 days
                    self.due_date = (self.created_at + timedelta(days=interval_days)).date()

                # Save again to update due_date
                super().save(update_fields=["due_date"])

                task_notify_invoice_generated.delay(self.id)
                InvoiceLog.objects.create(
                    invoice=self,
                    status="SUCCESS",
                    customer_id=self.customer.customer_id,
                    customer_name=self.customer.full_name,
                    motorcycle_vin=self.motorcycle.vin if self.motorcycle else None,
                    amount=self.amount_due
                )

        except Exception as e:
            self.status = "FAILED"
            super().save(*args, **kwargs)
            InvoiceLog.objects.create(
                invoice=self,
                status="FAILED",
                reason=str(e),
                customer_id=self.customer.customer_id if self.customer else None,
                customer_name=self.customer.full_name if self.customer else None,
                motorcycle_vin=self.motorcycle.vin if self.motorcycle else None,
                amount=self.amount_due
            )

    def __str__(self):
        return f"Invoice {self.invoice_id} - {self.customer.customer_id} ({self.status})"

    @property
    def total_paid(self):
        return sum(p.amount_paid for p in self.payments.all())

    @property
    def balance_remaining(self):
        return self.amount_due - self.total_paid if self.amount_due else 0

    @property
    def last_payment_date(self):
        last_payment = self.payments.order_by("-timestamp").first()
        return last_payment.timestamp if last_payment else None


class InvoiceLog(models.Model):
    invoice = models.ForeignKey("Invoice", on_delete=models.CASCADE, null=True, blank=True)
    status = models.CharField(
        max_length=20,
        choices=[
            ("SUCCESS", "Success"),
            ("FAILED", "Failed"),
            ("REGENERATED", "Re-generated"),
        ]
    )
    reason = models.TextField(blank=True, null=True)

    customer_id = models.CharField(max_length=30, blank=True, null=True)
    customer_name = models.CharField(max_length=255, blank=True, null=True)

    motorcycle_vin = models.CharField(max_length=100, blank=True, null=True)
    amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    created_on = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"InvoiceLog {self.id} - {self.status} ({self.customer_id} - {self.customer_name})"

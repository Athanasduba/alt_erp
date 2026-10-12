from django.db import models
from customers.models import Customer
from motorcycles.models import Motorcycle
from agents.models import Agent
from users.models import User
from warehouses.models import Warehouse

class Sale(models.Model):
    PAYMENT_TYPE_CHOICES = [
        ('CASH', 'Cash'),
        ('INSTALLMENT', 'Installment'),
    ]

    customer = models.ForeignKey(Customer, on_delete=models.CASCADE, related_name="sales")
    motorcycle = models.ForeignKey(Motorcycle, on_delete=models.CASCADE, related_name="sales")
    agent = models.ForeignKey(Agent, on_delete=models.SET_NULL, null=True, blank=True, related_name="sales")
    officer_in_charge = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        limit_choices_to={'role': 'OFFICER'},
        related_name="sales"
    )
    warehouse = models.ForeignKey(Warehouse, on_delete=models.SET_NULL, null=True, blank=True, related_name="sales")

    payment_type = models.CharField(max_length=20, choices=PAYMENT_TYPE_CHOICES)
    total_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    installments = models.PositiveIntegerField(default=1)
    installment_amount = models.DecimalField(max_digits=12, decimal_places=2, blank=True, null=True)

    initial_deposit = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    amount_paid = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    balance_remaining = models.DecimalField(max_digits=12, decimal_places=2, default=0)

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Sale {self.id} - {self.customer.account_number} ({self.payment_type})"

    def update_balance(self, payment_amount):
        """Update sale balance when a payment is recorded."""
        self.amount_paid += payment_amount
        self.balance_remaining = max(self.total_amount - self.amount_paid, 0)
        self.save(update_fields=["amount_paid", "balance_remaining"])

    def save(self, *args, **kwargs):
        # Auto-calculate installment amount if applicable
        if self.payment_type == "INSTALLMENT" and self.installments > 1 and self.total_amount:
            net_amount = self.total_amount - self.initial_deposit
            self.installment_amount = net_amount / self.installments
        super().save(*args, **kwargs)


class SalePayment(models.Model):
    METHOD_CHOICES = [
        ('CASH', 'Cash'),
        ('BANK', 'Bank'),
        ('SELCOM', 'Selcom'),
    ]

    sale = models.ForeignKey(Sale, on_delete=models.CASCADE, related_name="sale_payments")
    amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    method = models.CharField(max_length=20, choices=METHOD_CHOICES)
    reference = models.CharField(max_length=100, blank=True, null=True)
    agent_commission = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Payment {self.id} for Sale {self.sale.id}"

    def save(self, *args, **kwargs):
        # ✅ Auto-calculate agent commission if agent exists and has commission_rate
        if self.sale.agent and hasattr(self.sale.agent, "commission_rate"):
            self.agent_commission = self.amount * (self.sale.agent.commission_rate / 100)
        super().save(*args, **kwargs)

        # ✅ Update Sale balance after saving payment
        self.sale.update_balance(self.amount)

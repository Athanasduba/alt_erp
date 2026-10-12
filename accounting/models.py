from django.db import models
from customers.models import Customer
from motorcycles.models import Motorcycle
from invoices.models import Invoice
from agents.models import Agent   # ✅ new import for agent commission tracking


class LedgerEntry(models.Model):
    ENTRY_TYPE_CHOICES = [
        ('CREDIT', 'Credit'),
        ('DEBIT', 'Debit'),
    ]

    customer = models.ForeignKey(Customer, on_delete=models.SET_NULL, null=True, blank=True, related_name="ledger_entries")
    motorcycle = models.ForeignKey(Motorcycle, on_delete=models.SET_NULL, null=True, blank=True, related_name="ledger_entries")
    invoice = models.ForeignKey(Invoice, on_delete=models.SET_NULL, null=True, blank=True, related_name="ledger_entries")

    entry_type = models.CharField(max_length=10, choices=ENTRY_TYPE_CHOICES)
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    description = models.TextField(blank=True, null=True)

    # ✅ NEW: payment source logging
    transaction_id = models.CharField(max_length=100, blank=True, null=True)
    mobile_number = models.CharField(max_length=20, blank=True, null=True)
    bank_account = models.CharField(max_length=50, blank=True, null=True)

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.entry_type} - {self.amount} ({self.created_at})"


class CustomerAccount(models.Model):
    """
    Tracks credits and arrears per customer per motorcycle.
    """
    customer = models.ForeignKey(Customer, on_delete=models.CASCADE, related_name="accounts")
    motorcycle = models.ForeignKey(Motorcycle, on_delete=models.CASCADE, related_name="accounts")
    credit_balance = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    arrears_balance = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    updated_at = models.DateTimeField(auto_now=True)

    def apply_payment(self, invoice, amount, transaction_id=None, mobile_number=None, bank_account=None):
        """
        Apply payment logic:
        - If overpayment → store credit.
        - If underpayment → store arrears.
        - If exact → mark invoice as PAID.
        """
        if amount > invoice.amount_due:
            invoice.status = 'PAID'
            self.credit_balance += (amount - invoice.amount_due)
            LedgerEntry.objects.create(
                customer=self.customer,
                motorcycle=self.motorcycle,
                invoice=invoice,
                entry_type='CREDIT',
                amount=amount,
                description="Overpayment credited to account",
                transaction_id=transaction_id,
                mobile_number=mobile_number,
                bank_account=bank_account
            )
        elif amount < invoice.amount_due:
            invoice.status = 'PARTIAL'
            self.arrears_balance += (invoice.amount_due - amount)
            LedgerEntry.objects.create(
                customer=self.customer,
                motorcycle=self.motorcycle,
                invoice=invoice,
                entry_type='DEBIT',
                amount=amount,
                description="Partial payment, arrears recorded",
                transaction_id=transaction_id,
                mobile_number=mobile_number,
                bank_account=bank_account
            )
        else:
            invoice.status = 'PAID'
            LedgerEntry.objects.create(
                customer=self.customer,
                motorcycle=self.motorcycle,
                invoice=invoice,
                entry_type='CREDIT',
                amount=amount,
                description="Invoice fully paid",
                transaction_id=transaction_id,
                mobile_number=mobile_number,
                bank_account=bank_account
            )

        invoice.save()
        self.save()

    def apply_credit_to_invoice(self, invoice):
        if self.credit_balance > 0:
            if self.credit_balance >= invoice.amount_due:
                self.credit_balance -= invoice.amount_due
                invoice.amount_due = 0
                invoice.status = 'PAID'
            else:
                invoice.amount_due -= self.credit_balance
                self.credit_balance = 0
                invoice.status = 'PARTIAL'
            invoice.save()
            self.save()

    def apply_arrears_to_invoice(self, invoice):
        if self.arrears_balance > 0:
            invoice.amount_due += self.arrears_balance
            self.arrears_balance = 0
            invoice.save()
            self.save()


# ✅ NEW: Agent commission tracking
class AgentAccount(models.Model):
    agent = models.ForeignKey(Agent, on_delete=models.CASCADE, related_name="accounts")
    accrued_commission = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    updated_at = models.DateTimeField(auto_now=True)

    def accrue_commission(self, invoice, amount):
        """Accrue commission when invoice is paid."""
        self.accrued_commission += amount
        self.save()

    def payout(self):
        """Reset commission after payout."""
        CommissionPayout.objects.create(agent=self.agent, amount=self.accrued_commission)
        self.accrued_commission = 0
        self.save()


class CommissionPayout(models.Model):
    agent = models.ForeignKey(Agent, on_delete=models.CASCADE, related_name="payouts")
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    paid_on = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Payout {self.amount} to {self.agent.full_name} on {self.paid_on}"

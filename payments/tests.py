import uuid
from django.test import TestCase
from datetime import date
from customers.models import Customer
from motorcycles.models import Motorcycle
from agents.models import Agent
from invoices.models import Invoice
from payments.models import Payment


class PaymentLogicTests(TestCase):
    """Tests for arrears, credits, commission, and recovery logic."""

    def setUp(self):
        self.motorcycle = Motorcycle.objects.create(vin="VIN-PAY-001", status="AVAILABLE")
        self.agent = Agent.objects.create(name="Commission Agent")

        self.customer = Customer.objects.create(
            full_name="Payment Test Customer",
            payment_model="CASH",
            approval_status="APPROVED",
            motorcycle=self.motorcycle,
            agent=self.agent,
            agent_commission_percent=10,
            opening_balance=1000,
            customer_id=f"CUST-{uuid.uuid4().hex[:6]}",
            account_number=f"ACC-{uuid.uuid4().hex[:6]}",
            national_id=f"NID-{uuid.uuid4().hex[:6]}"
        )

        self.invoice = Invoice.objects.create(
            customer=self.customer,
            motorcycle=self.motorcycle,
            agent=self.agent,
            amount_due=1000,
            due_date=date.today(),
            status="PENDING"
        )

    def test_partial_payment_creates_arrears(self):
        Payment.objects.create(invoice=self.invoice, customer=self.customer,
                               motorcycle=self.motorcycle, agent=self.agent,
                               amount_paid=400)
        self.invoice.refresh_from_db()
        self.assertEqual(self.invoice.status, "PARTIAL")

    def test_full_payment_clears_invoice(self):
        Payment.objects.create(invoice=self.invoice, customer=self.customer,
                               motorcycle=self.motorcycle, agent=self.agent,
                               amount_paid=1000)
        self.invoice.refresh_from_db()
        self.assertEqual(self.invoice.status, "PAID")

    def test_overpayment_creates_credit(self):
        Payment.objects.create(invoice=self.invoice, customer=self.customer,
                               motorcycle=self.motorcycle, agent=self.agent,
                               amount_paid=1200)
        self.invoice.refresh_from_db()
        self.assertEqual(self.invoice.status, "PAID")
        payment = self.invoice.payments.first()
        self.assertTrue(payment.credit > 0)

    def test_agent_commission_calculated_on_payment(self):
        Payment.objects.create(invoice=self.invoice, customer=self.customer,
                               motorcycle=self.motorcycle, agent=self.agent,
                               amount_paid=1000)
        self.invoice.refresh_from_db()
        expected_commission = (self.invoice.amount_due * self.customer.agent_commission_percent) / 100
        self.assertEqual(self.invoice.agent_commission, expected_commission)

    def test_recovery_restores_motorcycle(self):
        # Simulate repossession
        self.motorcycle.status = "RETAINED"
        self.motorcycle.save()

        Payment.objects.create(invoice=self.invoice, customer=self.customer,
                               motorcycle=self.motorcycle, agent=self.agent,
                               amount_paid=self.invoice.amount_due)

        self.invoice.refresh_from_db()
        self.motorcycle.refresh_from_db()
        self.customer.refresh_from_db()

        self.assertEqual(self.invoice.status, "PAID")
        self.assertEqual(self.motorcycle.status, "ACTIVE")
        self.assertFalse(self.customer.repossession_flag)
        if hasattr(self.motorcycle, "history"):
            history_entry = self.motorcycle.history.first()
            self.assertIn("Arrears cleared", history_entry.notes)

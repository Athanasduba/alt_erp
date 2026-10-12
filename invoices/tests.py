import uuid
from django.test import TestCase
from datetime import date, timedelta
from customers.models import Customer, InstallmentPlan, LeasePlan
from motorcycles.models import Motorcycle
from agents.models import Agent
from invoices.models import Invoice
from payments.models import Payment
from invoices.tasks import check_overdue_invoices


# -----------------------------
# UNIT TESTS (Signals only)
# -----------------------------
class InvoiceSignalUnitTests(TestCase):
    """Unit tests: signals only, expect first invoice for lease."""

    def setUp(self):
        self.motorcycle = Motorcycle.objects.create(vin="VIN123", status="AVAILABLE")
        self.agent = Agent.objects.create(name="Test Agent")

    def _unique_fields(self):
        return {
            "customer_id": f"CUST-{uuid.uuid4().hex[:6]}",
            "account_number": f"ACC-{uuid.uuid4().hex[:6]}",
            "national_id": f"NID-{uuid.uuid4().hex[:6]}"
        }

    def test_cash_customer_invoice_created(self):
        customer = Customer.objects.create(
            full_name="Cash Customer",
            payment_model="CASH",
            approval_status="APPROVED",
            motorcycle=self.motorcycle,
            agent=self.agent,
            agent_commission_percent=10,
            opening_balance=1000,
            **self._unique_fields()
        )
        invoices = Invoice.objects.filter(customer=customer)
        self.assertEqual(invoices.count(), 1)
        invoice = invoices.first()
        self.assertEqual(invoice.amount_due, 1000)
        self.assertEqual(invoice.agent_commission, 100)

    def test_installment_customer_invoices_created(self):
        customer = Customer.objects.create(
            full_name="Installment Customer",
            payment_model="INSTALLMENT",
            approval_status="APPROVED",
            motorcycle=self.motorcycle,
            agent=self.agent,
            agent_commission_percent=5,
            **self._unique_fields()
        )
        plan = InstallmentPlan.objects.create(
            customer=customer,
            total_amount=1200,
            initial_deposit=200,
            number_of_installments=5,
            start_date=date.today()
        )
        customer.save()

        invoices = Invoice.objects.filter(customer=customer)
        self.assertEqual(invoices.count(), 5)

    def test_lease_customer_first_invoice_created(self):
        customer = Customer.objects.create(
            full_name="Lease Customer",
            payment_model="LEASE",
            approval_status="APPROVED",
            motorcycle=self.motorcycle,
            agent=self.agent,
            agent_commission_percent=8,
            **self._unique_fields()
        )
        plan = LeasePlan.objects.create(
            customer=customer,
            total_amount=800,
            weekly_lease_amount=100,
            start_date=date.today()
        )
        customer.save()

        invoices = Invoice.objects.filter(customer=customer)
        self.assertEqual(invoices.count(), 1)
        invoice = invoices.first()
        self.assertEqual(invoice.amount_due, 100)
        self.assertEqual(invoice.due_date, plan.start_date)


# -----------------------------
# INTEGRATION TESTS
# -----------------------------
class InvoiceIntegrationTests(TestCase):
    def setUp(self):
        self.motorcycle = Motorcycle.objects.create(vin="VIN999", status="AVAILABLE")
        self.agent = Agent.objects.create(name="Agent X")
        self.customer = Customer.objects.create(
            full_name="Payment Customer",
            payment_model="CASH",
            approval_status="APPROVED",
            motorcycle=self.motorcycle,
            agent=self.agent,
            agent_commission_percent=10,
            opening_balance=500,
            customer_id=f"CUST-{uuid.uuid4().hex[:6]}",
            account_number=f"ACC-{uuid.uuid4().hex[:6]}",
            national_id=f"NID-{uuid.uuid4().hex[:6]}"
        )
        self.invoice = Invoice.objects.filter(customer=self.customer).first()

    def test_partial_payment_updates_status(self):
        Payment.objects.create(invoice=self.invoice, customer=self.customer,
                               motorcycle=self.motorcycle, agent=self.agent,
                               amount_paid=200)
        self.invoice.refresh_from_db()
        self.assertEqual(self.invoice.status, "PARTIAL")

    def test_full_payment_updates_status(self):
        Payment.objects.create(invoice=self.invoice, customer=self.customer,
                               motorcycle=self.motorcycle, agent=self.agent,
                               amount_paid=500)
        self.invoice.refresh_from_db()
        self.assertEqual(self.invoice.status, "PAID")

    def test_multiple_payments_accumulate(self):
        Payment.objects.create(invoice=self.invoice, customer=self.customer,
                               motorcycle=self.motorcycle, agent=self.agent,
                               amount_paid=200)
        Payment.objects.create(invoice=self.invoice, customer=self.customer,
                               motorcycle=self.motorcycle, agent=self.agent,
                               amount_paid=300)
        self.invoice.refresh_from_db()
        self.assertEqual(self.invoice.status, "PAID")

    def test_lease_customer_integration_invoices(self):
        customer = Customer.objects.create(
            full_name="Lease Customer Integration",
            payment_model="LEASE",
            approval_status="APPROVED",
            motorcycle=self.motorcycle,
            agent=self.agent,
            agent_commission_percent=8,
            customer_id=f"CUST-{uuid.uuid4().hex[:6]}",
            account_number=f"ACC-{uuid.uuid4().hex[:6]}",
            national_id=f"NID-{uuid.uuid4().hex[:6]}"
        )
        plan = LeasePlan.objects.create(
            customer=customer,
            total_amount=800,
            weekly_lease_amount=100,
            start_date=date.today()
        )
        customer.save()

        invoices = Invoice.objects.filter(customer=customer)
        self.assertGreaterEqual(invoices.count(), 1)


# -----------------------------
# OVERDUE / DEFAULT TESTS
# -----------------------------
class OverdueDefaultTests(TestCase):
    def setUp(self):
        self.motorcycle = Motorcycle.objects.create(vin="VIN777", status="AVAILABLE")
        self.agent = Agent.objects.create(name="Agent Y")
        self.customer = Customer.objects.create(
            full_name="Overdue Customer",
            payment_model="LEASE",
            approval_status="APPROVED",
            motorcycle=self.motorcycle,
            agent=self.agent,
            agent_commission_percent=5,
            opening_balance=500,
            customer_id=f"CUST-{uuid.uuid4().hex[:6]}",
            account_number=f"ACC-{uuid.uuid4().hex[:6]}",
            national_id=f"NID-{uuid.uuid4().hex[:6]}"
        )
        self.plan = LeasePlan.objects.create(
            customer=self.customer,
            total_amount=500,
            weekly_lease_amount=100,
            start_date=date.today() - timedelta(weeks=3)
        )
        self.customer.save()

        for i in range(3):
            Invoice.objects.create(
                customer=self.customer,
                motorcycle=self.motorcycle,
                agent=self.agent,
                amount_due=100,
                due_date=date.today() - timedelta(weeks=i+1),
                status="PENDING"
            )

    def test_overdue_invoices_trigger_default_and_retention(self):
        check_overdue_invoices()
        invoices = Invoice.objects.filter(customer=self.customer).order_by("due_date")
        self.motorcycle.refresh_from_db()
        self.assertEqual(invoices[0].status, "OVERDUE")
        self.assertEqual(invoices[1].status, "DEFAULTED")
        self.assertEqual(self.motorcycle.status, "RETAINED")

    def test_recovery_after_payment_restores_motorcycle(self):
        check_overdue_invoices()
        self.motorcycle.refresh_from_db()
        self.assertEqual(self.motorcycle.status, "RETAINED")

        invoice = self.customer.invoices.first()
        Payment.objects.create(invoice=invoice, customer=self.customer,
                               motorcycle=self.motorcycle, agent=self.agent,
                               amount_paid=invoice.amount_due)

        invoice.refresh_from_db()
        self.assertEqual(invoice.status, "PAID")

        # ✅ Re-fetch motorcycle after payment
        self.motorcycle.refresh_from_db()
        self.assertEqual(self.motorcycle.status, "ACTIVE")

        self.customer.refresh_from_db()
        self.assertFalse(self.customer.repossession_flag)

        history_entry = self.motorcycle.history.first()
        self.assertEqual(history_entry.action, "UPDATED")
        self.assertIn("Arrears cleared", history_entry.notes)

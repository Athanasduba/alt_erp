from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import timedelta
from customers.models import Customer, InstallmentPlan, LeasePlan
from invoices.models import Invoice

class Command(BaseCommand):
    help = "Test customer signals for CASH, INSTALLMENT, and LEASE flows"

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS("🚀 Starting signal tests..."))

        # --- CASH CUSTOMER ---
        cash_customer = Customer.objects.create(
            full_name="Cash Test",
            mobile_number="0712345678",
            nearest_warehouse_id=4,   # adjust IDs to valid records
            motorcycle_id=1,
            agent_id=None,
            agent_commission_percent=0,
            payment_model="CASH",
            cash_amount=500000,
            officer_in_charge_id=1,
            approval_status="APPROVED"
        )

        self.stdout.write("Cash Customer Balances:")
        self.stdout.write(f"Opening Balance: {cash_customer.opening_balance}")
        self.stdout.write(f"Balance Remaining: {cash_customer.balance_remaining}")
        self.stdout.write(f"Credit Amount: {cash_customer.credit_amount}")
        self.stdout.write(f"Is Settled: {cash_customer.is_settled}")
        self.stdout.write(f"Invoices: {list(Invoice.objects.filter(customer=cash_customer).values_list('amount_due','status'))}")

        # --- INSTALLMENT CUSTOMER ---
        install_customer = Customer.objects.create(
            full_name="Installment Test",
            mobile_number="0712345679",
            nearest_warehouse_id=3,
            motorcycle_id=1,
            agent_id=1,
            agent_commission_percent=10,
            payment_model="INSTALLMENT",
            officer_in_charge_id=1,
            approval_status="PENDING"
        )

        # ✅ Provide manual payment_schedule
        start_date = timezone.now().date()
        payment_schedule = [
            {"due_date": str(start_date), "amount": 200000, "label": "Initial Deposit"},
        ]
        for i in range(5):
            due_date = start_date + timedelta(weeks=(i+1)*4)
            payment_schedule.append({
                "due_date": str(due_date),
                "amount": 200000,
                "label": f"Installment {i+1}"
            })

        plan = InstallmentPlan.objects.create(
            customer=install_customer,
            total_amount=1200000,
            initial_deposit=200000,
            number_of_installments=5,
            start_date=start_date,
            payment_schedule=payment_schedule
        )

        install_customer.approval_status = "APPROVED"
        install_customer.save()

        self.stdout.write("Installment Customer Balances:")
        self.stdout.write(f"Opening Balance: {install_customer.opening_balance}")
        self.stdout.write(f"Balance Remaining: {install_customer.balance_remaining}")
        self.stdout.write(f"Credit Amount: {install_customer.credit_amount}")
        self.stdout.write(f"Is Settled: {install_customer.is_settled}")
        self.stdout.write(f"Invoices: {list(Invoice.objects.filter(customer=install_customer).values_list('amount_due','status'))}")

        # --- LEASE CUSTOMER ---
        lease_customer = Customer.objects.create(
            full_name="Lease Test",
            mobile_number="0712345680",
            nearest_warehouse_id=3,
            motorcycle_id=1,
            agent_id=1,
            agent_commission_percent=10,
            payment_model="LEASE",
            officer_in_charge_id=1,
            approval_status="PENDING"
        )

        lease_plan = LeasePlan.objects.create(
            customer=lease_customer,
            total_amount=800000,
            weekly_lease_amount=50000,
            start_date=timezone.now().date()
        )

        lease_customer.approval_status = "APPROVED"
        lease_customer.save()

        self.stdout.write("Lease Customer Balances:")
        self.stdout.write(f"Opening Balance: {lease_customer.opening_balance}")
        self.stdout.write(f"Balance Remaining: {lease_customer.balance_remaining}")
        self.stdout.write(f"Credit Amount: {lease_customer.credit_amount}")
        self.stdout.write(f"Is Settled: {lease_customer.is_settled}")
        self.stdout.write(f"Invoices: {list(Invoice.objects.filter(customer=lease_customer).values_list('amount_due','status'))}")

        self.stdout.write(self.style.SUCCESS("✅ Signal tests completed."))

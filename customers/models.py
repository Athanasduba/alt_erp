from django.db import models
from django.utils.timezone import now
from django.core.validators import RegexValidator, MaxLengthValidator
from warehouses.models import Warehouse
from agents.models import Agent
from users.models import User
from dateutil.relativedelta import relativedelta   # ✅ use relativedelta for calendar accuracy


class Customer(models.Model):
    PAYMENT_MODEL_CHOICES = [
        ('CASH', 'Cash'),
        ('INSTALLMENT', 'Installment'),
        ('LEASE', 'Lease'),
    ]

    APPROVAL_STATUS_CHOICES = [
        ('PENDING', 'Pending'),
        ('APPROVED', 'Approved'),
        ('REJECTED', 'Rejected'),
    ]

    ONBOARDING_TYPES = [
        ('DIRECT', 'Direct'),
        ('AGENT', 'Via Agent'),
    ]

    phone_validator = RegexValidator(
        regex=r'^\+?\d{7,30}$',
        message="Enter a valid phone number (digits only, optional +, max 30 chars)."
    )

    # Onboarding details
    onboarding_type = models.CharField(max_length=10, choices=ONBOARDING_TYPES, default='DIRECT')
    customer_id = models.CharField(max_length=50, unique=True, blank=True)
    account_number = models.CharField(max_length=50, unique=True, blank=True)
    full_name = models.CharField(max_length=150, default="Unknown")

    mobile_number = models.CharField(
        max_length=30,
        default="",
        validators=[phone_validator, MaxLengthValidator(30)]
    )
    cash_amount = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    settled_flag = models.BooleanField(default=False) # For Payment Completion status check

    # Relations
    nearest_warehouse = models.ForeignKey(Warehouse, on_delete=models.SET_NULL, null=True, blank=True, related_name="customers")
    motorcycle = models.ForeignKey("motorcycles.Motorcycle", on_delete=models.SET_NULL, null=True, blank=True, related_name="customers")
    agent = models.ForeignKey(Agent, on_delete=models.SET_NULL, null=True, blank=True, related_name="customers")
    officer_in_charge = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        limit_choices_to={'role': 'OFFICER'},
        related_name="customers"
    )

    # Contract upload
    contract = models.FileField(upload_to="customers/contracts/", null=True, blank=True)

    # Guarantor 1
    guarantor1_name = models.CharField(max_length=150, default="Unknown")
    guarantor1_mobile = models.CharField(max_length=30, default="", validators=[phone_validator, MaxLengthValidator(15)])
    guarantor1_address = models.TextField(default="Unknown")
    guarantor1_national_id = models.CharField(max_length=50, default="")

    # Guarantor 2
    guarantor2_name = models.CharField(max_length=150, default="Unknown")
    guarantor2_mobile = models.CharField(max_length=30, default="", validators=[phone_validator, MaxLengthValidator(15)])
    guarantor2_address = models.TextField(default="Unknown")
    guarantor2_national_id = models.CharField(max_length=50, default="")

    # Payment model
    payment_model = models.CharField(max_length=30, choices=PAYMENT_MODEL_CHOICES)

    # Approval workflow
    approval_status = models.CharField(max_length=10, choices=APPROVAL_STATUS_CHOICES, default='PENDING')

    # Financial tracking
    opening_balance = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    balance_remaining = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    settled_flag = models.BooleanField(default=False, help_text="Raw flag for settlement status")

    # Credit & arrears
    credit_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    arrears_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)

    # Repossession
    missed_invoices_count = models.PositiveIntegerField(default=0)
    repossession_flag = models.BooleanField(default=False)

    # Agent commission %
    agent_commission_percent = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    per_initial_deposit_commission = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=0,
        help_text="Commission earned by agent from initial deposit"
    )

    # Audit fields
    created_at = models.DateTimeField(auto_now_add=True)
    last_financial_update = models.DateTimeField(null=True, blank=True)  # ✅ NEW FIELD

    def __str__(self):
        return f"{self.full_name} - {self.customer_id or 'NoID'} ({self.payment_model or 'NoPayment'}) [{self.approval_status}]"

    def save(self, *args, **kwargs):
        if not self.customer_id:
            last_id = Customer.objects.order_by("id").last()
            next_num = (last_id.id + 1) if last_id else 1
            self.customer_id = f"CUST{next_num:05d}"

        if not self.account_number:
            year = now().year
            warehouse_code = (
                self.nearest_warehouse.code
                if self.nearest_warehouse and hasattr(self.nearest_warehouse, "code")
                else "GEN"
            )
            self.account_number = f"ACC-{year}-{warehouse_code}-{self.customer_id}"

        super().save(*args, **kwargs)

    def calculate_commission(self, payment_amount, is_initial_deposit=False):
        if self.agent and self.agent_commission_percent > 0:
            commission = (payment_amount * self.agent_commission_percent) / 100
            if is_initial_deposit:
                self.per_initial_deposit_commission = commission
                self.save(update_fields=["per_initial_deposit_commission"])
            return commission
        return 0

    def apply_payment(self, amount, expected_invoice_amount=0):
        commission_amount = self.calculate_commission(amount)

        if amount >= self.balance_remaining:
            self.credit_amount += (amount - self.balance_remaining)
            self.balance_remaining = 0
            self.settled_flag = True
        else:
            self.balance_remaining -= amount
            if expected_invoice_amount and amount < expected_invoice_amount:
                self.arrears_amount += (expected_invoice_amount - amount)

        if amount > 0:
            self.missed_invoices_count = 0
            self.repossession_flag = False

        self.last_financial_update = now()
        self.save(update_fields=[
            'opening_balance', 'balance_remaining', 'credit_amount',
            'arrears_amount', 'settled_flag', 'missed_invoices_count',
            'repossession_flag', 'last_financial_update'
        ])

        if self.balance_remaining == 0 and self.is_settled and self.motorcycle:
            if self.payment_model == "INSTALLMENT":
                self.motorcycle.mark_completed(payment_model="INSTALLMENT")
            elif self.payment_model == "LEASE":
                self.motorcycle.mark_completed(payment_model="LEASE")

        return commission_amount

    @property
    def commission_preview(self):
        if self.payment_model == "CASH":
            base_amount = self.cash_amount or 0
            numeric = round(self.calculate_commission(base_amount), 2)
            return {"numeric": numeric, "formatted": f"{numeric:.2f} TZS (cash)"}

        elif self.payment_model == "INSTALLMENT" and hasattr(self, "installment_plan"):
            numeric = round(self.calculate_commission(self.installment_plan.installment_amount), 2)
            return {"numeric": numeric, "formatted": f"{numeric:.2f} TZS per installment"}

        elif self.payment_model == "LEASE" and hasattr(self, "lease_plan"):
            numeric = round(self.calculate_commission(self.lease_plan.weekly_lease_amount), 2)
            return {"numeric": numeric, "formatted": f"{numeric:.2f} TZS per week"}

        return {"numeric": None, "formatted": None}

    @property
    def is_settled(self):
        if self.payment_model == "CASH":
            return self.settled_flag

        elif self.payment_model == "INSTALLMENT" and hasattr(self, "installment_plan"):
            no_pending_invoices = not self.invoices.filter(status="PENDING").exists()
            arrears_cleared = (self.arrears_amount == 0)
            balance_cleared = (self.balance_remaining == 0)
            return no_pending_invoices and arrears_cleared and balance_cleared

        elif self.payment_model == "LEASE" and hasattr(self, "lease_plan"):
            no_pending_invoices = not self.invoices.filter(status="PENDING").exists()
            arrears_cleared = (self.arrears_amount == 0)
            balance_cleared = (self.balance_remaining == 0)
            return no_pending_invoices and arrears_cleared and balance_cleared

        return False


class InstallmentPlan(models.Model):
    customer = models.OneToOneField(
        Customer,
        on_delete=models.CASCADE,
        related_name="installment_plan",
        to_field="account_number"
    )
    total_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    initial_deposit = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    number_of_installments = models.PositiveIntegerField(default=1)
    installment_amount = models.DecimalField(max_digits=12, decimal_places=2, editable=False, default=0)

    # ✅ Payment schedule choices
    PAYMENT_SCHEDULE_CHOICES = [
        ("MONTHLY", "Monthly"),
        ("QUARTERLY", "Quarterly"),
        ("SEMI_ANNUAL", "Semi-Annual"),
        ("ANNUAL", "Annual"),
    ]
    payment_schedule = models.CharField(
        max_length=20,
        choices=PAYMENT_SCHEDULE_CHOICES,
        default="MONTHLY"
    )

    start_date = models.DateField()
    end_date = models.DateField(editable=False)

    def save(self, *args, **kwargs):
        if self.total_amount and self.number_of_installments:
            net_amount = self.total_amount - self.initial_deposit
            self.installment_amount = net_amount / self.number_of_installments

        if self.start_date and self.number_of_installments:
            # ✅ Use relativedelta for true calendar accuracy
            if self.payment_schedule == "MONTHLY":
                delta = relativedelta(months=self.number_of_installments)
            elif self.payment_schedule == "QUARTERLY":
                delta = relativedelta(months=3 * self.number_of_installments)
            elif self.payment_schedule == "SEMI_ANNUAL":
                delta = relativedelta(months=6 * self.number_of_installments)
            elif self.payment_schedule == "ANNUAL":
                delta = relativedelta(years=self.number_of_installments)
            else:
                delta = relativedelta(months=self.number_of_installments)

            self.end_date = self.start_date + delta

        super().save(*args, **kwargs)

    def get_schedule_delta(self, index: int):
        """
        Returns the relativedelta offset for the nth installment based on the payment schedule.
        index starts at 0 for the first installment.
        """
        if self.payment_schedule == "MONTHLY":
            return relativedelta(months=index + 1)
        elif self.payment_schedule == "QUARTERLY":
            return relativedelta(months=3 * (index + 1))
        elif self.payment_schedule == "SEMI_ANNUAL":
            return relativedelta(months=6 * (index + 1))
        elif self.payment_schedule == "ANNUAL":
            return relativedelta(years=index + 1)
        # fallback: monthly
        return relativedelta(months=index + 1)

    def __str__(self):
        return f"{self.customer.account_number} - {self.number_of_installments} installments"


class LeasePlan(models.Model):
    customer = models.OneToOneField(
        Customer,
        on_delete=models.CASCADE,
        related_name="lease_plan",
        to_field="account_number"
    )
    total_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    weekly_lease_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)

    lease_period_weeks = models.PositiveIntegerField(editable=False, default=0)

    start_date = models.DateField()
    end_date = models.DateField(editable=False)

    def save(self, *args, **kwargs):
        if self.total_amount and self.weekly_lease_amount:
            self.lease_period_weeks = int(self.total_amount / self.weekly_lease_amount)

        if self.start_date and self.lease_period_weeks:
            # ✅ Use relativedelta for weekly accuracy
            self.end_date = self.start_date + relativedelta(weeks=self.lease_period_weeks)

        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.customer.account_number} - {self.lease_period_weeks} weeks lease"

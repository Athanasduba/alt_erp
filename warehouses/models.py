from django.db import models
from django.conf import settings



class Warehouse(models.Model):
    WAREHOUSE_TYPES = (
        ('MAIN', 'Main Warehouse'),
        ('BRANCH', 'Branch Warehouse'),
        ('TEMP', 'Temporary Storage'),
    )

    name = models.CharField(max_length=150, unique=True)
    type = models.CharField(max_length=20, choices=WAREHOUSE_TYPES)
    physical_location = models.CharField(max_length=255)

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="warehouses_created"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    # ✅ Quantity tracking for all motorcycle statuses
    available_count = models.PositiveIntegerField(default=0)
    leased_count = models.PositiveIntegerField(default=0)

    # ✅ Separate counts for Sold
    sold_cash_count = models.PositiveIntegerField(default=0)
    sold_installment_count = models.PositiveIntegerField(default=0)

    retained_count = models.PositiveIntegerField(default=0)

    # ✅ Separate counts for Resold
    resold_cash_count = models.PositiveIntegerField(default=0)
    resold_installment_count = models.PositiveIntegerField(default=0)

    re_leased_count = models.PositiveIntegerField(default=0)
    lease_completed_count = models.PositiveIntegerField(default=0)
    installment_completed_count = models.PositiveIntegerField(default=0)

    class Meta:
        verbose_name = "Warehouse"
        verbose_name_plural = "Warehouses"

    def __str__(self):
        return f"{self.name} ({self.type})"

    # ✅ Helper to recalc counts dynamically
    def update_motorcycle_counts(self):
        # ✅ Import inside method to avoid circular import
        from motorcycles.models import Motorcycle

        self.available_count = Motorcycle.objects.filter(warehouse=self, status="AVAILABLE").count()
        self.leased_count = Motorcycle.objects.filter(warehouse=self, status="LEASED").count()

        # ✅ Sold
        self.sold_cash_count = Motorcycle.objects.filter(warehouse=self, status="SOLD_CASH").count()
        self.sold_installment_count = Motorcycle.objects.filter(warehouse=self, status="SOLD_INSTALLMENT").count()

        # ✅ Retained
        self.retained_count = Motorcycle.objects.filter(warehouse=self, status="RETAINED").count()

        # ✅ Resold
        self.resold_cash_count = Motorcycle.objects.filter(warehouse=self, status="RESOLD_CASH").count()
        self.resold_installment_count = Motorcycle.objects.filter(warehouse=self, status="RESOLD_INSTALLMENT").count()

        # ✅ Re-leased
        self.re_leased_count = Motorcycle.objects.filter(warehouse=self, status="RELEASED").count()

        # ✅ Completed
        self.lease_completed_count = Motorcycle.objects.filter(warehouse=self, status="LEASE_COMPLETED").count()
        self.installment_completed_count = Motorcycle.objects.filter(warehouse=self, status="INSTALLMENT_COMPLETED").count()

        self.save(update_fields=[
            "available_count", "leased_count",
            "sold_cash_count", "sold_installment_count",
            "retained_count",
            "resold_cash_count", "resold_installment_count",
            "re_leased_count", "lease_completed_count", "installment_completed_count"
        ])


class StockTransfer(models.Model):
    STATUS_CHOICES = (
        ('PENDING', 'Pending Approval'),
        ('APPROVED', 'Approved'),
        ('DENIED', 'Denied'),
        ('RETURNED', 'Returned for Correction'),
    )

    motorcycle = models.ForeignKey("motorcycles.Motorcycle", on_delete=models.CASCADE)
    from_warehouse = models.ForeignKey(Warehouse, on_delete=models.CASCADE, related_name="transfers_out")
    to_warehouse = models.ForeignKey(Warehouse, on_delete=models.CASCADE, related_name="transfers_in")
    initiated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="transfers_initiated"
    )  # Store role
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="transfers_approved"
    )  # Admin/Manager
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PENDING')
    reason = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def approve(self, approver):
        self.status = "APPROVED"
        self.approved_by = approver

        # ✅ Move motorcycle to new warehouse
        old_warehouse = self.motorcycle.warehouse
        self.motorcycle.warehouse = self.to_warehouse
        self.motorcycle.save()
        self.save()

        # ✅ Update counts for both warehouses
        if old_warehouse:
            old_warehouse.update_motorcycle_counts()
        if self.to_warehouse:
            self.to_warehouse.update_motorcycle_counts()

        TransferHistory.objects.create(
            transfer=self,
            action="APPROVED",
            performed_by=approver,
            notes="Approved transfer"
        )

    def deny(self, approver, reason, returned=False):
        self.approved_by = approver
        if returned:
            self.status = "RETURNED"
            action = "RETURNED"
        else:
            self.status = "DENIED"
            action = "DENIED"
        self.reason = reason
        self.save()
        TransferHistory.objects.create(
            transfer=self,
            action=action,
            performed_by=approver,
            notes=reason
        )

    def resubmit(self, user, new_to_warehouse=None):
        if new_to_warehouse:
            self.to_warehouse = new_to_warehouse
        self.status = "PENDING"
        self.save()
        TransferHistory.objects.create(
            transfer=self,
            action="RESUBMITTED",
            performed_by=user,
            notes="Resubmitted transfer"
        )

    def __str__(self):
        return f"Transfer {self.id}: {self.motorcycle.vin} {self.from_warehouse} → {self.to_warehouse} ({self.status})"


class TransferHistory(models.Model):
    ACTION_CHOICES = (
        ('INITIATED', 'Initiated'),
        ('APPROVED', 'Approved'),
        ('DENIED', 'Denied'),
        ('RETURNED', 'Returned for Correction'),
        ('RESUBMITTED', 'Resubmitted'),
    )

    transfer = models.ForeignKey(StockTransfer, on_delete=models.CASCADE, related_name="history")
    action = models.CharField(max_length=20, choices=ACTION_CHOICES)
    performed_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True)
    notes = models.TextField(blank=True, null=True)
    timestamp = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Transfer History"
        verbose_name_plural = "Transfer Histories"
        ordering = ["-timestamp"]

    def __str__(self):
        return f"{self.transfer} - {self.action} by {self.performed_by} at {self.timestamp}"


class RetainedMotorcycle(models.Model):
    STATUS_CHOICES = (
        ('PENDING', 'Pending Approval'),
        ('APPROVED', 'Approved'),
        ('DENIED', 'Denied'),
    )

    motorcycle = models.OneToOneField("motorcycles.Motorcycle", on_delete=models.CASCADE, related_name="retained_record")
    customer = models.ForeignKey("customers.Customer", on_delete=models.SET_NULL, null=True, blank=True, related_name="retained_motorcycles")
    warehouse = models.ForeignKey(Warehouse, on_delete=models.CASCADE, related_name="retained_motorcycles")
    officer_in_charge = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="retentions_initiated")
    approved_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="retentions_approved")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PENDING')
    reason = models.TextField(blank=True, null=True)
    repossession_date = models.DateTimeField(auto_now_add=True)

    def approve(self, approver):
        self.status = "APPROVED"
        self.approved_by = approver
        self.motorcycle.status = "RETAINED"
        self.motorcycle.warehouse = self.warehouse
        self.motorcycle.save()
        self.save()

        # ✅ Update warehouse counts
        if self.warehouse:
            self.warehouse.update_motorcycle_counts()

    def deny(self, approver, reason):
        self.status = "DENIED"
        self.approved_by = approver
        self.reason = reason
        self.save()

    def __str__(self):
        return f"Retained {self.motorcycle.vin} ({self.status})"

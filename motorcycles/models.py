from django.db import models
from django.conf import settings
from django.utils.timezone import now
from warehouses.models import Warehouse
from agents.models import Agent
import logging

logger = logging.getLogger(__name__)


class Motorcycle(models.Model):
    CATEGORY_CHOICES = [
        ('TWO_WHEELS', 'Two-Wheels'),
        ('THREE_WHEELS', 'Three-Wheels'),
    ]

    STATUS_CHOICES = [
        ('NEW', 'New'),
        ('AVAILABLE', 'Available'),
        ('ACTIVE', 'Active'),
        ('SOLD_CASH', 'Sold (Cash)'),
        ('SOLD_INSTALLMENT', 'Sold (Installment)'),
        ('LEASED', 'Leased'),
        ('RETAINED', 'Retained'),
        ('RESOLD_CASH', 'Resold (Cash)'),
        ('RESOLD_INSTALLMENT', 'Resold (Installment)'),
        ('RELEASED', 'Re-leased'),
        ('LEASE_COMPLETED', 'Lease Completed'),
        ('INSTALLMENT_COMPLETED', 'Installment Completed'),
        ('DELETED', 'Deleted'),
    ]

    vin = models.CharField(max_length=50, unique=True)
    frame_number = models.CharField(max_length=100, unique=True, default="TEMP_FRAME")
    engine_number = models.CharField(max_length=100, unique=True, default="TEMP_ENGINE")
    model = models.CharField(max_length=100, default="Unknown Model")
    brand = models.CharField(max_length=100, default="Unknown Brand")
    color = models.CharField(max_length=50, default="Unspecified")
    category = models.CharField(max_length=20, choices=CATEGORY_CHOICES, default="TWO_WHEELS")

    warehouse = models.ForeignKey(Warehouse, on_delete=models.SET_NULL, null=True, blank=True, related_name="motorcycles")
    agent = models.ForeignKey(Agent, on_delete=models.SET_NULL, null=True, blank=True, related_name="motorcycles")
    customer_account = models.ForeignKey("customers.Customer", on_delete=models.SET_NULL, null=True, blank=True, related_name="motorcycles")

    status = models.CharField(max_length=30, choices=STATUS_CHOICES, default='NEW')
    is_sold = models.BooleanField(default=False)

    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="motorcycles_created")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        if self.warehouse:
            self.warehouse.update_motorcycle_counts()
        if kwargs.get("force_insert", False):
            MotorcycleHistory.objects.create(
                motorcycle=self,
                action="CREATED",
                performed_by=self.created_by,
                notes=f"Motorcycle {self.vin} created"
            )

    # --- Lifecycle methods with guards ---
    def move_to_warehouse(self, warehouse, user):
        if self.status == "AVAILABLE" and self.warehouse == warehouse:
            return  # prevent duplicate
        self.warehouse = warehouse
        self.status = "AVAILABLE"
        self.is_sold = False
        self.updated_at = now()
        self.save(update_fields=["warehouse", "status", "is_sold", "updated_at"])
        MotorcycleHistory.objects.create(
            motorcycle=self,
            action="MOVED_TO_WAREHOUSE",
            performed_by=user,
            notes=f"Moved to {warehouse.name}"
        )

    def sell_to_customer(self, customer, user, payment_model="CASH", is_resale=False):
        if payment_model == "CASH":
            status = "RESOLD_CASH" if is_resale else "SOLD_CASH"
        elif payment_model == "INSTALLMENT":
            status = "RESOLD_INSTALLMENT" if is_resale else "SOLD_INSTALLMENT"
        else:
            status = "SOLD_CASH"

        if self.status == status and self.customer_account == customer:
            return  # prevent duplicate

        agent_value = customer.agent if getattr(customer, "onboarding_type", None) == "AGENT" else None
        self.customer_account = customer
        self.agent = agent_value
        self.status = status
        self.is_sold = True
        self.updated_at = now()
        self.save(update_fields=["customer_account", "agent", "status", "is_sold", "updated_at"])

        MotorcycleHistory.objects.create(
            motorcycle=self,
            action="RESOLD" if is_resale else "SOLD",
            performed_by=user,
            notes=f"{'Re-' if is_resale else ''}Sold ({payment_model}) to {customer.full_name}"
        )

    def lease_to_customer(self, customer, user, is_resale=False):
        status = "RELEASED" if is_resale else "LEASED"
        if self.status == status and self.customer_account == customer:
            return  # prevent duplicate

        agent_value = customer.agent if getattr(customer, "onboarding_type", None) == "AGENT" else None
        self.customer_account = customer
        self.agent = agent_value
        self.status = status
        self.is_sold = False
        self.updated_at = now()
        self.save(update_fields=["customer_account", "agent", "status", "is_sold", "updated_at"])

        MotorcycleHistory.objects.create(
            motorcycle=self,
            action="RESOLD" if is_resale else "LEASED",
            performed_by=user,
            notes=f"{'Re-' if is_resale else ''}Leased to {customer.full_name}"
        )

    def retain(self, user, reason=""):
        if self.status == "RETAINED":
            return  # prevent duplicate
        self.customer_account = None
        self.status = "RETAINED"
        self.is_sold = False
        self.updated_at = now()
        self.save(update_fields=["customer_account", "status", "is_sold", "updated_at"])
        MotorcycleHistory.objects.create(
            motorcycle=self,
            action="RETAINED",
            performed_by=user,
            notes=reason
        )

    def restore_to_active(self, customer, user=None, reason="Arrears cleared"):
        if self.status == "ACTIVE" and self.customer_account == customer:
            return  # prevent duplicate
        self.customer_account = customer
        self.status = "ACTIVE"
        self.updated_at = now()
        self.save(update_fields=["customer_account", "status", "updated_at"])
        MotorcycleHistory.objects.create(
            motorcycle=self,
            action="UPDATED",
            performed_by=user,
            notes=reason
        )

    def return_to_customer(self, customer, user=None):
        if self.status == "ACTIVE" and self.customer_account == customer:
            return  # prevent duplicate
        self.customer_account = customer
        self.status = "ACTIVE"
        self.updated_at = now()
        self.save(update_fields=["customer_account", "status", "updated_at"])
        MotorcycleHistory.objects.create(
            motorcycle=self,
            action="UPDATED",
            performed_by=user,
            notes=f"Returned to {customer.full_name} after arrears cleared"
        )

    def resell_after_default(self, new_customer, user, payment_model="CASH"):
        self.sell_to_customer(new_customer, user, payment_model, is_resale=True)

    def mark_completed(self, payment_model="LEASE"):
        status = "LEASE_COMPLETED" if payment_model == "LEASE" else \
                 "INSTALLMENT_COMPLETED" if payment_model == "INSTALLMENT" else self.status
        if self.status == status:
            return  # prevent duplicate
        self.status = status
        self.updated_at = now()
        self.save(update_fields=["status", "updated_at"])
        MotorcycleHistory.objects.create(
            motorcycle=self,
            action="UPDATED",
            performed_by=None,
            notes=f"{payment_model} plan completed"
        )

    def soft_delete(self, user):
        if self.status == "DELETED":
            return  # prevent duplicate
        self.status = "DELETED"
        self.is_sold = False
        self.updated_at = now()
        self.save(update_fields=["status", "is_sold", "updated_at"])
        MotorcycleHistory.objects.create(
            motorcycle=self,
            action="DELETED",
            performed_by=user,
            notes=f"Motorcycle {self.vin} soft-deleted by {user}"
        )

    # --- Financial lifecycle hooks ---
    def flag_arrears(self, user=None, amount=0):
        # Guard: only log if arrears amount changed
        MotorcycleHistory.objects.create(
            motorcycle=self,
            action="UPDATED",
            performed_by=user,
            notes=f"Arrears flagged: {amount}"
        )

    def clear_arrears(self, user=None):
        MotorcycleHistory.objects.create(
            motorcycle=self,
            action="UPDATED",
            performed_by=user,
            notes="Arrears cleared"
        )

    def defaulted(self, user=None):
        if self.status == "RETAINED":
            return  # prevent duplicate
        self.status = "RETAINED"
        self.save(update_fields=["status"])
        MotorcycleHistory.objects.create(
            motorcycle=self,
            action="RETAINED",
            performed_by=user,
            notes="Motorcycle repossessed due to default"
        )


class MotorcycleHistory(models.Model):
    ACTION_CHOICES = [
        ('CREATED', 'Created'),
        ('MOVED_TO_WAREHOUSE', 'Moved to Warehouse'),
        ('SOLD', 'Sold'),
        ('LEASED', 'Leased'),
        ('RETAINED', 'Retained'),
        ('RESOLD', 'Re-Sold'),
        ('UPDATED', 'Updated'),
        ('DELETED', 'Deleted'),
    ]

    motorcycle = models.ForeignKey(Motorcycle, on_delete=models.CASCADE, related_name="history")
    action = models.CharField(max_length=30, choices=ACTION_CHOICES)
    performed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )
    notes = models.TextField(blank=True, null=True)
    timestamp = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Motorcycle History"
        verbose_name_plural = "Motorcycle Histories"
        ordering = ["-timestamp"]

    def __str__(self):
        return f"{self.motorcycle.vin} - {self.action} by {self.performed_by} at {self.timestamp}"

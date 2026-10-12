from django.db import models
from django.utils import timezone


class NotificationLog(models.Model):
    ROLE_CHOICES = [
        ("Admin", "Admin"),
        ("Manager", "Manager"),
        ("Officer", "Officer"),
        ("Customer", "Customer"),
        ("Agent", "Agent"),
    ]

    role = models.CharField(max_length=50, choices=ROLE_CHOICES, default="Customer")
    customer_name = models.CharField(max_length=255, blank=True, null=True)
    motorcycle_vin = models.CharField(max_length=50, blank=True, null=True)
    phone_number = models.CharField(max_length=20, blank=True, null=True)
    message = models.TextField()
    status = models.CharField(max_length=20, default="SENT")  # SENT, FAILED, PENDING
    sent_at = models.DateTimeField(default=timezone.now)

    def __str__(self):
        return f"{self.role} - {self.customer_name or self.phone_number} ({self.status})"

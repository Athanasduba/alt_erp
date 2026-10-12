from django.db import models
from django.utils.timezone import now

class NotificationLog(models.Model):
    ROLE_CHOICES = [
        ("CUSTOMER", "Customer"),
        ("AGENT", "Agent"),
        ("OFFICER", "Officer"),
    ]

    role = models.CharField(max_length=20, choices=ROLE_CHOICES)
    customer_name = models.CharField(max_length=100)  # ✅ mandatory
    motorcycle_vin = models.CharField(max_length=50)  # ✅ mandatory
    phone_number = models.CharField(max_length=20)
    message = models.TextField()
    sent_at = models.DateTimeField(default=now)
    status = models.CharField(max_length=20, default="SENT")  # SENT / FAILED

    def __str__(self):
        return f"{self.role} - {self.customer_name} ({self.motorcycle_vin})"

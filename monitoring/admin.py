from django.contrib import admin
from notifications.models import NotificationLog

@admin.register(NotificationLog)
class NotificationLogAdmin(admin.ModelAdmin):
    list_display = ("role", "customer_name", "motorcycle_vin", "phone_number", "status", "sent_at")
    search_fields = ("customer_name", "motorcycle_vin", "phone_number", "message")
    list_filter = ("role", "status", "sent_at")

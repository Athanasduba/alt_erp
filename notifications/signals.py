import logging
from django.db.models.signals import post_save
from django.dispatch import receiver
from invoices.models import Invoice
from payments.models import Payment
from notifications.tasks import (
    task_notify_invoice_generated,
    task_notify_payment_processed,
)

logger = logging.getLogger(__name__)

@receiver(post_save, sender=Invoice)
def log_invoice_notification(sender, instance, created, **kwargs):
    if created:
        logger.info(f"[Notification Signal] Invoice {instance.invoice_id} created for {instance.customer.full_name}")
        # ✅ No NotificationLog entry here — Celery tasks handle both individual SMS logs and batch summary
        task_notify_invoice_generated.delay(instance.id)

@receiver(post_save, sender=Payment)
def log_payment_notification(sender, instance, created, **kwargs):
    if created:
        logger.info(f"[Notification Signal] Payment {instance.transaction_id} logged for Customer {instance.customer.full_name}")
        # ✅ No NotificationLog entry here — Celery tasks handle both individual SMS logs and batch summary
        task_notify_payment_processed.delay(instance.id)

import os
from celery import Celery
from celery.schedules import crontab

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'alt_erp.settings')

app = Celery('alt_erp')
app.config_from_object('django.conf:settings', namespace='CELERY')
app.autodiscover_tasks()

# -----------------------------
# Celery Beat Schedule
# -----------------------------
app.conf.beat_schedule = {
    # Daily payment reminders to customers
    "send-payment-reminders-daily": {
        "task": "notifications.tasks.task_send_payment_reminders",
        "schedule": crontab(hour=9, minute=0),  # every day at 9 AM
    },

    # Weekly invoice generation for leasing customers
    "generate-weekly-lease-invoices": {
        "task": "invoices.tasks.run_weekly_lease_generation",
        "schedule": crontab(hour=8, minute=0, day_of_week="monday"),  # every Monday at 8 AM
    },

    # Installment invoice generation (runs daily, task handles schedule internally)
    "generate-installment-invoices": {
        "task": "invoices.tasks.run_installment_generation",
        "schedule": crontab(hour=8, minute=0),  # every day at 8 AM
    },

    # Nightly overdue invoice check
    "check-overdue-invoices": {
        "task": "invoices.tasks.check_overdue_invoices",
        "schedule": crontab(hour=23, minute=0),  # every night at 11 PM
    },
}

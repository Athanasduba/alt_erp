from django.urls import path
from . import views

urlpatterns = [
    # Dashboard + grouped views
    path("dashboard/", views.payment_dashboard, name="payment_dashboard"),
    path("successful/", views.successful_payments, name="successful_payments"),
    path("failed/", views.failed_payments, name="failed_payments"),

    # Payment list
    path("list/", views.payment_list, name="payment_list"),

    # Manual re-apply of failed payment (now uses payment_id)
    path("create/<int:payment_id>/", views.create_payment, name="create_payment"),

    # Selcom webhook
    path("selcom/webhook/", views.selcom_webhook, name="selcom_webhook"),

    # Re-generate failed payment
    path("regenerate/<int:payment_id>/", views.regenerate_payment, name="regenerate_payment"),

    # Selcom Payment Logs (restricted to admin in views)
    path("logs/", views.payment_logs, name="payment_logs"),
]

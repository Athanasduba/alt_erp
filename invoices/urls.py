from django.urls import path
from . import views

urlpatterns = [
    # Existing invoice list
    path("list/", views.invoice_list, name="invoice_list"),

    # New dashboard + lists
    path("dashboard/", views.invoice_dashboard, name="invoice_dashboard"),
    path("successful/", views.successful_invoices, name="successful_invoices"),
    path("failed/", views.failed_invoices, name="failed_invoices"),

    # Selcom webhook
    path("selcom/webhook/", views.selcom_webhook, name="selcom_webhook"),

    #Re-generate the failed invoice
    path("regenerate/<str:invoice_id>/", views.regenerate_invoice, name="regenerate_invoice"),

]

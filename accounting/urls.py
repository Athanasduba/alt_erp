from django.urls import path
from . import views   # import your views module

urlpatterns = [
    path("dashboard/", views.accounting_dashboard, name="accounting_dashboard"),
    path("ledger/", views.ledger_entries_view, name="ledger_entries"),
    path("agents/", views.agent_commission_view, name="agent_commission"),
    path("payout/", views.commission_payout_view, name="commission_payout"),
    path("export/excel/", views.export_accounting_excel, name="export_accounting_excel"),
    path("export/pdf/", views.export_accounting_pdf, name="export_accounting_pdf"),
    path("receipt/<int:payout_id>/", views.agent_receipt_pdf, name="agent_receipt_pdf"),

]

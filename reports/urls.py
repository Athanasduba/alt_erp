from django.urls import path
from . import views

urlpatterns = [
    # Customer Reports
    path("customers/settlement/", views.customer_settlement_report, name="customer_settlement_report"),
    path("customers/arrears-aging/", views.customer_arrears_aging_report, name="customer_arrears_aging_report"),
    path("customers/<int:customer_id>/statement/", views.customer_statement_report, name="customer_statement_report"),
    path("customers/aggregation/", views.customer_aggregation_report, name="customer_aggregation_report"),

    # Agent Reports
    path("agents/commission/", views.agent_commission_report, name="agent_commission_report"),
    path("agents/performance/", views.agent_performance_report, name="agent_performance_report"),

    # Invoices Reports
    path("invoices/status/", views.invoice_status_report, name="invoice_status_report"),
    path("invoices/aging/", views.invoice_aging_report, name="invoice_aging_report"),
    path("invoices/outstanding/", views.outstanding_report, name="outstanding_report"),

    # Payment Reports
    path("payments/success/", views.payment_success_report, name="payment_success_report"),
    path("payments/reconciliation/", views.payment_reconciliation_report, name="payment_reconciliation_report"),
    path("payments/collection/", views.collection_report, name="collection_report"),

    # Accounting Reports
    path("accounting/ledger/", views.ledger_report, name="ledger_report"),
    path("accounting/credit-vs-arrears/", views.credit_vs_arrears_report, name="credit_vs_arrears_report"),

    # Warehouse & Motorcycle Reports
    path("warehouses/stock/", views.warehouse_stock_report, name="warehouse_stock_report"),
    path("motorcycles/status/", views.motorcycle_status_report, name="motorcycle_status_report"),

    # Motorcycle Reports (VIN-based)
    path("motorcycles/statement/", views.motorcycle_statement_report, name="motorcycle_statement_report"),
    path("motorcycles/movement/", views.motorcycle_movement_report, name="motorcycle_movement_report"),

]

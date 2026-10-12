from celery import shared_task
from invoices.models import Invoice
from accounting.models import CustomerAccount, LedgerEntry

@shared_task
def apply_account_balances_to_invoices():
    """
    Runs after new invoices are generated.
    Applies credits and arrears from CustomerAccount to invoices
    and creates ledger entries for each adjustment.
    """
    invoices = Invoice.objects.filter(status='PENDING')
    for invoice in invoices:
        try:
            account = CustomerAccount.objects.get(
                customer=invoice.customer,
                motorcycle=invoice.motorcycle
            )

            # Apply credits first
            if account.credit_balance > 0:
                original_amount = invoice.amount_due
                account.apply_credit_to_invoice(invoice)
                LedgerEntry.objects.create(
                    customer=invoice.customer,
                    motorcycle=invoice.motorcycle,
                    invoice=invoice,
                    entry_type='CREDIT',
                    amount=original_amount - invoice.amount_due,
                    description="Credit applied to invoice"
                )

            # Then apply arrears
            if account.arrears_balance > 0:
                original_amount = invoice.amount_due
                account.apply_arrears_to_invoice(invoice)
                LedgerEntry.objects.create(
                    customer=invoice.customer,
                    motorcycle=invoice.motorcycle,
                    invoice=invoice,
                    entry_type='DEBIT',
                    amount=invoice.amount_due - original_amount,
                    description="Arrears added to invoice"
                )

        except CustomerAccount.DoesNotExist:
            # If no account exists yet, create one
            CustomerAccount.objects.create(
                customer=invoice.customer,
                motorcycle=invoice.motorcycle
            )

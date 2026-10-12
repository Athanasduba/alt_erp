# customers/utils.py
from django.utils import timezone

def initialize_financial_tracking(customer, plan):
    """
    Initialize or refresh financial tracking fields for a customer
    based on their payment plan details.
    The initial deposit is treated as a planned payment, not credit.
    Commission on initial deposit only applies to INSTALLMENT customers.
    """
    total_amount = getattr(plan, "total_amount", 0)

    # ✅ Opening balance is always the full motorcycle price
    customer.opening_balance = total_amount

    # ✅ Balance remains full until payments are made
    customer.balance_remaining = total_amount

    # ✅ Credit only comes from overpayments, not deposits
    customer.credit_amount = 0

    # --- Initial deposit commission logic (INSTALLMENT only) ---
    if customer.payment_model == "INSTALLMENT":
        initial_deposit = getattr(plan, "initial_deposit", 0)
        if initial_deposit > 0 and customer.agent and customer.agent_commission_percent > 0:
            # ✅ Just call the method — it saves commission itself
            customer.calculate_commission(initial_deposit, is_initial_deposit=True)
        else:
            customer.per_initial_deposit_commission = 0
    else:
        customer.per_initial_deposit_commission = 0

    # --- Other tracking fields ---
    customer.arrears_amount = 0
    customer.is_settled = False
    customer.missed_invoices_count = 0
    customer.repossession_flag = False
    customer.last_financial_update = timezone.now()

    customer.save(update_fields=[
        "opening_balance", "balance_remaining", "credit_amount",
        "arrears_amount", "is_settled", "missed_invoices_count",
        "repossession_flag", "last_financial_update",
        "per_initial_deposit_commission"
    ])

from django.shortcuts import render, redirect
from django.db.models import Sum
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse
from django.utils import timezone
import io, xlsxwriter
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4

from accounting.models import CustomerAccount, LedgerEntry, AgentAccount, CommissionPayout
from customers.models import Customer
from motorcycles.models import Motorcycle


# --- Dashboard (summary only) ---
@login_required
def accounting_dashboard(request):
    accounts = CustomerAccount.objects.select_related('customer', 'motorcycle')

    credits_total = accounts.aggregate(total_credit=Sum('credit_balance'))['total_credit'] or 0
    arrears_total = accounts.aggregate(total_arrears=Sum('arrears_balance'))['total_arrears'] or 0

    settled_count = Customer.objects.filter(settled_flag=True).count()
    unsettled_count = Customer.objects.filter(settled_flag=False).count()

    ledger_count = LedgerEntry.objects.count()
    agent_count = AgentAccount.objects.count()
    payout_count = CommissionPayout.objects.count()

    context = {
        "credits_total": credits_total,
        "arrears_total": arrears_total,
        "settled_count": settled_count,
        "unsettled_count": unsettled_count,
        "ledger_count": ledger_count,
        "agent_count": agent_count,
        "payout_count": payout_count,
    }
    return render(request, "accounting/dashboard.html", context)


# --- Ledger Entries Submodule ---
@login_required
def ledger_entries_view(request):
    entries = LedgerEntry.objects.select_related("customer", "motorcycle", "invoice").order_by("-created_at")
    return render(request, "accounting/ledger_entries.html", {"ledger_entries": entries})


# --- Agent Commission Submodule ---
@login_required
def agent_commission_view(request):
    accounts = AgentAccount.objects.select_related("agent")
    payouts = CommissionPayout.objects.select_related("agent").order_by("-paid_on")
    return render(request, "accounting/agent_commission.html", {
        "agent_accounts": accounts,
        "commission_payouts": payouts,
    })


# --- Commission Payout Workflow ---
@login_required
def commission_payout_view(request):
    if request.method == "POST":
        agent_id = request.POST.get("agent_id")
        start_date = request.POST.get("start_date")
        end_date = request.POST.get("end_date")

        # TODO: calculate commission for agent between start_date and end_date
        # Example:
        # CommissionPayout.objects.create(
        #     agent_id=agent_id,
        #     amount=calculated_amount,
        #     paid_on=timezone.now()
        # )

        return redirect("agent_commission")

    agents = AgentAccount.objects.select_related("agent")
    return render(request, "accounting/commission_payout.html", {"agents": agents})


# --- Agent Receipt PDF ---
@login_required
def agent_receipt_pdf(request, payout_id):
    payout = CommissionPayout.objects.select_related("agent").get(id=payout_id)

    response = HttpResponse(content_type="application/pdf")
    filename = f"agent_receipt_{payout.id}.pdf"
    response["Content-Disposition"] = f'attachment; filename="{filename}"'

    buffer = io.BytesIO()
    p = canvas.Canvas(buffer, pagesize=A4)
    width, height = A4

    # --- Logo ---
    logo_path = "static/img/logo.png"   # adjust path if needed
    try:
        p.drawImage(logo_path, 50, height - 100, width=80, height=80, preserveAspectRatio=True, mask='auto')
    except Exception:
        # fallback if logo not found
        p.setFont("Helvetica-Bold", 12)
        p.drawString(50, height - 80, "Alternative ERP")

    # --- Header ---
    p.setFont("Helvetica-Bold", 16)
    p.drawString(150, height - 50, "Agent Commission Receipt")

    # --- Receipt details ---
    y = height - 150
    p.setFont("Helvetica", 12)
    p.drawString(50, y, f"Receipt ID: {payout.id}")
    y -= 25
    p.drawString(50, y, f"Agent: {payout.agent.full_name}")
    y -= 25
    p.drawString(50, y, f"Amount Paid: {payout.amount}")
    y -= 25
    p.drawString(50, y, f"Paid On: {payout.paid_on.strftime('%Y-%m-%d %H:%M')}")
    y -= 25
    p.drawString(50, y, f"Generated At: {timezone.now().strftime('%Y-%m-%d %H:%M')}")

    # --- Footer ---
    y -= 50
    p.setFont("Helvetica-Oblique", 10)
    p.drawString(50, y, "This receipt is system-generated and valid for reference.")

    p.save()
    pdf = buffer.getvalue()
    buffer.close()
    response.write(pdf)
    return response



# --- Export Functions ---
@login_required
def export_accounting_excel(request):
    output = io.BytesIO()
    workbook = xlsxwriter.Workbook(output)

    # --- Summary sheet ---
    summary = workbook.add_worksheet("Summary")
    summary.write_row(0, 0, ["Customer", "Motorcycle VIN", "Credit Balance", "Arrears Balance"])
    accounts = CustomerAccount.objects.select_related("customer", "motorcycle")
    for row, acc in enumerate(accounts, start=1):
        summary.write(row, 0, acc.customer.full_name)
        summary.write(row, 1, acc.motorcycle.vin)
        summary.write(row, 2, float(acc.credit_balance))
        summary.write(row, 3, float(acc.arrears_balance))

    # --- Individual VIN sheets ---
    vins = Motorcycle.objects.values_list("vin", flat=True).distinct()
    for vin in vins:
        ws = workbook.add_worksheet(vin)
        ws.write_row(0, 0, ["Date", "Customer", "Invoice", "Type", "Amount", "Description", "Mobile", "Transaction ID", "Bank"])
        entries = LedgerEntry.objects.filter(motorcycle__vin=vin).select_related("customer", "invoice")
        for row, entry in enumerate(entries, start=1):
            ws.write(row, 0, str(entry.created_at))
            ws.write(row, 1, entry.customer.full_name if entry.customer else "")
            ws.write(row, 2, entry.invoice.invoice_id if entry.invoice else "")
            ws.write(row, 3, entry.entry_type)
            ws.write(row, 4, float(entry.amount))
            ws.write(row, 5, entry.description or "")
            ws.write(row, 6, entry.mobile_number or "")
            ws.write(row, 7, entry.transaction_id or "")
            ws.write(row, 8, entry.bank_account or "")

    # --- Agent Accounts ---
    ws_agents = workbook.add_worksheet("Agent Accounts")
    ws_agents.write_row(0, 0, ["Agent", "Accrued Commission", "Updated At"])
    for row, acc in enumerate(AgentAccount.objects.select_related("agent"), start=1):
        ws_agents.write(row, 0, acc.agent.full_name)
        ws_agents.write(row, 1, float(acc.accrued_commission))
        ws_agents.write(row, 2, str(acc.updated_at))

    # --- Commission Payouts ---
    ws_payouts = workbook.add_worksheet("Commission Payouts")
    ws_payouts.write_row(0, 0, ["Agent", "Amount Paid", "Paid On"])
    for row, payout in enumerate(CommissionPayout.objects.select_related("agent"), start=1):
        ws_payouts.write(row, 0, payout.agent.full_name)
        ws_payouts.write(row, 1, float(payout.amount))
        ws_payouts.write(row, 2, str(payout.paid_on))

    workbook.close()
    output.seek(0)

    response = HttpResponse(output.read(), content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    response["Content-Disposition"] = 'attachment; filename="accounting_report.xlsx"'
    return response


@login_required
def export_accounting_pdf(request):
    response = HttpResponse(content_type="application/pdf")
    response["Content-Disposition"] = 'attachment; filename="accounting_report.pdf"'

    buffer = io.BytesIO()
    p = canvas.Canvas(buffer, pagesize=A4)
    width, height = A4

    p.setFont("Helvetica-Bold", 14)
    p.drawString(50, height - 50, "Accounting Report")

    y = height - 100

    # --- Customer Accounts ---
    p.setFont("Helvetica-Bold", 12)
    p.drawString(50, y, "Customer Accounts")
    y -= 30
    for acc in CustomerAccount.objects.select_related("customer", "motorcycle"):
        line = f"{acc.customer.full_name} | VIN: {acc.motorcycle.vin} | Credit: {acc.credit_balance} | Arrears: {acc.arrears_balance}"
        p.setFont("Helvetica", 10)
        p.drawString(50, y, line)
        y -= 20
        if y < 50:
            p.showPage()
            y = height - 50

    # --- Agent Accounts ---
    p.showPage()
    y = height - 50
    p.setFont("Helvetica-Bold", 12)
    p.drawString(50, y, "Agent Accounts")
    y -= 30
    for acc in AgentAccount.objects.select_related("agent"):
        line = f"{acc.agent.full_name} | Commission: {acc.accrued_commission} | Updated: {acc.updated_at}"
        p.setFont("Helvetica", 10)
        p.drawString(50, y, line)
        y -= 20
        if y < 50:
            p.showPage()
            y = height - 50

    # --- Commission Payouts ---
    p.showPage()
    y = height - 50
    p.setFont("Helvetica-Bold", 12)
    p.drawString(50, y, "Commission Payouts")
    y -= 30
    for payout in CommissionPayout.objects.select_related("agent"):
        line = f"{payout.agent.full_name} | Amount: {payout.amount} | Paid On: {payout.paid_on}"
        p.setFont("Helvetica", 10)
        p.drawString(50, y, line)
        y -= 20
        if y < 50:
            p.showPage()
            y = height - 50

    p.save()
    pdf = buffer.getvalue()
    buffer.close()
    response.write(pdf)
    return response

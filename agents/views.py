from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect
from django.urls import reverse_lazy
from django.views.generic import ListView, DetailView, CreateView, UpdateView, DeleteView
from django.contrib.auth import get_user_model
from django.db.models import Q, Count, Sum
from django.utils.dateparse import parse_date
from django.db.models.functions import TruncMonth
from django.contrib import messages
from django.contrib.auth.hashers import make_password
from .models import Agent, IndividualAgent, CompanyAgent
from .forms import AgentForm, IndividualAgentForm, CompanyAgentForm
from customers.models import Customer
from motorcycles.models import Motorcycle
from invoices.models import Invoice
from payments.models import Payment

User = get_user_model()

@login_required
def agent_dashboard(request):
    if getattr(request.user, "role", None) not in ["ADMIN", "MANAGER"]:
        return render(request, "403.html")

    # ✅ Time range filter
    start_date_str = request.GET.get("start_date")
    end_date_str = request.GET.get("end_date")

    start_date = parse_date(start_date_str) if start_date_str else None
    end_date = parse_date(end_date_str) if end_date_str else None

    customers_qs = Customer.objects.all()
    if start_date:
        customers_qs = customers_qs.filter(created_at__date__gte=start_date)
    if end_date:
        customers_qs = customers_qs.filter(created_at__date__lte=end_date)

    # ✅ Monthly onboarding trend
    monthly_data = (
        customers_qs.annotate(month=TruncMonth("created_at"))
        .values("month")
        .annotate(count=Count("id"))
        .order_by("month")
    )
    months = [d["month"].strftime("%b %Y") for d in monthly_data]
    monthly_counts = [d["count"] for d in monthly_data]

    # ✅ Agents sorted by motorcycles sold (ascending)
    agents_with_stats = (
        Agent.objects.annotate(
            customer_count=Count("customers"),
            motorcycle_count=Count("customers__motorcycle"),
            arrears_total=Sum("customers__arrears_amount"),
            payments_total=Sum("payments__amount_paid"),
        )
        .order_by("motorcycle_count")  # ascending order
    )

    context = {
        "agents": agents_with_stats,
        "months": months,
        "monthly_counts": monthly_counts,
        "start_date": start_date_str or "",
        "end_date": end_date_str or "",
    }
    return render(request, "agents/agent_dashboard.html", context)


class AgentListView(ListView):
    model = Agent
    template_name = "agents/agent_list.html"
    context_object_name = "agents"
    paginate_by = 50

    def get_queryset(self):
        qs = Agent.objects.all().order_by("-created_on")

        agent_type = self.request.GET.get("agent_type")
        warehouse = self.request.GET.get("warehouse")
        supervisor = self.request.GET.get("supervisor")
        search = self.request.GET.get("search")
        start_date = self.request.GET.get("start_date")
        end_date = self.request.GET.get("end_date")

        if agent_type:
            qs = qs.filter(agent_type__iexact=agent_type)
        if warehouse:
            qs = qs.filter(warehouse__id=warehouse)
        if supervisor:
            qs = qs.filter(supervisor__id=supervisor)
        if search:
            qs = qs.filter(Q(user__username__icontains=search))
        if start_date:
            qs = qs.filter(created_on__date__gte=parse_date(start_date))
        if end_date:
            qs = qs.filter(created_on__date__lte=parse_date(end_date))

        return qs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["warehouses"] = []  # load warehouses if needed
        context["supervisors"] = User.objects.filter(role="MANAGER")
        return context


class AgentDetailView(DetailView):
    model = Agent
    template_name = "agents/agent_detail.html"
    context_object_name = "agent"


class AgentCreateView(CreateView):
    model = Agent
    form_class = AgentForm
    template_name = "agents/agent_form.html"
    success_url = reverse_lazy("agent_list")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # Always provide blank forms for GET
        context["individual_form"] = kwargs.get("individual_form") or IndividualAgentForm()
        context["company_form"] = kwargs.get("company_form") or CompanyAgentForm()
        return context

    def post(self, request, *args, **kwargs):
        agent_form = AgentForm(request.POST)
        individual_form = IndividualAgentForm(request.POST, request.FILES)
        company_form = CompanyAgentForm(request.POST, request.FILES)

        if agent_form.is_valid():
            username = agent_form.cleaned_data.get("username")
            raw_password = agent_form.cleaned_data.get("new_password") or "default123"

            user = User.objects.create(
                username=username,
                password=make_password(raw_password),
            )

            agent = agent_form.save(commit=False)
            agent.user = user
            agent.save()

            if agent.agent_type == "INDIVIDUAL" and individual_form.is_valid():
                details = individual_form.save(commit=False)
                details.agent = agent
                details.save()
            elif agent.agent_type == "COMPANY" and company_form.is_valid():
                details = company_form.save(commit=False)
                details.agent = agent
                details.save()

            messages.success(request, "Agent created successfully.")
            return redirect(self.success_url)

        # Pass forms back if invalid
        context = {
            "form": agent_form,
            "individual_form": individual_form,
            "company_form": company_form,
        }
        return self.render_to_response(context)


class AgentUpdateView(UpdateView):
    model = Agent
    form_class = AgentForm
    template_name = "agents/agent_form.html"
    success_url = reverse_lazy("agent_list")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        agent = self.object
        # Always provide forms with instance data
        context["individual_form"] = kwargs.get("individual_form") or IndividualAgentForm(
            self.request.POST or None,
            self.request.FILES or None,
            instance=getattr(agent, "individual_details", None)
        )
        context["company_form"] = kwargs.get("company_form") or CompanyAgentForm(
            self.request.POST or None,
            self.request.FILES or None,
            instance=getattr(agent, "company_details", None)
        )
        return context

    def form_valid(self, form):
        agent = form.save(commit=False)
        new_password = form.cleaned_data.get("new_password")
        username = form.cleaned_data.get("username")

        if not agent.user:
            agent.user = User.objects.create(
                username=username,
                password=make_password(new_password or "default123"),
            )
        else:
            agent.user.username = username
            if new_password:
                agent.user.password = make_password(new_password)
            agent.user.save()

        agent.save()

        context = self.get_context_data()
        detail_form = context["individual_form"] if agent.agent_type == "INDIVIDUAL" else context["company_form"]

        if detail_form.is_valid():
            details = detail_form.save(commit=False)
            details.agent = agent
            details.save()
        else:
            messages.error(self.request, "Please correct the errors in Agent details form.")
            return self.render_to_response(context)

        messages.success(self.request, "Agent updated successfully.")
        return redirect(self.success_url)

    def form_invalid(self, form):
        context = self.get_context_data(form=form)
        return self.render_to_response(context)



class AgentDeleteView(DeleteView):
    model = Agent
    template_name = "agents/agent_confirm_delete.html"
    success_url = reverse_lazy("agent_list")

    def dispatch(self, request, *args, **kwargs):
        if getattr(request.user, "role", None) not in ["ADMIN", "MANAGER"]:
            return render(request, "403.html")
        return super().dispatch(request, *args, **kwargs)

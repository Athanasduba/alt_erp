import logging
from django.core.paginator import Paginator
from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django_celery_results.models import TaskResult
from django.db.models import Q
from django.utils.dateparse import parse_date
from .models import NotificationLog

logger = logging.getLogger(__name__)


@login_required
def dashboard(request):
    if request.user.role not in ["ADMIN", "MANAGER", "OFFICER"]:
        return render(request, "403.html")

    tasks = TaskResult.objects.all().order_by("-date_done")

    # Filters
    status = request.GET.get("status")
    task_name = request.GET.get("task_name")
    search = request.GET.get("search")
    start_date = request.GET.get("start_date")
    end_date = request.GET.get("end_date")

    if status:
        tasks = tasks.filter(status__iexact=status)
    if task_name:
        tasks = tasks.filter(task_name__icontains=task_name)
    if search:
        tasks = tasks.filter(
            Q(task_name__icontains=search) |
            Q(result__icontains=search)
        )

    start = parse_date(start_date) if start_date else None
    end = parse_date(end_date) if end_date else None

    if start and end and start > end:
        return render(request, "monitoring/dashboard.html", {
            "page_obj": [],
            "error": "Invalid date range: start date is after end date."
        })
    if start:
        tasks = tasks.filter(date_done__date__gte=start)
    if end:
        tasks = tasks.filter(date_done__date__lte=end)

    # Pagination
    paginator = Paginator(tasks, 50)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    return render(request, "monitoring/dashboard.html", {
        "page_obj": page_obj,
    })


@login_required
def notifications_list(request):
    # Role check: only Admin, Manager, Officer
    if request.user.role not in ["ADMIN", "MANAGER", "OFFICER"]:
        return render(request, "403.html")

    notifications = NotificationLog.objects.all().order_by("-sent_at")

    # Filters
    role = request.GET.get("role")
    search = request.GET.get("search")
    start_date = request.GET.get("start_date")
    end_date = request.GET.get("end_date")

    if role:
        notifications = notifications.filter(role__iexact=role)
    if search:
        notifications = notifications.filter(
            Q(customer_name__icontains=search) |
            Q(motorcycle_vin__icontains=search) |
            Q(phone_number__icontains=search) |
            Q(status__icontains=search) |
            Q(message__icontains=search)
        )

    start = parse_date(start_date) if start_date else None
    end = parse_date(end_date) if end_date else None

    if start and end and start > end:
        return render(request, "notifications/notifications_list.html", {
            "page_obj": [],
            "error": "Invalid date range: start date is after end date."
        })
    if start:
        notifications = notifications.filter(sent_at__date__gte=start)
    if end:
        notifications = notifications.filter(sent_at__date__lte=end)

    # Pagination: 50 per page
    paginator = Paginator(notifications, 50)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    return render(request, "notifications/notifications_list.html", {
        "page_obj": page_obj,
    })

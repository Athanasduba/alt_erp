import json
from django.http import JsonResponse
from django.shortcuts import render
from django.core.paginator import Paginator
from django.db.models import Q
from django.utils.dateparse import parse_date
from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth.decorators import login_required
from .models import NotificationLog


@login_required
def notifications_list(request):
    """
    Display NotificationLog entries (individual SMS + SYSTEM batch summaries).
    Supports filtering by role, search, and date range.
    Only Admin, Manager, Officer can view.
    """
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
            Q(message__icontains=search)   # ✅ allow searching SYSTEM batch summaries too
        )
    if start_date and end_date and parse_date(start_date) > parse_date(end_date):
        return render(request, "notifications/notifications_list.html", {
            "page_obj": [],
            "error": "Invalid date range: start date is after end date."
        })
    if start_date:
        notifications = notifications.filter(sent_at__date__gte=parse_date(start_date))
    if end_date:
        notifications = notifications.filter(sent_at__date__lte=parse_date(end_date))

    # Pagination: 50 per page
    paginator = Paginator(notifications, 50)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    return render(request, "notifications/notifications_list.html", {
        "page_obj": page_obj,
    })


@csrf_exempt
@login_required
def create_notification(request):
    """
    Manual notification creation (rarely used).
    Normally notifications are created via signals + Celery tasks.
    Only Admin, Manager, Officer can create manually.
    """
    if request.user.role not in ["ADMIN", "MANAGER", "OFFICER"]:
        return render(request, "403.html")

    if request.method == "POST":
        role = request.POST.get("role", "Customer")
        customer_name = request.POST.get("customer_name")
        motorcycle_vin = request.POST.get("motorcycle_vin")
        phone_number = request.POST.get("phone_number")
        message = request.POST.get("message", "")
        status = request.POST.get("status", "SENT")

        notification = NotificationLog.objects.create(
            role=role,
            customer_name=customer_name,
            motorcycle_vin=motorcycle_vin,
            phone_number=phone_number,
            message=message,
            status=status,
        )
        return JsonResponse({"status": "success", "id": notification.id})

    return render(request, "notifications/notification_form.html")

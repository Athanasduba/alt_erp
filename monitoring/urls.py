from django.urls import path
from .views import dashboard, notifications_list

urlpatterns = [
    path("dashboard/", dashboard, name="monitoring_dashboard"),
    path("notifications/", notifications_list, name="notifications_list"),
]

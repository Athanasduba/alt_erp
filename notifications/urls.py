from django.urls import path
from . import views

app_name = "notifications"

urlpatterns = [
    path("list/", views.notifications_list, name="notifications_list"),  # ✅ plural
    path("create/", views.create_notification, name="create_notification"),
]

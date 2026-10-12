from django.urls import path
from . import views

urlpatterns = [
    path("dashboard/", views.agent_dashboard, name="agent_dashboard"),
    path("list/", views.AgentListView.as_view(), name="agent_list"),
    path("<int:pk>/", views.AgentDetailView.as_view(), name="agent_detail"),
    path("create/", views.AgentCreateView.as_view(), name="agent_create"),
    path("<int:pk>/update/", views.AgentUpdateView.as_view(), name="agent_update"),
    path("<int:pk>/delete/", views.AgentDeleteView.as_view(), name="agent_delete"),
]

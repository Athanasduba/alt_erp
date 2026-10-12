from django.urls import path
from .views import (
    # Authentication
    login_view, logout_view, role_redirect,

    # Dashboards
    admin_dashboard, manager_dashboard, accountant_dashboard,
    officer_dashboard, store_dashboard, agent_dashboard,
    sales_dashboard, care_dashboard,

    # User Management CRUD
    user_management, user_edit, user_delete, user_toggle_active
)

urlpatterns = [
    # Authentication
    path('login/', login_view, name='login'),
    path('logout/', logout_view, name='logout'),
    # ❌ Removed duplicate 'redirect/' path — handled in project urls.py

    # Role Dashboards
    path('admin/', admin_dashboard, name='admin_dashboard'),
    path('manager/', manager_dashboard, name='manager_dashboard'),
    path('accountant/', accountant_dashboard, name='accountant_dashboard'),
    path('officer/', officer_dashboard, name='officer_dashboard'),
    path('store/', store_dashboard, name='store_dashboard'),
    path('agent/', agent_dashboard, name='agent_dashboard'),
    path('sales/', sales_dashboard, name='sales_dashboard'),
    path('care/', care_dashboard, name='care_dashboard'),

    # Combined User Management
    path('management/', user_management, name='user_management'),
    path('<int:pk>/edit/', user_edit, name='user_edit'),
    path('<int:pk>/delete/', user_delete, name='user_delete'),
    path('<int:pk>/toggle-active/', user_toggle_active, name='user_toggle_active'),
]

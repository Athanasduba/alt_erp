from django.urls import path
from . import views

urlpatterns = [
    path('list/', views.customer_list, name='customer_list'),
    path('manager/', views.manager_dashboard, name='manager_dashboard'),
    path('approve/<int:pk>/', views.approve_customer, name='approve_customer'),
    path('onboarding/', views.customer_onboarding, name='customer_onboarding'),
    path('<int:pk>/edit/', views.customer_onboarding, name='customer_edit'),
    path('<int:customer_id>/<str:status>/update/', views.update_customer_status, name='update_customer_status'),
    path('<int:pk>/', views.customer_detail, name='customer_detail'),
    # ✅ AJAX endpoint
    path('available-motorcycles/<int:warehouse_id>/', views.available_motorcycles, name='available_motorcycles'),
]


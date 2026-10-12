from django.urls import path
from . import views

urlpatterns = [
    path("dashboard/", views.sales_dashboard, name="sales_dashboard"),
    path("", views.sale_list, name="sale_list"),
    path("<int:sale_id>/", views.sale_detail, name="sale_detail"),
    path("<int:sale_id>/add-payment/", views.add_payment, name="add_payment"),
]

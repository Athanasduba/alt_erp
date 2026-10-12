from django.urls import path
from . import views

urlpatterns = [
    # Warehouse dashboard + CRUD
    path('', views.warehouse_list, name='warehouse_list'),
    path('create/', views.warehouse_create, name='warehouse_create'),

    # Stock transfers
    path('transfer/create/', views.transfer_create, name='transfer_create'),
    path('transfer/<int:pk>/approve/', views.transfer_approve, name='transfer_approve'),

    # Repossession workflow
    path('repossession/create/', views.repossession_create, name='repossession_create'),
    path('repossession/<int:pk>/approve/', views.repossession_approve, name='repossession_approve'),
]

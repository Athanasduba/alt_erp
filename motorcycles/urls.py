from django.urls import path
from . import views
 
urlpatterns = [
    path("", views.motorcycle_list, name="motorcycle_list"),
    path("add/", views.add_motorcycle, name="add_motorcycle"),
    path("<int:pk>/edit/", views.edit_motorcycle, name="edit_motorcycle"),
    path("<int:pk>/delete/", views.delete_motorcycle, name="delete_motorcycle"),
    path("move/", views.move_motorcycles, name="move_motorcycles"),
    path("upload/", views.upload_motorcycles_excel, name="upload_motorcycles_excel"),
    path("<int:pk>/", views.motorcycle_detail, name="motorcycle_detail"),  # <-- keep this last
    path("api/motorcycles/by-warehouse/<int:warehouse_id>/", views.motorcycles_by_warehouse, name="motorcycles_by_warehouse"),
]

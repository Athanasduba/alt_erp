from django.contrib import admin
from django.urls import path, include
from django.shortcuts import redirect
from users.views import role_redirect
from django.conf import settings
from django.conf.urls.static import static

# Redirect root URL "/" directly to /users/login/
def root_redirect(request):
    return redirect("/users/login/")

urlpatterns = [
    path('admin/', admin.site.urls),
    path('dashboard/redirect/', role_redirect, name='role_redirect'),
    path('dashboard/', include('dashboard.urls')),
    path('users/', include('users.urls')),
    path('customers/', include('customers.urls')),
    path('warehouses/', include('warehouses.urls')),
    path('motorcycles/', include('motorcycles.urls')),
    path('agents/', include('agents.urls')),
    path('sales/', include('sales.urls')),
    path('invoices/', include('invoices.urls')),
    path('accounting/', include('accounting.urls')),
    path('reports/', include('reports.urls')),
    path('monitoring/', include('monitoring.urls')),
    path('payments/', include('payments.urls')),

    # Root URL fallback
    path('', root_redirect, name='home'),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

from django.contrib import admin
from django.urls import path, include
from django.shortcuts import redirect
from users.views import role_redirect   # ✅ role-based redirect function
from django.conf import settings
from django.conf.urls.static import static

# Redirect root URL "/" to the login page
def root_redirect(request):
    # ✅ Explicitly redirect to /users/login/
    return redirect("/users/login/")

urlpatterns = [
    path('admin/', admin.site.urls),

    # Role-based redirect after login (separate path to avoid conflict)
    path('dashboard/redirect/', role_redirect, name='role_redirect'),

    # Dashboard app routes
    path('dashboard/', include('dashboard.urls')),

    # ERP app routes
    path('users/', include('users.urls')),
    path('customers/', include('customers.urls')),
    path('warehouses/', include('warehouses.urls')),
    path('motorcycles/', include('motorcycles.urls')),  # CRUD & inventory
    path('agents/', include('agents.urls')),
    path('sales/', include('sales.urls')),
    path('invoices/', include('invoices.urls')),
    path('accounting/', include('accounting.urls')),
    path('reports/', include('reports.urls')),          # ✅ Reporting routes

    # System Logs (Monitoring + Notifications)
    path('monitoring/', include('monitoring.urls')),

    # Payment app routes
    path('payments/', include('payments.urls')),

    # Root URL fallback
    path('', root_redirect, name='home'),
]

# ✅ Serve media files in development (contracts, licenses, etc.)
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

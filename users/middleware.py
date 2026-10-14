from django.shortcuts import redirect
from django.utils.deprecation import MiddlewareMixin
from django.contrib import messages

RAILWAY_DOMAINS = [
    "hefhjsz3.up.railway.app",
    "alterp-production.up.railway.app",
]

class SessionSecurityMiddleware(MiddlewareMixin):
    def process_request(self, request):
        host = request.get_host()

        # --- Force domain redirect ---
        if host.startswith("www."):
            new_url = request.build_absolute_uri().replace("://www.", "://")
            return redirect(new_url, permanent=True)
        if host in RAILWAY_DOMAINS:
            new_url = request.build_absolute_uri().replace(host, "alt-erp.com")
            return redirect(new_url, permanent=True)

        # ✅ Do nothing if already alt-erp.com
        if host == "alt-erp.com":
            return None

        # --- Enforce session validity ---
        if not request.user.is_authenticated:
            if request.path.startswith('/users/login') or request.path.startswith('/static/') \
               or request.path == '/login/' \
               or request.path.startswith('/payments/selcom/webhook/') \
               or request.path.startswith('/payments/logs/'):
                return None
            return redirect('login')
        return None

    def process_response(self, request, response):
        if request.path.startswith('/users/login') or request.path.startswith('/users/logout') \
           or request.path == '/login/' or request.path == '/logout/':
            storage = messages.get_messages(request)
            for _ in storage:
                pass
            storage.used = True
        return response

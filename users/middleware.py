from django.shortcuts import redirect
from django.utils.deprecation import MiddlewareMixin
from django.contrib import messages

RAILWAY_DOMAINS = [
    "hefhjsz3.up.railway.app",
    "alterp-production.up.railway.app",
]

class SessionSecurityMiddleware(MiddlewareMixin):
    """
    Middleware to enforce session validity:
    - Redirects to login if session expired or invalid
    - Prevents access to dashboards without fresh credentials
    - Clears old messages when visiting login/logout so they don't leak
    - Redirects www and Railway domains to alt-erp.com
    """

    def process_request(self, request):
        host = request.get_host()

        # --- Force domain redirect ---
        if host.startswith("www."):
            new_url = request.build_absolute_uri().replace("://www.", "://")
            return redirect(new_url, permanent=True)
        if host in RAILWAY_DOMAINS:
            new_url = request.build_absolute_uri().replace(host, "alt-erp.com")
            return redirect(new_url, permanent=True)

        # --- Enforce session validity ---
        if not request.user.is_authenticated:
            # Allow login page, static files, Selcom webhook, and Payment Logs
            if request.path.startswith('/users/login') or request.path.startswith('/static/') \
               or request.path == '/login/' \
               or request.path.startswith('/payments/selcom/webhook/') \
               or request.path.startswith('/payments/logs/'):
                return None
            return redirect('login')
        return None

    def process_response(self, request, response):
        # --- Clear messages on login/logout routes AFTER response is built ---
        if request.path.startswith('/users/login') or request.path.startswith('/users/logout') \
           or request.path == '/login/' or request.path == '/logout/':
            storage = messages.get_messages(request)
            for _ in storage:
                pass
            storage.used = True
        return response

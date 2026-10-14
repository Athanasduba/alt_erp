from django.shortcuts import redirect
from django.utils.deprecation import MiddlewareMixin
from django.contrib import messages

class SessionSecurityMiddleware(MiddlewareMixin):
    def process_request(self, request):
        # --- Enforce session validity ---
        if not request.user.is_authenticated:
            if request.path.startswith('/users/login') or request.path.startswith('/static/') \
               or request.path.startswith('/payments/selcom/webhook/') \
               or request.path.startswith('/payments/logs/'):
                return None
            # ✅ always send unauthenticated users to /users/login/
            return redirect("/users/login/")
        return None

    def process_response(self, request, response):
        if request.path.startswith('/users/login') or request.path.startswith('/users/logout'):
            storage = messages.get_messages(request)
            for _ in storage:
                pass
            storage.used = True
        return response

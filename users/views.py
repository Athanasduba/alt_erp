from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import authenticate, login, logout, get_user_model
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib import messages
from .forms import UserCreateForm, UserUpdateForm
from warehouses.models import Warehouse
from payments.models import Payment

User = get_user_model()

# --- Authentication Views ---

def login_view(request):
    if request.method == "POST":
        username = request.POST.get("username")
        password = request.POST.get("password")
        user = authenticate(request, username=username, password=password)

        if user is not None:
            login(request, user)
            return redirect("role_redirect")  # send to role-based dashboard
        else:
            # Add error message to be displayed in template
            messages.error(request, "Invalid username or password")

    # Always render the login page, with any messages included
    return render(request, "users/login.html")


@login_required
def logout_view(request):
    logout(request)
    return redirect("login")

@login_required
def role_redirect(request):
    """Send each role to its landing page after login."""
    role = getattr(request.user, "role", None)

    if role == 'ADMIN':
        return redirect('admin_dashboard')
    elif role == 'MANAGER':
        return redirect('manager_dashboard')
    elif role == 'ACCOUNTANT':
        return redirect('accountant_dashboard')
    elif role == 'OFFICER':
        return redirect('officer_dashboard')
    elif role == 'STORE':
        return redirect('store_dashboard')
    elif role == 'AGENT':
        return redirect('agent_dashboard')
    elif role == 'SALES':
        return redirect('sales_dashboard')
    elif role == 'CARE':
        return redirect('care_dashboard')
    else:
        return redirect('dashboard_home')  # fallback

# --- Role-based decorators ---

def role_required(role):
    """Decorator to restrict view access to a specific role."""
    def check_role(user):
        return getattr(user, "role", None) == role
    return user_passes_test(check_role)

# --- Role Dashboards ---
@login_required
@role_required('ADMIN')
def admin_dashboard(request):
    """Admin dashboard view with context for sidebar links."""
    # Get the latest failed payment (or None if none exist)
    failed_payment = Payment.objects.filter(status="FAILED").order_by("-timestamp").first()

    context = {
        "failed_payment": failed_payment,
        "is_admin": True,   # so your template condition works
        "is_manager": False # adjust if you want managers to see it too
    }
    return render(request, "users/admin_dashboard.html", context)


@login_required
@role_required('MANAGER')
def manager_dashboard(request):
    return render(request, "users/manager_dashboard.html")

@login_required
@role_required('ACCOUNTANT')
def accountant_dashboard(request):
    return render(request, "users/accountant_dashboard.html")

@login_required
@role_required('OFFICER')
def officer_dashboard(request):
    return render(request, "users/officer_dashboard.html")

@login_required
@role_required('STORE')
def store_dashboard(request):
    return render(request, "users/store_dashboard.html")

@login_required
@role_required('AGENT')
def agent_dashboard(request):
    return render(request, "users/agent_dashboard.html")

@login_required
@role_required('SALES')
def sales_dashboard(request):
    return render(request, "users/sales_dashboard.html")

@login_required
@role_required('CARE')
def care_dashboard(request):
    return render(request, "users/care_dashboard.html")

# --- Combined User Management ---

@login_required
def user_management(request):
    role = (getattr(request.user, "role", "") or "").upper()

    if role not in ['ADMIN', 'MANAGER']:
        messages.error(request, "You do not have permission to manage users.")
        return redirect("role_redirect")

    users = User.objects.all() if role == 'ADMIN' else User.objects.exclude(role='ADMIN')
    form = UserCreateForm(request.POST or None)
    warehouses = Warehouse.objects.all()
    password_error = None

    if request.method == "POST" and form.is_valid():
        new_user = form.save(commit=False)

        # Warehouses (checkboxes)
        warehouse_ids = request.POST.getlist("warehouses")
        selected_warehouses = Warehouse.objects.filter(pk__in=warehouse_ids)

        # Password validation handled by form
        if form.errors.get("password2"):
            password_error = form.errors["password2"]

        # Active status
        new_user.is_active = bool(request.POST.get("is_active"))

        # Role restrictions
        if role == 'MANAGER' and new_user.role == 'ADMIN':
            messages.error(request, "Managers cannot create Admin users.")
        else:
            new_user.save()
            form.save_m2m()
            new_user.warehouses.set(selected_warehouses)
            messages.success(request, f"User {new_user.username} created successfully.")
            return redirect("user_management")

    return render(request, "users/user_management.html", {
        "users": users,
        "form": form,
        "warehouses": warehouses,
        "title": "User Management",
        "password_error": password_error,
    })

# --- Edit/Delete/Toggle ---

@login_required
def user_edit(request, pk):
    target_user = get_object_or_404(User, pk=pk)
    role = getattr(request.user, "role", None)

    if role not in ['ADMIN', 'MANAGER']:
        messages.error(request, "You do not have permission to edit users.")
        return redirect("user_management")

    password_error = None

    if request.method == "POST":
        form = UserUpdateForm(request.POST, instance=target_user)
        if form.is_valid():
            updated_user = form.save(commit=False)

            # Role restrictions
            if role == 'MANAGER' and updated_user.role == 'ADMIN':
                messages.error(request, "Managers cannot assign Admin role.")
                return redirect("user_management")

            # Admin-only password reset
            if role == "ADMIN":
                new_password1 = form.cleaned_data.get("new_password1")
                new_password2 = form.cleaned_data.get("new_password2")
                if new_password1 or new_password2:
                    if new_password1 == new_password2:
                        updated_user.set_password(new_password1)
                        messages.success(request, f"Password for {updated_user.username} updated successfully.")
                    else:
                        password_error = "New passwords do not match."
                        return render(request, "users/user_form.html", {
                            "form": form,
                            "title": "Edit User",
                            "password_error": password_error,
                        })

            updated_user.save()
            form.save_m2m()  # ✅ handles warehouses automatically

            messages.success(request, "User updated successfully.")
            return redirect("user_management")
    else:
        form = UserUpdateForm(instance=target_user)

    return render(request, "users/user_form.html", {
        "form": form,
        "title": "Edit User",
        "password_error": password_error,
    })


@login_required
def user_delete(request, pk):
    target_user = get_object_or_404(User, pk=pk)
    role = getattr(request.user, "role", None)

    if role not in ['ADMIN', 'MANAGER']:
        messages.error(request, "You do not have permission to delete users.")
        return redirect("user_management")

    if request.method == "POST":
        target_user.delete()
        messages.success(request, "User deleted successfully.")
        return redirect("user_management")
    return render(request, "users/user_confirm_delete.html", {"user": target_user})

@login_required
def user_toggle_active(request, pk):
    target_user = get_object_or_404(User, pk=pk)
    role = getattr(request.user, "role", None)

    if role not in ['ADMIN', 'MANAGER']:
        messages.error(request, "You do not have permission to change user status.")
        return redirect("user_management")

    target_user.is_active = not target_user.is_active
    target_user.save()
    messages.info(request, f"User {target_user.username} is now {'active' if target_user.is_active else 'inactive'}.")
    return redirect("user_management")

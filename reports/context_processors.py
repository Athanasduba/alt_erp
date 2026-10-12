from customers.models import Customer
from motorcycles.models import Motorcycle

def reports_context(request):
    # Only load if user is authenticated (avoid errors on login page)
    if request.user.is_authenticated:
        customers = Customer.objects.all()
        motorcycles = Motorcycle.objects.all()
    else:
        customers = []
        motorcycles = []

    return {
        "customers": customers,
        "motorcycles": motorcycles,
    }

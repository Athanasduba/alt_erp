def role_flags(request):
    """
    Adds role-based flags to all templates based on User.role field.
    """
    flags = {
        "is_admin": False,
        "is_manager": False,
        "is_officer": False,
        "is_store": False,
        "is_accountant": False,
        "is_agent": False,
        "is_sales": False,
        "is_care": False,
    }

    if request.user.is_authenticated and hasattr(request.user, "role"):
        role = request.user.role.upper()

        if role == "ADMIN":
            flags["is_admin"] = True
        elif role == "MANAGER":
            flags["is_manager"] = True
        elif role == "OFFICER":
            flags["is_officer"] = True
        elif role == "STORE":
            flags["is_store"] = True
        elif role == "ACCOUNTANT":
            flags["is_accountant"] = True
        elif role == "AGENT":
            flags["is_agent"] = True
        elif role == "SALES":
            flags["is_sales"] = True
        elif role == "CARE":
            flags["is_care"] = True

    return flags

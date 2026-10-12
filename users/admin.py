from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.core.exceptions import ValidationError
from .models import User

@admin.register(User)
class CustomUserAdmin(BaseUserAdmin):
    list_display = (
        'username', 'full_name', 'email', 'phone_number',
        'role', 'is_active', 'is_verified', 'date_joined'
    )
    list_filter = ('role', 'is_active', 'is_verified')
    search_fields = ('username', 'first_name', 'last_name', 'email', 'phone_number')
    filter_horizontal = ('warehouses', 'groups', 'user_permissions')

    fieldsets = (
        (None, {'fields': ('username', 'password')}),
        ('Personal info', {'fields': ('first_name', 'last_name', 'email', 'phone_number')}),
        ('Role & Warehouses', {'fields': ('role', 'warehouses')}),
        ('Permissions', {
            'fields': (
                'is_active', 'is_staff', 'is_superuser',
                'is_verified', 'groups', 'user_permissions'
            )
        }),
        ('Important dates', {'fields': ('last_login', 'date_joined')}),
    )

    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': (
                'username', 'email', 'first_name', 'last_name',
                'phone_number', 'role', 'password1', 'password2'
            ),
        }),
    )

    def delete_model(self, request, obj):
        # Prevent deletion of any Admin user
        if obj.role == 'ADMIN':
            raise ValidationError("Admin accounts cannot be deleted.")
        super().delete_model(request, obj)

    def save_model(self, request, obj, form, change):
        # Prevent deactivation of Admin accounts
        if obj.role == 'ADMIN' and not obj.is_active:
            raise ValidationError("Admin accounts cannot be deactivated.")
        super().save_model(request, obj, form, change)

"""Expose marketplace user fields in Django's built-in staff admin."""

from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin

from .models import User


@admin.register(User)
class UserAdmin(DjangoUserAdmin):
    """Extend Django's familiar user admin with role and marketplace profile data."""

    # These columns make role, verification, and suspension status easy to scan.
    list_display = (
        "username",
        "email",
        "role",
        "shop_name",
        "is_verified",
        "is_active",
        "is_staff",
    )
    # Filters help staff isolate sellers, admins, suspended users, or verified users.
    list_filter = DjangoUserAdmin.list_filter + ("role", "is_verified")
    # Add marketplace fields to the normal edit form without removing auth controls.
    fieldsets = DjangoUserAdmin.fieldsets + (
        (
            "Marketplace profile",
            {
                "fields": (
                    "role",
                    "phone_number",
                    "shop_name",
                    "profile_picture",
                    "is_verified",
                )
            },
        ),
    )
    # These fields also appear when staff create a new user in Django admin.
    add_fieldsets = DjangoUserAdmin.add_fieldsets + (
        (
            "Marketplace profile",
            {
                "fields": (
                    "email",
                    "role",
                    "phone_number",
                    "shop_name",
                    "profile_picture",
                    "is_verified",
                )
            },
        ),
    )

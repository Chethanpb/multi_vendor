"""Name all authentication routes for safe reverse URL lookups."""

from django.urls import path

from . import views


# Namespacing prevents a login route in another app from causing ambiguity.
app_name = "accounts"

# Registration is role-specific, while login and logout are shared by all roles.
urlpatterns = [
    path("register/buyer/", views.buyer_register, name="buyer_register"),
    path("register/seller/", views.seller_register, name="seller_register"),
    path("login/", views.login_view, name="login"),
    path("logout/", views.logout_view, name="logout"),
    path("redirect/", views.role_redirect, name="role_redirect"),
]

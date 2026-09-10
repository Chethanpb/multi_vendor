"""Name custom admin analytics, moderation, and account-management routes."""

from django.urls import path

from . import views


# Namespacing separates custom marketplace admin URLs from Django's /admin/ site.
app_name = "adminpanel"

# Every route checks role='admin'; all mutations additionally require POST.
urlpatterns = [
    path("dashboard/", views.dashboard, name="dashboard"),
    path("products/", views.product_list, name="product_list"),
    path(
        "products/<int:product_id>/deactivate/",
        views.deactivate_product,
        name="deactivate_product",
    ),
    path(
        "products/<int:product_id>/reactivate/",
        views.reactivate_product,
        name="reactivate_product",
    ),
    path("users/", views.user_list, name="user_list"),
    path("users/<int:user_id>/suspend/", views.suspend_user, name="suspend_user"),
    path(
        "users/<int:user_id>/reactivate/",
        views.reactivate_user,
        name="reactivate_user",
    ),
]

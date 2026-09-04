"""Route public catalog pages and the protected seller inventory workspace."""

from django.urls import path

from . import views


# Namespaced URLs make product links explicit in templates and redirects.
app_name = "products"

# The first group is public; every seller route is protected again inside its view.
urlpatterns = [
    path("", views.product_list, name="home"),
    path("products/", views.product_list, name="product_list"),
    path("products/<int:product_id>/", views.product_detail, name="product_detail"),
    path("seller/dashboard/", views.seller_dashboard, name="seller_dashboard"),
    path("seller/products/", views.seller_product_list, name="seller_product_list"),
    path(
        "seller/products/add/",
        views.seller_product_create,
        name="seller_product_create",
    ),
    path(
        "seller/products/<int:product_id>/edit/",
        views.seller_product_update,
        name="seller_product_update",
    ),
    path(
        "seller/products/<int:product_id>/delete/",
        views.seller_product_delete,
        name="seller_product_delete",
    ),
    path(
        "seller/products/<int:product_id>/reactivate/",
        views.seller_product_reactivate,
        name="seller_product_reactivate",
    ),
]

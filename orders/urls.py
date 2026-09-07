from django.urls import path
from . import views
urlpatterns = [
    path()
]
"""Name cart, checkout, buyer order, and seller fulfillment routes."""

from django.urls import path

from . import views


# Namespacing keeps order links distinct from payment and tracking endpoints.
app_name = "orders"

# State-changing cart endpoints accept POST only in their decorated views.
urlpatterns = [
    path("cart/", views.cart_detail, name="cart_detail"),
    path("cart/add/<int:product_id>/", views.add_to_cart, name="add_to_cart"),
    path(
        "cart/item/<int:item_id>/update/",
        views.update_cart_item,
        name="update_cart_item",
    ),
    path(
        "cart/item/<int:item_id>/remove/",
        views.remove_cart_item,
        name="remove_cart_item",
    ),
    path("checkout/", views.checkout_review, name="checkout_review"),
    path("orders/", views.buyer_order_list, name="buyer_order_list"),
    path(
        "orders/<int:order_id>/",
        views.buyer_order_detail,
        name="buyer_order_detail",
    ),
    path("seller/orders/", views.seller_order_list, name="seller_order_list"),
]

"""Name buyer tracking lookup/timeline and seller update routes."""

from django.urls import path

from . import views


# Namespacing makes tracking links unambiguous across buyer and seller templates.
app_name = "tracking"

# Every route is authenticated and role-protected inside its corresponding view.
urlpatterns = [
    path("track/", views.track_lookup, name="track_lookup"),
    path("track/<int:order_id>/", views.track_order, name="track_order"),
    path(
        "seller/orders/<int:order_id>/tracking/",
        views.seller_update_shipment,
        name="seller_update_shipment",
    ),
]

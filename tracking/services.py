"""Enforce ordered manual tracking transitions and synchronize order status."""

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction

from orders.models import Order

from .models import Shipment, TrackingHistory


# Explicit transition rules prevent impossible backward or post-delivery changes.
ALLOWED_STATUS_TRANSITIONS = {
    Shipment.Status.PACKED: (
        Shipment.Status.SHIPPED,
        Shipment.Status.CANCELLED,
    ),
    Shipment.Status.SHIPPED: (
        Shipment.Status.OUT_FOR_DELIVERY,
        Shipment.Status.CANCELLED,
    ),
    Shipment.Status.OUT_FOR_DELIVERY: (
        Shipment.Status.DELIVERED,
        Shipment.Status.CANCELLED,
    ),
    Shipment.Status.DELIVERED: (),
    Shipment.Status.CANCELLED: (),
}


def get_allowed_next_statuses(current_status):
    """Return the legal next manual choices for one current shipment state."""

    # Unknown status values safely produce no transitions rather than broad access.
    return ALLOWED_STATUS_TRANSITIONS.get(current_status, ())


def _order_status_for_shipment_status(shipment_status):
    """Map detailed tracking milestones onto the broader Order status choices."""

    status_mapping = {
        Shipment.Status.PACKED: Order.Status.PROCESSING,
        Shipment.Status.SHIPPED: Order.Status.SHIPPED,
        Shipment.Status.OUT_FOR_DELIVERY: Order.Status.SHIPPED,
        Shipment.Status.DELIVERED: Order.Status.DELIVERED,
        Shipment.Status.CANCELLED: Order.Status.CANCELLED,
    }
    return status_mapping[shipment_status]


@transaction.atomic
def update_shipment_status(shipment_id, seller, new_status):
    """Authorize a seller, advance a locked shipment, and append its history row."""

    # Locking makes simultaneous seller updates serialize for multi-vendor orders.
    shipment = (
        Shipment.objects.select_for_update().select_related("order").get(pk=shipment_id)
    )
    seller_participates = shipment.order.items.filter(seller=seller).exists()

    if not seller_participates:
        # Service-level authorization protects callers beyond the current web view.
        raise PermissionDenied("You do not fulfill any product in this order.")

    allowed_statuses = get_allowed_next_statuses(shipment.current_status)

    if new_status not in allowed_statuses:
        # A crafted POST cannot skip, reverse, or change a terminal milestone.
        raise ValidationError(
            f"Cannot move from {shipment.get_current_status_display()} to that status."
        )

    shipment.current_status = new_status
    # The authenticated session, not a hidden form field, supplies attribution.
    shipment.updated_by = seller
    shipment.full_clean()
    shipment.save(update_fields=("current_status", "updated_by", "last_updated_at"))
    TrackingHistory.objects.create(
        shipment=shipment,
        status=new_status,
        changed_by=seller,
        note=f"Status updated manually by {seller.shop_name or seller.username}.",
    )
    # Keep the broader order badge aligned with its more detailed tracking state.
    shipment.order.status = _order_status_for_shipment_status(new_status)
    shipment.order.save(update_fields=("status", "updated_at"))
    return shipment

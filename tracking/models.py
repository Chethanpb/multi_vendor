"""Define one shipment per order and an append-only manual status history."""

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models

from orders.models import Order


class Shipment(models.Model):
    """Store the latest manually controlled fulfillment status for an order."""

    class Status(models.TextChoices):
        """List the supported manual fulfillment milestones."""

        # Stripe confirmation creates every new shipment at this first milestone.
        PACKED = "packed", "Packed"
        # A seller uses this after handing the package to its delivery process.
        SHIPPED = "shipped", "Shipped"
        # A seller uses this when the package is on its final delivery route.
        OUT_FOR_DELIVERY = "out_for_delivery", "Out for Delivery"
        # This terminal status records successful delivery to the buyer.
        DELIVERED = "delivered", "Delivered"
        # This terminal status records stopped fulfillment without implying a refund.
        CANCELLED = "cancelled", "Cancelled"

    # OneToOne matches the requested single shipment tracker per marketplace order.
    order = models.OneToOneField(
        Order,
        on_delete=models.CASCADE,
        related_name="shipment",
        help_text="Paid order whose manual fulfillment state is tracked here.",
    )
    # A database index speeds seller queues and buyer status filtering.
    current_status = models.CharField(
        max_length=24,
        choices=Status.choices,
        default=Status.PACKED,
        db_index=True,
        help_text="Most recent seller-controlled shipment milestone.",
    )
    # NULL represents Stripe's automatic initial Packed state before a seller acts.
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="shipment_updates",
        null=True,
        blank=True,
        help_text="Seller who made the latest manual status change.",
    )
    # auto_now records the exact time of each latest-state save.
    last_updated_at = models.DateTimeField(
        auto_now=True,
        help_text="Timestamp of the most recent shipment status update.",
    )
    # Creation time remains stable even after many tracking updates.
    created_at = models.DateTimeField(
        auto_now_add=True,
        help_text="Timestamp when successful payment created the shipment.",
    )

    class Meta:
        """Show recently changed shipments first to staff users."""

        # Urgent, newly changed shipments appear at the top of support lists.
        ordering = ("-last_updated_at",)

    def clean(self):
        """Ensure a manual updater is a seller participating in this order."""

        # Keep standard Django model validation before relationship rules.
        super().clean()

        if not self.updated_by_id:
            # The payment webhook is intentionally allowed to create system state.
            return

        if self.updated_by.role != "seller":
            # Buyers and admins cannot impersonate a fulfillment update source.
            raise ValidationError({"updated_by": "Shipment updates require a seller."})

        if (
            self.order_id
            and not self.order.items.filter(seller_id=self.updated_by_id).exists()
        ):
            # A seller can update only an order containing at least one owned line.
            raise ValidationError(
                {"updated_by": "Seller does not fulfill any item in this order."}
            )

    def __str__(self):
        """Return order and latest milestone for staff interfaces."""

        return (
            f"Shipment for order #{self.order_id} — {self.get_current_status_display()}"
        )


class TrackingHistory(models.Model):
    """Keep an append-only timestamped record of every shipment state change."""

    # CASCADE removes history only if its parent order/shipment is removed.
    shipment = models.ForeignKey(
        Shipment,
        on_delete=models.CASCADE,
        related_name="history",
        help_text="Shipment whose status changed at this point in time.",
    )
    # Store the snapshot status instead of deriving it from current shipment state.
    status = models.CharField(
        max_length=24,
        choices=Shipment.Status.choices,
        help_text="Shipment milestone recorded by this history entry.",
    )
    # NULL identifies the automatic Packed event created by the payment webhook.
    changed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="tracking_history_changes",
        null=True,
        blank=True,
        help_text="Seller who made this change, or blank for the payment system.",
    )
    # auto_now_add makes this timestamp immutable after the log row is created.
    changed_at = models.DateTimeField(
        auto_now_add=True,
        help_text="Exact timestamp when this status was appended to history.",
    )
    # A note explains automatic events and can support future seller comments.
    note = models.CharField(
        max_length=255,
        blank=True,
        help_text="Optional short explanation of the status change.",
    )

    class Meta:
        """Display shipment history chronologically as a natural timeline."""

        # Oldest-first ordering reads from Packed toward the latest state.
        ordering = ("changed_at", "id")
        # The plural label avoids Django's default 'Tracking historys' text.
        verbose_name_plural = "tracking history"

    def clean(self):
        """Validate that any named updater is a participating seller."""

        # Retain the standard field-level validation before relationship checks.
        super().clean()

        if self.changed_by_id and self.changed_by.role != "seller":
            # Manual history attribution is reserved for seller accounts.
            raise ValidationError({"changed_by": "Tracking changes require a seller."})

        if (
            self.changed_by_id
            and self.shipment_id
            and not self.shipment.order.items.filter(
                seller_id=self.changed_by_id
            ).exists()
        ):
            # History attribution must match a seller who owns an order line.
            raise ValidationError(
                {"changed_by": "Seller does not fulfill any item in this order."}
            )

    def __str__(self):
        """Return a concise status and timestamp description for staff."""

        return f"{self.get_status_display()} for order #{self.shipment.order_id}"

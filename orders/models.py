"""Define buyer carts, immutable order snapshots, and seller order lines."""

from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import models

from products.models import Product


class Cart(models.Model):
    """Hold one buyer's not-yet-purchased product selections."""

    # OneToOne guarantees each buyer has at most one active marketplace cart.
    buyer = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="cart",
        help_text="Buyer account that owns this private shopping cart.",
    )
    # Creation time helps support staff understand when a cart first appeared.
    created_at = models.DateTimeField(
        auto_now_add=True,
        help_text="Timestamp recorded when the cart was first created.",
    )
    # Updates identify active or abandoned carts without tracking every click.
    updated_at = models.DateTimeField(
        auto_now=True,
        help_text="Timestamp refreshed whenever the cart record is saved.",
    )

    def clean(self):
        """Ensure only buyer accounts can own shopping carts."""

        # Retain any validation supplied by Django's base model implementation.
        super().clean()

        if self.buyer_id and self.buyer.role != "buyer":
            # Sellers and admins have separate workspaces and cannot place orders.
            raise ValidationError({"buyer": "Only buyer accounts can own carts."})

    @property
    def total_amount(self):
        """Calculate the current cart total from live product prices."""

        # Python Decimal addition stays exact and is clear for a small cart.
        return sum(
            (item.subtotal for item in self.items.select_related("product")),
            Decimal("0.00"),
        )

    @property
    def total_quantity(self):
        """Return the number of product units rather than distinct rows."""

        # A database SUM avoids loading every CartItem merely for the navigation badge.
        aggregate = self.items.aggregate(total=models.Sum("quantity"))
        return aggregate["total"] or 0

    def __str__(self):
        """Identify the cart by its buyer in staff interfaces."""

        return f"Cart for {self.buyer.username}"


class CartItem(models.Model):
    """Store one product and requested quantity inside a buyer cart."""

    # CASCADE removes line items when their short-lived parent cart is removed.
    cart = models.ForeignKey(
        Cart,
        on_delete=models.CASCADE,
        related_name="items",
        help_text="Private buyer cart containing this line.",
    )
    # PROTECT avoids a seller deleting an item while a buyer is considering it.
    product = models.ForeignKey(
        Product,
        on_delete=models.PROTECT,
        related_name="cart_items",
        help_text="Live catalog product selected by the buyer.",
    )
    # At least one unit is required; stock availability is validated separately.
    quantity = models.PositiveIntegerField(
        validators=[MinValueValidator(1)],
        help_text="Number of units the buyer wants to purchase.",
    )

    class Meta:
        """Prevent duplicate product rows inside the same cart."""

        # A database constraint protects against duplicate rows during concurrent clicks.
        constraints = [
            models.UniqueConstraint(
                fields=("cart", "product"),
                name="unique_product_per_cart",
            )
        ]
        # Stable ordering makes cart display and tests predictable.
        ordering = ("id",)

    def clean(self):
        """Reject inactive products and quantities greater than current stock."""

        # Run field and parent validation before cross-field business rules.
        super().clean()

        if not self.product_id:
            # ModelForm may validate before server code assigns the product.
            return

        if not self.product.is_active:
            # Deactivated or moderated inventory must not remain purchasable.
            raise ValidationError({"product": "This product is no longer available."})

        if self.quantity is not None and self.quantity > self.product.stock:
            # Stock is checked again under a database lock during checkout.
            raise ValidationError(
                {"quantity": f"Only {self.product.stock} unit(s) are available."}
            )

    @property
    def subtotal(self):
        """Calculate this cart line using the product's current catalog price."""

        return self.product.price * self.quantity

    def __str__(self):
        """Show quantity and product when staff inspect a cart line."""

        return f"{self.quantity} × {self.product.name}"


class Order(models.Model):
    """Represent one buyer checkout containing products from one or more sellers."""

    class Status(models.TextChoices):
        """Describe payment and fulfillment stages visible across the platform."""

        # The stock is reserved but Stripe has not confirmed payment yet.
        PENDING_PAYMENT = "pending_payment", "Pending payment"
        # Stripe confirmed the payment and a packed shipment now exists.
        PAID = "paid", "Paid"
        # A seller has begun active fulfillment work.
        PROCESSING = "processing", "Processing"
        # Manual tracking indicates that the package has left the seller.
        SHIPPED = "shipped", "Shipped"
        # Manual tracking indicates successful buyer delivery.
        DELIVERED = "delivered", "Delivered"
        # The checkout or fulfillment was intentionally cancelled.
        CANCELLED = "cancelled", "Cancelled"
        # Stripe reported a payment failure rather than a user cancellation.
        PAYMENT_FAILED = "payment_failed", "Payment failed"

    # PROTECT preserves the buyer identity attached to financial history.
    buyer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="orders",
        help_text="Buyer account that submitted and owns this order.",
    )
    # This frozen total must match Stripe and never uses later catalog prices.
    total_amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        validators=[MinValueValidator(Decimal("0.01"))],
        help_text="Snapshot total reserved and sent to Stripe at checkout.",
    )
    # A database index speeds buyer history and seller fulfillment filters.
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING_PAYMENT,
        db_index=True,
        help_text="Current combined payment and fulfillment state.",
    )
    # auto_now_add gives each order a stable audit timestamp.
    created_at = models.DateTimeField(
        auto_now_add=True,
        db_index=True,
        help_text="Timestamp recorded when checkout reserved the inventory.",
    )
    # Status changes refresh this timestamp for simple activity sorting.
    updated_at = models.DateTimeField(
        auto_now=True,
        help_text="Timestamp refreshed whenever the order record changes.",
    )

    class Meta:
        """Show newest orders first in buyer, seller, and staff interfaces."""

        # Descending creation time surfaces the most urgent work first.
        ordering = ("-created_at",)

    def clean(self):
        """Ensure only buyer accounts can own marketplace orders."""

        # Preserve any validation inherited from Django's base Model.
        super().clean()

        if self.buyer_id and self.buyer.role != "buyer":
            # Financial records must never be assigned to a seller or administrator.
            raise ValidationError({"buyer": "Only buyer accounts can place orders."})

    @property
    def item_count(self):
        """Return the number of units across every immutable order line."""

        aggregate = self.items.aggregate(total=models.Sum("quantity"))
        return aggregate["total"] or 0

    def __str__(self):
        """Return a compact order reference used throughout the user interface."""

        return f"Order #{self.pk} for {self.buyer.username}"


class OrderItem(models.Model):
    """Freeze product, seller, quantity, and price details at checkout time."""

    # CASCADE removes snapshots only if their owning order is deliberately removed.
    order = models.ForeignKey(
        Order,
        on_delete=models.CASCADE,
        related_name="items",
        help_text="Order that owns this immutable purchase line.",
    )
    # PROTECT preserves the product identity in historical purchases.
    product = models.ForeignKey(
        Product,
        on_delete=models.PROTECT,
        related_name="order_items",
        help_text="Catalog product purchased on this line.",
    )
    # PROTECT preserves which seller received this line even if an account closes.
    seller = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="sold_order_items",
        help_text="Seller responsible for fulfilling this specific line.",
    )
    # Quantity is frozen once checkout begins and must be at least one.
    quantity = models.PositiveIntegerField(
        validators=[MinValueValidator(1)],
        help_text="Number of units purchased at checkout.",
    )
    # Snapshot pricing protects historical totals from later product edits.
    price_at_purchase = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(Decimal("0.01"))],
        help_text="Unit price copied from the product during checkout.",
    )

    class Meta:
        """Keep order lines in their original creation order."""

        # Primary-key ordering is stable and easy for new Django developers to follow.
        ordering = ("id",)

    def clean(self):
        """Ensure the immutable seller snapshot matches the product owner."""

        # Run standard model validation before checking related-object consistency.
        super().clean()

        if (
            self.product_id
            and self.seller_id
            and self.product.seller_id != self.seller_id
        ):
            # A mismatched seller would send revenue and fulfillment to the wrong shop.
            raise ValidationError({"seller": "Seller must match the product owner."})

    @property
    def line_total(self):
        """Calculate this immutable order line from its snapshot values."""

        return self.price_at_purchase * self.quantity

    def __str__(self):
        """Return a readable line description for logs and staff screens."""

        return f"{self.quantity} × {self.product.name} on order #{self.order_id}"

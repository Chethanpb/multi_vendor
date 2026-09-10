"""Define an audit log for administrator product deactivation decisions."""

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models

from products.models import Product


class ProductRemovalLog(models.Model):
    """Record who deactivated a product, why, and when the action occurred."""

    # PROTECT preserves the product referenced by the moderation audit trail.
    product = models.ForeignKey(
        Product,
        on_delete=models.PROTECT,
        related_name="removal_logs",
        help_text="Product hidden from buyers by this moderation action.",
    )
    # PROTECT preserves administrator attribution even if accounts are reorganized.
    removed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="product_removal_actions",
        help_text="Marketplace administrator who performed the deactivation.",
    )
    # A required text reason makes each moderation decision explainable.
    reason = models.TextField(
        help_text="Required explanation for deactivating this seller product.",
    )
    # auto_now_add gives the audit action an immutable original timestamp.
    removed_at = models.DateTimeField(
        auto_now_add=True,
        db_index=True,
        help_text="Timestamp recorded when the administrator removed the product.",
    )

    class Meta:
        """Show newest moderation actions first in staff interfaces."""

        # Recent actions are normally the most relevant for review or appeal.
        ordering = ("-removed_at",)

    def clean(self):
        """Ensure only an explicit marketplace admin is credited with removal."""

        # Preserve Django's normal field-level model validation.
        super().clean()

        if self.removed_by_id and self.removed_by.role != "admin":
            # Seller and buyer accounts cannot be recorded as marketplace moderators.
            raise ValidationError(
                {"removed_by": "Only marketplace administrators remove products."}
            )

    def __str__(self):
        """Return product and administrator for readable audit records."""

        return f"{self.product.name} removed by {self.removed_by.username}"

"""Expose product-removal audit records in Django's built-in admin."""

from django.contrib import admin

from .models import ProductRemovalLog


@admin.register(ProductRemovalLog)
class ProductRemovalLogAdmin(admin.ModelAdmin):
    """Present moderation logs as read-only audit evidence."""

    # Product, administrator, reason, and time summarize each action.
    list_display = ("product", "removed_by", "short_reason", "removed_at")
    # Date and administrator filters assist moderation reviews.
    list_filter = ("removed_at", "removed_by")
    # Search matches product names, seller shops, and explanation text.
    search_fields = ("product__name", "product__seller__shop_name", "reason")
    # Related objects are joined once for efficient audit-list rendering.
    list_select_related = ("product", "product__seller", "removed_by")
    # Audit records must not be altered after they are written.
    readonly_fields = ("product", "removed_by", "reason", "removed_at")

    @admin.display(description="Reason")
    def short_reason(self, removal_log):
        """Return a compact reason preview without hiding the full detail page."""

        # Truncate visually while preserving the complete immutable database value.
        return (
            removal_log.reason
            if len(removal_log.reason) <= 80
            else f"{removal_log.reason[:77]}..."
        )

    def has_add_permission(self, request):
        """Prevent manual log creation outside the custom moderation workflow."""

        return False

    def has_change_permission(self, request, obj=None):
        """Keep saved moderation evidence immutable in Django admin."""

        return False

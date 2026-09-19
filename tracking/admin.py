"""Expose current shipments and append-only history through Django admin."""

from django.contrib import admin

from .models import Shipment, TrackingHistory


class TrackingHistoryInline(admin.TabularInline):
    """Show timestamped shipment events directly under the current shipment."""

    # Inline rows come from TrackingHistory's shipment foreign key.
    model = TrackingHistory
    # History is audit data and should not be edited through the normal admin form.
    readonly_fields = ("status", "changed_by", "changed_at", "note")
    # Do not display an unused blank history row.
    extra = 0
    # Prevent staff from deleting individual audit entries while leaving the shipment.
    can_delete = False


@admin.register(Shipment)
class ShipmentAdmin(admin.ModelAdmin):
    """Provide support staff a searchable view of current fulfillment state."""

    # These columns identify the order, status, updater, and last activity.
    list_display = ("order", "current_status", "updated_by", "last_updated_at")
    # Status and date filters help locate delayed or cancelled shipments.
    list_filter = ("current_status", "last_updated_at")
    # Exact order ID and buyer details connect support reports to records.
    search_fields = ("=order__id", "order__buyer__username", "order__buyer__email")
    # Related rows are joined once for efficient staff-list rendering.
    list_select_related = ("order", "order__buyer", "updated_by")
    # Tracking changes should use the seller workflow, so admin fields are read-only.
    readonly_fields = (
        "order",
        "current_status",
        "updated_by",
        "created_at",
        "last_updated_at",
    )
    # The inline gives staff the full history without a second navigation step.
    inlines = (TrackingHistoryInline,)

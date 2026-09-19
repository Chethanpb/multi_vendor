"""Serve buyer-owned tracking timelines and seller-authorized status updates."""

from django.contrib import messages
from django.core.exceptions import ValidationError
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_http_methods

from accounts.decorators import buyer_required, seller_required
from orders.models import Order

from .forms import ShipmentStatusForm, TrackOrderLookupForm
from .models import Shipment
from .services import update_shipment_status


@buyer_required
@require_http_methods(["GET", "POST"])
def track_lookup(request):
    """Accept an order ID and redirect only when the signed-in buyer owns it."""

    # GET can prefill from a query string; POST performs the actual redirect lookup.
    form_data = request.POST if request.method == "POST" else request.GET or None
    form = TrackOrderLookupForm(form_data)

    if request.method == "POST" and form.is_valid():
        order_id = form.cleaned_data["order_id"]
        order_exists = Order.objects.filter(pk=order_id, buyer=request.user).exists()

        if order_exists:
            # The next view repeats ownership checking as defense in depth.
            return redirect("tracking:track_order", order_id=order_id)

        # Use the same message for absent and foreign IDs to avoid information leaks.
        form.add_error("order_id", "No order with that ID belongs to your account.")

    return render(request, "tracking/track_lookup.html", {"form": form})


@buyer_required
def track_order(request, order_id):
    """Show a milestone timeline only for an order owned by the signed-in buyer."""

    # select_related fetches the optional OneToOne shipment in the same query.
    order = get_object_or_404(
        Order.objects.select_related("shipment").prefetch_related(
            "items__product", "items__seller"
        ),
        pk=order_id,
        buyer=request.user,
    )
    shipment = getattr(order, "shipment", None)
    milestones = []
    cancellation_history = None

    if shipment:
        # Chronological model ordering produces an accurate append-only audit trail.
        history_entries = list(shipment.history.select_related("changed_by"))
        history_by_status = {entry.status: entry for entry in history_entries}
        milestone_statuses = (
            Shipment.Status.PACKED,
            Shipment.Status.SHIPPED,
            Shipment.Status.OUT_FOR_DELIVERY,
            Shipment.Status.DELIVERED,
        )
        labels_by_status = dict(Shipment.Status.choices)

        for status in milestone_statuses:
            # A history row, not numeric guessing, decides whether a step completed.
            history_entry = history_by_status.get(status)
            milestones.append(
                {
                    "status": status,
                    "label": labels_by_status[status],
                    "is_complete": history_entry is not None,
                    "history": history_entry,
                }
            )

        cancellation_history = history_by_status.get(Shipment.Status.CANCELLED)

    context = {
        "order": order,
        "shipment": shipment,
        "milestones": milestones,
        "cancellation_history": cancellation_history,
    }
    return render(request, "tracking/track_order.html", context)


@seller_required
@require_http_methods(["GET", "POST"])
def seller_update_shipment(request, order_id):
    """Let a participating seller advance the shared order shipment manually."""

    # The order-item relationship enforces seller participation at query time.
    shipment = get_object_or_404(
        Shipment.objects.select_related("order", "updated_by")
        .filter(
            order_id=order_id,
            order__items__seller=request.user,
        )
        .distinct()
    )
    form = ShipmentStatusForm(request.POST or None, instance=shipment)

    if request.method == "POST" and form.is_valid():
        new_status = form.cleaned_data["current_status"]

        try:
            # The service locks and rechecks authorization and transition validity.
            updated_shipment = update_shipment_status(
                shipment.pk,
                request.user,
                new_status,
            )
        except ValidationError as validation_error:
            # A concurrent update may make a formerly valid choice stale.
            form.add_error(None, validation_error.messages[0])
        else:
            messages.success(
                request,
                f"Order #{order_id} is now "
                f"{updated_shipment.get_current_status_display()}.",
            )
            return redirect("orders:seller_order_list")

    # Terminal states have an empty choice list and are rendered as read-only history.
    history_entries = shipment.history.select_related("changed_by")
    context = {
        "shipment": shipment,
        "form": form,
        "history_entries": history_entries,
        "has_next_status": bool(form.fields["current_status"].choices),
    }
    return render(request, "tracking/seller_update_shipment.html", context)

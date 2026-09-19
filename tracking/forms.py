"""Validate buyer tracking lookups and seller shipment transition choices."""

from django import forms

from .models import Shipment
from .services import get_allowed_next_statuses


class TrackOrderLookupForm(forms.Form):
    """Validate a numeric order reference before an ownership-aware lookup."""

    # Positive integers match Django's default order primary key behavior.
    order_id = forms.IntegerField(
        min_value=1,
        label="Order ID",
        widget=forms.NumberInput(
            attrs={
                "class": "form-control form-control-lg",
                "placeholder": "For example, 1042",
            }
        ),
    )


class ShipmentStatusForm(forms.ModelForm):
    """Offer only valid next states for a seller-controlled shipment."""

    class Meta:
        """Limit editing to current_status; updater identity is server-controlled."""

        # updated_by and order must never come from submitted browser values.
        model = Shipment
        fields = ("current_status",)
        widgets = {
            "current_status": forms.Select(
                attrs={"class": "form-select form-select-lg"}
            )
        }

    def __init__(self, *args, **kwargs):
        """Replace all status choices with transitions allowed from this instance."""

        # ModelForm binds POST data and the existing Shipment before choice filtering.
        super().__init__(*args, **kwargs)

        if self.instance and self.instance.pk:
            # Restricting choices gives both friendly UI and server-side validation.
            allowed_statuses = get_allowed_next_statuses(self.instance.current_status)
            status_labels = dict(Shipment.Status.choices)
            self.fields["current_status"].choices = [
                (status, status_labels[status]) for status in allowed_statuses
            ]

"""Validate cart quantity changes before order and stock services use them."""

from django import forms


class CartQuantityForm(forms.Form):
    """Validate a requested cart quantity against a specific product's stock."""

    # IntegerField rejects decimals, text, zero, and negative quantities.
    quantity = forms.IntegerField(
        min_value=1,
        widget=forms.NumberInput(attrs={"class": "form-control", "min": "1"}),
    )

    def __init__(self, product, *args, **kwargs):
        """Set the maximum accepted quantity from the server-loaded product."""

        # The calling view must supply a product fetched from the database.
        self.product = product
        # Django creates the declared quantity field during parent initialization.
        super().__init__(*args, **kwargs)
        # max_value performs server validation; the HTML max improves usability only.
        self.fields["quantity"].max_value = product.stock
        self.fields["quantity"].widget.attrs["max"] = str(product.stock)

    def clean_quantity(self):
        """Reject quantities for inactive products even if stock remains positive."""

        quantity = self.cleaned_data["quantity"]

        if not self.product.is_active:
            # Moderated or seller-deactivated inventory cannot be newly purchased.
            raise forms.ValidationError("This product is no longer available.")

        return quantity

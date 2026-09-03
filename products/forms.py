"""Provide seller product forms and validated buyer catalog filters."""

from django import forms

from .models import Category, Product


class ProductForm(forms.ModelForm):
    """Let a seller edit safe product fields while ownership stays server-controlled."""

    class Meta:
        """Declare the Product fields a seller is allowed to submit."""

        # seller and is_active are deliberately absent to prevent ownership abuse.
        model = Product
        fields = ("category", "name", "description", "price", "stock", "image")
        # A larger text area makes detailed descriptions comfortable to edit.
        widgets = {
            "description": forms.Textarea(attrs={"rows": 6}),
            "price": forms.NumberInput(attrs={"step": "0.01", "min": "0.01"}),
            "stock": forms.NumberInput(attrs={"min": "0"}),
        }

    def __init__(self, *args, **kwargs):
        """Apply accessible Bootstrap styling to each seller-editable field."""

        # ModelForm still performs all model validators after adding CSS classes.
        super().__init__(*args, **kwargs)

        for field in self.fields.values():
            # Selects use form-select; all other widgets use form-control.
            css_class = (
                "form-select"
                if isinstance(field.widget, forms.Select)
                else "form-control"
            )
            field.widget.attrs["class"] = css_class

    def clean_image(self):
        """Reject unexpectedly large images before they consume server storage."""

        # cleaned_data may contain an existing ImageFieldFile during product edits.
        image = self.cleaned_data.get("image")

        if image and hasattr(image, "size") and image.size > 5 * 1024 * 1024:
            # Five MiB is generous for a web catalog while limiting abuse.
            raise forms.ValidationError("Product images must be 5 MB or smaller.")

        return image


class ProductFilterForm(forms.Form):
    """Validate search and price filters before values reach an ORM query."""

    # Search is free text and optional; the view applies it to several safe fields.
    query = forms.CharField(
        required=False,
        max_length=120,
        label="Search",
        widget=forms.TextInput(
            attrs={"class": "form-control", "placeholder": "Search products or shops"}
        ),
    )
    # ModelChoiceField prevents invented category identifiers from being trusted.
    category = forms.ModelChoiceField(
        queryset=Category.objects.all(),
        required=False,
        empty_label="All categories",
        widget=forms.Select(attrs={"class": "form-select"}),
    )
    # DecimalField rejects malformed values before the database comparison occurs.
    min_price = forms.DecimalField(
        required=False,
        min_value=0,
        decimal_places=2,
        max_digits=10,
        widget=forms.NumberInput(
            attrs={"class": "form-control", "placeholder": "Min ₹", "step": "0.01"}
        ),
    )
    # A second validated bound lets buyers narrow expensive or broad searches.
    max_price = forms.DecimalField(
        required=False,
        min_value=0,
        decimal_places=2,
        max_digits=10,
        widget=forms.NumberInput(
            attrs={"class": "form-control", "placeholder": "Max ₹", "step": "0.01"}
        ),
    )

    def clean(self):
        """Require the maximum price to be at least the minimum price."""

        # Preserve Django's field-level validation and receive normalized decimals.
        cleaned_data = super().clean()
        minimum_price = cleaned_data.get("min_price")
        maximum_price = cleaned_data.get("max_price")

        if (
            minimum_price is not None
            and maximum_price is not None
            and maximum_price < minimum_price
        ):
            # Attach one clear error to the form because two fields are involved.
            raise forms.ValidationError("Maximum price cannot be below minimum price.")

        return cleaned_data

"""Provide validated registration and login forms with Bootstrap-ready widgets."""

from django import forms
from django.contrib.auth.forms import AuthenticationForm, UserCreationForm

from .models import User


class BootstrapFieldsMixin:
    """Apply consistent Bootstrap classes without repeating widget attributes."""

    def add_bootstrap_classes(self):
        """Add form-control classes while preserving any existing CSS classes."""

        for field_name, field in self.fields.items():
            # File inputs use a distinct Bootstrap class for correct spacing.
            desired_class = "form-control"

            if isinstance(field.widget, forms.CheckboxInput):
                # Checkboxes use form-check-input instead of the text-input class.
                desired_class = "form-check-input"

            # Keep classes supplied by Django and append our presentation class.
            existing_classes = field.widget.attrs.get("class", "")
            field.widget.attrs["class"] = f"{existing_classes} {desired_class}".strip()
            # Human-readable placeholders make blank text fields less confusing.
            field.widget.attrs.setdefault("placeholder", field.label)


class BaseRoleRegistrationForm(BootstrapFieldsMixin, UserCreationForm):
    """Share safe registration behavior while subclasses choose a fixed role."""

    # Subclasses must replace this value; users never choose role in submitted HTML.
    assigned_role = None

    class Meta:
        """Connect this ModelForm to the custom user and editable profile fields."""

        # Django will save a User instance after password validation succeeds.
        model = User
        # Password fields are automatically supplied by UserCreationForm.
        fields = (
            "username",
            "email",
            "first_name",
            "last_name",
            "phone_number",
            "profile_picture",
        )

    def __init__(self, *args, **kwargs):
        """Mark email as required and style every visible field."""

        # UserCreationForm builds password1 and password2 before this code runs.
        super().__init__(*args, **kwargs)
        # Email is used for order and payment communication, so require it here.
        self.fields["email"].required = True
        # The mixin keeps styling logic separate from validation logic.
        self.add_bootstrap_classes()

    def clean_email(self):
        """Normalize email and prevent case-insensitive duplicate registrations."""

        # strip removes accidental surrounding spaces from pasted addresses.
        email = self.cleaned_data["email"].strip().lower()

        if User.objects.filter(email__iexact=email).exists():
            # Case-insensitive matching prevents user@example.com duplicates.
            raise forms.ValidationError("An account already uses this email address.")

        return email

    def save(self, commit=True):
        """Assign the server-controlled role before saving the new account."""

        # commit=False lets us set protected attributes before the database write.
        user = super().save(commit=False)

        if self.assigned_role is None:
            # A missing subclass role is a programming error, not user input error.
            raise ValueError("Registration forms must define assigned_role.")

        # Never accept role from request.POST; use the trusted class constant.
        user.role = self.assigned_role

        if commit:
            # UserCreationForm has already hashed the password before this save.
            user.save()

        return user


class BuyerRegistrationForm(BaseRoleRegistrationForm):
    """Register a buyer without exposing any seller or admin permissions."""

    # This server-side constant prevents privilege escalation through form tampering.
    assigned_role = User.Role.BUYER


class SellerRegistrationForm(BaseRoleRegistrationForm):
    """Register a seller and require the shop name shown to buyers."""

    # This server-side constant prevents privilege escalation through form tampering.
    assigned_role = User.Role.SELLER

    class Meta(BaseRoleRegistrationForm.Meta):
        """Add shop_name to the common user-registration field list."""

        # Reuse all buyer fields while inserting the seller-only business name.
        fields = BaseRoleRegistrationForm.Meta.fields + ("shop_name",)

    def __init__(self, *args, **kwargs):
        """Make shop name visibly required in both browser and server validation."""

        # The parent initializes password fields, email rules, and Bootstrap classes.
        super().__init__(*args, **kwargs)
        # Model.clean also validates this, providing defense in depth.
        self.fields["shop_name"].required = True


class MarketplaceAuthenticationForm(BootstrapFieldsMixin, AuthenticationForm):
    """Style Django's secure built-in authentication form for marketplace pages."""

    def __init__(self, request=None, *args, **kwargs):
        """Initialize normal authentication validation and Bootstrap presentation."""

        # AuthenticationForm handles inactive accounts and password verification.
        super().__init__(request=request, *args, **kwargs)
        # Styling does not alter authentication behavior or submitted values.
        self.add_bootstrap_classes()

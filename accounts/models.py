"""Define the custom user model shared by buyers, sellers, and administrators."""

from django.contrib.auth.models import AbstractUser, UserManager
from django.core.exceptions import ValidationError
from django.db import models

class MarketplaceUserManager(UserManager):
    """Ensure command-line superusers always receive the marketplace admin role."""

    def create_superuser(self, username, email=None, password=None, **extra_fields):
        """Create a Django superuser that can also access the custom admin panel."""

        # Django admin requires both flags to be true for unrestricted access.
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        # The custom dashboard separately checks this explicit marketplace role.
        extra_fields.setdefault("role", self.model.Role.ADMIN)

        if extra_fields.get("is_staff") is not True:
            # Reject inconsistent superusers early instead of creating bad data.
            raise ValueError("A superuser must have is_staff=True.")

        if extra_fields.get("is_superuser") is not True:
            # Reject inconsistent superusers early instead of creating bad data.
            raise ValueError("A superuser must have is_superuser=True.")

        # The parent manager hashes the password and saves the user safely.
        return super().create_superuser(username, email, password, **extra_fields)


class User(AbstractUser):
    """Extend Django's proven user model with marketplace-specific profile data."""

    class Role(models.TextChoices):
        """List the three roles used for navigation and authorization checks."""

        # Buyers browse products and own carts and orders.
        BUYER = "buyer", "Buyer"
        # Sellers manage products, order lines, and tracking updates.
        SELLER = "seller", "Seller"
        # Admins moderate the complete marketplace through a custom dashboard.
        ADMIN = "admin", "Admin"

    # Role drives server-side permissions; it is never trusted from hidden HTML.
    role = models.CharField(
        max_length=10,
        choices=Role.choices,
        default=Role.BUYER,
        db_index=True,
        help_text="Controls which marketplace interface and actions are available.",
    )
    # A flexible string supports country codes and leading plus signs.
    phone_number = models.CharField(
        max_length=20,
        blank=True,
        help_text="Optional contact number, for example +91 98765 43210.",
    )
    # Only seller accounts need a public shop name.
    shop_name = models.CharField(
        max_length=150,
        blank=True,
        help_text="Required for sellers and displayed beside their products.",
    )
    # Uploaded profiles are stored below MEDIA_ROOT/profile_pictures/.
    profile_picture = models.ImageField(
        upload_to="profile_pictures/",
        blank=True,
        null=True,
        help_text="Optional profile or shop image uploaded by the user.",
    )
    # Verification is intentionally admin-controlled rather than self-assigned.
    is_verified = models.BooleanField(
        default=False,
        help_text="Indicates that an administrator has verified this account.",
    )

    # Use the custom manager so createsuperuser also sets the admin role.
    objects = MarketplaceUserManager()

    def clean(self):
        """Validate role-specific profile rules before model-form saves."""

        # Preserve AbstractUser's username and email normalization behavior.
        super().clean()

        if self.role == self.Role.SELLER and not (self.shop_name or "").strip():
            # A seller needs a shop identity before products can be displayed.
            raise ValidationError({"shop_name": "Sellers must provide a shop name."})

    @property
    def is_buyer(self):
        """Return True when this account belongs to a buyer."""

        return self.role == self.Role.BUYER

    @property
    def is_seller(self):
        """Return True when this account belongs to a seller."""

        return self.role == self.Role.SELLER

    @property
    def is_marketplace_admin(self):
        """Return True when this account may use the custom admin interface."""

        return self.role == self.Role.ADMIN

    def __str__(self):
        """Show a useful identity in logs, forms, and Django's default admin."""

        # Seller records are clearer when their shop is visible to staff users.
        if self.is_seller and self.shop_name:
            return f"{self.username} ({self.shop_name})"

        # Other roles use the stable username and readable role label.
        return f"{self.username} ({self.get_role_display()})"

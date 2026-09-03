from django.db import models

# Create your models here.
"""Define categories and seller-owned products for the marketplace catalog."""

from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import models
from django.urls import reverse


class Category(models.Model):
    """Group related products into buyer-friendly catalog sections."""

    # Category names are unique so navigation never shows duplicate labels.
    name = models.CharField(
        max_length=100,
        unique=True,
        help_text="A short buyer-facing category name, such as Electronics.",
    )
    # Slugs create readable, stable values for category filter URLs.
    slug = models.SlugField(
        max_length=110,
        unique=True,
        help_text="URL-safe category value, such as electronics.",
    )

    class Meta:
        """Keep category dropdowns and admin lists alphabetically sorted."""

        # Alphabetical ordering helps buyers and staff locate categories quickly.
        ordering = ("name",)
        # A readable plural avoids Django's default 'Categorys' spelling.
        verbose_name_plural = "categories"

    def __str__(self):
        """Return the buyer-facing category name in forms and admin pages."""

        return self.name


class Product(models.Model):
    """Store one sellable item that belongs to exactly one seller."""

    # PROTECT prevents account deletion from silently destroying catalog history.
    seller = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="products",
        help_text="Seller account that owns and manages this product.",
    )
    # PROTECT keeps category meaning intact for existing product records.
    category = models.ForeignKey(
        Category,
        on_delete=models.PROTECT,
        related_name="products",
        help_text="Catalog category used for buyer browsing and filtering.",
    )
    # A database index speeds up common name-based catalog operations.
    name = models.CharField(
        max_length=200,
        db_index=True,
        help_text="Clear product title shown on cards and order lines.",
    )
    # TextField supports detailed features, materials, and usage information.
    description = models.TextField(
        help_text="Detailed buyer-facing description of the product.",
    )
    # Decimal avoids floating-point rounding errors in currency calculations.
    price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(Decimal("0.01"))],
        help_text="Current unit price in Indian rupees.",
    )
    # A non-negative integer accurately represents physical stock units.
    stock = models.PositiveIntegerField(
        default=0,
        help_text="Number of units currently available for purchase.",
    )
    # Each uploaded product image receives a date-based media folder.
    image = models.ImageField(
        upload_to="products/%Y/%m/%d/",
        blank=True,
        null=True,
        help_text="Optional product photo; JPG, PNG, or WEBP is recommended.",
    )
    # Soft deletion preserves references from past orders and moderation logs.
    is_active = models.BooleanField(
        default=True,
        db_index=True,
        help_text="Only active products are visible and purchasable by buyers.",
    )
    # auto_now_add records the original creation time exactly once.
    created_at = models.DateTimeField(
        auto_now_add=True,
        help_text="Timestamp recorded when the seller first created the product.",
    )
    # auto_now helps sellers and staff identify recently edited inventory.
    updated_at = models.DateTimeField(
        auto_now=True,
        help_text="Timestamp refreshed whenever the product is edited.",
    )

    class Meta:
        """Show newest products first and add a common catalog index."""

        # New listings appear before older listings unless a view overrides order.
        ordering = ("-created_at",)
        # This composite index helps active category filtering on the storefront.
        indexes = [
            models.Index(fields=("is_active", "category"), name="product_active_cat")
        ]

    def clean(self):
        """Reject product ownership by buyer or admin accounts."""

        # Run any validation inherited from Django's base Model class first.
        super().clean()

        if self.seller_id and self.seller.role != "seller":
            # Only seller accounts may own inventory, even through admin or scripts.
            raise ValidationError({"seller": "Products must belong to a seller."})

    @property
    def is_in_stock(self):
        """Return True only when an active product has at least one unit."""

        return self.is_active and self.stock > 0

    @property
    def seller_display_name(self):
        """Return the shop name when available, otherwise the seller username."""

        return self.seller.shop_name or self.seller.username

    def get_absolute_url(self):
        """Return the public detail URL used after form saves and in templates."""

        return reverse("products:product_detail", kwargs={"product_id": self.pk})

    def __str__(self):
        """Show product and shop together in logs and staff interfaces."""

        return f"{self.name} — {self.seller_display_name}"

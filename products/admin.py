"""Expose categories and products in Django's built-in staff admin."""

from django.contrib import admin

from .models import Category, Product


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    """Make category creation quick while keeping slugs predictable."""

    # Staff can scan the public label and URL value side by side.
    list_display = ("name", "slug")
    # Django proposes a slug from the typed name but still allows manual editing.
    prepopulated_fields = {"slug": ("name",)}
    # Search remains useful once the category list grows.
    search_fields = ("name", "slug")


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    """Give staff a searchable overview of every seller's inventory."""

    # Common moderation and stock fields appear without opening each record.
    list_display = (
        "name",
        "seller",
        "category",
        "price",
        "stock",
        "is_active",
        "created_at",
    )
    # Sidebar filters isolate inactive, category-specific, or recently added items.
    list_filter = ("is_active", "category", "created_at")
    # Search covers public title and both stable seller identifiers.
    search_fields = ("name", "seller__username", "seller__shop_name")
    # Foreign-key joins are loaded once to prevent one query per table row.
    list_select_related = ("seller", "category")
    # Creation time is an audit field and should not be manually changed.
    readonly_fields = ("created_at", "updated_at")

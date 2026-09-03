"""Configure Django's products application."""

from django.apps import AppConfig


class ProductsConfig(AppConfig):
    """Register the products app and its default primary-key type."""

    # BigAutoField supports a large catalog without primary-key exhaustion.
    default_auto_field = "django.db.models.BigAutoField"
    # Django uses this name to discover product models and templates.
    name = "products"

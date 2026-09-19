"""Configure Django's tracking application."""

from django.apps import AppConfig


class TrackingConfig(AppConfig):
    """Register the tracking app and its default primary-key type."""

    # BigAutoField keeps tracking keys consistent with high-volume order tables.
    default_auto_field = "django.db.models.BigAutoField"
    # Django uses this name to locate tracking models and templates.
    name = "tracking"

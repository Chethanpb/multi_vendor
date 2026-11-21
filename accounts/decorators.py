"""Authorization decorators for marketplace role-specific views."""

from functools import wraps

from django.contrib.auth.views import redirect_to_login
from django.core.exceptions import PermissionDenied

from .models import User


def _require_role(view, role):
    @wraps(view)
    def wrapped_view(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect_to_login(
                request.get_full_path(), login_url="accounts:login"
            )

        if request.user.role != role:
            raise PermissionDenied

        return view(request, *args, **kwargs)

    return wrapped_view


def seller_required(view):
    """Allow only authenticated sellers to access a view."""
    return _require_role(view, User.Role.SELLER)


def buyer_required(view):
    """Allow only authenticated buyers to access a view."""
    return _require_role(view, User.Role.BUYER)

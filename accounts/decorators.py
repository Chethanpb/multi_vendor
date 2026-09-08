"""Authorization decorators for marketplace role-specific views."""

from functools import wraps

from django.contrib.auth.views import redirect_to_login
from django.core.exceptions import PermissionDenied

from .models import User


def seller_required(view):
    """Allow only authenticated seller accounts to access a view."""

    @wraps(view)
    def wrapped_view(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect_to_login(request.get_full_path(), login_url="/accounts/login/")

        if request.user.role != User.Role.SELLER:
            raise PermissionDenied

        return view(request, *args, **kwargs)

    return wrapped_view

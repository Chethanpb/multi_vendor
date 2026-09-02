"""Handle buyer/seller registration, login, logout, and role-aware redirects."""

from django.contrib import messages
from django.contrib.auth import login, logout
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_http_methods, require_POST

from .forms import (
    BuyerRegistrationForm,
    MarketplaceAuthenticationForm,
    SellerRegistrationForm,
)
from .models import User


def _redirect_authenticated_user(request):
    """Return the role redirect for signed-in users, or None for guests."""

    if request.user.is_authenticated:
        # Registration and login pages are unnecessary after authentication.
        return redirect("accounts:role_redirect")

    # None tells the calling view to continue displaying its public form.
    return None


@require_http_methods(["GET", "POST"])
def buyer_register(request):
    """Create a buyer account, sign it in, and open the buyer storefront."""

    authenticated_redirect = _redirect_authenticated_user(request)

    if authenticated_redirect:
        # Avoid creating a second account while another user is already signed in.
        return authenticated_redirect

    # Bound POST data and uploaded files are validated; GET creates an empty form.
    form = BuyerRegistrationForm(request.POST or None, request.FILES or None)

    if request.method == "POST" and form.is_valid():
        # The form hashes the password and assigns the buyer role server-side.
        buyer = form.save()
        # Sign in immediately so the new buyer can start shopping.
        login(request, buyer)
        messages.success(request, "Welcome! Your buyer account is ready.")
        return redirect("products:home")

    # Validation errors are rendered beside their corresponding fields.
    return render(request, "accounts/buyer_register.html", {"form": form})


@require_http_methods(["GET", "POST"])
def seller_register(request):
    """Create a seller account, sign it in, and open its store dashboard."""

    authenticated_redirect = _redirect_authenticated_user(request)

    if authenticated_redirect:
        # Avoid creating a second account while another user is already signed in.
        return authenticated_redirect

    # request.FILES carries the optional shop/profile image uploaded by the seller.
    form = SellerRegistrationForm(request.POST or None, request.FILES or None)

    if request.method == "POST" and form.is_valid():
        # The form validates shop name and fixes the role to seller server-side.
        seller = form.save()
        # Sign in immediately so the seller can add the first product.
        login(request, seller)
        messages.success(request, "Your seller account and shop are ready.")
        return redirect("products:seller_dashboard")

    # The same template handles blank and invalid forms without losing user input.
    return render(request, "accounts/seller_register.html", {"form": form})


@require_http_methods(["GET", "POST"])
def login_view(request):
    """Authenticate any role and redirect it to an authorized destination."""

    authenticated_redirect = _redirect_authenticated_user(request)

    if authenticated_redirect:
        # An authenticated user should not see a redundant login form.
        return authenticated_redirect

    # Django's AuthenticationForm checks the password hash and is_active status.
    form = MarketplaceAuthenticationForm(request, data=request.POST or None)

    if request.method == "POST" and form.is_valid():
        # get_user returns the exact account authenticated by the built-in form.
        authenticated_user = form.get_user()
        login(request, authenticated_user)
        messages.success(request, f"Welcome back, {authenticated_user.username}.")

        # A protected page may provide next so the user can continue after login.
        requested_next_url = request.POST.get("next", "")
        next_url_is_safe = url_has_allowed_host_and_scheme(
            url=requested_next_url,
            allowed_hosts={request.get_host()},
            require_https=request.is_secure(),
        )

        if requested_next_url and next_url_is_safe:
            # Only same-host destinations are accepted to prevent open redirects.
            return redirect(requested_next_url)

        return redirect("accounts:role_redirect")

    # GET supplies next as a hidden value; POST keeps it after validation errors.
    next_url = request.POST.get("next") or request.GET.get("next", "")
    return render(request, "accounts/login.html", {"form": form, "next": next_url})


@require_POST
def logout_view(request):
    """End the current session through a CSRF-protected POST request."""

    if request.user.is_authenticated:
        # Django removes the authenticated user ID from the current session.
        logout(request)
        messages.success(request, "You have been signed out safely.")

    # Guests and signed-out users both return to the public storefront.
    return redirect("products:home")


def role_redirect(request):
    """Send each authenticated role to its visually separate landing page."""

    if not request.user.is_authenticated:
        # Keep guest behavior predictable by directing them to one login route.
        return redirect(f"{reverse('accounts:login')}?next={request.path}")

    if request.user.role == User.Role.SELLER:
        # Sellers land on store performance and inventory information.
        return redirect("products:seller_dashboard")

    if request.user.role == User.Role.ADMIN:
        # Marketplace admins land on global analytics and moderation controls.
        return redirect("adminpanel:dashboard")

    # Buyer is the safe default for normal customer accounts.
    return redirect("products:home")

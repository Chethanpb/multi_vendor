"""Expose a small buyer cart badge count to shared templates."""

from django.db.models import Sum

from .models import CartItem


def cart_item_count(request):
    """Return total buyer cart units without exposing cart data to other roles."""

    if not request.user.is_authenticated or request.user.role != "buyer":
        # Guests, sellers, and admins do not need a storefront cart query.
        return {"cart_item_count": 0}

    aggregate = CartItem.objects.filter(cart__buyer=request.user).aggregate(
        total=Sum("quantity")
    )
    # SQL SUM returns None for no rows; templates expect a normal integer.
    return {"cart_item_count": aggregate["total"] or 0}
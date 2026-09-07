"""Handle buyer cart/order pages and seller-specific incoming order lines."""

from django.contrib import messages
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST


from products.models import Product

from .forms import CartQuantityForm
from .models import CartItem, Order, OrderItem




def cart_detail(request):
    """Display the signed-in buyer's cart with current prices and stock."""

    cart = get_or_create_buyer_cart(request.user)
    # select_related avoids separate product and seller queries for every cart row.
    cart_items = cart.items.select_related("product", "product__seller")
    context = {"cart": cart, "cart_items": cart_items}
    return render(request, "orders/cart_detail.html", context)



@require_POST
@transaction.atomic
def add_to_cart(request, product_id):
    """Add an active product or increase its existing buyer-cart quantity safely."""

    # Lock stock while reading and updating the requested cart quantity.
    product = get_object_or_404(
        Product.objects.select_for_update(),
        pk=product_id,
        is_active=True,
    )
    quantity_form = CartQuantityForm(product, request.POST)

    if not quantity_form.is_valid():
        # Form errors may include malformed, zero, negative, or excessive quantities.
        messages.error(request, quantity_form.errors.as_text())
        return redirect("products:product_detail", product_id=product_id)

    requested_quantity = quantity_form.cleaned_data["quantity"]
    cart = get_or_create_buyer_cart(request.user)
    cart_item, created = CartItem.objects.select_for_update().get_or_create(
        cart=cart,
        product=product,
        defaults={"quantity": requested_quantity},
    )

    if not created:
        # Adding the same product combines quantities instead of making duplicates.
        combined_quantity = cart_item.quantity + requested_quantity

        if combined_quantity > product.stock:
            # Current locked stock is more authoritative than the HTML max attribute.
            messages.error(
                request,
                f"Your cart cannot exceed the {product.stock} available unit(s).",
            )
            return redirect("products:product_detail", product_id=product_id)

        cart_item.quantity = combined_quantity
        cart_item.save(update_fields=("quantity",))

    messages.success(request, f"{product.name} was added to your cart.")
    return redirect("orders:cart_detail")



@require_POST
@transaction.atomic
def update_cart_item(request, item_id):
    """Change quantity only for a cart line owned by the signed-in buyer."""

    # Ownership is enforced before reading any product or quantity information.
    cart_item = get_object_or_404(
        CartItem.objects.select_for_update().select_related("product"),
        pk=item_id,
        cart__buyer=request.user,
    )
    # Lock the product row so the validated stock cannot change mid-update.
    product = Product.objects.select_for_update().get(pk=cart_item.product_id)
    quantity_form = CartQuantityForm(product, request.POST)

    if quantity_form.is_valid():
        cart_item.quantity = quantity_form.cleaned_data["quantity"]
        cart_item.save(update_fields=("quantity",))
        messages.success(request, f"{product.name} quantity was updated.")
    else:
        # Keep the previous valid quantity and explain why the update was rejected.
        messages.error(request, quantity_form.errors.as_text())

    return redirect("orders:cart_detail")



@require_POST
def remove_cart_item(request, item_id):
    """Remove one cart line only when it belongs to the signed-in buyer."""

    # The buyer relationship in this lookup prevents cross-account deletions.
    cart_item = get_object_or_404(
        CartItem.objects.select_related("product"),
        pk=item_id,
        cart__buyer=request.user,
    )
    product_name = cart_item.product.name
    cart_item.delete()
    messages.success(request, f"{product_name} was removed from your cart.")
    return redirect("orders:cart_detail")



def checkout_review(request):
    """Review current cart values before a POST starts Stripe Checkout."""

    cart = get_or_create_buyer_cart(request.user)
    cart_items = list(cart.items.select_related("product", "product__seller"))

    if not cart_items:
        # Avoid showing a checkout action that cannot create a Stripe session.
        messages.info(request, "Add at least one product before checkout.")
        return redirect("products:product_list")

    checkout_errors = []

    for cart_item in cart_items:
        if not cart_item.product.is_active:
            # A product can be moderated after it was placed in a cart.
            checkout_errors.append(f"{cart_item.product.name} is no longer active.")
        elif cart_item.quantity > cart_item.product.stock:
            # This friendly pre-check is repeated under locks during reservation.
            checkout_errors.append(
                f"Only {cart_item.product.stock} of {cart_item.product.name} remain."
            )

    context = {
        "cart": cart,
        "cart_items": cart_items,
        "checkout_errors": checkout_errors,
    }
    return render(request, "orders/checkout_review.html", context)


def buyer_order_list(request):
    """List complete order history belonging only to the signed-in buyer."""

    # Prefetch line products and shipment state in bounded additional queries.
    orders = (
        Order.objects.filter(buyer=request.user)
        .prefetch_related("items__product", "items__seller")
        .select_related("payment")
    )
    return render(request, "orders/buyer_order_list.html", {"orders": orders})



def buyer_order_detail(request, order_id):
    """Show one order only when the signed-in buyer owns it."""

    # Buyer ownership in the lookup prevents sequential-ID information disclosure.
    order = get_object_or_404(
        Order.objects.prefetch_related("items__product", "items__seller"),
        pk=order_id,
        buyer=request.user,
    )
    return render(request, "orders/buyer_order_detail.html", {"order": order})



def seller_order_list(request):
    """List paid fulfillment lines belonging only to the signed-in seller."""

    # Pending payments are hidden because they are not yet real seller work.
    fulfillment_statuses = (
        Order.Status.PAID,
        Order.Status.PROCESSING,
        Order.Status.SHIPPED,
        Order.Status.DELIVERED,
        Order.Status.CANCELLED,
    )
    order_items = (
        OrderItem.objects.filter(
            seller=request.user,
            order__status__in=fulfillment_statuses,
        )
        .select_related("order", "order__buyer", "product")
        .order_by("-order__created_at")
    )
    return render(
        request,
        "orders/seller_order_list.html",
        {"order_items": order_items},
    )

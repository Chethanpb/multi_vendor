from django.shortcuts import render

# Create your views here.
"""Serve role-restricted analytics, product moderation, and account suspension."""

from decimal import Decimal

from django.contrib import messages
from django.contrib.auth import get_user_model
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import DecimalField, F, Q, Sum
from django.db.models.functions import Coalesce
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from accounts.decorators import admin_required
from orders.models import Order
from payments.models import Payment
from products.models import Product

from .forms import ProductRemovalForm


# get_user_model respects the project's AUTH_USER_MODEL setting.
User = get_user_model()


@admin_required
def dashboard(request):
    """Display global marketplace metrics calculated with Django ORM aggregation."""

    # Count each role independently so the cards remain clear and verifiable.
    total_users = User.objects.count()
    total_buyers = User.objects.filter(role=User.Role.BUYER).count()
    total_sellers = User.objects.filter(role=User.Role.SELLER).count()
    total_orders = Order.objects.count()
    paid_revenue = Payment.objects.filter(status=Payment.Status.PAID).aggregate(
        total=Coalesce(
            Sum("amount"),
            Decimal("0.00"),
            output_field=DecimalField(max_digits=14, decimal_places=2),
        )
    )["total"]
    # Sum immutable order lines only when their one-to-one payment is confirmed paid.
    top_selling_products = (
        Product.objects.filter(order_items__order__payment__status=Payment.Status.PAID)
        .annotate(
            units_sold=Sum("order_items__quantity"),
            sales_value=Sum(
                F("order_items__quantity") * F("order_items__price_at_purchase"),
                output_field=DecimalField(max_digits=14, decimal_places=2),
            ),
        )
        .select_related("seller", "category")
        .order_by("-units_sold")[:5]
    )
    # These small recent lists are bounded to keep dashboard queries and HTML compact.
    recent_signups = User.objects.order_by("-date_joined")[:8]
    recent_orders = Order.objects.select_related("buyer").order_by("-created_at")[:8]

    context = {
        "total_users": total_users,
        "total_buyers": total_buyers,
        "total_sellers": total_sellers,
        "total_orders": total_orders,
        "paid_revenue": paid_revenue,
        "active_products": Product.objects.filter(is_active=True).count(),
        "top_selling_products": top_selling_products,
        "recent_signups": recent_signups,
        "recent_orders": recent_orders,
    }
    return render(request, "adminpanel/dashboard.html", context)


@admin_required
def product_list(request):
    """List products from every seller with search and active-state filtering."""

    # select_related prevents repeated seller/category queries in the global table.
    products = Product.objects.select_related("seller", "category")
    search_query = request.GET.get("query", "").strip()
    status_filter = request.GET.get("status", "all")

    if search_query:
        # Q combines safe case-insensitive search over product and shop identity.
        products = products.filter(
            Q(name__icontains=search_query)
            | Q(seller__username__icontains=search_query)
            | Q(seller__shop_name__icontains=search_query)
        )

    if status_filter == "active":
        products = products.filter(is_active=True)
    elif status_filter == "inactive":
        products = products.filter(is_active=False)

    # Twenty-five rows keep the cross-seller moderation page responsive.
    paginator = Paginator(products, 25)
    page = paginator.get_page(request.GET.get("page"))
    context = {
        "page": page,
        "search_query": search_query,
        "status_filter": status_filter,
        "removal_form": ProductRemovalForm(),
    }
    return render(request, "adminpanel/product_list.html", context)


@admin_required
@require_POST
@transaction.atomic
def deactivate_product(request, product_id):
    """Soft-delete any active product and append the required moderation audit log."""

    # Lock the row so two admin actions cannot create conflicting active states.
    product = get_object_or_404(
        Product.objects.select_for_update().select_related("seller"),
        pk=product_id,
    )
    form = ProductRemovalForm(request.POST)

    if not product.is_active:
        # Repeated submissions should not create duplicate removal audit entries.
        messages.info(request, f"{product.name} is already inactive.")
        return redirect("adminpanel:product_list")

    if not form.is_valid():
        # The list page uses messages because each row has a compact inline form.
        messages.error(request, form.errors.as_text())
        return redirect("adminpanel:product_list")

    product.is_active = False
    product.save(update_fields=("is_active", "updated_at"))
    removal_log = form.save(commit=False)
    # Product and admin identity come from trusted database/session values.
    removal_log.product = product
    removal_log.removed_by = request.user
    removal_log.full_clean()
    removal_log.save()
    messages.success(
        request,
        f"{product.name} from {product.seller_display_name} was deactivated.",
    )
    return redirect("adminpanel:product_list")


@admin_required
@require_POST
@transaction.atomic
def reactivate_product(request, product_id):
    """Let an administrator restore a previously inactive product to the catalog."""

    # The locked product is loaded by trusted URL ID and not by seller ownership.
    product = get_object_or_404(Product.objects.select_for_update(), pk=product_id)

    if product.is_active:
        # Idempotent behavior gives repeated clicks a harmless result.
        messages.info(request, f"{product.name} is already active.")
    else:
        product.is_active = True
        product.save(update_fields=("is_active", "updated_at"))
        messages.success(request, f"{product.name} is visible to buyers again.")

    return redirect("adminpanel:product_list")


@admin_required
def user_list(request):
    """List all accounts with role, verification, and suspension filters."""

    users = User.objects.all()
    search_query = request.GET.get("query", "").strip()
    role_filter = request.GET.get("role", "all")
    status_filter = request.GET.get("status", "all")

    if search_query:
        # Search does not expose passwords or private authentication internals.
        users = users.filter(
            Q(username__icontains=search_query)
            | Q(email__icontains=search_query)
            | Q(shop_name__icontains=search_query)
        )

    if role_filter in {User.Role.BUYER, User.Role.SELLER, User.Role.ADMIN}:
        users = users.filter(role=role_filter)

    if status_filter == "active":
        users = users.filter(is_active=True)
    elif status_filter == "suspended":
        users = users.filter(is_active=False)

    paginator = Paginator(users.order_by("-date_joined"), 25)
    page = paginator.get_page(request.GET.get("page"))
    context = {
        "page": page,
        "search_query": search_query,
        "role_filter": role_filter,
        "status_filter": status_filter,
    }
    return render(request, "adminpanel/user_list.html", context)


@admin_required
@require_POST
@transaction.atomic
def suspend_user(request, user_id):
    """Deactivate a buyer or seller so Django's auth backend rejects future access."""

    # Locking prevents simultaneous suspend/reactivate requests from crossing.
    target_user = get_object_or_404(User.objects.select_for_update(), pk=user_id)

    if target_user.pk == request.user.pk:
        # An administrator must not accidentally lock themselves out mid-session.
        messages.error(request, "You cannot suspend your own account.")
    elif target_user.role == User.Role.ADMIN:
        # This custom tool intentionally limits suspension to buyers and sellers.
        messages.error(request, "Administrator accounts are managed in Django admin.")
    elif not target_user.is_active:
        # Repeated POSTs remain harmless and auditable through normal server logs.
        messages.info(request, f"{target_user.username} is already suspended.")
    else:
        target_user.is_active = False
        target_user.save(update_fields=("is_active",))
        messages.success(request, f"{target_user.username} was suspended.")

    return redirect("adminpanel:user_list")


@admin_required
@require_POST
@transaction.atomic
def reactivate_user(request, user_id):
    """Restore login access for a previously suspended buyer or seller."""

    # The database lock pairs with suspend_user to prevent a last-write race.
    target_user = get_object_or_404(User.objects.select_for_update(), pk=user_id)

    if target_user.role == User.Role.ADMIN:
        # Admin accounts remain under Django's built-in superuser governance.
        messages.error(request, "Administrator accounts are managed in Django admin.")
    elif target_user.is_active:
        messages.info(request, f"{target_user.username} is already active.")
    else:
        target_user.is_active = True
        target_user.save(update_fields=("is_active",))
        messages.success(request, f"{target_user.username} can sign in again.")

    return redirect("adminpanel:user_list")

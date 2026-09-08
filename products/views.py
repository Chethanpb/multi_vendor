"""Serve the buyer catalog and protect every seller inventory operation."""

from decimal import Decimal

from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import Count, DecimalField, ExpressionWrapper, F, Q, Sum
from django.db.models.functions import Coalesce
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_http_methods, require_POST

from accounts.decorators import seller_required

from .forms import ProductFilterForm, ProductForm
from .models import Product


def _filtered_active_products(filter_form):
    """Build one optimized active-product query from a validated filter form."""

    # select_related fetches seller and category in one SQL join, avoiding N+1 queries.
    products = Product.objects.filter(is_active=True).select_related(
        "seller", "category"
    )

    if not filter_form.is_valid():
        # Invalid filters show form errors and return the unfiltered active catalog.
        return products

    search_query = filter_form.cleaned_data.get("query", "")
    category = filter_form.cleaned_data.get("category")
    minimum_price = filter_form.cleaned_data.get("min_price")
    maximum_price = filter_form.cleaned_data.get("max_price")

    if search_query:
        # Q objects safely combine OR conditions using parameterized SQL.
        products = products.filter(
            Q(name__icontains=search_query)
            | Q(description__icontains=search_query)
            | Q(seller__shop_name__icontains=search_query)
        )

    if category:
        # ModelChoiceField guarantees this is a real Category instance.
        products = products.filter(category=category)

    if minimum_price is not None:
        # Decimal values remain exact when compared with DecimalField prices.
        products = products.filter(price__gte=minimum_price)

    if maximum_price is not None:
        # The inclusive upper bound matches normal storefront expectations.
        products = products.filter(price__lte=maximum_price)

    return products


def product_list(request):
    """Display the public product catalog with search, filters, and pagination."""

    # Binding request.GET lets Django validate every optional filter value.
    filter_form = ProductFilterForm(request.GET or None)
    products = _filtered_active_products(filter_form)
    # Twelve cards per page keeps response size and scrolling manageable.
    paginator = Paginator(products, 12)
    page = paginator.get_page(request.GET.get("page"))
    # Preserve filters when page links add or replace only the page number.
    query_parameters = request.GET.copy()
    query_parameters.pop("page", None)

    context = {
        "filter_form": filter_form,
        "page": page,
        "query_string": query_parameters.urlencode(),
        "is_home": request.path == "/",
    }
    return render(request, "products/product_list.html", context)


def product_detail(request, product_id):
    """Show one active product with stock, seller, and purchase controls."""

    # Filtering is_active here prevents direct URLs from exposing moderated items.
    product = get_object_or_404(
        Product.objects.select_related("seller", "category"),
        pk=product_id,
        is_active=True,
    )
    return render(request, "products/product_detail.html", {"product": product})


@seller_required
def seller_dashboard(request):
    """Summarize the signed-in seller's products, orders, and earned revenue."""

    seller_products = Product.objects.filter(seller=request.user)
    try:
        from orders.models import Order, OrderItem
    except ModuleNotFoundError as error:
        if error.name != "orders":
            raise
        sales_summary = {
            "total_orders": 0,
            "total_units": 0,
            "total_revenue": Decimal("0.00"),
        }
        recent_order_items = []
        orders_available = False
    else:
        # Only paid or fulfilled orders count as real sales on the seller dashboard.
        sale_statuses = (
            Order.Status.PAID,
            Order.Status.PROCESSING,
            Order.Status.SHIPPED,
            Order.Status.DELIVERED,
        )
        seller_order_items = OrderItem.objects.filter(
            seller=request.user,
            order__status__in=sale_statuses,
        )
        line_revenue = ExpressionWrapper(
            F("quantity") * F("price_at_purchase"),
            output_field=DecimalField(max_digits=14, decimal_places=2),
        )
        sales_summary = seller_order_items.aggregate(
            total_orders=Count("order_id", distinct=True),
            total_units=Coalesce(Sum("quantity"), 0),
            total_revenue=Coalesce(
                Sum(line_revenue),
                Decimal("0.00"),
                output_field=DecimalField(max_digits=14, decimal_places=2),
            ),
        )
        recent_order_items = seller_order_items.select_related(
            "order", "order__buyer", "product"
        ).order_by("-order__created_at")[:6]
        orders_available = True

    context = {
        "product_count": seller_products.count(),
        "active_product_count": seller_products.filter(is_active=True).count(),
        "low_stock_count": seller_products.filter(is_active=True, stock__lte=5).count(),
        "sales_summary": sales_summary,
        "recent_order_items": recent_order_items,
        "orders_available": orders_available,
    }
    return render(request, "products/seller_dashboard.html", context)


@seller_required
def seller_product_list(request):
    """List all inventory owned by the signed-in seller, including inactive items."""

    # Ownership is enforced in SQL so another seller's rows never enter the context.
    products = Product.objects.filter(seller=request.user).select_related("category")
    return render(request, "products/seller_product_list.html", {"products": products})


@seller_required
@require_http_methods(["GET", "POST"])
def seller_product_create(request):
    """Create a product owned by the signed-in seller after model validation."""

    # request.FILES is required for ImageField uploads on POST requests.
    form = ProductForm(request.POST or None, request.FILES or None)

    if request.method == "POST" and form.is_valid():
        # Delay saving because seller is intentionally not an editable form field.
        product = form.save(commit=False)
        # Assign ownership from the authenticated session, never from client data.
        product.seller = request.user
        # Run complete validation again now that the server-owned field is present.
        product.full_clean()
        product.save()
        messages.success(request, f"{product.name} was added to your inventory.")
        return redirect("products:seller_product_list")

    return render(
        request,
        "products/seller_product_form.html",
        {"form": form, "page_title": "Add a product", "submit_label": "Add product"},
    )


@seller_required
@require_http_methods(["GET", "POST"])
def seller_product_update(request, product_id):
    """Edit a product only when it belongs to the signed-in seller."""

    # Including seller in get_object_or_404 is the central ownership guarantee.
    product = get_object_or_404(Product, pk=product_id, seller=request.user)
    form = ProductForm(
        request.POST or None,
        request.FILES or None,
        instance=product,
    )

    if request.method == "POST" and form.is_valid():
        # ModelForm updates only whitelisted fields and preserves product ownership.
        updated_product = form.save()
        messages.success(request, f"{updated_product.name} was updated.")
        return redirect("products:seller_product_list")

    return render(
        request,
        "products/seller_product_form.html",
        {"form": form, "page_title": "Edit product", "submit_label": "Save changes"},
    )


@seller_required
@require_POST
def seller_product_delete(request, product_id):
    """Delete unused inventory or deactivate products referenced by past orders."""

    # The seller filter blocks crafted requests targeting another shop's product.
    product = get_object_or_404(Product, pk=product_id, seller=request.user)
    product_name = product.name

    product_has_references = (
        product.order_items.exists()
        or product.cart_items.exists()
        or product.removal_logs.exists()
    )

    if product_has_references:
        # Orders and buyer carts need the row, so use safe soft deletion instead.
        product.is_active = False
        product.save(update_fields=("is_active", "updated_at"))
        messages.success(
            request,
            f"{product_name} was deactivated because another record references it.",
        )
    else:
        # An unused product has no financial history and can be removed permanently.
        product.delete()
        messages.success(request, f"{product_name} was deleted.")

    return redirect("products:seller_product_list")


@seller_required
@require_POST
def seller_product_reactivate(request, product_id):
    """Allow a seller to return its own inactive, stocked product to the catalog."""

    # Ownership remains part of the database lookup for every state-changing action.
    product = get_object_or_404(Product, pk=product_id, seller=request.user)

    if product.removal_logs.exists():
        # A seller cannot override an administrator's recorded moderation decision.
        messages.error(
            request,
            "An administrator removed this product; contact support for review.",
        )
        return redirect("products:seller_product_list")

    product.is_active = True
    product.save(update_fields=("is_active", "updated_at"))
    messages.success(request, f"{product.name} is active again.")
    return redirect("products:seller_product_list")

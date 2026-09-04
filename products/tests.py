"""Test public catalog visibility and seller ownership enforcement."""

from decimal import Decimal

from django.test import TestCase
from django.urls import reverse

from accounts.models import User

from .models import Category, Product


class ProductCatalogTests(TestCase):
    """Verify buyers see only active products and can use server-validated filters."""

    @classmethod
    def setUpTestData(cls):
        """Create shared sellers, category, and products once for this test class."""

        cls.seller = User.objects.create_user(
            username="catalog_seller",
            password="StrongSellerPass123!",
            role=User.Role.SELLER,
            shop_name="Green Cart",
        )
        cls.other_seller = User.objects.create_user(
            username="other_seller",
            password="StrongSellerPass123!",
            role=User.Role.SELLER,
            shop_name="Other Shop",
        )
        cls.category = Category.objects.create(name="Home", slug="home")
        cls.active_product = Product.objects.create(
            seller=cls.seller,
            category=cls.category,
            name="Bamboo Lamp",
            description="A warm handmade lamp for a desk.",
            price=Decimal("899.00"),
            stock=8,
            is_active=True,
        )
        cls.inactive_product = Product.objects.create(
            seller=cls.seller,
            category=cls.category,
            name="Hidden Lamp",
            description="A moderated listing.",
            price=Decimal("499.00"),
            stock=4,
            is_active=False,
        )

    def test_public_catalog_hides_inactive_products(self):
        """Soft-deleted products should not appear in list or public detail routes."""

        list_response = self.client.get(reverse("products:product_list"))
        detail_response = self.client.get(
            reverse(
                "products:product_detail",
                kwargs={"product_id": self.inactive_product.pk},
            )
        )

        self.assertContains(list_response, self.active_product.name)
        self.assertNotContains(list_response, self.inactive_product.name)
        self.assertEqual(detail_response.status_code, 404)

    def test_search_matches_seller_shop_name(self):
        """A buyer should be able to discover products through a public shop name."""

        response = self.client.get(
            reverse("products:product_list"),
            {"query": "Green Cart"},
        )

        self.assertContains(response, self.active_product.name)

    def test_seller_cannot_edit_another_sellers_product(self):
        """Ownership in the ORM lookup should return 404 for a foreign product ID."""

        self.client.force_login(self.other_seller)
        response = self.client.get(
            reverse(
                "products:seller_product_update",
                kwargs={"product_id": self.active_product.pk},
            )
        )

        self.assertEqual(response.status_code, 404)

    def test_seller_delete_deactivates_product_referenced_by_buyer_cart(self):
        """A product in a cart should soft-delete instead of raising PROTECT errors."""

        # Local imports keep this catalog test's normal setup focused on products.
        from orders.models import Cart, CartItem

        buyer = User.objects.create_user(
            username="cart_reference_buyer",
            password="StrongBuyerPass123!",
            role=User.Role.BUYER,
        )
        cart = Cart.objects.create(buyer=buyer)
        CartItem.objects.create(cart=cart, product=self.active_product, quantity=1)
        self.client.force_login(self.seller)
        response = self.client.post(
            reverse(
                "products:seller_product_delete",
                kwargs={"product_id": self.active_product.pk},
            )
        )
        self.active_product.refresh_from_db()

        self.assertRedirects(response, reverse("products:seller_product_list"))
        self.assertFalse(self.active_product.is_active)
        self.assertTrue(CartItem.objects.filter(cart=cart).exists())

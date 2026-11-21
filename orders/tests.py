from decimal import Decimal

from django.test import TestCase
from django.urls import reverse

from accounts.models import User
from products.models import Category, Product

from .models import CartItem, Order, OrderItem


class OrderPageTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.buyer = User.objects.create_user("buyer")
        cls.other_buyer = User.objects.create_user("other_buyer")
        cls.seller = User.objects.create_user(
            "seller", role=User.Role.SELLER, shop_name="Test Shop"
        )
        category = Category.objects.create(name="Lighting", slug="lighting")
        cls.product = Product.objects.create(
            seller=cls.seller,
            category=category,
            name="Reading lamp",
            price=Decimal("199.00"),
            stock=3,
        )

    def test_buyer_can_manage_cart_and_open_checkout_review(self):
        self.client.force_login(self.buyer)
        add_url = reverse("orders:add_to_cart", args=[self.product.pk])
        cart_url = reverse("orders:cart_detail")

        self.assertEqual(self.client.get(add_url).status_code, 405)
        self.client.post(add_url, {"quantity": 4})
        self.assertFalse(CartItem.objects.exists())
        self.assertRedirects(self.client.post(add_url, {"quantity": 2}), cart_url)
        item = CartItem.objects.get(cart__buyer=self.buyer)
        self.assertEqual(item.quantity, 2)
        self.assertEqual(self.client.get(cart_url).context["cart_item_count"], 2)

        update_url = reverse("orders:update_cart_item", args=[item.pk])
        self.client.post(add_url, {"quantity": 2})
        self.client.post(update_url, {"quantity": 4})
        item.refresh_from_db()
        self.assertEqual(item.quantity, 2)

        self.assertRedirects(self.client.post(update_url, {"quantity": 1}), cart_url)
        review = self.client.get(reverse("orders:checkout_review"))
        self.assertContains(review, "Reading lamp")
        self.assertContains(review, "Online payments are currently unavailable.")
        self.assertEqual(review.context["cart"].total_amount, Decimal("199.00"))

        remove_url = reverse("orders:remove_cart_item", args=[item.pk])
        self.client.force_login(self.other_buyer)
        self.assertEqual(self.client.post(update_url, {"quantity": 3}).status_code, 404)
        self.assertEqual(self.client.post(remove_url).status_code, 404)
        self.client.force_login(self.buyer)
        self.assertRedirects(self.client.post(remove_url), cart_url)
        self.assertFalse(CartItem.objects.exists())

    def test_orders_are_available_only_to_the_appropriate_role_and_owner(self):
        order = Order.objects.create(
            buyer=self.buyer, total_amount=self.product.price, status=Order.Status.PAID
        )
        OrderItem.objects.create(
            order=order,
            product=self.product,
            seller=self.seller,
            quantity=1,
            price_at_purchase=self.product.price,
        )
        detail_url = reverse("orders:buyer_order_detail", args=[order.pk])
        history_url = reverse("orders:buyer_order_list")
        seller_url = reverse("orders:seller_order_list")
        self.assertRedirects(
            self.client.get(history_url), f"{reverse('accounts:login')}?next={history_url}"
        )

        self.client.force_login(self.buyer)
        self.assertContains(self.client.get(history_url), detail_url)
        self.assertContains(self.client.get(detail_url), "Reading lamp")
        self.assertEqual(self.client.get(seller_url).status_code, 403)

        self.client.force_login(self.other_buyer)
        self.assertNotContains(self.client.get(history_url), detail_url)
        self.assertEqual(self.client.get(detail_url).status_code, 404)

        self.client.force_login(self.seller)
        self.assertEqual(self.client.get(history_url).status_code, 403)
        self.assertContains(self.client.get(seller_url), "Reading lamp")
        self.assertContains(
            self.client.get(reverse("products:seller_dashboard")), "Reading lamp"
        )

"""Test seller authorization and ordered manual shipment transitions."""

from decimal import Decimal

from django.core.exceptions import PermissionDenied, ValidationError
from django.test import TestCase

from accounts.models import User
from orders.models import Order, OrderItem
from products.models import Category, Product

from .models import Shipment, TrackingHistory
from .services import update_shipment_status


class ShipmentTransitionTests(TestCase):
    """Verify only participating sellers can make legal forward status changes."""

    def setUp(self):
        """Create a paid order, participating seller, outsider, and packed shipment."""

        self.buyer = User.objects.create_user(
            username="tracking_buyer",
            password="StrongBuyerPass123!",
            role=User.Role.BUYER,
        )
        self.seller = User.objects.create_user(
            username="tracking_seller",
            password="StrongSellerPass123!",
            role=User.Role.SELLER,
            shop_name="Tracking Shop",
        )
        self.outsider = User.objects.create_user(
            username="outside_seller",
            password="StrongSellerPass123!",
            role=User.Role.SELLER,
            shop_name="Outside Shop",
        )
        category = Category.objects.create(name="Travel", slug="travel")
        product = Product.objects.create(
            seller=self.seller,
            category=category,
            name="Canvas Bag",
            description="A lightweight travel bag.",
            price=Decimal("1200.00"),
            stock=3,
        )
        self.order = Order.objects.create(
            buyer=self.buyer,
            total_amount=Decimal("1200.00"),
            status=Order.Status.PAID,
        )
        OrderItem.objects.create(
            order=self.order,
            product=product,
            seller=self.seller,
            quantity=1,
            price_at_purchase=Decimal("1200.00"),
        )
        self.shipment = Shipment.objects.create(order=self.order)
        TrackingHistory.objects.create(
            shipment=self.shipment,
            status=Shipment.Status.PACKED,
            note="Initial packed state.",
        )

    def test_participating_seller_can_advance_to_shipped(self):
        """A valid update should change shipment, append history, and sync order."""

        updated_shipment = update_shipment_status(
            self.shipment.pk,
            self.seller,
            Shipment.Status.SHIPPED,
        )
        self.order.refresh_from_db()

        self.assertEqual(updated_shipment.current_status, Shipment.Status.SHIPPED)
        self.assertEqual(updated_shipment.updated_by, self.seller)
        self.assertEqual(self.order.status, Order.Status.SHIPPED)
        self.assertEqual(self.shipment.history.count(), 2)

    def test_seller_cannot_skip_directly_from_packed_to_delivered(self):
        """A crafted transition should fail and leave shipment history unchanged."""

        with self.assertRaises(ValidationError):
            update_shipment_status(
                self.shipment.pk,
                self.seller,
                Shipment.Status.DELIVERED,
            )

        self.shipment.refresh_from_db()
        self.assertEqual(self.shipment.current_status, Shipment.Status.PACKED)
        self.assertEqual(self.shipment.history.count(), 1)

    def test_non_participating_seller_cannot_update_shipment(self):
        """A seller with no order line should be rejected by the service layer."""

        with self.assertRaises(PermissionDenied):
            update_shipment_status(
                self.shipment.pk,
                self.outsider,
                Shipment.Status.SHIPPED,
            )

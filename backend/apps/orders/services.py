from decimal import Decimal
from django.db import transaction
from rest_framework.exceptions import ValidationError
from apps.catalog.models import Product
from apps.cart.models import Cart
from apps.payments.models import Payment
from apps.payments.services import MockPaymentService
from apps.common.exceptions import (
    StockUnavailableException,
    PaymentFailedException,
    InvalidStatusTransitionException,
)
from .models import Order, OrderItem, OrderStatusHistory

class CheckoutService:
    @classmethod
    def execute_checkout(cls, user, shipping_address: str, payment_token: str, idempotency_key: str):
        """
        Executes atomic checkout with row-level locking, idempotency check,
        server-side price calculation, and mock payment simulation.
        """
        if not idempotency_key:
            raise ValidationError({'detail': 'Idempotency-Key header is required.'})

        if not shipping_address or not shipping_address.strip():
            raise ValidationError({'detail': 'Shipping address cannot be empty.'})

        # 1. Check idempotency: if order with this key already exists for user, return it
        existing_order = Order.objects.filter(
            user=user,
            idempotency_key=idempotency_key
        ).first()
        if existing_order:
            return existing_order, False  # Already processed

        # 2. Begin atomic transaction
        with transaction.atomic():
            cart = Cart.objects.filter(user=user).first()
            if not cart or not cart.items.exists():
                raise ValidationError({'detail': 'Cart is empty. Add products before checkout.'})

            cart_items = list(cart.items.select_related('product').all())
            product_ids = [item.product_id for item in cart_items]

            # 3. Row-level Lock on Products (SELECT ... FOR UPDATE)
            # This serializes concurrent checkouts attempting to buy the same product
            locked_products_qs = Product.objects.select_for_update().filter(id__in=product_ids)
            locked_products = {p.id: p for p in locked_products_qs}

            total_amount = Decimal('0.00')
            items_to_create = []

            # 4. Verify stock and calculate totals
            for item in cart_items:
                product = locked_products.get(item.product_id)
                if not product or not product.is_active:
                    raise ValidationError({'detail': f'Product is unavailable or has been removed.'})

                if product.stock_quantity < item.quantity:
                    raise StockUnavailableException(
                        f"Not enough stock for: {product.name} (available: {product.stock_quantity})."
                    )

                line_amount = product.price * item.quantity
                total_amount += line_amount

                items_to_create.append({
                    'product': product,
                    'product_name': product.name,
                    'unit_price': product.price,
                    'quantity': item.quantity,
                })

            # 5. Create Order with status 'pending'
            order = Order.objects.create(
                user=user,
                total_amount=total_amount,
                shipping_address=shipping_address.strip(),
                idempotency_key=idempotency_key,
                status='pending'
            )

            # 6. Create Order Items (snapshotting product name and price)
            for it in items_to_create:
                OrderItem.objects.create(
                    order=order,
                    product=it['product'],
                    product_name=it['product_name'],
                    unit_price=it['unit_price'],
                    quantity=it['quantity']
                )

            # 7. Execute Mock Payment
            payment_result = MockPaymentService.charge(order=order, token=payment_token)

            if not payment_result.is_success:
                # Payment failed -> raise PaymentFailedException to rollback transaction
                raise PaymentFailedException(payment_result.error_message)

            # Payment succeeded: deduct stock
            for it in items_to_create:
                prod = it['product']
                prod.stock_quantity -= it['quantity']
                prod.save(update_fields=['stock_quantity', 'updated_at'])

            # Record Payment
            Payment.objects.create(
                order=order,
                amount=total_amount,
                status='success',
                provider_ref=payment_result.provider_ref
            )

            # Update Order status to 'paid'
            order.status = 'paid'
            order.save(update_fields=['status', 'updated_at'])

            OrderStatusHistory.objects.create(
                order=order,
                old_status='pending',
                new_status='paid',
                changed_by=user
            )

            # 8. Empty user's cart
            cart.items.all().delete()

            return order, True


class OrderStatusService:
    ALLOWED_TRANSITIONS = {
        'pending': ['paid', 'cancelled'],
        'paid': ['shipped', 'cancelled'],
        'shipped': ['delivered'],
        'delivered': [],
        'cancelled': [],
    }

    @classmethod
    def transition_status(cls, order: Order, new_status: str, changed_by=None):
        old_status = order.status
        allowed = cls.ALLOWED_TRANSITIONS.get(old_status, [])

        if new_status not in allowed:
            raise InvalidStatusTransitionException(
                f"Cannot change order status from '{old_status}' to '{new_status}'."
            )

        with transaction.atomic():
            # If cancelling an already 'paid' order, return stock to products
            if new_status == 'cancelled' and old_status == 'paid':
                order_items = order.items.select_related('product').all()
                product_ids = [item.product_id for item in order_items]
                locked_products = {
                    p.id: p for p in Product.objects.select_for_update().filter(id__in=product_ids)
                }
                for item in order_items:
                    prod = locked_products.get(item.product_id)
                    if prod:
                        prod.stock_quantity += item.quantity
                        prod.save(update_fields=['stock_quantity', 'updated_at'])

            order.status = new_status
            order.save(update_fields=['status', 'updated_at'])

            OrderStatusHistory.objects.create(
                order=order,
                old_status=old_status,
                new_status=new_status,
                changed_by=changed_by
            )

        return order

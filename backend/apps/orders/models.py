from django.db import models
from django.conf import settings
from apps.catalog.models import Product

class Order(models.Model):
    STATUS_CHOICES = (
        ('pending', 'Pending'),
        ('paid', 'Paid'),
        ('shipped', 'Shipped'),
        ('delivered', 'Delivered'),
        ('cancelled', 'Cancelled'),
    )

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.RESTRICT,
        related_name='orders',
        db_index=True
    )
    status = models.CharField(
        max_length=12,
        choices=STATUS_CHOICES,
        default='pending',
        db_index=True
    )
    total_amount = models.DecimalField(max_digits=12, decimal_places=2)
    shipping_address = models.TextField()
    idempotency_key = models.CharField(max_length=64, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'orders'
        ordering = ['-created_at']
        constraints = [
            models.CheckConstraint(
                check=models.Q(status__in=['pending', 'paid', 'shipped', 'delivered', 'cancelled']),
                name='check_order_status_valid'
            ),
            models.CheckConstraint(
                check=models.Q(total_amount__gte=0),
                name='check_order_total_amount_positive'
            ),
            models.UniqueConstraint(
                fields=['user', 'idempotency_key'],
                name='unique_order_user_idempotency'
            ),
        ]
        indexes = [
            models.Index(fields=['user', '-created_at'], name='idx_order_user_created'),
            models.Index(fields=['status'], name='idx_order_status'),
        ]

    def __str__(self):
        return f"Order #{self.id} - {self.user.email} [{self.status}]"

class OrderItem(models.Model):
    order = models.ForeignKey(
        Order,
        on_delete=models.CASCADE,
        related_name='items'
    )
    product = models.ForeignKey(
        Product,
        on_delete=models.PROTECT,
        related_name='order_items'
    )
    product_name = models.CharField(max_length=200)
    unit_price = models.DecimalField(max_digits=10, decimal_places=2)
    quantity = models.IntegerField()

    class Meta:
        db_table = 'order_items'
        constraints = [
            models.CheckConstraint(
                check=models.Q(quantity__gt=0),
                name='check_order_item_quantity_positive'
            ),
            models.CheckConstraint(
                check=models.Q(unit_price__gte=0),
                name='check_order_item_price_positive'
            ),
        ]

    def __str__(self):
        return f"{self.quantity}x {self.product_name} @ {self.unit_price} (Order #{self.order_id})"

    @property
    def line_total(self):
        return self.unit_price * self.quantity

class OrderStatusHistory(models.Model):
    order = models.ForeignKey(
        Order,
        on_delete=models.CASCADE,
        related_name='status_history'
    )
    old_status = models.CharField(max_length=12)
    new_status = models.CharField(max_length=12)
    changed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )
    changed_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'order_status_history'
        ordering = ['-changed_at']

    def __str__(self):
        return f"Order #{self.order_id}: {self.old_status} -> {self.new_status}"

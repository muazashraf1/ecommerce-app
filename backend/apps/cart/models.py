from django.db import models
from django.conf import settings
from apps.catalog.models import Product

class Cart(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='cart'
    )
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'carts'

    def __str__(self):
        return f"Cart of {self.user.email}"

class CartItem(models.Model):
    cart = models.ForeignKey(
        Cart,
        on_delete=models.CASCADE,
        related_name='items'
    )
    product = models.ForeignKey(
        Product,
        on_delete=models.CASCADE,
        related_name='cart_items'
    )
    quantity = models.IntegerField(default=1)

    class Meta:
        db_table = 'cart_items'
        constraints = [
            models.CheckConstraint(
                check=models.Q(quantity__gt=0),
                name='check_cart_item_quantity_positive'
            ),
            models.UniqueConstraint(
                fields=['cart', 'product'],
                name='unique_cart_product'
            ),
        ]

    def __str__(self):
        return f"{self.quantity}x {self.product.name} (Cart #{self.cart.id})"

    @property
    def line_total(self):
        return self.product.price * self.quantity

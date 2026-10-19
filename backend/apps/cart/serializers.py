from rest_framework import serializers
from decimal import Decimal
from apps.catalog.models import Product
from apps.catalog.serializers import ProductListSerializer
from .models import Cart, CartItem

class CartItemSerializer(serializers.ModelSerializer):
    product = ProductListSerializer(read_only=True)
    product_id = serializers.IntegerField(write_only=True)
    line_total = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)
    unit_price = serializers.DecimalField(source='product.price', max_digits=10, decimal_places=2, read_only=True)
    is_in_stock = serializers.BooleanField(source='product.is_in_stock', read_only=True)
    available_stock = serializers.IntegerField(source='product.stock_quantity', read_only=True)

    class Meta:
        model = CartItem
        fields = (
            'id', 'product', 'product_id', 'quantity', 'unit_price',
            'line_total', 'is_in_stock', 'available_stock'
        )

class CartSerializer(serializers.ModelSerializer):
    items = CartItemSerializer(many=True, read_only=True)
    total_amount = serializers.SerializerMethodField()
    total_items = serializers.SerializerMethodField()

    class Meta:
        model = Cart
        fields = ('id', 'items', 'total_amount', 'total_items', 'updated_at')

    def get_total_amount(self, obj):
        total = sum(item.line_total for item in obj.items.all())
        return f"{total:.2f}"

    def get_total_items(self, obj):
        return sum(item.quantity for item in obj.items.all())

class AddToCartSerializer(serializers.Serializer):
    product_id = serializers.IntegerField()
    quantity = serializers.IntegerField(min_value=1, default=1)

    def validate_product_id(self, value):
        try:
            product = Product.objects.get(id=value, is_active=True)
        except Product.DoesNotExist:
            raise serializers.ValidationError("Product not found or inactive.")
        return value

    def validate(self, attrs):
        product = Product.objects.get(id=attrs['product_id'])
        requested_qty = attrs.get('quantity', 1)

        # Check existing cart quantity
        request = self.context.get('request')
        if request and request.user.is_authenticated:
            cart, _ = Cart.objects.get_or_create(user=request.user)
            existing_item = CartItem.objects.filter(cart=cart, product=product).first()
            if existing_item:
                requested_qty += existing_item.quantity

        if requested_qty > product.stock_quantity:
            raise serializers.ValidationError(
                f"Requested quantity ({requested_qty}) exceeds available stock ({product.stock_quantity})."
            )
        return attrs

class UpdateCartItemSerializer(serializers.Serializer):
    quantity = serializers.IntegerField(min_value=1)

    def validate_quantity(self, value):
        cart_item = self.context.get('cart_item')
        if cart_item:
            if value > cart_item.product.stock_quantity:
                raise serializers.ValidationError(
                    f"Quantity ({value}) exceeds available stock ({cart_item.product.stock_quantity})."
                )
        return value

from rest_framework import serializers
from .models import Order, OrderItem, OrderStatusHistory

class CheckoutPaymentSerializer(serializers.Serializer):
    method = serializers.CharField(default='mock_card')
    token = serializers.CharField(required=True)

class CheckoutRequestSerializer(serializers.Serializer):
    shipping_address = serializers.CharField(required=True, min_length=5)
    payment = CheckoutPaymentSerializer(required=True)

class OrderItemSerializer(serializers.ModelSerializer):
    name = serializers.CharField(source='product_name', read_only=True)
    unit_price = serializers.DecimalField(max_digits=10, decimal_places=2, read_only=True)
    line_total = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)

    class Meta:
        model = OrderItem
        fields = ('product_id', 'name', 'unit_price', 'quantity', 'line_total')

class OrderStatusHistorySerializer(serializers.ModelSerializer):
    changed_by_name = serializers.CharField(source='changed_by.full_name', read_only=True)

    class Meta:
        model = OrderStatusHistory
        fields = ('id', 'old_status', 'new_status', 'changed_by_name', 'changed_at')

class OrderSerializer(serializers.ModelSerializer):
    order_id = serializers.IntegerField(source='id', read_only=True)
    items = OrderItemSerializer(many=True, read_only=True)
    payment = serializers.SerializerMethodField()
    status_history = OrderStatusHistorySerializer(many=True, read_only=True)
    user_email = serializers.EmailField(source='user.email', read_only=True)

    class Meta:
        model = Order
        fields = (
            'order_id', 'status', 'total_amount', 'shipping_address',
            'items', 'payment', 'status_history', 'user_email', 'created_at', 'updated_at'
        )

    def get_payment(self, obj):
        latest_payment = obj.payments.order_by('-created_at').first()
        if latest_payment:
            return {
                'status': latest_payment.status,
                'provider_ref': latest_payment.provider_ref,
            }
        return None

class OrderStatusUpdateSerializer(serializers.Serializer):
    status = serializers.ChoiceField(choices=['pending', 'paid', 'shipped', 'delivered', 'cancelled'])

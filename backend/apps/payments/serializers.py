from rest_framework import serializers
from .models import Payment

class PaymentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Payment
        fields = ('id', 'order_id', 'amount', 'status', 'provider_ref', 'created_at')
        read_only_fields = fields

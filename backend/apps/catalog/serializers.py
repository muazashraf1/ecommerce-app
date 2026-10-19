from rest_framework import serializers
from .models import Category, Product

class CategorySerializer(serializers.ModelSerializer):
    products_count = serializers.IntegerField(source='products.count', read_only=True)

    class Meta:
        model = Category
        fields = ('id', 'name', 'slug', 'products_count')

class ProductListSerializer(serializers.ModelSerializer):
    category_name = serializers.CharField(source='category.name', read_only=True)
    category_slug = serializers.CharField(source='category.slug', read_only=True)
    is_in_stock = serializers.BooleanField(read_only=True)

    class Meta:
        model = Product
        fields = (
            'id', 'category', 'category_name', 'category_slug',
            'name', 'slug', 'price', 'stock_quantity', 'image_url',
            'is_in_stock', 'is_active', 'created_at'
        )

class ProductDetailSerializer(serializers.ModelSerializer):
    category = CategorySerializer(read_only=True)
    category_id = serializers.PrimaryKeyRelatedField(
        queryset=Category.objects.all(), source='category', write_only=True
    )
    is_in_stock = serializers.BooleanField(read_only=True)

    class Meta:
        model = Product
        fields = (
            'id', 'category', 'category_id', 'name', 'slug',
            'description', 'price', 'stock_quantity', 'image_url',
            'is_in_stock', 'is_active', 'created_at', 'updated_at'
        )

class StockUpdateSerializer(serializers.Serializer):
    stock_quantity = serializers.IntegerField(min_value=0)

    def update(self, instance, validated_data):
        instance.stock_quantity = validated_data['stock_quantity']
        instance.save(update_fields=['stock_quantity', 'updated_at'])
        return instance

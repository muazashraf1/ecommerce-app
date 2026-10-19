from rest_framework import generics, permissions, status
from rest_framework.response import Response
from django.shortcuts import get_object_or_404
from apps.common.permissions import IsCustomerRole
from apps.catalog.models import Product
from .models import Cart, CartItem
from .serializers import (
    CartSerializer,
    CartItemSerializer,
    AddToCartSerializer,
    UpdateCartItemSerializer,
)

class CartView(generics.RetrieveAPIView):
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = CartSerializer

    def get_object(self):
        if getattr(self, 'swagger_fake_view', False) or not self.request.user.is_authenticated:
            return None
        cart, _ = Cart.objects.prefetch_related('items__product__category').get_or_create(
            user=self.request.user
        )
        return cart

class CartItemCreateView(generics.CreateAPIView):
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = AddToCartSerializer

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)

        product_id = serializer.validated_data['product_id']
        quantity = serializer.validated_data['quantity']

        cart, _ = Cart.objects.get_or_create(user=request.user)
        product = Product.objects.get(id=product_id)

        cart_item, created = CartItem.objects.get_or_create(
            cart=cart,
            product=product,
            defaults={'quantity': quantity}
        )
        if not created:
            cart_item.quantity += quantity
            cart_item.save(update_fields=['quantity'])

        cart_item.refresh_from_db()
        return Response(CartItemSerializer(cart_item).data, status=status.HTTP_201_CREATED)

class CartItemDetailView(generics.GenericAPIView):
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = UpdateCartItemSerializer
    queryset = CartItem.objects.all()

    def get_object(self):
        if getattr(self, 'swagger_fake_view', False) or not self.request.user.is_authenticated:
            return None
        cart, _ = Cart.objects.get_or_create(user=self.request.user)
        return get_object_or_404(CartItem, id=self.kwargs['id'], cart=cart)

    def patch(self, request, *args, **kwargs):
        cart_item = self.get_object()
        serializer = UpdateCartItemSerializer(
            data=request.data,
            context={'cart_item': cart_item}
        )
        serializer.is_valid(raise_exception=True)
        cart_item.quantity = serializer.validated_data['quantity']
        cart_item.save(update_fields=['quantity'])
        return Response(CartItemSerializer(cart_item).data, status=status.HTTP_200_OK)

    def delete(self, request, *args, **kwargs):
        cart_item = self.get_object()
        cart_item.delete()
        return Response(
            {'detail': 'Item removed from cart successfully.'},
            status=status.HTTP_204_NO_CONTENT
        )

from rest_framework import generics, permissions, status
from rest_framework.response import Response
from rest_framework.exceptions import NotFound, PermissionDenied, ValidationError
from django.shortcuts import get_object_or_404
from apps.common.permissions import IsAdminRole
from .models import Order
from .services import CheckoutService, OrderStatusService
from .serializers import (
    CheckoutRequestSerializer,
    OrderSerializer,
    OrderStatusUpdateSerializer,
)

class CheckoutView(generics.GenericAPIView):
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = CheckoutRequestSerializer

    def post(self, request, *args, **kwargs):
        idempotency_key = (
            request.headers.get('Idempotency-Key') or
            request.META.get('HTTP_IDEMPOTENCY_KEY') or
            request.data.get('idempotency_key')
        )
        if not idempotency_key:
            return Response(
                {'detail': 'Idempotency-Key header is required for checkout.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        shipping_address = serializer.validated_data['shipping_address']
        payment_data = serializer.validated_data['payment']
        payment_token = payment_data.get('token', '')

        order, is_new = CheckoutService.execute_checkout(
            user=request.user,
            shipping_address=shipping_address,
            payment_token=payment_token,
            idempotency_key=str(idempotency_key).strip()
        )

        response_data = OrderSerializer(order).data
        response_status = status.HTTP_201_CREATED if is_new else status.HTTP_200_OK
        return Response(response_data, status=response_status)

class OrderListView(generics.ListAPIView):
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = OrderSerializer
    queryset = Order.objects.all()

    def get_queryset(self):
        if getattr(self, 'swagger_fake_view', False) or not self.request.user.is_authenticated:
            return Order.objects.none()
        return Order.objects.filter(user=self.request.user).prefetch_related(
            'items', 'payments', 'status_history'
        ).order_by('-created_at')

class OrderDetailView(generics.RetrieveAPIView):
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = OrderSerializer
    lookup_field = 'id'
    queryset = Order.objects.all()

    def get_queryset(self):
        if getattr(self, 'swagger_fake_view', False) or not self.request.user.is_authenticated:
            return Order.objects.none()
        # Admin can view all; Customer can only see their own
        if self.request.user.role == 'admin' or self.request.user.is_staff:
            return Order.objects.all().prefetch_related('items', 'payments', 'status_history')
        # Return 404 if looking for another user's order to hide existence
        return Order.objects.filter(user=self.request.user).prefetch_related(
            'items', 'payments', 'status_history'
        )

    def get_object(self):
        queryset = self.get_queryset()
        try:
            return queryset.get(id=self.kwargs['id'])
        except Order.DoesNotExist:
            raise NotFound(detail="Order not found.")

class OrderCancelView(generics.GenericAPIView):
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = OrderSerializer
    lookup_field = 'id'

    def post(self, request, *args, **kwargs):
        # Admin or Owner
        if request.user.role == 'admin' or request.user.is_staff:
            order = get_object_or_404(Order, id=self.kwargs['id'])
        else:
            try:
                order = Order.objects.get(id=self.kwargs['id'], user=request.user)
            except Order.DoesNotExist:
                raise NotFound(detail="Order not found.")

        updated_order = OrderStatusService.transition_status(
            order=order,
            new_status='cancelled',
            changed_by=request.user
        )
        return Response(OrderSerializer(updated_order).data, status=status.HTTP_200_OK)

class AdminOrderListView(generics.ListAPIView):
    permission_classes = [IsAdminRole]
    serializer_class = OrderSerializer

    def get_queryset(self):
        qs = Order.objects.all().select_related('user').prefetch_related(
            'items', 'payments', 'status_history'
        ).order_by('-created_at')
        status_param = self.request.query_params.get('status')
        if status_param:
            qs = qs.filter(status=status_param)
        return qs

class AdminOrderStatusUpdateView(generics.GenericAPIView):
    permission_classes = [IsAdminRole]
    serializer_class = OrderStatusUpdateSerializer
    lookup_field = 'id'

    def patch(self, request, *args, **kwargs):
        order = get_object_or_404(Order, id=self.kwargs['id'])
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        new_status = serializer.validated_data['status']
        updated_order = OrderStatusService.transition_status(
            order=order,
            new_status=new_status,
            changed_by=request.user
        )
        return Response(OrderSerializer(updated_order).data, status=status.HTTP_200_OK)

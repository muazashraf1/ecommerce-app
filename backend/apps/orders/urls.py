from django.urls import path
from .views import (
    CheckoutView,
    OrderListView,
    OrderDetailView,
    OrderCancelView,
    AdminOrderListView,
    AdminOrderStatusUpdateView,
)

urlpatterns = [
    # Customer endpoints
    path('checkout/', CheckoutView.as_view(), name='checkout'),
    path('orders/', OrderListView.as_view(), name='order-list'),
    path('orders/<int:id>/', OrderDetailView.as_view(), name='order-detail'),
    path('orders/<int:id>/cancel/', OrderCancelView.as_view(), name='order-cancel'),

    # Admin order management endpoints
    path('admin/orders/', AdminOrderListView.as_view(), name='admin-order-list'),
    path('admin/orders/<int:id>/status/', AdminOrderStatusUpdateView.as_view(), name='admin-order-status-update'),
]

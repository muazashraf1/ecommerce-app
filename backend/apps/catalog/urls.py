from django.urls import path
from .views import (
    CategoryListView,
    ProductListCreateView,
    ProductDetailView,
    ProductStockUpdateView,
)

urlpatterns = [
    path('categories/', CategoryListView.as_view(), name='category-list'),
    path('products/', ProductListCreateView.as_view(), name='product-list'),
    path('products/<int:id>/', ProductDetailView.as_view(), name='product-detail'),
    path('products/<int:id>/stock/', ProductStockUpdateView.as_view(), name='product-stock-update'),
]

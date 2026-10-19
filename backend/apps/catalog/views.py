from rest_framework import generics, permissions, status, filters
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend
from apps.common.permissions import IsAdminRole
from .models import Category, Product
from .serializers import (
    CategorySerializer,
    ProductListSerializer,
    ProductDetailSerializer,
    StockUpdateSerializer,
)
from .filters import ProductFilter

class CategoryListView(generics.ListCreateAPIView):
    queryset = Category.objects.all().prefetch_related('products')
    serializer_class = CategorySerializer

    def get_permissions(self):
        if self.request.method == 'POST':
            return [IsAdminRole()]
        return [permissions.AllowAny()]

class ProductListCreateView(generics.ListCreateAPIView):
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_class = ProductFilter
    search_fields = ['name', 'description']
    ordering_fields = ['price', 'created_at', 'stock_quantity']
    ordering = ['-created_at']

    def get_permissions(self):
        if self.request.method == 'POST':
            return [IsAdminRole()]
        return [permissions.AllowAny()]

    def get_serializer_class(self):
        if self.request.method == 'POST':
            return ProductDetailSerializer
        return ProductListSerializer

    def get_queryset(self):
        # Public gets only active products; Admins can see all
        user = self.request.user
        if user and user.is_authenticated and (user.role == 'admin' or user.is_staff):
            return Product.objects.all().select_related('category')
        return Product.objects.filter(is_active=True).select_related('category')

class ProductDetailView(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = ProductDetailSerializer
    lookup_field = 'id'

    def get_permissions(self):
        if self.request.method in ['PUT', 'PATCH', 'DELETE']:
            return [IsAdminRole()]
        return [permissions.AllowAny()]

    def get_queryset(self):
        user = self.request.user
        if user and user.is_authenticated and (user.role == 'admin' or user.is_staff):
            return Product.objects.all().select_related('category')
        return Product.objects.filter(is_active=True).select_related('category')

    def perform_destroy(self, instance):
        # Soft-delete requirement from project PDF
        instance.is_active = False
        instance.save(update_fields=['is_active', 'updated_at'])

class ProductStockUpdateView(generics.GenericAPIView):
    permission_classes = [IsAdminRole]
    serializer_class = StockUpdateSerializer
    queryset = Product.objects.all()
    lookup_field = 'id'

    def patch(self, request, *args, **kwargs):
        product = self.get_object()
        serializer = self.get_serializer(product, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(ProductDetailSerializer(product).data, status=status.HTTP_200_OK)

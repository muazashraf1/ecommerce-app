import pytest
from decimal import Decimal
from rest_framework import status
from apps.catalog.models import Product

@pytest.mark.django_db
def test_list_categories(api_client, category, category_audio):
    response = api_client.get('/api/v1/categories/')
    assert response.status_code == status.HTTP_200_OK
    slugs = [c['slug'] for c in response.data['results']] if 'results' in response.data else [c['slug'] for c in response.data]
    assert 'electronics' in slugs
    assert 'audio' in slugs

@pytest.mark.django_db
def test_list_active_products(api_client, in_stock_product, single_stock_product):
    response = api_client.get('/api/v1/products/')
    assert response.status_code == status.HTTP_200_OK
    assert response.data['count'] >= 2

@pytest.mark.django_db
def test_search_products_by_name(api_client, in_stock_product, single_stock_product):
    response = api_client.get('/api/v1/products/?search=Vintage')
    assert response.status_code == status.HTTP_200_OK
    assert response.data['count'] == 1
    assert response.data['results'][0]['name'] == 'Rare Vintage Keyboard'

@pytest.mark.django_db
def test_filter_products_by_category(api_client, in_stock_product, category_audio):
    Product.objects.create(
        category=category_audio,
        name='Studio Headphones',
        slug='studio-headphones',
        price=Decimal('8000.00'),
        stock_quantity=5,
        is_active=True
    )
    response = api_client.get('/api/v1/products/?category=audio')
    assert response.status_code == status.HTTP_200_OK
    assert response.data['count'] == 1
    assert response.data['results'][0]['slug'] == 'studio-headphones'

@pytest.mark.django_db
def test_filter_products_by_price_range(api_client, in_stock_product, single_stock_product):
    response = api_client.get('/api/v1/products/?min_price=1000&max_price=3000')
    assert response.status_code == status.HTTP_200_OK
    assert response.data['count'] == 1
    assert response.data['results'][0]['id'] == single_stock_product.id

@pytest.mark.django_db
def test_out_of_stock_product_shows_status(api_client, out_of_stock_product):
    response = api_client.get(f'/api/v1/products/{out_of_stock_product.id}/')
    assert response.status_code == status.HTTP_200_OK
    assert response.data['stock_quantity'] == 0
    assert response.data['is_in_stock'] is False

@pytest.mark.django_db
def test_inactive_product_hidden_from_public(api_client, category):
    inactive = Product.objects.create(
        category=category,
        name='Secret Prototype',
        slug='secret-prototype',
        price=Decimal('9999.00'),
        stock_quantity=10,
        is_active=False
    )
    # Public request
    response = api_client.get('/api/v1/products/')
    ids = [p['id'] for p in response.data['results']]
    assert inactive.id not in ids

@pytest.mark.django_db
def test_customer_cannot_create_product(customer_client, category):
    payload = {
        'category_id': category.id,
        'name': 'Hacked Product',
        'price': '100.00',
        'stock_quantity': 5
    }
    response = customer_client.post('/api/v1/products/', payload)
    assert response.status_code == status.HTTP_403_FORBIDDEN

@pytest.mark.django_db
def test_admin_can_create_product(admin_client, category):
    payload = {
        'category_id': category.id,
        'name': 'Official Admin Product',
        'slug': 'official-admin-product',
        'price': '1250.00',
        'stock_quantity': 25
    }
    response = admin_client.post('/api/v1/products/', payload)
    assert response.status_code == status.HTTP_201_CREATED
    assert response.data['name'] == 'Official Admin Product'

@pytest.mark.django_db
def test_admin_can_update_stock(admin_client, in_stock_product):
    response = admin_client.patch(
        f'/api/v1/products/{in_stock_product.id}/stock/',
        {'stock_quantity': 45}
    )
    assert response.status_code == status.HTTP_200_OK
    in_stock_product.refresh_from_db()
    assert in_stock_product.stock_quantity == 45

@pytest.mark.django_db
def test_admin_stock_negative_rejected(admin_client, in_stock_product):
    response = admin_client.patch(
        f'/api/v1/products/{in_stock_product.id}/stock/',
        {'stock_quantity': -10}
    )
    assert response.status_code == status.HTTP_400_BAD_REQUEST

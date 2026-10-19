import pytest
import uuid
from decimal import Decimal
from rest_framework import status
from apps.catalog.models import Product
from apps.orders.models import Order, OrderItem
from apps.cart.models import Cart

@pytest.mark.django_db
def test_checkout_success(customer_client, in_stock_product):
    # Add 2 items to cart (initial stock: 10)
    customer_client.post('/api/v1/cart/items/', {'product_id': in_stock_product.id, 'quantity': 2}, format='json')

    key = str(uuid.uuid4())
    payload = {
        'shipping_address': 'House 10, Street 5, Lahore',
        'payment': {'method': 'mock_card', 'token': 'tok_success'}
    }
    response = customer_client.post('/api/v1/checkout/', payload, format='json', HTTP_IDEMPOTENCY_KEY=key)

    assert response.status_code == status.HTTP_201_CREATED
    assert response.data['status'] == 'paid'
    assert response.data['total_amount'] == '1000.00'
    assert len(response.data['items']) == 1
    assert response.data['payment']['status'] == 'success'
    assert response.data['payment']['provider_ref'].startswith('mock_')

    # Verify stock deducted from 10 to 8
    in_stock_product.refresh_from_db()
    assert in_stock_product.stock_quantity == 8

    # Verify cart emptied
    cart_resp = customer_client.get('/api/v1/cart/')
    assert len(cart_resp.data['items']) == 0

@pytest.mark.django_db
def test_checkout_empty_cart_fails(customer_client):
    key = str(uuid.uuid4())
    payload = {
        'shipping_address': 'Flat 4B, Clifton, Karachi',
        'payment': {'method': 'mock_card', 'token': 'tok_success'}
    }
    response = customer_client.post('/api/v1/checkout/', payload, format='json', HTTP_IDEMPOTENCY_KEY=key)
    assert response.status_code == status.HTTP_400_BAD_REQUEST

@pytest.mark.django_db
def test_checkout_missing_idempotency_key_fails(customer_client, in_stock_product):
    customer_client.post('/api/v1/cart/items/', {'product_id': in_stock_product.id, 'quantity': 1}, format='json')
    payload = {
        'shipping_address': 'Islamabad',
        'payment': {'method': 'mock_card', 'token': 'tok_success'}
    }
    response = customer_client.post('/api/v1/checkout/', payload, format='json') # No header
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert 'Idempotency-Key' in response.data['detail']

@pytest.mark.django_db
def test_checkout_empty_shipping_address_fails(customer_client, in_stock_product):
    customer_client.post('/api/v1/cart/items/', {'product_id': in_stock_product.id, 'quantity': 1}, format='json')
    key = str(uuid.uuid4())
    payload = {
        'shipping_address': '',
        'payment': {'method': 'mock_card', 'token': 'tok_success'}
    }
    response = customer_client.post('/api/v1/checkout/', payload, format='json', HTTP_IDEMPOTENCY_KEY=key)
    assert response.status_code == status.HTTP_400_BAD_REQUEST

@pytest.mark.django_db
def test_price_snapshot_preserved_when_product_price_changes_later(customer_client, in_stock_product):
    # in_stock_product is 500.00
    customer_client.post('/api/v1/cart/items/', {'product_id': in_stock_product.id, 'quantity': 1}, format='json')

    key = str(uuid.uuid4())
    checkout_resp = customer_client.post('/api/v1/checkout/', {
        'shipping_address': 'F-7/2, Islamabad',
        'payment': {'method': 'mock_card', 'token': 'tok_success'}
    }, format='json', HTTP_IDEMPOTENCY_KEY=key)
    order_id = checkout_resp.data['order_id']

    # Now merchant increases product price to 999.00
    in_stock_product.price = Decimal('999.00')
    in_stock_product.save()

    # Fetch order details: must still be 500.00 (snapshot preserved)
    order_resp = customer_client.get(f'/api/v1/orders/{order_id}/')
    assert order_resp.status_code == status.HTTP_200_OK
    assert order_resp.data['items'][0]['unit_price'] == '500.00'
    assert order_resp.data['total_amount'] == '500.00'

@pytest.mark.django_db
def test_customer_cannot_view_other_users_order(customer_client, other_customer_client, in_stock_product):
    # Customer 1 makes an order
    customer_client.post('/api/v1/cart/items/', {'product_id': in_stock_product.id, 'quantity': 1}, format='json')
    resp = customer_client.post('/api/v1/checkout/', {
        'shipping_address': 'User 1 Address',
        'payment': {'method': 'mock_card', 'token': 'tok_success'}
    }, format='json', HTTP_IDEMPOTENCY_KEY=str(uuid.uuid4()))
    order_id = resp.data['order_id']

    # Customer 2 attempts to fetch Customer 1's order
    other_resp = other_customer_client.get(f'/api/v1/orders/{order_id}/')
    # Must return 404 to hide existence (Section 7.3)
    assert other_resp.status_code == status.HTTP_404_NOT_FOUND

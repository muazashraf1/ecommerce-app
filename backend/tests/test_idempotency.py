import pytest
import uuid
from rest_framework import status
from apps.orders.models import Order

@pytest.mark.django_db
def test_duplicate_checkout_returns_same_order(customer_client, in_stock_product):
    # Customer puts 2 items in cart (stock 10)
    customer_client.post('/api/v1/cart/items/', {'product_id': in_stock_product.id, 'quantity': 2}, format='json')

    idempotency_key = "idem-test-key-12345"
    payload = {
        'shipping_address': 'Sector G-11, Islamabad',
        'payment': {'method': 'mock_card', 'token': 'tok_success'}
    }

    # 1. First checkout call
    first_response = customer_client.post(
        '/api/v1/checkout/',
        payload,
        format='json',
        HTTP_IDEMPOTENCY_KEY=idempotency_key
    )
    assert first_response.status_code == status.HTTP_201_CREATED
    order_id = first_response.data['order_id']

    # 2. Second checkout call with EXACT same Idempotency-Key (simulating user double-click)
    second_response = customer_client.post(
        '/api/v1/checkout/',
        payload,
        format='json',
        HTTP_IDEMPOTENCY_KEY=idempotency_key
    )
    # AC5: Must return the existing order
    assert second_response.status_code == status.HTTP_200_OK
    assert second_response.data['order_id'] == order_id
    assert second_response.data['status'] == 'paid'

    # 3. Verify exactly ONE order in database
    assert Order.objects.filter(idempotency_key=idempotency_key).count() == 1

    # 4. Verify stock was deducted only once (10 - 2 = 8, not 6!)
    in_stock_product.refresh_from_db()
    assert in_stock_product.stock_quantity == 8

@pytest.mark.django_db
def test_different_idempotency_key_processes_independent_order(customer_client, in_stock_product):
    # Order 1
    customer_client.post('/api/v1/cart/items/', {'product_id': in_stock_product.id, 'quantity': 1}, format='json')
    resp1 = customer_client.post('/api/v1/checkout/', {
        'shipping_address': 'Peshawar',
        'payment': {'method': 'mock_card', 'token': 'tok_success'}
    }, format='json', HTTP_IDEMPOTENCY_KEY=str(uuid.uuid4()))
    assert resp1.status_code == status.HTTP_201_CREATED

    # Order 2
    customer_client.post('/api/v1/cart/items/', {'product_id': in_stock_product.id, 'quantity': 1}, format='json')
    resp2 = customer_client.post('/api/v1/checkout/', {
        'shipping_address': 'Peshawar',
        'payment': {'method': 'mock_card', 'token': 'tok_success'}
    }, format='json', HTTP_IDEMPOTENCY_KEY=str(uuid.uuid4()))
    assert resp2.status_code == status.HTTP_201_CREATED

    assert resp1.data['order_id'] != resp2.data['order_id']
    assert Order.objects.count() == 2

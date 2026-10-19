import pytest
import uuid
from rest_framework import status
from apps.orders.models import Order
from apps.cart.models import Cart

@pytest.mark.django_db
def test_mock_payment_failure_with_tok_fail(customer_client, in_stock_product):
    # Customer adds 2 items (stock is 10)
    customer_client.post('/api/v1/cart/items/', {'product_id': in_stock_product.id, 'quantity': 2}, format='json')

    key = str(uuid.uuid4())
    payload = {
        'shipping_address': 'Bahria Town, Rawalpindi',
        'payment': {'method': 'mock_card', 'token': 'tok_fail'}
    }
    response = customer_client.post('/api/v1/checkout/', payload, format='json', HTTP_IDEMPOTENCY_KEY=key)

    # Must return 402 Payment Required per PDF Section 7.2
    assert response.status_code == status.HTTP_402_PAYMENT_REQUIRED
    assert 'Payment failed' in response.data['detail']

    # AC7: Stock must remain untouched (still 10)
    in_stock_product.refresh_from_db()
    assert in_stock_product.stock_quantity == 10

    # AC7: Cart must NOT be cleared on payment failure
    cart_resp = customer_client.get('/api/v1/cart/')
    assert len(cart_resp.data['items']) == 1
    assert cart_resp.data['items'][0]['quantity'] == 2

    # AC7: No paid order created in DB
    assert Order.objects.filter(status='paid').count() == 0

@pytest.mark.django_db
def test_invalid_token_fails_payment(customer_client, in_stock_product):
    customer_client.post('/api/v1/cart/items/', {'product_id': in_stock_product.id, 'quantity': 1}, format='json')
    response = customer_client.post('/api/v1/checkout/', {
        'shipping_address': 'Lahore',
        'payment': {'method': 'mock_card', 'token': 'garbage_token'}
    }, format='json', HTTP_IDEMPOTENCY_KEY=str(uuid.uuid4()))

    assert response.status_code == status.HTTP_402_PAYMENT_REQUIRED
    in_stock_product.refresh_from_db()
    assert in_stock_product.stock_quantity == 10

@pytest.mark.django_db
def test_retry_after_payment_failure_succeeds(customer_client, in_stock_product):
    customer_client.post('/api/v1/cart/items/', {'product_id': in_stock_product.id, 'quantity': 2}, format='json')

    # 1. First attempt fails
    key1 = str(uuid.uuid4())
    fail_resp = customer_client.post('/api/v1/checkout/', {
        'shipping_address': 'Multan',
        'payment': {'method': 'mock_card', 'token': 'tok_fail'}
    }, format='json', HTTP_IDEMPOTENCY_KEY=key1)
    assert fail_resp.status_code == status.HTTP_402_PAYMENT_REQUIRED

    # 2. Second attempt with valid token and new key succeeds
    key2 = str(uuid.uuid4())
    success_resp = customer_client.post('/api/v1/checkout/', {
        'shipping_address': 'Multan',
        'payment': {'method': 'mock_card', 'token': 'tok_success'}
    }, format='json', HTTP_IDEMPOTENCY_KEY=key2)
    assert success_resp.status_code == status.HTTP_201_CREATED
    assert success_resp.data['status'] == 'paid'

    # Now stock is deducted to 8
    in_stock_product.refresh_from_db()
    assert in_stock_product.stock_quantity == 8

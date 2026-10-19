import pytest
import uuid
from decimal import Decimal
from django.db import IntegrityError, transaction
from rest_framework import status
from apps.catalog.models import Product

@pytest.mark.django_db(transaction=True)
def test_two_buyers_last_item_concurrency(customer_client, other_customer_client, single_stock_product):
    """
    Simulates race condition: two customers both try to buy the last 1 item in stock.
    Only one must succeed; the second must fail with 409 Conflict.
    Stock must never go below 0.
    """
    assert single_stock_product.stock_quantity == 1

    # Customer 1 adds 1 to cart
    customer_client.post('/api/v1/cart/items/', {'product_id': single_stock_product.id, 'quantity': 1}, format='json')
    # Customer 2 adds 1 to cart
    other_customer_client.post('/api/v1/cart/items/', {'product_id': single_stock_product.id, 'quantity': 1}, format='json')

    payload1 = {
        'shipping_address': 'Address 1',
        'payment': {'method': 'mock_card', 'token': 'tok_success'}
    }
    payload2 = {
        'shipping_address': 'Address 2',
        'payment': {'method': 'mock_card', 'token': 'tok_success'}
    }

    # First checkout executes
    resp1 = customer_client.post(
        '/api/v1/checkout/',
        payload1,
        format='json',
        HTTP_IDEMPOTENCY_KEY=str(uuid.uuid4())
    )
    # Second checkout executes
    resp2 = other_customer_client.post(
        '/api/v1/checkout/',
        payload2,
        format='json',
        HTTP_IDEMPOTENCY_KEY=str(uuid.uuid4())
    )

    # Assertions
    assert resp1.status_code == status.HTTP_201_CREATED
    assert resp1.data['status'] == 'paid'

    # Second must receive 409 Conflict
    assert resp2.status_code == status.HTTP_409_CONFLICT
    assert 'Not enough stock' in resp2.data['detail']

    # Final stock in DB must be exactly 0 (never negative)
    single_stock_product.refresh_from_db()
    assert single_stock_product.stock_quantity == 0

@pytest.mark.django_db
def test_stock_cannot_be_negative_in_database(category):
    """
    Direct verification of database CHECK constraint: stock_quantity >= 0
    """
    with pytest.raises((IntegrityError, Exception)):
        with transaction.atomic():
            Product.objects.create(
                category=category,
                name='Illegal Negative Product',
                slug='illegal-negative-product',
                price=Decimal('100.00'),
                stock_quantity=-5
            )

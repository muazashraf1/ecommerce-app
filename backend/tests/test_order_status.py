import pytest
import uuid
from rest_framework import status
from apps.orders.models import Order

@pytest.mark.django_db
def test_admin_can_list_all_orders(admin_client, customer_client, in_stock_product):
    # Customer makes order
    customer_client.post('/api/v1/cart/items/', {'product_id': in_stock_product.id, 'quantity': 1}, format='json')
    customer_client.post('/api/v1/checkout/', {
        'shipping_address': 'Lahore',
        'payment': {'method': 'mock_card', 'token': 'tok_success'}
    }, format='json', HTTP_IDEMPOTENCY_KEY=str(uuid.uuid4()))

    response = admin_client.get('/api/v1/admin/orders/')
    assert response.status_code == status.HTTP_200_OK
    assert response.data['count'] >= 1

@pytest.mark.django_db
def test_customer_cannot_access_admin_orders(customer_client):
    response = customer_client.get('/api/v1/admin/orders/')
    # AC8: Customer calling admin route gets 403
    assert response.status_code == status.HTTP_403_FORBIDDEN

@pytest.mark.django_db
def test_valid_status_transition_sequence(admin_client, customer_client, in_stock_product):
    customer_client.post('/api/v1/cart/items/', {'product_id': in_stock_product.id, 'quantity': 1}, format='json')
    resp = customer_client.post('/api/v1/checkout/', {
        'shipping_address': 'Karachi',
        'payment': {'method': 'mock_card', 'token': 'tok_success'}
    }, format='json', HTTP_IDEMPOTENCY_KEY=str(uuid.uuid4()))
    order_id = resp.data['order_id']

    # Initial status is 'paid'
    assert resp.data['status'] == 'paid'

    # Admin changes to 'shipped'
    ship_resp = admin_client.patch(
        f'/api/v1/admin/orders/{order_id}/status/',
        {'status': 'shipped'},
        format='json'
    )
    assert ship_resp.status_code == status.HTTP_200_OK
    assert ship_resp.data['status'] == 'shipped'

    # Admin changes to 'delivered'
    deliv_resp = admin_client.patch(
        f'/api/v1/admin/orders/{order_id}/status/',
        {'status': 'delivered'},
        format='json'
    )
    assert deliv_resp.status_code == status.HTTP_200_OK
    assert deliv_resp.data['status'] == 'delivered'

@pytest.mark.django_db
def test_invalid_status_transition_rejected(admin_client, customer_client, in_stock_product):
    customer_client.post('/api/v1/cart/items/', {'product_id': in_stock_product.id, 'quantity': 1}, format='json')
    resp = customer_client.post('/api/v1/checkout/', {
        'shipping_address': 'Quetta',
        'payment': {'method': 'mock_card', 'token': 'tok_success'}
    }, format='json', HTTP_IDEMPOTENCY_KEY=str(uuid.uuid4()))
    order_id = resp.data['order_id']

    # Progress to delivered
    admin_client.patch(f'/api/v1/admin/orders/{order_id}/status/', {'status': 'shipped'}, format='json')
    admin_client.patch(f'/api/v1/admin/orders/{order_id}/status/', {'status': 'delivered'}, format='json')

    # Try invalid jump: delivered -> pending
    invalid_resp = admin_client.patch(
        f'/api/v1/admin/orders/{order_id}/status/',
        {'status': 'pending'},
        format='json'
    )
    # AC9: Invalid status jump must return 409
    assert invalid_resp.status_code == status.HTTP_409_CONFLICT
    assert 'Cannot change order status' in invalid_resp.data['detail']

@pytest.mark.django_db
def test_cancel_paid_order_restores_stock(customer_client, in_stock_product):
    # in_stock_product has 10
    customer_client.post('/api/v1/cart/items/', {'product_id': in_stock_product.id, 'quantity': 3}, format='json')
    resp = customer_client.post('/api/v1/checkout/', {
        'shipping_address': 'Sialkot',
        'payment': {'method': 'mock_card', 'token': 'tok_success'}
    }, format='json', HTTP_IDEMPOTENCY_KEY=str(uuid.uuid4()))
    order_id = resp.data['order_id']

    # Stock reduced to 7
    in_stock_product.refresh_from_db()
    assert in_stock_product.stock_quantity == 7

    # Cancel order
    cancel_resp = customer_client.post(f'/api/v1/orders/{order_id}/cancel/')
    assert cancel_resp.status_code == status.HTTP_200_OK
    assert cancel_resp.data['status'] == 'cancelled'

    # Section 7.4: When an order is cancelled from paid, stock is returned
    in_stock_product.refresh_from_db()
    assert in_stock_product.stock_quantity == 10

@pytest.mark.django_db
def test_admin_filter_orders_by_status(admin_client, customer_client, in_stock_product):
    customer_client.post('/api/v1/cart/items/', {'product_id': in_stock_product.id, 'quantity': 1}, format='json')
    customer_client.post('/api/v1/checkout/', {
        'shipping_address': 'Peshawar',
        'payment': {'method': 'mock_card', 'token': 'tok_success'}
    }, format='json', HTTP_IDEMPOTENCY_KEY=str(uuid.uuid4()))

    resp_paid = admin_client.get('/api/v1/admin/orders/?status=paid')
    assert resp_paid.status_code == status.HTTP_200_OK
    assert all(o['status'] == 'paid' for o in resp_paid.data['results'])

import pytest
from decimal import Decimal
from rest_framework import status
from apps.cart.models import Cart, CartItem

@pytest.mark.django_db
def test_unauthenticated_cart_access_fails(api_client):
    response = api_client.get('/api/v1/cart/')
    assert response.status_code == status.HTTP_401_UNAUTHORIZED

@pytest.mark.django_db
def test_add_item_to_cart_success(customer_client, in_stock_product):
    payload = {
        'product_id': in_stock_product.id,
        'quantity': 2
    }
    response = customer_client.post('/api/v1/cart/items/', payload)
    assert response.status_code == status.HTTP_201_CREATED
    assert response.data['quantity'] == 2
    assert response.data['line_total'] == '1000.00'

@pytest.mark.django_db
def test_add_same_product_increments_quantity(customer_client, in_stock_product):
    # Add 2 first
    customer_client.post('/api/v1/cart/items/', {'product_id': in_stock_product.id, 'quantity': 2})
    # Add 3 again
    response = customer_client.post('/api/v1/cart/items/', {'product_id': in_stock_product.id, 'quantity': 3})
    assert response.status_code == status.HTTP_201_CREATED
    assert response.data['quantity'] == 5
    assert response.data['line_total'] == '2500.00'

    # Check cart only has 1 item row
    cart_resp = customer_client.get('/api/v1/cart/')
    assert len(cart_resp.data['items']) == 1

@pytest.mark.django_db
def test_add_to_cart_exceeding_stock_fails(customer_client, single_stock_product):
    # Available stock is 1, trying to add 2
    response = customer_client.post('/api/v1/cart/items/', {
        'product_id': single_stock_product.id,
        'quantity': 2
    })
    assert response.status_code == status.HTTP_400_BAD_REQUEST

@pytest.mark.django_db
def test_add_to_cart_out_of_stock_fails(customer_client, out_of_stock_product):
    response = customer_client.post('/api/v1/cart/items/', {
        'product_id': out_of_stock_product.id,
        'quantity': 1
    })
    assert response.status_code == status.HTTP_400_BAD_REQUEST

@pytest.mark.django_db
def test_update_cart_item_quantity_success(customer_client, in_stock_product):
    add_resp = customer_client.post('/api/v1/cart/items/', {'product_id': in_stock_product.id, 'quantity': 2})
    item_id = add_resp.data['id']

    patch_resp = customer_client.patch(f'/api/v1/cart/items/{item_id}/', {'quantity': 4})
    assert patch_resp.status_code == status.HTTP_200_OK
    assert patch_resp.data['quantity'] == 4
    assert patch_resp.data['line_total'] == '2000.00'

@pytest.mark.django_db
def test_update_cart_item_quantity_exceeding_stock_fails(customer_client, in_stock_product):
    # in_stock_product has 10
    add_resp = customer_client.post('/api/v1/cart/items/', {'product_id': in_stock_product.id, 'quantity': 2})
    item_id = add_resp.data['id']

    patch_resp = customer_client.patch(f'/api/v1/cart/items/{item_id}/', {'quantity': 15})
    assert patch_resp.status_code == status.HTTP_400_BAD_REQUEST

@pytest.mark.django_db
def test_remove_cart_item_success(customer_client, in_stock_product):
    add_resp = customer_client.post('/api/v1/cart/items/', {'product_id': in_stock_product.id, 'quantity': 2})
    item_id = add_resp.data['id']

    del_resp = customer_client.delete(f'/api/v1/cart/items/{item_id}/')
    assert del_resp.status_code == status.HTTP_204_NO_CONTENT

    cart_resp = customer_client.get('/api/v1/cart/')
    assert len(cart_resp.data['items']) == 0

@pytest.mark.django_db
def test_cart_totals_calculated_correctly(customer_client, in_stock_product, single_stock_product):
    # in_stock_product: 500 * 3 = 1500
    customer_client.post('/api/v1/cart/items/', {'product_id': in_stock_product.id, 'quantity': 3})
    # single_stock_product: 2500 * 1 = 2500
    customer_client.post('/api/v1/cart/items/', {'product_id': single_stock_product.id, 'quantity': 1})

    cart_resp = customer_client.get('/api/v1/cart/')
    assert cart_resp.status_code == status.HTTP_200_OK
    assert cart_resp.data['total_items'] == 4
    assert cart_resp.data['total_amount'] == '4000.00'

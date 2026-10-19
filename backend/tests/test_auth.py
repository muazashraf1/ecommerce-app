import pytest
from rest_framework import status
from django.contrib.auth import get_user_model

User = get_user_model()

@pytest.mark.django_db
def test_register_customer_success(api_client):
    payload = {
        'email': 'newcustomer@example.com',
        'password': 'password123',
        'full_name': 'New Customer'
    }
    response = api_client.post('/api/v1/auth/register/', payload)
    assert response.status_code == status.HTTP_201_CREATED
    assert response.data['user']['email'] == 'newcustomer@example.com'
    assert response.data['user']['role'] == 'customer'
    assert 'tokens' in response.data
    assert 'access' in response.data['tokens']
    assert 'refresh' in response.data['tokens']

@pytest.mark.django_db
def test_register_duplicate_email_fails(api_client, customer_user):
    payload = {
        'email': customer_user.email,
        'password': 'password123',
        'full_name': 'Duplicate User'
    }
    response = api_client.post('/api/v1/auth/register/', payload)
    assert response.status_code == status.HTTP_400_BAD_REQUEST

@pytest.mark.django_db
def test_register_short_password_fails(api_client):
    payload = {
        'email': 'shortpass@example.com',
        'password': '123',
        'full_name': 'Short Pass'
    }
    response = api_client.post('/api/v1/auth/register/', payload)
    assert response.status_code == status.HTTP_400_BAD_REQUEST

@pytest.mark.django_db
def test_login_success(api_client, customer_user):
    payload = {
        'email': customer_user.email,
        'password': 'password123'
    }
    response = api_client.post('/api/v1/auth/login/', payload)
    assert response.status_code == status.HTTP_200_OK
    assert 'access' in response.data
    assert 'refresh' in response.data
    assert response.data['user']['email'] == customer_user.email
    assert response.data['user']['role'] == 'customer'

@pytest.mark.django_db
def test_login_invalid_password_fails(api_client, customer_user):
    payload = {
        'email': customer_user.email,
        'password': 'wrongpassword'
    }
    response = api_client.post('/api/v1/auth/login/', payload)
    assert response.status_code == status.HTTP_401_UNAUTHORIZED

@pytest.mark.django_db
def test_token_refresh(api_client, customer_user):
    # Obtain refresh token
    login_resp = api_client.post('/api/v1/auth/login/', {
        'email': customer_user.email,
        'password': 'password123'
    })
    refresh_token = login_resp.data['refresh']

    # Call refresh
    refresh_resp = api_client.post('/api/v1/auth/refresh/', {
        'refresh': refresh_token
    })
    assert refresh_resp.status_code == status.HTTP_200_OK
    assert 'access' in refresh_resp.data

@pytest.mark.django_db
def test_get_current_user_profile(customer_client, customer_user):
    response = customer_client.get('/api/v1/auth/me/')
    assert response.status_code == status.HTTP_200_OK
    assert response.data['email'] == customer_user.email
    assert response.data['role'] == 'customer'

@pytest.mark.django_db
def test_unauthenticated_profile_access_fails(api_client):
    response = api_client.get('/api/v1/auth/me/')
    assert response.status_code == status.HTTP_401_UNAUTHORIZED

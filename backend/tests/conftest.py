import pytest
from decimal import Decimal
from rest_framework.test import APIClient
from django.contrib.auth import get_user_model
from apps.catalog.models import Category, Product

User = get_user_model()

@pytest.fixture
def api_client():
    return APIClient()

@pytest.fixture
def customer_user(db):
    user = User.objects.create_user(
        email='buyer@example.com',
        password='password123',
        full_name='Test Buyer',
        role='customer'
    )
    return user

@pytest.fixture
def other_customer_user(db):
    user = User.objects.create_user(
        email='other@example.com',
        password='password123',
        full_name='Other Buyer',
        role='customer'
    )
    return user

@pytest.fixture
def admin_user(db):
    user = User.objects.create_superuser(
        email='boss@example.com',
        password='adminpassword',
        full_name='Test Admin',
    )
    return user

@pytest.fixture
def customer_client(customer_user):
    client = APIClient()
    client.force_authenticate(user=customer_user)
    return client

@pytest.fixture
def other_customer_client(other_customer_user):
    client = APIClient()
    client.force_authenticate(user=other_customer_user)
    return client

@pytest.fixture
def admin_client(admin_user):
    client = APIClient()
    client.force_authenticate(user=admin_user)
    return client

@pytest.fixture
def category(db):
    return Category.objects.create(name='Electronics', slug='electronics')

@pytest.fixture
def category_audio(db):
    return Category.objects.create(name='Audio', slug='audio')

@pytest.fixture
def in_stock_product(db, category):
    return Product.objects.create(
        category=category,
        name='Wireless Mouse',
        slug='wireless-mouse',
        description='Smooth optical wireless mouse',
        price=Decimal('500.00'),
        stock_quantity=10,
        is_active=True
    )

@pytest.fixture
def single_stock_product(db, category):
    return Product.objects.create(
        category=category,
        name='Rare Vintage Keyboard',
        slug='rare-vintage-keyboard',
        description='Last one in stock',
        price=Decimal('2500.00'),
        stock_quantity=1,
        is_active=True
    )

@pytest.fixture
def out_of_stock_product(db, category):
    return Product.objects.create(
        category=category,
        name='Gaming Monitor 144Hz',
        slug='gaming-monitor-144hz',
        description='Sold out monitor',
        price=Decimal('15000.00'),
        stock_quantity=0,
        is_active=True
    )

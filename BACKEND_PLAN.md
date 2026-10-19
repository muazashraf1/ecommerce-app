# E-Commerce Store — Complete Backend Architecture & Implementation Plan

> **Framework:** Django 5.x + Django REST Framework (DRF)  
> **Database:** PostgreSQL 16 (Row-Level Locking, Atomic Transactions, Constraints)  
> **Authentication:** JWT via `djangorestframework-simplejwt`  
> **API Docs:** `drf-spectacular` (OpenAPI 3.0 / Swagger)  
> **Testing Suite:** `pytest` + `pytest-django` (Target: 35–45 Tests)

---

## 1. Backend Project Structure

Under the `backend/` folder, the codebase is architected with a modular, scalable app structure:

```text
backend/
├── manage.py
├── Dockerfile
├── requirements.txt
├── pytest.ini
├── .env.example
├── config/                         # Django project core configuration
│   ├── __init__.py
│   ├── asgi.py
│   ├── wsgi.py
│   ├── urls.py                     # Root URL routing (/api/v1/...)
│   └── settings/
│       ├── __init__.py
│       ├── base.py                 # Shared settings (apps, middleware, rest_framework, jwt)
│       ├── local.py                # Development settings
│       └── production.py           # Production settings (SSL, host configs)
├── apps/
│   ├── common/                     # Common utilities, custom permissions, exception handling
│   │   ├── __init__.py
│   │   ├── exceptions.py           # Custom exception handler (standard 400, 402, 409 responses)
│   │   └── permissions.py          # IsAdminRole, IsCustomerRole, IsOwnerOrAdmin
│   ├── users/                      # Authentication & user profile management
│   │   ├── __init__.py
│   │   ├── models.py               # Custom User (email, role, full_name)
│   │   ├── serializers.py          # RegisterSerializer, UserSerializer, TokenSerializers
│   │   ├── views.py                # RegisterView, ProfileView, Token views
│   │   └── urls.py                 # /api/v1/auth/...
│   ├── catalog/                    # Categories, products, and inventory
│   │   ├── __init__.py
│   │   ├── models.py               # Category, Product (with CHECK constraints & indexes)
│   │   ├── serializers.py          # CategorySerializer, ProductListSerializer, ProductDetailSerializer
│   │   ├── views.py                # Public catalog, Admin Product CRUD, Stock Patch
│   │   ├── filters.py              # Filtering by category, price range, search query
│   │   └── urls.py                 # /api/v1/categories/, /api/v1/products/...
│   ├── cart/                       # Server-side persistent shopping cart
│   │   ├── __init__.py
│   │   ├── models.py               # Cart, CartItem (UNIQUE(cart_id, product_id))
│   │   ├── serializers.py          # CartItemSerializer, CartSerializer (calculates totals)
│   │   ├── services.py             # Cart item addition, quantity updates, stock pre-validation
│   │   ├── views.py                # CartView, CartItemDetailView
│   │   └── urls.py                 # /api/v1/cart/...
│   ├── payments/                   # Isolated mock payment subsystem
│   │   ├── __init__.py
│   │   ├── models.py               # Payment (order FK, amount, status, provider_ref)
│   │   ├── serializers.py          # PaymentSerializer
│   │   └── services.py             # MockPaymentService (clean charge(order, token) interface)
│   └── orders/                     # Orders, snapshotting, row locking, status state machine
│       ├── __init__.py
│       ├── models.py               # Order, OrderItem, OrderStatusHistory
│       ├── serializers.py          # CheckoutSerializer, OrderSerializer, AdminOrderSerializer
│       ├── services/
│       │   ├── checkout_service.py # Atomic checkout, select_for_update(), idempotency
│       │   └── status_service.py   # State machine transitions and stock return on cancellation
│       ├── views.py                # CheckoutView, OrderListView, OrderDetailView, AdminOrderViews
│       └── urls.py                 # /api/v1/orders/, /api/v1/checkout/, /api/v1/admin/orders/
└── tests/                          # Automated tests suite (Pytest)
    ├── conftest.py                 # Shared fixtures (users, tokens, products, carts)
    ├── test_auth.py                # Registration, login, role permissions
    ├── test_catalog.py             # Catalog search, filter, stock checks
    ├── test_cart.py                # Cart calculations, quantity validations
    ├── test_checkout.py            # Successful checkout, empty cart, price snapshot
    ├── test_concurrency.py         # Race condition / row-lock tests (two buyers for last item)
    ├── test_idempotency.py         # Duplicate checkout with identical Idempotency-Key
    ├── test_mock_payment.py        # tok_success vs tok_fail rollback tests
    └── test_order_status.py        # State transitions & cancel restocking
```

---

## 2. Core Dependencies & Configuration

### 2.1 Dependencies (`requirements.txt`)
```text
Django>=5.0,<5.2
djangorestframework>=3.15.0
djangorestframework-simplejwt>=5.3.1
django-cors-headers>=4.3.1
django-filter>=24.2
psycopg[binary]>=3.1.18
drf-spectacular>=0.27.1
pytest>=8.1.1
pytest-django>=4.8.0
pytest-xdist>=3.5.0
gunicorn>=21.2.0
```

### 2.2 Critical Settings Configurations
1. **Custom User Model:**
   ```python
   AUTH_USER_MODEL = 'users.User'
   ```
2. **REST Framework Settings:**
   ```python
   REST_FRAMEWORK = {
       'DEFAULT_AUTHENTICATION_CLASSES': (
           'rest_framework_simplejwt.authentication.JWTAuthentication',
       ),
       'DEFAULT_PERMISSION_CLASSES': (
           'rest_framework.permissions.IsAuthenticated',
       ),
       'DEFAULT_SCHEMA_CLASS': 'drf_spectacular.openapi.AutoSchema',
       'DEFAULT_PAGINATION_CLASS': 'rest_framework.pagination.PageNumberPagination',
       'PAGE_SIZE': 12,
       'EXCEPTION_HANDLER': 'apps.common.exceptions.custom_exception_handler',
   }
   ```
3. **SimpleJWT Configuration:**
   * Access Token Lifetime: `15 minutes`
   * Refresh Token Lifetime: `7 days`
   * Rotate Refresh Tokens: `True`
   * Blacklist After Rotation: `True`

---

## 3. Detailed App-by-App Implementation Plan

---

### App 1: `apps/users` (Authentication & Roles)

#### Models (`users/models.py`)
* **`User` (inherits from `AbstractBaseUser`, `PermissionsMixin`)**:
  * `email`: `EmailField(unique=True, db_index=True)`
  * `full_name`: `CharField(max_length=120)`
  * `role`: `CharField(max_length=10, choices=[('customer', 'Customer'), ('admin', 'Admin')], default='customer')`
  * `is_active`: `BooleanField(default=True)`
  * `is_staff`: Computed property or field based on `role == 'admin'`
  * `created_at`: `DateTimeField(auto_now_add=True)`
  * `USERNAME_FIELD = 'email'`

#### Permissions (`apps/common/permissions.py`)
* `IsCustomerRole`: Returns `True` if `request.user.role == 'customer'`.
* `IsAdminRole`: Returns `True` if `request.user.role == 'admin'`.
* `IsOwnerOrAdmin`: Checks `obj.user == request.user` or `request.user.role == 'admin'`.

#### Endpoints (`/api/v1/auth/`)
* `POST /auth/register/` $\rightarrow$ Accepts `email`, `password`, `full_name`. Returns user data + tokens.
* `POST /auth/login/` $\rightarrow$ Returns `access` and `refresh` tokens + user object (`role`, `full_name`).
* `POST /auth/refresh/` $\rightarrow$ Issues new `access` token using valid refresh token.
* `GET /auth/me/` $\rightarrow$ Returns authenticated user profile, role, and cart summary count.

---

### App 2: `apps/catalog` (Products & Stock Control)

#### Models (`catalog/models.py`)
* **`Category`**:
  * `name`: `CharField(max_length=80, unique=True)`
  * `slug`: `SlugField(max_length=100, unique=True)`
* **`Product`**:
  * `category`: `ForeignKey(Category, on_delete=models.PROTECT, related_name='products')`
  * `name`: `CharField(max_length=200, db_index=True)`
  * `slug`: `SlugField(max_length=220, unique=True)`
  * `description`: `TextField(blank=True)`
  * `price`: `DecimalField(max_digits=10, decimal_places=2)` — *CheckConstraint: `price >= 0`*
  * `stock_quantity`: `IntegerField(default=0)` — *CheckConstraint: `stock_quantity >= 0`*
  * `image_url`: `URLField(max_length=500, blank=True)`
  * `is_active`: `BooleanField(default=True, db_index=True)` *(Soft-delete flag)*
  * `created_at`: `DateTimeField(auto_now_add=True)`
  * `updated_at`: `DateTimeField(auto_now=True)`
  * **Database Constraints & Indexes**:
    ```python
    class Meta:
        constraints = [
            models.CheckConstraint(check=models.Q(price__gte=0), name='product_price_non_negative'),
            models.CheckConstraint(check=models.Q(stock_quantity__gte=0), name='product_stock_non_negative'),
        ]
        indexes = [
            models.Index(fields=['category', 'is_active']),
            models.Index(fields=['price']),
            models.Index(fields=['slug']),
        ]
    ```

#### Endpoints
* `GET /categories/` (Public) $\rightarrow$ List all categories with product counts.
* `GET /products/` (Public) $\rightarrow$ Search (`?search=`), filter (`?category=slug`, `?min_price=`, `?max_price=`), sort (`?ordering=price/-price`), pagination (`?page=`). Only returns `is_active=True`.
* `GET /products/{id}/` or `/products/{slug}/` (Public) $\rightarrow$ Product detail with real-time `stock_quantity` and availability flag.
* `POST /products/` (Admin only) $\rightarrow$ Add new product.
* `PATCH /products/{id}/` (Admin only) $\rightarrow$ Edit product details / soft-delete (`is_active=False`).
* `PATCH /products/{id}/stock/` (Admin only) $\rightarrow$ Update stock quantity:
  ```json
  {"stock_quantity": 50}
  ```

---

### App 3: `apps/cart` (Server-Side Cart Management)

#### Models (`cart/models.py`)
* **`Cart`**:
  * `user`: `OneToOneField(User, on_delete=models.CASCADE, related_name='cart')`
  * `updated_at`: `DateTimeField(auto_now=True)`
* **`CartItem`**:
  * `cart`: `ForeignKey(Cart, on_delete=models.CASCADE, related_name='items')`
  * `product`: `ForeignKey(Product, on_delete=models.CASCADE)`
  * `quantity`: `PositiveIntegerField(default=1)`
  * *Unique Constraint:* `unique_together = ('cart', 'product')`
  * *Check Constraint:* `quantity > 0`

#### Serializers & Server Calculation
`CartSerializer` dynamically calculates line items and summary totals from the database:
* `line_total`: `item.product.price * item.quantity`
* `cart_total`: `sum(line_total for item in items)`
* `is_in_stock`: `item.product.stock_quantity >= item.quantity`

#### Endpoints (`/api/v1/cart/`) (Customer only)
* `GET /cart/` $\rightarrow$ Returns cart items, product details, line totals, and total amount.
* `POST /cart/items/` $\rightarrow$ Add item (`product_id`, `quantity`).
  * If product already in cart, increments quantity.
  * Validates that requested quantity $\le$ available stock; otherwise returns HTTP 400.
* `PATCH /cart/items/{id}/` $\rightarrow$ Update item quantity (`1 <= quantity <= stock_quantity`).
* `DELETE /cart/items/{id}/` $\rightarrow$ Remove item from cart.

---

### App 4: `apps/payments` (Mock Payment Subsystem)

#### Architecture
The payment module is isolated from the order processing business logic, adhering to clean architecture. It simulates an external gateway (like Stripe) without incurring API dependencies or credit card security vulnerabilities.

#### Service Interface (`payments/services.py`)
```python
class MockPaymentResult:
    def __init__(self, is_success: bool, provider_ref: str, error_message: str = ""):
        self.is_success = is_success
        self.provider_ref = provider_ref
        self.error_message = error_message

class MockPaymentService:
    @staticmethod
    def charge(amount: Decimal, token: str) -> MockPaymentResult:
        """
        Simulates payment gateway charge.
        - 'tok_success' -> Approved (generates fake provider ref 'mock_<random_hex>')
        - 'tok_fail'    -> Declined (simulates insufficient funds / card decline)
        - anything else -> Rejected (invalid token)
        """
        if token == "tok_success":
            return MockPaymentResult(
                is_success=True, 
                provider_ref=f"mock_{uuid.uuid4().hex[:8]}"
            )
        elif token == "tok_fail":
            return MockPaymentResult(
                is_success=False, 
                provider_ref="", 
                error_message="Card was declined by issuing bank (simulated failure)."
            )
        else:
            return MockPaymentResult(
                is_success=False, 
                provider_ref="", 
                error_message=f"Invalid payment token: '{token}'."
            )
```

#### Models (`payments/models.py`)
* **`Payment`**:
  * `order`: `ForeignKey('orders.Order', on_delete=models.CASCADE, related_name='payments')`
  * `amount`: `DecimalField(max_digits=12, decimal_places=2)`
  * `status`: `CharField(max_length=10, choices=[('success', 'Success'), ('failed', 'Failed')])`
  * `provider_ref`: `CharField(max_length=64, blank=True)`
  * `created_at`: `DateTimeField(auto_now_add=True)`

---

### App 5: `apps/orders` (Orders, Concurrency & Idempotency)

#### Models (`orders/models.py`)
* **`Order`**:
  * `user`: `ForeignKey(User, on_delete=models.RESTRICT, related_name='orders')`
  * `status`: `CharField(max_length=12, choices=[('pending', 'Pending'), ('paid', 'Paid'), ('shipped', 'Shipped'), ('delivered', 'Delivered'), ('cancelled', 'Cancelled')], default='pending')`
  * `total_amount`: `DecimalField(max_digits=12, decimal_places=2)`
  * `shipping_address`: `TextField()`
  * `idempotency_key`: `CharField(max_length=64, db_index=True)`
  * `created_at`: `DateTimeField(auto_now_add=True, db_index=True)`
  * `updated_at`: `DateTimeField(auto_now=True)`
  * *Constraint:* `UniqueConstraint(fields=['user', 'idempotency_key'], name='unique_user_idempotency')`
* **`OrderItem`**:
  * `order`: `ForeignKey(Order, on_delete=models.CASCADE, related_name='items')`
  * `product`: `ForeignKey('catalog.Product', on_delete=models.PROTECT)`
  * `product_name`: `CharField(max_length=200)` *(Historical frozen snapshot)*
  * `unit_price`: `DecimalField(max_digits=10, decimal_places=2)` *(Historical frozen snapshot)*
  * `quantity`: `PositiveIntegerField()`
* **`OrderStatusHistory`**:
  * `order`: `ForeignKey(Order, on_delete=models.CASCADE, related_name='status_history')`
  * `old_status`: `CharField(max_length=12)`
  * `new_status`: `CharField(max_length=12)`
  * `changed_by`: `ForeignKey(User, on_delete=models.SET_NULL, null=True)`
  * `changed_at`: `DateTimeField(auto_now_add=True)`

---

## 4. The Atomic Checkout Algorithm (Heart of the Backend)

### Request Execution Flow:
1. **Header Validation:** Check for `Idempotency-Key` header (UUID format). If absent, return HTTP 400.
2. **Idempotency Deduplication:**
   ```python
   existing_order = Order.objects.filter(user=request.user, idempotency_key=idempotency_key).first()
   if existing_order:
       serializer = OrderSerializer(existing_order)
       return Response(serializer.data, status=status.HTTP_200_OK)
   ```
3. **Database Transaction (`transaction.atomic()`):**
   * **Cart Verification:** Fetch user's cart. If empty, return HTTP 400.
   * **Row-Level Locking:**
     ```python
     product_ids = [item.product_id for item in cart_items]
     # SELECT ... FOR UPDATE locks the exact rows in PostgreSQL
     locked_products = {
         p.id: p for p in Product.objects.select_for_update().filter(id__in=product_ids)
     }
     ```
   * **Stock & Price Validation:**
     * Check if every product is active (`is_active=True`).
     * Compare `product.stock_quantity < item.quantity`. If insufficient:
       $$\rightarrow \text{Raise StockUnavailableException (HTTP 409: "Not enough stock for: <Name> (available: X)")}$$
     * Accumulate server-verified total:
       $$\text{Total} = \sum (\text{product.price} \times \text{item.quantity})$$
   * **Order & Line Items Creation:**
     * Create `Order(user=user, total_amount=total, status='pending', idempotency_key=key)`.
     * Create `OrderItem` for each cart item with snapshotted `product_name` and `unit_price`.
   * **Mock Payment Execution:**
     * Call `MockPaymentService.charge(amount=total, token=payment_token)`.
     * **If Failed (`tok_fail`):**
       * Create failed payment record for audit or raise `PaymentFailedException(HTTP 402)`.
       * **The transaction rolls back automatically:** No stock is deducted, cart is preserved, and HTTP 402 is returned to client.
     * **If Success (`tok_success`):**
       * Deduct stock for each product:
         ```python
         product.stock_quantity -= item.quantity
         product.save(update_fields=['stock_quantity', 'updated_at'])
         ```
       * Record successful `Payment(order=order, status='success', provider_ref=ref)`.
       * Update `Order.status = 'paid'`.
       * Clear customer's cart items: `cart.items.all().delete()`.
4. **Commit & Response:** Return HTTP 201 Created with full Order details.

---

## 5. Order Status State Machine & Restocking Logic

```
   [ Pending ]
     /     \
    v       v
[ Paid ]   [ Cancelled ] (Stock unchanged)
  /    \
 v      v
[Shipped] [ Cancelled ] (Restores stock inside atomic transaction)
 |
 v
[ Delivered ] (Final State)
```

### State Transition Rules:
| Current Status | Allowed Next Statuses | Business Action |
|---|---|---|
| `pending` | `paid`, `cancelled` | Normal payment completion or user abandonment |
| `paid` | `shipped`, `cancelled` | If `cancelled`: **Iterate over `order_items` and add quantity back to `Product.stock_quantity`** |
| `shipped` | `delivered` | Tracking completion |
| `delivered` | None | Final state. Rejection HTTP 409 on any change attempt |
| `cancelled` | None | Final state. Rejection HTTP 409 on any change attempt |

---

## 6. Pytest Automated Test Matrix (35–45 Tests)

| Category | Test File | Test Descriptions | Target Count |
|---|---|---|---|
| **Auth & Permissions** | `test_auth.py` | Register customer, register duplicate email (400), login valid (200), login invalid (401), access cart without token (401), customer calls admin endpoint (403), user views another's order (404). | 7 tests |
| **Catalog & Stock** | `test_catalog.py` | List active products, search by term, filter by category slug, filter by min/max price, out-of-stock product display, soft-deleted product excluded from public catalog, admin updates stock. | 7 tests |
| **Cart Operations** | `test_cart.py` | Add item to cart, add duplicate item increments quantity, exceed available stock at add-to-cart (400), update quantity, remove item, computed cart totals match item prices. | 6 tests |
| **Atomic Checkout** | `test_checkout.py` | Successful checkout with `tok_success` (201), empty cart checkout (400), price snapshot verified after product price changes, cart emptied after success. | 5 tests |
| **Mock Payments** | `test_mock_payment.py` | Failed payment with `tok_fail` (402), verify cart items are NOT deleted after payment failure, verify stock is NOT deducted on failure, invalid payment token (400). | 4 tests |
| **Concurrency & Row Locking** | `test_concurrency.py` | Two simultaneous checkouts for last 1 item in stock $\rightarrow$ exactly one succeeds (201), the other gets 409, final database stock is exactly 0 and never negative. | 3 tests |
| **Idempotency** | `test_idempotency.py` | First checkout request returns 201, second request with identical `Idempotency-Key` returns 200 with same order ID, database contains only 1 order row, stock deducted only once. | 3 tests |
| **Order Status & Restock** | `test_order_status.py` | Valid transition `paid -> shipped -> delivered`, invalid transition `delivered -> pending` rejected (409), cancelling a `paid` order restores inventory stock. | 5 tests |
| **Total** | | | **40 Tests** |

---

## 7. Step-by-Step Implementation Sequence

1. **Step 1: Docker & PostgreSQL Setup**
   * Write `backend/Dockerfile` and root `docker-compose.yml`.
   * Configure PostgreSQL database service with persistent volume.
2. **Step 2: Django Core & Settings**
   * Initialize Django project with modular settings (`base.py`, `local.py`).
   * Setup SimpleJWT, CORS headers, and DRF Spectacular.
3. **Step 3: Users App (`apps/users`)**
   * Build Custom User model with roles (`customer`, `admin`).
   * Implement Registration, Login, Token Refresh, and Profile endpoints.
4. **Step 4: Catalog App (`apps/catalog`)**
   * Build `Category` and `Product` models with check constraints & indexes.
   * Implement Public Listing, Filtering, Search, Pagination, and Admin CRUD.
5. **Step 5: Cart App (`apps/cart`)**
   * Build `Cart` and `CartItem` models.
   * Implement server-side calculation and stock pre-validation endpoints.
6. **Step 6: Payments & Orders Apps (`apps/payments`, `apps/orders`)**
   * Build `MockPaymentService` (`tok_success`, `tok_fail`).
   * Implement `Order`, `OrderItem`, and `OrderStatusHistory` models.
   * Build atomic checkout logic with `select_for_update()` and `Idempotency-Key` handling.
   * Build order status state machine with cancellation restocking.
7. **Step 7: Automated Test Suite (`tests/`)**
   * Configure `pytest.ini` and fixtures in `conftest.py`.
   * Write and execute all 40 tests until 100% pass rate is achieved.
8. **Step 8: API Documentation Export**
   * Generate `docs/api-spec/openapi.yaml` and `docs/schema.sql`.

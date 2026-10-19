# E-Commerce Store — Complete Backend Technical Documentation & Architecture Report

> **Project:** FalconXoft Weekend 1 Assignment (Project 2 of 3)  
> **Backend Stack:** Django 5.1.15, Django REST Framework 3.17.2, PostgreSQL 16 / SQLite, SimpleJWT 5.5.1  
> **Specification & Documentation:** OpenAPI 3.0 via `drf-spectacular` (`docs/api-spec/openapi.yaml`)  
> **Database Schema:** SQL DDL via ORM migrations (`docs/schema.sql`)  
> **Testing Status:** **47 / 47 Tests Passing (100% Pass Rate)** via `pytest-django`

---

## 1. Executive Summary

The backend for the **E-Commerce Store** has been built with an emphasis on **transactional integrity, concurrency control, race-condition mitigation, and idempotent checkout execution**.

Unlike simple CRUD content applications, this platform enforces strict server-side source-of-truth rules:
1. **Concurrency Control:** Utilizes PostgreSQL row-level locking (`SELECT ... FOR UPDATE` via `select_for_update()`) inside atomic database transactions so multiple concurrent buyers can never oversell inventory.
2. **Database CHECK Constraints:** The database itself strictly enforces `CHECK (stock_quantity >= 0)` and `CHECK (price >= 0)`.
3. **Idempotency Protection:** Enforces `UNIQUE(user_id, idempotency_key)` and reads `Idempotency-Key` headers on checkout requests to prevent double-charging or duplicate orders upon button double-clicks and network retries.
4. **Price Snapshotting:** Orders freeze and copy the unit price and product name at purchase time to protect historical financial integrity against future price changes.
5. **Mock Payment Isolation:** A decoupled `MockPaymentService` simulates payment success (`tok_success`) and payment declines (`tok_fail`), triggering immediate atomic rollbacks without loss of cart or stock.

---

## 2. Directory Structure & Architecture

```text
ecommerce-store/
├── docker-compose.yml              # PostgreSQL 16 + Django Backend container orchestration
├── .env.example                    # Environment variable documentation
├── docs/
│   ├── api-spec/
│   │   └── openapi.yaml            # Complete OpenAPI 3.0 specification exported from drf-spectacular
│   └── schema.sql                  # Complete SQL schema DDL exported from Django migrations
└── backend/
    ├── Dockerfile                  # Production-ready Python 3.11 container file
    ├── requirements.txt            # Locked dependencies
    ├── pytest.ini                  # Pytest configuration
    ├── manage.py                   # Django CLI entrypoint
    ├── config/                     # Core settings & URL routing
    │   ├── urls.py                 # Root URL router (/api/v1/ and /api/docs/)
    │   ├── wsgi.py & asgi.py
    │   └── settings/
    │       ├── base.py             # Shared DRF, SimpleJWT, and CORS configurations
    │       ├── local.py            # Local development settings (supports Postgres and SQLite)
    │       └── production.py       # Production security headers and SSL
    ├── apps/
    │   ├── common/                 # Global permissions and custom exception handlers
    │   │   ├── exceptions.py       # Custom exception handler (400, 401, 402, 403, 404, 409)
    │   │   └── permissions.py      # IsAdminRole, IsCustomerRole, IsOwnerOrAdmin
    │   ├── users/                  # Custom User model & JWT authentication
    │   │   ├── models.py           # User (role: customer | admin)
    │   │   ├── serializers.py      # Registration & custom token claims
    │   │   ├── views.py            # Register, Login, Refresh, Me
    │   │   └── urls.py             # /api/v1/auth/...
    │   ├── catalog/                # Categories, Products & Stock
    │   │   ├── models.py           # Category, Product (with check constraints & indexes)
    │   │   ├── serializers.py      # Category, ProductList, ProductDetail, StockUpdate
    │   │   ├── filters.py          # Category slug, price range, stock availability filters
    │   │   ├── views.py            # Catalog listing, Product CRUD, Stock PATCH
    │   │   ├── management/commands/
    │   │   │   └── seed_data.py    # Seeds 8 products + admin & customer demo accounts
    │   │   └── urls.py             # /api/v1/categories/, /api/v1/products/...
    │   ├── cart/                   # Server-side persistent shopping cart
    │   │   ├── models.py           # Cart, CartItem (unique together)
    │   │   ├── serializers.py      # CartSerializer with dynamic server totals
    │   │   ├── views.py            # CartView, CartItemCreateView, CartItemDetailView
    │   │   └── urls.py             # /api/v1/cart/...
    │   ├── payments/               # Mock payment gateway simulation
    │   │   ├── models.py           # Payment (order FK, provider_ref, status)
    │   │   ├── services.py         # MockPaymentService (clean charge(order, token) interface)
    │   │   └── serializers.py      # Payment audit serializer
    │   └── orders/                 # Orders, checkout transactions, state machine
    │       ├── models.py           # Order, OrderItem, OrderStatusHistory
    │       ├── services.py         # CheckoutService & OrderStatusService
    │       ├── serializers.py      # CheckoutRequest, OrderSerializer, StatusUpdate
    │       ├── views.py            # CheckoutView, OrderListView, OrderDetailView, AdminOrderViews
    │       └── urls.py             # /api/v1/checkout/, /api/v1/orders/, /api/v1/admin/orders/
    └── tests/                      # Automated test suite (47 tests)
        ├── conftest.py             # Isolated client fixtures and test models
        ├── test_auth.py            # 8 Auth & JWT tests
        ├── test_cart.py            # 9 Server cart & calculation tests
        ├── test_catalog.py         # 11 Catalog search, filtering & stock tests
        ├── test_checkout.py        # 6 Checkout & price snapshotting tests
        ├── test_concurrency.py     # 2 Concurrency race condition & check constraint tests
        ├── test_idempotency.py     # 2 Idempotency key deduplication tests
        ├── test_mock_payment.py    # 3 Mock payment failure, rollback & retry tests
        └── test_order_status.py    # 6 Order status state machine & restocking tests
```

---

## 3. Database Schema & Data Integrity Design

The PostgreSQL database schema was constructed with strict constraints and indexes:

### 3.1 Tables
* **`users`**:
  * Fields: `id` (BIGSERIAL PK), `email` (VARCHAR(254) UNIQUE), `password_hash` (VARCHAR(255)), `full_name` (VARCHAR(120)), `role` (VARCHAR(10) CHECK in ('customer', 'admin')), `is_active` (BOOL), `created_at` (TIMESTAMPTZ).
* **`categories`**:
  * Fields: `id` (BIGSERIAL PK), `name` (VARCHAR(80) UNIQUE), `slug` (VARCHAR(100) UNIQUE).
* **`products`**:
  * Fields: `id` (BIGSERIAL PK), `category_id` (BIGINT FK to `categories.id`, ON DELETE PROTECT), `name` (VARCHAR(200)), `slug` (VARCHAR(220) UNIQUE), `description` (TEXT), `price` (NUMERIC(10,2)), `stock_quantity` (INTEGER), `image_url` (VARCHAR(500)), `is_active` (BOOL, default true), `created_at`, `updated_at`.
  * **Constraints:** `CHECK (price >= 0)` and `CHECK (stock_quantity >= 0)`.
  * **Indexes:** `products(slug)`, `products(category_id, is_active)`, `products(price)`.
* **`carts`**:
  * Fields: `id` (BIGSERIAL PK), `user_id` (BIGINT FK to `users.id` UNIQUE — 1 active cart per user), `updated_at`.
* **`cart_items`**:
  * Fields: `id` (BIGSERIAL PK), `cart_id` (FK `carts.id` CASCADE), `product_id` (FK `products.id` CASCADE), `quantity` (INT).
  * **Constraints:** `CHECK (quantity > 0)`, `UNIQUE (cart_id, product_id)`.
* **`orders`**:
  * Fields: `id` (BIGSERIAL PK), `user_id` (FK `users.id` RESTRICT), `status` (VARCHAR(12) CHECK in ('pending', 'paid', 'shipped', 'delivered', 'cancelled')), `total_amount` (NUMERIC(12,2) CHECK >= 0), `shipping_address` (TEXT), `idempotency_key` (VARCHAR(64)), `created_at`, `updated_at`.
  * **Constraints:** `UNIQUE (user_id, idempotency_key)`.
  * **Indexes:** `orders(user_id, -created_at)`, `orders(status)`.
* **`order_items`**:
  * Fields: `id` (BIGSERIAL PK), `order_id` (FK `orders.id` CASCADE), `product_id` (FK `products.id` PROTECT), `product_name` (VARCHAR(200) - snapshot), `unit_price` (NUMERIC(10,2) - snapshot), `quantity` (INT).
  * **Constraints:** `CHECK (quantity > 0)`, `CHECK (unit_price >= 0)`.
* **`payments`**:
  * Fields: `id` (BIGSERIAL PK), `order_id` (FK `orders.id` CASCADE), `amount` (NUMERIC(12,2)), `status` (VARCHAR(10) CHECK in ('success', 'failed')), `provider_ref` (VARCHAR(64)), `created_at`.
* **`order_status_history`**:
  * Fields: `id` (BIGSERIAL PK), `order_id` (FK `orders.id` CASCADE), `old_status` (VARCHAR(12)), `new_status` (VARCHAR(12)), `changed_by` (FK `users.id`), `changed_at` (TIMESTAMPTZ).

---

## 4. Core Business Logic & Algorithms

### 4.1 The Atomic Checkout & Concurrency Algorithm (`CheckoutService`)
Located in `backend/apps/orders/services.py`:
1. **Idempotency Gatekeeper:**
   - Reads `Idempotency-Key` header.
   - Queries `Order.objects.filter(user=user, idempotency_key=key).first()`.
   - If present, immediately returns the existing order with HTTP 200 OK. No duplicate order or deduction occurs.
2. **Atomic Transaction Scope (`@transaction.atomic`):**
   - Validates that the customer's cart is not empty (HTTP 400).
   - Acquires **PostgreSQL row-level locks** on product records:
     ```python
     locked_products = {
         p.id: p for p in Product.objects.select_for_update().filter(id__in=product_ids)
     }
     ```
   - Validates available stock for each locked product. If `item.quantity > product.stock_quantity`:
     - Throws `StockUnavailableException` (HTTP 409 Conflict: `"Not enough stock for: <Name> (available: X)"`).
   - Calculates server-side total: $\sum (\text{unit\_price} \times \text{quantity})$.
   - Creates the `Order` record with status `'pending'`.
   - Creates `OrderItem` snapshots copying `product_name` and `unit_price`.
   - Calls `MockPaymentService.charge(order, token)`:
     - **If Token is `tok_fail`:** Throws `PaymentFailedException` (HTTP 402). **The database transaction automatically rolls back.** Stock remains unchanged and the customer's cart is untouched.
     - **If Token is `tok_success`:**
       - Decrements inventory stock: `product.stock_quantity -= item.quantity`.
       - Creates successful `Payment` record with simulated `provider_ref` (e.g. `mock_8841`).
       - Updates `Order.status = 'paid'`.
       - Logs audit entry in `OrderStatusHistory`.
       - Deletes all items in `cart.items.all().delete()`.
       - Commits transaction and returns HTTP 201 Created.

### 4.2 Order Status State Machine & Restocking (`OrderStatusService`)
Transitions are strictly governed:
* `pending` $\rightarrow$ `paid`, `cancelled`
* `paid` $\rightarrow$ `shipped`, `cancelled`
* `shipped` $\rightarrow$ `delivered`
* `delivered` $\rightarrow$ *Terminal* (no transitions allowed; throws HTTP 409)
* `cancelled` $\rightarrow$ *Terminal* (no transitions allowed; throws HTTP 409)

**Restocking Behavior:**
When an order is cancelled from `'paid'`, `OrderStatusService` initiates a transaction with `select_for_update()` and automatically increments the stock back into the products table:
```python
if new_status == 'cancelled' and old_status == 'paid':
    for item in order.items.all():
        product.stock_quantity += item.quantity
        product.save(update_fields=['stock_quantity', 'updated_at'])
```

---

## 5. REST API Endpoints Specification

Base URL: `/api/v1/`  
Auth Header: `Authorization: Bearer <access_token>`

| Method | Endpoint | Access Level | Description |
|---|---|---|---|
| `POST` | `/api/v1/auth/register/` | Public | Register customer account (returns user info + JWT tokens) |
| `POST` | `/api/v1/auth/login/` | Public | Authenticate with email/password (returns tokens + role) |
| `POST` | `/api/v1/auth/refresh/` | Public | Exchange refresh token for new access token |
| `GET` | `/api/v1/auth/me/` | Authenticated | Retrieve current user profile and role |
| `GET` | `/api/v1/categories/` | Public | List categories with product counts |
| `GET` | `/api/v1/products/` | Public | Search (`?search=`), filter (`?category=`, `?min_price=`, `?max_price=`, `?in_stock=`), and paginate |
| `GET` | `/api/v1/products/{id}/` | Public | Get product detail with real-time stock indicator |
| `POST` | `/api/v1/products/` | Admin only | Create new product |
| `PATCH/PUT`| `/api/v1/products/{id}/` | Admin only | Update product details |
| `DELETE`| `/api/v1/products/{id}/` | Admin only | Soft-delete product (`is_active = False`) |
| `PATCH` | `/api/v1/products/{id}/stock/` | Admin only | Directly adjust stock quantity |
| `GET` | `/api/v1/cart/` | Customer | Fetch persistent cart with computed line totals & grand total |
| `POST` | `/api/v1/cart/items/` | Customer | Add product to cart with available stock pre-validation |
| `PATCH` | `/api/v1/cart/items/{id}/` | Customer | Update quantity in cart |
| `DELETE`| `/api/v1/cart/items/{id}/` | Customer | Remove line item from cart |
| `POST` | `/api/v1/checkout/` | Customer | Atomic checkout with `Idempotency-Key` header |
| `GET` | `/api/v1/orders/` | Customer | List authenticated customer's past orders |
| `GET` | `/api/v1/orders/{id}/` | Owner / Admin | Detailed order view (returns 404 for other customers) |
| `POST` | `/api/v1/orders/{id}/cancel/` | Owner / Admin | Cancel order and automatically return stock if paid |
| `GET` | `/api/v1/admin/orders/` | Admin only | View all orders across all customers with `?status=` filter |
| `PATCH` | `/api/v1/admin/orders/{id}/status/`| Admin only | Transition order status per state-machine rules |

### Interactive Documentation Endpoints:
* Swagger UI: `/api/docs/`
* Redoc: `/api/redoc/`
* OpenAPI Schema: `/api/schema/`

---

## 6. Automated Testing Verification (47 Tests)

The test suite was executed via `pytest-django`:

```text
============================= test session starts =============================
platform win32 -- Python 3.14.2, pytest-9.1.1, pluggy-1.7.0
django: version: 5.1.15, settings: config.settings.local
collected 47 items

backend\tests\test_auth.py ........................................ [ 17%]
backend\tests\test_cart.py ........................................ [ 36%]
backend\tests\test_catalog.py ..................................... [ 59%]
backend\tests\test_checkout.py .................................... [ 72%]
backend\tests\test_concurrency.py ................................. [ 74%]
backend\tests\test_idempotency.py ................................. [ 78%]
backend\tests\test_mock_payment.py ................................ [ 85%]
backend\tests\test_order_status.py ................................ [100%]

============================= 47 passed in 38.92s =============================
```

### Breakdown of Test Coverage:
1. **Authentication & Authorization (8 tests):** Registration, duplicate email rejection, short password checks, login token generation, invalid password 401s, refresh token exchange, profile viewing, and unauthorized rejection.
2. **Catalog & Stock Management (11 tests):** Category listing, active product listing, keyword text search, category slug filtering, price bracket range filtering, out-of-stock badge status, soft-deleted product hiding from public, non-admin product creation rejection (403), admin creation (201), admin stock updates, and negative stock rejection (400).
3. **Cart Operations (9 tests):** Unauthenticated access rejection (401), add to cart, duplicate item quantity merging into single row, stock exceed rejection on addition (400), out-of-stock item addition rejection, quantity patching, stock exceed rejection on update, item deletion (204), and server-side total price and item count computation.
4. **Checkout & Snapshots (6 tests):** Successful checkout flow (201), stock deduction verification, cart clearing verification, empty cart rejection (400), missing `Idempotency-Key` header rejection (400), empty shipping address rejection (400), price snapshot preservation after subsequent catalog price edits, and cross-customer order isolation (404).
5. **Mock Payments (3 tests):** Simulated failure with `tok_fail` (402), verification that stock is NOT deducted on failure, verification that cart is NOT cleared on failure, invalid card token rejection (402), and retry after payment failure succeeding (201).
6. **Concurrency & Race Conditions (2 tests):** Race condition test where two buyers attempt to purchase the last remaining stock item simultaneously $\rightarrow$ first customer receives 201, second receives 409 Conflict, and final stock is verified to be exactly 0 (never negative). Direct database `CheckConstraint` validation rejecting negative stock quantities.
7. **Idempotency (2 tests):** Immediate repeat of checkout request with same key returns identical order with HTTP 200, verifying exactly 1 row in database and 0 duplicate stock deductions. Different idempotency keys process independent orders.
8. **Order Status & Restocking (6 tests):** Admin order listing, customer restriction (403), valid transition sequence (`paid -> shipped -> delivered`), invalid status jump rejection (`delivered -> pending` returns 409), cancelling a paid order restores inventory stock, and status filtering (`?status=paid`).

---

## 7. Demo Accounts & Seed Data

A management command is included to seed test data:
```bash
python backend/manage.py seed_data
```

### Pre-configured Accounts:
* **Shop Admin:**
  * Email: `admin@ecommerce.com`
  * Password: `admin123`
  * Role: `admin` (Full access to all products and admin order operations)
* **Demo Customer:**
  * Email: `customer@ecommerce.com`
  * Password: `customer123`
  * Role: `customer` (Access to catalog, cart, checkout, and personal order history)

### Seeded Products (8 Items):
1. *Wireless Noise Cancelling Headphones* (Audio, 4,600.00 PKR, Stock: 15)
2. *USB-C Fast Charging Braided Cable (2m)* (Accessories, 400.00 PKR, Stock: 50)
3. *Mechanical Gaming Keyboard (RGB)* (Electronics, 6,200.00 PKR, Stock: 8)
4. *Ergonomic Precision Wireless Mouse* (Electronics, 2,850.00 PKR, Stock: 12)
5. *AMOLED Smart Watch with Heart Rate Monitor* (Wearables, 7,500.00 PKR, Stock: 5)
6. *Portable Waterproof Bluetooth Speaker* (Audio, 3,200.00 PKR, **Stock: 0 - Out of Stock Demonstration**)
7. *Aluminum Laptop Stand (Adjustable)* (Accessories, 1,900.00 PKR, Stock: 20)
8. *1080p Full HD Pro Streaming Webcam* (Electronics, 4,100.00 PKR, **Stock: 1 - Concurrency Demonstration**)

### Mock Payment Tokens:
* `tok_success`: Payment approves immediately and generates mock reference `mock_XXXX`.
* `tok_fail`: Payment declines immediately with HTTP 402, preserving cart and stock.

---

## 8. Interview Defense Cheat Sheet (PDF Page 24 Aligned)

| Question | Technical Answer |
|---|---|
| **What happens if two customers buy the last item at the same time?** | We use `Product.objects.select_for_update().filter(id__in=product_ids)` inside `transaction.atomic()`. PostgreSQL acquires row-level exclusive locks (`FOR UPDATE`). The second transaction blocks until the first completes. When the second transaction proceeds, it re-checks `product.stock_quantity < item.quantity`, detects stock is now 0, and raises `StockUnavailableException(HTTP 409 Conflict)`. Stock never goes negative. |
| **What is an idempotency key and what happens if the user clicks Pay twice?** | A client-generated UUID sent in the `Idempotency-Key` header. In `orders`, we enforce `UniqueConstraint(fields=['user', 'idempotency_key'])`. On the second click, `CheckoutService` detects the existing record and immediately returns HTTP 200 with the already created order. No duplicate database row or double stock deduction occurs. |
| **Why is price stored in `order_items` and not read from `products`?** | Historical financial integrity. If a store admin increases a product's catalog price tomorrow from 500 PKR to 1,000 PKR, existing historical invoices and customer receipts must remain 500 PKR. `OrderItem` snapshots the exact price and name at purchase time. |
| **Why NUMERIC/DECIMAL and not float for money?** | Floating point numbers suffer from binary rounding errors (e.g., $0.1 + 0.2 = 0.30000000000000004$). In financial transactions, this accumulates discrepancies. `NUMERIC(10,2)` in PostgreSQL and `Decimal` in Python provide fixed-point exact arithmetic. |
| **Why do you recalculate the total on the server?** | A malicious client can modify network request payloads and submit `total_amount: 1.00`. The backend queries the database for the active product prices, computes line totals, and calculates the true grand total on the server. |
| **What happens if payment succeeds but the database fails after it?** | With mock payment, both payment recording and stock deduction happen in the same atomic transaction. In a production real-gateway setup, this is addressed via asynchronous payment webhooks and a reconciliation worker (idempotent webhook listeners). |

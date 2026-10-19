# E-commerce Store — Full Stack Master Project Plan & Execution Roadmap

> **Assessment:** FalconXoft Weekend 1 Assignment (Project 2 of 3)  
> **Tech Stack:** Django REST Framework (Backend) + Next.js App Router (Frontend) + PostgreSQL (Database)  
> **Core Focus:** Data Integrity, Concurrency Row-Locking, Idempotent Checkout, Mock Payment

---

## 1. Project Analysis & Core Problem Definition

In an e-commerce platform, frontend UI is only the visible surface. **The true engineering challenge lies in transactional integrity, race condition handling, and state consistency.**

### The 5 Core Engineering Truths of this Project:
1. **Zero Stock Overselling (Concurrency Control):**
   - In PostgreSQL, products must have a strict `CHECK (stock_quantity >= 0)` constraint.
   - At checkout, Django MUST use `select_for_update()` inside `transaction.atomic()` to lock the targeted product rows. If two users concurrently buy the last remaining stock, the second will safely receive an HTTP 409 conflict and stock will never drop below zero.
2. **Checkout Idempotency:**
   - Every checkout POST request requires an `Idempotency-Key` header (UUID).
   - If a customer double-clicks "Pay" or a network retry happens, the database table has `UNIQUE(user_id, idempotency_key)`. It returns the previously created order instead of charging or creating another order.
3. **Price Snapshotting (Historical Integrity):**
   - The product price in the catalog can change over time.
   - At checkout, the unit price and product name are copied/frozen into `order_items`. Future price updates will never alter historical orders.
4. **Server-Side Truth:**
   - Frontend never calculates the final order amount. The backend queries the database for the active product prices and calculates line items and grand totals.
5. **Atomic Mock Payment Integration:**
   - Payment is simulated via a clean, swappable internal module `charge(order, token)`.
   - `tok_success` completes the transaction; `tok_fail` raises an exception and cleanly rolls back the entire transaction (cart and stock remain intact).

---

## 2. System Architecture & Boundaries

```
[ User Browser (Customer / Admin) ]
                |
                | HTTPS / JSON
                v
       [ Next.js Frontend ]  (Port 3000)
                |
                | REST API (Bearer JWT, Idempotency-Key)
                v
       [ Django REST Framework ]  (Port 8000)
           |             |
           |             +---> [ Mock Payment Service ] (charge(order, token))
           |
           v SQL (select_for_update, atomic transactions)
       [ PostgreSQL Database ]  (Port 5432)
```

### Deployment Boundaries
* **Public Zone:** Frontend (Next.js), Reverse Proxy / Nginx (Port 80/443).
* **Private Zone:** Django REST API, Mock Payment Service, PostgreSQL Database (no public access).

---

## 3. Database Schema Specification (PostgreSQL)

### 3.1 Tables & Schema Structure

#### `users`
* `id` : BIGSERIAL PRIMARY KEY
* `email` : VARCHAR(254) UNIQUE NOT NULL
* `password_hash` : VARCHAR(255) NOT NULL
* `full_name` : VARCHAR(120) NOT NULL
* `role` : VARCHAR(10) CHECK (role IN ('customer', 'admin')) DEFAULT 'customer'
* `is_active` : BOOLEAN DEFAULT TRUE
* `created_at` : TIMESTAMPTZ DEFAULT NOW()

#### `categories`
* `id` : BIGSERIAL PRIMARY KEY
* `name` : VARCHAR(80) UNIQUE NOT NULL
* `slug` : VARCHAR(100) UNIQUE NOT NULL

#### `products`
* `id` : BIGSERIAL PRIMARY KEY
* `category_id` : BIGINT REFERENCES categories(id) ON DELETE PROTECT
* `name` : VARCHAR(200) NOT NULL
* `slug` : VARCHAR(220) UNIQUE NOT NULL
* `description` : TEXT
* `price` : NUMERIC(10,2) CHECK (price >= 0) NOT NULL
* `stock_quantity` : INTEGER CHECK (stock_quantity >= 0) NOT NULL
* `image_url` : VARCHAR(500)
* `is_active` : BOOLEAN DEFAULT TRUE *(soft delete: hide instead of hard delete)*
* `created_at`, `updated_at` : TIMESTAMPTZ DEFAULT NOW()

#### `carts`
* `id` : BIGSERIAL PRIMARY KEY
* `user_id` : BIGINT UNIQUE REFERENCES users(id) ON DELETE CASCADE
* `updated_at` : TIMESTAMPTZ DEFAULT NOW()

#### `cart_items`
* `id` : BIGSERIAL PRIMARY KEY
* `cart_id` : BIGINT REFERENCES carts(id) ON DELETE CASCADE
* `product_id` : BIGINT REFERENCES products(id) ON DELETE CASCADE
* `quantity` : INTEGER CHECK (quantity > 0) NOT NULL
* *Constraint:* `UNIQUE (cart_id, product_id)`

#### `orders`
* `id` : BIGSERIAL PRIMARY KEY
* `user_id` : BIGINT REFERENCES users(id) ON DELETE RESTRICT
* `status` : VARCHAR(12) CHECK (status IN ('pending', 'paid', 'shipped', 'delivered', 'cancelled')) DEFAULT 'pending'
* `total_amount` : NUMERIC(12,2) CHECK (total_amount >= 0) NOT NULL
* `shipping_address` : TEXT NOT NULL
* `idempotency_key` : VARCHAR(64) NOT NULL
* `created_at`, `updated_at` : TIMESTAMPTZ DEFAULT NOW()
* *Constraint:* `UNIQUE (user_id, idempotency_key)`

#### `order_items`
* `id` : BIGSERIAL PRIMARY KEY
* `order_id` : BIGINT REFERENCES orders(id) ON DELETE CASCADE
* `product_id` : BIGINT REFERENCES products(id) ON DELETE PROTECT
* `product_name` : VARCHAR(200) NOT NULL *(frozen at purchase)*
* `unit_price` : NUMERIC(10,2) NOT NULL *(frozen at purchase)*
* `quantity` : INTEGER CHECK (quantity > 0) NOT NULL

#### `payments`
* `id` : BIGSERIAL PRIMARY KEY
* `order_id` : BIGINT REFERENCES orders(id) ON DELETE CASCADE
* `amount` : NUMERIC(12,2) NOT NULL
* `status` : VARCHAR(10) CHECK (status IN ('success', 'failed')) NOT NULL
* `provider_ref` : VARCHAR(64) NOT NULL *(e.g. mock_8841)*
* `created_at` : TIMESTAMPTZ DEFAULT NOW()

#### `order_status_history` *(Optional / Recommended)*
* `id` : BIGSERIAL PRIMARY KEY
* `order_id` : BIGINT REFERENCES orders(id) ON DELETE CASCADE
* `old_status` : VARCHAR(12)
* `new_status` : VARCHAR(12)
* `changed_by` : BIGINT REFERENCES users(id)
* `changed_at` : TIMESTAMPTZ DEFAULT NOW()

### 3.2 Strategic Indexes
* `products(slug)` — Fast product detail lookups.
* `products(category_id, is_active)` — Fast catalog filtering.
* `products(price)` — Sorting and price bracket filtering.
* `orders(user_id, created_at DESC)` — Customer order history sorting.
* `orders(status)` — Admin dashboard order filtration.

---

## 4. API Endpoints Specification

Base URL: `/api/v1/`  
Auth Header: `Authorization: Bearer <access_token>`

### Auth
* `POST /auth/register/` (Public) - Create customer account
* `POST /auth/login/` (Public) - Return JWT pair (`access`, `refresh`)
* `POST /auth/refresh/` (Public) - Return new access token
* `GET /auth/me/` (Authenticated) - Return current user profile & role

### Catalog
* `GET /categories/` (Public) - List categories
* `GET /products/` (Public) - Search by `search`, filter by `category`, `min_price`, `max_price`, paginate (`page`)
* `GET /products/{id}/` (Public) - Product detail by ID or slug
* `POST /products/` (Admin) - Create new product
* `PATCH /products/{id}/` (Admin) - Update details / set `is_active=false`
* `PATCH /products/{id}/stock/` (Admin) - Direct stock adjustment

### Cart (Customer Only)
* `GET /cart/` - Get active cart, items, item totals, and grand total
* `POST /cart/items/` - Add item (`product_id`, `quantity`) with stock check
* `PATCH /cart/items/{id}/` - Update item quantity
* `DELETE /cart/items/{id}/` - Remove item

### Checkout & Orders
* `POST /checkout/` (Customer) - Execute order with header `Idempotency-Key`
  * Body: `{"shipping_address": "...", "payment": {"method": "mock_card", "token": "tok_success"}}`
  * Returns: 201 Created on success, 402 on failed payment, 409 on out of stock, 200 on duplicate idempotency key.
* `GET /orders/` (Customer) - Order history
* `GET /orders/{id}/` (Owner or Admin) - Single order details
* `POST /orders/{id}/cancel/` (Owner or Admin) - Cancel order and restore stock if already 'paid'

### Admin Order Management
* `GET /admin/orders/` (Admin) - View all orders with status filter
* `PATCH /admin/orders/{id}/status/` (Admin) - Transition order status:
  * Allowed: `pending -> paid -> shipped -> delivered`
  * Any invalid jump returns HTTP 409.

---

## 5. Detailed Checkout & Concurrency Algorithm

```python
@transaction.atomic
def process_checkout(user, shipping_address, payment_token, idempotency_key):
    # 1. Idempotency Check
    existing_order = Order.objects.filter(user=user, idempotency_key=idempotency_key).first()
    if existing_order:
        return existing_order, False # Return existing without double charging

    # 2. Get Cart
    cart = Cart.objects.prefetch_related('items').get(user=user)
    if not cart.items.exists():
        raise ValidationError("Cart is empty", code=400)

    # 3. Row-level Lock on Products
    product_ids = [item.product_id for item in cart.items.all()]
    locked_products = {
        p.id: p for p in Product.objects.select_for_update().filter(id__in=product_ids)
    }

    # 4. Stock & Total Verification
    total_amount = Decimal("0.00")
    order_items_to_create = []

    for item in cart.items.all():
        product = locked_products.get(item.product_id)
        if not product or not product.is_active:
            raise ProductUnavailableException(f"Product {item.product_id} is unavailable", code=400)
        if product.stock_quantity < item.quantity:
            raise OutOfStockException(f"Not enough stock for: {product.name} (available: {product.stock_quantity})", code=409)

        total_amount += product.price * item.quantity
        order_items_to_create.append({
            "product": product,
            "product_name": product.name,
            "unit_price": product.price,
            "quantity": item.quantity
        })

    # 5. Create Order (Pending)
    order = Order.objects.create(
        user=user,
        total_amount=total_amount,
        shipping_address=shipping_address,
        idempotency_key=idempotency_key,
        status='pending'
    )

    for item_data in order_items_to_create:
        OrderItem.objects.create(
            order=order,
            product=item_data["product"],
            product_name=item_data["product_name"],
            unit_price=item_data["unit_price"],
            quantity=item_data["quantity"]
        )

    # 6. Mock Payment Execution
    payment_result = MockPaymentService.charge(amount=total_amount, token=payment_token)
    if not payment_result.is_success:
        # Transaction rolls back automatically upon raising exception
        Payment.objects.create(order=order, amount=total_amount, status='failed', provider_ref=payment_result.ref)
        raise PaymentFailedException("Payment failed. No money was taken and your cart is unchanged.", code=402)

    # 7. Deduct Stock & Record Success
    for item_data in order_items_to_create:
        product = item_data["product"]
        product.stock_quantity -= item_data["quantity"]
        product.save(update_fields=['stock_quantity', 'updated_at'])

    Payment.objects.create(order=order, amount=total_amount, status='success', provider_ref=payment_result.ref)
    order.status = 'paid'
    order.save(update_fields=['status', 'updated_at'])

    # 8. Empty Cart
    cart.items.all().delete()

    return order, True
```

---

## 6. Next.js Frontend Architecture

### 6.1 Pages & Routes
* `app/page.tsx` — Landing Page (Hero, Featured Products, Categories, Trust Badges).
* `app/products/page.tsx` — Catalog Page (Filter sidebar, live search, sorting, stock badge).
* `app/products/[slug]/page.tsx` — Product Detail (High-res view, stock status, quantity picker, Add to Cart).
* `app/cart/page.tsx` — Cart Page (Live subtotal, quantity updates, remove button, checkout redirect).
* `app/checkout/page.tsx` — Checkout Page (Address form, Mock Payment toggle: Success vs Failure simulator, one-click protection).
* `app/orders/page.tsx` & `app/orders/[id]/page.tsx` — Orders list & live status timeline.
* `app/login/page.tsx` & `app/register/page.tsx` — Auth pages with JWT token handling.
* `app/admin/products/page.tsx` — Inventory CRUD and stock updater.
* `app/admin/orders/page.tsx` — Admin fulfillment screen with status transitions.

### 6.2 Frontend UX & Resilience Rules
* **Single Pay Button Click:** Button enters `disabled={loading}` state immediately upon click to prevent accidental rapid re-submissions.
* **Persistent Cart Hydration:** Cart fetched on login and synced cleanly.
* **Rich Aesthetic Standard:** Vibrant modern UI, responsive layout, glassmorphic accents, clear badges for stock status (`In Stock`, `Low Stock`, `Out of Stock`).

---

## 7. Testing Suite Plan (`pytest` + `pytest-django`)

Target: **35–45 tests** across 7 test categories:

1. **Positive Flow Tests:**
   - User registration & JWT login.
   - Add product to cart, verify server totals.
   - Checkout with `tok_success`: order status = `paid`, stock reduced, cart cleared.
   - Admin transitions status: `paid -> shipped -> delivered`.
2. **Negative Flow Tests:**
   - Checkout with `tok_fail`: HTTP 402, cart preserved, stock unmodified.
   - Checkout when quantity exceeds stock: HTTP 409 conflict.
   - Adding non-existent product ID to cart: HTTP 404.
   - Adding 0 or negative quantity: HTTP 400.
3. **Boundary Tests:**
   - Buying exact remaining stock (stock becomes 0).
   - Price calculation with 2 decimal precision (e.g. `99.99 * 3`).
   - Pagination edge cases (page 1, last page, empty page).
4. **Permissions & Security Tests:**
   - Unauthenticated access to `/cart/` or `/checkout/` returns 401.
   - Customer trying to call `/admin/orders/` or `/products/ [POST]` returns 403.
   - Customer trying to view another user's order ID returns 404 (hides existence).
5. **Concurrency & Race Condition Tests:**
   - Multi-threaded or simulated parallel checkout requests for the last 1 remaining item: exactly 1 order succeeds, 1 fails with 409, final stock is exactly 0.
6. **Idempotency Tests:**
   - Sending checkout twice with the identical `Idempotency-Key`: returns 1st order ID, exactly 1 order in DB, no duplicate stock deduction.
7. **Order Status Transition Rules:**
   - Invalid jump (`delivered -> pending` or `cancelled -> paid`) returns 409.
   - Cancelling a `paid` order restocks product quantity inside a transaction.

---

## 8. FalconXoft Submission Deliverables Checklist

| # | Deliverable File | Description / Purpose |
|---|---|---|
| 1 | `01-README.md` | Complete setup guide, architecture summary, test instructions, mock tokens |
| 2 | `02-architecture.pdf` | System architecture, public vs private zone, data movement |
| 3 | `03-database-design.pdf` & `schema.sql` | Entity-Relationship Diagram (ERD), tables, indexes, constraints |
| 4 | `04-api-workflows.pdf` & `openapi.yaml` | Sequence diagrams for checkout success/failure & OpenAPI spec |
| 5 | `05-test-cases.xlsx` | Comprehensive test matrix with actual results and evidence links |
| 6 | `06-engineering-decisions.md` | Architectural Decision Records (ADRs) explaining technical choices |
| 7 | `07-source-and-demo-links.md` | GitHub repo link, deployment link, and demo video link |
| 8 | `08-cost-and-scaling.xlsx` | Hosting cost comparison (VPS vs AWS) across 100 to 1M users |
| 9 | `09-sources-and-disclosure.md` | Open-source attribution and AI transparency statement |
| 10 | Demo Video (3–5 min) | Video walkthrough script and recording covering full journey and failure cases |

---

## 9. Next Steps & Execution Sequence

1. **Step 1:** Initialize repository structure (`backend/`, `frontend/`, `docs/`, `docker-compose.yml`, `.env.example`).
2. **Step 2:** Build backend Django core (`users`, `catalog`, `cart`, `payments`, `orders`).
3. **Step 3:** Implement the critical checkout transaction, row locking, and idempotency logic.
4. **Step 4:** Write and execute the full Pytest suite (confirming concurrency & idempotency pass).
5. **Step 5:** Build the Next.js frontend with modern design, state management, and error handling.
6. **Step 6:** Assemble all 9 FalconXoft documentation files and demo video script.

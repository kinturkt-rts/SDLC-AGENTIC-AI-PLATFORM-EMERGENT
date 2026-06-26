# Inventory Desk — Solution Design

## 1. Summary
Single-tenant warehouse inventory REST API (FastAPI + PostgreSQL) with JWT-based RBAC, product/stock CRUD, and atomic stock adjustments. Primary store is RDS PostgreSQL (`inventory_app` schema); no browser UI — Swagger at `/docs` is the demo surface.
Diagram: `docs/diagrams/generated-diagrams/inventory-app.png`. TBD: category delete endpoint, user deactivation API, pagination max-limit enforcement.

## 2. Stack
| Layer | Technology |
|-------|------------|
| API Service | FastAPI (uvicorn), ECS-hosted, `target-apps/inventory-app/` |
| Auth | JWT HS256 via `python-jose`, passwords via `passlib[bcrypt]` |
| ORM | SQLAlchemy 2.x (sync), Alembic migrations |
| Database | RDS PostgreSQL 15, schema `inventory_app` |
| Cache | ElastiCache Redis — hot product/stock-level reads |
| Async Alerts | SQS + Lambda — reorder-threshold evaluation (out of app scope) |

## 3. Data model
| Table | Columns | Indexes / Constraints |
|---|---|---|
| `users` | `id uuid PK`, `username text UNIQUE NOT NULL`, `password_hash text NOT NULL`, `role user_role NOT NULL`, `is_active bool DEFAULT true`, `created_at timestamptz` | IDX: `username`; ENUM: `user_role('admin','staff')` |
| `categories` | `id uuid PK`, `name varchar(80) NOT NULL`, `slug varchar(100) UNIQUE NOT NULL`, `created_at timestamptz` | IDX: `slug`; ON DELETE RESTRICT (from products) |
| `products` | `id uuid PK`, `category_id uuid FK→categories RESTRICT`, `sku text UNIQUE NOT NULL`, `name varchar(120) NOT NULL`, `unit_price numeric(10,2) CHECK(>=0)`, `qty_on_hand int NOT NULL DEFAULT 0 CHECK(>=0)`, `created_at timestamptz`, `updated_at timestamptz` | IDX: `category_id`, `sku` |
| `stock_movements` | `id uuid PK`, `product_id uuid FK→products CASCADE`, `delta int NOT NULL`, `reason movement_reason NOT NULL`, `note varchar(500)`, `performed_by uuid FK→users NULLABLE`, `created_at timestamptz` | IDX: `product_id`, `created_at DESC`; ENUM: `movement_reason('sale','restock','adjustment')`; immutable |

## 4. API surface
| Method | Path | Request | Response | Notes |
|--------|------|---------|----------|-------|
| GET | `/health` | — | `{status,service}` | FR-1; no auth |
| POST | `/auth/login` | `{username,password}` | `{access_token,token_type,role,expires_in}` | FR-2; returns 401 on bad creds/inactive |
| GET | `/categories` | `?limit&offset` | `{items,total,limit,offset}` | FR-4; admin+staff |
| POST | `/categories` | `{name,slug?}` | Category 201 | FR-4; admin only; 409 on dup slug |
| GET | `/categories/{id}` | — | Category+`product_count` | FR-4; admin+staff |
| PATCH | `/categories/{id}` | `{name?,slug?}` | Category | FR-4; admin only |
| GET | `/products` | `?category_id&sku&low_stock&limit&offset` | `{items,total,limit,offset}` | FR-6; admin+staff |
| POST | `/products` | `{category_id,sku,name,unit_price}` | Product 201 | FR-5; admin only; 409 dup SKU |
| GET | `/products/{id}` | — | Product | FR-5; admin+staff |
| PATCH | `/products/{id}` | `{name?,category_id?,unit_price?}` | Product | FR-5; `qty_on_hand` ignored |
| DELETE | `/products/{id}` | — | 204 | FR-9; admin only; 409 if qty>0 |
| POST | `/products/{id}/adjust-stock` | `{delta,reason,note?}` | Movement 200 | FR-7; admin+staff; 422 if qty<0 |
| GET | `/products/{id}/movements` | `?limit&offset` | `{items,total,limit,offset}` | FR-8; admin+staff; newest-first |

## 5. Rules
- **RBAC roles:** `admin` — all routes; `staff` — GET categories/products, adjust-stock, movements only (FR-3).
- **401** on missing/invalid/expired JWT; **403** on valid JWT with insufficient role (NFR-3).
- **Atomic adjust-stock:** `SELECT FOR UPDATE` on product row + insert movement + update `qty_on_hand` in single transaction; rollback on negative result (NFR-6).
- **Immutability:** `stock_movements` rows are never updated or deleted via API; CASCADE delete only when parent product is removed (FR-11).
- **Slug:** auto-derived (lowercase, hyphens) from `name` if omitted; unique index is the integrity backstop (FR-4).
- **Startup guard:** app exits non-zero if `DATABASE_URL` or `JWT_SECRET_KEY` absent (FR-12).
- **Logging:** INFO per request `{method,path,status,latency_ms}`; WARNING on auth failure (no password echo); ERROR + stack trace on 5xx (NFR-8).

## 6. DB delivery
1. Migration order: `001_create_enums_and_users.sql` → `002_create_categories.sql` → `003_create_products.sql` → `004_create_stock_movements.sql`
2. Seed file: `seeds/dev_users.sql` — inserts `admin` (role=`admin`) with bcrypt hash of `Admin123!` and `staff` (role=`staff`) with bcrypt hash of `Staff123!`; scoped dev-only; README warns to rotate before production (NFR-10).
3. All tables under `inventory_app` schema; prepend `SET search_path TO inventory_app;` in each file; use `gen_random_uuid()` for UUIDs (Postgres 13+, fallback `uuid_generate_v4()` with `pgcrypto`).

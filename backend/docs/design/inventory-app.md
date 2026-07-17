# Inventory Desk — Solution Design

## 1. Summary
REST API for warehouse stock management: single Postgres DB, JWT-auth FastAPI service, append-only adjustments for full audit trail. No web UI in v1 — Swagger at `/docs` serves as demo surface. Diagram: `docs/generated-diagrams/inventory-app.png`. TBD: low-stock threshold env-var config, manager user-CRUD endpoint (Phase 2).

## 2. Stack
| Layer | Technology | Path |
|-------|------------|------|
| API | FastAPI (Python) | `target-apps/inventory-app/` |
| Auth | PyJWT + bcrypt | `app/auth/` |
| ORM | SQLAlchemy + Alembic | `app/models/`, `alembic/` |
| DB | PostgreSQL (RDS) | env `DATABASE_URL` |
| Container | Docker / docker compose | `docker-compose.yml` |

## 3. Data model
| Table | Columns | Indexes / constraints |
|-------|---------|----------------------|
| `users` | `id uuid PK`, `username text UNIQUE`, `hashed_password text`, `role text`, `is_active bool DEFAULT true`, `created_at timestamptz` | idx on `username`; role IN ('manager','staff') |
| `categories` | `id uuid PK`, `name text UNIQUE`, `created_at timestamptz`, `updated_at timestamptz` | idx on `name` |
| `products` | `id uuid PK`, `name text`, `sku text UNIQUE`, `price numeric(10,2)`, `quantity_on_hand int DEFAULT 0`, `category_id uuid FK(categories)`, `is_active bool DEFAULT true`, `created_at timestamptz`, `updated_at timestamptz` | idx on `sku`, `category_id`; CHECK `quantity_on_hand >= 0` |
| `adjustments` | `id uuid PK`, `product_id uuid FK(products)`, `user_id uuid FK(users)`, `delta int`, `reason text`, `note text`, `quantity_after int`, `created_at timestamptz` | idx on `product_id, created_at`; reason IN ('sale','restock','manual_adjustment'); no UPDATE/DELETE |

## 4. API surface
| Method | Path | Request | Response | Notes |
|--------|------|---------|----------|-------|
| POST | `/auth/token` | `username, password` | `{access_token, token_type}` | FR-1; 401 if inactive |
| GET | `/health` | — | `{status, db}` | FR-10; no auth |
| GET | `/categories` | — | `[{id, name}]` | FR-3 |
| POST | `/categories` | `{name}` | `{id, name}` | FR-3; manager only; 409 on dup |
| PUT | `/categories/{id}` | `{name}` | `{id, name}` | FR-3; manager only |
| DELETE | `/categories/{id}` | — | 204 | FR-3; 409 if products assigned |
| GET | `/products` | `?category_id&sku&name&low_stock` | `[{id,name,sku,price,quantity_on_hand,low_stock}]` | FR-7, FR-8 |
| POST | `/products` | `{name,sku,price,category_id,quantity_on_hand}` | `{id,...}` | FR-4; manager only; 409 dup SKU |
| PUT | `/products/{id}` | `{name,price,category_id}` | `{id,...}` | FR-4; manager only |
| DELETE | `/products/{id}` | — | 204 | FR-4; 409 if qty > 0 |
| POST | `/products/{id}/adjustments` | `{delta,reason,note?}` | `{id,quantity_after}` | FR-5; manager+staff; 422 if qty < 0 |
| GET | `/products/{id}/adjustments` | — | `[{id,user_id,delta,reason,note,quantity_after,created_at}]` | FR-6; ascending order |

## 5. Rules
- **Auth (FR-1, NFR-1, NFR-2):** bcrypt cost≥12 hashing; JWT HS256 8h expiry; secret from env `JWT_SECRET_KEY`; API: `Depends(get_current_user)` on all non-health routes; 401 on invalid/expired token; `is_active` checked at login only.
- **RBAC (FR-2):** roles `manager`/`staff`; API: `Depends(require_role("manager"))` guards POST/PUT/DELETE on `/categories` and `/products`; staff may call POST `/products/{id}/adjustments` and all GETs; wrong role → 403.
- **Adjustment integrity (FR-5, NFR-6):** `SELECT FOR UPDATE` on product row during adjustment; reject if `quantity_on_hand + delta < 0` → HTTP 422; validate sign convention: `sale`→delta<0, `restock`→delta>0, `manual_adjustment`→either; enforced in route handler + DB CHECK constraint.
- **Audit immutability (FR-6, NFR-9):** No `UPDATE`/`DELETE` routes on adjustments; DB role revokes those privileges on `adjustments` table; `quantity_after` written atomically with product update.
- **Category delete guard (FR-3):** Check `products` FK before delete; return 409 with message if any active product references category.
- **Product delete guard (FR-4):** Reject DELETE if `quantity_on_hand > 0` → 409.
- **Structured logging (NFR-8):** JSON middleware logs `method, path, status, latency_ms, user_id`; no request bodies logged; adjustments emit `INFO` event with `product_id, delta, reason, user_id`.
- **Seed idempotency (FR-9):** Startup script uses `INSERT … ON CONFLICT DO NOTHING`; credentials from env vars `SEED_MANAGER_PASSWORD` / `SEED_STAFF_PASSWORD`.

## 6. DB delivery
1. Migration order: `001_create_users.sql`, `002_create_categories.sql`, `003_create_products.sql`, `004_create_adjustments.sql`
2. Seed data: one `manager` user (`demo_manager` / env `SEED_MANAGER_PASSWORD`), one `staff` user (`demo_staff` / env `SEED_STAFF_PASSWORD`), two categories (`Beverages`, `Snacks`), two sample products (qty 10 + qty 3 to demonstrate low-stock flag)
3. Athena / NoSQL: not used

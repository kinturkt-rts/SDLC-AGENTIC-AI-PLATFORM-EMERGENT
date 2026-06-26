# Inventory Desk

A minimal warehouse REST API: JWT-authenticated user roles (admin / staff),
category and product CRUD, and atomic stock movements with full audit history.
Built with **FastAPI + SQLAlchemy 2.x + PostgreSQL 15**. Swagger UI at `/docs`
is the demo surface — there is no browser front end in MVP.

## Endpoints

| Method | Path | Auth | Notes |
|--------|------|------|-------|
| GET    | `/health` | none | Liveness probe (FR-1) |
| POST   | `/auth/login` | none | Returns a bearer JWT (FR-2) |
| GET    | `/categories` | admin + staff | Paginated list (FR-4) |
| POST   | `/categories` | admin only | Auto-derives slug; 409 on duplicate |
| GET    | `/categories/{id}` | admin + staff | Includes `product_count` |
| PATCH  | `/categories/{id}` | admin only | Partial update |
| GET    | `/products` | admin + staff | Filters: `category_id`, `sku`, `low_stock=true` (FR-6) |
| POST   | `/products` | admin only | Starts at `qty_on_hand=0`; 409 on duplicate SKU |
| GET    | `/products/{id}` | admin + staff | |
| PATCH  | `/products/{id}` | admin only | `qty_on_hand` ignored — use adjust-stock |
| DELETE | `/products/{id}` | admin only | 409 when `qty_on_hand > 0` (FR-9) |
| POST   | `/products/{id}/adjust-stock` | admin + staff | Atomic; 422 on negative result (FR-7) |
| GET    | `/products/{id}/movements` | admin + staff | Newest-first, paginated (FR-8) |

All list endpoints return `{items, total, limit, offset}`.

## Environment variables

Copy `.env.example` to `.env` and fill in real values. The application aborts
startup with a non-zero exit code if `DATABASE_URL` or `JWT_SECRET_KEY` are
missing (FR-12).

| Variable | Required | Default | Purpose |
|----------|----------|---------|---------|
| `DATABASE_URL` | yes | — | SQLAlchemy DSN, e.g. `postgresql+psycopg://user:pwd@host:5432/db` |
| `POSTGRES_SCHEMA` | no | `inventory_app` | Schema set on `search_path` per session |
| `JWT_SECRET_KEY` | yes | — | HS256 signing secret. Generate with `python -c "import secrets; print(secrets.token_urlsafe(48))"` |
| `JWT_ALGORITHM` | no | `HS256` | |
| `JWT_EXPIRE_MINUTES` | no | `60` | Token lifetime |
| `PORT` | no | `8000` | uvicorn bind port |
| `APP_ENV` | no | `development` | Toggles SQL echo |
| `LOG_LEVEL` | no | `INFO` | |
| `CORS_ORIGINS` | no | _empty_ | Comma-separated allowed origins |

## Local development

```bash
# 1. From repository root
cd target-apps/inventory-app

# 2. Create a virtualenv and install
python -m venv .venv
source .venv/bin/activate           # Windows: .venv\Scripts\activate
pip install -r requirements.txt

# 3. Configure environment
cp .env.example .env
# edit .env to set DATABASE_URL and JWT_SECRET_KEY

# 4. Apply DDL + seed (Postgres 13+ required)
psql "$DATABASE_URL" -f db/sql/001_create_enums_and_users.sql
psql "$DATABASE_URL" -f db/sql/002_create_categories.sql
psql "$DATABASE_URL" -f db/sql/003_create_products.sql
psql "$DATABASE_URL" -f db/sql/004_create_stock_movements.sql
psql "$DATABASE_URL" -f db/sql/011_seed.sql

# 5. Run
uvicorn app.main:app --reload --port "${PORT:-8000}"

# 6. Open Swagger UI
# → http://localhost:8000/docs
```

### Seed credentials (dev only — **rotate before production**)

| Username | Password | Role |
|----------|----------|------|
| `admin`  | `Admin123!` | admin |
| `staff`  | `Staff123!` | staff |

> ⚠️ The seed bcrypt hashes ship with the dev SQL. Replace them or run
> `python -c "from app.security import hash_password; print(hash_password('your-pw'))"`
> to generate fresh hashes before any non-dev deployment. (PRD NFR-10.)

### curl walkthrough

```bash
# Login as admin
TOKEN=$(curl -s -X POST http://localhost:8000/auth/login \
  -H 'Content-Type: application/json' \
  -d '{"username":"admin","password":"Admin123!"}' | jq -r .access_token)

# Create a category
curl -s -X POST http://localhost:8000/categories \
  -H "Authorization: Bearer $TOKEN" \
  -H 'Content-Type: application/json' \
  -d '{"name":"Office Supplies"}'

# Adjust stock as staff
STAFF_TOKEN=$(curl -s -X POST http://localhost:8000/auth/login \
  -H 'Content-Type: application/json' \
  -d '{"username":"staff","password":"Staff123!"}' | jq -r .access_token)
curl -s -X POST "http://localhost:8000/products/<product-id>/adjust-stock" \
  -H "Authorization: Bearer $STAFF_TOKEN" \
  -H 'Content-Type: application/json' \
  -d '{"delta":-1,"reason":"sale","note":"counter sale"}'
```

## Tests

```bash
pytest
```

Baseline run uses an in-memory **SQLite** database (no Postgres required),
which is sufficient for route shape, role enforcement, pagination, and
adjust-stock semantics. To exercise the same suite against Postgres
(recommended per PRD NFR-11), set `TEST_DATABASE_URL`:

```bash
export TEST_DATABASE_URL=postgresql+psycopg://user:pwd@localhost:5432/inventory_app_test
pytest
```

## Project layout

```
target-apps/inventory-app/
├── app/
│   ├── main.py             # FastAPI app + lifespan startup guard (FR-12)
│   ├── config.py           # pydantic-settings → env vars
│   ├── database.py         # engine + SessionLocal + search_path hook
│   ├── security.py         # bcrypt + JWT helpers + slugify
│   ├── deps.py             # auth dependency + role guards (FR-3)
│   ├── models/             # SQLAlchemy ORM (mirrors db/sql/)
│   ├── schemas/            # Pydantic v2 DTOs
│   ├── routers/            # auth, categories, products
│   └── services/stock.py   # atomic adjust-stock transaction (NFR-6)
├── tests/                  # pytest baseline (qa-agent extends)
├── db/sql/                 # database-agent migrations + seed (read-only)
├── db/HANDOFF.md           # database-agent handoff (read-only)
├── requirements.txt
├── .env.example
└── README.md
```

## Deployment (AWS dev — devops-agent)

This service is container-ready: it binds to `0.0.0.0:$PORT` (default 8000),
reads all configuration from environment variables (no hard-coded hostnames),
and exposes `GET /health` for ALB / ECS health checks. The devops-agent
will produce the Dockerfile, ECS task definition, and Secrets Manager
bindings; this repository ships application code only.

Required runtime config in AWS (from Secrets Manager / SSM):

- `DATABASE_URL` → RDS PostgreSQL DSN
- `JWT_SECRET_KEY` → rotated at deploy
- `POSTGRES_SCHEMA=inventory_app`

## References

- Product brief: [`docs/PRD/inventory-app.md`](../../docs/PRD/inventory-app.md)
- Solution design: [`docs/design/inventory-app.md`](../../docs/design/inventory-app.md)
- Database handoff: [`db/HANDOFF.md`](db/HANDOFF.md)

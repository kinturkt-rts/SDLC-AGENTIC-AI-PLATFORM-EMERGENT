# Hot Desk Booking — Solution Design

## 1. Summary
API-only hot desk booking system for hybrid office teams. Employees reserve desks by date/time-slot with conflict prevention via PostgreSQL UNIQUE constraints. FastAPI REST service with token-based auth.

## 2. Stack
| Layer | Technology | Notes |
|-------|------------|-------|
| Load Balancer | ALB | Routes HTTP traffic |
| API | FastAPI | target-apps/desk-booking/ |
| Database | PostgreSQL | Multi-column constraints for conflict detection |
| Deployment | EC2 | Single-AZ MVP deployment |

## 3. Data model
| Table / collection | Columns (name type PK/FK UNIQUE) | Indexes / constraints |
|--------------------|----------------------------------|------------------------|
| zones | id uuid PK, name text UNIQUE, created_at timestamp | name IN ('north', 'south', 'lab') |
| desks | id uuid PK, zone_id uuid FK, label text, is_active boolean, created_at timestamp | FK zones(id) ON DELETE CASCADE |
| users | id uuid PK, email text UNIQUE, full_name text, user_token text UNIQUE, created_at timestamp | Index on user_token |
| bookings | id uuid PK, desk_id uuid FK, user_id uuid FK, booking_date date, slot enum, created_at timestamp | UNIQUE (desk_id, booking_date, slot), FK desks(id), FK users(id) |
| blackouts | id uuid PK, desk_id uuid FK, starts_on date, ends_on date, reason text, created_at timestamp | FK desks(id) ON DELETE CASCADE |

## 4. API surface
| Method | Path | Request | Response | Notes |
|--------|------|---------|----------|-------|
| GET | /zones | - | zones: List[Zone] | All zones with desk counts |
| POST | /bookings | desk_id: uuid, booking_date: date, slot: str | booking: Booking | Creates reservation (409 on conflict) |
| GET | /bookings/mine | - | bookings: List[Booking] | User's bookings with pagination |
| DELETE | /bookings/{booking_id} | - | message: str | Cancel booking (owner/admin only) |
| GET | /availability | date: date, zone_id?: uuid | availability: List[DeskAvailability] | Available slots per desk |
| POST | /blackouts | desk_id: uuid, starts_on: date, ends_on: date, reason: str | blackout: Blackout | Admin creates blackout period |
| DELETE | /blackouts/{blackout_id} | - | message: str | Admin removes blackout |

## 5. Rules
- Auth: X-User-Token header for employees, X-Admin-Key for admin routes (/blackouts)
- One booking per user per date (validated in endpoint logic)
- Booking window: 1-30 days from current date
- Time slots: full/am/pm with conflict detection (full blocks am+pm)
- Audit: Log all 409 conflicts with desk_id, date, slot context
- Blackout periods block all booking attempts during date ranges

## 6. DB delivery
1. Migration order: `001_zones.sql`, `002_desks.sql`, `003_users.sql`, `004_bookings.sql`, `005_blackouts.sql`
2. Seed data: 3 zones (north/south/lab), 10 desks per zone, 5 test users with tokens
3. Enum types: CREATE TYPE slot_type AS ENUM ('full', 'am', 'pm')

"""Shared PostgreSQL / SQLite compatible column types."""
from __future__ import annotations

import enum

from sqlalchemy import Enum as SAEnum, String
from sqlalchemy.dialects.postgresql import UUID as PG_UUID


# ── Python enums ─────────────────────────────────────────────────────────────

class UserRole(str, enum.Enum):
    it_admin = "it_admin"
    it_staff = "it_staff"
    finance_readonly = "finance_readonly"


class AssetType(str, enum.Enum):
    laptop = "laptop"
    monitor = "monitor"
    phone = "phone"
    license = "license"
    misc = "misc"


class AssetStatus(str, enum.Enum):
    in_stock = "in_stock"
    assigned = "assigned"
    repair = "repair"
    retired = "retired"


class AssignmentEventType(str, enum.Enum):
    assign = "assign"
    return_ = "return"


# ── SQLAlchemy column types ──────────────────────────────────────────────────

SCHEMA = "it_asset_lifecycle"

UserRoleType = SAEnum(
    UserRole,
    name="user_role",
    schema=SCHEMA,
    create_type=False,
    native_enum=True,
    values_callable=lambda x: [e.value for e in x],
).with_variant(String(30), "sqlite")

AssetTypeCol = SAEnum(
    AssetType,
    name="asset_type",
    schema=SCHEMA,
    create_type=False,
    native_enum=True,
    values_callable=lambda x: [e.value for e in x],
).with_variant(String(30), "sqlite")

AssetStatusCol = SAEnum(
    AssetStatus,
    name="asset_status",
    schema=SCHEMA,
    create_type=False,
    native_enum=True,
    values_callable=lambda x: [e.value for e in x],
).with_variant(String(30), "sqlite")

AssignmentEventTypeCol = SAEnum(
    AssignmentEventType,
    name="assignment_event_type",
    schema=SCHEMA,
    create_type=False,
    native_enum=True,
    values_callable=lambda x: [e.value for e in x],
).with_variant(String(30), "sqlite")

# UUID column compatible with both Postgres UUID and SQLite String(36)
PGUUID = PG_UUID(as_uuid=False).with_variant(String(36), "sqlite")

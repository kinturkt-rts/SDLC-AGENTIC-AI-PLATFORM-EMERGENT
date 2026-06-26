from sqlalchemy import String
from sqlalchemy.dialects.postgresql import UUID as PG_UUID, ENUM as SAEnum
from enum import Enum


# Enum definitions
class UserRole(str, Enum):
    viewer = "viewer"
    contributor = "contributor"
    admin = "admin"


class UserStatus(str, Enum):
    active = "active"
    inactive = "inactive"


class CollectionMemberRole(str, Enum):
    viewer = "viewer"
    contributor = "contributor"


class DocumentStatus(str, Enum):
    pending = "pending"
    processing = "processing"
    success = "success"
    failed = "failed"


# Column type helpers
def pg_uuid_column():
    """UUID column with SQLite compatibility"""
    return PG_UUID(as_uuid=False).with_variant(String(36), "sqlite")


def user_role_column():
    """User role enum column"""
    return SAEnum(
        UserRole,
        name="user_role",
        schema="jwt_rag_streamlit",  # Default schema, will be overridden by search_path
        create_type=False,
        native_enum=True
    ).with_variant(String(20), "sqlite")


def user_status_column():
    """User status enum column"""
    return SAEnum(
        UserStatus,
        name="user_status",
        schema="jwt_rag_streamlit",
        create_type=False,
        native_enum=True
    ).with_variant(String(20), "sqlite")


def collection_member_role_column():
    """Collection member role enum column"""
    return SAEnum(
        CollectionMemberRole,
        name="collection_member_role",
        schema="jwt_rag_streamlit",
        create_type=False,
        native_enum=True
    ).with_variant(String(20), "sqlite")


def document_status_column():
    """Document status enum column"""
    return SAEnum(
        DocumentStatus,
        name="document_status",
        schema="jwt_rag_streamlit",
        create_type=False,
        native_enum=True
    ).with_variant(String(20), "sqlite")
import os
import pytest
from sqlalchemy import create_engine, event, text
from sqlalchemy.orm import sessionmaker
from fastapi.testclient import TestClient
from unittest.mock import MagicMock
import bcrypt

# Set environment variables BEFORE any app imports
os.environ.setdefault("DATABASE_URL", "sqlite:///./test.db")
os.environ.setdefault("POSTGRES_SCHEMA", "jwt_rag_streamlit")
os.environ.setdefault("APP_ENV", "test")
os.environ.setdefault("SKIP_STARTUP_CHECKS", "1")
os.environ.setdefault("JWT_SECRET_KEY", "test_secret_key")
os.environ.setdefault("AWS_REGION", "us-east-2")
os.environ.setdefault("BEDROCK_REGION", "us-east-2")
os.environ.setdefault("PDF_STORAGE_DIR", "./test_pdfs")

# Now import app modules
from app.main import app
from app.database import Base, get_db
from app.models.user import User
from app.models.collection import Collection, CollectionMembership
from app.models.document import Document, DocumentChunk
from app.models.chat import ChatSession, ChatMessage
from app.models.audit import AuditLog
from app.models.pg_types import UserRole, UserStatus, CollectionMemberRole, DocumentStatus
from app.services.auth import create_access_token, hash_password
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy import String, TypeDecorator

# UUID TypeDecorator for SQLite compatibility
class _UUIDStr(TypeDecorator):
    impl = String
    cache_ok = True
    
    def load_dialect_impl(self, dialect):
        if dialect.name == 'sqlite':
            return dialect.type_descriptor(String(36))
        else:
            return dialect.type_descriptor(PG_UUID(as_uuid=False))
    
    def process_result_value(self, value, dialect):
        if value is not None:
            return str(value)  # Always return string for consistency
        return value

# Test engine setup
TEST_DATABASE_URL = "sqlite:///./test.db"
engine = create_engine(TEST_DATABASE_URL, connect_args={"check_same_thread": False})

# Create schema attachment for SQLite
@event.listens_for(engine, "connect")
def attach_schema(dbapi_connection, connection_record):
    """Attach schema for SQLite testing"""
    cursor = dbapi_connection.cursor()
    cursor.execute("ATTACH DATABASE ':memory:' AS jwt_rag_streamlit")
    cursor.close()

# Patch UUID columns for SQLite
@pytest.fixture(autouse=True)
def patch_uuid_columns(monkeypatch):
    """Patch PG_UUID columns to work with SQLite"""
    def mock_pg_uuid_column():
        return _UUIDStr(36)
    
    monkeypatch.setattr("app.models.pg_types.pg_uuid_column", mock_pg_uuid_column)

# Session setup
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

@pytest.fixture(scope="function")
def db():
    """Create test database session"""
    # Create tables
    Base.metadata.create_all(bind=engine)
    
    # Create session
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()
    
    # Drop tables after each test
    Base.metadata.drop_all(bind=engine)

@pytest.fixture(scope="function")
def client(db):
    """Create test client with database override"""
    def override_get_db():
        try:
            yield db
        finally:
            pass
    
    app.dependency_overrides[get_db] = override_get_db
    
    with TestClient(app) as test_client:
        yield test_client
    
    app.dependency_overrides.clear()

@pytest.fixture
def mock_bedrock(monkeypatch):
    """Mock Bedrock client for testing"""
    fake_client = MagicMock()
    fake_client.invoke_text.return_value = "Test answer based on the provided documents."
    fake_client.invoke_embed.return_value = [0.1] * 1024
    
    monkeypatch.setattr("app.services.bedrock_client.get_bedrock_client", lambda: fake_client)
    monkeypatch.setattr("app.services.ingestion.invoke_embed", lambda text: [0.1] * 1024)
    monkeypatch.setattr("app.services.pgvector_retriever.invoke_embed", lambda text: [0.1] * 1024)
    
    return fake_client

# User fixtures with bcrypt compatibility
def _hash_password_test(password: str) -> str:
    """Hash password for testing (compatible with bcrypt >= 4.0)"""
    return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

@pytest.fixture
def admin_user(db):
    """Create admin user"""
    user = User(
        email="admin@company.com",
        password_hash=_hash_password_test("admin123"),
        role=UserRole.admin,
        status=UserStatus.active
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user

@pytest.fixture
def contributor_user(db):
    """Create contributor user"""
    user = User(
        email="hr@company.com",
        password_hash=_hash_password_test("hr123"),
        role=UserRole.contributor,
        status=UserStatus.active
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user

@pytest.fixture
def viewer_user(db):
    """Create viewer user"""
    user = User(
        email="employee@company.com",
        password_hash=_hash_password_test("emp123"),
        role=UserRole.viewer,
        status=UserStatus.active
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user

@pytest.fixture
def sample_collection(db, admin_user):
    """Create sample collection"""
    collection = Collection(
        name="Employee Handbook",
        description="Official employee policies",
        owner_id=admin_user.id,
        archived=False
    )
    db.add(collection)
    db.commit()
    db.refresh(collection)
    return collection

@pytest.fixture
def sample_document(db, sample_collection, admin_user):
    """Create sample document"""
    document = Document(
        title="Test Policy Document",
        file_path="/test/path/document.pdf",
        collection_id=sample_collection.id,
        status=DocumentStatus.success,
        uploaded_by=admin_user.id
    )
    db.add(document)
    db.commit()
    db.refresh(document)
    return document

@pytest.fixture
def sample_chunk(db, sample_document):
    """Create sample document chunk"""
    chunk = DocumentChunk(
        document_id=sample_document.id,
        content="This is a test policy document with important information about company policies.",
        embedding="0.1,0.2,0.3",  # Mock embedding as comma-separated string
        page_number=1,
        chunk_index=0
    )
    db.add(chunk)
    db.commit()
    db.refresh(chunk)
    return chunk

@pytest.fixture
def collection_membership(db, sample_collection, viewer_user):
    """Create collection membership for viewer"""
    membership = CollectionMembership(
        collection_id=sample_collection.id,
        user_id=viewer_user.id,
        role=CollectionMemberRole.viewer.value
    )
    db.add(membership)
    db.commit()
    db.refresh(membership)
    return membership

@pytest.fixture
def auth_headers_admin(admin_user):
    """Get auth headers for admin user"""
    token = create_access_token(admin_user)
    return {"Authorization": f"Bearer {token}"}

@pytest.fixture
def auth_headers_contributor(contributor_user):
    """Get auth headers for contributor user"""
    token = create_access_token(contributor_user)
    return {"Authorization": f"Bearer {token}"}

@pytest.fixture
def auth_headers_viewer(viewer_user):
    """Get auth headers for viewer user"""
    token = create_access_token(viewer_user)
    return {"Authorization": f"Bearer {token}"}

# JWT RAG Streamlit — Solution Design

## 1. Summary
Internal policy RAG portal enabling JWT-authenticated employees to upload PDFs and query policy documents via natural language chat. Uses PostgreSQL with pgvector for semantic search and Bedrock Claude for LLM responses. TBD: document versioning, compliance log retention periods.

## 2. Stack
| Layer | Technology | Notes |
|-------|------------|-------|
| UI | Streamlit | ui/streamlit_app.py calls FastAPI over HTTP (port 8501) |
| API | FastAPI | target-apps/jwt-rag-streamlit/ with JWT Bearer auth |
| Database | PostgreSQL + pgvector | Vector similarity search for document chunks |
| LLM | Amazon Bedrock Claude Sonnet v4 | Natural language question answering |
| Embeddings | Amazon Bedrock Titan Embed v2 | 1024-dimension document embeddings |
| Storage | Local filesystem | PDF_STORAGE_DIR for document files |

## 3. Data model
| Table | Columns | Indexes / constraints |
|-------|---------|---------------------|
| users | id SERIAL PK, email VARCHAR UNIQUE NOT NULL, password_hash VARCHAR NOT NULL, role ENUM('viewer','contributor','admin'), status ENUM('active','inactive'), created_at TIMESTAMP | idx_users_email, idx_users_role |
| collections | id SERIAL PK, name VARCHAR UNIQUE NOT NULL, description TEXT, owner_id INT FK(users.id), archived BOOLEAN DEFAULT false, created_at TIMESTAMP | idx_collections_owner, idx_collections_archived |
| collection_memberships | id SERIAL PK, collection_id INT FK(collections.id), user_id INT FK(users.id), role ENUM('viewer','contributor'), created_at TIMESTAMP | UNIQUE(collection_id, user_id) |
| documents | id SERIAL PK, title VARCHAR NOT NULL, file_path VARCHAR NOT NULL, collection_id INT FK(collections.id), status ENUM('pending','processing','success','failed'), uploaded_by INT FK(users.id), created_at TIMESTAMP | idx_documents_collection, idx_documents_status |
| document_chunks | id SERIAL PK, document_id INT FK(documents.id), content TEXT NOT NULL, embedding VECTOR(1024), page_number INT, chunk_index INT, created_at TIMESTAMP | idx_chunks_embedding USING hnsw(embedding vector_cosine_ops) |
| chat_sessions | id SERIAL PK, collection_id INT FK(collections.id), user_id INT FK(users.id), created_at TIMESTAMP | idx_sessions_user_collection |
| chat_messages | id SERIAL PK, session_id INT FK(chat_sessions.id), content TEXT NOT NULL, is_user BOOLEAN NOT NULL, confidence_score FLOAT, citations JSONB, created_at TIMESTAMP | idx_messages_session |
| audit_log | id SERIAL PK, user_id INT FK(users.id), action VARCHAR NOT NULL, resource_type VARCHAR, resource_id INT, details JSONB, ip_address INET, created_at TIMESTAMP | idx_audit_user_action, idx_audit_created_at |

## 4. API surface
| Method | Path | Request | Response | Notes |
|--------|------|---------|----------|-------|
| POST | /auth/token | TokenRequest(email, password) | TokenResponse(access_token, token_type, expires_in) | JWT authentication |
| GET | /auth/me | - | UserProfile(id, email, role, collections) | Current user info |
| GET | /collections | - | List[CollectionSummary] | User's accessible collections |
| POST | /collections | CreateCollection(name, description) | Collection | Admin/contributor only |
| POST | /collections/{id}/documents | FormData(file, title) | Document | PDF upload with ingestion |
| GET | /collections/{id}/documents | - | List[DocumentSummary] | Collection documents |
| POST | /collections/{id}/chat | ChatRequest(message, session_id?) | ChatResponse(answer, confidence, citations, session_id) | RAG query |
| GET | /collections/{id}/chat/{session_id} | - | List[ChatMessage] | Chat history |
| POST | /collections/{id}/members | AddMember(user_id, role) | Membership | Admin only |
| GET | /health | - | HealthStatus(api, database, bedrock) | System health check |

## 5. Rules
- Auth: JWT Bearer tokens (60min expiry), bcrypt password hashing
- RBAC: viewer (chat only), contributor (+ upload), admin (+ collection mgmt)
- Collection access: users must have membership to view/interact
- RAG confidence: answers below 0.25 threshold return honest refusal
- Audit: log all uploads, queries, auth events with user context and timestamps
- Document processing: chunk PDFs into ~500 token segments with overlap
- Citation format: include document title, page number, confidence score
- Session isolation: chat sessions scoped to collection + user

## 6. DB delivery
1. Migration order: `001_users.sql`, `002_collections.sql`, `003_memberships.sql`, `004_documents.sql`, `005_chunks.sql`, `006_chat.sql`, `007_audit.sql`
2. Seed data: admin user (admin@company.com), sample collection ("Employee Handbook"), test PDF document
3. pgvector setup: `CREATE EXTENSION vector;` with HNSW index on embedding column

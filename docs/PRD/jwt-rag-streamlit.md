# Internal Policy RAG Portal PRD

## 1. Overview

HR and IT teams maintain internal policy PDFs (handbooks, security standards, expense policies) in scattered shared drives, leading to employees repeatedly asking the same questions in Slack channels. The **Policy RAG Portal** addresses this by providing a centralized, searchable knowledge base where authorized staff can upload policy documents into organized collections and employees can ask natural-language questions through an intuitive chat interface.

The solution leverages JWT-based authentication with role-based access control, pgvector for semantic search, and Amazon Bedrock for natural language processing. All answers are grounded in retrieved document chunks with proper citations, and low-confidence responses trigger honest refusals rather than hallucinations. This system serves as a comprehensive end-to-end validation of the product-to-development pipeline with real authentication flows.

## 2. Goals & Success Metrics

| Goal | Metric | Target | Notes |
|------|--------|--------|-------|
| Reduce repetitive policy questions | Slack policy questions per week | 50% reduction | Baseline measurement needed |
| Improve policy accessibility | Employee satisfaction with policy search | 4.0/5.0 rating | Quarterly survey |
| Ensure answer accuracy | Citation accuracy rate | >95% | Manual review of sample queries |
| Maintain security compliance | Zero unauthorized access incidents | 0 incidents | Monthly security audit |
| Enable self-service policy lookup | Response time to policy questions | <30 seconds | P95 end-to-end latency |

## 3. Non-Goals / Out of Scope

• S3 storage integration (using local PDF storage for MVP)
• OpenSearch or external vector databases 
• Cognito/OAuth SSO integration
• OCR processing for scanned PDFs
• Multi-tenant organization isolation
• React/Next.js frontend (Streamlit for MVP)
• Docker deployment and container orchestration
• Email-based password reset functionality
• Real-time collaboration features
• Mobile application support

## 4. Users & Use Cases

| Persona | Need | Primary use case |
|---------|------|------------------|
| Policy Viewer (Employee) | Quick answers to policy questions without hunting through PDFs | Search for expense policy limits, vacation accrual rules, security requirements |
| Policy Contributor (HR/IT Staff) | Upload and manage policy documents in their domain | Upload new employee handbook, update security standards, organize documents by category |
| Policy Administrator (HR/IT Manager) | Full control over collections, users, and system oversight | Create new policy collections, assign access permissions, monitor usage patterns |

## 5. Functional Requirements

| ID | Description | Priority | Acceptance criteria (Given / When / Then) |
|----|-------------|----------|---------------------------------------------|
| FR-1 | JWT-based user authentication | P0 | Given valid email/password, When user calls POST /auth/token, Then system returns JWT with role and expiration |
| FR-2 | Role-based document collection access | P0 | Given user with viewer role, When accessing collection they're not member of, Then system returns 403 forbidden |
| FR-3 | PDF document upload and ingestion | P0 | Given contributor user, When uploading PDF to assigned collection, Then system chunks, embeds, and indexes content |
| FR-4 | Natural language policy question answering | P0 | Given viewer user in collection, When asking question via chat, Then system returns answer with document citations or honest refusal |
| FR-5 | Document citation and confidence scoring | P0 | Given chat response, When answer is provided, Then system includes document title, page number, and confidence score |
| FR-6 | Collection membership management | P1 | Given admin user, When assigning user to collection with role, Then user gains appropriate access permissions |
| FR-7 | Query and upload audit logging | P1 | Given any user action, When performing uploads or queries, Then system logs action with timestamp and user context |
| FR-8 | Streamlit UI with role-gated features | P0 | Given logged-in user, When accessing UI, Then appropriate tabs display based on user role (chat, documents, collections, audit) |
| FR-9 | Document ingestion status tracking | P1 | Given uploaded document, When processing occurs, Then status updates to pending/processing/success/failed with visibility to uploader |
| FR-10 | Chat session history | P2 | Given user with chat history, When returning to collection, Then previous conversations remain accessible with context |

## 6. Non-Functional Requirements

| ID | Category | Target | Measurement / verification | Notes |
|----|----------|--------|---------------------------|-------|
| NFR-1 | Security | JWT tokens expire in 60 minutes, bcrypt password hashing | Token validation testing, password hash verification | No plaintext passwords in database |
| NFR-2 | Performance | Chat responses <30 seconds P95 | API response time monitoring | Includes embedding, retrieval, and LLM generation |
| NFR-3 | Availability | 99.5% uptime during business hours | Health check endpoint monitoring | Excludes planned maintenance windows |
| NFR-4 | Scalability | Support 100 concurrent users | Load testing with simulated chat requests | Based on expected initial user base |
| NFR-5 | Data Privacy | All user actions logged for audit | Audit log completeness verification | Supports compliance requirements |
| NFR-6 | Reliability | Confidence threshold 0.25 for answer refusal | Manual accuracy testing of low-confidence responses | Prevents hallucinated responses |
| NFR-7 | Observability | Health checks for API and database | GET /health endpoint returns component status | Enables monitoring and alerting |

## 7. Data & Integrations

**Core Entities:**
- Users (email, hashed password, role, status)
- Collections (name, description, owner, archive status)
- Documents (title, file path, ingestion status, metadata)
- Document chunks (text content, embeddings, page references)
- Chat sessions and messages with confidence scoring
- Comprehensive audit logs for all user actions

**External Integrations:**
- Amazon Bedrock Claude Sonnet v4 for natural language answers
- Amazon Bedrock Titan Embed v2 for 1024-dimension embeddings
- PostgreSQL with pgvector extension for semantic similarity search
- Local filesystem storage for PDF documents (PDF_STORAGE_DIR)

## 8. Analytics & Observability

**Key Metrics:**
- Query volume by collection and user role
- Document upload frequency and ingestion success rates
- Chat response confidence score distributions
- Authentication failure rates and patterns
- API endpoint latency and error rates

**Monitoring:**
- Health check endpoint for API and database connectivity
- Audit log analysis for security and usage patterns
- Embedding generation and retrieval performance metrics
- JWT token validation and expiration tracking

## 9. Risks & Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| Unauthorized access to sensitive policies | High | JWT authentication with role-based access control, comprehensive audit logging |
| Poor answer quality from RAG pipeline | Medium | Confidence thresholds, citation requirements, honest refusal for low-confidence responses |
| PDF ingestion failures | Medium | Status tracking, error handling, retry mechanisms for processing pipeline |
| Database performance with vector similarity | Medium | Proper indexing on embedding columns (HNSW/ivfflat), query optimization |
| Bedrock service availability | Medium | Graceful error handling, clear user messaging when LLM unavailable |

## 10. Open Questions

| # | Question | Suggested owner |
|---|----------|-----------------|
| 1 | What is the expected volume of policy documents and concurrent users? | Product Manager |
| 2 | Are there specific compliance requirements for audit log retention? | Legal/Compliance team |
| 3 | Should the system support versioning of policy documents? | HR/IT stakeholders |
| 4 | What level of document preview/display is needed beyond chat citations? | UX/Product team |
| 5 | Are there integration requirements with existing HR systems or Active Directory? | IT Architecture team |

## 11. Delivery & Client Surface

| Concern | Choice | Implementation notes |
|---------|--------|---------------------|
| Client UI | Streamlit | Login page, role-gated tabs (Chat, Documents, Collections, Audit), sidebar with user context |
| API | FastAPI under `target-apps/jwt-rag-streamlit/` | REST + OpenAPI with JWT Bearer authentication |
| UI location | `ui/streamlit_app.py` | HTTP client to API only via httpx — never import `app/` from Streamlit |
| Auth for UI | JWT Bearer tokens | Streamlit stores token in session state, sends on every API call |

## Appendix: Assumptions

• Initial user base of approximately 100 employees across HR, IT, and general staff
• Policy documents are primarily text-based PDFs without complex formatting requirements  
• English language content only for MVP deployment
• Standard business hours usage patterns with minimal weekend activity
• Existing PostgreSQL RDS instance available with pgvector extension support
• AWS Bedrock access configured with appropriate service limits for expected usage
• Local development environment supports Python 3.12 and required dependencies
• Network connectivity allows API calls between Streamlit UI and FastAPI backend on different ports
• Bcrypt password hashing provides sufficient security for internal employee authentication
• 60-minute JWT expiration balances security with user experience for typical session lengths

# Benefits Q&A Desk — Product Requirements Document

## 1. Overview

HR benefit guides, enrollment handbooks, and policy PDFs are typically scattered across shared drives, leading employees to rely on outdated copies or repeat the same questions to HR staff every enrollment cycle. There is no single authoritative, searchable source of truth tied directly to current documents, and HR teams bear the burden of answering repetitive queries manually.

The Benefits Q&A Desk is an internal web application that lets HR contributors upload and organize benefit documents into named collections, and lets employees ask plain-English questions against those collections. Every answer is grounded exclusively in the uploaded content and includes document citations (file name + relevant snippet). If the documents do not support an answer, the system explicitly responds "Not found in documents" rather than guessing. A lightweight audit trail supports demo and compliance review needs.

The MVP ships as a FastAPI backend (Postgres for app data and document text search, Amazon Bedrock for LLM-based retrieval and answer generation) with a Streamlit frontend that communicates only through the API. Role-based access controls enforce a clear separation between employees (ask only), HR contributors (upload and manage), and admins (audit visibility). Demo seed data ensures a walkthrough is immediately functional from first launch.

---

## 2. Goals & Success Metrics

| Goal | Metric | Target | Notes |
|------|--------|--------|-------|
| Eliminate repeated HR Q&A burden | % of benefit questions answered by the system without HR intervention | ≥ 70 % of demo-session queries resolved with a citation | Measured during acceptance / demo |
| Grounded answers only | Rate of "invented" answers (answers not traceable to an uploaded document) | 0 % — system must return "Not found" when unsupported | Verified by test queries against known gaps |
| Successful demo path completion | End-to-end login → upload → ask → cited answer runs without error | 100 % success rate across three consecutive dry runs | Demo readiness gate |
| Fast document readiness | Time from upload submission to "Ready" status | ≤ 2 minutes for PDFs ≤ 20 MB | P95 target (Assumption) |
| Audit coverage | Fraction of upload and Q&A events captured in audit log | 100 % of all events recorded | Verified by log inspection |
| Role enforcement | Unauthorized actions blocked at API layer | 0 unauthorized actions succeed in security test suite | Automated test gate |

---

## 3. Non-Goals / Out of Scope

- Corporate SSO / SAML / OAuth integration (deferred post-MVP)
- Real-time document co-editing or version-controlled document workflows
- Public-facing or internet-accessible deployment
- Direct integration with HRIS, payroll, or benefits administration platforms
- Support for video, audio, or binary non-text file formats (e.g., `.xlsx` with embedded charts, `.pptx`) unless they yield extractable text
- End-user self-registration (accounts created by admin seeding or admin UI)
- Multi-tenant isolation across separate companies or business units
- Email or Slack notifications for processing status
- Analytics dashboards beyond the basic audit trail
- Mobile-native applications

---

## 4. Users & Use Cases

| Persona | Need | Primary use case |
|---------|------|------------------|
| **Employee** | Get a quick, trustworthy answer to a benefits question without emailing HR | Selects an accessible collection, types a plain-English question, receives a cited answer or "Not found" |
| **HR Contributor** | Keep benefit documents current and well-organized for employees | Creates/edits collections, uploads new or updated PDFs, monitors processing status, manages FAQ topic labels |
| **Admin** | Oversee system activity for governance, demos, and troubleshooting | Reviews the audit trail of all uploads and Q&A events; manages users and collections at a high level |
| **Demo Presenter** | Walk stakeholders through the full product value in one sitting | Uses seeded demo users, a pre-loaded collection, and live Q&A to show login → upload → ask → citation flow |

---

## 5. Functional Requirements

| ID | Description | Priority | Acceptance criteria (Given / When / Then) |
|----|-------------|----------|-------------------------------------------|
| FR-1 | **User Authentication — Username/Password Sign-In** | P0 | **Given** a user with valid credentials exists in the system, **When** they submit their username and password via the Streamlit sign-in screen, **Then** the API returns a session token, the UI stores it in session state, and the user is directed to their role-appropriate home view. **Given** invalid credentials, **When** submitted, **Then** the API returns HTTP 401 and the UI displays a clear error message without revealing whether the username or password was wrong. |
| FR-2 | **Role-Based Access Control** | P0 | **Given** a logged-in user, **When** they attempt any API action, **Then** the API enforces their role: Employees may only read collections and submit/view their own Q&A; Contributors may additionally create/edit collections and upload documents; Admins may additionally read the full audit trail and manage FAQ topics. Any out-of-role request returns HTTP 403. Role is evaluated server-side; the Streamlit UI hides controls but API enforcement is the authoritative gate. |
| FR-3 | **Collection Management (CRUD)** | P0 | **Given** a logged-in Contributor or Admin, **When** they create a collection with a unique name and optional short description, **Then** the collection is persisted and appears in the collection list for all roles with access. **When** they edit the name or description, **Then** changes are reflected immediately. **When** they attempt to create a collection with a duplicate name, **Then** the API returns HTTP 409 with a descriptive error. Deletion is out of scope for MVP unless no documents are attached (Assumption). |
| FR-4 | **Document Upload with Processing Status** | P0 | **Given** a logged-in Contributor, **When** they upload a supported file (PDF, plain text, DOCX — Assumption) to a collection, **Then** the system creates a document record with status `waiting`, transitions it through `processing`, and settles on `ready` or `failed`. **Given** an unsupported file type, **When** uploaded, **Then** the API rejects the file with HTTP 422 and a human-readable error identifying the unsupported type. The document list for that collection reflects the current status of every file without requiring a page reload beyond a manual refresh (polling acceptable for MVP). |
| FR-5 | **Document List per Collection** | P1 | **Given** a logged-in user with access to a collection, **When** they navigate to that collection's document list, **Then** they see each document's file name, upload date/time, uploader username, and current processing status (`waiting` / `processing` / `ready` / `failed`). |
| FR-6 | **Grounded Q&A with Citations** | P0 | **Given** a logged-in Employee (or any role) and at least one `ready` document in a collection, **When** the user selects a collection and submits a plain-English question, **Then** the API queries Amazon Bedrock using only the content of that collection's documents and returns either: (a) an answer with one or more citations (document name + short verbatim or near-verbatim snippet from the source), or (b) the exact phrase "Not found in documents" when the uploaded content does not support an answer. The API must never fabricate policy details not present in the documents. |
| FR-7 | **FAQ Topic Label Management (CRUD)** | P1 | **Given** a logged-in Contributor or Admin, **When** they create a FAQ topic label (e.g., "Enrollment", "Dental", "Parental Leave"), **Then** the label is persisted and appears in the topic catalog. Labels can be edited and deleted. Labels are informational only — chat queries still route through the document-backed Q&A engine regardless of selected label. |
| FR-8 | **Audit Trail Recording and Viewing** | P0 | **Given** any user performs a document upload or Q&A event (success or "not found"), **Then** the system records: actor username, role, action type, target resource (collection/document name), timestamp, and outcome. **Given** a logged-in Admin, **When** they navigate to the audit trail view, **Then** they see a paginated list of all recorded events. Employees and Contributors receive HTTP 403 when accessing the audit endpoint. |
| FR-9 | **Streamlit UI Implementing Primary User Journeys** | P0 | **Given** the Streamlit application is running, **When** any user navigates to it, **Then** they are presented with a sign-in screen. After authentication, role-based views are displayed: Employees see collection selector and chat; Contributors additionally see upload and document list screens; Admins additionally see audit trail and FAQ management. The Streamlit app communicates exclusively with the FastAPI backend via HTTP; it imports no `app/` modules directly. All error responses from the API are surfaced to the user with a human-readable message. |
| FR-10 | **Demo Seed Data** | P0 | **Given** a fresh environment after running the seed script, **Then** the database contains: at least one Admin user, one HR Contributor user, and one Employee user with documented credentials; at least one collection (e.g., "2026 Benefits Demo") containing at least one pre-processed `ready` document; and at least one FAQ topic label. A demo walkthrough (login → upload → ask → citation) must complete without any manual data setup beyond running the seed. |

---

## 6. Non-Functional Requirements

| ID | Category | Target | Measurement / verification | Notes |
|----|----------|--------|---------------------------|-------|
| NFR-1 | Security / Auth | All API endpoints except `/health` require a valid bearer token; tokens expire after 8 hours | Automated test: unauthenticated requests return HTTP 401; expired tokens return HTTP 401 | (Assumption) token TTL of 8 hours; adjust to org policy |
| NFR-2 | Security / Role Enforcement | Zero privilege-escalation paths; role checked server-side on every request | Penetration / unit tests covering all role × endpoint combinations | Must not rely solely on Streamlit UI hiding |
| NFR-3 | Security / Data at Rest | Document text stored in Postgres with access restricted to the application service account | Infrastructure review; no direct public DB exposure | (Assumption) deployment environment controls DB network access |
| NFR-4 | Performance — Q&A Latency | P95 end-to-end Q&A response ≤ 10 seconds for collections up to 50 documents | Load test with representative query set; measured at API layer | (Assumption) Bedrock model latency is the dominant factor |
| NFR-5 | Performance — Upload Processing | P95 time from upload acceptance to `ready` status ≤ 2 minutes for files ≤ 20 MB | Timed integration test with a 15 MB sample PDF | (Assumption) file size cap of 20 MB per document |
| NFR-6 | Availability | API uptime ≥ 99 % during business hours in demo/staging environment | Uptime monitoring (e.g., health-check endpoint pinged every 60 seconds) | (Assumption) non-production SLA; production targets TBD |
| NFR-7 | Scalability | System handles ≥ 20 concurrent Q&A sessions without degradation beyond NFR-4 target | Concurrent load test with 20 simulated users | (Assumption) MVP scale; horizontal scaling deferred |
| NFR-8 | Observability | Structured JSON logs for every API request (method, path, user ID, role, status code, latency); errors logged with stack trace | Log output verified in local and staging runs; sample Splunk / CloudWatch query documented | (Assumption) log destination TBD by infra team |
| NFR-9 | Compliance / Data Retention | Audit log records retained for a minimum of 90 days; document files and extracted text retained until explicitly deleted by an Admin | Retention policy documented; automated test checks records exist 90+ days post-creation | (Assumption) 90-day floor; legal minimum TBD |
| NFR-10 | Operability | Service starts with a single `docker compose up`; seed script runs with one command; README covers all setup steps | New-engineer setup test: ≤ 30 minutes from clone to running demo | (Assumption) Docker is available in the deployment environment |
| NFR-11 | Privacy | Audit log entries must not store the full text of employee questions; store question hash or truncated form (≤ 100 chars) | Code review + data inspection of audit table | Protects potentially sensitive benefits questions |

---

## 7. Data & Integrations

### Core Data Entities (Postgres)

| Entity | Key Attributes |
|--------|---------------|
| `users` | `id`, `username`, `hashed_password`, `role` (`employee` / `contributor` / `admin`), `created_at`, `is_active` |
| `collections` | `id`, `name` (unique), `description`, `created_by_user_id`, `created_at`, `updated_at` |
| `documents` | `id`, `collection_id`, `filename`, `file_type`, `status` (`waiting` / `processing` / `ready` / `failed`), `uploaded_by_user_id`, `uploaded_at`, `updated_at`, `error_message` |
| `document_chunks` | `id`, `document_id`, `chunk_text`, `chunk_index`, `embedding_vector` (if stored in Postgres via pgvector — see note) |
| `faq_topics` | `id`, `label`, `created_by_user_id`, `created_at`, `updated_at` |
| `audit_events` | `id`, `user_id`, `role_at_time`, `action_type`, `resource_type`, `resource_id`, `resource_name`, `outcome`, `question_excerpt` (≤ 100 chars), `timestamp` |

### External Integrations

| System | Purpose | Notes |
|--------|---------|-------|
| **Amazon Bedrock** | LLM inference for answer generation; embedding model for semantic chunk matching | Model IDs TBD (e.g., Anthropic Claude on Bedrock for answers; Amazon Titan Embeddings or Cohere for vectors) — see Open Questions |
| **Postgres (+ pgvector extension)** | Relational app data + vector similarity search over document chunks | Alternatively, Bedrock Knowledge Bases could manage embeddings — architecture decision in Open Questions |
| **File storage (local / S3)** | Raw uploaded files persisted before text extraction | Local volume acceptable for MVP; S3 recommended for staging (Assumption) |

---

## 8. Analytics & Observability

**Structured Logging**
- Every API request emits a JSON log line: timestamp, request ID, user ID (not username in plain text), role, HTTP method, path, response status, latency ms.
- Background document-processing jobs log status transitions with document ID, collection ID, step name, and duration.
- Errors include full stack traces at `ERROR` level.

**Key Application Metrics** (to be wired to a monitoring target TBD)
- `qa_requests_total` — counter by outcome (`cited_answer` / `not_found` / `error`)
- `document_processing_duration_seconds` — histogram by file type
- `upload_total` — counter by status (`accepted` / `rejected_type` / `rejected_size`)
- `active_sessions` — gauge of authenticated sessions

**Alerts** (Assumption — thresholds TBD by ops team)
- Q&A error rate > 5 % over 5-minute window → page on-call
- Document processing queue depth > 10 unprocessed items for > 5 minutes → warning alert
- API P95 latency > 15 seconds → warning alert

**Audit Trail UI**
- Admin-facing paginated table in Streamlit surfacing `audit_events`; filterable by date range, action type, and username.

---

## 9. Risks & Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| Amazon Bedrock returns a fabricated answer not grounded in documents | High — employees act on incorrect benefits information | Implement strict retrieval-augmented generation (RAG) prompt that instructs the model to answer only from provided context; add automated regression tests with known-gap queries that must return "Not found" |
| Bedrock API quota / throttling under concurrent demo load | Medium — demo stalls, eroding stakeholder confidence | Implement request queuing and exponential back-off; cache answers for identical question + collection hash pairs (Assumption) |
| Large or malformed PDFs cause processing failures or timeouts | Medium — contributor uploads fail silently | Enforce file size limit (20 MB, Assumption); validate MIME type on ingest; surface `failed` status with error message; provide retry option |
| Sensitive employee question text stored in logs / audit trail | Medium — privacy / HR policy concern | Store only truncated question excerpt (≤ 100 chars) in audit log; exclude full text from structured logs; document data handling policy |
| pgvector not available in target Postgres version | Medium — blocks vector search implementation | Confirm pgvector availability early; fallback option is Bedrock Knowledge Bases managing embeddings externally |
| Demo seed data not matching actual document content | Low-Medium — cited answers during demo refer to wrong file | Seed script must include a real (or realistic synthetic) PDF whose content is known; write demo script queries against confirmed document content |
| Username/password auth insufficient for production rollout | Low for MVP — medium later | Document SSO migration path (SAML/OIDC) as a post-MVP work item; ensure auth layer is abstracted so JWT issuer can be swapped |

---

## 10. Open Questions

| # | Question | Suggested owner |
|---|----------|-----------------|
| 1 | Which Amazon Bedrock model(s) should be used for answer generation (e.g., Claude 3 Sonnet, Claude 3 Haiku) and for embedding generation (e.g., Amazon Titan Embeddings v2, Cohere Embed)? | Tech Lead / ML Engineer |
| 2 | Should embeddings and vector search be managed in Postgres via pgvector, or should Bedrock Knowledge Bases own the document index? This affects architecture of `document_chunks` and the retrieval pipeline. | Tech Lead |
| 3 | What is the maximum supported file size per upload? (20 MB assumed — confirm with HR and infra.) | HR Lead + Infra |
| 4 | Which file formats must be supported at launch beyond PDF? (DOCX and plain text assumed; Word `.doc`, Excel, PowerPoint are TBD.) | HR Lead |
| 5 | Are collection access permissions per-collection (i.e., some collections visible only to certain employee groups), or is all content visible to all employees? | HR Lead + Product |
| 6 | What is the target deployment environment for the demo (local Docker, AWS ECS, EC2)? This affects S3 vs. local file storage and networking for Bedrock access. | Infra / DevOps |
| 7 | Is a 90-day audit log retention floor acceptable, or does HR / legal require a longer period? | HR / Legal |
| 8 | Should the Admin role be able to create and deactivate user accounts through the UI, or is account management handled only via seed script / direct DB for MVP? | Product / HR |
| 9 | Is answer caching for repeated identical questions acceptable (potential staleness after document updates), and if so what is the cache TTL? | Tech Lead + HR |
| 10 | Will the Streamlit UI need to display the full document viewer / PDF inline, or is a citation snippet (file name + text excerpt) sufficient for MVP? | Product / HR |

---

## 11. Delivery & Client Surface

| Concern | Choice | Implementation notes |
|---------|--------|---------------------|
| Client UI | **Streamlit** | Primary user-facing surface for sign-in, collection management, document upload, document list, chat/Q&A, FAQ topics, and audit trail |
| API | **FastAPI** under `target-apps/benefits-qa-desk/` | REST + OpenAPI (Swagger UI auto-generated); all business logic, role enforcement, and Bedrock calls live here |
| UI location | `ui/streamlit_app.py` (with sub-pages per role) | HTTP client (`httpx` or `requests`) to API only — never import `app/` or any backend module from Streamlit |
| Auth for UI | **JWT Bearer token** (username/password → `/auth/token` → JWT) | Streamlit stores token in `st.session_state`; token passed as `Authorization: Bearer <token>` header on every API call; no SSO for MVP |
| Auth for API | FastAPI `Depends` on JWT decode + role check per endpoint | Role embedded in JWT claims; validated server-side on every request |
| Database | **Postgres** (app data + pgvector for embeddings, subject to Open Question 2) | Managed via SQLAlchemy ORM + Alembic migrations |
| LLM / Embeddings | **Amazon Bedrock** (boto3 client in API layer) | Never called from Streamlit directly |
| File storage | Local volume (MVP) → S3 (staging/prod, Assumption) | API handles multipart upload; raw files stored before text extraction |
| Seed script | `scripts/seed_demo.py` — one command | Creates demo users (admin / contributor / employee), one sample collection, at least one pre-processed document, and FAQ topic labels |
| Containerization | `docker-compose.yml` at repo root | Services: `api`, `ui`, `postgres`; single `docker compose up` starts full stack |

---

## Appendix: Assumptions

- **File size limit**: 20 MB per uploaded document. Files exceeding this limit are rejected at the API boundary with a clear error.
- **Supported file types at launch**: PDF (primary), plain text (`.txt`), and DOCX. Other formats (`.doc`, `.xlsx`, `.pptx`) are unsupported unless confirmed.
- **Vector storage**: pgvector Postgres extension is available and used for storing and querying document chunk embeddings. If unavailable, Amazon Bedrock Knowledge Bases is the fallback.
- **JWT token TTL**: 8 hours; configurable via environment variable.
- **Collection access**: All collections are visible to all authenticated employees unless scoped access is confirmed as a requirement (Open Question 5).
- **Collection deletion**: Collections with attached documents cannot be deleted in MVP; only empty collections may be removed.
- **Answer caching**: No caching of Q&A responses in MVP to avoid stale answers after document updates; may be added in a follow-on sprint pending Open Question 9.
- **Admin user management via UI**: Admin users can view users but account creation/deactivation is seed-script-only for MVP, pending answer to Open Question 8.
- **Deployment target**: Local Docker Compose for demo; AWS deployment (ECS or EC2) and S3 file storage are staging/production concerns outside MVP scope.
- **Log destination**: stdout / Docker log driver for MVP; shipping to CloudWatch, Splunk, or equivalent is an infra concern post-demo.
- **Bedrock model selection**: Anthropic Claude (mid-tier model, e.g., Claude 3 Haiku for cost efficiency) for answer generation and Amazon Titan Embeddings v2 for vector generation, pending confirmation in Open Question 1.
- **pgvector chunk strategy**: Documents split into ~500-token overlapping chunks (overlap ~50 tokens) for embedding. Chunk size tunable via config.
- **Audit log question excerpt**: Limited to 100 characters to balance traceability with employee privacy.
- **Demo document**: A synthetic or publicly available benefits summary PDF is included in the seed script to ensure Q&A works out of the box without proprietary HR content.
- **No self-registration**: All user accounts are pre-created via seed script or future admin UI; there is no public sign-up flow.

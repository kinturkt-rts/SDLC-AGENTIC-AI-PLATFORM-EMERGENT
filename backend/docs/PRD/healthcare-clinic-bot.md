# Healthcare Clinic Assistant — FAQ Chatbot PRD

## 1. Overview

Front-desk staff at healthcare clinics spend a disproportionate share of their time answering the same routine questions — office hours, accepted insurance plans, how to book an appointment, parking directions — via phone and email. After hours, patients have no self-service channel and receive no response until the clinic reopens. This creates friction for patients and reduces staff capacity for higher-value work.

This document defines the MVP for a **Healthcare Clinic Assistant**: a conversational FAQ chatbot built with a Streamlit UI and a REST backend API. The chatbot answers common clinic questions by retrieving structured FAQ entries stored in a Postgres database and using AWS Bedrock to compose grounded, natural-language replies. Every answer includes a mandatory medical disclaimer. When no FAQ content matches a query, the assistant honestly says so and directs the user to call the clinic rather than fabricating clinical information.

The MVP is a demo-quality proof-of-concept intended to demonstrate value to stakeholders. It is not a diagnostic tool, not a production HIPAA system, and does not integrate with booking or EHR systems. Success is defined as the application running locally against RDS Postgres, answering seeded FAQ questions correctly, and passing the automated test suite.

---

## 2. Goals & Success Metrics

| Goal | Metric | Target | Notes |
|------|--------|--------|-------|
| Patients receive instant answers to common questions | Grounded FAQ answer returned for questions matching seeded content | 100 % of seeded FAQ topics return a grounded answer in demo | Verified via pytest integration tests |
| Honest fallback when no FAQ match exists | Fallback response rate for out-of-scope questions | 100 % of unmatched queries return fallback + clinic-call suggestion | No fabricated clinical facts allowed |
| Medical disclaimer on every reply | Presence of disclaimer text in every chatbot response | 100 % of responses contain the required disclaimer string | Verified in automated tests |
| Staff can maintain FAQ content without engineering support | Staff can add/update FAQ entries via UI | CRUD operations complete without error in Streamlit admin view | Manual demo acceptance test |
| Sensitive data is not collected or persisted | No SSN, full DOB, or detailed symptom data in database | Zero sensitive-field columns in schema; redirect message shown to user | Schema review + test |
| Local developer setup succeeds | App starts and tests pass against RDS Postgres | `pytest` green; `streamlit run` renders chat UI | CI smoke test |

---

## 3. Non-Goals / Out of Scope

- Appointment booking or calendar integrations (no EHR / FHIR / HL7)
- Telehealth, video, or voice channels
- Production HIPAA hardening, BAA agreements, or audit logging at HIPAA scope
- Multi-clinic tenancy or white-label support
- Document RAG pipeline (no PDF upload, no pgvector, no OpenSearch, no vector embeddings)
- SSO / enterprise identity provider integration (deferred to post-MVP)
- Mobile-native applications
- Prescription refill or test-result delivery
- Diagnostic, triage, or clinical decision support of any kind
- PII collection fields (SSN, full date of birth, insurance member ID, detailed symptom capture)

---

## 4. Users & Use Cases

| Persona | Need | Primary use case |
|---------|------|------------------|
| **Patient / Prospective Patient** | Get quick answers to routine clinic questions at any hour without calling | Opens Streamlit chat, asks "Do you accept Blue Cross?", receives a grounded FAQ answer with medical disclaimer |
| **Front-Desk / Clinical Staff Admin** | Keep FAQ content current without engineering help | Logs in to Streamlit admin view, adds a new FAQ entry for updated parking instructions, sees it reflected in subsequent chat answers |
| **Clinic Stakeholder / Demo Viewer** | Evaluate the chatbot concept before committing to full build | Watches a multi-turn demo conversation; observes honest fallback when an out-of-scope question is asked |
| **Developer / QA Engineer** | Build, test, and iterate on the system locally | Runs `pytest` against local/RDS Postgres, inspects API responses, verifies disclaimer and fallback behavior |

---

## 5. Functional Requirements

| ID | Description | Priority | Acceptance criteria (Given / When / Then) |
|----|-------------|----------|-------------------------------------------|
| FR-1 | **Chat question answering grounded in FAQ** — The chatbot must answer user questions by retrieving relevant FAQ entries from Postgres and using AWS Bedrock to compose a natural-language reply that is grounded solely in that content. | P0 | **Given** the database contains a seeded FAQ entry for "office hours"; **When** the user submits "What are your hours?" in the chat UI; **Then** the API returns a response that references the seeded office-hours content and contains no information absent from the FAQ entries retrieved. |
| FR-2 | **Mandatory medical disclaimer** — Every chatbot response, regardless of topic, must include the standard disclaimer: *"This information is for general purposes only and is not medical advice. For emergencies, call 911. For personal medical questions, please contact the clinic directly."* (exact wording TBD; must be substantively equivalent). | P0 | **Given** any user question (matched or unmatched); **When** the API returns a response; **Then** the response body contains the disclaimer text; verified in automated tests for at least ten distinct question types. |
| FR-3 | **Honest fallback for unmatched questions** — When no FAQ entry is sufficiently relevant to answer a question, the chatbot must respond with an honest "I don't have information on that" message and direct the user to call the clinic. It must not fabricate clinical facts. | P0 | **Given** the user submits a question with no matching FAQ content (e.g., "What is the dosage for ibuprofen?"); **When** the API processes the request; **Then** the response contains a fallback message and clinic-contact suggestion, and contains no invented clinical information; Bedrock is not used to generate clinical content for unmatched queries. |
| FR-4 | **Sensitive data redirect** — If a user message appears to contain or request sensitive personal data (SSN, full date of birth, detailed symptoms, prescription details), the chatbot must decline to process or store that data and redirect the user to call the clinic. No sensitive values are written to the database. | P0 | **Given** the user submits a message containing an SSN-like pattern or asks the chatbot to store personal medical details; **When** the API processes the message; **Then** the API returns a redirect-to-clinic message; the messages table contains no sensitive data fields; verified via test with synthetic sensitive inputs. |
| FR-5 | **Persistent chat sessions and message history** — Each chat session must be assigned a unique session ID and persisted in Postgres. All user messages and assistant responses within a session must be stored and retrievable, enabling multi-turn context within a demo conversation. | P0 | **Given** a user sends three sequential messages in one session; **When** the Postgres `sessions` and `messages` tables are queried; **Then** all three user messages and three assistant responses are present under the correct session ID, in order, with timestamps. |
| FR-6 | **FAQ browsing UI** — The Streamlit application must include a read-only FAQ browser that displays all active FAQ entries (question + answer + category) stored in Postgres, accessible without authentication. | P1 | **Given** the database contains at least five seeded FAQ entries across two categories; **When** a user navigates to the FAQ browser page in Streamlit; **Then** all entries are displayed with their question, answer, and category label; no entries are missing or duplicated. |
| FR-7 | **Staff FAQ management (Create / Update)** — Authenticated staff users must be able to add new FAQ entries and edit existing ones (question, answer, category, active/inactive status) via the Streamlit admin interface. Changes must be reflected in subsequent chat responses immediately. | P1 | **Given** a staff user is logged in; **When** they create a new FAQ entry with question "Is free parking available?" and save it; **Then** the entry appears in the FAQ browser; a subsequent chat query "Where do I park?" retrieves and uses that entry in the Bedrock-grounded response. |
| FR-8 | **Simple developer-friendly authentication** — The MVP must implement a lightweight authentication mechanism (e.g., username/password checked against an environment variable or a seeded users table) that gates access to the staff admin pages. No external identity provider is required for MVP. | P1 | **Given** an unauthenticated user navigates to the admin FAQ management page; **When** the page renders; **Then** the user is presented with a login prompt and cannot access admin functionality without valid credentials. |
| FR-9 | **Backend REST API** — A backend API must expose endpoints for: (a) submitting a chat message and receiving a response, (b) listing/creating/updating FAQ entries, (c) retrieving session message history. The Streamlit UI must consume this API exclusively (no direct DB calls from the UI layer). | P1 | **Given** the API is running; **When** a valid `POST /chat/message` request is submitted with a session ID and user message; **Then** the API returns HTTP 200 with a JSON body containing the assistant reply, session ID, and disclaimer; endpoint contracts verified in pytest. |
| FR-10 | **Seeded FAQ content** — The repository must include a database seed script that populates Postgres with a representative set of FAQ entries covering at minimum: office hours, accepted insurance, appointment booking instructions, parking/directions, and general wellness policy. | P1 | **Given** a fresh Postgres database; **When** the seed script is executed; **Then** at least five FAQ entries exist across at least three categories; `pytest` smoke test confirms entries are present and the chat endpoint returns grounded answers for each seeded topic. |

---

## 6. Non-Functional Requirements

| ID | Category | Target | Measurement / verification | Notes |
|----|----------|--------|---------------------------|-------|
| NFR-1 | Performance | End-to-end chat response (API receipt → response returned to UI) ≤ 8 seconds at p95 | Manual timing during demo; logged response duration in API | (Assumption) Bedrock latency dominates; 8 s is acceptable for demo context |
| NFR-2 | Performance | FAQ CRUD API responses ≤ 500 ms p95 (no Bedrock call) | pytest timing assertions on CRUD endpoints | (Assumption) |
| NFR-3 | Security / Privacy | No sensitive patient data (SSN, full DOB, detailed symptoms) persisted in any database table or log | Schema review; automated test submitting synthetic sensitive inputs verifies no storage | Defined in FR-4; schema must omit sensitive-data columns by design |
| NFR-4 | Security / Privacy | Admin and staff endpoints require authentication; unauthenticated requests return HTTP 401 | pytest: unauthenticated request to admin endpoints returns 401 | MVP uses simple credential check; production SSO deferred |
| NFR-5 | Security / Privacy | AWS Bedrock API keys and database credentials stored in environment variables or secrets manager; never hard-coded or committed to source control | `git grep` for secrets in CI; `.env` in `.gitignore` | (Assumption) |
| NFR-6 | Availability | Application available during stakeholder demo sessions; no SLA required for MVP | Manual verification; no on-call requirement | Demo / POC tier; production availability targets deferred |
| NFR-7 | Scalability | Must support at least 5 concurrent demo users without error | Locust or manual concurrent test with 5 simultaneous chat requests | (Assumption) Demo-scale only; production scaling deferred |
| NFR-8 | Observability | All API requests and Bedrock calls logged with: timestamp, endpoint, session ID (non-PII), response status, latency | Log output visible in console / stdout; structured JSON preferred | (Assumption) No PII in logs |
| NFR-9 | Observability | Application errors and unhandled exceptions captured and surfaced in logs with stack traces | Verified by intentionally triggering an error in local dev | (Assumption) |
| NFR-10 | Operability | Full local setup (DB migrations, seed, app start) achievable by a new developer following the README in under 30 minutes | Peer review of setup instructions; timed dry-run by one developer | (Assumption) |
| NFR-11 | Compliance / Disclaimer | Chatbot is never presented as providing medical diagnoses or clinical advice; disclaimer (FR-2) is non-removable in UI and API response | Code review confirms disclaimer cannot be toggled off; 100 % response coverage verified in tests | Scope is informational FAQ only; not a regulated medical device |
| NFR-12 | Data Retention | Chat session and message data retained for the duration of the demo POC only; no formal retention policy required at MVP | Documented in README; data can be cleared by truncating tables | (Assumption) Formal retention policy deferred to production |

---

## 7. Data & Integrations

### Core Data Entities (Postgres / RDS)

| Entity | Key Fields | Notes |
|--------|-----------|-------|
| `faq_entries` | `id`, `category`, `question`, `answer`, `is_active`, `created_at`, `updated_at` | No sensitive patient data; staff-maintained |
| `chat_sessions` | `id` (UUID), `created_at`, `session_label` (optional display name) | No PII; session identity only |
| `chat_messages` | `id`, `session_id` (FK), `role` (user / assistant), `content`, `created_at` | Content must never include sensitive data (FR-4); no SSN, DOB, symptom fields |
| `users` (staff) | `id`, `username`, `hashed_password`, `role`, `created_at` | MVP auth only; no PII beyond username |

### External Integrations

| System | Purpose | Interface | Notes |
|--------|---------|-----------|-------|
| **AWS Bedrock** | Generate natural-language responses grounded in retrieved FAQ content | AWS SDK (boto3); invoked from backend API only | Model selection TBD (see Open Questions); API key via environment variable |
| **AWS RDS Postgres** | Persistent storage for FAQs, sessions, messages, users | SQLAlchemy / psycopg2 or equivalent ORM | No pgvector extension required; plain relational queries only |
| **Streamlit** | Demo UI — chat interface, FAQ browser, staff admin | Python Streamlit library; calls backend REST API | No direct DB access from Streamlit layer |

### Explicitly Excluded Integrations
- No EHR / FHIR APIs
- No calendar or booking systems
- No SMS / email notification services
- No vector databases or search engines (pgvector, OpenSearch, Pinecone)
- No PDF or document ingestion pipelines

---

## 8. Analytics & Observability

**Request Logging**
Every API request logs: timestamp, HTTP method, endpoint path, session ID (UUID — non-PII), HTTP response status, and wall-clock latency. Logs are written to stdout in structured JSON to facilitate future ingestion into a log aggregator.

**Bedrock Call Tracing**
Each Bedrock invocation logs: session ID, number of FAQ entries retrieved and passed as context, model ID, and response latency. Prompt content is logged at DEBUG level only and must be reviewed before enabling in any environment where real patient data could appear.

**Fallback Rate Tracking**
The API records whether each response was a grounded FAQ answer or a fallback (no-match). This ratio can be queried from the `chat_messages` table to identify FAQ coverage gaps.

**Error Monitoring**
Unhandled exceptions surface full stack traces in logs. A future enhancement (post-MVP) would route these to an alerting channel, but no alerting infrastructure is required for the demo POC.

**Demo Metrics**
The seed script and a simple admin stats endpoint (TBD) should make it easy to show stakeholders: total FAQ entries, total chat sessions, total messages, and fallback rate during the demo.

---

## 9. Risks & Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| Bedrock generates a response that contradicts or extends beyond the FAQ content, presenting invented clinical information | High — undermines trust; potential patient harm if misinterpreted | Prompt engineering instructs Bedrock to answer only from supplied FAQ context; FR-3 enforces fallback for low-confidence matches; disclaimer on every response |
| User enters sensitive PII (SSN, symptoms) and it is stored in the database | High — privacy violation even at demo scope | FR-4 detects and redirects; schema has no sensitive-data columns; input sanitization in API layer |
| Stakeholders mistake the demo for a production-ready or HIPAA-compliant system | Medium — sets incorrect expectations; may fast-track unsafe deployment | README, UI header, and demo script explicitly label the app as a POC; disclaimer present throughout |
| AWS Bedrock rate limits or latency spikes disrupt a live demo | Medium — poor stakeholder impression | Pre-warm session before demo; consider caching Bedrock responses for identical FAQ matches (post-MVP) |
| FAQ content is outdated or incorrect, leading to wrong answers given to patients | Medium — misinformation risk | Staff admin UI (FR-7) enables rapid updates; seed content reviewed before each demo; disclaimer directs users to call for definitive answers |
| Postgres RDS connectivity fails in local dev or during demo | Low-Medium — blocks demo | README documents connection troubleshooting; pytest fixtures use test DB; fallback to local Postgres documented |
| Simple MVP auth credentials are weak or leaked | Low (demo scope) | Credentials stored in environment variables only; not committed to source; production SSO planned for post-MVP |

---

## 10. Open Questions

| # | Question | Suggested owner |
|---|----------|-----------------|
| 1 | Which AWS Bedrock model should be used (e.g., Anthropic Claude, Amazon Titan)? What are the cost and latency implications at demo scale? | Engineering / AWS account owner |
| 2 | What is the exact wording of the required medical disclaimer? Does the clinic's legal or compliance team need to approve it? | Clinic stakeholder / Legal |
| 3 | How should FAQ relevance matching work without vector search? Rule-based keyword matching, SQL `LIKE` / `ts_vector` full-text search, or passing all active FAQs as context to Bedrock? | Engineering |
| 4 | What categories and initial FAQ entries should be seeded? Who provides the canonical answers for hours, insurance, booking, parking, and wellness? | Clinic stakeholder / Front-desk staff |
| 5 | What constitutes "sufficient" relevance for Bedrock to attempt a grounded answer vs. triggering the fallback? What confidence threshold or heuristic applies? | Engineering / PM |
| 6 | What is the maximum number of FAQ entries expected in v1? This affects whether passing all entries as Bedrock context is feasible within token limits. | Engineering |
| 7 | What is the staff admin authentication mechanism — environment-variable credentials, seeded users table, or a lightweight config file? | Engineering |
| 8 | Is there a target demo date or stakeholder review deadline? This affects how much polish (error states, loading spinners, mobile responsiveness) is warranted. | PM / Clinic stakeholder |
| 9 | Are there any state or clinic-specific requirements around the disclaimer language or the definition of "sensitive data" beyond SSN and full DOB? | Clinic stakeholder / Legal |
| 10 | Should the chat history shown in the UI be scoped to the current browser session only, or should named sessions be resumable across browser refreshes? | PM / Engineering |

---

## Appendix: Assumptions

- **Framework**: The backend API is implemented in Python (e.g., FastAPI or Flask); the choice is left to engineering but must expose a REST interface consumed by Streamlit.
- **Bedrock model**: A capable instruction-following model available in AWS Bedrock (e.g., an Anthropic Claude variant) will be used; final model selection is an open question.
- **FAQ relevance strategy**: In the absence of vector search, the implementation will use Postgres full-text search (`tsvector`) or a keyword-match approach to retrieve candidate FAQ entries, then pass them as context to Bedrock. This is an engineering decision to be confirmed.
- **Token budget**: It is assumed that passing a reasonable number of FAQ entries (up to ~20–30 entries) as context fits within the selected Bedrock model's context window for MVP scale.
- **Auth mechanism**: MVP authentication uses a seeded `users` table with bcrypt-hashed passwords; no external IdP is required.
- **Disclaimer wording**: A default disclaimer string will be hardcoded in the backend and appended to every response; final wording requires stakeholder sign-off.
- **Sensitive data detection**: Pattern-matching heuristics (regex for SSN format, keyword detection for symptoms) are used at MVP; ML-based PII detection is out of scope.
- **RDS access**: Developers have VPN or local tunnel access to the RDS instance; or a local Postgres instance is used for development with the same schema.
- **No real patient data**: All demo interactions use synthetic or test data; no real patient identities are involved in the POC.
- **Single clinic**: The MVP serves one clinic's FAQ content; multi-tenancy is explicitly out of scope.
- **Response latency target of 8 seconds p95** is an assumption based on typical Bedrock model latency; this should be validated during development.
- **Streamlit page structure**: The UI contains at minimum three pages — Chat, FAQ Browser, and Staff Admin (login-gated).
- **No message-level edit or delete**: Staff admin only covers FAQ CRUD; chat message history is read-only and append-only.
- **Postgres schema migrations** are managed via Alembic or a similar migration tool included in the repository.
- **CI/CD**: A basic GitHub Actions (or equivalent) pipeline runs `pytest` on pull requests; deployment pipeline beyond local dev is out of scope for MVP.

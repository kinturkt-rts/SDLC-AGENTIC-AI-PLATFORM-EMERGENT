# AI PR Diff Summarizer

## 1. Overview

Engineering managers need a quick way to assess the complexity and risk of incoming pull requests before assigning reviewers. Currently, they must manually read through diffs of varying sizes and complexity to understand scope and potential impact. This AI PR Diff Summarizer provides an automated analysis service that processes pull request diffs, generates human-readable summaries, and calculates risk scores based on both AI analysis and code-based heuristics. The system stores analysis history and provides a dashboard for tracking PR review patterns over time.

## 2. Goals & Success Metrics

| Goal | Metric | Target | Notes |
|------|--------|--------|-------|
| Reduce PR triage time | Average time to assign reviewer | < 2 minutes per PR | Compared to manual review |
| Accurate risk assessment | Risk score alignment with actual PR complexity | 80% accuracy | Manual validation sample |
| System adoption | Daily active reviewers | 10+ unique API key users | Within first month |
| Response performance | API response time for diff analysis | < 5 seconds | 95th percentile |

## 3. Non-Goals / Out of Scope

- Live GitLab/GitHub integration (mock the fetch in MVP)
- AI-suggested reviewer recommendations  
- Inline-comment generation
- Webhook trigger automation
- Real-time notifications
- Multi-repository support
- Advanced user management beyond API keys

## 4. Users & Use Cases

| Persona | Need | Primary use case |
|---------|------|------------------|
| Engineering Manager | Quick PR risk assessment | Paste diff, get summary + risk score to inform reviewer assignment |
| Tech Lead | Historical PR complexity tracking | Review dashboard showing team's PR risk patterns over time |
| Senior Developer | Self-assessment before submission | Check own PR complexity before requesting review |

## 5. Functional Requirements

| ID | Description | Priority | Acceptance criteria (Given / When / Then) |
|----|-------------|----------|---------------------------------------------|
| FR-1 | Process PR diffs via API | P0 | Given valid diff text, When POST /reviews called with API key, Then return 201 with summary, risk_score, and stored record |
| FR-2 | Generate AI-powered summaries | P0 | Given diff input, When processed by Bedrock Claude, Then return 2-4 sentence plain English summary with no code blocks |
| FR-3 | Calculate risk scores with heuristics | P0 | Given LLM base score, When heuristics applied (+15 for migrations/, +10 for secrets, -10 for <30 lines), Then return clamped final score 0-100 |
| FR-4 | Categorize risk bands | P0 | Given final risk score, When score is 0-30/31-70/71-100, Then assign low/medium/high risk_band respectively |
| FR-5 | Store and retrieve analysis history | P1 | Given completed analysis, When stored in Postgres, Then GET /reviews returns paginated history with optional risk_band filter |
| FR-6 | Provide analytics dashboard | P1 | Given stored reviews, When GET /stats called, Then return last 30 days counts by risk_band and average risk score |
| FR-7 | Streamlit UI for demo interaction | P1 | Given Streamlit app, When user submits diff in Tab 1, Then display results and update history in Tab 2 |
| FR-8 | API authentication via headers | P0 | Given X-API-Key header, When valid key provided, Then allow access to protected endpoints, else return 401 |

## 6. Non-Functional Requirements

| ID | Category | Target | Measurement / verification | Notes |
|----|----------|--------|---------------------------|-------|
| NFR-1 | Performance | < 5s API response time | 95th percentile monitoring | (Assumption) |
| NFR-2 | Security | API key authentication | Header validation on all protected endpoints | X-API-Key header requirement |
| NFR-3 | Availability | 99% uptime | Health check monitoring | (Assumption) |
| NFR-4 | Scalability | Handle 100 concurrent requests | Load testing verification | (Assumption) |
| NFR-5 | Data Retention | Store all reviews indefinitely | Postgres storage capacity | No explicit retention policy |
| NFR-6 | Observability | Request/response logging | Structured logs for API calls | (Assumption) |
| NFR-7 | Testability | Mock Bedrock in tests | pytest with mocked bedrock_client | No live AWS calls in test suite |

## 7. Data & Integrations

**Database Schema (Postgres):**
- reviews table: id (uuid), submitted_at (timestamp), title (text), diff_text (text), file_count (int), lines_added (int), lines_removed (int), summary (text), risk_score (int 0-100), risk_band (enum: low/medium/high), model_id (text), created_by (text)

**External Integrations:**
- AWS Bedrock Claude Sonnet via app/services/bedrock_client.py
- Structured JSON response: { summary, risk_factors[], risk_score }

## 8. Analytics & Observability

**Key Metrics:**
- API request volume and response times
- Risk score distribution over time  
- Error rates by endpoint
- Bedrock API success/failure rates

**Logging Requirements:**
- All API requests with timestamps and user identification
- Bedrock interaction success/failure
- Database query performance

## 9. Risks & Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| Bedrock API failures | Service unavailable | Implement retry logic and circuit breaker |
| Large diff timeouts | Poor user experience | Set reasonable input size limits and timeout handling |
| Inaccurate risk scoring | Wrong reviewer assignments | Regular calibration against manual assessments |
| API key management | Security exposure | Implement key rotation and monitoring |

## 10. Open Questions

| # | Question | Suggested owner |
|---|----------|-----------------|
| 1 | What are the specific API key values and rotation policy? | Security team |
| 2 | Should there be input size limits for diff_text? | Engineering team |
| 3 | What Postgres instance specifications are needed? | Infrastructure team |
| 4 | Are there compliance requirements for storing code diffs? | Legal/Security team |
| 5 | Should risk factors be customizable per organization? | Product team |

## Appendix: Assumptions

- API keys are pre-generated and distributed manually
- Postgres database is provisioned and accessible
- AWS Bedrock access is configured with appropriate IAM permissions
- Streamlit deployment follows Pattern C architecture
- No user registration or self-service key management needed
- Default performance and availability targets are acceptable
- English-only diff analysis required
- Standard HTTP status codes and JSON responses
- Basic pagination sufficient for history viewing

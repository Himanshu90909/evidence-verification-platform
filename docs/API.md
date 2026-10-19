# API Reference

## ML service (FastAPI, default :8000)

All endpoints except `/health` and `/metrics` require service authentication:
`X-API-Key: <ML_API_KEY>` or `Authorization: Bearer <ML_API_KEY>`.

### POST /verify
Request: `{ "claim": "string (3..2000)", "top_k": 1..20 (optional), "return_evidence": bool }`

Response: `claim`, `verdict` (SUPPORTED | REFUTED | NOT_ENOUGH_INFORMATION), `confidence` [0,1], `uncertainty` [0,1] (normalized entropy), `retrieval {method, top_k, latency_ms, n_documents_searched}`, `evidence[] {document_id, text, score, source, source_url, page, line_id, rank}`, `nli[] {document_id, label, probabilities, is_top_evidence}`, `model {model, version, embedding_model, retriever, nli_model, nli_backend, temperature, config_hash}`, `latency_ms`, `explanation {steps[], aggregated_probabilities, top_evidence_id, uncertainty_measure}`.

Errors: 401 invalid key · 422 validation · 503 pipeline not ready.

### POST /retrieve
`{ "query", "top_k" 1..50, "method": "bm25"|"dense"|"hybrid" }` → ranked evidence list.

### POST /predict
`{ "premise", "hypothesis" }` → `{ label: ENTAILMENT|CONTRADICTION|NEUTRAL, probabilities }`.

### POST /explain
`{ "claim", "top_k", "decision_threshold" }` → verdict + `decision_path[]` + per-evidence NLI.

### GET /health → `{status, nli_backend, retrieval_backend, corpus_loaded, corpus_documents, uptime_seconds, detail}`

### GET /model-info → service version, active pipeline model card, corpus size, live metrics summary.

### GET /metrics → Prometheus text format (`evp_requests_total`, `evp_errors_total`, `evp_verdicts_total{verdict=..}`, `evp_stage_latency_ms{stage=..}`).

## Web API (Next.js route handlers)

Session auth: JWT in `evp_session` httpOnly cookie (Sign in via `/api/auth/login`).

| Route | Method | Auth | Notes |
|---|---|---|---|
| `/api/auth/register` | POST | — | email + password (≥8 chars), rate limited 5/min/IP |
| `/api/auth/login` | POST | — | rate limited 10/min/IP |
| `/api/auth/logout` | POST | cookie | clears session |
| `/api/auth/me` | GET | cookie | current user |
| `/api/verify` | POST | cookie | claim 3..2000 chars; 20 req/min/user; persists everything |
| `/api/claims` | GET | cookie | last 50 claims + latest result |
| `/api/claims/[id]` | GET | cookie | full detail: NLI predictions, retrieval results, evidence |
| `/api/evidence/search` | POST | cookie | corpus search via ML /retrieve; 30 req/min |
| `/api/model-info` | GET | cookie | service card + recorded model versions |
| `/api/research/results` | GET | — | real experiment outputs (or `available: false`) |
| `/api/feedback` | GET/POST | cookie | rating 1..5, optional comment + result id |
| `/api/health` | GET | — | web + database + ML service status |

All writes are validated with zod and recorded in `audit_logs` (action, IP, user agent, status, latency).

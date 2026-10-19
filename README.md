# Evidence Verification Platform

**Research-grade + reproducible + production-oriented + database-backed + ML-powered** claim verification system.

The system verifies natural-language claims against a **controlled FEVER/Wikipedia research corpus** using hybrid retrieval (BM25 + dense embeddings) and Natural Language Inference (NLI), with uncertainty estimation, full model versioning, and a PostgreSQL-backed production web application.

```
User
 ↓
Next.js / Vercel  ──  validation, auth, rate limiting, audit
 ↓
Secure API (service key)
 ↓
Python FastAPI ML Service  ──  hybrid retrieval → evidence ranking → NLI → uncertainty → verdict
 ↓
PostgreSQL  ── claims, results, evidence, predictions, model versions, experiments, feedback, audit logs
 ↓
Vercel UI  ── dashboard, verification, evidence analysis, history, model info, research results
```

**Research mode** (dataset experiments, evaluation, ablations, calibration) and **production mode** (real-time verification, user history, feedback, monitoring) share the same pipeline but never mix results without explicit identification (`experiments.mode = "research"`; production predictions are always tied to a `model_versions` row).

---

## 1. Project objective

Build a system that, given a factual claim, retrieves real evidence passages, scores them with an NLI model, aggregates the judgments, estimates uncertainty, and returns a structured, fully traceable verdict. The platform treats verification as a scientific pipeline: every prediction records the exact model versions, configuration hash, retrieval scores, and NLI probabilities that produced it.

## 2. Research problem

Claim verification over a knowledge corpus is a three-class classification problem (`SUPPORTS` / `REFUTES` / `NOT ENOUGH INFO`) whose quality depends jointly on (a) retrieving the right evidence and (b) reasoning over it. The research questions addressed by the experiment pipeline:

- RQ1: How much does hybrid BM25+dense retrieval (RRF fusion) improve gold-evidence recall over either method alone?
- RQ2: How well does a pretrained cross-encoder NLI model transfer to claim-evidence pairs (zero-shot, no fine-tuning)?
- RQ3: How calibrated are the confidence scores, and does temperature scaling improve calibration (ECE)?
- RQ4: How sensitive is the end-to-end verdict to retrieval method and top-k (ablations)?

## 3. Architecture

- **Frontend + API**: Next.js 14 (App Router, TypeScript) with API routes (Node runtime), deployed on Vercel.
- **Database**: PostgreSQL via Prisma ORM; normalized schema with FKs, indexes, constraints; migrations in `web/prisma/migrations`.
- **ML service**: standalone Python FastAPI service (PyTorch, Transformers, Sentence-Transformers, FAISS, BM25, scikit-learn); Dockerized; independently deployable.
- **Evidence**: controlled FEVER-derived corpus indexed locally (BM25 pickle + FAISS flat index + document metadata mapping). No uncontrolled web scraping is part of the methodology.

The web layer calls the ML service over HTTPS with a service API key; the ML service never exposes models to the browser.

## 4. Dataset

- **Corpus**: gold evidence sentences from the FEVER shared task (`copenlu/fever_gold_evidence` on HuggingFace), i.e. Wikipedia-derived evidence. Union of train+validation gold evidence is the knowledge corpus (documents keyed `Page::L<line>` with source URL metadata).
- **Evaluation**: FEVER **validation** claims (held out from the corpus build only in the claim dimension; the knowledge corpus is corpus-side, matching the original FEVER setup where evidence is Wikipedia, independent of claim splits).
- Labels map to the pipeline: `SUPPORTS→SUPPORTED`, `REFUTES→REFUTED`, `NOT ENOUGH INFO→NOT_ENOUGH_INFORMATION`.

## 5. ML methodology

Pipeline (`ml-service/app/pipeline.py`): preprocess claim → BM25 retrieval → dense retrieval → hybrid fusion → NLI-based evidence reranking → retrieval-weighted multi-evidence aggregation → entropy-based uncertainty → thresholded verdict.

- **Reranking**: retrieved passages are scored by the NLI model (premise=evidence, hypothesis=claim) and reranked by informativeness (entailment+contradiction mass).
- **Aggregation**: per-evidence NLI probabilities are combined with normalized hybrid-retrieval weights.
- **Uncertainty**: normalized Shannon entropy of the aggregated 3-class distribution (always displayed; never hidden).
- **NEI decision**: if neither support nor refute mass reaches `MIN_EVIDENCE_PROB` (default 0.35), the verdict is `NOT_ENOUGH_INFORMATION`.
- A deterministic lexical fallback backend exists for offline operation; it identifies itself in every response (`nli_backend: "lexical-fallback"`) and never fabricates evidence.

## 6. Retrieval methodology

- **BM25**: `rank_bm25.BM25Okapi` with stopword-filtered alphanumeric tokenization.
- **Dense**: sentence embeddings (`sentence-transformers/all-MiniLM-L6-v2` default), cosine similarity via `faiss.IndexFlatIP` over L2-normalized vectors.
- **Hybrid**: Reciprocal Rank Fusion (k=60) over both ranked lists (configurable weighted-score fusion also implemented). Over-fetch ×3, fuse, cut to top-k.
- Evaluated with Recall@5/@10, MRR@10, nDCG@10 against FEVER gold evidence.

## 7. NLI methodology

- **Model**: cross-encoder sequence classification, default `cross-encoder/nli-deberta-v3-small` (zero-shot; label mapping resolved from the model's own `id2label`).
- **Temperature scaling** fitted on the validation sample (grid search minimizing NLL) is reported in `research/results/calibration.json` and deployed via the `TEMPERATURE` env var.
- **Calibration**: ECE over 10 bins before/after scaling, reliability curve data included.

## 8. Database schema

`web/prisma/schema.prisma` (PostgreSQL, normalized):

| Table | Purpose |
|---|---|
| `User` | accounts (bcrypt password hashes, roles) |
| `Claim` | user-submitted claims (unique per user+text) |
| `VerificationResult` | verdict, confidence, uncertainty, latencies, request id |
| `Evidence` | corpus passages (unique `document_id`, page/line metadata) |
| `EvidenceSource` | source registry (FEVER/Wikipedia), license |
| `RetrievalResult` | per-result retrieval scores/ranks |
| `NliPrediction` | per-evidence NLI label + 3-class probabilities |
| `ModelVersion` | every model/config that ever produced a prediction |
| `Experiment` | research results metadata (mode, dataset, metrics JSON) |
| `Feedback` | user ratings/comments on results |
| `AuditLog` | request-level audit trail (action, IP, status, latency) |

All keys are cuids with FKs and cascade rules; hot paths are indexed (`verdict`, `claim_id`, `model_version_id`, timestamps, `document_id` unique, etc.). Timestamps on every table. Migrations: `web/prisma/migrations/*` (apply with `npx prisma migrate deploy`). Credentials only ever come from `DATABASE_URL`.

## 9. API documentation

### ML service (requires `X-API-Key` or `Authorization: Bearer`)

| Endpoint | Description |
|---|---|
| `POST /verify` | full pipeline: `{claim, top_k?}` → verdict, confidence, uncertainty, evidence, NLI, model metadata |
| `POST /retrieve` | `{query, top_k, method∈bm25,dense,hybrid}` → ranked evidence |
| `POST /predict` | single `{premise, hypothesis}` NLI prediction |
| `POST /explain` | `{claim}` → verdict + human-readable decision path + per-evidence NLI |
| `GET /health` | status, backends, corpus size |
| `GET /model-info` | model card + live service metrics |
| `GET /metrics` | Prometheus text format |

Example `/verify` response:

```json
{
  "claim": "The Eiffel Tower is named after Gustave Eiffel.",
  "verdict": "SUPPORTED",
  "confidence": 0.91,
  "uncertainty": 0.08,
  "retrieval": { "method": "hybrid", "top_k": 5 },
  "evidence": [
    { "document_id": "Eiffel Tower::L0", "text": "The Eiffel Tower is named after the engineer Gustave Eiffel ...", "score": 0.92, "nli_label": "ENTAILMENT" }
  ],
  "model": { "model": "hybrid-bm25-dense-nli", "version": "1.0.0", "embedding_model": "...", "nli_model": "...", "config_hash": "..." }
}
```

All evidence is retrieved from the indexed corpus with its source metadata; **no evidence is ever fabricated**.

### Web API (session cookie auth)

`POST /api/auth/register|login|logout`, `GET /api/auth/me`, `POST /api/verify` (validates, rate-limits, calls ML, persists to PostgreSQL), `GET /api/claims`, `GET /api/claims/[id]`, `POST /api/evidence/search`, `GET /api/model-info`, `GET /api/research/results`, `GET|POST /api/feedback`, `GET /api/health`.

## 10. Local setup

```bash
git clone https://github.com/Himanshu90909/evidence-verification-platform
cd evidence-verification-platform
npm install -g pnpm  # optional; plain npm is used below

# one-command setup (env files, deps, venv, corpus + indexes):
./scripts/setup.sh

# or manually:
docker compose up -d db          # PostgreSQL 16
cp web/.env.example web/.env     # set DATABASE_URL + AUTH_SECRET
cp ml-service/.env.example ml-service/.env  # set ML_API_KEY
cd web && npm install && npx prisma generate
```

## 11. ML setup

```bash
cd ml-service
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
# build the FEVER evidence corpus + indexes (downloads dataset + models once):
python scripts/build_corpus.py --out data/corpus/evidence_corpus.jsonl
python scripts/build_indexes.py --corpus data/corpus/evidence_corpus.jsonl --out data/indexes
uvicorn main:app --port 8000       # service auto-loads corpus/indexes
curl http://localhost:8000/health # should report status "ok"
```

## 12. Database migration

```bash
cd web
export DATABASE_URL="postgresql://evp:evp_dev_password@localhost:5432/evidence_verification"
npx prisma migrate deploy   # apply committed migrations
npm run db:seed              # evidence source + experiments from real results (no fabricated metrics)
```

## 13. Vercel deployment

1. Push the repo to GitHub; import `web/` as the Vercel project (or `vercel --cwd web`).
2. Environment variables (Production + Preview):
   - `DATABASE_URL` (Neon/Supabase/RDS Postgres connection string)
   - `ML_API_URL` (HTTPS URL of the deployed ML service)
   - `MODEL_SERVICE_KEY` (the ML service's `ML_API_KEY`)
   - `AUTH_SECRET` (`openssl rand -base64 32`)
3. Run `npx prisma migrate deploy` once against the production database.
4. Build: `npm run build` in `web/` (default Next.js settings; no `vercel.json` needed for this configuration). API routes run on the Node runtime so Prisma and bcrypt work.

The web layer stays lightweight on Vercel on purpose: all ML inference runs on the separate Python service.

## 14. ML service deployment

```bash
docker build -t evp-ml ./ml-service
docker run -d -p 8000:8000 -v evp_data:/data \
  -e ML_API_KEY=$(openssl rand -hex 24) \
  -e CORS_ORIGINS=https://your-app.vercel.app \
  evp-ml
```

- On first boot the entrypoint builds the corpus + indexes into `/data` (volume; needs egress to huggingface.co).
- Health check: `GET /health`; metrics: `GET /metrics` (Prometheus).
- Deploy anywhere with Docker: Railway, Render, Fly.io, ECS, or a GPU-less VPS. Point `ML_API_URL` at its HTTPS endpoint and set the same key in `MODEL_SERVICE_KEY` on Vercel.
- Paths are fully configurable via env (`CORPUS_PATH`, `INDEX_DIR`) — no hard-coded OS paths.

### Hugging Face Spaces (recommended free option)

The ML service ships a one-command deploy to a **private HF Space** (Docker SDK,
free CPU tier, 16 GB RAM — plenty for this workload). The Space bundles the
prebuilt corpus, BM25 index, and FAISS index, so first boot only downloads the
transformer models (~2–4 min), never rebuilds indexes.

```bash
cd ml-service
HF_TOKEN=hf_xxx MODEL_SERVICE_KEY=<shared-secret>   python3 scripts/deploy_hf_space.py
```

Then set in Vercel (Production **and** Preview):
`ML_API_URL=https://<user>-evidence-verification-ml.hf.space`
and `MODEL_SERVICE_KEY` to the same value passed above (or use the one the
script generates). Redeploy the web app and `POST /api/verify` is live.

> Free Spaces sleep after ~48 h of inactivity; the first request after sleep
> takes a few minutes while models reload. Keep-alive ping (optional):
> `curl -s https://<user>-evidence-verification-ml.hf.space/health` on a cron.

## 15. Environment variables

| Variable | Where | Purpose |
|---|---|---|
| `DATABASE_URL` | web | PostgreSQL connection (never committed) |
| `ML_API_URL` | web | ML service base URL |
| `MODEL_SERVICE_KEY` | web | service key for the ML API |
| `AUTH_SECRET` | web | JWT session signing secret |
| `ML_API_KEY` | ml-service | the key the web layer must present |
| `EMBEDDING_MODEL` | ml-service | dense retrieval encoder |
| `NLI_MODEL` | ml-service | NLI cross-encoder |
| `CORPUS_PATH` / `INDEX_DIR` / `DATA_DIR` | ml-service | artifact locations |
| `TOP_K`, `TEMPERATURE`, `MIN_EVIDENCE_PROB`, `USE_RRF`, `CORS_ORIGINS` | ml-service | pipeline configuration |

`.env.example` files exist for both services; secrets are never in the repo or frontend code.

## 16. Running experiments

```bash
cd ml-service
python scripts/run_experiments.py            # writes ../research/results/*.json
node ../scripts/sync-research.mjs            # copies real results into web/public/research/
cd ../web && npm run db:seed                 # records experiments in PostgreSQL
```

Outputs: `meta.json` (dataset, versions, seed, temperature), `retrieval_eval.json` (Recall@5/@10, MRR@10, nDCG@10, latency per method), `nli_eval.json` (accuracy, macro-F1, per-class P/R/F1, confusion matrix, latency), `calibration.json` (ECE before/after temperature scaling, reliability bins), `ablations.json` (method × top-k).

## 17. Reproducing results

Fixed seed (42) for stratified sampling; the corpus builder is deterministic (sorted document ids); models are pinned by name from the HuggingFace hub; the fitted temperature is stored in `calibration.json` and deployed via `TEMPERATURE`. Every prediction records the pipeline version, model names, config hash, and temperature, so any stored result can be traced to the exact configuration that produced it.

## 18. Limitations

- Evidence coverage is bounded by the FEVER-derived corpus; claims outside its Wikipedia slice will honestly return `NOT_ENOUGH_INFORMATION`.
- The NLI model is zero-shot (no FEVER fine-tuning in this release); the lexical fallback is a degraded mode, clearly flagged in every response and stored prediction.
- In-memory rate limiting on Vercel is per-instance (best effort); use Upstash Redis for strict global limits.
- Calibration is fitted on the FEVER validation sample; domain shift may degrade calibration on other corpora.
- No multi-tenant isolation beyond per-user claim scoping.

## 19. Future research

- Fine-tuning the NLI encoder on FEVER train claims (the pipeline already supports any HF model via `NLI_MODEL`).
- Learned reranking (cross-encoder MS-MARCO rerankers) before NLI.
- Long-doc evidence aggregation (sentence-level page expansion, graph evidence chains).
- Human feedback loops: use the `feedback` table to drive error analysis and active-learning experiments.
- Multi-dataset evaluation (SciFact, CREAK) with the same harness.

---

## Testing

```bash
# ML service (offline: hashing dense backend + lexical NLI fallback for CI)
cd ml-service && pytest -q          # 29 tests

# Web unit tests (validation, auth, rate limiting)
cd web && npm test                  # vitest

# End-to-end (needs running stack): Claim -> API -> ML -> PostgreSQL
cd web && npm run test:e2e
```

## Repository layout

```
web/                 Next.js 14 frontend + API (TypeScript, Prisma, Tailwind)
ml-service/          FastAPI ML service (retrieval, NLI, pipeline, Docker)
research/results/    actual experiment outputs (loaded by the Research dashboard)
scripts/             setup + research-sync helpers
docker-compose.yml   local PostgreSQL + ML service stack
```

## Deployment Status (live)

| Component | Status | URL |
|---|---|---|
| Web app (Next.js) | **Deployed** (Vercel, project `evidence-verification-platform`) | https://evidence-verification-platform-live.vercel.app |
| PostgreSQL | **Live** (Neon, dedicated `evidence_verification` schema, migrations + seed run in the Vercel build) | — |
| ML service | **Ready to deploy** (Docker; see ML Deployment) — set `ML_API_URL` + `MODEL_SERVICE_KEY` in Vercel when hosted | — |

Verified live (2026-10-19): all pages 200, auth (register/login/session) working,
PostgreSQL reads/writes confirmed, research dashboard serving real FEVER
experiment outputs via `/api/research/results`. The Eiffel Tower is a fine
first claim once the ML service is up.

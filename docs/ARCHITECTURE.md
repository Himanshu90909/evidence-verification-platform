# Architecture

```
┌────────────┐     HTTPS      ┌─────────────────┐     service key      ┌──────────────────┐
│  Browser   │ ─────────────► │ Next.js on      │ ───────────────────► │ FastAPI ML       │
│  (Vercel UI)│ ◄──────────── │ Vercel          │ ◄─────────────────── │ Service (Docker) │
└────────────┘                │  - API routes   │                      │  - BM25 index    │
                              │  - auth (JWT)   │                      │  - FAISS index   │
                              │  - zod validate │                      │  - NLI (PyTorch) │
                              │  - rate limit   │                      │  - uncertainty   │
                              │  - audit log    │                      └──────────────────┘
                              │  - Prisma ORM   │
                              └───────┬─────────┘        ┌──────────────┐
                                      │                  │ FEVER corpus │
                                      ▼                  │ + indexes    │
                              ┌─────────────────┐        │ (volume /    │
                              │  PostgreSQL     │         │  artifact)   │
                              │  users, claims, │        └──────────────┘
                              │  results, nli,  │
                              │  evidence, exps,│
                              │  feedback, audit │
                              └─────────────────┘
```

## Design decisions

- **Separation of concerns**: Vercel hosts only the lightweight web layer. The Python service owns all ML (models are far too large/heavy for serverless functions). PostgreSQL owns all application state.
- **Model versioning as a first-class citizen**: `model_versions.config_hash` makes every stored prediction reproducible; changing temperature/top-k/model changes the hash, creating a new version row.
- **Research/production separation**: the same `VerificationPipeline` class powers the FastAPI service and the experiment runner. Research outputs go to `research/results/*.json` + the `experiments` table (mode="research"); production predictions go through the API with user attribution. They are never conflated.
- **Never fabricate evidence**: every passage returned by the API is read from the indexed corpus by `document_id`, carries its source metadata, and is stored verbatim in `evidence`. A degraded backend (lexical NLI fallback) is always flagged in the response and in the DB.
- **Uncertainty is not hidden**: verdict, confidence, and entropy-based uncertainty are shown together everywhere (verify page, history, model metrics).

#!/usr/bin/env bash
# One-command local setup: env files, database migration, dependency check.
set -e
cd "$(dirname "$0")/.."

echo "== Evidence Verification Platform - local setup =="

# 1) Environment files
if [ ! -f web/.env ]; then
  cp web/.env.example web/.env
  echo "[setup] created web/.env (fill in DATABASE_URL / AUTH_SECRET)"
fi
if [ ! -f ml-service/.env ]; then
  cp ml-service/.env.example ml-service/.env
  echo "[setup] created ml-service/.env (set ML_API_KEY + AUTH_SECRET to match)"
fi

# 2) Generate a strong AUTH_SECRET if openssl is available and var is placeholder
gen_secret() {
  if command -v openssl >/dev/null 2>&1; then openssl rand -base64 32; else echo "change-me-please-use-a-random-string-at-least-32-chars"; fi
}
WEB_SECRET=$(gen_secret)
ML_KEY=$( [ -n "$(command -v python3)" ] && python3 -c "import secrets; print('evp_' + secrets.token_urlsafe(32))" )

# 3) Web dependencies + database
echo "[setup] installing web dependencies ..."
(cd web && npm install)
echo "[setup] generating Prisma client ..."
(cd web && npx prisma generate)
if grep -q "localhost:5432" web/.env 2>/dev/null; then
  echo "[setup] NOTE: start PostgreSQL first (docker compose up -d db), then run:"
  echo "         cd web && npx prisma migrate deploy && npm run db:seed"
fi

# 4) ML service Python environment
if [ ! -d ml-service/.venv ]; then
  echo "[setup] creating Python virtualenv ..."
  python3 -m venv ml-service/.venv
fi
echo "[setup] installing ML dependencies (this can take a few minutes) ..."
ml-service/.venv/bin/pip install -q -r ml-service/requirements.txt

# 5) Corpus + indexes (downloads FEVER evidence + models on first run)
echo "[setup] building evidence corpus + indexes ..."
(cd ml-service && [ -f data/corpus/evidence_corpus.jsonl ] || .venv/bin/python scripts/build_corpus.py --out data/corpus/evidence_corpus.jsonl)
(cd ml-service && [ -f data/indexes/dense.faiss ] || .venv/bin/python scripts/build_indexes.py --corpus data/corpus/evidence_corpus.jsonl --out data/indexes)

echo ""
echo "== Setup complete =="
echo "Start the ML service:   cd ml-service && .venv/bin/python -m uvicorn main:app --port 8000"
echo "Start PostgreSQL:        docker compose up -d db"
echo "Migrate the database:    cd web && npx prisma migrate deploy && npm run db:seed"
echo "Start the web app:       cd web && npm run dev"
echo "Open http://localhost:3000"

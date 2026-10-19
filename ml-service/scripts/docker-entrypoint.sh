#!/usr/bin/env bash
# Build corpus + indexes on first boot when the data volume is empty.
set -e
CORPUS_PATH="${CORPUS_PATH:-/data/corpus/evidence_corpus.jsonl}"
INDEX_DIR="${INDEX_DIR:-/data/indexes}"
if [ "${PREBUILD_INDEX:-1}" = "1" ] && [ ! -f "$CORPUS_PATH" ]; then
    echo "[entrypoint] No corpus found - building FEVER evidence corpus and indexes..."
    python scripts/build_corpus.py --out "$CORPUS_PATH" \
        ${CORPUS_MAX_DOCUMENTS:+--max-docs "$CORPUS_MAX_DOCUMENTS"} || {
            echo "[entrypoint] WARNING: corpus build failed. Service will start in degraded mode."; }
    if [ -f "$CORPUS_PATH" ]; then
        python scripts/build_indexes.py --corpus "$CORPUS_PATH" --out "$INDEX_DIR" || {
            echo "[entrypoint] WARNING: index build failed."; }
    fi
fi
exec "$@"

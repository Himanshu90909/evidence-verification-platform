"""Model / pipeline versioning - required for reproducible research."""
from __future__ import annotations

import hashlib
import time
from typing import Any, Dict

import app.config as config

SERVICE_VERSION = "1.0.0"
PIPELINE_NAME = "hybrid-bm25-dense-nli"

# Label mapping between FEVER gold labels and NLI labels
FEVER_TO_NLI = {"SUPPORTS": "ENTAILMENT", "REFUTES": "CONTRADICTION", "NOT ENOUGH INFO": "NEUTRAL"}
NLI_TO_FEVER = {v: k for k, v in FEVER_TO_NLI.items()}


def model_info(settings: config.Settings, active: Dict[str, Any]) -> Dict[str, Any]:
    """Return a full model card describing every component that produced a prediction."""
    return {
        "model": PIPELINE_NAME,
        "version": SERVICE_VERSION,
        "embedding_model": settings.embedding_model,
        "retriever": "bm25+dense (hybrid, RRF fusion)" if settings.use_rrf else "bm25+dense (hybrid, weighted)",
        "nli_model": active.get("nli_model", settings.nli_model),
        "nli_backend": active.get("nli_backend", "transformers"),
        "reranker": active.get("reranker") or "nli-probability rerank",
        "temperature": settings.temperature,
        "top_k": settings.top_k,
        "corpus_documents": active.get("corpus_documents"),
        "config_hash": pipeline_config_hash(settings),
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S%z") or None,
    }


def pipeline_config_hash(settings: config.Settings) -> str:
    """Stable short hash of the effective pipeline configuration."""
    payload = "|".join(
        [
            PIPELINE_NAME,
            SERVICE_VERSION,
            settings.embedding_model,
            settings.nli_model,
            str(settings.use_rrf),
            str(settings.top_k),
            str(settings.temperature),
            str(settings.min_evidence_prob),
        ]
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:12]

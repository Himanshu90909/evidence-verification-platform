"""Central configuration, loaded from environment variables only."""
from __future__ import annotations

import os
from functools import lru_cache
from typing import List, Optional

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """All configuration comes from environment variables (12-factor)."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Service
    ml_api_key: str = "dev-service-key-change-me"
    host: str = "0.0.0.0"
    port: int = 8000
    log_level: str = "INFO"
    allow_unauthenticated: bool = False

    # Models
    embedding_model: str = "sentence-transformers/all-MiniLM-L6-v2"
    # 'sbert' for production sentence-transformers; 'hashing' is a deterministic
    # offline backend intended for tests/CI only (lower quality, no downloads).
    dense_backend: str = "sbert"
    nli_model: str = "cross-encoder/nli-deberta-v3-small"
    reranker_model: str = ""

    # Corpus / indexes
    data_dir: str = "./data"
    corpus_path: str = "./data/corpus/evidence_corpus.jsonl"
    index_dir: str = "./data/indexes"
    evidence_source_name: str = "FEVER / Wikipedia (research corpus)"

    # Pipeline
    top_k: int = 5
    dense_weight: float = 1.0
    bm25_weight: float = 1.0
    use_rrf: bool = True
    temperature: float = 1.0
    min_evidence_prob: float = 0.35

    # CORS: comma separated origins
    cors_origins: str = "http://localhost:3000"

    @property
    def cors_origin_list(self) -> List[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()


def artifact_path(p: Optional[str], default: str) -> str:
    """Resolve a path without assuming any OS-specific location."""
    return os.path.expanduser(p) if p else default

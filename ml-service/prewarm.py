"""Prewarm build step for the Modal image (see modal_app.py).

Kept in its own module so Modal's builder imports ONLY this file (no
module-level code from modal_app.py runs on the builder side). Downloads the
exact models the service uses, so containers never pay HF-hub download time
on cold start.
"""
from __future__ import annotations

EMBEDDING_MODEL = "sentence-transformers/all-MiniLM-L6-v2"
NLI_MODEL = "cross-encoder/nli-deberta-v3-small"


def prewarm() -> str:
    from sentence_transformers import SentenceTransformer
    from transformers import AutoModelForSequenceClassification, AutoTokenizer

    SentenceTransformer(EMBEDDING_MODEL)
    AutoTokenizer.from_pretrained(NLI_MODEL)
    AutoModelForSequenceClassification.from_pretrained(NLI_MODEL)
    return "ok"

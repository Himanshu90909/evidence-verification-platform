"""BM25 sparse retrieval over the research corpus."""
from __future__ import annotations

import logging
import math
import os
import pickle
import re
import time
from typing import Dict, List, Optional, Tuple

from rank_bm25 import BM25Okapi

logger = logging.getLogger("evp.bm25")

_TOKEN_RE = re.compile(r"[a-z0-9]+")

_stop = {
    "a", "an", "the", "is", "are", "was", "were", "be", "been", "being",
    "and", "or", "but", "of", "in", "on", "at", "to", "for", "with",
    "that", "this", "it", "its", "as", "by", "from", "he", "she", "they",
}


def tokenize(text: str) -> List[str]:
    return [t for t in _TOKEN_RE.findall(text.lower()) if t not in _stop]


class BM25Store:
    """Wraps rank_bm25 with persistence and normalization utilities."""

    def __init__(self) -> None:
        self.bm25: Optional[BM25Okapi] = None
        self.doc_ids: List[str] = []
        self._index_file: Optional[str] = None

    @property
    def ready(self) -> bool:
        return self.bm25 is not None

    def build(self, doc_ids: List[str], texts: List[str]) -> None:
        t0 = time.time()
        corpus_tokens = [tokenize(t) for t in texts]
        self.bm25 = BM25Okapi(corpus_tokens)
        self.doc_ids = list(doc_ids)
        logger.info("BM25 index built over %d docs in %.1fs", len(doc_ids), time.time() - t0)

    def save(self, index_dir: str) -> None:
        if self.bm25 is None:
            return
        os.makedirs(index_dir, exist_ok=True)
        path = os.path.join(index_dir, "bm25.pkl")
        with open(path, "wb") as fh:
            pickle.dump({"bm25": self.bm25, "doc_ids": self.doc_ids}, fh, protocol=4)
        self._index_file = path

    def load(self, index_dir: str) -> bool:
        path = os.path.join(index_dir, "bm25.pkl")
        if not os.path.exists(path):
            return False
        with open(path, "rb") as fh:
            data = pickle.load(fh)
        self.bm25 = data["bm25"]
        self.doc_ids = data["doc_ids"]
        self._index_file = path
        logger.info("BM25 index loaded from %s (%d docs)", path, len(self.doc_ids))
        return True

    def search(self, query: str, top_k: int) -> List[Tuple[str, float]]:
        """Return [(document_id, raw_bm25_score)] sorted descending."""
        if self.bm25 is None:
            return []
        scores = self.bm25.get_scores(tokenize(query))
        ranked = sorted(
            ((self.doc_ids[i], float(scores[i])) for i in range(len(scores))),
            key=lambda x: x[1],
            reverse=True,
        )
        return ranked[:top_k]

    def search_scores(self, query: str, top_k: int) -> Dict[str, float]:
        return dict(self.search(query, top_k))

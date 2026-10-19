"""Hybrid retrieval: fuses BM25 and dense rankings.

Two fusion strategies:
- RRF (Reciprocal Rank Fusion): rank-based, robust to incompatible score scales.
- Weighted normalized scores: min-max normalisation then weighted sum.
"""
from __future__ import annotations

from typing import Dict, List, Tuple

EPS = 1e-9


def _minmax(scores: Dict[str, float]) -> Dict[str, float]:
    if not scores:
        return {}
    lo, hi = min(scores.values()), max(scores.values())
    rng = hi - lo
    if rng < EPS:
        return {k: 0.0 for k in scores}
    return {k: (v - lo) / rng for k, v in scores.items()}


def rrf_fuse(
    bm25_ranked: List[Tuple[str, float]],
    dense_ranked: List[Tuple[str, float]],
    top_k: int,
    k: int = 60,
    bm25_weight: float = 1.0,
    dense_weight: float = 1.0,
) -> List[Tuple[str, float]]:
    """Standard RRF: score = sum weight / (k + rank)."""
    fused: Dict[str, float] = {}
    for rank, (doc_id, _) in enumerate(bm25_ranked):
        fused[doc_id] = fused.get(doc_id, 0.0) + bm25_weight / (k + rank + 1)
    for rank, (doc_id, _) in enumerate(dense_ranked):
        fused[doc_id] = fused.get(doc_id, 0.0) + dense_weight / (k + rank + 1)
    ranked = sorted(fused.items(), key=lambda x: x[1], reverse=True)[:top_k]
    max_s = ranked[0][1] if ranked else 1.0
    return [(d, s / max_s if max_s > EPS else 0.0) for d, s in ranked]


def weighted_fuse(
    bm25_ranked: List[Tuple[str, float]],
    dense_ranked: List[Tuple[str, float]],
    top_k: int,
    bm25_weight: float = 1.0,
    dense_weight: float = 1.0,
) -> List[Tuple[str, float]]:
    """Weighted sum of min-max normalised scores."""
    b = _minmax(dict(bm25_ranked))
    d = _minmax(dict(dense_ranked))
    candidates = set(b) | set(d)
    fused = {
        c: bm25_weight * b.get(c, 0.0) + dense_weight * d.get(c, 0.0) for c in candidates
    }
    ranked = sorted(fused.items(), key=lambda x: x[1], reverse=True)[:top_k]
    return ranked


class HybridRetriever:
    """Combines BM25Store + DenseStore with a configurable fusion strategy."""

    def __init__(self, bm25_store, dense_store, use_rrf: bool = True,
                 bm25_weight: float = 1.0, dense_weight: float = 1.0) -> None:
        self.bm25 = bm25_store
        self.dense = dense_store
        self.use_rrf = use_rrf
        self.bm25_weight = bm25_weight
        self.dense_weight = dense_weight

    @property
    def ready(self) -> bool:
        return self.bm25.ready and self.dense.ready

    def search(self, query: str, top_k: int, method: str = "hybrid") -> List[Tuple[str, float]]:
        if method == "bm25":
            return self.bm25.search(query, top_k)
        if method == "dense":
            return self.dense.search(query, top_k)
        # hybrid: over-fetch from both, then fuse
        fetch = max(top_k * 3, 30)
        bm25_hits = self.bm25.search(query, fetch)
        dense_hits = self.dense.search(query, fetch)
        fuse = rrf_fuse if self.use_rrf else weighted_fuse
        return fuse(bm25_hits, dense_hits, top_k, self.bm25_weight, self.dense_weight)

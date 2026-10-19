"""Unit tests for BM25, dense (hashing backend), and hybrid fusion."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.retrieval.bm25_store import BM25Store, tokenize
from app.retrieval.hybrid import rrf_fuse, weighted_fuse

from conftest import CORPUS


def test_tokenize_lowercase_and_stops():
    assert tokenize("The Eiffel Tower is in Paris") == ["eiffel", "tower", "paris"]


def test_bm25_retrieval(index_dir):
    bm25 = BM25Store()
    assert bm25.load(index_dir)
    hits = bm25.search("Eiffel Tower Gustave Eiffel", 3)
    assert len(hits) >= 2
    assert hits[0][0] == "Eiffel Tower::L0"
    assert all(isinstance(s, float) for _, s in hits)


def test_dense_retrieval_hashing(index_dir):
    from app.retrieval.dense_store import DenseStore

    dense = DenseStore("offline-test", backend="hashing")
    assert dense.load(index_dir)
    hits = dense.search("Nikola Tesla patents", 3)
    assert len(hits) >= 1
    assert hits[0][0] in ("Nikola Tesla::L1", "Nikola Tesla::L0")


def test_rrf_fusion_prefers_docs_in_both_lists():
    bm25 = [("a", 5.0), ("b", 4.0), ("c", 1.0)]
    dense = [("b", 0.9), ("a", 0.8), ("d", 0.3)]
    fused = rrf_fuse(bm25, dense, top_k=2)
    ids = [d for d, _ in fused]
    assert ids[0] in ("a", "b")
    # scores normalized to (0, 1]
    assert all(0 < s <= 1.0 for _, s in fused)


def test_weighted_fusion():
    bm25 = [("a", 5.0), ("b", 4.0), ("c", 1.0)]
    dense = [("b", 0.9), ("c", 0.5), ("a", 0.1)]
    fused = dict(weighted_fuse(bm25, dense, top_k=3))
    # b is strong in both; a strong in bm25 only; c weak everywhere
    assert fused["b"] > fused["a"] > fused["c"]

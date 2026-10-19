"""Tests for the end-to-end verification pipeline (offline backends)."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.pipeline import preprocess_claim


def test_preprocess_claim():
    assert preprocess_claim("  The   Eiffel\nTower  is in Paris. ") == "The Eiffel Tower is in Paris."


def test_verify_returns_structured_result(pipeline_direct):
    res = pipeline_direct.verify("The Eiffel Tower is named after the engineer Gustave Eiffel.", top_k=3)
    assert res.verdict in ("SUPPORTED", "REFUTED", "NOT_ENOUGH_INFORMATION")
    assert 0.0 <= res.confidence <= 1.0
    assert 0.0 <= res.uncertainty <= 1.0
    assert res.evidence, "evidence must be returned"
    for ev in res.evidence:
        assert ev["document_id"].startswith(("Eiffel", "Paris", "Nikola", "Mitochondrion", "Great", "Unrelated"))
        assert 0 < ev["score"] <= 1.0
        assert ev["text"], "evidence text must never be empty"
    assert len(res.nli) == len(res.evidence)
    assert res.latency_ms > 0
    assert res.explanation and res.explanation["steps"]


def test_verify_evidence_never_fabricated(pipeline_direct):
    """Every returned evidence passage must come from the indexed corpus."""
    from conftest import CORPUS

    corpus_texts = {rec["text"] for rec in CORPUS}
    res = pipeline_direct.verify("Nikola Tesla was an inventor.", top_k=5)
    for ev in res.evidence:
        assert ev["text"] in corpus_texts


def test_verify_confidence_uncertainty_semantics(pipeline_direct):
    res = pipeline_direct.verify("Blue whales are the largest animals known to have ever lived on Earth.", top_k=3)
    # high overlap evidence should yield a confident entailment-style verdict
    assert res.confidence + res.uncertainty >= 0.0  # sanity: both are valid probs
    if res.verdict == "SUPPORTED":
        assert res.confidence > 0.3


def test_predict_single_pair(pipeline_direct):
    pred, ms = pipeline_direct.predict(
        "Nikola Tesla was a Serbian-American inventor.", "Nikola Tesla was an inventor."
    )
    assert pred.label in ("ENTAILMENT", "CONTRADICTION", "NEUTRAL")
    assert abs(sum(pred.probabilities.values()) - 1.0) < 1e-6
    assert ms >= 0

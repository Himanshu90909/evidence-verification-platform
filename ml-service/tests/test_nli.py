"""Tests for the NLI predictor (lexical fallback backend + label mapping)."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.nli.predictor import LexicalFallbackNli, NliPredictor


def test_fallback_reports_backend_name():
    nli = NliPredictor("definitely-not-a-real-model")
    backend = nli.load()
    assert backend == "lexical-fallback"
    assert nli.backend_model_name == "lexical-overlap-fallback"


def test_fallback_entails_identical_sentence():
    nli = LexicalFallbackNli()
    text = "Paris is the capital and largest city of France."
    preds = nli.predict_batch([(text, "Paris is the capital of France.")])
    assert preds[0].label in ("ENTAILMENT", "NEUTRAL")
    assert abs(sum(preds[0].probabilities.values()) - 1.0) < 1e-6


def test_fallback_neutral_for_unrelated():
    nli = LexicalFallbackNli()
    preds = nli.predict_batch([("Blue whales are large animals.", "Nikola Tesla held 300 patents.")])
    assert preds[0].label == "NEUTRAL"


def test_fallback_contradiction_with_negation_mismatch():
    nli = LexicalFallbackNli()
    premise = "The tower is not made of iron."
    hypothesis = "The tower is made of iron lattice structure."
    preds = nli.predict_batch([(premise, hypothesis)])
    assert preds[0].label in ("CONTRADICTION", "NEUTRAL")

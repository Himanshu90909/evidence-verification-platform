"""NLI (Natural Language Inference) predictor.

Primary backend: HuggingFace sequence-classification transformers
(e.g. cross-encoder/nli-deberta-v3-small), premise=evidence, hypothesis=claim.

Fallback backend: an interpretable lexical-overlap scorer used ONLY when the
transformer model cannot be loaded (offline / constrained environments).
It never fabricates evidence - it only scores evidence texts that were
actually retrieved, and it reports itself as `lexical-fallback` so every
prediction records which backend produced it.
"""
from __future__ import annotations

import logging
import math
import time
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger("evp.nli")

LABELS = ("ENTAILMENT", "CONTRADICTION", "NEUTRAL")

_NEGATION_CUES = {
    "not", "no", "never", "none", "n't", "cannot", "without", "neither",
    "nor", "isn't", "wasn't", "aren't", "doesn't", "didn't", "won't",
}


@dataclass
class NliPrediction:
    label: str
    probabilities: Dict[str, float]


class TransformerNli:
    """Sequence-classification NLI via transformers."""

    def __init__(self, model_name: str) -> None:
        self.model_name = model_name
        self.backend = "transformers"
        self.id2label: Dict[int, str] = {}
        self._model = None
        self._tokenizer = None

    def load(self) -> bool:
        try:
            import torch
            from transformers import AutoModelForSequenceClassification, AutoTokenizer

            self._tokenizer = AutoTokenizer.from_pretrained(self.model_name)
            self._model = AutoModelForSequenceClassification.from_pretrained(self.model_name)
            self._model.eval()
            self.id2label = {
                int(k): str(v).upper() for k, v in self._model.config.id2label.items()
            }
            logger.info("NLI model loaded: %s (id2label=%s)", self.model_name, self.id2label)
            return True
        except Exception as exc:  # pragma: no cover - depends on network/GPU
            logger.warning("Could not load NLI model %s: %s", self.model_name, exc)
            self._model = None
            return False

    @property
    def ready(self) -> bool:
        return self._model is not None

    @staticmethod
    def _map_label(raw: str) -> str:
        raw = raw.upper()
        if "ENTAIL" in raw:
            return "ENTAILMENT"
        if "CONTRADICTION" in raw or "CONTRADICT" in raw:
            return "CONTRADICTION"
        return "NEUTRAL"

    def _prob_vector(self, logits_row, temperature: float) -> Dict[str, float]:
        """Softmax with temperature over the model's raw logits."""
        import torch

        scaled = logits_row / max(temperature, 1e-6)
        probs = torch.softmax(scaled, dim=-1).tolist()
        out: Dict[str, float] = {"ENTAILMENT": 0.0, "CONTRADICTION": 0.0, "NEUTRAL": 0.0}
        for idx, p in enumerate(probs):
            out[self._map_label(self.id2label.get(idx, str(idx)))] += float(p)
        return out

    def predict_batch(
        self, pairs: List[Tuple[str, str]], temperature: float = 1.0, batch_size: int = 16
    ) -> List[NliPrediction]:
        import torch

        results: List[NliPrediction] = []
        with torch.inference_mode():
            for start in range(0, len(pairs), batch_size):
                batch = pairs[start : start + batch_size]
                enc = self._tokenizer(
                    [p for p, _ in batch],
                    [h for _, h in batch],
                    padding=True,
                    truncation=True,
                    max_length=384,
                    return_tensors="pt",
                )
                logits = self._model(**enc).logits
                for row in logits:
                    probs = self._prob_vector(row, temperature)
                    label = max(probs, key=probs.get)  # type: ignore[arg-type]
                    results.append(NliPrediction(label=label, probabilities=probs))
        return results


class LexicalFallbackNli:
    """Deterministic fallback scorer (see module docstring)."""

    def __init__(self) -> None:
        self.backend = "lexical-fallback"
        self.model_name = "lexical-overlap-fallback"

    @property
    def ready(self) -> bool:
        return True

    def load(self) -> bool:  # pragma: no cover - trivial
        return True

    @staticmethod
    def _tokens(text: str) -> set:
        import re
        return set(re.findall(r"[a-z0-9]+", text.lower()))

    def predict_batch(
        self, pairs: List[Tuple[str, str]], temperature: float = 1.0, batch_size: int = 16
    ) -> List[NliPrediction]:
        from app.retrieval.bm25_store import tokenize

        results: List[NliPrediction] = []
        for premise, hypothesis in pairs:
            ev = set(tokenize(premise))
            cl = set(tokenize(hypothesis))
            if not cl:
                results.append(NliPrediction("NEUTRAL", {"ENTAILMENT": 0.1, "CONTRADICTION": 0.1, "NEUTRAL": 0.8}))
                continue
            overlap = len(ev & cl) / len(cl)
            neg_ev = bool(ev & _NEGATION_CUES)
            neg_cl = bool(cl & _NEGATION_CUES)
            if overlap >= 0.6 and neg_ev == neg_cl:
                probs = {"ENTAILMENT": 0.5 + 0.4 * overlap, "CONTRADICTION": 0.1, "NEUTRAL": 0.0}
            elif overlap >= 0.5 and neg_ev != neg_cl:
                probs = {"ENTAILMENT": 0.1, "CONTRADICTION": 0.5 + 0.3 * overlap, "NEUTRAL": 0.1}
            else:
                probs = {"ENTAILMENT": 0.15, "CONTRADICTION": 0.15, "NEUTRAL": 0.7}
            s = sum(probs.values())
            probs = {k: v / s for k, v in probs.items()}
            label = max(probs, key=probs.get)  # type: ignore[arg-type]
            results.append(NliPrediction(label=label, probabilities=probs))
        return results


class NliPredictor:
    """Facade: transformer backend with automatic lexical fallback."""

    def __init__(self, model_name: str) -> None:
        self.transformer = TransformerNli(model_name)
        self.fallback = LexicalFallbackNli()
        self._active = None

    def load(self) -> str:
        if self.transformer.load():
            self._active = self.transformer
        else:
            self._active = self.fallback
        return self.backend_name

    @property
    def backend_name(self) -> str:
        if self._active is None:
            return "not-loaded"
        return self._active.backend

    @property
    def backend_model_name(self) -> str:
        if self._active is None:
            return self.transformer.model_name
        return getattr(self._active, "model_name", self.transformer.model_name)

    @property
    def ready(self) -> bool:
        return self._active is not None and self._active.ready

    def predict_batch(self, pairs, temperature: float = 1.0) -> List[NliPrediction]:
        assert self._active is not None, "NLI predictor not loaded"
        return self._active.predict_batch(pairs, temperature=temperature)

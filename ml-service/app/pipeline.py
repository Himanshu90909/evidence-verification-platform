"""End-to-end verification pipeline.

claim -> BM25 retrieval -> dense retrieval -> hybrid fusion -> NLI-based
evidence reranking -> multi-evidence weighted aggregation -> uncertainty
estimation -> verdict.

Every stage is timed and observable; no stage ever invents evidence: all
returned passages come from the indexed research corpus.
"""
from __future__ import annotations

import logging
import math
import re
import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

from app.evidence_store import EvidenceDoc, EvidenceStore
from app.monitoring import metrics
from app.nli.predictor import LABELS, NliPrediction, NliPredictor
from app.retrieval.bm25_store import BM25Store
from app.retrieval.dense_store import DenseStore
from app.retrieval.hybrid import HybridRetriever

logger = logging.getLogger("evp.pipeline")

_WS_RE = re.compile(r"\s+")


def preprocess_claim(claim: str) -> str:
    return _WS_RE.sub(" ", claim).strip()


@dataclass
class PipelineResult:
    claim: str
    verdict: str
    confidence: float
    uncertainty: float
    retrieval_method: str
    top_k: int
    latency_ms: float
    evidence: List[Dict] = field(default_factory=list)
    nli: List[Dict] = field(default_factory=list)
    stage_latencies_ms: Dict[str, float] = field(default_factory=dict)
    explanation: Optional[Dict] = None


class VerificationPipeline:
    def __init__(
        self,
        evidence_store: EvidenceStore,
        bm25: BM25Store,
        dense: DenseStore,
        nli: NliPredictor,
        top_k: int = 5,
        use_rrf: bool = True,
        bm25_weight: float = 1.0,
        dense_weight: float = 1.0,
        temperature: float = 1.0,
        min_evidence_prob: float = 0.35,
    ) -> None:
        self.store = evidence_store
        self.retriever = HybridRetriever(bm25, dense, use_rrf, bm25_weight, dense_weight)
        self.bm25 = bm25
        self.dense = dense
        self.nli = nli
        self.top_k = top_k
        self.temperature = temperature
        self.min_evidence_prob = min_evidence_prob

    @property
    def ready(self) -> bool:
        return self.store.loaded and self.retriever.ready and self.nli.ready

    # ------------------------------------------------------------------ retrieval
    def retrieve(self, claim: str, top_k: int, method: str = "hybrid"):
        t0 = time.perf_counter()
        hits = self.retriever.search(claim, top_k, method=method)
        lat_ms = (time.perf_counter() - t0) * 1000
        metrics.observe_latency("retrieval", lat_ms)
        return hits, lat_ms

    # ------------------------------------------------------------------ verify
    def verify(self, claim: str, top_k: Optional[int] = None, return_evidence: bool = True, method: str = "hybrid") -> PipelineResult:
        t_start = time.perf_counter()
        top_k = top_k or self.top_k
        claim = preprocess_claim(claim)

        # 1-2) hybrid retrieval (BM25 + dense + fusion)
        hits, retrieval_ms = self.retrieve(claim, top_k * 2, method=method)
        if not hits:
            return PipelineResult(
                claim=claim, verdict="NOT_ENOUGH_INFORMATION", confidence=0.0,
                uncertainty=1.0, retrieval_method="hybrid", top_k=top_k,
                latency_ms=(time.perf_counter() - t_start) * 1000,
                evidence=[], nli=[],
                explanation={"reason": "No evidence retrieved from the corpus."},
            )
        candidates = hits[: top_k * 2]  # rerank pool

        docs: List[EvidenceDoc] = []
        weights: List[float] = []
        raw_scores: Dict[str, Dict[str, float]] = {}
        for rank, (doc_id, score) in enumerate(candidates):
            d = self.store.get(doc_id)
            if d is None:
                continue
            docs.append(d)
            weights.append(max(score, 1e-6))
            raw_scores[doc_id] = {"fused": score}
            raw_scores[doc_id]["rank_in_fusion"] = rank

        # 3) NLI scoring = evidence reranking signal
        t0 = time.perf_counter()
        pairs = [(d.text, claim) for d in docs]
        preds: List[NliPrediction] = self.nli.predict_batch(pairs, temperature=self.temperature)
        nli_ms = (time.perf_counter() - t0) * 1000
        metrics.observe_latency("nli", nli_ms)

        # rerank by entailment prob, keep top_k for the final decision
        scored = sorted(
            zip(docs, weights, preds),
            key=lambda t: (t[2].probabilities["ENTAILMENT"] + t[2].probabilities["CONTRADICTION"], t[1]),
            reverse=True,
        )[:top_k]

        # 4) multi-evidence weighted aggregation
        w_sum = sum(w for _, w, _ in scored) or 1.0
        claim_probs = {l: 0.0 for l in LABELS}
        for d, w, p in scored:
            for label in LABELS:
                claim_probs[label] += (w / w_sum) * p.probabilities[label]

        # 5) decision + uncertainty
        ent, con, neu = claim_probs["ENTAILMENT"], claim_probs["CONTRADICTION"], claim_probs["NEUTRAL"]
        if ent < self.min_evidence_prob and con < self.min_evidence_prob:
            verdict = "NOT_ENOUGH_INFORMATION"
            confidence = max(ent, con, neu)
        else:
            verdict = "SUPPORTED" if ent >= con else "REFUTED"
            confidence = max(ent, con)
        entropy = -sum(p * math.log(p + 1e-12) for p in (ent, con, neu))
        uncertainty = min(entropy / math.log(3.0), 1.0)

        # 6) build evidence payload (real documents, real scores)
        evidence_out: List[Dict] = []
        nli_out: List[Dict] = []
        top_ids = set()
        for i, (d, w, p) in enumerate(scored):
            top_ids.add(d.document_id)
            evidence_out.append(
                {
                    "document_id": d.document_id,
                    "text": d.text,
                    "score": round(w, 4),
                    "source": d.source_name,
                    "source_url": d.source_url,
                    "page": d.page,
                    "line_id": d.line_id,
                    "rank": i + 1,
                }
            )
            nli_out.append(
                {
                    "document_id": d.document_id,
                    "label": p.label,
                    "probabilities": {k: round(v, 4) for k, v in p.probabilities.items()},
                    "is_top_evidence": i == 0,
                }
            )

        total_ms = (time.perf_counter() - t_start) * 1000
        metrics.observe_latency("total", total_ms)
        metrics.observe_verdict(verdict, confidence, preds[0].label if preds else "NEUTRAL")

        explanation = self._explain(claim_probs, scored, verdict, confidence, uncertainty)

        return PipelineResult(
            claim=claim,
            verdict=verdict,
            confidence=round(confidence, 4),
            uncertainty=round(uncertainty, 4),
            retrieval_method="hybrid",
            top_k=top_k,
            latency_ms=round(total_ms, 2),
            evidence=evidence_out if return_evidence else [],
            nli=nli_out,
            stage_latencies_ms={"retrieval": round(retrieval_ms, 2), "nli": round(nli_ms, 2)},
            explanation=explanation,
        )

    # ------------------------------------------------------------------ explain
    def _explain(self, claim_probs, scored, verdict, confidence, uncertainty) -> Dict:
        ent, con, neu = (claim_probs[l] for l in LABELS)
        steps = [
            "Claim preprocessed and normalized.",
            "BM25 and dense retrieval executed; results fused (hybrid).",
            "Each retrieved passage scored by NLI (premise=evidence, hypothesis=claim).",
            "Evidence reranked by NLI informativeness; top evidence aggregated with retrieval-score weights.",
            f"Aggregated support={ent:.3f}, refute={con:.3f}, neutral={neu:.3f}.",
        ]
        if verdict == "NOT_ENOUGH_INFORMATION":
            steps.append(
                f"Neither support nor refute mass reached the evidence threshold "
                f"({self.min_evidence_prob}); verdict: NOT ENOUGH INFORMATION."
            )
        else:
            steps.append(f"Verdict: {verdict} (confidence {confidence:.3f}).")
        top_evidence = scored[0][0] if scored else None
        top_pred = scored[0][2] if scored else None
        return {
            "steps": steps,
            "aggregated_probabilities": {k: round(v, 4) for k, v in claim_probs.items()},
            "top_evidence_id": top_evidence.document_id if top_evidence else None,
            "top_evidence_nli": top_pred.label if top_pred else None,
            "uncertainty_measure": "normalized entropy of aggregated 3-class distribution",
        }

    def predict(self, premise: str, hypothesis: str) -> Tuple[NliPrediction, float]:
        t0 = time.perf_counter()
        preds = self.nli.predict_batch([(preprocess_claim(premise), preprocess_claim(hypothesis))], self.temperature)
        ms = (time.perf_counter() - t0) * 1000
        metrics.observe_latency("nli", ms)
        return preds[0], round(ms, 2)

"""Pydantic request/response models - the API contract for the ML service."""
from __future__ import annotations

from typing import Dict, List, Literal, Optional

from pydantic import BaseModel, Field, field_validator

Verdict = Literal["SUPPORTED", "REFUTED", "NOT_ENOUGH_INFORMATION"]
NliLabel = Literal["ENTAILMENT", "CONTRADICTION", "NEUTRAL"]


class VerifyRequest(BaseModel):
    claim: str = Field(..., min_length=3, max_length=2000, description="Natural-language claim to verify")
    top_k: Optional[int] = Field(default=None, ge=1, le=20)
    return_evidence: bool = Field(default=True, description="Include evidence passages in the response")

    @field_validator("claim")
    @classmethod
    def claim_not_blank(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("claim must not be blank")
        return v.strip()


class RetrieveRequest(BaseModel):
    query: str = Field(..., min_length=2, max_length=2000)
    top_k: int = Field(default=5, ge=1, le=50)
    method: Literal["bm25", "dense", "hybrid"] = "hybrid"


class PredictRequest(BaseModel):
    premise: str = Field(..., min_length=1, max_length=8000, description="Evidence text")
    hypothesis: str = Field(..., min_length=1, max_length=2000, description="Claim")
    with_scores: bool = True


class ExplainRequest(BaseModel):
    claim: str = Field(..., min_length=3, max_length=2000)
    top_k: int = Field(default=5, ge=1, le=20)
    decision_threshold: float = Field(default=0.5, ge=0.0, le=1.0)


class Evidence(BaseModel):
    document_id: str
    text: str
    score: float = Field(..., description="Fused retrieval score in [0, 1] (higher = more relevant)")
    source: Optional[str] = None
    source_url: Optional[str] = None
    bm25_score: Optional[float] = None
    dense_score: Optional[float] = None
    nli_label: Optional[str] = None
    rank: int


class NliResult(BaseModel):
    document_id: str
    label: NliLabel
    probabilities: Dict[str, float]
    is_top_evidence: bool = False


class RetrievalMeta(BaseModel):
    method: str
    top_k: int
    latency_ms: float
    n_documents_searched: int


class ModelMeta(BaseModel):
    model: str
    version: str
    embedding_model: str
    retriever: str
    nli_model: str
    nli_backend: str
    temperature: float
    config_hash: str
    timestamp: Optional[str] = None


class VerifyResponse(BaseModel):
    claim: str
    verdict: Verdict
    confidence: float = Field(..., ge=0.0, le=1.0)
    uncertainty: float = Field(..., ge=0.0, le=1.0)
    retrieval: RetrievalMeta
    evidence: List[Evidence]
    nli: List[NliResult]
    model: ModelMeta
    latency_ms: float
    explanation: Optional[Dict] = None


class RetrieveResponse(BaseModel):
    query: str
    retrieval: RetrievalMeta
    evidence: List[Evidence]
    model: ModelMeta


class PredictResponse(BaseModel):
    label: NliLabel
    probabilities: Dict[str, float]
    model: ModelMeta
    latency_ms: float


class ExplainResponse(BaseModel):
    claim: str
    verdict: Verdict
    confidence: float
    uncertainty: float
    decision_path: List[str]
    per_evidence: List[NliResult]
    evidence: List[Evidence]
    model: ModelMeta


class HealthResponse(BaseModel):
    status: Literal["ok", "degraded", "loading", "error"]
    nli_backend: str
    retrieval_backend: str
    corpus_loaded: bool
    corpus_documents: int
    uptime_seconds: float
    detail: Optional[str] = None


class ModelInfoResponse(BaseModel):
    service_version: str
    pipeline: ModelMeta
    corpus_documents: int
    metrics: Dict


class ErrorDetail(BaseModel):
    error: str
    detail: Optional[str] = None
    request_id: Optional[str] = None

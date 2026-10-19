"""Evidence Verification Platform - ML inference service (FastAPI).

Endpoints:
    POST /verify       full claim verification pipeline
    POST /retrieve     hybrid evidence retrieval
    POST /predict      single premise/hypothesis NLI prediction
    POST /explain      decision-path explanation for a claim
    GET  /health       liveness/readiness
    GET  /model-info   model card + live service metrics
    GET  /metrics      Prometheus text format metrics

All endpoints (except /health and /metrics) require service authentication
via X-API-Key or `Authorization: Bearer <key>`.
"""
from __future__ import annotations

import logging
import os
import uuid
from contextlib import asynccontextmanager
from typing import Optional

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import PlainTextResponse

import app.config as config
from app.evidence_store import EvidenceStore
from app.monitoring import Metrics, metrics
from app.nli.predictor import NliPredictor
from app.pipeline import VerificationPipeline
from app.retrieval.bm25_store import BM25Store
from app.retrieval.dense_store import DenseStore
from app.schemas import (
    ErrorDetail, ExplainRequest, ExplainResponse, HealthResponse, ModelInfoResponse,
    PredictRequest, PredictResponse, RetrieveRequest, RetrieveResponse,
    VerifyRequest, VerifyResponse,
)
from app.security import require_api_key
from app.versioning import model_info

logging.basicConfig(
    level=os.environ.get("LOG_LEVEL", "INFO"),
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
logger = logging.getLogger("evp.service")

settings = config.get_settings()

store = EvidenceStore()
bm25_store = BM25Store()
dense_store = DenseStore(settings.embedding_model, backend=settings.dense_backend)
nli_predictor = NliPredictor(settings.nli_model)
pipeline: Optional[VerificationPipeline] = None
service_state = {"status": "loading", "detail": None}


def _load_backends() -> None:
    global pipeline
    logger.info("Loading corpus and indexes ...")
    if os.path.exists(settings.corpus_path):
        store.load(settings.corpus_path)
    else:
        logger.warning("Corpus not found at %s - service starts degraded.", settings.corpus_path)

    index_dir = settings.index_dir
    bm25_ok = bm25_store.load(index_dir)
    dense_ok = dense_store.load(index_dir)

    if store.loaded and not (bm25_ok and dense_ok):
        logger.info("Indexes missing/incomplete - building from corpus ...")
        if not bm25_ok:
            bm25_store.build([d.document_id for d in store.docs], [d.text for d in store.docs])
            bm25_store.save(index_dir)
        if not dense_ok:
            try:
                dense_store.build([d.document_id for d in store.docs], [d.text for d in store.docs])
                dense_store.save(index_dir)
            except Exception as exc:
                logger.warning("Dense index build failed: %s", exc)

    nli_backend = nli_predictor.load()
    logger.info("NLI backend: %s", nli_backend)

    pipeline = VerificationPipeline(
        evidence_store=store,
        bm25=bm25_store,
        dense=dense_store,
        nli=nli_predictor,
        top_k=settings.top_k,
        use_rrf=settings.use_rrf,
        bm25_weight=settings.bm25_weight,
        dense_weight=settings.dense_weight,
        temperature=settings.temperature,
        min_evidence_prob=settings.min_evidence_prob,
    )
    if pipeline.ready:
        service_state.update({"status": "ok", "detail": None})
    else:
        degraded = []
        if not store.loaded:
            degraded.append("corpus missing")
        if not bm25_store.ready:
            degraded.append("bm25 index missing")
        if not dense_store.ready:
            degraded.append("dense index missing")
        if not nli_predictor.ready:
            degraded.append("nli backend missing")
        service_state.update({"status": "degraded", "detail": ", ".join(degraded)})
        logger.warning("Service degraded: %s", service_state["detail"])


@asynccontextmanager
async def lifespan(app: FastAPI):
    _load_backends()
    logger.info("ML service ready (status=%s)", service_state["status"])
    yield


app = FastAPI(
    title="Evidence Verification Platform - ML Service",
    version="1.0.0",
    description="Hybrid retrieval + NLI claim verification over a FEVER-derived evidence corpus.",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=False,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["X-API-Key", "Authorization", "Content-Type"],
)


@app.get("/health", response_model=HealthResponse, tags=["service"])
def health() -> HealthResponse:
    return HealthResponse(
        status=service_state["status"],
        nli_backend=nli_predictor.backend_name,
        retrieval_backend="bm25+dense" if (bm25_store.ready and dense_store.ready) else "unavailable",
        corpus_loaded=store.loaded,
        corpus_documents=store.size,
        uptime_seconds=metrics.summary()["uptime_seconds"],  # type: ignore[index]
        detail=service_state["detail"],
    )


@app.get("/metrics", response_class=PlainTextResponse, include_in_schema=False)
def prometheus_metrics() -> str:
    return metrics.prometheus()


def _model_meta():
    active = {
        "nli_backend": nli_predictor.backend_name,
        "nli_model": nli_predictor.backend_model_name,
        "corpus_documents": store.size,
    }
    info = model_info(settings, active)
    info["timestamp"] = None
    from app.schemas import ModelMeta

    return ModelMeta(**{k: v for k, v in info.items() if k in ModelMeta.model_fields})


@app.get("/model-info", response_model=ModelInfoResponse, tags=["service"])
def get_model_info(_: str = Depends(require_api_key)) -> ModelInfoResponse:
    return ModelInfoResponse(
        service_version="1.0.0",
        pipeline=_model_meta(),
        corpus_documents=store.size,
        metrics=metrics.summary(),
    )


@app.post("/verify", response_model=VerifyResponse, tags=["verification"])
def verify(req: VerifyRequest, _: str = Depends(require_api_key)) -> VerifyResponse:
    if pipeline is None or not pipeline.ready:
        raise HTTPException(status_code=503, detail=f"Pipeline not ready: {service_state['detail']}")
    metrics.observe_request()
    result = pipeline.verify(req.claim, top_k=req.top_k, return_evidence=req.return_evidence)
    nli_by_doc = {n["document_id"]: n["label"] for n in result.nli}
    evidence_out = [
        {**ev, "nli_label": nli_by_doc.get(ev["document_id"])}
        for ev in result.evidence
    ]
    return VerifyResponse(
        claim=result.claim,
        verdict=result.verdict,  # type: ignore[arg-type]
        confidence=result.confidence,
        uncertainty=result.uncertainty,
        retrieval={
            "method": result.retrieval_method,
            "top_k": result.top_k,
            "latency_ms": result.stage_latencies_ms.get("retrieval", 0.0),
            "n_documents_searched": store.size,
        },
        evidence=evidence_out,  # type: ignore[arg-type]
        nli=result.nli,  # type: ignore[arg-type]
        model=_model_meta(),
        latency_ms=result.latency_ms,
        explanation=result.explanation,
    )


@app.post("/retrieve", response_model=RetrieveResponse, tags=["verification"])
def retrieve(req: RetrieveRequest, _: str = Depends(require_api_key)) -> RetrieveResponse:
    if pipeline is None or not pipeline.ready:
        raise HTTPException(status_code=503, detail=f"Pipeline not ready: {service_state['detail']}")
    metrics.observe_request()
    from app.pipeline import preprocess_claim

    query = preprocess_claim(req.query)
    hits, lat_ms = pipeline.retrieve(query, req.top_k, method=req.method)
    evidence = []
    for rank, (doc_id, score) in enumerate(hits):
        d = store.get(doc_id)
        if d is None:
            continue
        evidence.append(
            {
                "document_id": doc_id,
                "text": d.text,
                "score": round(score, 4),
                "source": d.source_name,
                "source_url": d.source_url,
                "rank": rank + 1,
            }
        )
    return RetrieveResponse(
        query=query,
        retrieval={
            "method": req.method,
            "top_k": req.top_k,
            "latency_ms": round(lat_ms, 2),
            "n_documents_searched": store.size,
        },
        evidence=evidence,  # type: ignore[arg-type]
        model=_model_meta(),
    )


@app.post("/predict", response_model=PredictResponse, tags=["verification"])
def predict(req: PredictRequest, _: str = Depends(require_api_key)) -> PredictResponse:
    if pipeline is None or not pipeline.ready:
        raise HTTPException(status_code=503, detail=f"Pipeline not ready: {service_state['detail']}")
    metrics.observe_request()
    pred, ms = pipeline.predict(req.premise, req.hypothesis)
    return PredictResponse(
        label=pred.label,  # type: ignore[arg-type]
        probabilities={k: round(v, 4) for k, v in pred.probabilities.items()},
        model=_model_meta(),
        latency_ms=ms,
    )


@app.post("/explain", response_model=ExplainResponse, tags=["verification"])
def explain(req: ExplainRequest, _: str = Depends(require_api_key)) -> ExplainResponse:
    if pipeline is None or not pipeline.ready:
        raise HTTPException(status_code=503, detail=f"Pipeline not ready: {service_state['detail']}")
    metrics.observe_request()
    result = pipeline.verify(req.claim, top_k=req.top_k)
    explanation = result.explanation or {}
    return ExplainResponse(
        claim=result.claim,
        verdict=result.verdict,  # type: ignore[arg-type]
        confidence=result.confidence,
        uncertainty=result.uncertainty,
        decision_path=explanation.get("steps", []),
        per_evidence=result.nli,  # type: ignore[arg-type]
        evidence=result.evidence,  # type: ignore[arg-type]
        model=_model_meta(),
    )


@app.middleware("http")
async def observe_errors(request: Request, call_next):
    response = await call_next(request)
    if response.status_code >= 400:
        metrics.observe_request(error=True)
    return response


if __name__ == "__main__":  # pragma: no cover
    import uvicorn

    uvicorn.run("main:app", host=settings.host, port=int(settings.port), log_level=settings.log_level.lower())

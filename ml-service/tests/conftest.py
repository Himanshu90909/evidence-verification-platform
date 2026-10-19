"""Shared test fixtures: a tiny offline corpus + indexes + fallback NLI.

The API tests exercise the FULL production pipeline (BM25 + dense retrieval +
NLI + aggregation) using two test-only backends:
- dense backend 'hashing' (deterministic, no downloads)
- NLI model name that fails to load, falling back to the lexical scorer
"""
from __future__ import annotations

import json
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

TEST_DIR = os.path.dirname(os.path.abspath(__file__))
CORPUS = [
    {
        "document_id": "Paris::L0",
        "text": "Paris is the capital and largest city of France.",
        "page": "Paris",
        "line_id": 0,
        "source": {"name": "FEVER / Wikipedia (research corpus)", "url": "https://en.wikipedia.org/wiki/Paris"},
    },
    {
        "document_id": "Paris::L1",
        "text": "The Eiffel Tower is a wrought-iron lattice tower on the Champ de Mars in Paris, France.",
        "page": "Eiffel Tower",
        "line_id": 1,
        "source": {"name": "FEVER / Wikipedia (research corpus)", "url": "https://en.wikipedia.org/wiki/Eiffel_Tower"},
    },
    {
        "document_id": "Eiffel Tower::L0",
        "text": "The Eiffel Tower is named after the engineer Gustave Eiffel, whose company designed and built the tower.",
        "page": "Eiffel Tower",
        "line_id": 0,
        "source": {"name": "FEVER / Wikipedia (research corpus)", "url": "https://en.wikipedia.org/wiki/Eiffel_Tower"},
    },
    {
        "document_id": "Nikola Tesla::L0",
        "text": "Nikola Tesla was a Serbian-American inventor, electrical engineer and futurist.",
        "page": "Nikola Tesla",
        "line_id": 0,
        "source": {"name": "FEVER / Wikipedia (research corpus)", "url": "https://en.wikipedia.org/wiki/Nikola_Tesla"},
    },
    {
        "document_id": "Nikola Tesla::L1",
        "text": "Tesla obtained around 300 patents worldwide for his inventions.",
        "page": "Nikola Tesla",
        "line_id": 1,
        "source": {"name": "FEVER / Wikipedia (research corpus)", "url": "https://en.wikipedia.org/wiki/Nikola_Tesla"},
    },
    {
        "document_id": "Mitochondrion::L0",
        "text": "The mitochondrion is an organelle found in the cells of most eukaryotic organisms.",
        "page": "Mitochondrion",
        "line_id": 0,
        "source": {"name": "FEVER / Wikipedia (research corpus)", "url": "https://en.wikipedia.org/wiki/Mitochondrion"},
    },
    {
        "document_id": "Great Wall::L0",
        "text": "The Great Wall of China was not built in a single dynasty but over many centuries.",
        "page": "Great Wall of China",
        "line_id": 0,
        "source": {"name": "FEVER / Wikipedia (research corpus)", "url": "https://en.wikipedia.org/wiki/Great_Wall_of_China"},
    },
    {
        "document_id": "Unrelated::L0",
        "text": "Blue whales are the largest animals known to have ever lived on Earth.",
        "page": "Blue whale",
        "line_id": 0,
        "source": {"name": "FEVER / Wikipedia (research corpus)", "url": "https://en.wikipedia.org/wiki/Blue_whale"},
    },
]


@pytest.fixture(scope="session")
def corpus_path(tmp_path_factory):
    path = tmp_path_factory.mktemp("corpus") / "evidence_corpus.jsonl"
    with open(path, "w", encoding="utf-8") as fh:
        for rec in CORPUS:
            fh.write(json.dumps(rec) + "\n")
    return str(path)


@pytest.fixture(scope="session")
def index_dir(tmp_path_factory, corpus_path):
    index_dir = tmp_path_factory.mktemp("indexes")
    from app.retrieval.bm25_store import BM25Store
    from app.retrieval.dense_store import DenseStore

    ids = [rec["document_id"] for rec in CORPUS]
    texts = [rec["text"] for rec in CORPUS]
    bm25 = BM25Store()
    bm25.build(ids, texts)
    bm25.save(str(index_dir))
    dense = DenseStore("offline-test", backend="hashing")
    dense.build(ids, texts)
    dense.save(str(index_dir))
    return str(index_dir)


@pytest.fixture(scope="session")
def test_env(corpus_path, index_dir, monkeypatch_session):
    """Environment for the FastAPI app: offline backends, known API key."""
    monkeypatch_session.setenv("CORPUS_PATH", corpus_path)
    monkeypatch_session.setenv("INDEX_DIR", index_dir)
    monkeypatch_session.setenv("NLI_MODEL", "hf-internal-testing/tiny-random-nonexistent-nli-model")
    monkeypatch_session.setenv("EMBEDDING_MODEL", "offline-test")
    monkeypatch_session.setenv("DENSE_EMBEDDING_BACKEND", "hashing")
    monkeypatch_session.setenv("DENSE_BACKEND", "hashing")
    monkeypatch_session.setenv("ML_API_KEY", "test-api-key-123")
    monkeypatch_session.setenv("CORS_ORIGINS", "http://localhost:3000")
    return {"key": "test-api-key-123"}


import pytest


class _SessionMonkey:
    def __init__(self):
        self._undo = []

    def setenv(self, name, value):
        self._undo.append((name, os.environ.get(name)))
        os.environ[name] = value


@pytest.fixture(scope="session")
def monkeypatch_session():
    m = _SessionMonkey()
    yield m


@pytest.fixture(scope="session")
def client(test_env):
    """FastAPI TestClient with the app's lifespan executed."""
    from fastapi.testclient import TestClient

    import main as main_module

    # cached settings must be rebuilt with test env
    main_module.config.get_settings.cache_clear()
    main_module.settings = main_module.config.get_settings()

    with TestClient(main_module.app) as c:
        yield c


@pytest.fixture(scope="session")
def auth_headers(test_env):
    return {"X-API-Key": test_env["key"]}


@pytest.fixture(scope="session")
def pipeline_direct(corpus_path, index_dir):
    """Pipeline instance for direct (non-HTTP) tests."""
    from app.evidence_store import EvidenceStore
    from app.nli.predictor import NliPredictor
    from app.pipeline import VerificationPipeline
    from app.retrieval.bm25_store import BM25Store
    from app.retrieval.dense_store import DenseStore

    store = EvidenceStore()
    store.load(corpus_path)
    bm25 = BM25Store()
    assert bm25.load(index_dir)
    dense = DenseStore("offline-test", backend="hashing")
    assert dense.load(index_dir)
    nli = NliPredictor("hf-internal-testing/tiny-random-nonexistent-nli-model")
    backend = nli.load()
    assert backend == "lexical-fallback"
    return VerificationPipeline(evidence_store=store, bm25=bm25, dense=dense, nli=nli, top_k=3)

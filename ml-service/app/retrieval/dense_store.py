"""Dense retrieval: sentence-transformers embeddings + FAISS index."""
from __future__ import annotations

import logging
import os
import time
from typing import List, Optional, Tuple

import faiss
import numpy as np

logger = logging.getLogger("evp.dense")

try:  # heavy import, kept lazy-friendly
    from sentence_transformers import SentenceTransformer
except Exception:  # pragma: no cover - environments without the package
    SentenceTransformer = None  # type: ignore


class HashingEncoder:
    """Deterministic hashing embedder for tests/CI (no model download).

    Character-trigram hashing into a fixed-dimension vector, L2-normalised.
    Quality is far below a trained sentence transformer - it exists only so
    the full pipeline can be exercised offline in tests.
    """

    def __init__(self, dim: int = 256) -> None:
        self.dim = dim

    def get_embedding_dimension(self) -> int:
        return self.dim

    # sentence-transformers compatible signature
    get_sentence_embedding_dimension = get_embedding_dimension

    def encode(self, texts, normalize_embeddings: bool = True, show_progress_bar: bool = False, batch_size: int = 32):
        import hashlib

        out = np.zeros((len(texts), self.dim), dtype="float32")
        for i, text in enumerate(texts):
            lowered = text.lower()
            for j in range(len(lowered) - 2):
                gram = lowered[j : j + 3]
                h = int(hashlib.md5(gram.encode("utf-8")).hexdigest()[:8], 16)
                out[i, h % self.dim] += 1.0
            norm = np.linalg.norm(out[i])
            if norm > 0:
                out[i] /= norm
        return out


class DenseStore:
    def __init__(self, model_name: str, backend: str = "sbert") -> None:
        self.model_name = model_name
        self.backend = backend
        self.model = None  # SentenceTransformer or HashingEncoder
        self.index: Optional[faiss.IndexFlatIP] = None
        self.doc_ids: List[str] = []
        self._dim: Optional[int] = None

    @property
    def ready(self) -> bool:
        return self.index is not None and self.model is not None

    def load_model(self) -> None:
        if self.model is not None:
            return
        if self.backend == "hashing":
            logger.info("Using offline hashing embedder (tests/CI backend).")
            self.model = HashingEncoder()
            self._dim = self._dim_of()
            return
        if SentenceTransformer is None:
            return
        logger.info("Loading embedding model %s ...", self.model_name)
        self.model = SentenceTransformer(self.model_name)
        self._dim = self._dim_of()

    def embed_queries(self, texts: List[str]) -> np.ndarray:
        assert self.model is not None
        vecs = self.model.encode(
            texts, normalize_embeddings=True, show_progress_bar=False, batch_size=32
        )
        return np.asarray(vecs, dtype="float32")

    def _dim_of(self) -> int:
        get_dim = getattr(self.model, "get_embedding_dimension", None) or getattr(
            self.model, "get_sentence_embedding_dimension"
        )
        return int(get_dim())

    def build(self, doc_ids: List[str], texts: List[str], batch_size: int = 256) -> None:
        self.load_model()
        assert self.model is not None
        t0 = time.time()
        self.doc_ids = list(doc_ids)
        dim = self._dim_of()
        n = len(texts)
        index = faiss.IndexFlatIP(dim)
        for start in range(0, n, batch_size):
            batch = texts[start : start + batch_size]
            emb = self.model.encode(batch, normalize_embeddings=True, show_progress_bar=False)
            index.add(np.asarray(emb, dtype="float32"))
        self.index = index
        logger.info("FAISS index built over %d docs (dim=%d) in %.1fs", n, dim, time.time() - t0)

    def save(self, index_dir: str) -> None:
        if self.index is None:
            return
        os.makedirs(index_dir, exist_ok=True)
        faiss.write_index(self.index, os.path.join(index_dir, "dense.faiss"))
        with open(os.path.join(index_dir, "dense_doc_ids.txt"), "w", encoding="utf-8") as fh:
            fh.write("\n".join(self.doc_ids))

    def load(self, index_dir: str) -> bool:
        idx_path = os.path.join(index_dir, "dense.faiss")
        ids_path = os.path.join(index_dir, "dense_doc_ids.txt")
        if not (os.path.exists(idx_path) and os.path.exists(ids_path)):
            return False
        self.load_model()
        if self.model is None:
            logger.warning("Embedding model unavailable; cannot load FAISS index.")
            return False
        self.index = faiss.read_index(idx_path)
        with open(ids_path, "r", encoding="utf-8") as fh:
            self.doc_ids = [l for l in fh.read().split("\n") if l]
        logger.info("FAISS index loaded from %s (%d docs)", idx_path, len(self.doc_ids))
        return True

    def search(self, query: str, top_k: int) -> List[Tuple[str, float]]:
        if self.index is None or self.model is None:
            return []
        emb = self.embed_queries([query])
        k = min(top_k, self.index.ntotal)
        scores, idxs = self.index.search(emb, max(k, 1))
        out: List[Tuple[str, float]] = []
        for score, idx in zip(scores[0], idxs[0]):
            if idx < 0:
                continue
            out.append((self.doc_ids[idx], float(score)))
        return out[:top_k]

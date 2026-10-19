"""Build BM25 + FAISS dense indexes over the evidence corpus."""
from __future__ import annotations

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.retrieval.bm25_store import BM25Store
from app.retrieval.dense_store import DenseStore


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--corpus", required=True)
    ap.add_argument("--out", required=True, help="Index output directory")
    ap.add_argument("--embedding-model", default=os.environ.get(
        "EMBEDDING_MODEL", "sentence-transformers/all-MiniLM-L6-v2"))
    args = ap.parse_args()

    ids, texts = [], []
    with open(args.corpus, "r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            rec = json.loads(line)
            ids.append(rec["document_id"])
            texts.append(rec["text"])
    print(f"Loaded {len(ids)} documents from {args.corpus}")

    bm25 = BM25Store()
    bm25.build(ids, texts)
    bm25.save(args.out)
    print(f"BM25 index saved to {args.out}/bm25.pkl")

    dense = DenseStore(args.embedding_model)
    dense.build(ids, texts)
    dense.save(args.out)
    print(f"FAISS dense index saved to {args.out}/dense.faiss")

    meta = {
        "n_documents": len(ids),
        "embedding_model": args.embedding_model,
        "bm25": "rank_bm25.BM25Okapi",
        "dense": "faiss.IndexFlatIP (cosine, normalized)",
    }
    with open(os.path.join(args.out, "index_meta.json"), "w", encoding="utf-8") as fh:
        json.dump(meta, fh, indent=2)
    print("Index metadata written.")


if __name__ == "__main__":
    main()

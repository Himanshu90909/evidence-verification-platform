"""Build the FEVER/Wikipedia-derived evidence corpus (JSONL) for indexing.

Source: HuggingFace `copenlu/fever_gold_evidence` - the FEVER shared-task
dataset (claim, gold label, gold evidence sentences from Wikipedia).

We treat the UNION of gold evidence sentences across the train and
validation splits as the research knowledge corpus (mimicking the original
FEVER setup where the corpus is Wikipedia, independent of claim splits),
then hold out the validation CLAIMS for evaluation.

Output: one JSON object per line:
{"document_id": "Page::L31", "text": "...", "page": "Page", "line_id": 31,
 "source": {"name": "FEVER / Wikipedia (research corpus)",
            "url": "https://en.wikipedia.org/wiki/Page"}}
"""
from __future__ import annotations

import argparse
import json
import os
import random
from typing import Dict, Set


def wiki_url(page: str) -> str:
    return "https://en.wikipedia.org/wiki/" + page.strip().replace(" ", "_")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", required=True, help="Output corpus JSONL path")
    ap.add_argument("--max-docs", type=int, default=0, help="0 = no limit")
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--splits", default="train,validation")
    args = ap.parse_args()

    from datasets import load_dataset

    os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)

    seen: Set[str] = set()
    docs: Dict[str, dict] = {}
    for split in args.splits.split(","):
        ds = load_dataset("copenlu/fever_gold_evidence", split=split)
        for rec in ds:
            for ev in rec.get("evidence") or []:
                if len(ev) < 3 or not ev[2]:
                    continue
                page, line_id, text = str(ev[0]).strip(), int(ev[1]), str(ev[2]).strip()
                doc_id = f"{page}::L{line_id}"
                if doc_id in seen or not text:
                    continue
                seen.add(doc_id)
                docs[doc_id] = {
                    "document_id": doc_id,
                    "text": text,
                    "page": page,
                    "line_id": line_id,
                    "source": {
                        "name": "FEVER / Wikipedia (research corpus)",
                        "url": wiki_url(page),
                    },
                }

    ids = sorted(docs.keys())
    if args.max_docs and args.max_docs < len(ids):
        rng = random.Random(args.seed)
        ids = rng.sample(ids, args.max_docs)
        # keep sorted order for deterministic index alignment
        ids = sorted(ids)

    with open(args.out, "w", encoding="utf-8") as fh:
        for doc_id in ids:
            fh.write(json.dumps(docs[doc_id], ensure_ascii=False) + "\n")

    print(f"Corpus written: {len(ids)} documents -> {args.out}")


if __name__ == "__main__":
    main()
